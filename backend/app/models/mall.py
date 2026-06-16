from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.time import utc_now
from app.db.session import Base


class MallProduct(Base):
    __tablename__ = "mall_products"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    product_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    brand: Mapped[str | None] = mapped_column(String(80), nullable=True)
    category_code: Mapped[str] = mapped_column(String(50), nullable=False)
    category_name: Mapped[str] = mapped_column(String(50), nullable=False)
    price_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    original_price_cents: Mapped[int | None] = mapped_column(Integer, nullable=True)
    spec: Mapped[str | None] = mapped_column(String(80), nullable=True)
    sales_text: Mapped[str | None] = mapped_column(String(40), nullable=True)
    image_emoji: Mapped[str | None] = mapped_column(String(20), nullable=True)
    image_url: Mapped[str | None] = mapped_column(String(255), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    ingredients: Mapped[str | None] = mapped_column(Text, nullable=True)
    shelf_life: Mapped[str | None] = mapped_column(String(80), nullable=True)
    nutrition: Mapped[str | None] = mapped_column(Text, nullable=True)
    health_tags: Mapped[str | None] = mapped_column(Text, nullable=True)
    recommend_tags: Mapped[str | None] = mapped_column(Text, nullable=True)
    warning_tags: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=utc_now,
        onupdate=utc_now,
    )


class MallZone(Base):
    __tablename__ = "mall_zones"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    zone_code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    zone_type: Mapped[str] = mapped_column(String(20), nullable=False)
    icon: Mapped[str | None] = mapped_column(String(20), nullable=True)
    match_tag: Mapped[str | None] = mapped_column(String(50), nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class MallCartItem(Base):
    __tablename__ = "mall_cart_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    cart_owner_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    product_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=utc_now,
        onupdate=utc_now,
    )


class MallProductRelation(Base):
    __tablename__ = "mall_product_relations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    product_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    related_product_id: Mapped[str] = mapped_column(String(64), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
