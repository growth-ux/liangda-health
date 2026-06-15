import json
import os
from pathlib import Path

import pytest

from app.services.chunker import TextChunk
from app.services.chunker import chunk_page_text
from app.services.health_fact_extractor import HealthFactExtractor
from app.services.kb_service import PageCreate
from app.services.pdf_extractor import PdfExtractor


class FakeLlmClient:
    def __init__(self, response: str):
        self.response = response
        self.calls = []

    def extract(self, prompt: str) -> str:
        self.calls.append(prompt)
        return self.response


def _page(text: str, page_no: int = 1) -> PageCreate:
    return PageCreate(document_id="doc_1", page_no=page_no, text_content=text)


def _chunk(content: str, *, chunk_id: str = "chunk_1", page_no: int = 1) -> TextChunk:
    return TextChunk(
        chunk_id=chunk_id,
        document_id="doc_1",
        member_id="mem_1",
        page_no=page_no,
        content=content,
    )


def test_llm_extractor_builds_health_facts_and_exact_chunk_match():
    llm = FakeLlmClient(
        """
        {
          "facts": [
            {
              "fact_type": "metric",
              "name": "总胆固醇",
              "value": "6.2",
              "unit": "mmol/L",
              "reference_range": "<5.2",
              "status": "warning",
              "source_page_no": 2,
              "evidence_text": "总胆固醇 6.2 mmol/L ↑ 参考范围 <5.2"
            }
          ]
        }
        """
    )
    extractor = HealthFactExtractor(llm_client=llm)

    facts = extractor.extract(
        document_id="doc_1",
        member_id="mem_1",
        pages=[
            _page("封面", page_no=1),
            _page("总胆固醇 6.2 mmol/L ↑ 参考范围 <5.2", page_no=2),
        ],
        chunks=[_chunk("姓名 张三 总胆固醇 6.2 mmol/L ↑ 参考范围 <5.2", page_no=2)],
    )

    assert len(facts) == 1
    assert facts[0].member_id == "mem_1"
    assert facts[0].fact_type == "metric"
    assert facts[0].name == "总胆固醇"
    assert facts[0].value == "6.2"
    assert facts[0].unit == "mmol/L"
    assert facts[0].reference_range == "<5.2"
    assert facts[0].status == "warning"
    assert facts[0].source_document_id == "doc_1"
    assert facts[0].source_page_no == 2
    assert facts[0].source_chunk_id == "chunk_1"
    assert facts[0].evidence_text == "总胆固醇 6.2 mmol/L ↑ 参考范围 <5.2"
    assert len(llm.calls) == 1
    assert "【第 1 页】" in llm.calls[0]
    assert "【第 2 页】" in llm.calls[0]
    assert "不要把否定句抽取为风险" in llm.calls[0]


def test_llm_extractor_extracts_whole_document_in_one_llm_call():
    llm = FakeLlmClient(
        """
        {
          "facts": [
            {
              "fact_type": "metric",
              "name": "尿酸",
              "value": "520",
              "unit": "umol/L",
              "reference_range": "208-428",
              "status": "warning",
              "source_page_no": 1,
              "evidence_text": "尿酸 520 umol/L ↑ 参考范围 208-428"
            },
            {
              "fact_type": "advice",
              "name": "低嘌呤饮食",
              "value": null,
              "unit": null,
              "reference_range": null,
              "status": "warning",
              "source_page_no": 2,
              "evidence_text": "建议低嘌呤饮食，减少动物内脏摄入"
            }
          ]
        }
        """
    )
    extractor = HealthFactExtractor(llm_client=llm)

    facts = extractor.extract(
        document_id="doc_1",
        member_id="mem_1",
        pages=[
            _page("尿酸 520 umol/L ↑ 参考范围 208-428", page_no=1),
            _page("建议低嘌呤饮食，减少动物内脏摄入", page_no=2),
        ],
        chunks=[
            _chunk("尿酸 520 umol/L ↑ 参考范围 208-428", chunk_id="chunk_1", page_no=1),
            _chunk("建议低嘌呤饮食，减少动物内脏摄入", chunk_id="chunk_2", page_no=2),
        ],
    )

    assert len(llm.calls) == 1
    assert "【第 1 页】" in llm.calls[0]
    assert "【第 2 页】" in llm.calls[0]
    assert [fact.source_page_no for fact in facts] == [1, 2]
    assert [fact.source_chunk_id for fact in facts] == ["chunk_1", "chunk_2"]


def test_llm_extractor_filters_invalid_negated_and_normal_facts():
    llm = FakeLlmClient(
        """
        {
          "facts": [
            {
              "fact_type": "risk",
              "name": "血糖偏高",
              "value": null,
              "unit": null,
              "reference_range": null,
              "status": "warning",
              "source_page_no": 1,
              "evidence_text": "未见血糖异常"
            },
            {
              "fact_type": "metric",
              "name": "",
              "value": "6.2",
              "unit": "mmol/L",
              "reference_range": null,
              "status": "warning",
              "source_page_no": 1,
              "evidence_text": "总胆固醇 6.2"
            },
            {
              "fact_type": "metric",
              "name": "血红蛋白",
              "value": "145",
              "unit": "g/L",
              "reference_range": "130-175",
              "status": "normal",
              "source_page_no": 1,
              "evidence_text": "血红蛋白 145 g/L 参考范围 130-175"
            }
          ]
        }
        """
    )
    extractor = HealthFactExtractor(llm_client=llm)

    facts = extractor.extract(
        document_id="doc_1",
        member_id="mem_1",
        pages=[_page("未见血糖异常。总胆固醇 6.2。血红蛋白 145 g/L 参考范围 130-175")],
        chunks=[_chunk("未见血糖异常。总胆固醇 6.2。血红蛋白 145 g/L 参考范围 130-175")],
    )

    assert facts == []


def test_llm_extractor_filters_metric_within_reference_range():
    llm = FakeLlmClient(
        """
        {
          "facts": [
            {
              "fact_type": "metric",
              "name": "尿酸",
              "value": 402,
              "unit": "μmol/L",
              "reference_range": "208-428",
              "status": "warning",
              "source_page_no": 1,
              "evidence_text": "尿酸 402 208-428 μmol/L 正常高值"
            },
            {
              "fact_type": "metric",
              "name": "总胆固醇",
              "value": "5.9",
              "unit": "mmol/L",
              "reference_range": "<5.2",
              "status": "warning",
              "source_page_no": 1,
              "evidence_text": "总胆固醇 5.9 <5.2 mmol/L 偏高"
            }
          ]
        }
        """
    )
    extractor = HealthFactExtractor(llm_client=llm)

    facts = extractor.extract(
        document_id="doc_1",
        member_id="mem_1",
        pages=[_page("尿酸 402 208-428 μmol/L 正常高值。总胆固醇 5.9 <5.2 mmol/L 偏高")],
        chunks=[_chunk("尿酸 402 208-428 μmol/L 正常高值。总胆固醇 5.9 <5.2 mmol/L 偏高")],
    )

    assert [fact.name for fact in facts] == ["总胆固醇"]


def test_llm_extractor_raises_when_llm_returns_invalid_fact_type():
    llm = FakeLlmClient(
        """
        {
          "facts": [
            {
              "fact_type": "recheck",
              "name": "复查血脂",
              "value": null,
              "unit": null,
              "reference_range": null,
              "status": "warning",
              "source_page_no": 1,
              "evidence_text": "建议三个月后复查血脂"
            }
          ]
        }
        """
    )
    extractor = HealthFactExtractor(llm_client=llm)

    with pytest.raises(ValueError):
        extractor.extract(
            document_id="doc_1",
            member_id="mem_1",
            pages=[_page("建议三个月后复查血脂")],
            chunks=[_chunk("建议三个月后复查血脂")],
        )


def test_llm_extractor_leaves_source_chunk_empty_when_match_is_weak():
    llm = FakeLlmClient(
        """
        {
          "facts": [
            {
              "fact_type": "risk",
              "name": "骨密度低",
              "value": null,
              "unit": null,
              "reference_range": null,
              "status": "warning",
              "source_page_no": 1,
              "evidence_text": "骨密度 T 值 -2.1，提示骨量减少"
            }
          ]
        }
        """
    )
    extractor = HealthFactExtractor(llm_client=llm)

    facts = extractor.extract(
        document_id="doc_1",
        member_id="mem_1",
        pages=[_page("骨密度 T 值 -2.1，提示骨量减少")],
        chunks=[_chunk("完全无关的文本", chunk_id="chunk_1")],
    )

    assert len(facts) == 1
    assert facts[0].source_chunk_id is None


def test_manual_pdf_health_fact_extraction_prints_result():
    pdf_path = os.getenv("HEALTH_FACT_TEST_PDF_PATH", "/Users/tiger/Downloads/体检报告体检/张志远-体检报告.pdf")
    if not pdf_path:
        pytest.skip("Set HEALTH_FACT_TEST_PDF_PATH=/path/to/report.pdf to run manual PDF extraction")

    path = Path(pdf_path).expanduser()
    if not path.exists():
        pytest.skip("Set HEALTH_FACT_TEST_PDF_PATH=/path/to/report.pdf to run manual PDF extraction")
    assert path.suffix.lower() == ".pdf"

    pages_text = PdfExtractor().extract_pages(path)
    pages = [
        PageCreate(document_id="manual_doc", page_no=index + 1, text_content=text)
        for index, text in enumerate(pages_text)
    ]
    chunks: list[TextChunk] = []
    for page in pages:
        chunks.extend(
            chunk_page_text(
                document_id="manual_doc",
                member_id="manual_member",
                page_no=page.page_no,
                text=page.text_content,
            )
        )

    facts = HealthFactExtractor().extract(
        document_id="manual_doc",
        member_id="manual_member",
        pages=pages,
        chunks=chunks,
    )

    output = [
        {
            "fact_type": fact.fact_type,
            "name": fact.name,
            "value": fact.value,
            "unit": fact.unit,
            "reference_range": fact.reference_range,
            "status": fact.status,
            "source_page_no": fact.source_page_no,
            "source_chunk_id": fact.source_chunk_id,
            "evidence_text": fact.evidence_text,
        }
        for fact in facts
    ]
    print(json.dumps(output, ensure_ascii=False, indent=2))

    assert isinstance(output, list)
