"""equicast-fx: class-based FX pair market data extraction."""

from equicast_fx.client import FXClient
from equicast_fx.config import FxPair, load_fx_pairs, parse_fx_pairs_json

__version__ = "0.1.0"

__all__ = ["FXClient", "FxPair", "load_fx_pairs", "parse_fx_pairs_json"]
