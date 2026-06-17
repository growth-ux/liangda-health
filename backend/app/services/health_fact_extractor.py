from __future__ import annotations

from difflib import SequenceMatcher
import logging
import re
from typing import Protocol
from uuid import uuid4

from pydantic import BaseModel, Field, field_validator

from app.core.config import settings
from app.repositories.health_fact_repository import HealthFactCreate
from app.services.chunker import TextChunk
from app.services.llm_logging import log_llm_request

logger = logging.getLogger(__name__)


class PageLike(Protocol):
    page_no: int
    text_content: str


class ExtractedHealthFact(BaseModel):
    fact_type: str = Field(pattern="^(metric|risk|advice)$")
    name: str
    value: str | None = None
    unit: str | None = None
    reference_range: str | None = None
    status: str = Field(pattern="^(normal|warning|danger)$")
    source_page_no: int
    evidence_text: str

    @field_validator("value", mode="before")
    @classmethod
    def _coerce_value_to_string(cls, value):
        if value is None or isinstance(value, str):
            return value
        if isinstance(value, int | float):
            return str(value)
        return value


class ExtractedHealthFactsPayload(BaseModel):
    facts: list[ExtractedHealthFact]


class DashScopeHealthFactLlmClient:
    def extract(self, prompt: str) -> str:
        from openai import OpenAI

        if not settings.llm_api_key:
            return '{"facts": []}'

        client = OpenAI(api_key=settings.llm_api_key, base_url=settings.llm_base_url)
        log_llm_request(
            logger,
            service="health_fact.extract",
            payload={
                "model": settings.llm_model,
                "base_url": settings.llm_base_url,
                "temperature": 0,
                "timeout": settings.llm_timeout_seconds,
                "messages": [
                    {"role": "system", "content": _SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
            },
        )
        response = client.chat.completions.create(
            model=settings.llm_model,
            temperature=0,
            timeout=settings.llm_timeout_seconds,
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
        )
        return response.choices[0].message.content or '{"facts": []}'


class HealthFactExtractor:
    def __init__(self, llm_client=None):
        self.llm_client = llm_client or DashScopeHealthFactLlmClient()

    def extract(
        self,
        *,
        document_id: str,
        member_id: str,
        pages: list[PageLike],
        chunks: list[TextChunk],
    ) -> list[HealthFactCreate]:
        facts: list[HealthFactCreate] = []
        seen: set[tuple[int, str, str, str | None]] = set()
        chunks_by_page = _group_chunks_by_page(chunks)
        page_numbers = {page.page_no for page in pages}

        payload = self._extract_document(pages)
        for item in payload.facts:
            cleaned = _clean_fact(item)
            if cleaned is None or cleaned.source_page_no not in page_numbers:
                continue
            key = (cleaned.source_page_no, cleaned.fact_type, cleaned.name, cleaned.value)
            if key in seen:
                continue
            seen.add(key)
            source_chunk_id = _match_source_chunk_id(
                cleaned.evidence_text,
                chunks_by_page.get(cleaned.source_page_no, []),
            )
            facts.append(
                HealthFactCreate(
                    fact_id=f"fact_{uuid4().hex}",
                    member_id=member_id,
                    fact_type=cleaned.fact_type,
                    name=cleaned.name,
                    value=cleaned.value,
                    unit=cleaned.unit,
                    reference_range=cleaned.reference_range,
                    status=cleaned.status,
                    source_document_id=document_id,
                    source_page_no=cleaned.source_page_no,
                    source_chunk_id=source_chunk_id,
                    evidence_text=cleaned.evidence_text[:500],
                )
            )

        return facts

    def _extract_document(self, pages: list[PageLike]) -> ExtractedHealthFactsPayload:
        raw = self.llm_client.extract(_build_user_prompt(pages))
        return ExtractedHealthFactsPayload.model_validate_json(_strip_json(raw))


_SYSTEM_PROMPT = """你是健康体检报告结构化抽取器。只输出 JSON，不输出 Markdown。
你只能抽取报告原文明确出现的事实，不要医学推断。
不要把否定句抽取为风险，例如“未见异常”“未见血糖异常”“无高血压”不能抽为 warning。
每条事实必须有 evidence_text，且 evidence_text 必须是报告原文中的短句或表格行。"""


def _build_user_prompt(pages: list[PageLike]) -> str:
    document_text = "\n\n".join(
        f"【第 {page.page_no} 页】\n{page.text_content}"
        for page in pages
    )
    return f"""请从下面整份体检报告文本中一次性抽取健康事实。报告文本已经按页码分段。

只允许输出这个 JSON 结构：
{{
  "facts": [
    {{
      "fact_type": "metric|risk|advice",
      "name": "异常指标名、风险名或建议名",
      "value": "指标值，没有则为 null",
      "unit": "单位，没有则为 null",
      "reference_range": "参考范围，没有则为 null",
      "status": "warning|danger",
      "source_page_no": 1,
      "evidence_text": "报告原文证据"
    }}
  ]
}}

抽取规则：
- 只抽异常和可行动事实，不抽正常指标、普通阴性结论、复查事项或泛泛健康宣教。
- metric：只抽报告明确异常的指标，例如总胆固醇升高、空腹血糖升高、尿酸升高、BMI 超标、骨密度降低。
- risk：报告明确提示的风险或异常，例如血脂偏高、血糖偏高、骨密度低。
- advice：报告明确给出的饮食、运动、生活方式建议。
- 不要把否定句抽取为风险。
- 不要输出报告没有明确写出的结论。
- 不要输出 status=normal 的事实。
- source_page_no 必须填写证据所在页码。

报告文本：
{document_text}
"""


def _strip_json(raw: str) -> str:
    text = raw.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.startswith("json"):
            text = text[4:]
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end < start:
        raise ValueError("LLM response does not contain JSON object")
    return text[start : end + 1]


def _clean_fact(item: ExtractedHealthFact) -> ExtractedHealthFact | None:
    name = item.name.strip()
    evidence_text = item.evidence_text.strip()
    if not name or not evidence_text:
        return None
    if item.status == "normal":
        return None
    if _is_negated(evidence_text) and item.fact_type == "risk":
        return None
    if item.fact_type == "metric" and _is_value_within_reference_range(item.value, item.reference_range):
        return None
    return ExtractedHealthFact(
        fact_type=item.fact_type,
        name=name,
        value=item.value.strip() if item.value else None,
        unit=item.unit.strip() if item.unit else None,
        reference_range=item.reference_range.strip() if item.reference_range else None,
        status=item.status,
        source_page_no=item.source_page_no,
        evidence_text=evidence_text,
    )


def _is_negated(text: str) -> bool:
    return any(keyword in text for keyword in ("未见", "无明显", "无异常", "未提示", "阴性"))


def _is_value_within_reference_range(value: str | None, reference_range: str | None) -> bool:
    if not value or not reference_range:
        return False

    values = _extract_numbers(value)
    reference_values = _extract_numbers(reference_range)
    if not values or not reference_values:
        return False

    reference = reference_range.strip()
    if "-" in reference or "–" in reference or "—" in reference or "~" in reference or "至" in reference:
        if len(reference_values) < 2 or len(values) != 1:
            return False
        lower, upper = reference_values[0], reference_values[1]
        return lower <= values[0] <= upper

    if reference.startswith(("<=", "≤")):
        if len(values) != len(reference_values):
            return False
        return all(value <= limit for value, limit in zip(values, reference_values, strict=False))

    if reference.startswith("<"):
        if len(values) != len(reference_values):
            return False
        return all(value < limit for value, limit in zip(values, reference_values, strict=False))

    if reference.startswith((">=", "≥")):
        if len(values) != len(reference_values):
            return False
        return all(value >= limit for value, limit in zip(values, reference_values, strict=False))

    if reference.startswith(">"):
        if len(values) != len(reference_values):
            return False
        return all(value > limit for value, limit in zip(values, reference_values, strict=False))

    return False


def _extract_numbers(text: str) -> list[float]:
    return [float(value) for value in re.findall(r"\d+(?:\.\d+)?", text)]


def _group_chunks_by_page(chunks: list[TextChunk]) -> dict[int, list[TextChunk]]:
    result: dict[int, list[TextChunk]] = {}
    for chunk in chunks:
        result.setdefault(chunk.page_no, []).append(chunk)
    return result


def _match_source_chunk_id(evidence_text: str, chunks: list[TextChunk]) -> str | None:
    if not evidence_text or not chunks:
        return None
    normalized_evidence = _normalize(evidence_text)
    for chunk in chunks:
        if normalized_evidence and normalized_evidence in _normalize(chunk.content):
            return chunk.chunk_id

    best_chunk_id: str | None = None
    best_score = 0.0
    for chunk in chunks:
        score = SequenceMatcher(None, normalized_evidence, _normalize(chunk.content)).ratio()
        if score > best_score:
            best_score = score
            best_chunk_id = chunk.chunk_id
    return best_chunk_id if best_score >= 0.75 else None


def _normalize(text: str) -> str:
    return "".join(text.split()).lower()
