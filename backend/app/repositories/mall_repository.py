from sqlalchemy import and_
from sqlalchemy.orm import Session

from app.models.mall import MallCartItem, MallProduct, MallProductRelation, MallZone
from app.schemas.mall import MallCartResponse, MallCartItem as MallCartItemSchema, MallProductSummary, MallZone as MallZoneSchema
from app.services.mall_catalog import load_mall_catalog


def _product_to_summary(product: MallProduct, recommend_reason: str | None = None) -> MallProductSummary:
    return MallProductSummary(
        product_id=product.product_id,
        name=product.name,
        brand=product.brand,
        category_code=product.category_code,
        category_name=product.category_name,
        price_cents=product.price_cents,
        original_price_cents=product.original_price_cents,
        spec=product.spec,
        sales_text=product.sales_text,
        image_emoji=product.image_emoji,
        image_url=product.image_url,
        health_tags_raw=product.health_tags,
        recommend_reason=recommend_reason,
    )


def _zone_to_schema(zone: MallZone) -> MallZoneSchema:
    return MallZoneSchema(
        zone_code=zone.zone_code,
        name=zone.name,
        zone_type=zone.zone_type,
        icon=zone.icon,
        match_tag=zone.match_tag,
        sort_order=zone.sort_order,
    )


class SqlAlchemyMallRepository:
    def __init__(self, db: Session):
        self.db = db

    def list_products(
        self,
        zone_code: str | None = None,
        category_code: str | None = None,
    ) -> list[MallProduct]:
        query = self.db.query(MallProduct)
        if category_code:
            query = query.filter(MallProduct.category_code == category_code)
        if zone_code:
            zone = self.db.query(MallZone).filter(MallZone.zone_code == zone_code).one_or_none()
            if zone and zone.match_tag:
                tag = zone.match_tag
                query = query.filter(MallProduct.recommend_tags.contains(tag))
        return query.order_by(MallProduct.id).all()

    def get_product(self, product_id: str) -> MallProduct | None:
        return (
            self.db.query(MallProduct)
            .filter(MallProduct.product_id == product_id)
            .one_or_none()
        )

    def list_all_products(self) -> list[MallProduct]:
        return self.db.query(MallProduct).order_by(MallProduct.id).all()

    def list_zones(self, zone_type: str | None = None) -> list[MallZone]:
        query = self.db.query(MallZone)
        if zone_type:
            query = query.filter(MallZone.zone_type == zone_type)
        return query.order_by(MallZone.sort_order).all()

    def get_zone(self, zone_code: str) -> MallZone | None:
        return (
            self.db.query(MallZone)
            .filter(MallZone.zone_code == zone_code)
            .one_or_none()
        )

    def list_related_products(self, product_id: str) -> list[MallProduct]:
        relations = (
            self.db.query(MallProductRelation)
            .filter(MallProductRelation.product_id == product_id)
            .order_by(MallProductRelation.sort_order)
            .all()
        )
        if not relations:
            return []
        related_ids = [r.related_product_id for r in relations]
        products = (
            self.db.query(MallProduct)
            .filter(MallProduct.product_id.in_(related_ids))
            .all()
        )
        product_map = {p.product_id: p for p in products}
        return [product_map[rid] for rid in related_ids if rid in product_map]

    def list_cart_items(self, cart_owner_id: str) -> list[MallCartItem]:
        return (
            self.db.query(MallCartItem)
            .filter(MallCartItem.cart_owner_id == cart_owner_id)
            .order_by(MallCartItem.created_at)
            .all()
        )

    def get_cart_item(self, cart_owner_id: str, product_id: str) -> MallCartItem | None:
        return (
            self.db.query(MallCartItem)
            .filter(
                and_(
                    MallCartItem.cart_owner_id == cart_owner_id,
                    MallCartItem.product_id == product_id,
                )
            )
            .one_or_none()
        )

    def add_cart_item(self, cart_owner_id: str, product_id: str, quantity: int) -> MallCartItem:
        existing = self.get_cart_item(cart_owner_id, product_id)
        if existing:
            existing.quantity += quantity
            self.db.commit()
            self.db.refresh(existing)
            return existing
        from datetime import datetime

        item = MallCartItem(
            cart_owner_id=cart_owner_id,
            product_id=product_id,
            quantity=quantity,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        self.db.add(item)
        self.db.commit()
        self.db.refresh(item)
        return item

    def update_cart_item(self, cart_owner_id: str, product_id: str, quantity: int) -> MallCartItem | None:
        item = self.get_cart_item(cart_owner_id, product_id)
        if item is None:
            return None
        from datetime import datetime

        item.quantity = quantity
        item.updated_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(item)
        return item

    def delete_cart_item(self, cart_owner_id: str, product_id: str) -> bool:
        item = self.get_cart_item(cart_owner_id, product_id)
        if item is None:
            return False
        self.db.delete(item)
        self.db.commit()
        return True

    def build_cart_response(self, cart_owner_id: str) -> MallCartResponse:
        cart_items = self.list_cart_items(cart_owner_id)
        items: list[MallCartItemSchema] = []
        total_quantity = 0
        total_cents = 0
        for cart_item in cart_items:
            product = self.get_product(cart_item.product_id)
            if product is None:
                continue
            subtotal = product.price_cents * cart_item.quantity
            items.append(
                MallCartItemSchema(
                    product_id=product.product_id,
                    name=product.name,
                    spec=product.spec,
                    image_emoji=product.image_emoji,
                    image_url=product.image_url,
                    price_cents=product.price_cents,
                    quantity=cart_item.quantity,
                    subtotal_cents=subtotal,
                )
            )
            total_quantity += cart_item.quantity
            total_cents += subtotal
        return MallCartResponse(
            items=items,
            total_quantity=total_quantity,
            total_cents=total_cents,
        )

    def product_count(self) -> int:
        return self.db.query(MallProduct).count()

    def seed_default_data(self) -> None:
        self._sync_default_zones()
        catalog = load_mall_catalog()
        if self._catalog_matches_database(catalog):
            return
        self.db.query(MallProductRelation).delete()
        self.db.query(MallProduct).delete()
        self.db.query(MallZone).delete()
        self._seed_products(catalog)
        self._seed_zones()
        self._seed_relations(catalog)
        self.db.commit()

    def _catalog_matches_database(self, catalog) -> bool:
        existing_count = self.product_count()
        if existing_count != len(catalog.products):
            return False

        existing_products = self.db.query(MallProduct).all()
        if len(existing_products) != len(catalog.products):
            return False

        existing_map = {product.product_id: product for product in existing_products}
        for item in catalog.products:
            existing = existing_map.get(item.product_id)
            if existing is None:
                return False
            if (
                existing.name != item.name
                or existing.image_url != item.image_url
                or existing.health_tags != item.health_tags
                or existing.recommend_tags != item.recommend_tags
                or existing.warning_tags != item.warning_tags
            ):
                return False
        return True

    def _sync_default_zones(self) -> None:
        changed = False
        defaults = {
            "low_sodium": {"name": "低钠专区", "zone_type": "health", "icon": "🧂", "match_tag": "low_sodium", "sort_order": 1},
            "sugar_control": {"name": "控糖专区", "zone_type": "health", "icon": "🍬", "match_tag": "sugar_control", "sort_order": 2},
            "high_calcium": {"name": "高钙专区", "zone_type": "health", "icon": "🦴", "match_tag": "high_calcium", "sort_order": 3},
            "low_fat": {"name": "低脂专区", "zone_type": "health", "icon": "💚", "match_tag": "low_fat", "sort_order": 4},
            "high_protein": {"name": "高蛋白专区", "zone_type": "health", "icon": "🥚", "match_tag": "high_protein", "sort_order": 5},
            "high_fiber": {"name": "高纤维专区", "zone_type": "health", "icon": "🌾", "match_tag": "high_fiber", "sort_order": 6},
            "low_purine": {"name": "低嘌呤专区", "zone_type": "health", "icon": "🍄", "match_tag": "low_purine", "sort_order": 7},
            "nutrients": {"name": "营养素专区", "zone_type": "health", "icon": "🥜", "match_tag": "nutrients", "sort_order": 8},
            "rice_flour": {"name": "优质米面", "zone_type": "category", "icon": "🍚", "match_tag": None, "sort_order": 10},
            "grains": {"name": "精品杂粮", "zone_type": "category", "icon": "🌾", "match_tag": None, "sort_order": 16},
            "wine_tea": {"name": "红酒茶叶", "zone_type": "category", "icon": "🍷", "match_tag": None, "sort_order": 17},
        }
        for zone_code, values in defaults.items():
            zone = self.db.query(MallZone).filter(MallZone.zone_code == zone_code).one_or_none()
            if zone is None:
                self.db.add(MallZone(zone_code=zone_code, **values))
                changed = True
            elif any(getattr(zone, key) != value for key, value in values.items()):
                for key, value in values.items():
                    setattr(zone, key, value)
                changed = True
        if changed:
            self.db.commit()

    def _seed_products(self, catalog) -> None:
        from datetime import datetime

        now = datetime.utcnow()
        for item in catalog.products:
            self.db.add(
                MallProduct(
                    product_id=item.product_id,
                    name=item.name,
                    brand=item.brand,
                    category_code=item.category_code,
                    category_name=item.category_name,
                    price_cents=item.price_cents,
                    original_price_cents=item.original_price_cents,
                    spec=item.spec,
                    sales_text=item.sales_text,
                    image_emoji=None,
                    image_url=item.image_url,
                    description=item.description,
                    ingredients=item.ingredients,
                    shelf_life=item.shelf_life,
                    nutrition=item.nutrition,
                    health_tags=item.health_tags,
                    recommend_tags=item.recommend_tags,
                    warning_tags=item.warning_tags,
                    created_at=now,
                    updated_at=now,
                )
            )

    def _seed_zones(self) -> None:
        zones = [
            MallZone(zone_code="low_sodium", name="低钠专区", zone_type="health", icon="🧂", match_tag="low_sodium", sort_order=1),
            MallZone(zone_code="sugar_control", name="控糖专区", zone_type="health", icon="🍬", match_tag="sugar_control", sort_order=2),
            MallZone(zone_code="high_calcium", name="高钙专区", zone_type="health", icon="🦴", match_tag="high_calcium", sort_order=3),
            MallZone(zone_code="low_fat", name="低脂专区", zone_type="health", icon="💚", match_tag="low_fat", sort_order=4),
            MallZone(zone_code="high_protein", name="高蛋白专区", zone_type="health", icon="🥚", match_tag="high_protein", sort_order=5),
            MallZone(zone_code="high_fiber", name="高纤维专区", zone_type="health", icon="🌾", match_tag="high_fiber", sort_order=6),
            MallZone(zone_code="low_purine", name="低嘌呤专区", zone_type="health", icon="🍄", match_tag="low_purine", sort_order=7),
            MallZone(zone_code="nutrients", name="营养素专区", zone_type="health", icon="🥜", match_tag="nutrients", sort_order=8),
            MallZone(zone_code="rice_flour", name="优质米面", zone_type="category", icon="🍚", match_tag=None, sort_order=10),
            MallZone(zone_code="oil", name="健康好油", zone_type="category", icon="🫒", match_tag=None, sort_order=11),
            MallZone(zone_code="seasoning", name="调味酱料", zone_type="category", icon="🧴", match_tag=None, sort_order=12),
            MallZone(zone_code="dairy", name="乳制品", zone_type="category", icon="🥛", match_tag=None, sort_order=13),
            MallZone(zone_code="snacks", name="健康零食", zone_type="category", icon="🍪", match_tag=None, sort_order=14),
            MallZone(zone_code="beverages", name="健康饮品", zone_type="category", icon="🥤", match_tag=None, sort_order=15),
            MallZone(zone_code="grains", name="精品杂粮", zone_type="category", icon="🌾", match_tag=None, sort_order=16),
            MallZone(zone_code="wine_tea", name="红酒茶叶", zone_type="category", icon="🍷", match_tag=None, sort_order=17),
        ]
        for zone in zones:
            self.db.add(zone)

    def _seed_relations(self, catalog) -> None:
        for relation in catalog.relations:
            self.db.add(
                MallProductRelation(
                    product_id=relation.product_id,
                    related_product_id=relation.related_product_id,
                    sort_order=relation.sort_order,
                )
            )
