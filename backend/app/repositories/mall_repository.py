import json

from sqlalchemy import and_
from sqlalchemy.orm import Session

from app.models.mall import MallCartItem, MallProduct, MallProductRelation, MallZone
from app.schemas.mall import MallCartResponse, MallCartItem as MallCartItemSchema, MallProductSummary, MallZone as MallZoneSchema


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
        if self.product_count() > 0:
            self._sync_default_zones()
            return
        self._seed_products()
        self._seed_zones()
        self._seed_relations()
        self.db.commit()

    def _sync_default_zones(self) -> None:
        changed = False
        defaults = {
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

    def _seed_products(self) -> None:
        from datetime import datetime

        now = datetime.utcnow()
        products = [
            MallProduct(
                product_id="prod_low_sodium_soy",
                name="薄盐生抽",
                brand="海天",
                category_code="seasoning",
                category_name="调味品",
                price_cents=1990,
                original_price_cents=2590,
                spec="500ml",
                sales_text="月销 2000+",
                image_emoji="🧴",
                image_url="/mall-products/prod_low_sodium_soy.png",
                description="减盐25%，适合高血压人群日常调味。",
                ingredients="水、非转基因大豆、小麦、食用盐",
                shelf_life="18个月",
                nutrition=json.dumps(
                    [
                        {"label": "钠含量", "value": "≤ 4500 mg / 100ml"},
                        {"label": "蛋白质", "value": "≥ 8.0 g / 100ml"},
                        {"label": "氨基酸态氮", "value": "≥ 0.8 g / 100ml"},
                    ],
                    ensure_ascii=False,
                ),
                health_tags=json.dumps(["低钠", "非转基因"], ensure_ascii=False),
                recommend_tags=json.dumps(["low_sodium", "hypertension"], ensure_ascii=False),
                warning_tags=json.dumps(["soy", "wheat"], ensure_ascii=False),
                created_at=now,
                updated_at=now,
            ),
            MallProduct(
                product_id="prod_low_gi_rice",
                name="低GI胚芽米",
                brand="十月稻田",
                category_code="rice_flour",
                category_name="米面",
                price_cents=3990,
                original_price_cents=4990,
                spec="2.5kg",
                sales_text="月销 1500+",
                image_emoji="🍚",
                image_url="/mall-products/rice_flour/681-福临门五常大米5kg-绿稻花-1baef826.png",
                description="低升糖指数，保留胚芽营养，适合控糖人群。",
                ingredients="粳稻",
                shelf_life="12个月",
                nutrition=json.dumps(
                    [
                        {"label": "GI值", "value": "≤ 55"},
                        {"label": "膳食纤维", "value": "≥ 2.5 g / 100g"},
                        {"label": "蛋白质", "value": "≥ 7.0 g / 100g"},
                    ],
                    ensure_ascii=False,
                ),
                health_tags=json.dumps(["低GI", "控糖", "高纤维"], ensure_ascii=False),
                recommend_tags=json.dumps(["sugar_control", "low_gi", "diabetes"], ensure_ascii=False),
                warning_tags=json.dumps([], ensure_ascii=False),
                created_at=now,
                updated_at=now,
            ),
            MallProduct(
                product_id="prod_high_calcium_milk",
                name="高钙纯牛奶",
                brand="蒙牛",
                category_code="dairy",
                category_name="乳制品",
                price_cents=5990,
                original_price_cents=6990,
                spec="250ml × 12",
                sales_text="月销 5000+",
                image_emoji="🥛",
                image_url="/mall-products/dairy/10211691661797-蒙牛高钙牛奶营养早餐牛奶送礼推荐礼盒装年货送礼盒-250ml-24盒-2箱-066fc43b.jpg",
                description="每100ml含钙125mg，适合老人和青少年补钙。",
                ingredients="生牛乳",
                shelf_life="6个月",
                nutrition=json.dumps(
                    [
                        {"label": "钙", "value": "≥ 125 mg / 100ml"},
                        {"label": "蛋白质", "value": "≥ 3.2 g / 100ml"},
                        {"label": "脂肪", "value": "≥ 3.5 g / 100ml"},
                    ],
                    ensure_ascii=False,
                ),
                health_tags=json.dumps(["高钙", "高蛋白"], ensure_ascii=False),
                recommend_tags=json.dumps(["high_calcium", "elderly", "children"], ensure_ascii=False),
                warning_tags=json.dumps(["dairy"], ensure_ascii=False),
                created_at=now,
                updated_at=now,
            ),
            MallProduct(
                product_id="prod_olive_oil",
                name="特级初榨橄榄油",
                brand="欧丽薇兰",
                category_code="oil",
                category_name="油品",
                price_cents=7990,
                original_price_cents=9990,
                spec="750ml",
                sales_text="月销 800+",
                image_emoji="🫒",
                image_url="/mall-products/oil/42-福临门特级初榨橄榄油礼盒500ml-2-e5a18b1e.png",
                description="冷压初榨，富含单不饱和脂肪酸，适合凉拌和低温烹饪。",
                ingredients="特级初榨橄榄油",
                shelf_life="24个月",
                nutrition=json.dumps(
                    [
                        {"label": "单不饱和脂肪酸", "value": "≥ 70%"},
                        {"label": "维生素E", "value": "≥ 12 mg / 100g"},
                        {"label": "酸度", "value": "≤ 0.5%"},
                    ],
                    ensure_ascii=False,
                ),
                health_tags=json.dumps(["低脂", "不饱和脂肪酸"], ensure_ascii=False),
                recommend_tags=json.dumps(["low_fat", "heart_health"], ensure_ascii=False),
                warning_tags=json.dumps([], ensure_ascii=False),
                created_at=now,
                updated_at=now,
            ),
            MallProduct(
                product_id="prod_sugar_free_yogurt",
                name="无糖希腊酸奶",
                brand="简爱",
                category_code="dairy",
                category_name="乳制品",
                price_cents=4590,
                original_price_cents=5590,
                spec="135g × 6",
                sales_text="月销 3000+",
                image_emoji="🥄",
                image_url="/mall-products/prod_sugar_free_yogurt.png",
                description="0蔗糖添加，高蛋白希腊式发酵，适合控糖和健身人群。",
                ingredients="生牛乳、乳酸菌",
                shelf_life="21天（冷藏）",
                nutrition=json.dumps(
                    [
                        {"label": "蛋白质", "value": "≥ 7.0 g / 100g"},
                        {"label": "碳水化合物", "value": "≤ 5.0 g / 100g"},
                        {"label": "脂肪", "value": "≥ 4.0 g / 100g"},
                    ],
                    ensure_ascii=False,
                ),
                health_tags=json.dumps(["无糖", "高蛋白", "低GI"], ensure_ascii=False),
                recommend_tags=json.dumps(["sugar_control", "no_sugar", "high_protein"], ensure_ascii=False),
                warning_tags=json.dumps(["dairy"], ensure_ascii=False),
                created_at=now,
                updated_at=now,
            ),
            MallProduct(
                product_id="prod_buckwheat_noodle",
                name="纯荞麦面",
                brand="白象",
                category_code="rice_flour",
                category_name="米面",
                price_cents=1590,
                original_price_cents=None,
                spec="200g × 5",
                sales_text="月销 1200+",
                image_emoji="🍜",
                image_url="/mall-products/prod_buckwheat_noodle.png",
                description="100%荞麦粉，低GI主食替代，富含膳食纤维。",
                ingredients="荞麦粉、水",
                shelf_life="12个月",
                nutrition=json.dumps(
                    [
                        {"label": "膳食纤维", "value": "≥ 4.5 g / 100g"},
                        {"label": "蛋白质", "value": "≥ 10.0 g / 100g"},
                        {"label": "GI值", "value": "≤ 50"},
                    ],
                    ensure_ascii=False,
                ),
                health_tags=json.dumps(["低GI", "高纤维", "控糖"], ensure_ascii=False),
                recommend_tags=json.dumps(["sugar_control", "low_gi", "high_fiber"], ensure_ascii=False),
                warning_tags=json.dumps(["buckwheat"], ensure_ascii=False),
                created_at=now,
                updated_at=now,
            ),
            MallProduct(
                product_id="prod_low_sodium_salt",
                name="低钠盐",
                brand="中盐",
                category_code="seasoning",
                category_name="调味品",
                price_cents=590,
                original_price_cents=None,
                spec="350g",
                sales_text="月销 4000+",
                image_emoji="🧂",
                image_url="/mall-products/seasoning/100221736593-中盐-优质低钠盐250g-10-加碘-绿色食品低钠盐-吃好盐选中盐-b840c896.png",
                description="钠含量降低30%，以钾代钠，适合高血压人群。",
                ingredients="氯化钠、氯化钾、碘酸钾",
                shelf_life="36个月",
                nutrition=json.dumps(
                    [
                        {"label": "钠含量", "value": "≤ 70% 普通盐"},
                        {"label": "钾含量", "value": "≥ 20%"},
                        {"label": "碘", "value": "20-30 mg/kg"},
                    ],
                    ensure_ascii=False,
                ),
                health_tags=json.dumps(["低钠", "含钾"], ensure_ascii=False),
                recommend_tags=json.dumps(["low_sodium", "hypertension"], ensure_ascii=False),
                warning_tags=json.dumps([], ensure_ascii=False),
                created_at=now,
                updated_at=now,
            ),
            MallProduct(
                product_id="prod_calcium_biscuit",
                name="高钙苏打饼干",
                brand="太平",
                category_code="snacks",
                category_name="零食",
                price_cents=1290,
                original_price_cents=1590,
                spec="200g",
                sales_text="月销 1800+",
                image_emoji="🍪",
                image_url="/mall-products/snacks/10191738999535-悠采中粮-无糖饼干-混合口味5袋装-酥性饼干-办公室休闲零食108g-cc7de380.jpg",
                description="添加碳酸钙，酥脆口感，适合老人日常补钙零食。",
                ingredients="小麦粉、植物油、碳酸钙、食用盐",
                shelf_life="12个月",
                nutrition=json.dumps(
                    [
                        {"label": "钙", "value": "≥ 200 mg / 100g"},
                        {"label": "蛋白质", "value": "≥ 8.0 g / 100g"},
                        {"label": "脂肪", "value": "≤ 18 g / 100g"},
                    ],
                    ensure_ascii=False,
                ),
                health_tags=json.dumps(["高钙", "低脂"], ensure_ascii=False),
                recommend_tags=json.dumps(["high_calcium", "low_fat", "elderly"], ensure_ascii=False),
                warning_tags=json.dumps(["wheat"], ensure_ascii=False),
                created_at=now,
                updated_at=now,
            ),
            MallProduct(
                product_id="prod_walnut_oil",
                name="核桃油",
                brand="鲁花",
                category_code="oil",
                category_name="油品",
                price_cents=8990,
                original_price_cents=10990,
                spec="500ml",
                sales_text="月销 600+",
                image_emoji="🥜",
                image_url="/mall-products/oil/1018-悦润亚麻籽油5L-0c7c9791.png",
                description="富含Omega-3不饱和脂肪酸，适合儿童和老人食用。",
                ingredients="核桃仁",
                shelf_life="18个月",
                nutrition=json.dumps(
                    [
                        {"label": "Omega-3", "value": "≥ 10%"},
                        {"label": "维生素E", "value": "≥ 40 mg / 100g"},
                        {"label": "不饱和脂肪酸", "value": "≥ 90%"},
                    ],
                    ensure_ascii=False,
                ),
                health_tags=json.dumps(["不饱和脂肪酸", "健脑"], ensure_ascii=False),
                recommend_tags=json.dumps(["low_fat", "children", "elderly"], ensure_ascii=False),
                warning_tags=json.dumps(["nut"], ensure_ascii=False),
                created_at=now,
                updated_at=now,
            ),
            MallProduct(
                product_id="prod_oat_milk",
                name="燕麦奶",
                brand="OATLY",
                category_code="beverages",
                category_name="饮品",
                price_cents=2990,
                original_price_cents=3590,
                spec="1L",
                sales_text="月销 2500+",
                image_emoji="🥤",
                image_url="/mall-products/prod_oat_milk.png",
                description="植物基燕麦奶，0乳糖，高膳食纤维，适合乳糖不耐受人群。",
                ingredients="水、燕麦、菜籽油、碳酸钙",
                shelf_life="12个月",
                nutrition=json.dumps(
                    [
                        {"label": "膳食纤维", "value": "≥ 0.8 g / 100ml"},
                        {"label": "钙", "value": "≥ 120 mg / 100ml"},
                        {"label": "蛋白质", "value": "≥ 1.0 g / 100ml"},
                    ],
                    ensure_ascii=False,
                ),
                health_tags=json.dumps(["高纤维", "高钙", "0乳糖"], ensure_ascii=False),
                recommend_tags=json.dumps(["high_calcium", "high_fiber", "lactose_free"], ensure_ascii=False),
                warning_tags=json.dumps(["oat"], ensure_ascii=False),
                created_at=now,
                updated_at=now,
            ),
            MallProduct(
                product_id="prod_brown_rice",
                name="有机糙米",
                brand="北大荒",
                category_code="rice_flour",
                category_name="米面",
                price_cents=2990,
                original_price_cents=3590,
                spec="1kg",
                sales_text="月销 900+",
                image_emoji="🌾",
                image_url="/mall-products/grains/100059020674-初萃中粮-七色糙米2斤-糙米-黑米-红米-燕麦米-紫米-高粱米-荞麦米-a1f19a68.jpg",
                description="保留谷皮和胚芽，富含B族维生素和膳食纤维。",
                ingredients="有机糙米",
                shelf_life="12个月",
                nutrition=json.dumps(
                    [
                        {"label": "膳食纤维", "value": "≥ 3.5 g / 100g"},
                        {"label": "维生素B1", "value": "≥ 0.3 mg / 100g"},
                        {"label": "蛋白质", "value": "≥ 7.5 g / 100g"},
                    ],
                    ensure_ascii=False,
                ),
                health_tags=json.dumps(["高纤维", "有机", "全谷物"], ensure_ascii=False),
                recommend_tags=json.dumps(["high_fiber", "sugar_control", "low_gi"], ensure_ascii=False),
                warning_tags=json.dumps([], ensure_ascii=False),
                created_at=now,
                updated_at=now,
            ),
            MallProduct(
                product_id="prod_canola_oil",
                name="双低菜籽油",
                brand="金龙鱼",
                category_code="oil",
                category_name="油品",
                price_cents=4990,
                original_price_cents=5990,
                spec="1.8L",
                sales_text="月销 3500+",
                image_emoji="🫗",
                image_url="/mall-products/oil/3116-福临门福至心礼非转基因压榨玉米油5L-c9cf6ec3.jpg",
                description="低芥酸、低硫苷，脂肪酸比例均衡，适合日常烹饪。",
                ingredients="双低油菜籽",
                shelf_life="18个月",
                nutrition=json.dumps(
                    [
                        {"label": "芥酸", "value": "≤ 2%"},
                        {"label": "单不饱和脂肪酸", "value": "≥ 60%"},
                        {"label": "维生素E", "value": "≥ 45 mg / 100g"},
                    ],
                    ensure_ascii=False,
                ),
                health_tags=json.dumps(["低脂", "非转基因"], ensure_ascii=False),
                recommend_tags=json.dumps(["low_fat", "heart_health"], ensure_ascii=False),
                warning_tags=json.dumps([], ensure_ascii=False),
                created_at=now,
                updated_at=now,
            ),
        ]
        for product in products:
            self.db.add(product)

    def _seed_zones(self) -> None:
        zones = [
            MallZone(zone_code="low_sodium", name="低钠专区", zone_type="health", icon="🧂", match_tag="low_sodium", sort_order=1),
            MallZone(zone_code="sugar_control", name="控糖专区", zone_type="health", icon="🍬", match_tag="sugar_control", sort_order=2),
            MallZone(zone_code="high_calcium", name="高钙专区", zone_type="health", icon="🦴", match_tag="high_calcium", sort_order=3),
            MallZone(zone_code="low_fat", name="低脂专区", zone_type="health", icon="💚", match_tag="low_fat", sort_order=4),
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

    def _seed_relations(self) -> None:
        relations = [
            MallProductRelation(product_id="prod_low_sodium_soy", related_product_id="prod_low_sodium_salt", sort_order=1),
            MallProductRelation(product_id="prod_low_sodium_soy", related_product_id="prod_olive_oil", sort_order=2),
            MallProductRelation(product_id="prod_low_gi_rice", related_product_id="prod_buckwheat_noodle", sort_order=1),
            MallProductRelation(product_id="prod_low_gi_rice", related_product_id="prod_brown_rice", sort_order=2),
            MallProductRelation(product_id="prod_high_calcium_milk", related_product_id="prod_calcium_biscuit", sort_order=1),
            MallProductRelation(product_id="prod_high_calcium_milk", related_product_id="prod_oat_milk", sort_order=2),
            MallProductRelation(product_id="prod_olive_oil", related_product_id="prod_walnut_oil", sort_order=1),
            MallProductRelation(product_id="prod_olive_oil", related_product_id="prod_canola_oil", sort_order=2),
            MallProductRelation(product_id="prod_sugar_free_yogurt", related_product_id="prod_high_calcium_milk", sort_order=1),
            MallProductRelation(product_id="prod_sugar_free_yogurt", related_product_id="prod_oat_milk", sort_order=2),
            MallProductRelation(product_id="prod_buckwheat_noodle", related_product_id="prod_low_gi_rice", sort_order=1),
            MallProductRelation(product_id="prod_buckwheat_noodle", related_product_id="prod_brown_rice", sort_order=2),
            MallProductRelation(product_id="prod_low_sodium_salt", related_product_id="prod_low_sodium_soy", sort_order=1),
            MallProductRelation(product_id="prod_calcium_biscuit", related_product_id="prod_high_calcium_milk", sort_order=1),
            MallProductRelation(product_id="prod_walnut_oil", related_product_id="prod_olive_oil", sort_order=1),
            MallProductRelation(product_id="prod_oat_milk", related_product_id="prod_sugar_free_yogurt", sort_order=1),
            MallProductRelation(product_id="prod_brown_rice", related_product_id="prod_low_gi_rice", sort_order=1),
            MallProductRelation(product_id="prod_canola_oil", related_product_id="prod_olive_oil", sort_order=1),
        ]
        for relation in relations:
            self.db.add(relation)
