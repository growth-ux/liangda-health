from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.orm import Session

from app.core.demo import real_only
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
    ProductFeedbackRequest,
    ProductFeedbackResponse,
)
from app.services.mall.mall_recommendation import (
    build_daily_recommendations,
    build_family_recommendation,
    build_member_recommendations,
    find_best_member_for_product,
    score_product_for_member,
)

router = APIRouter(prefix="/api/mall", tags=["mall"])

CART_OWNER_ID = "default_family"


@router.get("/home", response_model=MallHomeResponse)
def get_mall_home(db: Session = Depends(get_db)):
    repo = SqlAlchemyMallRepository(db)
    repo.seed_default_data()

    products = repo.list_all_products()
    health_zones = repo.list_zones(zone_type="health")
    categories = repo.list_zones(zone_type="category")

    members = db.query(Member).filter(real_only(Member.member_id)).all()

    family_recommendations = build_member_recommendations(members, products)
    family_universal = build_family_recommendation(members, products)

    daily_products = build_daily_recommendations(members, products)

    return MallHomeResponse(
        family_recommendations=family_recommendations,
        family_universal=family_universal,
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
                from app.services.mall.mall_recommendation import build_recommend_reason

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

    members = db.query(Member).filter(real_only(Member.member_id)).all()
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


# -------- 商品反馈 --------

FEEDBACK_LABELS = {
    "like": "喜欢",
    "dislike": "不喜欢",
    "too_expensive": "觉得太贵",
    "purchased": "已购买",
}


@router.post("/feedback", response_model=ProductFeedbackResponse)
def submit_product_feedback(
    request: ProductFeedbackRequest,
    db: Session = Depends(get_db),
):
    from datetime import datetime as _dt

    from app.models.mall import MallProduct, MallProductFeedback
    from app.services.common.memory_service import MemoryService

    if request.feedback_type not in FEEDBACK_LABELS:
        raise HTTPException(status_code=400, detail="feedback_type 不合法")

    product = db.query(MallProduct).filter(MallProduct.product_id == request.product_id).one_or_none()
    product_name = product.name if product else request.product_id

    # 查询成员信息，用于记忆文本中的真实称呼
    member_name = None
    if request.member_id:
        member = db.query(Member).filter(Member.member_id == request.member_id).one_or_none()
        if member:
            member_name = member.name or member.relation

    # 幂等：同一 product+member+feedback_type 只保留最新一条
    existing = (
        db.query(MallProductFeedback)
        .filter(
            MallProductFeedback.product_id == request.product_id,
            MallProductFeedback.feedback_type == request.feedback_type,
            MallProductFeedback.member_id == request.member_id,
        )
        .first()
    )
    if existing:
        existing.session_id = request.session_id
        existing.message_id = request.message_id
        existing.created_at = _dt.utcnow()
    else:
        db.add(
            MallProductFeedback(
                product_id=request.product_id,
                feedback_type=request.feedback_type,
                member_id=request.member_id,
                session_id=request.session_id,
                message_id=request.message_id,
            )
        )
    db.commit()

    # 写入 mem0 记忆，让下一轮推荐能感知反馈
    label = FEEDBACK_LABELS[request.feedback_type]
    memory_text = _build_feedback_memory_text(request, product_name, label, member_name=member_name)
    try:
        mem = MemoryService()
        if mem.enabled:
            # member_id 为空时 fallback 到 family_user_id，确保 _resolve_owner 不会返回 None
            effective_member_id = request.member_id or mem.family_user_id
            mem.add_from_user_message(memory_text, member_id=effective_member_id)
    except Exception:
        import logging
        logging.getLogger(__name__).exception("feedback memory write failed")

    # 生成前端提示文案
    replacement_hint = None
    if request.feedback_type in ("dislike", "too_expensive"):
        replacement_hint = f"已收到反馈「{label}」，下次推荐将调整商品。"
    elif request.feedback_type == "like":
        replacement_hint = f"已记录「喜欢{product_name}」，后续会多推荐类似商品。"
    else:
        replacement_hint = f"已记录「{product_name}」已购买。"

    return ProductFeedbackResponse(
        ok=True,
        message=f"反馈「{label}」已记录",
        feedback_type=request.feedback_type,
        product_name=product_name,
        replacement_hint=replacement_hint,
    )


def _build_feedback_memory_text(
    request: ProductFeedbackRequest, product_name: str, label: str, *, member_name: str | None = None
) -> str:
    """把商品反馈包装成 mem0 能抽取为 marketing_feedback 的自然语言。"""
    # 优先用真实成员名，其次用“家人”，最fallback 用“我”
    who = member_name if member_name else ("家人" if request.member_id else "我")
    if request.feedback_type == "dislike":
        return f"{who}不喜欢「{product_name}」，下次不要推荐这个商品，换一款类似健康方向的其他商品。"
    if request.feedback_type == "too_expensive":
        return f"{who}觉得「{product_name}」太贵了，下次推荐时优先考虑性价比更高的同类商品。"
    if request.feedback_type == "like":
        return f"{who}喜欢「{product_name}」，以后可以多推荐同品牌或同类型的商品。"
    return f"{who}已经购买了「{product_name}」。"
