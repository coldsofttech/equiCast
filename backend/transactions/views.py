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
)
from identity.authentication import Auth0JWTAuthentication
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

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
_NUMERIC_FIELDS = {"no_of_shares", "average_price_native", "price_native", "amount_native", "fx_rate"}


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
_market_data_client = MarketDataClient(settings.MARKET_DATA_BUCKET, region_name=settings.AWS_REGION)


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
        try:
            _client.delete_transaction(user_id, holding_id, transaction_id)
        except TransactionNotFoundError:
            return Response(status=404)

        try:
            _holdings_client.get_holding(user_id, holding_id)
        except HoldingNotFoundError:
            return Response(status=204)
        profile = _profile_client.get_or_create_profile(user_id)
        _refresh_holding_rollup(user_id, holding_id, profile["transaction_type"])
        return Response(status=204)
