from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # LLM — LLM_MODEL is the full litellm model string (e.g. "gpt-4o", "claude-3-opus-20240229")
    llm_model: str = "gpt-4o"
    llm_temperature: float = 0.2
    llm_max_tokens: int = 4096
    llm_timeout_seconds: int = 60
    llm_max_retries: int = 5
    llm_request_delay_seconds: float = 0.0

    # Agent behavior
    agent_mode: str = "parallel"  # parallel | chain

    # Concurrency
    max_concurrent_pipelines: int = 5
    max_concurrent_agents: int = 2

    # Output
    output_format: str = "yaml"
    output_dir: str = "./outputs"

    # Data sources
    data_json: str = "./Data.json"
    sectors_json: str = "./Sectors.json"

    # Database
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_db: str = "stock_agents"
    postgres_user: str = "sa_user"
    postgres_password: str = "changeme"

    # Tavily web search
    tavily_api_key: str = ""
    search_enabled: bool = False
    search_max_results: int = 5
    search_depth: str = "basic"  # basic | advanced
    search_mode: str = "prefetch"  # prefetch | tool_call
    search_max_tool_rounds: int = 10  # max LLM↔tool cycles before forcing final answer

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
