import json
from pathlib import Path

from fastapi.testclient import TestClient

from app.db.session import get_db
from app.main import create_app
from app.models.mall import MallProduct
from app.services import mall_catalog
from app.services.mall_catalog import MANIFEST_ROOT


def _manifest_item(category: str, goods_id: str) -> dict | None:
    data = json.loads((MANIFEST_ROOT / category / "manifest.json").read_text(encoding="utf-8"))
    for item in data:
        if item.get("goods_id") == goods_id:
            return item
    return None


def _create_member(client, **kwargs):
    defaults = {
        "name": "测试家人",
        "relation": "母亲",
        "gender": "女",
        "birth_year": 1960,
        "health_tags": [],
    }
    defaults.update(kwargs)
    response = client.post("/api/members", json=defaults)
    assert response.status_code == 200
    return response.json()


def test_mall_home_returns_zones_categories_and_daily(db_session):
    app = create_app()
    app.dependency_overrides[get_db] = lambda: db_session
    client = TestClient(app)

    response = client.get("/api/mall/home")
    assert response.status_code == 200
    data = response.json()

    assert "health_zones" in data
    assert "categories" in data
    assert "daily_products" in data
    assert "family_recommendations" in data

    assert len(data["health_zones"]) >= 8
    zone_codes = [z["zone_code"] for z in data["health_zones"]]
    assert "low_sodium" in zone_codes
    assert "sugar_control" in zone_codes
    assert "high_protein" in zone_codes
    assert "high_fiber" in zone_codes
    assert "low_purine" in zone_codes
    assert "nutrients" in zone_codes

    assert len(data["categories"]) >= 4

    assert len(data["daily_products"]) > 0
    product = data["daily_products"][0]
    assert "product_id" in product
    assert "name" in product
    assert "price_cents" in product
    assert "price_text" in product

    expected_count = 0
    for manifest in MANIFEST_ROOT.glob("*/manifest.json"):
        expected_count += len(json.loads(manifest.read_text(encoding="utf-8")))
    assert db_session.query(MallProduct).count() == expected_count


def test_mall_seed_uses_manifest_products_instead_of_placeholder_seed(db_session):
    app = create_app()
    app.dependency_overrides[get_db] = lambda: db_session
    client = TestClient(app)

    response = client.get("/api/mall/products")
    assert response.status_code == 200

    names = [item["name"] for item in response.json()["products"]]
    assert "薄盐生抽" not in names
    assert "无糖希腊酸奶" not in names

    product = (
        db_session.query(MallProduct)
        .filter(MallProduct.name == "中盐低钠盐400g*5【未加碘】减盐不减咸 低钠 吃好盐 选中盐")
        .one_or_none()
    )
    assert product is not None
    manifest_item = _manifest_item("seasoning", "100104276720")
    assert manifest_item is not None
    assert product.image_url == manifest_item["local_url"]


def test_all_manifest_image_urls_point_to_existing_files():
    missing: list[str] = []
    for manifest in MANIFEST_ROOT.glob("*/manifest.json"):
        data = json.loads(manifest.read_text(encoding="utf-8"))
        for item in data:
            local_url = item.get("local_url")
            if not local_url:
                continue
            path = MANIFEST_ROOT.parent / local_url.lstrip("/")
            if not Path(path).exists():
                missing.append(local_url)

    assert missing == []


def test_load_mall_catalog_refreshes_when_manifest_changes(monkeypatch, tmp_path):
    manifest_root = tmp_path / "mall-products"
    for category in mall_catalog.CATEGORY_NAMES:
        category_dir = manifest_root / category
        category_dir.mkdir(parents=True, exist_ok=True)
        items = []
        if category == "snacks":
            items = [
                {
                    "title": "旧零食",
                    "goods_id": "1001",
                    "local_url": "/mall-products/snacks/old.jpg",
                }
            ]
        (category_dir / "manifest.json").write_text(
            json.dumps(items, ensure_ascii=False),
            encoding="utf-8",
        )

    monkeypatch.setattr(mall_catalog, "MANIFEST_ROOT", manifest_root)
    mall_catalog.load_mall_catalog.cache_clear()

    first = mall_catalog.load_mall_catalog()
    assert [p.product_id for p in first.products if p.category_code == "snacks"] == ["snacks-1001"]

    (manifest_root / "snacks" / "manifest.json").write_text(
        json.dumps(
            [
                {
                    "title": "新零食",
                    "goods_id": "2002",
                    "local_url": "/mall-products/snacks/new.jpg",
                }
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    second = mall_catalog.load_mall_catalog()
    assert [p.product_id for p in second.products if p.category_code == "snacks"] == ["snacks-2002"]


def test_mall_seed_refreshes_when_database_tags_stale(db_session):
    app = create_app()
    app.dependency_overrides[get_db] = lambda: db_session
    client = TestClient(app)

    response = client.get("/api/mall/home")
    assert response.status_code == 200

    product = (
        db_session.query(MallProduct)
        .filter(MallProduct.product_id == "dairy-10211691661797")
        .one_or_none()
    )
    assert product is not None
    product.recommend_tags = json.dumps(["high_calcium"], ensure_ascii=False)
    db_session.commit()

    response = client.get("/api/mall/home")
    assert response.status_code == 200

    updated = (
        db_session.query(MallProduct)
        .filter(MallProduct.product_id == "dairy-10211691661797")
        .one_or_none()
    )
    assert updated is not None
    assert updated.recommend_tags != json.dumps(["high_calcium"], ensure_ascii=False)
    assert "high_protein" in updated.recommend_tags


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

    response = client.get("/api/mall/home")
    assert response.status_code == 200
    data = response.json()

    assert len(data["family_recommendations"]) >= 1
    rec = data["family_recommendations"][0]
    assert rec["member_name"] == "张桂兰"
    assert rec["relation"] == "妈妈"
    assert len(rec["products"]) > 0

    assert any("低钠" in p["name"] for p in rec["products"])
    assert any("低钠" in " ".join(p["health_tags"]) for p in rec["products"])


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

    response = client.get("/api/mall/home")
    assert response.status_code == 200
    data = response.json()

    assert len(data["family_recommendations"]) >= 1
    rec = data["family_recommendations"][0]
    assert rec["member_name"] == "李建国"

    assert any(
        any(tag in {"控糖友好", "高钙", "轻负担"} for tag in p["health_tags"]) or "燕麦" in p["name"] or "无糖" in p["name"] or "糙米" in p["name"]
        for p in rec["products"]
    )


def test_mall_products_zone_filters_new_health_zones(db_session):
    app = create_app()
    app.dependency_overrides[get_db] = lambda: db_session
    client = TestClient(app)

    client.get("/api/mall/home")

    cases = [
        ("high_protein", ["高蛋白", "蛋白", "牛奶", "奶"]),
        ("high_fiber", ["高纤", "燕麦", "藜麦", "荞麦", "黑米"]),
        ("low_purine", ["菌", "银耳", "木耳", "燕麦"]),
        ("nutrients", ["高钙", "牛奶", "燕麦奶", "芝麻", "核桃"]),
    ]

    for zone_code, keywords in cases:
        response = client.get(f"/api/mall/products?zone_code={zone_code}")
        assert response.status_code == 200
        products = response.json()["products"]
        assert len(products) > 0
        assert any(any(keyword in product["name"] for keyword in keywords) for product in products)


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

    response = client.get("/api/mall/home")
    assert response.status_code == 200
    data = response.json()

    for rec in data["family_recommendations"]:
        if rec["member_name"] == "小明":
            product_ids = [p["product_id"] for p in rec["products"]]
            assert all("soy" not in pid for pid in product_ids)


def test_mall_product_detail_returns_detail_and_related(db_session):
    app = create_app()
    app.dependency_overrides[get_db] = lambda: db_session
    client = TestClient(app)

    client.get("/api/mall/home")

    response = client.get("/api/mall/products/seasoning-100104276720")
    assert response.status_code == 200
    data = response.json()

    assert "product" in data
    assert "recommend_reason" in data
    assert "nutrition_rows" in data
    assert "related_products" in data
    assert "health_notice" in data

    product = data["product"]
    assert product["product_id"] == "seasoning-100104276720"
    assert product["name"] == "中盐低钠盐400g*5【未加碘】减盐不减咸 低钠 吃好盐 选中盐"
    assert product["price_cents"] > 0
    assert product["price_text"].startswith("¥")
    assert "低钠" in product["health_tags"]
    assert product["ingredients"]

    assert len(data["nutrition_rows"]) > 0
    assert data["health_notice"] == "本推荐不构成医疗建议"


def test_all_seeded_products_have_ingredients(db_session):
    app = create_app()
    app.dependency_overrides[get_db] = lambda: db_session
    client = TestClient(app)

    client.get("/api/mall/home")

    products = db_session.query(MallProduct).all()
    missing = [(p.product_id, p.name) for p in products if not p.ingredients]
    assert missing == []


def test_mall_product_not_found(db_session):
    app = create_app()
    app.dependency_overrides[get_db] = lambda: db_session
    client = TestClient(app)

    client.get("/api/mall/home")

    response = client.get("/api/mall/products/prod_nonexistent")
    assert response.status_code == 404
    assert response.json()["detail"] == "商品不存在"


def test_mall_cart_add_accumulates_quantity(db_session):
    app = create_app()
    app.dependency_overrides[get_db] = lambda: db_session
    client = TestClient(app)

    client.get("/api/mall/home")

    response1 = client.post(
        "/api/mall/cart/items",
        json={"product_id": "seasoning-100104276720", "quantity": 2},
    )
    assert response1.status_code == 200
    cart1 = response1.json()
    assert cart1["total_quantity"] == 2

    response2 = client.post(
        "/api/mall/cart/items",
        json={"product_id": "seasoning-100104276720", "quantity": 3},
    )
    assert response2.status_code == 200
    cart2 = response2.json()
    assert cart2["total_quantity"] == 5

    item = cart2["items"][0]
    assert item["product_id"] == "seasoning-100104276720"
    assert item["quantity"] == 5
    assert item["subtotal_cents"] == item["price_cents"] * 5


def test_mall_cart_update_quantity(db_session):
    app = create_app()
    app.dependency_overrides[get_db] = lambda: db_session
    client = TestClient(app)

    client.get("/api/mall/home")

    client.post("/api/mall/cart/items", json={"product_id": "seasoning-100104276720", "quantity": 2})

    response = client.put(
        "/api/mall/cart/items/seasoning-100104276720",
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

    client.get("/api/mall/home")

    client.post("/api/mall/cart/items", json={"product_id": "seasoning-100104276720", "quantity": 1})

    response = client.put(
        "/api/mall/cart/items/seasoning-100104276720",
        json={"quantity": 0},
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "商品数量必须大于 0"


def test_mall_cart_delete_item(db_session):
    app = create_app()
    app.dependency_overrides[get_db] = lambda: db_session
    client = TestClient(app)

    client.get("/api/mall/home")

    client.post("/api/mall/cart/items", json={"product_id": "seasoning-100104276720", "quantity": 1})

    response = client.delete("/api/mall/cart/items/seasoning-100104276720")
    assert response.status_code == 204

    cart_response = client.get("/api/mall/cart")
    assert cart_response.status_code == 200
    cart = cart_response.json()
    assert cart["total_quantity"] == 0
    assert len(cart["items"]) == 0
