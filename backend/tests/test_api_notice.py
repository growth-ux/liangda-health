from datetime import date, datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy import text

from app.db.session import get_db
from app.main import create_app


def create_client(db_session) -> TestClient:
    app = create_app()
    app.dependency_overrides[get_db] = lambda: db_session
    return TestClient(app)


def create_member(client: TestClient, *, health_tags: list[str] | None = None) -> str:
    response = client.post(
        "/api/members",
        json={
            "name": "王秀英",
            "relation": "母亲",
            "gender": "女",
            "birth_year": 1961,
            "height_cm": 158,
            "weight_kg": 70,
            "health_tags": health_tags or [],
        },
    )
    assert response.status_code == 200
    return response.json()["member_id"]


def insert_ready_document(db_session, member_id: str, document_id: str = "doc_notice_1") -> None:
    db_session.execute(
        text(
            """
            INSERT INTO kb_documents (
                document_id, file_name, file_path, file_size, page_count,
                title, patient_name, exam_date, institution, status,
                created_at, updated_at, member_id
            ) VALUES (
                :document_id, 'report.pdf', '/tmp/report.pdf', 10, 1,
                '体检报告', '王秀英', :exam_date, '社区医院', 'ready',
                NOW(), NOW(), :member_id
            )
            """
        ),
        {
            "document_id": document_id,
            "member_id": member_id,
            "exam_date": date.today() - timedelta(days=10),
        },
    )
    db_session.commit()


def set_latest_bp(db_session, member_id: str, systolic: int, diastolic: int) -> None:
    metric_date = date.today()
    db_session.execute(
        text(
            """
            UPDATE device_daily_metrics
            SET systolic_bp = :systolic, diastolic_bp = :diastolic, updated_at = NOW()
            WHERE member_id = :member_id AND metric_date = :metric_date
            """
        ),
        {
            "member_id": member_id,
            "metric_date": metric_date,
            "systolic": systolic,
            "diastolic": diastolic,
        },
    )
    db_session.commit()


def flatten_items(payload: dict) -> list[dict]:
    return [item for group in payload["groups"] for item in group["items"]]


def test_notice_list_generates_welcome_once(db_session):
    with create_client(db_session) as client:
        first_response = client.get("/api/notices")
        second_response = client.get("/api/notices")

    assert first_response.status_code == 200
    first_items = flatten_items(first_response.json())
    assert len(first_items) == 1
    assert first_items[0]["title"] == "欢迎使用粮达健康"
    assert first_items[0]["category"] == "system"
    assert first_items[0]["status"] == "unread"

    assert second_response.status_code == 200
    second_items = flatten_items(second_response.json())
    assert len(second_items) == 1


def test_notice_rules_generate_report_bp_and_recommendation(db_session):
    with create_client(db_session) as client:
        member_id = create_member(client, health_tags=["高血压"])
        assert client.get(f"/api/devices/{member_id}/overview").status_code == 200
        set_latest_bp(db_session, member_id, 152, 92)
        insert_ready_document(db_session, member_id)

        response = client.get("/api/notices")

    assert response.status_code == 200
    payload = response.json()
    items = flatten_items(payload)
    titles = {item["title"] for item in items}
    assert "新报告已识别" in titles
    assert any(item["category"] == "health_alert" and "血压偏高" in item["title"] for item in items)
    assert any(item["category"] == "recommendation" for item in items)
    assert payload["counts"]["health_alert"] >= 1
    assert payload["counts"]["system"] >= 1
    assert payload["counts"]["recommendation"] >= 1


def test_notice_category_filter_and_all_includes_reminders(db_session):
    with create_client(db_session) as client:
        create_member(client, health_tags=["高血压"])

        all_response = client.get("/api/notices?category=all")
        system_response = client.get("/api/notices?category=system")

    assert all_response.status_code == 200
    all_items = flatten_items(all_response.json())
    assert any(item["category"] == "reminder" for item in all_items)

    assert system_response.status_code == 200
    system_items = flatten_items(system_response.json())
    assert system_items
    assert all(item["category"] == "system" for item in system_items)


def test_notice_read_all_and_single_status_mutations_update_summary(db_session):
    with create_client(db_session) as client:
        create_member(client, health_tags=["高血压"])
        list_response = client.get("/api/notices")
        first_notice = flatten_items(list_response.json())[0]

        read_response = client.post(f"/api/notices/{first_notice['notice_id']}/read")
        snooze_response = client.post(f"/api/notices/{first_notice['notice_id']}/snooze")
        done_response = client.post(f"/api/notices/{first_notice['notice_id']}/done")
        read_all_response = client.post("/api/notices/read-all")
        summary_response = client.get("/api/notices/summary")

    assert read_response.status_code == 200
    assert read_response.json()["status"] == "read"
    assert snooze_response.status_code == 200
    assert snooze_response.json()["status"] == "snoozed"
    assert done_response.status_code == 200
    assert done_response.json()["status"] == "done"
    assert read_all_response.status_code == 200
    assert summary_response.status_code == 200
    assert summary_response.json()["unread"] == 0


def test_notice_groups_by_today_this_week_and_earlier(db_session):
    with create_client(db_session) as client:
        assert client.get("/api/notices").status_code == 200

        notice_ids = db_session.execute(text("SELECT notice_id FROM notices")).scalars().all()
        assert notice_ids
        now = datetime.utcnow()
        db_session.execute(
            text("UPDATE notices SET created_at = :created_at WHERE notice_id = :notice_id"),
            {"created_at": now - timedelta(days=2), "notice_id": notice_ids[0]},
        )
        db_session.execute(
            text(
                """
                INSERT INTO notices (
                    notice_id, category, level, title, description, source, status,
                    dedupe_key, created_at, updated_at
                ) VALUES (
                    'not_old', 'system', 'info', '更早通知', '更早通知描述', 'system', 'unread',
                    'manual_old', :created_at, :updated_at
                )
                """
            ),
            {
                "created_at": now - timedelta(days=10),
                "updated_at": now - timedelta(days=10),
            },
        )
        db_session.commit()

        response = client.get("/api/notices")

    assert response.status_code == 200
    labels = [group["label"] for group in response.json()["groups"]]
    assert "本周" in labels
    assert "更早" in labels
