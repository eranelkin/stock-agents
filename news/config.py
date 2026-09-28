from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class NewsConfig(BaseSettings):
    ibk_host: str = "127.0.0.1"
    # 7496 = TWS live | 4002 = IB Gateway paper | 4001 = IB Gateway live
    ibk_port: int = 7496
    ibk_client_id: int = 1
    ibk_news_results: int = 10

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
