from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="FINCH_", env_file=".env", extra="ignore")

    gateway_api_key: str = ""
    gateway_base_url: str = "https://ai-gateway.vercel.sh/v1"
    extraction_model: str = "anthropic/claude-haiku-4.5"
    adjudication_model: str = "anthropic/claude-sonnet-5"
    voyage_api_key: str = ""
    embedding_model: str = "voyage-law-2"
    rerank_enabled: bool = False
    rerank_model: str = "rerank-2.5"
    retrieval_candidates: int = 30
    chunk_target_tokens: int = 1000
    metadata_check: bool = False
    qdrant_url: str = ""
    qdrant_api_key: str = ""
    tavily_api_key: str = ""
    courtlistener_token: str = ""
    database_url: str = ""
    api_secret: str = ""
    frontend_origin: str = "*"
    max_units: int = 40
    max_chars: int = 200000
    verify_rate_per_ip: int = 8
    verify_rate_global: int = 80
    chat_rate_per_ip: int = 40
    rate_window_seconds: int = 600
    global_window_seconds: int = 3600
