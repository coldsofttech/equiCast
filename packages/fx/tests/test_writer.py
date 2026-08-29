from pathlib import Path

import pandas as pd
from equicast_fx.writer import write_profile_parquet


def test_write_profile_parquet_partitions_by_pair(tmp_path: Path) -> None:
    profile = {
        "from_currency": "GBP",
        "to_currency": "USD",
        "exchange": "CCY",
        "region": "US",
        "description": "GBP/USD",
        "last_updated": "2026-08-28T21:29:05+00:00",
        "source": "yfinance",
    }

    path = write_profile_parquet(profile, tmp_path)

    assert path == tmp_path / "fx=GBPUSD" / "profile.parquet"
    result = pd.read_parquet(path)
    assert result.to_dict(orient="records") == [profile]
