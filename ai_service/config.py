from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # LLM — LLM_MODEL is the full litellm model string (e.g. "gpt-4o", "claude-3-opus-20240229", "gemini/gemini-1.5-flash")
    llm_model: str = "gpt-4o"
    llm_temperature: float = 0.2
    llm_max_tokens: int = 4096
    llm_timeout_seconds: int = 60
    llm_max_retries: int = 5
    llm_request_delay_seconds: float = 0.0
    llm_json_mode: bool = True  # set False for models that don't support response_format JSON mode (e.g. openrouter/owl-alpha)

    # Agent behavior
    agent_mode: str = "parallel"  # parallel | chain

    # Concurrency
    max_concurrent_pipelines: int = 5
    max_concurrent_agents: int = 2
    max_concurrent_ceo_pipelines: int = 4

    # Output
    output_format: str = "json"
    output_dir: str = "./outputs"

    # Data sources
    data_json: str = "./mocks/Data.json"
    sectors_json: str = "./mocks/Sectors.json"
    macro_json: str = "./mocks/Macro.json"

    # Database
    postgres_host: str = "localhost"
    postgres_port: int = 5434
    postgres_db: str = "stock_agents"
    postgres_user: str = "sa_user"
    postgres_password: str = "changeme"

    # Tavily web search
    tavily_api_keys: str = ""  # comma-separated; auto-rotates on quota/rate-limit errors
    tavily_key_cooldown_seconds: float = 900  # 15 min — an exhausted key becomes eligible to retry after this
    search_enabled: bool = False
    search_max_results: int = 5
    search_depth: str = "basic"  # basic | advanced
    search_mode: str = "prefetch"  # prefetch | tool_call
    search_max_tool_rounds: int = 10  # max LLM↔tool cycles before forcing final answer
    search_days: int = 3              # Tavily `days` param — fallback cutoff when since-last-close is disabled
    search_since_last_close_enabled: bool = True  # True = filter by last NYSE close instead of `search_days` (rollback switch)

    # Gemini Google Search grounding — replaces Tavily for test runs on Gemini models.
    # Prod always uses Tavily (real verified published_date per article); test uses
    # grounding to avoid burning Tavily's paid quota on non-production runs.
    search_grounding_enabled_test: bool = True  # False = test always uses Tavily too (rollback switch)

    # Pre-market data
    finnhub_api_key: str = ""
    premarket_enabled: bool = True
    premarket_source: str = "auto"         # auto | finnhub | yfinance

    # Market data enrichment
    market_data_output_dir: str = "market-data/outputs"

    # Service
    ai_service_port: int = 4102
    backend_url: str = "http://localhost:4101"  # used only for the run-alert callback (Tavily quota notice)

    @property
    def tavily_api_key_list(self) -> list[str]:
        """Parsed, ordered Tavily API keys from the comma-separated setting."""
        return [k.strip() for k in self.tavily_api_keys.split(",") if k.strip()]

    @property
    def database_url(self) -> str:
        """Async-compatible PostgreSQL DSN for SQLAlchemy."""
        return (
            f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
