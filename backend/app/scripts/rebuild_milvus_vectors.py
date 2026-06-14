"""重建 Milvus 向量库：从 SQL `kb_chunks` 全量重新 embed 写入。

⚠️  破坏性：脚本会 drop 现有 collection 再用新 schema 重建，所有现存向量丢失。
    SQL `kb_chunks` 是 source of truth —— 重 embed 之后向量与 SQL 重新对齐。

适用场景：
  - Milvus collection 缺 `member_id` 字段（早期部署未带此字段的旧 schema）
  - 向量数据被人为弄脏 / 错位，需要彻底重置

前置条件：
  - SQL `kb_chunks.member_id` 已被回填（先跑 `migrate_kb_member_binding.py`）
  - Milvus 已起；环境变量 `HEALTH_AGENT_LLM_API_KEY`（或 `HEALTH_AGENT_EMBEDDING_API_KEY`）已设

用法：
  python -m backend.app.scripts.rebuild_milvus_vectors            # 实际重建
  python -m backend.app.scripts.rebuild_milvus_vectors --dry-run  # 只统计，不写
  python -m backend.app.scripts.rebuild_milvus_vectors --limit 50 # 只处理前 50 条用于冒烟
"""
from __future__ import annotations

import argparse
import sys

from app.core.config import settings
from app.db.session import SessionLocal
from app.models.kb import KbChunk
from app.services.embedding import DashScopeEmbeddingService
from app.services.vector_store import MilvusVectorStore, VectorRecord

BATCH_SIZE = 10  # DashScope text-embedding-v3 单次最多 10 条


def _build_store() -> MilvusVectorStore:
    return MilvusVectorStore(
        uri=settings.milvus_uri,
        token=settings.milvus_token,
        collection_name=settings.milvus_collection,
        dimension=settings.embedding_dimension,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="重建 Milvus 向量库")
    parser.add_argument("--dry-run", action="store_true", help="只统计，不写 Milvus")
    parser.add_argument("--limit", type=int, default=None, help="只处理前 N 条（冒烟测试用）")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        query = db.query(
            KbChunk.chunk_id,
            KbChunk.document_id,
            KbChunk.member_id,
            KbChunk.content,
        ).order_by(KbChunk.id.asc())
        if args.limit is not None:
            query = query.limit(args.limit)
        rows = query.all()
    finally:
        db.close()

    print(f"读到 {len(rows)} 条 chunks")

    missing = [r for r in rows if not r.member_id]
    if missing:
        affected_docs = sorted({r.document_id for r in missing})
        print(f"⚠️  {len(missing)} 条 chunk 缺 member_id（来自 {len(affected_docs)} 个 document）")
        print("   请先跑：python -m backend.app.scripts.migrate_kb_member_binding")
        return 1

    if not settings.embedding_api_key and not settings.llm_api_key:
        print("⚠️  未配置 HEALTH_AGENT_EMBEDDING_API_KEY 或 HEALTH_AGENT_LLM_API_KEY")
        return 1

    if args.dry_run:
        print("[dry-run] 不执行任何写操作")
        return 0

    # 1) 预连接 + drop 旧 collection
    store = _build_store()
    print(f"drop collection: {store.collection_name}")
    store.client.drop_collection(store.collection_name)

    # 2) 重新构造触发 create_collection（新 schema 含 member_id）
    store = _build_store()
    print(f"recreated collection: {store.collection_name}")

    # 3) 全量 embed + 批量 upsert
    embedding_service = DashScopeEmbeddingService(
        model=settings.embedding_model,
        api_key=settings.embedding_api_key or settings.llm_api_key,
    )

    total = len(rows)
    for start in range(0, total, BATCH_SIZE):
        batch = rows[start:start + BATCH_SIZE]
        vectors = embedding_service.embed_many([r.content for r in batch])
        store.upsert([
            VectorRecord(
                chunk_id=r.chunk_id,
                document_id=r.document_id,
                member_id=r.member_id,
                embedding=vec,
            )
            for r, vec in zip(batch, vectors)
        ])
        print(f"  upsert {start + len(batch)}/{total}")

    print("done")
    return 0


if __name__ == "__main__":
    sys.exit(main())
