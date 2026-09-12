"""Bulk transaction import — CSV upload (a generic equicast schema, plus
broker-specific presets such as Trading 212) parsed via
`equicast_core.imports.PRESETS`, reviewed by the user, then bulk-created
through the same validation/FX/rollup pipeline `TransactionListView.post`
(views.py) uses for a single hand-entered transaction.

Two-phase, stateless: `ImportPreviewView` (parse + resolve, nothing
persisted) then `ImportCommitView` (create/extend holdings and
transactions from the user's reviewed selections). Nothing here is kept
between the two calls server-side — the frontend holds the preview
response and posts back exactly what the user chose to import.

Only BUY/SELL rows ever reach a preview/commit payload — dividend/interest/
other non-trade rows are dropped by the parser itself (see
`equicast_core.imports` module docstring): equicast already auto-backfills
DIVIDEND transactions from paid-dividend history once a BUY/SELL position
exists (`sync_dividends_for_holdings`), so importing a broker's own
dividend rows would double-count them. A row that looked like a BUY/SELL
but couldn't be parsed (most commonly a real Trading 212 `Market sell` for
a fractional share cashed out after a corporate action, reported with a
`Price / share` of `0E-10`) never aborts the whole file — it's surfaced in
the preview response's `invalid_rows` instead (see
`equicast_core.imports.InvalidRow`), same principle as
`sync_dividends_for_holdings`. Corporate-action row types Trading 212 can
export (stock splits, spin-offs, stock acquisitions/ISIN changes,
share-based dividends) are recognized-but-not-trades — silently skipped,
counted in `rows_skipped` — rather than actually modeled as position
changes; see the transaction-import follow-up GitHub issues for each.

Matching an imported row to equicast's instrument catalog is ticker-based
only for now (`MarketDataClient.get_profile`) — ISIN-based matching (a
Trading 212 row's `isin` is parsed but currently unused beyond display) is
a deferred follow-up, see GitHub issue #191.

An AVERAGE-mode target holding that already has a position is *extended*
by a commit, not skipped or overwritten: the existing position and the
imported rows are recombined via `compute_holding_rollup`'s weighted-
average-cost math into one new totals, written back via
`update_transaction`. This has no re-upload dedup safety net the way
TRANSACTION mode's `external_id` tracking does — re-importing the same
export in AVERAGE mode will double-count shares; see GitHub issue #192.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from django.conf import settings
from equicast_core import (
    PRESETS,
    AccountNotFoundError,
    AccountsClient,
    AllocationError,
    HoldingAlreadyExistsError,
    HoldingLimitExceededError,
    HoldingNotFoundError,
    HoldingsClient,
    ImportParseError,
    InsufficientSharesError,
    MarketDataClient,
    PieNotFoundError,
    PiesClient,
    TransactionAmountError,
    TransactionLimitExceededError,
    TransactionsClient,
    UserProfileClient,
    compute_holding_rollup,
)
from identity.authentication import Auth0JWTAuthentication
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from transactions.views import (
    TRANSACTABLE_ASSET_CLASSES,
    _refresh_holding_rollup,
    resolve_converted_amounts,
)

#: One shared client per domain for the process, mirroring the module-level
#: `_client` pattern every other app's views.py uses.
_client = TransactionsClient(
    settings.USER_DATA_BUCKET,
    region_name=settings.AWS_REGION,
    max_transactions_for_holding=settings.MAX_TRANSACTIONS_FOR_HOLDING,
)
_holdings_client = HoldingsClient(
    settings.USER_DATA_BUCKET,
    region_name=settings.AWS_REGION,
    max_holdings_for_account=settings.MAX_HOLDINGS_FOR_ACCOUNT,
    max_holdings_for_pie=settings.MAX_HOLDINGS_FOR_PIE,
    max_holdings_for_watchlist=settings.MAX_HOLDINGS_FOR_WATCHLIST,
)
_accounts_client = AccountsClient(
    settings.USER_DATA_BUCKET, region_name=settings.AWS_REGION, max_accounts=settings.MAX_ACCOUNTS
)
_pies_client = PiesClient(
    settings.USER_DATA_BUCKET,
    region_name=settings.AWS_REGION,
    max_pies_per_account=settings.MAX_PIES,
)
_profile_client = UserProfileClient(settings.USER_PROFILES_TABLE, region_name=settings.AWS_REGION)
_market_data_client = MarketDataClient(
    settings.MARKET_DATA_BUCKET,
    region_name=settings.AWS_REGION,
    cache_ttl_seconds=settings.MARKET_DATA_CACHE_TTL_SECONDS,
)


def _row_to_dict(row: Any) -> dict[str, Any]:
    """Flatten a `ParsedRow` into a plain dict — the same shape used
    throughout this module for a row, whether it just came out of a parser
    (preview) or arrived in a commit request body (JSON has no dataclass
    concept), so `_synthetic_trade`/`_validate_commit_rows` don't need to
    care which side of the round-trip they're looking at."""
    return {
        "external_id": row.external_id,
        "date": row.date,
        "type": row.type,
        "ticker": row.ticker,
        "asset_class": row.asset_class,
        "isin": row.isin,
        "name": row.name,
        "no_of_shares": row.no_of_shares,
        "price_native": row.price_native,
        "currency": row.currency,
        "fx_rate": row.fx_rate,
    }


def _resolve_asset_class(
    ticker: str, hint: str | None
) -> tuple[str | None, dict[str, Any] | None]:
    """Resolve `ticker` against the market-data catalog, returning
    `(asset_class, profile)` or `(None, None)` if nothing matches. Tries
    `hint` first when it's a real transactable asset class (the generic CSV
    preset supplies one; Trading 212 rows never do), then falls back to
    every transactable asset class in a fixed order — this is what lets a
    Trading 212 ticker resolve at all despite carrying no asset_class of its
    own."""
    candidates = [hint] if hint in TRANSACTABLE_ASSET_CLASSES else []
    candidates += [ac for ac in ("stock", "etf") if ac not in candidates]
    for asset_class in candidates:
        profile = _market_data_client.get_profile(asset_class, ticker)
        if profile is not None:
            return asset_class, profile
    return None, None


def _synthetic_trade(
    ticker: str, asset_class: str | None, default_currency: str, row: dict[str, Any]
) -> tuple[dict[str, Any], float | None]:
    """Build a `compute_holding_rollup`-shaped synthetic BUY/SELL record
    from a row dict, plus the effective `fx_rate` actually applied. Reuses
    `resolve_converted_amounts` — the same FX/override logic
    `TransactionListView.post` uses — rather than reimplementing it, so a
    row's own broker exchange rate is honored as an override exactly the
    way a hand-entered transaction's would be, falling back to equicast's
    own historical FX lookup on that function's usual terms when the row
    doesn't carry one."""
    resolved = resolve_converted_amounts(
        {"asset_class": asset_class, "ticker": ticker},
        default_currency,
        {
            "price_native": row.get("price_native"),
            "date": row.get("date"),
            "fx_rate": row.get("fx_rate"),
        },
    )
    synthetic = {
        "type": row.get("type"),
        "no_of_shares": row.get("no_of_shares"),
        "price_native": row.get("price_native"),
        "price": resolved.get("price"),
        "date": row.get("date"),
    }
    return synthetic, resolved.get("fx_rate")


def _rebalance_pie_allocations_for_add(
    existing_holdings: list[dict[str, Any]], new_allocation_pct: Decimal
) -> list[dict[str, Any]]:
    """Return the `reallocate` batch (`[{"id", "allocation_pct"}, ...]`)
    needed so `existing_holdings`' allocations, scaled down proportionally,
    plus `new_allocation_pct` for the holding being added, sum to exactly
    100 — `HoldingsClient.sync_pie_holdings` rejects anything else
    (`AllocationError`; `PieHoldingsView.put`, backend/pies/views.py, never
    auto-normalizes today, so nothing upstream does this for us).
    Proportional float scaling alone essentially never lands on an exact
    Decimal sum, so every entry but the last is rounded to 2 decimal places
    and the last absorbs whatever rounding remainder is left, guaranteeing
    an exact 100 total rather than relying on float luck. `[]` when
    `existing_holdings` is empty — the caller forces `new_allocation_pct`
    to 100 in that case, so there's nothing to reallocate."""
    if not existing_holdings:
        return []
    remaining = Decimal("100") - new_allocation_pct
    scale = remaining / Decimal("100")
    reallocated: list[dict[str, Any]] = []
    running_total = Decimal("0")
    last_index = len(existing_holdings) - 1
    for index, holding in enumerate(existing_holdings):
        if index == last_index:
            pct = remaining - running_total
        else:
            pct = (Decimal(str(holding["allocation_pct"])) * scale).quantize(Decimal("0.01"))
            running_total += pct
        reallocated.append({"id": holding["id"], "allocation_pct": float(pct)})
    return reallocated


class ImportPreviewView(APIView):
    """Stateless: parses an uploaded file and returns everything the
    review screen needs to render — nothing is persisted, no holding or
    transaction is created. See `ImportCommitView` for the write side."""

    authentication_classes = [Auth0JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request: Request) -> Response:
        preset = request.data.get("preset")
        parser = PRESETS.get(preset)
        if parser is None:
            return Response(
                {
                    "detail": f"Unknown preset '{preset}'. "
                    f"Valid presets: {', '.join(sorted(PRESETS))}."
                },
                status=400,
            )
        upload = request.FILES.get("file")
        if upload is None:
            return Response({"detail": "Missing field: file."}, status=400)

        try:
            parsed = parser(upload)
        except ImportParseError as exc:
            # str(exc) is safe here, unlike the other except blocks in this
            # module: ImportParseError's message is built entirely from a
            # row number plus known field names/the user's own uploaded
            # value (equicast_core.imports) — never internal state or a
            # stack trace. lgtm[py/stack-trace-exposure]
            return Response({"detail": str(exc)}, status=400)

        user_id = request.user.user_id
        profile = _profile_client.get_or_create_profile(user_id)
        mode = profile["transaction_type"]
        default_currency = profile["default_currency"]

        accounts_by_id = {a["id"]: a for a in _accounts_client.list_accounts(user_id)}
        pies_by_id = {p["id"]: p for p in _pies_client.list_pies(user_id)}
        all_holdings = _holdings_client.list_holdings(user_id)

        rows_by_ticker: dict[str, list[dict[str, Any]]] = {}
        hint_by_ticker: dict[str, str | None] = {}
        for parsed_row in parsed.rows:
            row = _row_to_dict(parsed_row)
            rows_by_ticker.setdefault(row["ticker"], []).append(row)
            hint_by_ticker.setdefault(row["ticker"], row["asset_class"])

        groups = []
        for ticker, rows in rows_by_ticker.items():
            asset_class, market_profile = _resolve_asset_class(ticker, hint_by_ticker[ticker])
            resolved = market_profile is not None

            synthetic_rows = []
            row_payload = []
            for row in rows:
                synthetic, effective_fx = _synthetic_trade(
                    ticker, asset_class, default_currency, row
                )
                synthetic_rows.append(synthetic)
                row_payload.append(
                    {
                        "external_id": row["external_id"],
                        "date": row["date"],
                        "type": row["type"],
                        "no_of_shares": row["no_of_shares"],
                        "price_native": row["price_native"],
                        "fx_rate": effective_fx,
                    }
                )
            mode_preview = (
                compute_holding_rollup(synthetic_rows, "TRANSACTION") if resolved else None
            )

            candidate_holdings = [
                h
                for h in all_holdings
                if h["ticker"] == ticker
                and h["watchlist_id"] is None
                and h["asset_class"] in TRANSACTABLE_ASSET_CLASSES
            ]
            existing_holdings = []
            for holding in candidate_holdings:
                existing_transactions = _client.list_transactions(user_id, holding_id=holding["id"])
                existing_external_ids = {
                    t["external_id"] for t in existing_transactions if t.get("external_id")
                }
                duplicate_count = sum(
                    1
                    for row in rows
                    if row["external_id"] and row["external_id"] in existing_external_ids
                )

                already_has_position = False
                combined_preview = None
                if mode == "AVERAGE":
                    existing_buy = next(
                        (t for t in existing_transactions if t["type"] in ("BUY", None)), None
                    )
                    already_has_position = existing_buy is not None
                    if existing_buy is not None:
                        existing_synth = {
                            "type": "BUY",
                            "no_of_shares": existing_buy["no_of_shares"],
                            "price_native": existing_buy.get("average_price_native"),
                            "price": existing_buy.get("average_price"),
                            "date": existing_buy.get("date") or "",
                        }
                        combined_preview = compute_holding_rollup(
                            [existing_synth, *synthetic_rows], "TRANSACTION"
                        )

                pie = pies_by_id.get(holding["pie_id"]) if holding["pie_id"] else None
                existing_holdings.append(
                    {
                        "id": holding["id"],
                        "account_id": holding["account_id"],
                        "account_name": (
                            accounts_by_id.get(holding["account_id"], {}).get("name")
                            if holding["account_id"]
                            else None
                        ),
                        "pie_id": holding["pie_id"],
                        "pie_name": pie.get("name") if pie else None,
                        "pie_account_name": (
                            accounts_by_id.get(pie.get("account_id"), {}).get("name")
                            if pie
                            else None
                        ),
                        "already_has_position": already_has_position,
                        "combined_preview": combined_preview,
                        "duplicate_count": duplicate_count,
                    }
                )

            groups.append(
                {
                    "ticker": ticker,
                    "asset_class": asset_class,
                    "resolved": resolved,
                    "name": market_profile.get("name") if market_profile else None,
                    "isin": rows[0]["isin"],
                    "existing_holdings": existing_holdings,
                    "mode_preview": mode_preview,
                    "rows": row_payload,
                }
            )

        return Response(
            {
                "preset": preset,
                "mode": mode,
                "rows_skipped": parsed.rows_skipped,
                "invalid_rows": [
                    {"row": row.row_number, "ticker": row.ticker, "reason": row.reason}
                    for row in parsed.invalid_rows
                ],
                "groups": groups,
            }
        )


def _validate_commit_rows(rows: Any) -> str | None:
    """Defensive re-validation of a commit selection's `rows` — a preview
    payload is always well-formed (the parser guarantees it), but a commit
    request is user-editable JSON the frontend built from it, not something
    this view can trust blindly. Returns an error detail string, or `None`
    if `rows` is a non-empty list of well-formed BUY/SELL row dicts."""
    if not isinstance(rows, list) or not rows:
        return "No rows selected to import."
    for row in rows:
        if not isinstance(row, dict) or row.get("type") not in ("BUY", "SELL"):
            return f"Invalid row type {row.get('type') if isinstance(row, dict) else row!r}."
        if not row.get("date"):
            return "Row missing date."
        try:
            shares = float(row.get("no_of_shares"))
            price = float(row.get("price_native"))
        except (TypeError, ValueError):
            return "Row has invalid no_of_shares/price_native."
        if shares <= 0 or price <= 0:
            return "Row no_of_shares/price_native must be positive."
    return None


def _resolve_import_target(
    user_id: str, ticker: str, asset_class: str, target: dict[str, Any]
) -> dict[str, Any]:
    """Resolve/create the holding a commit selection's rows will be
    imported against, from its `target` (`{"type": "existing_holding"|
    "account"|"pie", "id", "allocation_pct"}` — see `ImportCommitView`).
    Raises `ValueError` for anything the caller got wrong (unknown
    account/pie id, missing allocation_pct, unknown target type) alongside
    whatever `equicast_core` exception a downstream client call itself
    raises — `_commit_selection` catches both uniformly as a per-selection
    error, never aborting the rest of the batch."""
    target_type = target.get("type")

    if target_type == "existing_holding":
        return _holdings_client.get_holding(user_id, target.get("id"))

    if target_type == "account":
        account_id = target.get("id")
        try:
            _accounts_client.get_account(user_id, account_id)
        except AccountNotFoundError as exc:
            raise ValueError("Unknown account_id.") from exc
        try:
            return _holdings_client.create_holding(
                user_id, ticker=ticker, asset_class=asset_class, account_id=account_id
            )
        except HoldingAlreadyExistsError:
            # A holding for this ticker already exists in the target
            # account (e.g. created by an earlier row/selection in the
            # same import, or already there before the import started) —
            # import into it rather than treating this as a failure.
            return next(
                h
                for h in _holdings_client.list_holdings(user_id, account_id=account_id)
                if h["ticker"] == ticker
            )

    if target_type == "pie":
        pie_id = target.get("id")
        try:
            _pies_client.get_pie(user_id, pie_id)
        except PieNotFoundError as exc:
            raise ValueError("Unknown pie_id.") from exc

        existing_pie_holdings = _holdings_client.list_holdings(user_id, pie_id=pie_id)
        already_held = next((h for h in existing_pie_holdings if h["ticker"] == ticker), None)
        if already_held is not None:
            return already_held

        if existing_pie_holdings:
            requested_pct = target.get("allocation_pct")
            if requested_pct is None:
                raise ValueError("allocation_pct is required to add to a non-empty pie.")
            new_pct = Decimal(str(requested_pct))
        else:
            # A pie's holdings must sum to exactly 100% once non-empty —
            # for a pie's very first holding, 100% is the only valid value
            # regardless of what the caller supplied.
            new_pct = Decimal("100")

        reallocate = _rebalance_pie_allocations_for_add(existing_pie_holdings, new_pct)
        updated = _holdings_client.sync_pie_holdings(
            user_id,
            pie_id,
            add=[{"ticker": ticker, "asset_class": asset_class, "allocation_pct": float(new_pct)}],
            reallocate=reallocate,
        )
        return next(h for h in updated if h["ticker"] == ticker and h["pie_id"] == pie_id)

    raise ValueError(f"Unknown target type '{target_type}'.")


def _commit_average_mode(
    user_id: str,
    holding_id: str,
    ticker: str,
    asset_class: str,
    default_currency: str,
    rows: list[dict[str, Any]],
) -> dict[str, Any]:
    """AVERAGE mode: fold every row into one weighted-average position —
    creating the holding's first BUY if it has none yet, or extending its
    existing one (combined via `compute_holding_rollup`, written back via
    `update_transaction`) if it does. See module docstring for the
    re-upload dedup limitation this carries (GitHub issue #192)."""
    existing_transactions = _client.list_transactions(user_id, holding_id=holding_id)
    existing_buy = next((t for t in existing_transactions if t["type"] in ("BUY", None)), None)

    synthetic_rows = [
        _synthetic_trade(ticker, asset_class, default_currency, row)[0] for row in rows
    ]
    row_dates = [row["date"] for row in rows]

    if existing_buy is None:
        rollup = compute_holding_rollup(synthetic_rows, "TRANSACTION")
        try:
            _client.create_transaction(
                user_id,
                holding_id,
                "AVERAGE",
                type="BUY",
                no_of_shares=rollup["no_of_shares"],
                average_price_native=rollup["average_price_native"],
                average_price=rollup["average_price"],
                date=min(row_dates),
            )
        except (TransactionAmountError, TransactionLimitExceededError):
            return {
                "status": "error",
                "detail": "Unable to create a position from the imported rows.",
            }
        return {
            "status": "created",
            "created_count": len(rows),
            "skipped_duplicate_count": 0,
            "detail": f"Created a new position of {rollup['no_of_shares']} shares.",
        }

    existing_synth = {
        "type": "BUY",
        "no_of_shares": existing_buy["no_of_shares"],
        "price_native": existing_buy.get("average_price_native"),
        "price": existing_buy.get("average_price"),
        "date": existing_buy.get("date") or min(row_dates),
    }
    combined = compute_holding_rollup([existing_synth, *synthetic_rows], "TRANSACTION")
    new_date = min([existing_buy.get("date") or min(row_dates), *row_dates])
    try:
        # fx_rate is explicitly cleared (not carried forward) — a single
        # rate can't represent a blended multi-lot average, same "derived,
        # not a literal input" status average_price_native itself already
        # has after a merge. Patching date/no_of_shares here also drops
        # auto-created DIVIDENDs and rewinds dividends_synced_through (see
        # TransactionsClient.update_transaction) — exactly what's wanted,
        # so the next sync rebuilds from the new, possibly earlier, anchor.
        _client.update_transaction(
            user_id,
            holding_id,
            existing_buy["id"],
            "AVERAGE",
            no_of_shares=combined["no_of_shares"],
            average_price_native=combined["average_price_native"],
            average_price=combined["average_price"],
            date=new_date,
            fx_rate=None,
        )
    except TransactionAmountError:
        return {
            "status": "error",
            "detail": "Unable to update the existing position with the imported rows.",
        }
    return {
        "status": "created",
        "created_count": len(rows),
        "skipped_duplicate_count": 0,
        "detail": (
            f"Extended existing position: {existing_buy['no_of_shares']} -> "
            f"{combined['no_of_shares']} shares."
        ),
    }


def _commit_transaction_mode(
    user_id: str,
    holding_id: str,
    ticker: str,
    asset_class: str,
    default_currency: str,
    rows: list[dict[str, Any]],
) -> dict[str, Any]:
    """TRANSACTION mode: import each row as its own BUY/SELL log entry,
    re-checking `external_id` against a fresh read (not the preview
    payload's possibly-stale duplicate flags) so a repeat/overlapping
    import skips rows it already recorded instead of duplicating them."""
    existing_transactions = _client.list_transactions(user_id, holding_id=holding_id)
    existing_external_ids = {
        t["external_id"] for t in existing_transactions if t.get("external_id")
    }

    ordered_rows = sorted(rows, key=lambda r: r.get("date") or "")
    created_count = 0
    skipped_duplicate_count = 0
    errors: list[dict[str, Any]] = []
    for row in ordered_rows:
        external_id = row.get("external_id")
        if external_id and external_id in existing_external_ids:
            skipped_duplicate_count += 1
            continue

        synthetic, effective_fx = _synthetic_trade(ticker, asset_class, default_currency, row)
        try:
            _client.create_transaction(
                user_id,
                holding_id,
                "TRANSACTION",
                date=synthetic["date"],
                type=synthetic["type"],
                no_of_shares=synthetic["no_of_shares"],
                price_native=synthetic["price_native"],
                price=synthetic["price"],
                fx_rate=effective_fx,
                external_id=external_id,
            )
        except (TransactionAmountError, InsufficientSharesError, TransactionLimitExceededError):
            errors.append(
                {
                    "date": row.get("date"),
                    "external_id": external_id,
                    "detail": "Unable to import this row.",
                }
            )
            continue

        created_count += 1
        if external_id:
            existing_external_ids.add(external_id)
        # Same reasoning as TransactionListView.post (views.py): a backdated
        # BUY/SELL can land inside the dividend watermark's already-synced
        # range, so reopen it here too — bulk import creates transactions
        # directly rather than going through that view.
        _client.rewind_dividends_synced_through(user_id, holding_id, synthetic["date"])

    if created_count == 0 and not errors:
        status = "skipped"
    elif errors and created_count > 0:
        status = "partial"
    elif errors and created_count == 0:
        status = "error"
    else:
        status = "created"

    return {
        "status": status,
        "created_count": created_count,
        "skipped_duplicate_count": skipped_duplicate_count,
        "errors": errors,
        "detail": None,
    }


def _commit_selection(
    user_id: str, mode: str, default_currency: str, selection: Any
) -> dict[str, Any]:
    """Process one `{ticker, asset_class, target, rows}` commit selection
    end to end, never raising — any failure (a bad target, an
    equicast_core validation error) becomes `{"status": "error", ...}` in
    the returned dict rather than aborting the rest of the batch, per the
    plan's partial-failure requirement."""
    ticker = str(selection.get("ticker") or "").upper()
    asset_class = selection.get("asset_class")
    target = selection.get("target") or {}
    rows = selection.get("rows")

    if not ticker or asset_class not in TRANSACTABLE_ASSET_CLASSES:
        return {
            "ticker": ticker,
            "holding_id": None,
            "status": "error",
            "detail": "Invalid ticker/asset_class.",
        }
    rows_error = _validate_commit_rows(rows)
    if rows_error is not None:
        return {"ticker": ticker, "holding_id": None, "status": "error", "detail": rows_error}

    try:
        holding = _resolve_import_target(user_id, ticker, asset_class, target)
    except (
        HoldingNotFoundError,
        HoldingAlreadyExistsError,
        HoldingLimitExceededError,
        AllocationError,
        AccountNotFoundError,
        PieNotFoundError,
        ValueError,
    ):
        return {
            "ticker": ticker,
            "holding_id": None,
            "status": "error",
            "detail": "Unable to resolve the import target for this selection.",
        }

    holding_id = holding["id"]
    if mode == "AVERAGE":
        result = _commit_average_mode(
            user_id, holding_id, ticker, asset_class, default_currency, rows
        )
    else:
        result = _commit_transaction_mode(
            user_id, holding_id, ticker, asset_class, default_currency, rows
        )

    _refresh_holding_rollup(user_id, holding_id, mode)
    return {"ticker": ticker, "holding_id": holding_id, **result}


class ImportCommitView(APIView):
    """Bulk-creates transactions (and, where needed, the holdings they
    belong to) from the user's reviewed/edited selections — see
    `ImportPreviewView` for the read-only step this follows."""

    authentication_classes = [Auth0JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request: Request) -> Response:
        selections = request.data.get("selections")
        if not isinstance(selections, list) or not selections:
            return Response({"detail": "Missing field: selections (non-empty list)."}, status=400)

        user_id = request.user.user_id
        profile = _profile_client.get_or_create_profile(user_id)
        mode = profile["transaction_type"]
        default_currency = profile["default_currency"]

        results = [
            _commit_selection(user_id, mode, default_currency, selection)
            for selection in selections
        ]
        return Response({"results": results})
