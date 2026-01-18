from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    app_name: str = "AtlasRAG"
    database_url: str = "postgresql+psycopg2://atlas:atlas@localhost:5432/atlas"
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"
    app_encryption_key: str = ""
    rag_top_k: int = 5
    rag_min_score: float = 0.2
    environment: str = "development"
    rate_limit_per_minute: int = 30


settings = Settings()
