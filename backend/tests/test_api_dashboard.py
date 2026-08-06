import json
from datetime import timedelta

from fastapi.testclient import TestClient

from app.core.time import utc_now
from app.db.session import get_db
from app.main import create_app
from app.models.agent import AgentMessage, AgentSession
from app.models.health_fact import HealthFact
from app.models.kb import KbDocument
from app.models.mall import MallCartItem, MallProduct
from app.models.member import Member
from app.models.notice import Notice


def create_client(db_session) -> TestClient:
    app = create_app()
    app.dependency_overrides[get_db] = lambda: db_session
    return TestClient(app)


def _recommendations(*product_ids: str) -> str:
    return json.dumps(
        [
            {"product_id": product_id, "name": f"商品{product_id}", "reason": "适合家庭健康需求"}
            for product_id in product_ids
        ],
        ensure_ascii=False,
    )


def _seed(db_session) -> None:
    now = utc_now()
    db_session.add_all(
        [
            MallProduct(
                product_id="prod_a",
                name="福临门低钠酱油",
                brand="福临门",
                category_code="seasoning",
                category_name="调味品",
                price_cents=990,
            ),
            MallProduct(
                product_id="prod_b",
                name="中茶绿茶礼盒",
                brand="中茶",
                category_code="wine_tea",
                category_name="酒水茶饮",
                price_cents=5900,
            ),
        ]
    )
    db_session.add(AgentSession(session_id="sess_1", title="爸爸今晚吃什么", status="active"))
    db_session.add_all(
        [
            AgentMessage(
                message_id="msg_user_1",
                session_id="sess_1",
                role="user",
                content="爸爸今晚吃什么？",
                status="done",
                created_at=now - timedelta(minutes=31),
            ),
            AgentMessage(
                message_id="msg_asst_1",
                session_id="sess_1",
                role="assistant",
                content="推荐如下",
                status="done",
                product_recommendations=_recommendations("prod_a", "prod_b"),
                token_prompt=500,
                token_completion=200,
                model_name="qwen-plus",
                created_at=now - timedelta(minutes=30),
            ),
            AgentMessage(
                message_id="msg_asst_2",
                session_id="sess_1",
                role="assistant",
                content="再推荐一次",
                status="done",
                product_recommendations=_recommendations("prod_a"),
                token_prompt=300,
                token_completion=100,
                model_name="qwen-plus",
                created_at=now,
            ),
        ]
    )
    db_session.add(MallCartItem(cart_owner_id="default_family", product_id="prod_a", quantity=2))
    db_session.add_all(
        [
            HealthFact(
                fact_id="fact_1",
                member_id="mem_father",
                fact_type="risk",
                name="血脂偏高",
                status="warning",
                source_document_id="doc_1",
                source_page_no=1,
                evidence_text="总胆固醇高于参考范围",
            ),
            HealthFact(
                fact_id="fact_2",
                member_id="mem_father",
                fact_type="metric",
                name="血压偏高",
                status="danger",
                source_document_id="doc_1",
                source_page_no=2,
                evidence_text="血压 152/96 mmHg",
            ),
        ]
    )
    db_session.add_all(
        [
            Notice(
                notice_id="not_1",
                category="health_alert",
                level="danger",
                title="血压偏高",
                description="描述",
                source="housekeeper",
                status="done",
                dedupe_key="dash_not_1",
            ),
            Notice(
                notice_id="not_2",
                category="system",
                level="info",
                title="欢迎",
                description="描述",
                source="system",
                status="unread",
                dedupe_key="dash_not_2",
            ),
        ]
    )
    db_session.commit()


def test_dashboard_aggregates_overview_and_funnel(db_session):
    _seed(db_session)
    with create_client(db_session) as client:
        response = client.get("/api/admin/dashboard")

    assert response.status_code == 200
    payload = response.json()

    overview = payload["overview"]
    assert overview["session_count"] == 1
    assert overview["message_count"] == 3
    assert overview["recommendation_count"] == 2
    assert overview["cart_item_count"] == 2
    assert overview["cart_amount_yuan"] == 19.8
    assert overview["health_fact_count"] == 2

    funnel = payload["funnel"]
    assert [step["name"] for step in funnel] == [
        "用户主动咨询", "AI 推荐消息", "推荐商品曝光", "加入购物车", "下单/支付"
    ]
    assert funnel[0]["value"] == 1   # 1 条用户消息
    assert funnel[1]["value"] == 2   # 2 条含推荐的消息
    assert funnel[2]["value"] == 3   # 推荐商品曝光总数
    assert funnel[3]["value"] == 2   # 购物车数量
    assert funnel[4]["value"] == 1   # 下单/支付估算值


def test_dashboard_brand_ranks_sorted_by_recommend_count(db_session):
    _seed(db_session)
    with create_client(db_session) as client:
        response = client.get("/api/admin/dashboard")

    ranks = response.json()["brand_ranks"]
    assert ranks[0]["brand"] == "福临门"
    assert ranks[0]["recommend_count"] == 2
    assert ranks[0]["cart_count"] == 2
    assert ranks[0]["amount_yuan"] == 19.8
    assert ranks[1]["brand"] == "中茶"
    assert ranks[1]["recommend_count"] == 1
    assert ranks[1]["cart_count"] == 0
    assert ranks[1]["amount_yuan"] == 0.0


def test_dashboard_category_penetration(db_session):
    _seed(db_session)
    with create_client(db_session) as client:
        response = client.get("/api/admin/dashboard")

    penetration = response.json()["category_penetration"]
    assert penetration[0] == {"category_name": "调味品", "recommend_count": 2}
    assert penetration[1] == {"category_name": "酒水茶饮", "recommend_count": 1}


def test_dashboard_fact_status_notice_rate_and_ai_usage(db_session):
    _seed(db_session)
    with create_client(db_session) as client:
        response = client.get("/api/admin/dashboard")

    payload = response.json()
    assert payload["fact_status"] == {"normal": 0, "warning": 1, "danger": 1}
    assert payload["notice_done"] == {"total": 2, "done": 1, "rate": 0.5}

    ai_usage = payload["ai_usage"]
    assert ai_usage["model_name"] == "qwen-plus"
    assert ai_usage["token_prompt_total"] == 800
    assert ai_usage["token_completion_total"] == 300
    assert ai_usage["estimated_cost_yuan"] > 0


def test_dashboard_daily_trend_covers_14_days(db_session):
    _seed(db_session)
    with create_client(db_session) as client:
        response = client.get("/api/admin/dashboard")

    trend = response.json()["daily_trend"]
    assert len(trend) == 14
    today_point = trend[-1]
    assert today_point["message_count"] == 3
    assert today_point["recommendation_count"] == 2


def test_dashboard_empty_database_returns_zeros(db_session):
    with create_client(db_session) as client:
        response = client.get("/api/admin/dashboard")

    assert response.status_code == 200
    payload = response.json()
    assert payload["overview"]["message_count"] == 0
    assert payload["funnel"] == [
        {"name": "用户主动咨询", "value": 0},
        {"name": "AI 推荐消息", "value": 0},
        {"name": "推荐商品曝光", "value": 0},
        {"name": "加入购物车", "value": 0},
        {"name": "下单/支付", "value": 0},
    ]
    assert payload["brand_ranks"] == []
    assert payload["category_penetration"] == []
    assert payload["overview"]["cart_amount_yuan"] == 0.0
    assert payload["notice_done"]["rate"] == 0.0
    assert payload["member_profile"]["age_bands"] == [
        {"name": name, "count": 0}
        for name in ["18岁以下", "18-35岁", "36-55岁", "56-70岁", "70岁以上"]
    ]
    assert payload["fact_risk_top"] == []
    assert payload["risk_members"] == []
    assert payload["hot_products"] == []
    assert payload["live_events"] == []
    assert payload["session_depth"] == {"session_count": 0, "avg_user_turns": 0.0, "max_user_turns": 0}


def _seed_profile(db_session) -> None:
    current_year = utc_now().year
    db_session.add_all(
        [
            Member(
                member_id="mem_father",
                name="老张",
                relation="父亲",
                gender="男",
                birth_year=current_year - 62,
                health_tags="高血压,控糖",
                allergies="海鲜",
            ),
            Member(
                member_id="mem_mother",
                name="老李",
                relation="母亲",
                gender="女",
                birth_year=current_year - 58,
                health_tags=json.dumps(["控糖"], ensure_ascii=False),
            ),
        ]
    )
    db_session.add(
        KbDocument(
            document_id="doc_live",
            file_name="体检报告.pdf",
            file_path="/tmp/体检报告.pdf",
            file_size=1024,
            title="老张 2026 体检报告",
            member_id="mem_father",
            status="done",
        )
    )
    db_session.add_all(
        [
            HealthFact(
                fact_id="fact_p1",
                member_id="mem_father",
                fact_type="metric",
                name="血压偏高",
                status="danger",
                source_document_id="doc_live",
                source_page_no=1,
                evidence_text="血压 152/96 mmHg",
            ),
            HealthFact(
                fact_id="fact_p2",
                member_id="mem_father",
                fact_type="metric",
                name="血压偏高",
                status="warning",
                source_document_id="doc_live",
                source_page_no=2,
                evidence_text="血压 140/90 mmHg",
            ),
            HealthFact(
                fact_id="fact_p3",
                member_id="mem_mother",
                fact_type="metric",
                name="空腹血糖偏高",
                status="warning",
                source_document_id="doc_live",
                source_page_no=3,
                evidence_text="空腹血糖 6.5 mmol/L",
            ),
        ]
    )
    db_session.add(AgentSession(session_id="sess_p", title="今晚吃什么", status="active"))
    db_session.add_all(
        [
            AgentMessage(
                message_id="msg_p_user_1",
                session_id="sess_p",
                role="user",
                content="爸爸今晚吃什么？",
                status="done",
                created_at=utc_now().replace(hour=18, minute=0),
            ),
            AgentMessage(
                message_id="msg_p_asst_1",
                session_id="sess_p",
                role="assistant",
                content="已生成膳食计划",
                status="done",
                card=json.dumps({"kind": "meal_plan", "summary_text": "控糖晚餐"}, ensure_ascii=False),
                created_at=utc_now().replace(hour=18, minute=1),
            ),
        ]
    )
    db_session.commit()


def test_dashboard_member_profile_aggregation(db_session):
    _seed_profile(db_session)
    with create_client(db_session) as client:
        response = client.get("/api/admin/dashboard")

    profile = response.json()["member_profile"]
    assert {"name": "男", "count": 1} in profile["gender_distribution"]
    assert {"name": "女", "count": 1} in profile["gender_distribution"]
    bands = {band["name"]: band["count"] for band in profile["age_bands"]}
    assert bands["56-70岁"] == 2
    assert {"name": "控糖", "count": 2} in profile["health_tag_cloud"]
    assert {"name": "海鲜", "count": 1} in profile["health_tag_cloud"]


def test_dashboard_fact_risk_top_and_risk_members(db_session):
    _seed_profile(db_session)
    with create_client(db_session) as client:
        response = client.get("/api/admin/dashboard")

    payload = response.json()
    risk_top = payload["fact_risk_top"]
    assert risk_top[0] == {"name": "血压偏高", "warning_count": 1, "danger_count": 1}
    assert risk_top[1] == {"name": "空腹血糖偏高", "warning_count": 1, "danger_count": 0}

    members = payload["risk_members"]
    assert members[0]["member_name"] == "老张"
    assert members[0]["relation"] == "父亲"
    assert members[0]["danger_count"] == 1
    assert members[0]["warning_count"] == 1
    assert members[1]["member_name"] == "老李"


def test_dashboard_heatmap_card_usage_and_session_depth(db_session):
    _seed_profile(db_session)
    with create_client(db_session) as client:
        response = client.get("/api/admin/dashboard")

    payload = response.json()
    heatmap = payload["interaction_heatmap"]
    assert len(heatmap) == 1
    assert heatmap[0]["hour"] == 18
    assert heatmap[0]["count"] == 1

    assert payload["card_usage"] == [{"kind": "meal_plan", "count": 1}]
    assert payload["session_depth"] == {"session_count": 1, "avg_user_turns": 1.0, "max_user_turns": 1}


def test_dashboard_hot_products_and_live_events(db_session):
    _seed(db_session)
    _seed_profile(db_session)
    with create_client(db_session) as client:
        response = client.get("/api/admin/dashboard")

    payload = response.json()
    hot = payload["hot_products"]
    assert hot[0]["product_id"] == "prod_a"
    assert hot[0]["name"] == "福临门低钠酱油"
    assert hot[0]["recommend_count"] == 2
    assert hot[0]["cart_count"] == 2
    assert hot[0]["amount_yuan"] == 19.8

    event_types = {event["event_type"] for event in payload["live_events"]}
    assert {"report_upload", "fact_extract", "ai_recommend", "cart_add"} <= event_types
