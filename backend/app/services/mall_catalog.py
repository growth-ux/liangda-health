from __future__ import annotations

import json
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[3]
MANIFEST_ROOT = ROOT_DIR / "frontend" / "public" / "mall-products"

CATEGORY_NAMES = {
    "rice_flour": "米面",
    "seasoning": "调味品",
    "wine_tea": "红酒茶饮",
    "grains": "杂粮",
    "beverages": "饮品",
    "dairy": "乳制品",
    "snacks": "零食",
    "oil": "油品",
}

BRAND_KEYWORDS = [
    "中盐",
    "蒙牛",
    "福临门",
    "山萃",
    "初萃中粮",
    "初萃",
    "金盈杂粮",
    "悠采中粮",
    "时怡中粮",
    "长城",
    "中茶",
    "悦润",
    "安达露西",
]


@dataclass(frozen=True)
class MallCatalogProduct:
    product_id: str
    name: str
    brand: str | None
    category_code: str
    category_name: str
    price_cents: int
    original_price_cents: int | None
    spec: str | None
    sales_text: str
    image_url: str
    description: str
    ingredients: str | None
    shelf_life: str | None
    nutrition: str | None
    health_tags: str | None
    recommend_tags: str | None
    warning_tags: str | None


@dataclass(frozen=True)
class MallCatalogRelation:
    product_id: str
    related_product_id: str
    sort_order: int


@dataclass(frozen=True)
class MallCatalog:
    products: list[MallCatalogProduct]
    relations: list[MallCatalogRelation]


def _read_manifest(category_code: str) -> list[dict]:
    manifest_path = MANIFEST_ROOT / category_code / "manifest.json"
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError(f"{manifest_path} 内容不是数组")
    return data


def _manifest_version() -> tuple[tuple[str, int], ...]:
    versions: list[tuple[str, int]] = []
    for category_code in CATEGORY_NAMES:
        manifest_path = MANIFEST_ROOT / category_code / "manifest.json"
        stat = manifest_path.stat()
        versions.append((category_code, stat.st_mtime_ns))
    return tuple(versions)


def _extract_brand(title: str) -> str | None:
    for brand in BRAND_KEYWORDS:
        if brand in title:
            return brand
    first = re.split(r"[\s（(【\[]", title.strip(), maxsplit=1)[0]
    return first[:20] if first else None


def _extract_spec(title: str) -> str | None:
    matches = re.findall(r"(\d+(?:\.\d+)?\s*(?:kg|g|ml|mL|L|盒|袋|瓶|罐|支|斤)(?:\s*[×xX*]\s*\d+(?:\.\d+)?)?)", title)
    if matches:
        return matches[-1].replace(" ", "")
    return None


def _price_for_title(category_code: str, title: str, goods_id: str | None) -> int:
    base_map = {
        "seasoning": 1590,
        "rice_flour": 2590,
        "wine_tea": 6990,
        "grains": 1990,
        "beverages": 2990,
        "dairy": 4590,
        "snacks": 1890,
        "oil": 5990,
    }
    price = base_map.get(category_code, 2990)
    if any(word in title for word in ["礼盒", "整箱", "2箱", "尊享", "国潮"]):
        price += 2000
    if any(word in title for word in ["特级", "有机", "初榨", "干红", "燕窝"]):
        price += 1200
    if any(word in title for word in ["1kg", "5kg", "5L", "10kg", "24盒", "2罐"]):
        price += 1500
    if goods_id and goods_id.isdigit():
        price += int(goods_id[-2:]) * 10
    return price


def _original_price(price_cents: int, title: str) -> int | None:
    if "换购" in title:
        return None
    return price_cents + 1000


def _sales_text(goods_id: str | None) -> str:
    suffix = int(goods_id[-3:]) if goods_id and goods_id[-3:].isdigit() else 180
    bucket = 800 + suffix * 3
    return f"月销 {bucket}+"


def _health_profile(category_code: str, title: str) -> tuple[list[str], list[str], list[str], list[dict[str, str]], str]:
    health_tags: list[str] = []
    recommend_tags: list[str] = []
    warning_tags: list[str] = []
    nutrition_rows: list[dict[str, str]] = []

    def add_health(*tags: str) -> None:
        for tag in tags:
            if tag not in health_tags:
                health_tags.append(tag)

    def add_recommend(*tags: str) -> None:
        for tag in tags:
            if tag not in recommend_tags:
                recommend_tags.append(tag)

    def add_warning(*tags: str) -> None:
        for tag in tags:
            if tag not in warning_tags:
                warning_tags.append(tag)

    if "低钠" in title or "薄盐" in title:
        add_health("低钠")
        add_recommend("low_sodium", "hypertension")
        nutrition_rows.extend(
            [
                {"label": "适配方向", "value": "减盐饮食"},
                {"label": "建议场景", "value": "家庭日常烹饪"},
            ]
        )
    if any(word in title for word in ["无糖", "糙米", "燕麦", "荞麦", "藜麦", "黑米", "红豆沙"]):
        add_health("控糖友好")
        add_recommend("sugar_control", "low_gi")
        nutrition_rows.extend(
            [
                {"label": "推荐方向", "value": "控糖主食/加餐"},
                {"label": "特点", "value": "更关注膳食纤维"},
            ]
        )
    if any(word in title for word in ["高钙", "牛奶", "燕麦奶"]):
        add_health("高钙")
        add_recommend("high_calcium")
        nutrition_rows.extend(
            [
                {"label": "推荐方向", "value": "补钙营养"},
                {"label": "适合人群", "value": "老人、儿童、家庭早餐"},
            ]
        )
    if any(word in title for word in ["脱脂", "低脂", "橄榄油", "亚麻籽油", "菜籽油", "燕麦奶"]):
        add_health("轻负担")
        add_recommend("low_fat")
        nutrition_rows.extend(
            [
                {"label": "推荐方向", "value": "清淡饮食"},
                {"label": "特点", "value": "更适合日常健康搭配"},
            ]
        )
    if any(word in title for word in ["高蛋白", "蛋白", "牛奶", "奶粉", "豆浆", "豆奶", "芝麻糊"]):
        add_health("高蛋白")
        add_recommend("high_protein")
        nutrition_rows.extend(
            [
                {"label": "推荐方向", "value": "蛋白质补充"},
                {"label": "适合场景", "value": "早餐、加餐、家庭营养补充"},
            ]
        )
    if any(word in title for word in ["高纤", "燕麦", "藜麦", "荞麦", "黑米", "糙米", "玉米", "银耳", "木耳"]):
        add_health("高纤维")
        add_recommend("high_fiber")
        nutrition_rows.extend(
            [
                {"label": "推荐方向", "value": "膳食纤维补充"},
                {"label": "适合场景", "value": "轻食、控糖主食、日常均衡饮食"},
            ]
        )
    if any(word in title for word in ["银耳", "木耳", "香菇", "菌", "燕麦", "藜麦", "荞麦"]):
        add_health("低嘌呤友好")
        add_recommend("low_purine")
        nutrition_rows.extend(
            [
                {"label": "推荐方向", "value": "清淡饮食"},
                {"label": "适合场景", "value": "关注嘌呤摄入的日常搭配"},
            ]
        )
    if any(word in title for word in ["高钙", "牛奶", "燕麦奶", "黑芝麻", "芝麻糊", "核桃", "红枣", "银耳"]):
        add_health("营养素补充")
        add_recommend("nutrients")
        nutrition_rows.extend(
            [
                {"label": "推荐方向", "value": "多营养素补充"},
                {"label": "适合场景", "value": "家庭营养搭配与日常补充"},
            ]
        )
    if any(word in title for word in ["牛奶", "高钙"]):
        add_recommend("elderly", "children")
        add_warning("dairy")
    if any(word in title for word in ["燕麦"]):
        add_warning("oat")
    if any(word in title for word in ["饼干", "小麦", "面", "桃酥"]):
        add_warning("wheat")
    if any(word in title for word in ["生抽", "酱油", "大豆", "豆浆", "黄豆"]):
        add_warning("soy")
    if any(word in title for word in ["核桃", "坚果", "开心果", "果仁"]):
        add_warning("nut")
    if any(word in title for word in ["酒", "白兰地", "葡萄酒"]):
        add_warning("alcohol")

    if category_code == "wine_tea":
        description = "真实商品图同步入库，作为礼赠和日常选购型商品展示。"
        nutrition_rows = nutrition_rows[:1]
        recommend_tags = []
        health_tags = []
    elif category_code == "beverages" and not recommend_tags:
        description = "适合作为家庭常备饮品或轻食搭配，商品信息来自真实图片目录。"
    elif recommend_tags:
        description = f"围绕{ '、'.join(health_tags[:2]) }方向整理的真实商品，适合商城健康推荐展示。"
    else:
        description = "真实商品图同步入库，适合商城日常展示与浏览。"

    return health_tags, recommend_tags, warning_tags, nutrition_rows[:3], description


def _ingredients_for_title(title: str, category_code: str) -> str | None:
    if "生抽" in title or "酱油" in title:
        return "水、大豆、小麦、食用盐"
    if any(word in title for word in ["盐", "海盐", "湖盐", "竹盐", "岩盐"]):
        return "食用盐"
    if any(word in title for word in ["牛奶", "酸奶"]):
        return "生牛乳"
    if any(word in title for word in ["燕麦奶", "燕麦"]):
        return "燕麦、水"
    if any(word in title for word in ["香菇", "银耳", "黑木耳", "食用菌"]):
        return "食用菌原料"
    if any(word in title for word in ["陈皮", "莲子", "红豆沙"]):
        return "植物原料、水"
    if any(word in title for word in ["糙米", "藜麦", "小米", "玉米糁", "大米"]):
        return "谷物原料"
    if any(word in title for word in ["麦香小麦粉", "小麦粉", "面粉", "荞麦面", "挂面"]):
        return "小麦粉"
    if any(word in title for word in ["杂粮", "礼盒", "谷礼盒", "道礼盒"]):
        return "杂粮原料"
    if any(word in title for word in ["油", "香油"]):
        return "植物油料"
    if category_code == "snacks":
        return "谷物、植物油、食用盐"
    fallback_by_category = {
        "seasoning": "调味原料",
        "rice_flour": "谷物原料",
        "grains": "杂粮原料",
        "beverages": "植物原料",
        "dairy": "乳制品原料",
        "wine_tea": "茶叶或酿造原料",
        "oil": "植物油料",
    }
    return fallback_by_category.get(category_code)


def _shelf_life_for_title(category_code: str, title: str) -> str | None:
    if any(word in title for word in ["酸奶"]):
        return "21天（冷藏）"
    if category_code in {"dairy", "beverages"}:
        return "6个月"
    if category_code in {"oil", "seasoning"}:
        return "18个月"
    if category_code == "wine_tea":
        return "24个月"
    return "12个月"


def _build_product(category_code: str, item: dict) -> MallCatalogProduct:
    title = str(item.get("title") or "").strip()
    goods_id = str(item.get("goods_id") or "").strip() or None
    product_id = f"{category_code}-{goods_id}" if goods_id else f"{category_code}-{abs(hash(title)) % 1000000}"
    health_tags, recommend_tags, warning_tags, nutrition_rows, description = _health_profile(category_code, title)
    price_cents = _price_for_title(category_code, title, goods_id)
    return MallCatalogProduct(
        product_id=product_id,
        name=title,
        brand=_extract_brand(title),
        category_code=category_code,
        category_name=CATEGORY_NAMES[category_code],
        price_cents=price_cents,
        original_price_cents=_original_price(price_cents, title),
        spec=_extract_spec(title),
        sales_text=_sales_text(goods_id),
        image_url=str(item.get("local_url") or ""),
        description=description,
        ingredients=_ingredients_for_title(title, category_code),
        shelf_life=_shelf_life_for_title(category_code, title),
        nutrition=json.dumps(nutrition_rows, ensure_ascii=False) if nutrition_rows else json.dumps([], ensure_ascii=False),
        health_tags=json.dumps(health_tags, ensure_ascii=False),
        recommend_tags=json.dumps(recommend_tags, ensure_ascii=False),
        warning_tags=json.dumps(warning_tags, ensure_ascii=False),
    )


def _build_relations(products: list[MallCatalogProduct]) -> list[MallCatalogRelation]:
    relations: list[MallCatalogRelation] = []
    by_category: dict[str, list[MallCatalogProduct]] = {}
    for product in products:
        by_category.setdefault(product.category_code, []).append(product)

    for category_products in by_category.values():
        for index, product in enumerate(category_products):
            related = category_products[index + 1:index + 3]
            if len(related) < 2:
                related += category_products[: 2 - len(related)]
            seen: set[str] = set()
            sort_order = 1
            for candidate in related:
                if candidate.product_id == product.product_id or candidate.product_id in seen:
                    continue
                relations.append(
                    MallCatalogRelation(
                        product_id=product.product_id,
                        related_product_id=candidate.product_id,
                        sort_order=sort_order,
                    )
                )
                seen.add(candidate.product_id)
                sort_order += 1
    return relations


@lru_cache(maxsize=8)
def _load_mall_catalog_cached(_version: tuple[tuple[str, int], ...]) -> MallCatalog:
    products: list[MallCatalogProduct] = []
    for category_code in CATEGORY_NAMES:
        for item in _read_manifest(category_code):
            products.append(_build_product(category_code, item))

    products.sort(key=lambda item: (item.category_code, item.product_id))
    relations = _build_relations(products)
    return MallCatalog(products=products, relations=relations)


def load_mall_catalog() -> MallCatalog:
    return _load_mall_catalog_cached(_manifest_version())


load_mall_catalog.cache_clear = _load_mall_catalog_cached.cache_clear  # type: ignore[attr-defined]
