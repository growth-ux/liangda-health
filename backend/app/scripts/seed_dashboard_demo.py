"""为集团经营看板注入演示数据。

用途：比赛演示时让看板有集团量级的家庭健康资产与营销转化数据。
只依赖现有表，不新增表；所有演示数据主键带 `demo_dash_` 前缀，可 `--reset` 清理。

模式：
  - 默认：只注入近 14 天对话/推荐/加购数据（轻量）。
  - --full：额外注入家庭规模健康资产（约 30 个家庭、120 个成员、180 份报告、600 条健康事实）。

⚠️  注意：
  - `--full` 注入期间，演示成员/报告等与真实家庭数据同库存储，
    家庭端（C 端）查询已按 `demo_dash_` 前缀统一排除，不会互相串扰。
  - 演示加购写入独立归属 `demo_dash_family`，不占用家庭端购物车；
    `--reset` 仅清理演示数据与演示购物车。

用法（在 backend 目录下，PYTHONPATH=backend）：
  python -m app.scripts.seed_dashboard_demo                # 轻量：对话/推荐/加购
  python -m app.scripts.seed_dashboard_demo --full         # 完整：健康资产 + 对话转化
  python -m app.scripts.seed_dashboard_demo --reset        # 清理全部演示数据
"""
from __future__ import annotations

import argparse
import json
import random
import sys
from datetime import date, timedelta
from uuid import uuid4

from app.core.demo import DEMO_CART_OWNER_ID
from app.core.time import utc_now
from app.db.session import SessionLocal
from app.models.agent import AgentMessage, AgentSession
from app.models.device import DeviceDailyMetric
from app.models.health_fact import HealthFact
from app.models.kb import KbDocument
from app.models.mall import MallCartItem, MallProduct
from app.models.member import Member
from app.models.notice import Notice

SEED_PREFIX = "demo_dash_"
CART_OWNER_ID = DEMO_CART_OWNER_ID
MODEL_NAME = "qwen-plus"

SURNAMES = ["王", "李", "张", "刘", "陈", "杨", "赵", "黄", "周", "吴", "徐", "孙", "马", "朱", "胡"]
GIVEN_NAMES = ["建国", "秀英", "国强", "桂芳", "志强", "玉兰", "永强", "淑珍", "海涛", "凤霞", "军", "丽娜"]

# 家庭成员模板：(relation, gender, 出生年范围, 常见健康标签池)
MEMBER_TEMPLATES = [
    ("父亲", "男", (1962, 1972), ["高血压", "高血脂", "低钠饮食", "控脂"]),
    ("母亲", "女", (1964, 1974), ["补钙", "骨密度偏低", "控糖"]),
    ("本人", "男", (1988, 1996), ["BMI 偏高", "健身", "高蛋白"]),
    ("孩子", "女", (2014, 2018), ["成长发育", "早餐营养"]),
    ("祖母", "女", (1938, 1948), ["高血压", "低钠饮食", "易消化"]),
]

INSTITUTIONS = ["北京协和医院", "上海瑞金医院", "广州中山一院", "成都华西医院", "社区健康服务中心"]

FACT_POOL = [
    # (name, fact_type, value, unit, reference_range, status 权重偏向)
    ("总胆固醇", "metric", "6.2", "mmol/L", "<5.2", "warning"),
    ("低密度脂蛋白", "metric", "4.1", "mmol/L", "<3.4", "warning"),
    ("收缩压", "metric", "148", "mmHg", "90-139", "warning"),
    ("空腹血糖", "metric", "6.8", "mmol/L", "3.9-6.1", "warning"),
    ("尿酸", "metric", "486", "μmol/L", "208-428", "warning"),
    ("骨密度 T 值", "metric", "-1.8", "", ">-1.0", "warning"),
    ("血红蛋白", "metric", "132", "g/L", "115-150", "normal"),
    ("肝功能 ALT", "metric", "24", "U/L", "7-40", "normal"),
    ("血脂偏高", "risk", None, None, None, "warning"),
    ("血压偏高", "risk", None, None, None, "danger"),
    ("脂肪肝", "risk", None, None, None, "warning"),
    ("骨量减少", "risk", None, None, None, "warning"),
    ("建议低钠饮食", "advice", None, None, None, "warning"),
    ("建议增加膳食纤维", "advice", None, None, None, "normal"),
    ("建议定期复查血脂", "advice", None, None, None, "warning"),
]

USER_QUESTIONS = [
    "爸爸今晚吃什么比较好？",
    "妈妈最近想补钙，有什么推荐？",
    "帮我看下爸爸报告里血脂的情况",
    "这周给全家安排一下晚餐",
    "爸爸血压偏高，有什么要注意？",
    "孩子早餐吃什么更营养？",
    "有没有适合控糖的主食推荐？",
    "妈妈骨密度偏低，饮食上怎么调整？",
    "推荐几款适合老人的低钠调味品",
    "爸爸不喜欢鱼，蛋白质怎么补？",
    "周末全家做饭，买点什么合适？",
    "最近买的杂粮还有没有类似的推荐？",
]

RECOMMEND_REASONS = [
    "适合血压偏高人群，低钠配方",
    "高钙高蛋白，契合补钙需求",
    "低脂高纤，适合控脂晚餐",
    "无糖配方，适合控糖目标",
    "杂粮主食，升糖负担小",
    "优质植物蛋白，替代鱼类选择",
    "全家适用，营养均衡",
]

ASSISTANT_REPLIES = [
    "已结合健康画像和近期记忆为您整理建议，推荐商品如下。",
    "根据最新体检事实和手环状态，给您如下饮食与商品建议。",
    "综合考虑家庭健康原则和口味偏好，推荐以下内容。",
]

NOTICE_TEMPLATES = [
    ("health_alert", "warning", "血压波动提醒", "近期手环数据显示血压偏高，请注意低钠饮食与规律作息。"),
    ("health_alert", "danger", "血脂异常干预", "总胆固醇超出参考范围，已生成低脂饮食方案。"),
    ("recommendation", "info", "本周饮食建议", "已根据健康画像生成本周低钠高纤餐单。"),
    ("report_reminder", "info", "定期复查提醒", "距上次体检已半年，建议安排复查计划。"),
]


# ===== 健康资产注入（--full） =====


def seed_assets(db, families: int) -> None:
    now = utc_now()
    member_count = 0
    document_count = 0
    fact_count = 0
    notice_count = 0

    for family_index in range(families):
        surname = random.choice(SURNAMES)
        for relation, gender, year_range, tag_pool in MEMBER_TEMPLATES:
            member_id = f"{SEED_PREFIX}mem_{uuid4().hex[:10]}"
            has_tags = random.random() < 0.45
            tags = random.sample(tag_pool, k=random.randint(1, 2)) if has_tags else []
            db.add(
                Member(
                    member_id=member_id,
                    name=f"{surname}{random.choice(GIVEN_NAMES)}",
                    relation=relation,
                    gender=gender,
                    birth_year=random.randint(*year_range),
                    height_cm=random.randint(155, 182),
                    weight_kg=random.randint(50, 85),
                    health_tags=json.dumps(tags, ensure_ascii=False) if tags else None,
                    created_at=now - timedelta(days=random.randint(20, 60)),
                )
            )
            member_count += 1

            # 每个成员约一半概率生成 1~2 条健康提醒，约 65% 已完成
            if random.random() < 0.5:
                for _ in range(random.randint(1, 2)):
                    category, level, title, description = random.choice(NOTICE_TEMPLATES)
                    notice_id = f"{SEED_PREFIX}not_{uuid4().hex[:10]}"
                    db.add(
                        Notice(
                            notice_id=notice_id,
                            category=category,
                            level=level,
                            title=title,
                            description=description,
                            source="housekeeper",
                            member_id=member_id,
                            status="done" if random.random() < 0.65 else "unread",
                            dedupe_key=notice_id,
                            created_at=now - timedelta(days=random.randint(0, 13)),
                        )
                    )
                    notice_count += 1

            for _ in range(random.randint(1, 2)):
                document_id = f"{SEED_PREFIX}doc_{uuid4().hex[:10]}"
                exam_date = date.today() - timedelta(days=random.randint(15, 170))
                db.add(
                    KbDocument(
                        document_id=document_id,
                        file_name=f"{surname}家{relation}体检报告.pdf",
                        file_path=f"uploads/demo/{document_id}.pdf",
                        file_size=random.randint(200_000, 2_000_000),
                        page_count=random.randint(4, 12),
                        title=f"{exam_date.year} 年度体检报告",
                        patient_name=f"{surname}{random.choice(GIVEN_NAMES)}",
                        exam_date=exam_date,
                        institution=random.choice(INSTITUTIONS),
                        member_id=member_id,
                        status="ready",
                        fact_extract_status="done",
                        created_at=now - timedelta(days=random.randint(10, 55)),
                    )
                )
                document_count += 1

                for _ in range(random.randint(3, 6)):
                    name, fact_type, value, unit, reference_range, bias_status = random.choice(FACT_POOL)
                    status = bias_status if random.random() < 0.75 else random.choice(["normal", "warning"])
                    db.add(
                        HealthFact(
                            fact_id=f"{SEED_PREFIX}fact_{uuid4().hex[:10]}",
                            member_id=member_id,
                            fact_type=fact_type,
                            name=name,
                            value=value,
                            unit=unit,
                            reference_range=reference_range,
                            status=status,
                            source_document_id=document_id,
                            source_page_no=random.randint(1, 6),
                            evidence_text=f"{name}相关检测结论见报告原文",
                            created_at=now - timedelta(days=random.randint(9, 54)),
                        )
                    )
                    fact_count += 1

    db.commit()
    print(
        f"已注入健康资产：成员 {member_count} 人、报告 {document_count} 份、"
        f"健康事实 {fact_count} 条、健康提醒 {notice_count} 条"
    )


# ===== 对话/推荐/加购注入 =====


def seed_chat(db, days: int, sessions_per_day: int, cart_rate: float) -> None:
    products = db.query(MallProduct).all()
    if not products:
        print("⚠️  商城没有商品，无法生成推荐数据，请先初始化商城商品")
        sys.exit(1)

    relations = [member.relation for member in db.query(Member).all()] or ["爸爸", "妈妈"]
    now = utc_now()
    recommended_product_ids: set[str] = set()
    session_total = 0
    message_total = 0

    for day_offset in range(days - 1, -1, -1):
        day_base = now - timedelta(days=day_offset)
        for _ in range(random.randint(max(1, sessions_per_day - 2), sessions_per_day + 2)):
            session_id = f"{SEED_PREFIX}sess_{uuid4().hex[:12]}"
            created_at = day_base.replace(
                hour=random.randint(7, 21),
                minute=random.randint(0, 59),
                second=random.randint(0, 59),
            )
            if created_at > now:
                created_at = now - timedelta(minutes=random.randint(1, 60))

            question = random.choice(USER_QUESTIONS).replace("爸爸", random.choice(relations))
            db.add(
                AgentSession(
                    session_id=session_id,
                    title=question[:40],
                    status="active",
                    created_at=created_at,
                    updated_at=created_at,
                )
            )
            db.add(
                AgentMessage(
                    message_id=f"{SEED_PREFIX}m_{uuid4().hex[:12]}",
                    session_id=session_id,
                    role="user",
                    content=question,
                    status="done",
                    created_at=created_at,
                )
            )
            message_total += 1

            reply_at = created_at + timedelta(seconds=random.randint(5, 40))
            recommendation_items: list[dict] = []
            if random.random() < 0.7:
                chosen = random.sample(products, k=random.randint(1, min(3, len(products))))
                recommendation_items = [
                    {
                        "product_id": product.product_id,
                        "name": product.name,
                        "reason": random.choice(RECOMMEND_REASONS),
                    }
                    for product in chosen
                ]
                recommended_product_ids.update(product.product_id for product in chosen)

            db.add(
                AgentMessage(
                    message_id=f"{SEED_PREFIX}m_{uuid4().hex[:12]}",
                    session_id=session_id,
                    role="assistant",
                    content=random.choice(ASSISTANT_REPLIES),
                    status="done",
                    product_recommendations=(
                        json.dumps(recommendation_items, ensure_ascii=False)
                        if recommendation_items
                        else None
                    ),
                    token_prompt=random.randint(400, 1200),
                    token_completion=random.randint(150, 600),
                    model_name=MODEL_NAME,
                    created_at=reply_at,
                )
            )
            session_total += 1
            message_total += 1

    # 转化承接：把部分被推荐商品加入购物车
    existing_cart_product_ids = {
        row[0]
        for row in db.query(MallCartItem.product_id)
        .filter(MallCartItem.cart_owner_id == CART_OWNER_ID)
        .all()
    }
    candidates = sorted(recommended_product_ids - existing_cart_product_ids)
    cart_count = int(len(candidates) * cart_rate)
    for product_id in random.sample(candidates, k=min(cart_count, len(candidates))):
        db.add(
            MallCartItem(
                cart_owner_id=CART_OWNER_ID,
                product_id=product_id,
                quantity=random.randint(1, 2),
            )
        )

    db.commit()
    print(
        f"已注入转化数据：会话 {session_total} 个、消息 {message_total} 条、"
        f"被推荐商品 {len(recommended_product_ids)} 种"
    )


# ===== 清理 =====


def reset_demo_data(db) -> None:
    prefix = f"{SEED_PREFIX}%"

    message_count = (
        db.query(AgentMessage).filter(AgentMessage.session_id.like(prefix)).delete(synchronize_session=False)
    )
    session_count = db.query(AgentSession).filter(AgentSession.session_id.like(prefix)).delete(synchronize_session=False)
    member_ids = [row[0] for row in db.query(Member.member_id).filter(Member.member_id.like(prefix)).all()]
    fact_count = db.query(HealthFact).filter(HealthFact.member_id.like(prefix)).delete(synchronize_session=False)
    document_count = db.query(KbDocument).filter(KbDocument.document_id.like(prefix)).delete(synchronize_session=False)
    member_count = db.query(Member).filter(Member.member_id.like(prefix)).delete(synchronize_session=False)
    notice_count = db.query(Notice).filter(Notice.member_id.like(prefix)).delete(synchronize_session=False)

    device_count = 0
    if member_ids:
        device_count = (
            db.query(DeviceDailyMetric)
            .filter(DeviceDailyMetric.member_id.in_(member_ids))
            .delete(synchronize_session=False)
        )

    cart_count = (
        db.query(MallCartItem)
        .filter(MallCartItem.cart_owner_id == DEMO_CART_OWNER_ID)
        .delete(synchronize_session=False)
    )
    db.commit()
    print(
        f"已清理演示数据：会话 {session_count}、消息 {message_count}、成员 {member_count}、"
        f"报告 {document_count}、健康事实 {fact_count}、设备记录 {device_count}、"
        f"关联通知 {notice_count}、演示购物车 {cart_count} 条"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="集团经营看板演示数据注入")
    parser.add_argument("--days", type=int, default=14, help="对话数据覆盖最近 N 天，默认 14")
    parser.add_argument("--sessions-per-day", type=int, default=8, help="每天会话数基准，默认 8")
    parser.add_argument("--cart-rate", type=float, default=0.4, help="被推荐商品加购比例，默认 0.4")
    parser.add_argument("--full", action="store_true", help="额外注入家庭规模健康资产（成员/报告/健康事实）")
    parser.add_argument("--families", type=int, default=30, help="--full 模式下注入家庭数，默认 30")
    parser.add_argument("--reset", action="store_true", help="清理全部演示数据并清空购物车")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        if args.reset:
            reset_demo_data(db)
            return 0
        if args.full:
            seed_assets(db, families=args.families)
        seed_chat(db, days=args.days, sessions_per_day=args.sessions_per_day, cart_rate=args.cart_rate)
        print("提示：演示加购写入独立归属 demo_dash_family，不影响家庭端购物车")
    finally:
        db.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
