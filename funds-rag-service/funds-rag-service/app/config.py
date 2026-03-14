import os
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # OpenAI
    openai_api_key: str

    # PostgreSQL
    postgres_user: str = "rag"
    postgres_password: str = "changeme"
    postgres_db: str = "funds_rag"
    postgres_host: str = "db"
    postgres_port: int = 5432

    # RAG
    rag_port: int = 8100
    embedding_model: str = "text-embedding-3-small"
    embedding_dim: int = 1536
    top_k: int = 10
    # Path to funds data: JSONL (primary) — use cleaned file funds_clean.jsonl
    funds_jsonl_path: str = "data/funds_clean.jsonl"
    funds_csv_path: str = "data/funds.csv"

    @property
    def database_url(self) -> str:
        return (
            f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def database_url_sync(self) -> str:
        return (
            f"postgresql://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
