from datetime import date

from app.services.metadata import extract_basic_metadata


def test_extract_basic_metadata_from_report_text():
    text = """
    市立医院体检报告
    姓名：王秀英
    检查日期：2026-05-12
    检查机构：市立医院
    骨密度 T 值 -2.1
    """

    metadata = extract_basic_metadata(text)

    assert metadata.title == "市立医院体检报告"
    assert metadata.patient_name == "王秀英"
    assert metadata.exam_date == date(2026, 5, 12)
    assert metadata.institution == "市立医院"


def test_extract_basic_metadata_from_english_labels():
    text = """
    General Check Report
    Name: WangXiuying
    Exam Date: 2026-05-12
    Institution: CityHospital
    """

    metadata = extract_basic_metadata(text)

    assert metadata.title == "General Check Report"
    assert metadata.patient_name == "WangXiuying"
    assert metadata.exam_date == date(2026, 5, 12)
    assert metadata.institution == "CityHospital"
