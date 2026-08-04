"""演示数据隔离约定。

集团经营看板的演示数据（app/scripts/seed_dashboard_demo.py 注入）主键统一带
`demo_dash_` 前缀；家庭端（C 端）查询通过本模块的条件统一排除演示数据，
看板侧则聚合全量（真实家庭 + 演示），互不干扰。
"""
from sqlalchemy import or_
from sqlalchemy.sql.elements import ColumnElement

DEMO_DATA_PREFIX = "demo_dash_"
# 演示加购使用独立购物车归属，避免污染家庭端 default_family 购物车。
DEMO_CART_OWNER_ID = f"{DEMO_DATA_PREFIX}family"


def real_only(column) -> ColumnElement:
    """排除演示数据行（主键/外键带演示前缀）。"""
    return ~column.like(f"{DEMO_DATA_PREFIX}%")


def real_member_or_null(column) -> ColumnElement:
    """保留成员为空的系统行，排除演示成员关联行。"""
    return or_(column.is_(None), ~column.like(f"{DEMO_DATA_PREFIX}%"))
