import json

from fastapi.testclient import TestClient

from app.db.session import get_db
from app.main import create_app


def _create_member(client, **kwargs):
    defaults = {
        "name": "测试家人",
        "relation": "母亲",
        "gender": "女",
        "birth_year": 1960,
        "health_tags": [],
    }
    defaults.update(kwargs)
    response = client.post("/members", json=defaults)
    assert response.status_code == 200
    return response.json()


def test_mall_home_returns_zones_categories_and_daily(db_session):
    app = create_app()
    app.dependency_overrides[get_db] = lambda: db_session
    client = TestClient(app)

    response = client.get("/mall/home")
    assert response.status_code == 200
    data = response.json()

    assert "health_zones" in data
    assert "categories" in data
    assert "daily_products" in data
    assert "family_recommendations" in data

    assert len(data["health_zones"]) >= 4
    zone_codes = [z["zone_code"] for z in data["health_zones"]]
    assert "low_sodium" in zone_codes
    assert "sugar_control" in zone_codes

    assert len(data["categories"]) >= 4

    assert len(data["daily_products"]) > 0
    product = data["daily_products"][0]
    assert "product_id" in product
    assert "name" in product
    assert "price_cents" in product
    assert "price_text" in product


def test_mall_home_hypertension_member_gets_low_sodium(db_session):
    app = create_app()
    app.dependency_overrides[get_db] = lambda: db_session
    client = TestClient(app)

    _create_member(
        client,
        name="张桂兰",
        relation="妈妈",
        gender="女",
        birth_year=1960,
        health_tags=["高血压"],
    )

    response = client.get("/mall/home")
    assert response.status_code == 200
    data = response.json()

    assert len(data["family_recommendations"]) >= 1
    rec = data["family_recommendations"][0]
    assert rec["member_name"] == "张桂兰"
    assert rec["relation"] == "妈妈"
    assert len(rec["products"]) > 0

    product_ids = [p["product_id"] for p in rec["products"]]
    assert "prod_low_sodium_soy" in product_ids or "prod_low_sodium_salt" in product_ids


def test_mall_home_diabetes_member_gets_sugar_control(db_session):
    app = create_app()
    app.dependency_overrides[get_db] = lambda: db_session
    client = TestClient(app)

    _create_member(
        client,
        name="李建国",
        relation="爸爸",
        gender="男",
        birth_year=1958,
        health_tags=["糖尿病"],
    )

    response = client.get("/mall/home")
    assert response.status_code == 200
    data = response.json()

    assert len(data["family_recommendations"]) >= 1
    rec = data["family_recommendations"][0]
    assert rec["member_name"] == "李建国"

    product_ids = [p["product_id"] for p in rec["products"]]
    assert any(pid in product_ids for pid in ["prod_low_gi_rice", "prod_buckwheat_noodle", "prod_sugar_free_yogurt"])


def test_mall_home_allergy_excludes_matching_products(db_session):
    app = create_app()
    app.dependency_overrides[get_db] = lambda: db_session
    client = TestClient(app)

    _create_member(
        client,
        name="小明",
        relation="儿子",
        gender="男",
        birth_year=2010,
        health_tags=[],
        allergies="大豆",
    )

    response = client.get("/mall/home")
    assert response.status_code == 200
    data = response.json()

    for rec in data["family_recommendations"]:
        if rec["member_name"] == "小明":
            product_ids = [p["product_id"] for p in rec["products"]]
            assert "prod_low_sodium_soy" not in product_ids


def test_mall_product_detail_returns_detail_and_related(db_session):
    app = create_app()
    app.dependency_overrides[get_db] = lambda: db_session
    client = TestClient(app)

    client.get("/mall/home")

    response = client.get("/mall/products/prod_low_sodium_soy")
    assert response.status_code == 200
    data = response.json()

    assert "product" in data
    assert "recommend_reason" in data
    assert "nutrition_rows" in data
    assert "related_products" in data
    assert "health_notice" in data

    product = data["product"]
    assert product["product_id"] == "prod_low_sodium_soy"
    assert product["name"] == "薄盐生抽"
    assert product["price_cents"] == 1990
    assert product["price_text"] == "¥19.9"
    assert "低钠" in product["health_tags"]

    assert len(data["nutrition_rows"]) > 0
    assert data["health_notice"] == "本推荐不构成医疗建议"


def test_mall_product_not_found(db_session):
    app = create_app()
    app.dependency_overrides[get_db] = lambda: db_session
    client = TestClient(app)

    client.get("/mall/home")

    response = client.get("/mall/products/prod_nonexistent")
    assert response.status_code == 404
    assert response.json()["detail"] == "商品不存在"


def test_mall_cart_add_accumulates_quantity(db_session):
    app = create_app()
    app.dependency_overrides[get_db] = lambda: db_session
    client = TestClient(app)

    client.get("/mall/home")

    response1 = client.post(
        "/mall/cart/items",
        json={"product_id": "prod_low_sodium_soy", "quantity": 2},
    )
    assert response1.status_code == 200
    cart1 = response1.json()
    assert cart1["total_quantity"] == 2

    response2 = client.post(
        "/mall/cart/items",
        json={"product_id": "prod_low_sodium_soy", "quantity": 3},
    )
    assert response2.status_code == 200
    cart2 = response2.json()
    assert cart2["total_quantity"] == 5

    item = cart2["items"][0]
    assert item["product_id"] == "prod_low_sodium_soy"
    assert item["quantity"] == 5
    assert item["subtotal_cents"] == 1990 * 5


def test_mall_cart_update_quantity(db_session):
    app = create_app()
    app.dependency_overrides[get_db] = lambda: db_session
    client = TestClient(app)

    client.get("/mall/home")

    client.post("/mall/cart/items", json={"product_id": "prod_low_sodium_soy", "quantity": 2})

    response = client.put(
        "/mall/cart/items/prod_low_sodium_soy",
        json={"quantity": 3},
    )
    assert response.status_code == 200
    cart = response.json()
    assert cart["items"][0]["quantity"] == 3
    assert cart["total_quantity"] == 3


def test_mall_cart_update_zero_quantity_returns_400(db_session):
    app = create_app()
    app.dependency_overrides[get_db] = lambda: db_session
    client = TestClient(app)

    client.get("/mall/home")

    client.post("/mall/cart/items", json={"product_id": "prod_low_sodium_soy", "quantity": 1})

    response = client.put(
        "/mall/cart/items/prod_low_sodium_soy",
        json={"quantity": 0},
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "商品数量必须大于 0"


def test_mall_cart_delete_item(db_session):
    app = create_app()
    app.dependency_overrides[get_db] = lambda: db_session
    client = TestClient(app)

    client.get("/mall/home")

    client.post("/mall/cart/items", json={"product_id": "prod_low_sodium_soy", "quantity": 1})

    response = client.delete("/mall/cart/items/prod_low_sodium_soy")
    assert response.status_code == 204

    cart_response = client.get("/mall/cart")
    assert cart_response.status_code == 200
    cart = cart_response.json()
    assert cart["total_quantity"] == 0
    assert len(cart["items"]) == 0
