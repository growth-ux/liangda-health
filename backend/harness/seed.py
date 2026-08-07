"""Test Data Loader：为 eval case 注入稳定可复现的测试数据。"""

import json
from datetime import datetime

from sqlalchemy.orm import Session

from app.db.session import Base
from app.models.kb import KbChunk, KbDocument
from app.models.mall import MallProduct
from app.models.member import Member
from app.models.health_fact import HealthFact


MEMBERS = [
    dict(member_id="mem_dad", name="张志远", relation="父亲", gender="男",
         birth_year=1976, height_cm=172, weight_kg=78,
         allergies="海鲜", taste_preferences="咸口,下饭",
         health_tags=json.dumps(["高血压", "血脂偏高"])),
    dict(member_id="mem_mom", name="李秀英", relation="母亲", gender="女",
         birth_year=1978, height_cm=160, weight_kg=55,
         allergies="", taste_preferences="清淡,少油",
         health_tags=json.dumps(["控糖"])),
    dict(member_id="mem_son", name="张小明", relation="本人", gender="男",
         birth_year=2000, height_cm=178, weight_kg=68,
         allergies="花生", taste_preferences="",
         health_tags=""),
]


def seed_harness_data(db: Session) -> list[str]:
    """建表 + 灌入测试数据，返回 member_id 列表。"""
    Base.metadata.create_all(bind=db.bind)

    for kwargs in MEMBERS:
        db.add(Member(created_at=datetime.utcnow(), updated_at=datetime.utcnow(), **kwargs))

    db.add(KbDocument(
        document_id="doc_dad", file_name="dad_report.pdf", title="张志远2026体检报告",
        file_path="/tmp/dad.pdf", file_size=1024,
        member_id="mem_dad", status="ready",
    ))
    db.add(KbDocument(
        document_id="doc_mom", file_name="mom_report.pdf", title="李秀英2026体检报告",
        file_path="/tmp/mom.pdf", file_size=1024,
        member_id="mem_mom", status="ready",
    ))

    db.add_all([
        KbChunk(chunk_id="chunk_dad_1", document_id="doc_dad", member_id="mem_dad",
                page_no=3, content="总胆固醇 6.8 mmol/L，高于参考范围。甘油三酯 2.1 mmol/L，偏高。"),
        KbChunk(chunk_id="chunk_dad_2", document_id="doc_dad", member_id="mem_dad",
                page_no=2, content="血压 152/96 mmHg，偏高。建议控制盐分摄入。"),
        KbChunk(chunk_id="chunk_mom_1", document_id="doc_mom", member_id="mem_mom",
                page_no=2, content="空腹血糖 6.5 mmol/L，偏高。建议控制碳水化合物摄入。"),
    ])

    db.add_all([
        HealthFact(fact_id="fact_dad_1", member_id="mem_dad", fact_type="risk",
                   name="血脂偏高", status="warning",
                   source_document_id="doc_dad", source_page_no=3,
                   evidence_text="总胆固醇高于参考范围"),
        HealthFact(fact_id="fact_dad_2", member_id="mem_dad", fact_type="metric",
                   name="血压偏高", status="danger",
                   source_document_id="doc_dad", source_page_no=2,
                   evidence_text="血压 152/96 mmHg"),
        HealthFact(fact_id="fact_mom_1", member_id="mem_mom", fact_type="risk",
                   name="血糖偏高", status="warning",
                   source_document_id="doc_mom", source_page_no=2,
                   evidence_text="空腹血糖 6.5 mmol/L"),
    ])

    db.add_all([
        MallProduct(product_id="p_low_sodium_sauce", name="味极鲜低钠酱油", brand="味极鲜",
                     category_code="seasoning", category_name="调味品",
                     price_cents=1590, health_tags=json.dumps(["low_sodium"]),
                     recommend_tags=json.dumps(["low_sodium", "hypertension"])),
        MallProduct(product_id="p_olive_oil", name="欧丽薇兰特级初榨橄榄油", brand="欧丽薇兰",
                     category_code="oil", category_name="食用油",
                     price_cents=5990, health_tags=json.dumps(["low_fat", "high_fiber"]),
                     recommend_tags=json.dumps(["low_fat"])),
        MallProduct(product_id="p_quinoa", name="藜麦杂粮包", brand="北大荒",
                     category_code="grains", category_name="杂粮",
                     price_cents=2990, health_tags=json.dumps(["high_fiber", "low_gi"]),
                     recommend_tags=json.dumps(["high_fiber", "sugar_control", "low_gi"])),
        MallProduct(product_id="p_tofu", name="有机嫩豆腐", brand="清美",
                     category_code="soy_products", category_name="豆制品",
                     price_cents=590, health_tags=json.dumps(["high_protein", "low_fat"]),
                     recommend_tags=json.dumps(["high_protein", "low_fat"])),
        MallProduct(product_id="p_salt_veg", name="腌渍咸菜", brand="老字号",
                     category_code="vegetables", category_name="蔬菜",
                     price_cents=890, health_tags=json.dumps(["high_sodium"]),
                     recommend_tags=json.dumps(["high_sodium"])),
    ])

    db.commit()
    return [m["member_id"] for m in MEMBERS]
