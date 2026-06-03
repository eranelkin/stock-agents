from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Database
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_db: str = "stock_agents"
    postgres_user: str = "sa_user"
    postgres_password: str = "changeme"

    # Backend
    backend_port: int = 4101
    secret_key: str = "change-this-in-production"
    cors_origins: str = "http://localhost:4100"

    # AI service
    ai_service_host: str = "ai-service"  # use "localhost" when running outside Docker
    ai_service_port: int = 4102

    # Tavily web search
    tavily_api_key: str = ""
    search_enabled: bool = False
    search_max_results: int = 5
    search_depth: str = "basic"
    search_mode: str = "prefetch"  # prefetch | tool_call

    @property
    def database_url(self) -> str:
        return (
            f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def ai_service_url(self) -> str:
        return f"http://{self.ai_service_host}:{self.ai_service_port}"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
