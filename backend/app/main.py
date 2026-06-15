from collections.abc import Callable
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy import inspect, text
from pathlib import Path

from app.api.agent import router as agent_router
from app.api.device import router as device_router
from app.api.health_analysis import router as health_analysis_router
from app.api.kb import router as kb_router
from app.api.mall import router as mall_router
from app.api.members import router as members_router
from app.api.notice import router as notice_router
from app.core.config import settings
from app.db.session import Base, SessionLocal, engine
from app.models import agent as _agent_models
from app.models import device as _device_models
from app.models import kb as _kb_models
from app.models import mall as _mall_models
from app.models import member as _member_models
from app.models import notice as _notice_models
from app.repositories.member_repository import SqlAlchemyMemberRepository
from app.services.device_service import DeviceService


def ensure_schema_updates() -> None:
    inspector = inspect(engine)
    table_names = inspector.get_table_names()

    with engine.begin() as connection:
        if "kb_documents" in table_names:
            columns = {column["name"] for column in inspector.get_columns("kb_documents")}
            if "member_id" not in columns:
                connection.execute(text("ALTER TABLE kb_documents ADD COLUMN member_id VARCHAR(64) NULL"))
            if "fact_extract_status" not in columns:
                connection.execute(
                    text(
                        "ALTER TABLE kb_documents "
                        "ADD COLUMN fact_extract_status VARCHAR(32) NOT NULL DEFAULT 'pending'"
                    )
                )
            else:
                connection.execute(
                    text(
                        "ALTER TABLE kb_documents "
                        "MODIFY COLUMN fact_extract_status VARCHAR(32) NOT NULL DEFAULT 'pending'"
                    )
                )
            if "fact_extract_error" not in columns:
                connection.execute(text("ALTER TABLE kb_documents ADD COLUMN fact_extract_error TEXT NULL"))
            indexes = {index["name"] for index in inspector.get_indexes("kb_documents")}
            if "ix_kb_documents_member_id" not in indexes:
                connection.execute(text("CREATE INDEX ix_kb_documents_member_id ON kb_documents (member_id)"))
            if "ix_kb_documents_fact_extract_status" not in indexes:
                connection.execute(
                    text("CREATE INDEX ix_kb_documents_fact_extract_status ON kb_documents (fact_extract_status)")
                )

        if "mall_products" in table_names:
            columns = {column["name"] for column in inspector.get_columns("mall_products")}
            if "image_url" not in columns:
                connection.execute(text("ALTER TABLE mall_products ADD COLUMN image_url VARCHAR(255) NULL"))


def ensure_device_seed_data(session_factory: Callable[[], object] = SessionLocal) -> None:
    db = session_factory()
    try:
        members = SqlAlchemyMemberRepository(db).list_members()
        service = DeviceService(db)
        for member in members:
            service.ensure_recent_7_days(member.member_id)
    finally:
        db.close()


@asynccontextmanager
async def lifespan(_: FastAPI, session_factory: Callable[[], object]):
    ensure_device_seed_data(session_factory)
    yield


def create_app(session_factory: Callable[[], object] = SessionLocal) -> FastAPI:
    Base.metadata.create_all(bind=engine)
    ensure_schema_updates()
    settings.upload_dir.mkdir(parents=True, exist_ok=True)
    mall_products_dir = Path(__file__).resolve().parents[2] / "frontend" / "public" / "mall-products"

    @asynccontextmanager
    async def app_lifespan(app: FastAPI):
        async with lifespan(app, session_factory):
            yield

    app = FastAPI(title=settings.app_name, lifespan=app_lifespan)
    origins = [origin.strip() for origin in settings.cors_origins.split(",") if origin.strip()]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(agent_router)
    app.include_router(device_router)
    app.include_router(health_analysis_router)
    app.include_router(kb_router)
    app.include_router(mall_router)
    app.include_router(members_router)
    app.include_router(notice_router)
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
