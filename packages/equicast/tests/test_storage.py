from pathlib import Path

import pandas as pd
from equicast.data.storage import read_parquet, write_parquet


def test_write_then_read_roundtrip(tmp_path: Path) -> None:
    df = pd.DataFrame({"date": ["2024-01-01"], "close": [100.0]})

    write_parquet(df, "TEST", data_dir=tmp_path)
    result = read_parquet("TEST", data_dir=tmp_path)

    pd.testing.assert_frame_equal(result, df)
