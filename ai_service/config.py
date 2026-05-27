from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # LLM — LLM_MODEL is the full litellm model string (e.g. "gpt-4o", "claude-3-opus-20240229")
    llm_model: str = "gpt-4o"
    llm_temperature: float = 0.2
    llm_max_tokens: int = 4096
    llm_timeout_seconds: int = 60
    llm_max_retries: int = 3

    # Agent behavior
    agent_mode: str = "parallel"  # parallel | chain

    # Concurrency
    max_concurrent_pipelines: int = 10
    max_concurrent_agents: int = 8

    # Output
    output_format: str = "yaml"
    output_dir: str = "./outputs"

    # Database
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_db: str = "stock_agents"
    postgres_user: str = "sa_user"
    postgres_password: str = "changeme"

    # Service
    ai_service_port: int = 4102

    @property
    def database_url(self) -> str:
        """Async-compatible PostgreSQL DSN for SQLAlchemy."""
        return (
            f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
