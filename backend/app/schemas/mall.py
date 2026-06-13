import json

from pydantic import BaseModel, Field, computed_field


def _safe_json_list(raw: str | None) -> list:
    if not raw:
        return []
    try:
        value = json.loads(raw)
    except json.JSONDecodeError:
        return []
    if not isinstance(value, list):
        return []
    return value


def _format_price(cents: int) -> str:
    yuan = cents / 100
    if yuan == int(yuan):
        return f"¥{int(yuan)}"
    return f"¥{yuan:.1f}"


class NutritionRow(BaseModel):
    label: str
    value: str


class MallProductSummary(BaseModel):
    product_id: str
    name: str
    brand: str | None = None
    category_code: str
    category_name: str
    price_cents: int
    original_price_cents: int | None = None
    spec: str | None = None
    sales_text: str | None = None
    image_emoji: str | None = None
    image_url: str | None = None
    health_tags_raw: str | None = None
    recommend_reason: str | None = None

    @computed_field
    @property
    def price_text(self) -> str:
        return _format_price(self.price_cents)

    @computed_field
    @property
    def original_price_text(self) -> str | None:
        if self.original_price_cents is None:
            return None
        return _format_price(self.original_price_cents)

    @computed_field
    @property
    def health_tags(self) -> list[str]:
        return _safe_json_list(self.health_tags_raw)


class MallProductDetail(MallProductSummary):
    description: str | None = None
    ingredients: str | None = None
    shelf_life: str | None = None
    nutrition_raw: str | None = None
    warning_tags_raw: str | None = None

    @computed_field
    @property
    def nutrition_rows(self) -> list[NutritionRow]:
        rows = _safe_json_list(self.nutrition_raw)
        result = []
        for item in rows:
            if isinstance(item, dict) and "label" in item and "value" in item:
                result.append(NutritionRow(label=item["label"], value=item["value"]))
        return result

    @computed_field
    @property
    def warning_tags(self) -> list[str]:
        return _safe_json_list(self.warning_tags_raw)


class MallZone(BaseModel):
    zone_code: str
    name: str
    zone_type: str
    icon: str | None = None
    match_tag: str | None = None
    sort_order: int = 0


class MallFamilyRecommendation(BaseModel):
    member_id: str
    member_name: str
    relation: str
    zone_name: str
    summary: str
    products: list[MallProductSummary] = Field(default_factory=list)


class MallHomeResponse(BaseModel):
    family_recommendations: list[MallFamilyRecommendation] = Field(default_factory=list)
    health_zones: list[MallZone] = Field(default_factory=list)
    daily_products: list[MallProductSummary] = Field(default_factory=list)
    categories: list[MallZone] = Field(default_factory=list)


class MallProductListResponse(BaseModel):
    products: list[MallProductSummary] = Field(default_factory=list)
    zone: MallZone | None = None


class MallProductDetailResponse(BaseModel):
    product: MallProductDetail
    recommend_reason: str | None = None
    nutrition_rows: list[NutritionRow] = Field(default_factory=list)
    related_products: list[MallProductSummary] = Field(default_factory=list)
    health_notice: str = "本推荐不构成医疗建议"


class MallCartItem(BaseModel):
    product_id: str
    name: str
    spec: str | None = None
    image_emoji: str | None = None
    image_url: str | None = None
    price_cents: int
    quantity: int
    subtotal_cents: int = 0

    @computed_field
    @property
    def price_text(self) -> str:
        return _format_price(self.price_cents)

    @computed_field
    @property
    def subtotal_text(self) -> str:
        return _format_price(self.subtotal_cents)


class MallCartResponse(BaseModel):
    items: list[MallCartItem] = Field(default_factory=list)
    total_quantity: int = 0
    total_cents: int = 0

    @computed_field
    @property
    def total_text(self) -> str:
        return _format_price(self.total_cents)


class MallCartItemCreateRequest(BaseModel):
    product_id: str
    quantity: int = 1


class MallCartItemUpdateRequest(BaseModel):
    quantity: int
