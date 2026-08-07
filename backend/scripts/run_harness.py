"""Harness CLI：运行 Agent 质量回归测试。

用法:
    cd backend
    python scripts/run_harness.py            # Mock 模式，验证框架
    python scripts/run_harness.py --real     # 真实 LLM 模式，做回归
    python scripts/run_harness.py --case meal_dad_dinner_001   # 跑指定用例
"""

import argparse
import json
import sys
from pathlib import Path

# 把 backend/ 加入 sys.path
BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import settings
from app.db.session import Base
from harness.case import EvalCase
from harness.runner import HarnessRunner
from harness.report import print_report
from harness.seed import seed_harness_data


def load_cases(path: Path, case_filter: str | None = None) -> list[EvalCase]:
    """从 JSON 文件加载 eval cases。"""
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    cases = [EvalCase.model_validate(item) for item in data]
    if case_filter:
        cases = [c for c in cases if case_filter in c.case_id]
    return cases


def main():
    parser = argparse.ArgumentParser(description="Harness Engineering Regression Runner")
    parser.add_argument("--real", action="store_true", help="使用真实 LLM 调用（默认 Mock 模式）")
    parser.add_argument("--case", type=str, default=None, help="只跑包含此关键词的用例")
    parser.add_argument("--cases-file", type=str, default=None,
                        help="eval cases 文件路径（默认 harness/cases/p1_core.json）")
    args = parser.parse_args()

    # 加载 cases
    cases_file = Path(args.cases_file) if args.cases_file else BACKEND_DIR / "harness" / "cases" / "p1_core.json"
    cases = load_cases(cases_file, args.case)
    if not cases:
        print("No eval cases found.")
        sys.exit(1)

    mode = "REAL LLM" if args.real else "MOCK"
    print(f"\n🔧 Harness Regression — Mode: {mode}")
    print(f"   Cases: {len(cases)}")
    print(f"   Source: {cases_file}")

    # 创建隔离测试数据库
    engine = create_engine(settings.test_database_url)
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    db = Session()

    try:
        # 灌入测试数据
        member_ids = seed_harness_data(db)

        # 创建 runner
        runner = HarnessRunner(db, member_ids, use_real_llm=args.real)

        # 逐个执行
        results = []
        for case in cases:
            print(f"   Running: {case.case_id}...", end=" ", flush=True)
            result = runner.run_case(case)
            status = "✅" if result.passed else "❌"
            print(f"{status} ({result.latency_ms}ms)")
            results.append(result)

        # 打印报告
        print_report(results)

        # 退出码
        failed = sum(1 for r in results if not r.passed)
        sys.exit(1 if failed > 0 else 0)
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)


if __name__ == "__main__":
    main()
