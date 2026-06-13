from dataclasses import dataclass
from datetime import date
import re


@dataclass(frozen=True)
class BasicMetadata:
    title: str | None = None
    patient_name: str | None = None
    exam_date: date | None = None
    institution: str | None = None


def extract_basic_metadata(text: str) -> BasicMetadata:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    return BasicMetadata(
        title=_find_title(lines),
        patient_name=_find_named_value(text, ("姓名", "患者姓名", "Name", "Patient Name")),
        exam_date=_find_date(text),
        institution=_find_named_value(text, ("检查机构", "体检机构", "医院", "Institution", "Hospital")),
    )


def _find_title(lines: list[str]) -> str | None:
    for line in lines[:5]:
        if "报告" in line and len(line) <= 40:
            return line
    return lines[0] if lines else None


def _find_named_value(text: str, labels: tuple[str, ...]) -> str | None:
    for label in labels:
        pattern = rf"{label}\s*[:：]\s*([^\s，,。；;]+)"
        match = re.search(pattern, text)
        if match:
            return match.group(1).strip()
    return None


def _find_date(text: str) -> date | None:
    match = re.search(r"(20\d{2})[-/.年](\d{1,2})[-/.月](\d{1,2})日?", text)
    if not match:
        return None
    year, month, day = (int(part) for part in match.groups())
    try:
        return date(year, month, day)
    except ValueError:
        return None
