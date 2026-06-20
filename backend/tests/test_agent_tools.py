from datetime import datetime

from app.models.kb import KbChunk, KbDocument
from app.services.agent_tools import KbSearchTool


class FakeEmbeddingService:
    def embed(self, text):
        return [1.0]


class FakeVectorStore:
    def __init__(self):
        self.calls = []

    def search(self, query_embedding, top_k, member_id=None):
        self.calls.append(member_id)
        if member_id == "mem_1":
            return [type("Hit", (), {"chunk_id": "chunk_1", "score": 0.9})()]
        return []


class FakeKbRepository:
    def __init__(self):
        self.requested_ids = []

    def get_chunks_by_ids(self, chunk_ids):
        self.requested_ids = chunk_ids
        return [
            KbChunk(
                chunk_id="chunk_1",
                document_id="doc_1",
                member_id="mem_1",
                page_no=2,
                content="血压 152，偏高",
                created_at=datetime(2026, 6, 13, 10, 0, 0),
            )
        ]

    def get_document(self, document_id):
        return KbDocument(
            document_id=document_id,
            file_name="report.pdf",
            file_path="/tmp/report.pdf",
            file_size=128,
            page_count=2,
            title="妈妈体检报告",
            status="ready",
            created_at=datetime(2026, 6, 13, 10, 0, 0),
            updated_at=datetime(2026, 6, 13, 10, 0, 0),
        )


def test_kb_search_tool_searches_with_member_id():
    repository = FakeKbRepository()
    tool = KbSearchTool(repository, FakeEmbeddingService(), FakeVectorStore(), allowed_member_ids=["mem_1"])

    result = tool.search(query="爸爸血糖", member_id="mem_1")

    assert repository.requested_ids == ["chunk_1"]
    assert "文档：妈妈体检报告" in result
    assert "页码：2" in result
    assert "血压 152，偏高" in result


def test_kb_search_tool_rejects_unknown_member_id():
    vector_store = FakeVectorStore()
    tool = KbSearchTool(FakeKbRepository(), FakeEmbeddingService(), vector_store, allowed_member_ids=["mem_1"])

    result = tool.search(query="爸爸血糖", member_id="mem_unknown")

    assert "Error" in result
    assert "不在可用家人列表中" in result
    assert vector_store.calls == []  # 没调用 vector store


def test_kb_search_tool_filters_by_member_id_in_vector_store():
    vector_store = FakeVectorStore()
    tool = KbSearchTool(FakeKbRepository(), FakeEmbeddingService(), vector_store, allowed_member_ids=["mem_1", "mem_2"])

    tool.search(query="爸爸血糖", member_id="mem_2")

    assert vector_store.calls == ["mem_2"]


class FakeMemoryService:
    def __init__(self):
        self.calls = []

    def search_text(self, query, member_id=None, limit=5):
        self.calls.append((query, member_id, limit))
        return "[avoidance] 爸爸不喜欢鱼"


def test_memory_search_tool_returns_memory_text():
    from app.services.agent_tools import MemorySearchTool

    service = FakeMemoryService()
    tool = MemorySearchTool(service)

    result = tool.search(query="爸爸 饮食 排斥", member_id="mem_dad", limit=3)

    assert service.calls == [("爸爸 饮食 排斥", "mem_dad", 3)]
    assert "爸爸不喜欢鱼" in result


def test_memory_search_tool_rejects_empty_query():
    from app.services.agent_tools import MemorySearchTool

    service = FakeMemoryService()
    tool = MemorySearchTool(service)

    result = tool.search(query="   ")

    assert result == "Error: query 不能为空"
    assert service.calls == []


def test_memory_search_tool_pushes_evidence_item():
    from app.services.agent_evidence import AgentEvidenceCollector
    from app.services.agent_tools import MemorySearchTool

    collector = AgentEvidenceCollector()
    service = FakeMemoryService()
    tool = MemorySearchTool(service, evidence_collector=collector)

    tool.search(query="爸爸 饮食 排斥", member_id="mem_dad")

    assert collector.content_items[0].type == "memory"
    assert collector.content_items[0].source_label == "互动记忆"
    assert "[" not in collector.content_items[0].excerpt
    assert collector.content_items[0].excerpt.startswith("爸爸不喜欢鱼")


def test_evidence_collector_dedupes_same_memory_evidence_item():
    from app.schemas.agent_response import EvidenceItem
    from app.services.agent_evidence import AgentEvidenceCollector

    collector = AgentEvidenceCollector()
    item = EvidenceItem(
        type="memory",
        title="关于「爸爸 饮食 排斥」的互动记忆",
        excerpt="爸爸不喜欢鱼",
        source_id="memory:mem_dad:爸爸 饮食 排斥",
        source_label="互动记忆",
    )

    collector.add_content(item)
    collector.add_content(item)

    assert len(collector.content_items) == 1


class FakeMealPlanService:
    def __init__(self):
        self.calls = []
        self.evidence_calls = []

    def build(self, *, scope, member_id=None, goal=None, meal_type="day"):
        self.calls.append((scope, member_id, goal, meal_type))
        return "早餐：燕麦牛奶\n午餐：杂粮饭\n晚餐：清蒸鱼"

    def get_evidence_items(self, *, scope, member_id=None):
        self.evidence_calls.append((scope, member_id))
        from app.schemas.agent_response import EvidenceItem

        return [
            EvidenceItem(
                type="report_fact",
                title="5 月体检报告",
                excerpt="报告提示血压偏高，建议控制盐分摄入。",
                source_id="fact_1",
                source_label="5 月体检报告 p3",
            ),
            EvidenceItem(
                type="device",
                title="最近7天手环",
                excerpt="平均睡眠 5.2 小时，最近步数偏低。",
                source_id="device:mem_dad:recent_7d",
                source_label="最近7天手环",
            ),
        ]


def test_meal_plan_tool_pushes_report_and_device_evidence_items():
    from app.services.agent_evidence import AgentEvidenceCollector
    from app.services.agent_tools import MealPlanTool

    collector = AgentEvidenceCollector()
    service = FakeMealPlanService()
    tool = MealPlanTool(service, allowed_member_ids=["mem_dad"], evidence_collector=collector)

    result = tool.build(scope="member", member_id="mem_dad", meal_type="day")

    assert "早餐" in result
    assert service.calls == [("member", "mem_dad", None, "day")]
    assert service.evidence_calls == [("member", "mem_dad")]
    assert [item.type for item in collector.content_items] == ["report_fact", "device"]


class FakeMallRecommendService:
    def __init__(self):
        self.calls = []

    def recommend(self, *, scope, meal_plan_text, member_id=None, query_text="", limit=5):
        self.calls.append((scope, meal_plan_text, member_id, query_text, limit))
        return {
            "items": [
                {
                    "product_id": "p_salt",
                    "name": "低钠盐",
                    "reason": "契合低钠方向",
                    "price_text": "¥15.9",
                    "image_url": None,
                    "image_emoji": "🧂",
                    "score": 80,
                    "evidence_source": "报告健康事实 + 商品标签",
                }
            ],
            "is_error": False,
            "error": None,
        }


def test_mall_recommend_tool_returns_structured_json():
    """工具把 service 的 dict JSON 序列化后返回，runner 后续按结构解析。"""
    from app.services.agent_tools import MallRecommendTool

    service = FakeMallRecommendService()
    tool = MallRecommendTool(service, allowed_member_ids=["mem_dad"])

    result = tool.recommend(
        scope="member",
        member_id="mem_dad",
        meal_plan_text="晚餐：低钠杂粮饭",
        limit=2,
    )

    assert service.calls == [("member", "晚餐：低钠杂粮饭", "mem_dad", "", 2)]
    import json

    payload = json.loads(result)
    assert payload["items"][0]["name"] == "低钠盐"
    # 不再是 "可选商品：" markdown
    assert "可选商品" not in result


def test_mall_recommend_tool_rejects_unknown_member():
    from app.services.agent_tools import MallRecommendTool

    service = FakeMallRecommendService()
    tool = MallRecommendTool(service, allowed_member_ids=["mem_dad"])

    result = tool.recommend(scope="member", member_id="mem_unknown", meal_plan_text="晚餐：低钠杂粮饭")

    assert "Error" in result
    assert service.calls == []


def test_mall_recommend_tool_allows_empty_meal_plan_text():
    """直接商品推荐（如"推荐一款适合全家人的油"）没有 meal_plan 时，
    工具必须放行并把空串透传给 service，让 service 用健康画像兜底匹配。"""
    from app.services.agent_tools import MallRecommendTool

    service = FakeMallRecommendService()
    tool = MallRecommendTool(service, allowed_member_ids=["mem_dad"])

    result = tool.recommend(scope="member", member_id="mem_dad", meal_plan_text="")

    assert "Error" not in result
    assert service.calls == [("member", "", "mem_dad", "", 5)]
    import json

    payload = json.loads(result)
    assert payload["items"][0]["name"] == "低钠盐"


def test_mall_recommend_tool_passes_query_text_for_category_requests():
    from app.services.agent_tools import MallRecommendTool

    service = FakeMallRecommendService()
    tool = MallRecommendTool(service, allowed_member_ids=["mem_dad"])

    result = tool.recommend(
        scope="member",
        member_id="mem_dad",
        meal_plan_text="",
        query_text="推荐一款适合全家人的油",
    )

    assert "Error" not in result
    assert service.calls == [("member", "", "mem_dad", "推荐一款适合全家人的油", 5)]


def test_mall_recommend_tool_pushes_product_evidence_items():
    from app.services.agent_evidence import AgentEvidenceCollector
    from app.services.agent_tools import MallRecommendTool

    collector = AgentEvidenceCollector()
    service = FakeMallRecommendService()
    tool = MallRecommendTool(service, allowed_member_ids=["mem_dad"], evidence_collector=collector)

    tool.recommend(
        scope="member",
        member_id="mem_dad",
        meal_plan_text="",
        query_text="推荐一款适合全家人的油",
    )

    assert len(collector.product_items) == 1
    assert collector.product_items[0].type == "product"
    assert collector.product_items[0].title == "低钠盐"
    assert collector.product_items[0].source_label == "报告健康事实 + 商品标签"


def test_kb_search_tool_pushes_first_chunk_only_as_evidence():
    """kb_search 只把第一个 chunk 写入 evidence；一次返回多个 chunk 也不能把右栏塞满。"""
    from app.services.agent_evidence import AgentEvidenceCollector

    class MultiChunkRepository(FakeKbRepository):
        def get_chunks_by_ids(self, chunk_ids):
            return [
                KbChunk(
                    chunk_id="chunk_1",
                    document_id="doc_1",
                    member_id="mem_1",
                    page_no=2,
                    content="血压 152，偏高",
                    created_at=datetime(2026, 6, 13, 10, 0, 0),
                ),
                KbChunk(
                    chunk_id="chunk_2",
                    document_id="doc_1",
                    member_id="mem_1",
                    page_no=3,
                    content="血脂偏高",
                    created_at=datetime(2026, 6, 13, 10, 0, 0),
                ),
            ]

    class MultiHitVectorStore:
        def search(self, query_embedding, top_k, member_id=None):
            return [
                type("Hit", (), {"chunk_id": "chunk_1", "score": 0.9})(),
                type("Hit", (), {"chunk_id": "chunk_2", "score": 0.8})(),
            ]

    collector = AgentEvidenceCollector()
    repository = MultiChunkRepository()
    tool = KbSearchTool(
        repository,
        FakeEmbeddingService(),
        MultiHitVectorStore(),
        allowed_member_ids=["mem_1"],
        evidence_collector=collector,
    )

    tool.search(query="体检报告", member_id="mem_1")

    assert len(collector.content_items) == 1
    assert collector.content_items[0].source_id == "chunk_1"
    assert collector.content_items[0].type == "report_fact"
    assert "妈妈体检报告" in collector.content_items[0].source_label
    assert "p2" in collector.content_items[0].source_label
