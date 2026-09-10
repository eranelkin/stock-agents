from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# Always load from the project root .env, regardless of CWD
_ROOT_ENV = Path(__file__).parent.parent / ".env"


class Settings(BaseSettings):
    alpha_vantage_api_key: str = ""
    finnhub_api_key: str = ""
    market_data_output_dir: str = "./outputs"
    alpha_vantage_rpm: int = 5
    alpha_vantage_max_symbols: int = 0

    model_config = SettingsConfigDict(
        env_file=str(_ROOT_ENV),
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
