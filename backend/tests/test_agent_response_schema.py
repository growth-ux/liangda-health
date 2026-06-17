import pytest
from pydantic import ValidationError

from app.schemas.agent_response import (
    GeneralAdvicePayload,
    GreetingPayload,
    KbInterpretationPayload,
    MealPlanPayload,
    QaPayload,
    StructuredResponse,
)


def test_meal_plan_payload_validates():
    payload = {
        "kind": "meal_plan",
        "summary_text": "今晚清淡为主。",
        "payload": {
            "scope": "family",
            "target_member_name": None,
            "meal_items": [
                {"slot": "dinner", "title": "清蒸鸡胸", "summary": "低脂高蛋白"},
            ],
            "member_adjustments": [
                {"member_name": "爸爸", "note": "控脂", "tags": ["控脂"]},
            ],
            "avoid_tags": ["油炸"],
            "extra_note": None,
        },
    }
    response = StructuredResponse.model_validate(payload)
    assert response.kind == "meal_plan"
    assert response.payload.scope == "family"
    assert response.payload.meal_items[0].title == "清蒸鸡胸"


def test_qa_payload_validates():
    payload = {
        "kind": "qa",
        "summary_text": "早餐建议如下。",
        "payload": {"question_topic": "早餐", "answer": "高蛋白 + 慢碳", "tips": ["加一个鸡蛋"]},
    }
    response = StructuredResponse.model_validate(payload)
    assert response.kind == "qa"
    assert response.payload.tips == ["加一个鸡蛋"]


def test_greeting_payload_validates():
    payload = {
        "kind": "greeting",
        "summary_text": "你好，今天可以问我一日三餐。",
        "payload": {"message": "你好", "suggested_topics": ["三餐"]},
    }
    response = StructuredResponse.model_validate(payload)
    assert response.payload.suggested_topics == ["三餐"]


def test_kb_interpretation_payload_validates():
    payload = {
        "kind": "kb_interpretation",
        "summary_text": "爸爸血脂轻度偏高。",
        "payload": {
            "topic": "血脂",
            "evidence": [{"source": "2024 体检", "excerpt": "LDL-C 3.8"}],
            "suggestions": [{"text": "调整饮食", "priority": "primary"}],
            "red_flags": ["胸闷"],
        },
    }
    response = StructuredResponse.model_validate(payload)
    assert response.payload.evidence[0].source == "2024 体检"


def test_structured_response_payload_follows_kind():
    payload = {
        "kind": "kb_interpretation",
        "summary_text": "爸爸的血脂指标偏高，建议少吃肥肉和动物内脏，多吃燕麦、豆类和绿叶菜，并定期复查。",
        "payload": {
            "topic": "爸爸血脂情况",
            "evidence": [
                {
                    "source": "2024年体检报告 第3页",
                    "excerpt": "总胆固醇 6.8 mmol/L，甘油三酯 2.1 mmol/L。",
                }
            ],
            "suggestions": [
                {"text": "少吃肥肉、动物内脏，多吃燕麦、豆类和绿叶菜。", "priority": "primary"},
                {"text": "每天快走或骑车30分钟，每周至少5天。", "priority": "secondary"},
            ],
            "red_flags": ["胸痛、胸闷或明显头晕时及时就医"],
        },
    }

    response = StructuredResponse.model_validate(payload)

    assert isinstance(response.payload, KbInterpretationPayload)
    assert response.payload.topic == "爸爸血脂情况"


def test_kb_interpretation_suggestions_accept_string_items():
    payload = {
        "kind": "kb_interpretation",
        "summary_text": "爸爸血脂偏高，建议先从饮食和运动调整。",
        "payload": {
            "topic": "血脂偏高",
            "evidence": [{"source": "2024年体检报告 第3页", "excerpt": "总胆固醇 6.8 mmol/L。"}],
            "suggestions": ["减少动物油、肥肉摄入", "定期复查血脂"],
            "red_flags": ["胸痛胸闷时及时就医"],
        },
    }

    response = StructuredResponse.model_validate(payload)

    assert response.payload.suggestions[0].text == "减少动物油、肥肉摄入"
    assert response.payload.suggestions[0].priority == "primary"


def test_general_advice_payload_validates():
    payload = {
        "kind": "general_advice",
        "summary_text": "少油少糖。",
        "payload": {"topic": "日常饮食", "advice": "少油少糖多蔬菜", "cautions": ["高糖"]},
    }
    response = StructuredResponse.model_validate(payload)
    assert response.payload.advice == "少油少糖多蔬菜"


def test_unknown_kind_rejected():
    payload = {
        "kind": "nonsense",
        "summary_text": "x",
        "payload": {},
    }
    with pytest.raises(ValidationError):
        StructuredResponse.model_validate(payload)


def test_summary_text_too_long_rejected():
    payload = {
        "kind": "qa",
        "summary_text": "x" * 401,
        "payload": {"question_topic": "x", "answer": "x", "tips": []},
    }
    with pytest.raises(ValidationError):
        StructuredResponse.model_validate(payload)


def test_meal_plan_missing_meal_items_rejected():
    payload = {
        "kind": "meal_plan",
        "summary_text": "x",
        "payload": {
            "scope": "family",
            "target_member_name": None,
            "member_adjustments": [],
            "avoid_tags": [],
            "extra_note": None,
        },
    }
    with pytest.raises(ValidationError):
        StructuredResponse.model_validate(payload)
