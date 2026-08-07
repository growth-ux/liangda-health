"""Context Pipeline 集成测试：验证端到端流程。"""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.session import Base
from app.models.member import Member
from app.models.health_fact import HealthFact
from app.models.device import DeviceDailyMetric
from app.services.context_pipeline import ContextPipeline, ContextBudget
from app.services.health_profile_service import HealthProfileService
from app.services.agent_evidence import AgentEvidenceCollector
from app.schemas.agent_response import EvidenceItem


@pytest.fixture
def db_session():
    """创建内存数据库会话。"""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


@pytest.fixture
def sample_member(db_session):
    """创建带健康数据的样本成员。"""
    import json
    member = Member(
        member_id="test_member_001",
        name="张三",
        relation="本人",
        birth_year=1980,  # 45 岁
        gender="男",
        height_cm=175,
        weight_kg=80,
        allergies="花生,海鲜",
        taste_preferences="清淡,少油",
        health_tags=json.dumps(["高血压", "高血脂"]),
    )
    db_session.add(member)
    db_session.commit()

    # 添加健康事实
    fact1 = HealthFact(
        fact_id="fact_001",
        member_id=member.member_id,
        fact_type="metric",
        name="收缩压",
        value="145",
        unit="mmHg",
        reference_range="90-140",
        status="warning",
        source_document_id="doc_001",
        source_page_no=1,
        evidence_text="收缩压 145mmHg，偏高",
    )
    fact2 = HealthFact(
        fact_id="fact_002",
        member_id=member.member_id,
        fact_type="metric",
        name="总胆固醇",
        value="6.2",
        unit="mmol/L",
        reference_range="2.8-5.7",
        status="danger",
        source_document_id="doc_001",
        source_page_no=2,
        evidence_text="总胆固醇 6.2mmol/L，明显偏高",
    )
    db_session.add_all([fact1, fact2])
    db_session.commit()

    return member


def test_health_profile_to_context_items(db_session, sample_member):
    """测试 HealthProfileService 能正确生成 ContextItems。"""
    service = HealthProfileService(db_session)
    items = service.member_context_items(sample_member.member_id)

    # 应该有多个 ContextItem
    assert len(items) > 0

    # 检查优先级分布
    sources = {item.source for item in items}
    assert "safety" in sources  # 过敏原
    assert "report_fact" in sources  # 健康事实
    assert "member_constraint" in sources  # 饮食原则

    # 检查 safety 项（过敏原）
    safety_items = [i for i in items if i.source == "safety"]
    assert len(safety_items) >= 2  # 花生 + 海鲜
    assert all(i.priority == 1000 for i in safety_items)

    # 检查 report_fact 项
    fact_items = [i for i in items if i.source == "report_fact"]
    assert len(fact_items) >= 2  # 血压 + 胆固醇
    assert all(i.priority == 900 for i in fact_items)

    # 检查 member_constraint 项（高血压/高血脂的饮食原则）
    constraint_items = [i for i in items if i.source == "member_constraint"]
    assert len(constraint_items) > 0
    assert all(i.priority == 500 for i in constraint_items)


def test_pipeline_ranking_budgeting_pruning(db_session, sample_member):
    """测试 Pipeline 的三件套流程。"""
    service = HealthProfileService(db_session)
    items = service.member_context_items(sample_member.member_id)

    # 使用较小的预算来触发裁剪
    budget = ContextBudget(
        limits={
            "safety": 200,
            "report_fact": 300,
            "device_anomaly": 200,
            "member_constraint": 200,
            "member_profile": 100,
            "memory": 100,
        },
        total_limit=800,
    )
    pipeline = ContextPipeline(budget=budget)

    # 执行 Pipeline
    pruning_log = pipeline.process(items)

    # 验证结果
    assert pruning_log.kept_count > 0
    assert pruning_log.kept_tokens <= 800

    # 高优先级项应该优先保留
    kept_priorities = [i.priority for i in pruning_log.kept]
    assert max(kept_priorities) >= 900  # 至少保留了 report_fact

    # 如果有裁剪，验证 dropped 列表
    if pruning_log.dropped_count > 0:
        dropped_priorities = [d.item.priority for d in pruning_log.dropped]
        # 被裁剪的项优先级应该低于保留的最高优先级
        assert max(dropped_priorities) <= max(kept_priorities)


def test_evidence_collector_with_pruning(db_session, sample_member):
    """测试 AgentEvidenceCollector 能记录 pruning log。"""
    service = HealthProfileService(db_session)
    items = service.member_context_items(sample_member.member_id)

    # 执行 Pipeline
    budget = ContextBudget(total_limit=600)
    pipeline = ContextPipeline(budget=budget)
    pruning_log = pipeline.process(items)

    # 创建 Collector 并记录
    collector = AgentEvidenceCollector()

    # 添加一些 evidence items
    collector.add_content(EvidenceItem(
        type="report_fact",
        title="收缩压偏高",
        excerpt="收缩压 145mmHg",
        source_id="fact_001",
        source_label="doc_001 p1",
    ))

    # 记录 pruning log
    collector.add_pruning_log(pruning_log)

    # dump 应该包含 pruning_summary
    evidence = collector.dump()
    assert evidence is not None
    assert evidence.pruning_summary is not None
    assert "上下文装配" in evidence.pruning_summary

    # 如果有裁剪，summary 应该提到裁剪数量
    if pruning_log.dropped_count > 0:
        assert "裁剪" in evidence.pruning_summary


def test_pipeline_preserves_safety_items(db_session, sample_member):
    """测试 Pipeline 在高负载下仍然保留 safety 项。"""
    service = HealthProfileService(db_session)
    items = service.member_context_items(sample_member.member_id)

    # 使用极小的预算
    budget = ContextBudget(
        limits={
            "safety": 50,  # 只够 1 条 safety
            "report_fact": 50,
            "member_constraint": 50,
        },
        total_limit=150,
    )
    pipeline = ContextPipeline(budget=budget)
    pruning_log = pipeline.process(items)

    # 即使预算很小，也应该保留至少 1 条 safety 项（因为优先级最高）
    kept_safety = [i for i in pruning_log.kept if i.source == "safety"]
    assert len(kept_safety) >= 1


def test_pipeline_with_empty_input():
    """测试 Pipeline 处理空输入。"""
    pipeline = ContextPipeline()
    pruning_log = pipeline.process([])

    assert pruning_log.kept_count == 0
    assert pruning_log.dropped_count == 0
    assert pruning_log.kept_tokens == 0


def test_evidence_collector_empty_pruning():
    """测试 AgentEvidenceCollector 没有 pruning log 时的行为。"""
    collector = AgentEvidenceCollector()

    # 添加一个 evidence item
    collector.add_content(EvidenceItem(
        type="report_fact",
        title="测试",
        excerpt="测试内容",
        source_id="test_001",
        source_label="test",
    ))

    # dump 应该成功，但 pruning_summary 为 None
    evidence = collector.dump()
    assert evidence is not None
    assert evidence.pruning_summary is None


def test_multiple_pruning_logs():
    """测试 Collector 可以记录多个 pruning log。"""
    from app.services.context_pipeline import ContextItem

    collector = AgentEvidenceCollector()

    # 第一个 pruning log
    pipeline1 = ContextPipeline()
    items1 = [ContextItem(source="memory", priority=300, content=f"记忆{i}") for i in range(5)]
    log1 = pipeline1.process(items1)
    collector.add_pruning_log(log1)

    # 第二个 pruning log
    pipeline2 = ContextPipeline()
    items2 = [ContextItem(source="product", priority=200, content=f"商品{i}") for i in range(3)]
    log2 = pipeline2.process(items2)
    collector.add_pruning_log(log2)

    # 应该记录了两个 log
    assert len(collector.pruning_logs) == 2

    # 添加一个 evidence item 以便 dump 成功
    collector.add_content(EvidenceItem(
        type="report_fact",
        title="测试",
        excerpt="测试",
        source_id="test",
        source_label="test",
    ))

    evidence = collector.dump()
    assert evidence is not None
    assert evidence.pruning_summary is not None
    # summary 应该汇总两个 log
    assert "上下文装配" in evidence.pruning_summary
