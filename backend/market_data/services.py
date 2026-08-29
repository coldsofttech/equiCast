from equicast.data.fetch import fetch_history
from equicast.data.storage import write_parquet


def get_history(ticker: str, period: str = "1y", interval: str = "1d") -> list[dict]:
    """Fetch history for `ticker`, cache it as Parquet, and return JSON-ready records."""
    df = fetch_history(ticker, period=period, interval=interval)
    write_parquet(df, ticker)

    df = df.copy()
    df["date"] = df["date"].astype(str)
    return df.to_dict(orient="records")
