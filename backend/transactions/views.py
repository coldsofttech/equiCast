import logging
from typing import Any

from django.conf import settings
from equicast_core import (
    HoldingNotFoundError,
    HoldingsClient,
    InsufficientSharesError,
    MarketDataClient,
    TransactionAlreadyExistsError,
    TransactionAmountError,
    TransactionLimitExceededError,
    TransactionNotFoundError,
    TransactionsClient,
    UserProfileClient,
    compute_holding_rollup,
    compute_new_dividend_transactions,
    latest_paid_dividend_date,
)
from identity.authentication import Auth0JWTAuthentication
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

logger = logging.getLogger(__name__)

#: Asset classes transactions are allowed against — fx holdings never carry
#: transactions (see module docstring in equicast_core.transactions).
TRANSACTABLE_ASSET_CLASSES = {"stock", "etf"}

#: Valid values for a TRANSACTION-mode record's `type`, re-exported here so
#: holdings/views.py's embedded-transaction path can reuse the same set
#: without importing straight from equicast_core.transactions. AVERAGE mode
#: only ever uses "BUY" (its one position entry) and "DIVIDEND".
TRANSACTION_ACTIONS = {"BUY", "SELL", "DIVIDEND"}

#: Field shape required/disallowed for a BUY/SELL record, keyed by mode —
#: see `build_transaction_fields`. A DIVIDEND record's shape is the same
#: regardless of mode — see `_DIVIDEND_FIELDS`. Only the *native* value of
#: a monetary field is ever a valid request field — its converted
#: counterpart (`average_price`/`price`/`amount`) is always
#: backend-resolved (see `resolve_converted_amounts`), never accepted from
#: a caller.
_FIELDS_BY_MODE = {
    "AVERAGE": {
        "required": {"no_of_shares", "average_price_native", "date", "type"},
        "disallowed": {"price_native", "amount_native", "average_price", "price", "amount"},
    },
    "TRANSACTION": {
        "required": {"no_of_shares", "price_native", "date", "type"},
        "disallowed": {"average_price_native", "amount_native", "average_price", "price", "amount"},
    },
}
_DIVIDEND_FIELDS = {
    "required": {"amount_native", "date", "type"},
    "disallowed": {
        "no_of_shares",
        "average_price_native",
        "price_native",
        "average_price",
        "price",
        "amount",
    },
}

#: Fields a caller may PATCH — native values plus `fx_rate` (GitHub issue
#: #149 — the only non-native field a caller may ever submit, since it's
#: an override, not a computed value); the converted counterpart is
#: recomputed server-side whenever a native value, `date`, or `fx_rate`
#: changes (see `TransactionDetailView.patch`).
UPDATABLE_FIELDS = {"no_of_shares", "average_price_native", "date", "amount_native", "fx_rate"}

#: Monetary/quantity fields that must always be stored (and returned) as a
#: JSON number, never whatever type the caller's request body happened to
#: carry (a controlled `<input type="number">` posts its value as a string)
#: — coerced via `_coerce_numeric_fields` right after `build_transaction_fields`/
#: `TransactionDetailView.patch` accept the raw payload.
_NUMERIC_FIELDS = {
    "no_of_shares",
    "average_price_native",
    "price_native",
    "amount_native",
    "fx_rate",
}


def _coerce_numeric_fields(fields: dict[str, Any]) -> dict[str, Any]:
    """Return `fields` with every key in `_NUMERIC_FIELDS` that's present
    and not `None` converted to `float` — `_validate_positive_amount` (via
    `TransactionsClient.create_transaction`/`update_transaction`) already
    validates these are positive numbers via their string form, but only
    for validation; the value actually stored is whatever was passed in.
    This is what makes the stored/returned value numeric regardless of
    whether the caller posted `150.5` or `"150.5"`."""
    result = dict(fields)
    for key in _NUMERIC_FIELDS:
        if result.get(key) is None:
            continue
        try:
            result[key] = float(result[key])
        except (TypeError, ValueError):
            # Left as whatever the caller sent — TransactionsClient's own
            # _validate_positive_amount (Decimal-based) is what actually
            # rejects a malformed value with a clean 400, not this helper.
            pass
    return result


class TransactionPagination(PageNumberPagination):
    """Standard DRF page-number pagination (`{count, next, previous,
    results}`) for `TransactionListView.get` — 50 per page by default,
    overridable per-request via `?page_size=` up to `max_page_size`. Doesn't
    reduce the underlying S3 read (`TransactionsClient` always loads a
    holding's whole transactions file in one GET — see its module
    docstring) — this only bounds the HTTP response size and lets the "See
    all" drawer fetch later pages on demand instead of the whole history up
    front."""

    page_size = 50
    page_size_query_param = "page_size"
    max_page_size = 200

#: One shared client for the process, mirroring holdings/views.py's
#: module-level _client pattern.
_client = TransactionsClient(
    settings.USER_DATA_BUCKET,
    region_name=settings.AWS_REGION,
    max_transactions_for_holding=settings.MAX_TRANSACTIONS_FOR_HOLDING,
)
#: Needed only to look up a transaction's holding — holdings/views.py holds
#: the client actually used for holdings CRUD.
_holdings_client = HoldingsClient(
    settings.USER_DATA_BUCKET,
    region_name=settings.AWS_REGION,
    max_holdings_for_account=settings.MAX_HOLDINGS_FOR_ACCOUNT,
    max_holdings_for_pie=settings.MAX_HOLDINGS_FOR_PIE,
    max_holdings_for_watchlist=settings.MAX_HOLDINGS_FOR_WATCHLIST,
)
#: Needed only to read the user's global transaction_type/default_currency —
#: identity/views.py holds the client actually used for profile CRUD.
_profile_client = UserProfileClient(settings.USER_PROFILES_TABLE, region_name=settings.AWS_REGION)
#: Needed only to resolve a holding's native currency (for FX conversion,
#: see `resolve_converted_amounts`) — market_data/views.py holds the
#: client actually used for market-data CRUD.
_market_data_client = MarketDataClient(
    settings.MARKET_DATA_BUCKET,
    region_name=settings.AWS_REGION,
    cache_ttl_seconds=settings.MARKET_DATA_CACHE_TTL_SECONDS,
)


def resolve_transaction_mode(
    user_id: str, holding: dict[str, Any]
) -> tuple[dict[str, Any] | None, Response | None]:
    """Return `(profile, None)` — the user's full profile (`UserProfileClient`
    item, carrying both `transaction_type` and `default_currency`) — or
    `(None, error_response)` if `holding` isn't eligible for transactions at
    all. Used by both `TransactionListView.post` and
    `TransactionDetailView.patch` so they apply the exact same eligibility
    rules and don't each fetch the profile separately.

    transaction_type is a single per-user setting (see UserProfileClient),
    not per-account — every holding across every one of the user's
    accounts/pies records transactions the same way, so this needs no
    account/pie lookup at all."""
    if holding["watchlist_id"] is not None:
        return None, Response(
            {"detail": "Transactions aren't supported for watchlist holdings."}, status=400
        )
    if holding["asset_class"] not in TRANSACTABLE_ASSET_CLASSES:
        return None, Response(
            {"detail": "Transactions aren't supported for fx holdings."}, status=400
        )

    profile = _profile_client.get_or_create_profile(user_id)
    return profile, None


def build_transaction_fields(
    data: dict[str, Any], mode: str
) -> tuple[dict[str, Any] | None, str | None]:
    """Validate `data` against the field shape required for `mode`
    (`"AVERAGE"` or `"TRANSACTION"`) and `data.get("type")`, returning
    `(kwargs, None)` — native values only, ready for
    `resolve_converted_amounts` and then
    `TransactionsClient.create_transaction` — or `(None, error_detail)` if
    the shape doesn't match. Shared the same way `resolve_transaction_mode`
    is.

    `type` must be `"BUY"` (either mode), `"SELL"` (`TRANSACTION` mode
    only), or `"DIVIDEND"` (either mode, same field shape regardless of
    mode — see `_DIVIDEND_FIELDS`).

    `fx_rate` (GitHub issue #149) is accepted for every type/mode
    combination, always optional — unlike `average_price`/`price`/`amount`
    it's never in a shape's `disallowed` set, since it's a real caller-
    supplied override, not a server-computed value; see
    `resolve_converted_amounts`."""
    allowed_types = {"BUY", "DIVIDEND"} if mode == "AVERAGE" else TRANSACTION_ACTIONS
    if data.get("type") not in allowed_types:
        return None, f"Invalid type '{data.get('type')}' for {mode} mode."

    shape = _DIVIDEND_FIELDS if data["type"] == "DIVIDEND" else _FIELDS_BY_MODE[mode]
    missing = shape["required"] - data.keys()
    if missing:
        return None, f"Missing field(s): {', '.join(sorted(missing))}."
    present_disallowed = shape["disallowed"] & data.keys()
    if present_disallowed:
        return None, f"Field(s) not applicable: {', '.join(sorted(present_disallowed))}."

    return _coerce_numeric_fields(
        {
            "no_of_shares": data.get("no_of_shares"),
            "average_price_native": data.get("average_price_native"),
            "price_native": data.get("price_native"),
            "amount_native": data.get("amount_native"),
            "fx_rate": data.get("fx_rate"),
            "date": data.get("date"),
            "type": data.get("type"),
        }
    ), None


def resolve_converted_amounts(
    holding: dict[str, Any], default_currency: str, fields: dict[str, Any]
) -> dict[str, Any]:
    """Return `fields` with `fx_rate` and its converted counterpart(s)
    (`average_price`/`price`/`amount`) filled in from whichever native
    value(s) (`average_price_native`/`price_native`/`amount_native`) it
    carries.

    If `fields` already carries an `fx_rate` (GitHub issue #149 — the
    caller overriding the rate themselves), that value is used directly
    and no FX lookup happens at all. Otherwise the rate is auto-resolved
    from the historical FX rate between the holding's own native currency
    (its market profile's `currency`) and `default_currency`, on
    `fields["date"]` (`MarketDataClient.get_fx_rate_on_date`). Either way,
    the *effective* rate used lands in `result["fx_rate"]` — `None` when
    neither an override nor an auto-resolve produced one (no market
    profile for this holding's ticker, no `date` given, or no FX rate
    published for that currency combination on or before that date).

    A converted value is `None` whenever `fx_rate` couldn't be resolved.
    The transaction is still recorded in that case, just without a
    converted figure (see equicast_core.transactions module docstring) —
    this never raises."""
    override = fields.get("fx_rate")
    if override is not None:
        rate = float(override)
    else:
        market_profile = _market_data_client.get_profile(holding["asset_class"], holding["ticker"])
        native_currency = market_profile.get("currency") if market_profile else None
        rate = None
        if native_currency and fields.get("date"):
            rate = _market_data_client.get_fx_rate_on_date(
                native_currency, default_currency, fields["date"]
            )

    result = dict(fields)
    result["fx_rate"] = rate
    for native_key, converted_key in (
        ("average_price_native", "average_price"),
        ("price_native", "price"),
        ("amount_native", "amount"),
    ):
        native_value = fields.get(native_key)
        if native_value is not None and rate is not None:
            result[converted_key] = float(native_value) * rate
        else:
            result[converted_key] = None
    return result


def _refresh_holding_rollup(user_id: str, holding_id: str, mode: str) -> None:
    """Recompute `holding_id`'s position rollup from its full transaction
    history and persist it onto the holding record (see
    `HoldingsClient.update_holding_financials`) — called after every
    transaction create/update/delete against this holding, from both this
    module and holdings/views.py's nested-transaction create path. A
    transaction can't outlive its holding under normal operation, but this
    stays a no-op rather than a 500 if it somehow does."""
    transactions = _client.list_transactions(user_id, holding_id=holding_id)
    rollup = compute_holding_rollup(transactions, mode)
    try:
        _holdings_client.update_holding_financials(user_id, holding_id, **rollup)
    except HoldingNotFoundError:
        pass


def sync_dividends_for_holdings(
    user_id: str, holdings: list[dict[str, Any]], profile: dict[str, Any]
) -> list[dict[str, Any]]:
    """Auto-create `DIVIDEND` transactions for every holding in `holdings`
    from its paid dividend history — AVERAGE mode (GitHub issue #123) and
    TRANSACTION mode (issue #124) alike, `profile["transaction_type"]`
    picking which share-count basis `compute_new_dividend_transactions`
    uses — returning `holdings` with each synced holding's rollup
    (`dividends_native`/`dividends`, alongside the rest of
    `compute_holding_rollup`'s fields) refreshed in place. Called from
    accounts/pies/holdings views.py's own `_enrich_holdings`/
    `_enrich_holding` — the same point each already resolves the caller's
    profile for market-data enrichment — so a holding's dividends stay
    caught up on every read, without the user manually recording each
    payout.

    Per-holding, skips anything `resolve_transaction_mode` wouldn't allow a
    transaction against at all (a watchlist holding, or an fx holding) —
    same eligibility rule, applied directly since there's no request here
    to build an error `Response` from — and anything
    `compute_new_dividend_transactions` finds nothing new for (no
    `BUY`/`SELL` on record yet, no market-data dividend history, or
    nothing since the holding's `dividends_synced_through` watermark).

    Every payout `compute_new_dividend_transactions` even considers —
    created here, or skipped as pre-history — advances that watermark via
    `TransactionsClient.advance_dividends_synced_through`, *provided every
    `create_transaction` call this pass actually succeeded* — this is what
    makes deleting an auto-created `DIVIDEND` transaction a lasting
    correction: without it, the next sync would see the payout as "missing"
    again (nothing recorded for its ex-date) and recreate it right back.
    But advancing the watermark unconditionally — even when a create
    genuinely failed (`TransactionAmountError`/`TransactionLimitExceededError`,
    caught below) — would silently and *permanently* lock that holding out
    of ever syncing the failed payout (or anything after it, once the
    watermark covers those dates too): every future call would see
    `ex_date <= synced_through` and skip it forever, with no created
    transaction to show for it. So the watermark only advances when nothing
    failed this pass; a partial failure leaves it exactly where it was, and
    the next sync retries the whole batch — already-created entries are
    naturally skipped via `recorded_dates`, so only the ones that actually
    failed (or are newly eligible) get reattempted. In TRANSACTION mode, a
    backdated `BUY`/`SELL` (issue #124's "past adjustments") reopens part of
    an already-advanced watermark instead — see
    `TransactionListView.post`/`TransactionDetailView.delete`'s calls to
    `TransactionsClient.rewind_dividends_synced_through`.

    Two concurrent calls syncing the same holding (two browser tabs, or
    React StrictMode's double-effect-mount in dev — this is the exact race
    that surfaced both bugs this and the next paragraph document) can make
    `create_transaction`'s own optimistic-concurrency retry
    (`_MAX_CONFLICT_RETRIES`) genuinely exhaust and raise a `RuntimeError`,
    since both callers are racing to write the same holding's transactions
    file. Every step for one holding — the reads, the create loop, the
    watermark advance — is wrapped in its own `try/except Exception`, so a
    `RuntimeError` (or anything else unexpected) here is logged and this
    holding is simply left for the next sync, rather than propagating out
    of the whole function and silently abandoning every holding still left
    in `holdings` (accounts/pies/holdings views.py's callers never see this
    partial-failure — they get every other holding's fully up-to-date
    result back regardless).

    The same race can otherwise let two concurrent calls both decide the
    same payout is new (neither has written it yet when each checks) and
    both call `create_transaction` for it — silently doubling that
    dividend rather than losing it. Each auto-created payout is given a
    synthetic `external_id` (`f"dividend:{ex_dividend_date}"`, unique per
    holding since it's scoped to one holding's transactions file), and
    `create_transaction` itself rejects a second transaction sharing an
    `external_id` (re-checked fresh on every conflict-retry attempt, not
    just once) — so whichever of the two racing calls loses the write
    raises `TransactionAlreadyExistsError` on its own retry instead of
    creating a duplicate; that's treated as a success here, not a failure,
    since the payout genuinely exists now."""
    mode = profile["transaction_type"]
    synced: list[dict[str, Any]] = []
    for holding in holdings:
        if (
            holding["watchlist_id"] is not None
            or holding["asset_class"] not in TRANSACTABLE_ASSET_CLASSES
        ):
            synced.append(holding)
            continue

        try:
            new_entries = _sync_dividends_for_one_holding(user_id, holding, mode, profile)
        except Exception:
            logger.exception(
                "sync_dividends_for_holdings: unexpected error syncing holding '%s' (%s); "
                "leaving it for the next sync",
                holding["id"],
                holding.get("ticker"),
            )
            synced.append(holding)
            continue

        if not new_entries:
            synced.append(holding)
            continue

        transactions = _client.list_transactions(user_id, holding_id=holding["id"])
        rollup = compute_holding_rollup(transactions, mode)
        try:
            holding = _holdings_client.update_holding_financials(user_id, holding["id"], **rollup)
        except HoldingNotFoundError:
            pass
        synced.append(holding)
    return synced


def _sync_dividends_for_one_holding(
    user_id: str, holding: dict[str, Any], mode: str, profile: dict[str, Any]
) -> list[dict[str, Any]]:
    """The per-holding body of `sync_dividends_for_holdings`'s loop,
    factored out so that function can wrap it in one `try/except` per
    holding — see that function's docstring for why. Returns whatever
    `compute_new_dividend_transactions` found (`[]` when there was nothing
    new), regardless of how many of those actually got created; the
    watermark itself only ever advances when every create this pass
    succeeded, same "all or nothing" reasoning either way."""
    existing = _client.list_transactions(user_id, holding_id=holding["id"])
    dividends_data = _market_data_client.get_dividends(holding["asset_class"], holding["ticker"])
    dividends = dividends_data["dividends"] if dividends_data else []
    synced_through = _client.get_dividends_synced_through(user_id, holding["id"])
    new_entries = compute_new_dividend_transactions(existing, dividends, synced_through, mode=mode)

    all_created = True
    for entry in new_entries:
        fields = resolve_converted_amounts(
            holding,
            profile["default_currency"],
            {
                "amount_native": entry["amount_native"],
                "date": entry["date"],
                "type": "DIVIDEND",
            },
        )
        try:
            _client.create_transaction(
                user_id,
                holding["id"],
                mode,
                external_id=f"dividend:{entry['date']}",
                **fields,
            )
        except TransactionAlreadyExistsError:
            # A concurrent sync for this same holding (two browser tabs, a
            # frontend effect double-firing) already created this exact
            # payout — see TransactionsClient.create_transaction's
            # external_id dedup. Nothing missing, so this doesn't count
            # against all_created.
            continue
        except (TransactionAmountError, TransactionLimitExceededError, RuntimeError) as exc:
            all_created = False
            logger.warning(
                "sync_dividends_for_holdings: failed to create DIVIDEND for holding "
                "'%s' (%s) on %s: %s",
                holding["id"],
                holding.get("ticker"),
                entry["date"],
                exc,
            )
            continue

    if all_created:
        new_watermark = latest_paid_dividend_date(dividends, synced_through)
        if new_watermark is not None and new_watermark != synced_through:
            _client.advance_dividends_synced_through(user_id, holding["id"], new_watermark)

    return new_entries


class TransactionListView(APIView):
    authentication_classes = [Auth0JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request: Request) -> Response:
        holding_id = request.query_params.get("holding_id")
        year = request.query_params.get("year")
        date_from = request.query_params.get("date_from")
        date_to = request.query_params.get("date_to")
        transactions = _client.list_transactions(
            request.user.user_id,
            holding_id=holding_id,
            year=year,
            date_from=date_from,
            date_to=date_to,
        )
        # Most-recent-date-first, so page 1 is always the recent activity a
        # holding page's top-N pane and "See all" drawer's first page want —
        # not just whatever order records happen to be stored in.
        transactions.sort(key=lambda t: t["date"] or "", reverse=True)

        paginator = TransactionPagination()
        page = paginator.paginate_queryset(transactions, request, view=self)
        return paginator.get_paginated_response(page)

    def post(self, request: Request) -> Response:
        holding_id = request.data.get("holding_id")
        if not holding_id:
            return Response({"detail": "Missing field(s): holding_id."}, status=400)

        try:
            holding = _holdings_client.get_holding(request.user.user_id, holding_id)
        except HoldingNotFoundError:
            return Response({"detail": "Unknown holding_id."}, status=400)

        profile, error = resolve_transaction_mode(request.user.user_id, holding)
        if error is not None:
            return error
        assert profile is not None
        mode = profile["transaction_type"]

        fields, detail = build_transaction_fields(request.data, mode)
        if detail is not None:
            return Response({"detail": detail}, status=400)
        assert fields is not None
        fields = resolve_converted_amounts(holding, profile["default_currency"], fields)

        try:
            transaction = _client.create_transaction(
                request.user.user_id, holding_id, mode, **fields
            )
        except TransactionAmountError:
            return Response(
                {
                    "detail": "no_of_shares/average_price_native/price_native/amount_native/"
                    "fx_rate must be positive numbers, date is required, and type must be "
                    "valid for this mode."
                },
                status=400,
            )
        except TransactionAlreadyExistsError:
            # Static, caller-agnostic message rather than str(exc) — same
            # py/stack-trace-exposure reasoning as PieHoldingsView.put's 409
            # (see pies/views.py).
            return Response(
                {"detail": "Holding already has a BUY record — update it instead."},
                status=409,
            )
        except TransactionLimitExceededError:
            cap = _client.max_transactions_for_holding
            return Response(
                {"detail": f"Transaction limit reached for this holding (max {cap})."}, status=409
            )
        except InsufficientSharesError:
            return Response(
                {"detail": "Sell quantity exceeds net shares recorded for this holding."},
                status=409,
            )
        # GitHub issue #124: a TRANSACTION-mode BUY/SELL changes the
        # running share-count timeline compute_new_dividend_transactions
        # uses for every payout after it — reopen the dividend sync
        # watermark if this one landed inside the range already synced,
        # so a backdated trade's "past adjustments" actually get picked up.
        if mode == "TRANSACTION" and fields["type"] in ("BUY", "SELL"):
            _client.rewind_dividends_synced_through(
                request.user.user_id, holding_id, fields["date"]
            )
        _refresh_holding_rollup(request.user.user_id, holding_id, mode)
        return Response(transaction, status=201)


class TransactionDetailView(APIView):
    """Addressed by `holding_id`/`transaction_id` together, not
    `transaction_id` alone — transactions are stored one JSON object per
    holding (see `TransactionsClient`), so this is a single-file
    read/write rather than a scan across every holding the user has."""

    authentication_classes = [Auth0JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request: Request, holding_id: str, transaction_id: str) -> Response:
        try:
            transaction = _client.get_transaction(request.user.user_id, holding_id, transaction_id)
        except TransactionNotFoundError:
            return Response(status=404)
        return Response(transaction)

    def patch(self, request: Request, holding_id: str, transaction_id: str) -> Response:
        user_id = request.user.user_id
        try:
            holding = _holdings_client.get_holding(user_id, holding_id)
        except HoldingNotFoundError:
            return Response(status=404)
        profile, error = resolve_transaction_mode(user_id, holding)
        if error is not None:
            return error
        assert profile is not None
        mode = profile["transaction_type"]

        fields = _coerce_numeric_fields(
            {k: v for k, v in request.data.items() if k in UPDATABLE_FIELDS}
        )

        # A native value, the date, or fx_rate changing all mean the
        # converted figure needs recomputing — merge onto the existing
        # record first so e.g. a date-only patch still recomputes using
        # the record's already-recorded native value, not a missing one.
        # `fx_rate` is deliberately *not* carried forward from the
        # existing record when this patch doesn't touch it — an earlier
        # override was a one-time decision for that save; changing the
        # date/native value without resubmitting fx_rate re-auto-resolves
        # fresh rather than silently reapplying a stale override to a
        # different date (see equicast_core.transactions module docstring).
        if fields.keys() & {"date", "average_price_native", "amount_native", "fx_rate"}:
            try:
                existing = _client.get_transaction(user_id, holding_id, transaction_id)
            except TransactionNotFoundError:
                return Response(status=404)
            native_key = (
                "amount_native"
                if existing["type"] == "DIVIDEND"
                else "average_price_native"
            )
            converted_key = "amount" if existing["type"] == "DIVIDEND" else "average_price"
            merged = {
                "date": fields.get("date", existing["date"]),
                native_key: fields.get(native_key, existing.get(native_key)),
            }
            if "fx_rate" in fields:
                merged["fx_rate"] = fields["fx_rate"]
            resolved = resolve_converted_amounts(holding, profile["default_currency"], merged)
            fields[converted_key] = resolved[converted_key]
            fields["fx_rate"] = resolved["fx_rate"]

        try:
            transaction = _client.update_transaction(
                user_id, holding_id, transaction_id, mode, **fields
            )
        except TransactionNotFoundError:
            return Response(status=404)
        except TransactionAmountError:
            return Response(
                {
                    "detail": "no_of_shares/average_price_native/amount_native/fx_rate must "
                    "be positive numbers."
                },
                status=400,
            )
        except ValueError:
            # Static, caller-agnostic message rather than str(exc) — same
            # py/stack-trace-exposure reasoning as TransactionListView.post's
            # 409 above (and PieHoldingsView.put's, see pies/views.py).
            return Response(
                {"detail": "This transaction can't be updated with the given fields."}, status=400
            )
        _refresh_holding_rollup(user_id, holding_id, mode)
        return Response(transaction)

    def delete(self, request: Request, holding_id: str, transaction_id: str) -> Response:
        user_id = request.user.user_id
        # Fetched before deleting purely to learn its type/date for the
        # GitHub issue #124 rewind check below — TransactionNotFoundError
        # here means the same 404 the plain delete would have raised.
        try:
            transaction = _client.get_transaction(user_id, holding_id, transaction_id)
        except TransactionNotFoundError:
            return Response(status=404)
        try:
            _client.delete_transaction(user_id, holding_id, transaction_id)
        except TransactionNotFoundError:
            return Response(status=404)

        try:
            _holdings_client.get_holding(user_id, holding_id)
        except HoldingNotFoundError:
            return Response(status=204)
        profile = _profile_client.get_or_create_profile(user_id)
        mode = profile["transaction_type"]
        # Same reasoning as TransactionListView.post's rewind call — a
        # deleted TRANSACTION-mode BUY/SELL changes the share-count
        # timeline just as much as a created one does.
        if mode == "TRANSACTION" and transaction["type"] in ("BUY", "SELL"):
            _client.rewind_dividends_synced_through(user_id, holding_id, transaction["date"])
        _refresh_holding_rollup(user_id, holding_id, mode)
        return Response(status=204)
