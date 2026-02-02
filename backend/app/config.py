from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_ignore_empty=True,
    )

    app_name: str = "AtlasRAG"
    database_url: str = "postgresql+psycopg2://atlas:atlas@localhost:5432/atlas"
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"
    app_encryption_key: str = ""
    rag_top_k: int = 5
    rag_min_score: float = 0.2
    agent_history_limit: int = 12
    agent_select_rounds: int = 3
    agent_select_rows: int = 200
    planner_model: str = "gpt-4o-mini"
    responder_model: str = "gpt-4o-mini"
    db_dialect: str = "postgres"
    sql_max_queries: int = 3
    sql_max_rows: int = 200
    sql_timeout_ms: int = 5000
    planner_retry_limit: int = 2
    schema_context_tables_limit: int = 80
    schema_context_columns_limit: int = 40
    schema_context_sample_rows_limit: int = 5
    schema_context_constraints_limit: int = 200
    schema_context_indexes_limit: int = 200
    environment: str = "development"
    rate_limit_per_minute: int = 30
    cors_origins: str = "http://localhost:5173"
    cors_allow_credentials: bool = False
    log_level: str = "DEBUG"


settings = Settings()
