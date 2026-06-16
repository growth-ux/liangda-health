"""为 agent_messages 表新增 card 列，存储结构化 respond payload（JSON 字符串）。

用法：
    python -m backend.app.scripts.migrate_add_agent_card            # 实际迁移
    python -m backend.app.scripts.migrate_add_agent_card --dry-run  # 只预览不写库
"""
from __future__ import annotations

import argparse
import sys

from sqlalchemy import text

from app.db.session import SessionLocal


def _column_exists(db, table: str, column: str) -> bool:
    rows = db.execute(text(f"SHOW COLUMNS FROM {table}")).fetchall()
    return any(row[0] == column for row in rows)


def migrate(db, dry_run: bool = False) -> dict:
    summary = {"table": "agent_messages", "column": "card", "existed": False, "added": False}

    if _column_exists(db, "agent_messages", "card"):
        summary["existed"] = True
        return summary

    ddl = "ALTER TABLE agent_messages ADD COLUMN card TEXT NULL"
    print(ddl)
    if not dry_run:
        db.execute(text(ddl))
        db.commit()
        summary["added"] = True

    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="为 agent_messages 增加 card 列")
    parser.add_argument("--dry-run", action="store_true", help="只预览不写库")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        summary = migrate(db, dry_run=args.dry_run)
        if summary["existed"]:
            print("列已存在，跳过。")
        elif summary["added"]:
            print("列已添加。")
        else:
            print("dry-run 完成，未写库。")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
