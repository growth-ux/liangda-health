from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy import inspect, text
from pathlib import Path

from app.api.agent import router as agent_router
from app.api.kb import router as kb_router
from app.api.mall import router as mall_router
from app.api.members import router as members_router
from app.core.config import settings
from app.db.session import Base, engine
from app.models import agent as _agent_models
from app.models import kb as _kb_models
from app.models import mall as _mall_models
from app.models import member as _member_models


def ensure_schema_updates() -> None:
    inspector = inspect(engine)
    table_names = inspector.get_table_names()

    with engine.begin() as connection:
        if "kb_documents" in table_names:
            columns = {column["name"] for column in inspector.get_columns("kb_documents")}
            if "member_id" not in columns:
                connection.execute(text("ALTER TABLE kb_documents ADD COLUMN member_id VARCHAR(64) NULL"))
            indexes = {index["name"] for index in inspector.get_indexes("kb_documents")}
            if "ix_kb_documents_member_id" not in indexes:
                connection.execute(text("CREATE INDEX ix_kb_documents_member_id ON kb_documents (member_id)"))

        if "mall_products" in table_names:
            columns = {column["name"] for column in inspector.get_columns("mall_products")}
            if "image_url" not in columns:
                connection.execute(text("ALTER TABLE mall_products ADD COLUMN image_url VARCHAR(255) NULL"))


def create_app() -> FastAPI:
    Base.metadata.create_all(bind=engine)
    ensure_schema_updates()
    settings.upload_dir.mkdir(parents=True, exist_ok=True)
    mall_products_dir = Path(__file__).resolve().parents[2] / "frontend" / "public" / "mall-products"

    app = FastAPI(title=settings.app_name)
    origins = [origin.strip() for origin in settings.cors_origins.split(",") if origin.strip()]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(agent_router)
    app.include_router(kb_router)
    app.include_router(mall_router)
    app.include_router(members_router)
    app.mount("/uploads", StaticFiles(directory=settings.upload_dir), name="uploads")
    app.mount("/mall-products", StaticFiles(directory=mall_products_dir), name="mall-products")

    @app.get("/api/health")
    def health():
        return {"status": "ok"}

    @app.get("/health")
    def health_legacy():
        """Deprecated alias for /api/health, kept for external monitors."""
        return {"status": "ok"}

    return app


app = create_app()
