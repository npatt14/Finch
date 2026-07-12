from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="FINCH_", env_file=".env", extra="ignore")

    gateway_api_key: str = ""
    gateway_base_url: str = "https://ai-gateway.vercel.sh/v1"
    extraction_model: str = "anthropic/claude-haiku-4.5"
    adjudication_model: str = "anthropic/claude-sonnet-5"
    voyage_api_key: str = ""
    embedding_model: str = "voyage-law-2"
    qdrant_url: str = ""
    qdrant_api_key: str = ""
    tavily_api_key: str = ""
    courtlistener_token: str = ""
    database_url: str = ""
    api_secret: str = ""
    frontend_origin: str = "*"
    max_units: int = 40
    max_chars: int = 200000
