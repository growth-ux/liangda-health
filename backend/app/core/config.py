from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "liangda-health PDF KB"
    database_url: str = "mysql+pymysql://root:123@127.0.0.1:3306/liangda_health"
    test_database_url: str = "mysql+pymysql://root:123@127.0.0.1:3306/liangda_health_test"
    upload_dir: Path = Path("./backend/uploads")

    embedding_dimension: int = 1024
    embedding_model: str = "text-embedding-v3"
    embedding_api_key: str | None = None

    milvus_enabled: bool = False
    milvus_uri: str = "http://localhost:19530"
    milvus_token: str | None = None
    milvus_collection: str = "kb_chunks_vector"

    cors_origins: str = "http://localhost:5173"
    cloud_ocr_endpoint: str | None = None
    cloud_ocr_api_key: str | None = None

    llm_base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    llm_api_key: str | None = None
    llm_model: str = "qwen-plus"
    llm_timeout_seconds: int = 60
    llm_temperature: float = 0.3

    model_config = SettingsConfigDict(env_prefix="HEALTH_AGENT_", env_file=".env")


settings = Settings()
