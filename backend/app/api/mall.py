from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.member import Member
from app.repositories.mall_repository import SqlAlchemyMallRepository
from app.schemas.mall import (
    MallCartItemCreateRequest,
    MallCartItemUpdateRequest,
    MallCartResponse,
    MallHomeResponse,
    MallProductDetail,
    MallProductDetailResponse,
    MallProductListResponse,
    MallProductSummary,
    MallZone as MallZoneSchema,
)
from app.services.mall_recommendation import (
    build_member_recommendations,
    find_best_member_for_product,
    score_product_for_member,
)

router = APIRouter(prefix="/mall", tags=["mall"])

CART_OWNER_ID = "default_family"


@router.get("/home", response_model=MallHomeResponse)
def get_mall_home(db: Session = Depends(get_db)):
    repo = SqlAlchemyMallRepository(db)
    repo.seed_default_data()

    products = repo.list_all_products()
    health_zones = repo.list_zones(zone_type="health")
    categories = repo.list_zones(zone_type="category")

    members = db.query(Member).all()

    family_recommendations = build_member_recommendations(members, products)

    daily_products: list[MallProductSummary] = []
    for product in products[:8]:
        daily_products.append(
            MallProductSummary(
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
            )
        )

    return MallHomeResponse(
        family_recommendations=family_recommendations,
        health_zones=[
            MallZoneSchema(
                zone_code=z.zone_code,
                name=z.name,
                zone_type=z.zone_type,
                icon=z.icon,
                match_tag=z.match_tag,
                sort_order=z.sort_order,
            )
            for z in health_zones
        ],
        daily_products=daily_products,
        categories=[
            MallZoneSchema(
                zone_code=z.zone_code,
                name=z.name,
                zone_type=z.zone_type,
                icon=z.icon,
                match_tag=z.match_tag,
                sort_order=z.sort_order,
            )
            for z in categories
        ],
    )


@router.get("/products", response_model=MallProductListResponse)
def list_mall_products(
    zone_code: str | None = Query(None),
    category_code: str | None = Query(None),
    member_id: str | None = Query(None),
    limit: int | None = Query(None),
    db: Session = Depends(get_db),
):
    repo = SqlAlchemyMallRepository(db)
    repo.seed_default_data()

    products = repo.list_products(zone_code=zone_code, category_code=category_code)

    if limit and limit > 0:
        products = products[:limit]

    zone = None
    if zone_code:
        zone_orm = repo.get_zone(zone_code)
        if zone_orm:
            zone = MallZoneSchema(
                zone_code=zone_orm.zone_code,
                name=zone_orm.name,
                zone_type=zone_orm.zone_type,
                icon=zone_orm.icon,
                match_tag=zone_orm.match_tag,
                sort_order=zone_orm.sort_order,
            )

    summaries: list[MallProductSummary] = []
    member = None
    if member_id:
        member = db.query(Member).filter(Member.member_id == member_id).one_or_none()

    for product in products:
        recommend_reason = None
        if member:
            s = score_product_for_member(member, product)
            if s > 0:
                from app.services.mall_recommendation import build_recommend_reason

                recommend_reason = build_recommend_reason(member, product)

        summaries.append(
            MallProductSummary(
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
        )

    if member and not category_code and not zone_code:
        scored = [(score_product_for_member(member, p), i) for i, p in enumerate(products)]
        scored.sort(key=lambda x: x[0], reverse=True)
        ordered = [summaries[i] for _, i in scored]
        summaries = ordered

    return MallProductListResponse(products=summaries, zone=zone)


@router.get("/products/{product_id}", response_model=MallProductDetailResponse)
def get_mall_product(product_id: str, db: Session = Depends(get_db)):
    repo = SqlAlchemyMallRepository(db)
    repo.seed_default_data()

    product = repo.get_product(product_id)
    if product is None:
        raise HTTPException(status_code=404, detail="商品不存在")

    related = repo.list_related_products(product_id)
    related_summaries = [
        MallProductSummary(
            product_id=p.product_id,
            name=p.name,
            brand=p.brand,
            category_code=p.category_code,
            category_name=p.category_name,
            price_cents=p.price_cents,
            original_price_cents=p.original_price_cents,
            spec=p.spec,
            sales_text=p.sales_text,
            image_emoji=p.image_emoji,
            image_url=p.image_url,
            health_tags_raw=p.health_tags,
        )
        for p in related
    ]

    members = db.query(Member).all()
    best_member, recommend_reason = find_best_member_for_product(members, product)
    if recommend_reason is None:
        recommend_reason = "该商品适合全家日常健康饮食，本推荐不构成医疗建议。"

    import json as _json

    nutrition_raw = product.nutrition
    nutrition_rows = []
    if nutrition_raw:
        try:
            rows = _json.loads(nutrition_raw)
            if isinstance(rows, list):
                for item in rows:
                    if isinstance(item, dict) and "label" in item and "value" in item:
                        from app.schemas.mall import NutritionRow

                        nutrition_rows.append(NutritionRow(label=item["label"], value=item["value"]))
        except _json.JSONDecodeError:
            pass

    detail = MallProductDetail(
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
        description=product.description,
        ingredients=product.ingredients,
        shelf_life=product.shelf_life,
        nutrition_raw=product.nutrition,
        warning_tags_raw=product.warning_tags,
    )

    return MallProductDetailResponse(
        product=detail,
        recommend_reason=recommend_reason,
        nutrition_rows=nutrition_rows,
        related_products=related_summaries,
        health_notice="本推荐不构成医疗建议",
    )


@router.get("/cart", response_model=MallCartResponse)
def get_mall_cart(db: Session = Depends(get_db)):
    repo = SqlAlchemyMallRepository(db)
    return repo.build_cart_response(CART_OWNER_ID)


@router.post("/cart/items", response_model=MallCartResponse)
def add_mall_cart_item(request: MallCartItemCreateRequest, db: Session = Depends(get_db)):
    if request.quantity <= 0:
        raise HTTPException(status_code=400, detail="商品数量必须大于 0")

    repo = SqlAlchemyMallRepository(db)
    product = repo.get_product(request.product_id)
    if product is None:
        raise HTTPException(status_code=404, detail="商品不存在")

    repo.add_cart_item(CART_OWNER_ID, request.product_id, request.quantity)
    return repo.build_cart_response(CART_OWNER_ID)


@router.put("/cart/items/{product_id}", response_model=MallCartResponse)
def update_mall_cart_item(
    product_id: str,
    request: MallCartItemUpdateRequest,
    db: Session = Depends(get_db),
):
    if request.quantity <= 0:
        raise HTTPException(status_code=400, detail="商品数量必须大于 0")

    repo = SqlAlchemyMallRepository(db)
    result = repo.update_cart_item(CART_OWNER_ID, product_id, request.quantity)
    if result is None:
        raise HTTPException(status_code=404, detail="购物车商品不存在")

    return repo.build_cart_response(CART_OWNER_ID)


@router.delete("/cart/items/{product_id}", status_code=204)
def delete_mall_cart_item(product_id: str, db: Session = Depends(get_db)):
    repo = SqlAlchemyMallRepository(db)
    if not repo.delete_cart_item(CART_OWNER_ID, product_id):
        raise HTTPException(status_code=404, detail="购物车商品不存在")
    return Response(status_code=204)
