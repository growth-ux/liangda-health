"""将历史脏数据（member_id IS NULL OR member_id = 'default'）按 patient_name 严格匹配回填。

用法：
    python -m backend.scripts.migrate_kb_member_binding            # 实际迁移
    python -m backend.scripts.migrate_kb_member_binding --dry-run  # 只预览不写库
"""
from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass, field

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models.kb import KbChunk, KbDocument
from app.models.member import Member


@dataclass
class MigrationReport:
    matched: list[tuple[str, str]] = field(default_factory=list)
    unmatched: list[str] = field(default_factory=list)
    ambiguous: list[str] = field(default_factory=list)
    failed: list[tuple[str, str]] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "matched": len(self.matched),
            "unmatched": len(self.unmatched),
            "ambiguous": len(self.ambiguous),
            "failed": len(self.failed),
            "details": {
                "matched": self.matched,
                "unmatched": self.unmatched,
                "ambiguous": self.ambiguous,
                "failed": self.failed,
            },
        }


def _ensure_member_id_column(db: Session) -> None:
    """如果 kb_chunks.member_id 列不存在，添加（线上库增量升级用）。"""
    inspector_results = db.execute(text("SHOW COLUMNS FROM kb_chunks")).fetchall()
    column_names = {row[0] for row in inspector_results}
    if "member_id" not in column_names:
        db.execute(text(
            "ALTER TABLE kb_chunks ADD COLUMN member_id VARCHAR(64) NULL, "
            "ADD INDEX idx_kb_chunks_member_id (member_id)"
        ))
        db.commit()


def _find_member_by_name(db: Session, patient_name: str | None) -> list[str]:
    if not patient_name:
        return []
    members = (
        db.query(Member)
        .filter(Member.name == patient_name)
        .all()
    )
    return [m.member_id for m in members]


def migrate(db: Session, dry_run: bool = False) -> dict:
    report = MigrationReport()
    _ensure_member_id_column(db)

    dirty_documents = (
        db.query(KbDocument)
        .filter((KbDocument.member_id.is_(None)) | (KbDocument.member_id == "default"))
        .all()
    )

    for document in dirty_documents:
        try:
            candidates = _find_member_by_name(db, document.patient_name)
            if len(candidates) == 1:
                new_member_id = candidates[0]
                if not dry_run:
                    document.member_id = new_member_id
                    db.query(KbChunk).filter(
                        KbChunk.document_id == document.document_id
                    ).update({KbChunk.member_id: new_member_id})
                    db.commit()
                report.matched.append((document.document_id, new_member_id))
            elif len(candidates) > 1:
                report.ambiguous.append(document.document_id)
            else:
                report.unmatched.append(document.document_id)
        except Exception as exc:
            db.rollback()
            report.failed.append((document.document_id, str(exc)))

    return report.to_dict()


def main() -> int:
    parser = argparse.ArgumentParser(description="迁移 KB 历史脏数据")
    parser.add_argument("--dry-run", action="store_true", help="只预览不写库")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        report = migrate(db, dry_run=args.dry_run)
        print(f"匹配成功: {report['matched']}")
        print(f"未匹配:   {report['unmatched']}")
        print(f"重名歧义: {report['ambiguous']}")
        print(f"失败:     {report['failed']}")
        if report["matched"] or report["unmatched"] or report["ambiguous"] or report["failed"]:
            print()
            print("明细：")
            for category, items in report["details"].items():
                if items:
                    print(f"  [{category}] {items}")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())