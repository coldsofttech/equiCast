from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    data_dir: Path = Path("data")
    default_period: str = "1y"
    default_interval: str = "1d"


settings = Settings()
