"""equicast-core: shared AWS storage clients for equicast (S3 market-data
reads, DynamoDB user-profile storage, S3 JSON user-owned data)."""

from equicast_core.accounts import (
    MAX_ACCOUNTS,
    AccountAlreadyExistsError,
    AccountLimitExceededError,
    AccountNotFoundError,
    AccountsClient,
)
from equicast_core.client import (
    ASSET_CLASSES,
    DEFAULT_PRICE_RANGE,
    PRICE_RANGES,
    MarketDataClient,
)
from equicast_core.holdings import (
    MAX_HOLDINGS_FOR_ACCOUNT,
    MAX_HOLDINGS_FOR_PIE,
    MAX_HOLDINGS_FOR_WATCHLIST,
    AllocationError,
    HoldingAlreadyExistsError,
    HoldingLimitExceededError,
    HoldingNotFoundError,
    HoldingsClient,
)
from equicast_core.pies import (
    MAX_PIES,
    PieLimitExceededError,
    PieNotFoundError,
    PiesClient,
)
from equicast_core.transactions import (
    MAX_TRANSACTIONS_FOR_HOLDING,
    TRANSACTION_ACTIONS,
    InsufficientSharesError,
    TransactionAlreadyExistsError,
    TransactionAmountError,
    TransactionLimitExceededError,
    TransactionNotFoundError,
    TransactionsClient,
)
from equicast_core.user_profiles import UserProfileClient
from equicast_core.watchlists import (
    MAX_WATCHLISTS,
    WatchlistLimitExceededError,
    WatchlistNotFoundError,
    WatchlistsClient,
)

__version__ = "0.1.0"

__all__ = [
    "MAX_ACCOUNTS",
    "AccountAlreadyExistsError",
    "AccountLimitExceededError",
    "AccountNotFoundError",
    "AccountsClient",
    "MAX_PIES",
    "PieLimitExceededError",
    "PieNotFoundError",
    "PiesClient",
    "MAX_WATCHLISTS",
    "WatchlistLimitExceededError",
    "WatchlistNotFoundError",
    "WatchlistsClient",
    "MAX_HOLDINGS_FOR_ACCOUNT",
    "MAX_HOLDINGS_FOR_PIE",
    "MAX_HOLDINGS_FOR_WATCHLIST",
    "AllocationError",
    "HoldingAlreadyExistsError",
    "HoldingLimitExceededError",
    "HoldingNotFoundError",
    "HoldingsClient",
    "MAX_TRANSACTIONS_FOR_HOLDING",
    "TRANSACTION_ACTIONS",
    "InsufficientSharesError",
    "TransactionAlreadyExistsError",
    "TransactionAmountError",
    "TransactionLimitExceededError",
    "TransactionNotFoundError",
    "TransactionsClient",
    "ASSET_CLASSES",
    "DEFAULT_PRICE_RANGE",
    "PRICE_RANGES",
    "MarketDataClient",
    "UserProfileClient",
]
