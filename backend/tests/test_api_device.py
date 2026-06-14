from datetime import date, timedelta

from fastapi.testclient import TestClient
from sqlalchemy import text

from app.db.session import get_db
from app.main import create_app


def create_member(client: TestClient) -> str:
    response = client.post(
        "/api/members",
        json={
            "name": "王建国",
            "relation": "父亲",
            "gender": "男",
            "birth_year": 1958,
            "health_tags": ["高血压"],
        },
    )
    assert response.status_code == 200
    return response.json()["member_id"]


def fetch_one_metric_row(db_session, member_id: str, metric_date: date):
    return db_session.execute(
        text(
            """
            SELECT metric_date, steps, avg_heart_rate, sleep_hours, blood_oxygen
            FROM device_daily_metrics
            WHERE member_id = :member_id AND metric_date = :metric_date
            """
        ),
        {"member_id": member_id, "metric_date": metric_date},
    ).mappings().one()


def test_device_overview_returns_recent_7_days(db_session):
    app = create_app()
    app.dependency_overrides[get_db] = lambda: db_session
    with TestClient(app) as client:
        member_id = create_member(client)

        response = client.get(f"/api/devices/{member_id}/overview")

        assert response.status_code == 200
        payload = response.json()
        assert payload["member"]["member_id"] == member_id
        assert payload["device"]["device_status"] == "connected"
        assert len(payload["charts"]["steps_7d"]) == 7
        assert len(payload["charts"]["heart_rate_24h"]) == 24
        assert len(payload["charts"]["sleep_7d"]) == 7
        assert len(payload["charts"]["blood_pressure_24h"]) == 24

        expected_dates = [
            (date.today() - timedelta(days=offset)).isoformat()
            for offset in range(6, -1, -1)
        ]
        assert [item["date"] for item in payload["charts"]["steps_7d"]] == expected_dates
        assert {"time", "value"} <= set(payload["charts"]["heart_rate_24h"][-1])
        assert {"time", "systolic", "diastolic"} <= set(payload["charts"]["blood_pressure_24h"][-1])


def test_device_sync_fills_missing_days_only(db_session):
    app = create_app()
    app.dependency_overrides[get_db] = lambda: db_session
    with TestClient(app) as client:
        member_id = create_member(client)
        overview_response = client.post(f"/api/devices/{member_id}/sync")
        assert overview_response.status_code == 200

        deleted_date = date.today() - timedelta(days=2)
        preserved_date = date.today() - timedelta(days=1)
        preserved_before = dict(fetch_one_metric_row(db_session, member_id, preserved_date))

        db_session.execute(
            text(
                """
                DELETE FROM device_daily_metrics
                WHERE member_id = :member_id AND metric_date = :metric_date
                """
            ),
            {"member_id": member_id, "metric_date": deleted_date},
        )
        db_session.commit()

        sync_response = client.post(f"/api/devices/{member_id}/sync")

        assert sync_response.status_code == 200
        payload = sync_response.json()
        assert len(payload["charts"]["steps_7d"]) == 7

        restored_row = fetch_one_metric_row(db_session, member_id, deleted_date)
        assert restored_row["metric_date"] == deleted_date

        preserved_after = dict(fetch_one_metric_row(db_session, member_id, preserved_date))
        assert preserved_after == preserved_before

        count = db_session.execute(
            text(
                """
                SELECT COUNT(*)
                FROM device_daily_metrics
                WHERE member_id = :member_id
                """
            ),
            {"member_id": member_id},
        ).scalar_one()
        assert count == 7


def test_device_sync_logs_hide_backfill_details(db_session):
    app = create_app()
    app.dependency_overrides[get_db] = lambda: db_session
    with TestClient(app) as client:
        member_id = create_member(client)

        response = client.post(f"/api/devices/{member_id}/sync")

        assert response.status_code == 200
        messages = [item["message"] for item in response.json()["sync_logs"]]
        assert messages
        assert all(message == "每日自动同步成功" for message in messages)
        assert not any("补齐" in message or "缺失" in message for message in messages)


def test_device_sync_logs_return_one_item_per_day(db_session):
    app = create_app()
    app.dependency_overrides[get_db] = lambda: db_session
    with TestClient(app) as client:
        member_id = create_member(client)

        response = client.post(f"/api/devices/{member_id}/sync")

        assert response.status_code == 200
        dates = [item["date"] for item in response.json()["sync_logs"]]
        assert dates
        assert len(dates) == len(set(dates))


def test_device_mock_data_reflects_member_health_tags(db_session):
    app = create_app()
    app.dependency_overrides[get_db] = lambda: db_session
    with TestClient(app) as client:
        member_id = create_member(client)

        response = client.get(f"/api/devices/{member_id}/overview")

        assert response.status_code == 200
        payload = response.json()
        latest_bp = payload["summary"]["blood_pressure"]
        systolic, diastolic = [int(value) for value in latest_bp.split("/")]
        bp_points = payload["charts"]["blood_pressure_24h"]

        assert systolic >= 140 or diastolic >= 90
        assert any(point["systolic"] >= 140 or point["diastolic"] >= 90 for point in bp_points)


def test_device_overview_auto_creates_binding_and_uses_latest_day(db_session):
    app = create_app()
    app.dependency_overrides[get_db] = lambda: db_session
    with TestClient(app) as client:
        member_id = create_member(client)
        response = client.get(f"/api/devices/{member_id}/overview")

        assert response.status_code == 200
        payload = response.json()
        binding = db_session.execute(
            text(
                """
                SELECT member_id, device_name, device_status
                FROM device_bindings
                WHERE member_id = :member_id
                """
            ),
            {"member_id": member_id},
        ).mappings().one()
        assert binding["member_id"] == member_id
        assert binding["device_name"] == "小米手环 8 Pro"
        assert binding["device_status"] == "connected"
        assert payload["device"]["device_name"] == binding["device_name"]
        assert payload["summary"]["steps"] == payload["charts"]["steps_7d"][-1]["value"]
        assert len(payload["charts"]["heart_rate_24h"]) == 24


def test_device_startup_seeds_existing_members(db_session):
    first_app = create_app()
    first_app.dependency_overrides[get_db] = lambda: db_session

    first_client = TestClient(first_app)
    created = create_member(first_client)
    first_client.close()

    second_app = create_app(session_factory=lambda: db_session)
    second_app.dependency_overrides[get_db] = lambda: db_session
    with TestClient(second_app):
        binding_count = db_session.execute(
            text("SELECT COUNT(*) FROM device_bindings WHERE member_id = :member_id"),
            {"member_id": created},
        ).scalar_one()
        metric_count = db_session.execute(
            text("SELECT COUNT(*) FROM device_daily_metrics WHERE member_id = :member_id"),
            {"member_id": created},
        ).scalar_one()

    assert binding_count == 1
    assert metric_count == 7
