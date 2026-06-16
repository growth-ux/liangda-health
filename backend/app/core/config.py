from pathlib import Path

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


PROJECT_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    app_name: str = "liangda-health PDF KB"
    database_url: str = "mysql+pymysql://root:123@127.0.0.1:3306/liangda_health"
    test_database_url: str = "mysql+pymysql://root:123@127.0.0.1:3306/liangda_health_test"
    upload_dir: Path = Path("./backend/uploads")

    embedding_dimension: int = 1024
    embedding_model: str = "text-embedding-v3"
    embedding_api_key: str | None = "sk-f3c793c9e1ee4427abbc33311695588c"

    milvus_uri: str = "http://localhost:19530"
    milvus_token: str | None = None
    milvus_collection: str = "kb_chunks_vector"

    cors_origins: str = "http://localhost:5173,http://localhost:3000,http://localhost:3001,http://127.0.0.1:3000,http://127.0.0.1:3001"
    cloud_ocr_endpoint: str | None = None
    cloud_ocr_api_key: str | None = None

    llm_base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    llm_api_key: str | None = None
    llm_model: str = "qwen-plus"
    llm_timeout_seconds: int = 60
    llm_temperature: float = 0.3

    memory_enabled: bool = True
    memory_family_user_id: str = "default_family"
    memory_provider: str = "mem0"
    memory_milvus_collection: str = "agent_memories_vector"
    memory_dir: Path = PROJECT_ROOT / "backend" / "runtime" / "mem0"
    memory_history_db_path: Path = PROJECT_ROOT / "backend" / "runtime" / "mem0" / "history.db"

    @model_validator(mode="after")
    def normalize_memory_credentials(self):
        if not self.embedding_api_key:
            self.embedding_api_key = self.llm_api_key
        return self

    model_config = SettingsConfigDict(env_prefix="HEALTH_AGENT_", env_file=PROJECT_ROOT / ".env")


settings = Settings()
