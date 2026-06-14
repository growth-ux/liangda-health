from datetime import datetime

from fastapi.testclient import TestClient
from sqlalchemy import text

from app.db.session import get_db
from app.main import create_app


def create_member(client: TestClient, payload: dict) -> str:
    response = client.post("/api/members", json=payload)
    assert response.status_code == 200
    return response.json()["member_id"]


def insert_ready_document(db_session, member_id: str, document_id: str = "doc_health_1") -> None:
    db_session.execute(
        text(
            """
            INSERT INTO kb_documents (
                document_id, file_name, file_path, file_size, page_count,
                status, created_at, updated_at, member_id
            ) VALUES (
                :document_id, 'report.pdf', '/tmp/report.pdf', 10, 1,
                'ready', NOW(), NOW(), :member_id
            )
            """
        ),
        {"document_id": document_id, "member_id": member_id},
    )
    db_session.commit()


def test_health_analysis_overview_returns_family_metrics(db_session):
    app = create_app()
    app.dependency_overrides[get_db] = lambda: db_session
    with TestClient(app) as client:
        mother_id = create_member(
            client,
            {
                "name": "王秀英",
                "relation": "母亲",
                "gender": "女",
                "birth_year": 1961,
                "height_cm": 158,
                "weight_kg": 70,
                "health_tags": ["高血压", "骨质疏松"],
            },
        )
        self_id = create_member(
            client,
            {
                "name": "张雨微",
                "relation": "本人",
                "gender": "女",
                "birth_year": 1994,
                "height_cm": 165,
                "weight_kg": 54,
                "health_tags": [],
            },
        )
        insert_ready_document(db_session, mother_id)
        assert client.get(f"/api/devices/{mother_id}/overview").status_code == 200
        assert client.get(f"/api/devices/{self_id}/overview").status_code == 200

        response = client.get("/api/health-analysis/overview")

    assert response.status_code == 200
    payload = response.json()
    assert payload["family"]["name"] == "张雨微的家庭"
    assert payload["family"]["period_label"] == datetime.now().strftime("%Y-%m")
    assert 0 <= payload["metrics"]["family_score"] <= 100
    assert payload["metrics"]["report_count"] == 1
    assert payload["metrics"]["device_count"] == 2
    assert payload["metrics"]["attention_count"] >= 1
    assert len(payload["summary"]) >= 1
    assert len(payload["abnormal_items"]) <= 5
    assert len(payload["member_cards"]) == 2


def test_health_analysis_high_blood_pressure_enters_top_items(db_session):
    app = create_app()
    app.dependency_overrides[get_db] = lambda: db_session
    with TestClient(app) as client:
        member_id = create_member(
            client,
            {
                "name": "王秀英",
                "relation": "母亲",
                "gender": "女",
                "birth_year": 1961,
                "height_cm": 158,
                "weight_kg": 70,
                "health_tags": ["高血压"],
            },
        )

        response = client.get("/api/health-analysis/overview")

    assert response.status_code == 200
    payload = response.json()
    labels = [(item["member_id"], item["metric"]) for item in payload["abnormal_items"]]
    assert any(item[0] == member_id and item[1] in {"收缩压", "舒张压", "高血压"} for item in labels)
    member_card = next(card for card in payload["member_cards"] if card["member_id"] == member_id)
    assert member_card["health_score"] < 100


def test_health_analysis_no_members_returns_empty_overview(db_session):
    app = create_app()
    app.dependency_overrides[get_db] = lambda: db_session
    with TestClient(app) as client:
        response = client.get("/api/health-analysis/overview")

    assert response.status_code == 200
    payload = response.json()
    assert payload["metrics"] == {
        "family_score": 0,
        "family_score_delta": 0,
        "attention_count": 0,
        "report_count": 0,
        "device_count": 0,
    }
    assert payload["summary"] == []
    assert payload["abnormal_items"] == []
    assert payload["member_cards"] == []


def test_member_health_analysis_returns_indicators_trend_and_advice(db_session):
    app = create_app()
    app.dependency_overrides[get_db] = lambda: db_session
    with TestClient(app) as client:
        member_id = create_member(
            client,
            {
                "name": "王秀英",
                "relation": "母亲",
                "gender": "女",
                "birth_year": 1961,
                "height_cm": 158,
                "weight_kg": 70,
                "health_tags": ["高血压"],
            },
        )
        insert_ready_document(db_session, member_id)

        response = client.get(f"/api/health-analysis/members/{member_id}")

    assert response.status_code == 200
    payload = response.json()
    assert payload["member_card"]["member_id"] == member_id
    assert payload["member_card"]["health_score"] < 100
    labels = {item["label"] for item in payload["indicators"]}
    assert {"收缩压", "舒张压", "心率", "睡眠", "血氧", "BMI", "报告数量"} <= labels
    assert len(payload["blood_pressure_7d"]) == 7
    assert {"date", "systolic", "diastolic"} <= set(payload["blood_pressure_7d"][0])
    assert payload["abnormalities"]
    assert payload["advice"]["title"]
    assert payload["advice"]["lines"]
    assert member_id in payload["advice"]["prompt"]
