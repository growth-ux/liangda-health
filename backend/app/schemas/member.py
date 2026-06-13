import json
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, computed_field


def _safe_tags(raw: str | None) -> list[str]:
    if not raw:
        return []
    try:
        value = json.loads(raw)
    except json.JSONDecodeError:
        return []
    if not isinstance(value, list):
        return []
    return [str(item) for item in value]


class MemberDocumentItem(BaseModel):
    document_id: str
    file_name: str
    exam_date: datetime | None = None
    status: str

    model_config = ConfigDict(from_attributes=True)


class MemberCreateRequest(BaseModel):
    name: str
    relation: str
    gender: str
    birth_year: int
    phone: str | None = None
    height_cm: int | None = None
    weight_kg: int | None = None
    health_tags: list[str] = Field(default_factory=list)
    allergies: str | None = None
    taste_preferences: str | None = None


class MemberUpdateRequest(MemberCreateRequest):
    pass


class MemberListItem(BaseModel):
    member_id: str
    name: str
    relation: str
    gender: str
    birth_year: int
    phone: str | None = None
    height_cm: int | None = None
    weight_kg: int | None = None
    allergies: str | None = None
    taste_preferences: str | None = None
    created_at: datetime
    updated_at: datetime
    report_count: int = 0
    recent_documents: list[MemberDocumentItem] = Field(default_factory=list)
    health_tags_raw: str | None = None

    model_config = ConfigDict(from_attributes=True)

    @computed_field
    @property
    def age(self) -> int:
        return max(0, datetime.now().year - self.birth_year)

    @computed_field
    @property
    def health_tags(self) -> list[str]:
        return _safe_tags(self.health_tags_raw)


class MemberDetail(BaseModel):
    member_id: str
    name: str
    relation: str
    gender: str
    birth_year: int
    phone: str | None = None
    height_cm: int | None = None
    weight_kg: int | None = None
    allergies: str | None = None
    taste_preferences: str | None = None
    created_at: datetime
    updated_at: datetime
    health_tags_raw: str | None = None

    model_config = ConfigDict(from_attributes=True)

    @computed_field
    @property
    def age(self) -> int:
        return max(0, datetime.now().year - self.birth_year)

    @computed_field
    @property
    def bmi(self) -> float | None:
        if not self.height_cm or not self.weight_kg or self.height_cm <= 0:
            return None
        bmi = self.weight_kg / ((self.height_cm / 100) ** 2)
        return round(bmi, 1)

    @computed_field
    @property
    def health_tags(self) -> list[str]:
        return _safe_tags(self.health_tags_raw)
