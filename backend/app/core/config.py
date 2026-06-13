from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "liangda-health PDF KB"
    database_url: str = "sqlite:///./backend/dev.db"
    upload_dir: Path = Path("./backend/uploads")

    embedding_dimension: int = 64
    embedding_endpoint: str | None = None
    embedding_api_key: str | None = None

    milvus_enabled: bool = False
    milvus_uri: str = "http://localhost:19530"
    milvus_token: str | None = None
    milvus_collection: str = "kb_chunks_vector"

    cors_origins: str = "http://localhost:5173"
    cloud_ocr_endpoint: str | None = None
    cloud_ocr_api_key: str | None = None

    model_config = SettingsConfigDict(env_prefix="MEAL_AGENT_", env_file=".env")


settings = Settings()
