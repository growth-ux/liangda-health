from fastapi.testclient import TestClient
from sqlalchemy import text

from app.db.session import get_db
from app.main import create_app


def test_members_create_and_list(db_session):
    app = create_app()
    app.dependency_overrides[get_db] = lambda: db_session
    client = TestClient(app)

    create_response = client.post(
        "/api/members",
        json={
            "name": "王秀英",
            "relation": "母亲",
            "gender": "女",
            "birth_year": 1961,
            "height_cm": 158,
            "weight_kg": 60,
            "health_tags": ["高血压"],
            "allergies": "忌辛辣",
            "taste_preferences": "偏清淡",
        },
    )

    assert create_response.status_code == 200
    created = create_response.json()
    assert created["name"] == "王秀英"
    assert created["relation"] == "母亲"
    assert created["age"] >= 60
    assert created["bmi"] == 24.0

    list_response = client.get("/api/members")

    assert list_response.status_code == 200
    payload = list_response.json()
    assert len(payload) == 1
    assert payload[0]["member_id"] == created["member_id"]
    assert payload[0]["name"] == "王秀英"
    assert payload[0]["report_count"] == 0
    assert payload[0]["recent_documents"] == []


def test_members_detail_update_and_documents(db_session):
    app = create_app()
    app.dependency_overrides[get_db] = lambda: db_session
    client = TestClient(app)

    created = client.post(
        "/api/members",
        json={
            "name": "张建国",
            "relation": "父亲",
            "gender": "男",
            "birth_year": 1958,
            "health_tags": ["高血压"],
        },
    ).json()
    member_id = created["member_id"]

    detail_response = client.get(f"/api/members/{member_id}")
    assert detail_response.status_code == 200
    assert detail_response.json()["name"] == "张建国"

    update_response = client.put(
        f"/api/members/{member_id}",
        json={
            "name": "张建国",
            "relation": "父亲",
            "gender": "男",
            "birth_year": 1958,
            "health_tags": ["高血压", "高血脂"],
            "height_cm": 172,
            "weight_kg": 75,
        },
    )
    assert update_response.status_code == 200
    updated = update_response.json()
    assert updated["health_tags"] == ["高血压", "高血脂"]
    assert updated["bmi"] == 25.4

    documents_response = client.get(f"/api/members/{member_id}/documents")
    assert documents_response.status_code == 200
    assert documents_response.json() == []

    delete_response = client.delete(f"/api/members/{member_id}")
    assert delete_response.status_code == 204


def test_member_delete_with_documents_rejected(db_session):
    app = create_app()
    app.dependency_overrides[get_db] = lambda: db_session
    client = TestClient(app)

    created = client.post(
        "/api/members",
        json={
            "name": "李阿姨",
            "relation": "其他",
            "gender": "女",
            "birth_year": 1970,
            "health_tags": [],
        },
    ).json()
    member_id = created["member_id"]

    db_session.execute(
        text(
            """
        INSERT INTO kb_documents (
            document_id, file_name, file_path, file_size, page_count, status, created_at, updated_at, member_id
        ) VALUES (
            'doc_member_1', 'report.pdf', '/tmp/report.pdf', 10, 1, 'ready', NOW(), NOW(), :member_id
        )
        """
        ),
        {"member_id": member_id},
    )
    db_session.commit()

    response = client.delete(f"/api/members/{member_id}")

    assert response.status_code == 400
    assert response.json()["detail"] == "该家人已有报告，不能删除"


def test_delete_member_rejects_when_has_kb_references(db_session):
    """Repository 层:有 KB 引用时拒绝删除,Member 仍存在。"""
    from app.repositories.member_repository import SqlAlchemyMemberRepository

    created_response = client_factory(db_session).post(
        "/api/members",
        json={
            "name": "王大爷",
            "relation": "本人",
            "gender": "男",
            "birth_year": 1955,
            "health_tags": [],
        },
    ).json()
    member_id = created_response["member_id"]

    db_session.execute(
        text(
            """
        INSERT INTO kb_documents (
            document_id, file_name, file_path, file_size, page_count, status, created_at, updated_at, member_id
        ) VALUES (
            'doc_repo_reject', 'report.pdf', '/tmp/r.pdf', 10, 1, 'ready', NOW(), NOW(), :member_id
        )
        """
        ),
        {"member_id": member_id},
    )
    db_session.commit()

    repo = SqlAlchemyMemberRepository(db_session)
    result = repo.delete_member(member_id)

    assert result is None  # 拒绝删除

    detail = client_factory(db_session).get(f"/api/members/{member_id}")
    assert detail.status_code == 200


def test_delete_member_succeeds_when_no_kb_references(db_session):
    """Repository 层:无 KB 引用时正常删除。"""
    from app.repositories.member_repository import SqlAlchemyMemberRepository

    created_response = client_factory(db_session).post(
        "/api/members",
        json={
            "name": "赵奶奶",
            "relation": "母亲",
            "gender": "女",
            "birth_year": 1948,
            "health_tags": [],
        },
    ).json()
    member_id = created_response["member_id"]

    repo = SqlAlchemyMemberRepository(db_session)
    result = repo.delete_member(member_id)

    assert result is not None
    detail = client_factory(db_session).get(f"/api/members/{member_id}")
    assert detail.status_code == 404


def client_factory(db_session):
    """辅助函数:每次返回绑定到 db_session 的新 TestClient。"""
    app = create_app()
    app.dependency_overrides[get_db] = lambda: db_session
    return TestClient(app)
