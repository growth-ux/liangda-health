# Health Analysis Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现健康分析页第一版，使用成员资料、报告数量、设备近 7 天数据和健康标签生成家庭健康分析。

**Architecture:** 后端新增 `health_analysis` API / schema / service，复用现有 members、kb_documents、device_daily_metrics 和 device service，不新增数据库表。前端新增 `/report` 页面，通过一个 React Query 请求获取完整页面数据，并按 `prd/prototype/report.html` 展示指标卡、摘要、异常 Top 5 和成员健康卡。

**Tech Stack:** FastAPI, SQLAlchemy, Pydantic, pytest, React 19, React Router, TanStack Query, TypeScript, Vite

---

## File Structure

- Create `backend/app/schemas/health_analysis.py`：定义健康分析接口返回模型。
- Create `backend/app/services/health_analysis_service.py`：聚合成员、报告、设备数据，计算健康分、异常项和摘要。
- Create `backend/app/api/health_analysis.py`：暴露 `GET /api/health-analysis/overview`。
- Modify `backend/app/main.py`：注册 health analysis router。
- Create `backend/tests/test_api_health_analysis.py`：覆盖 API 关键行为。
- Create `frontend/src/api/healthAnalysis.ts`：定义前端类型与请求函数。
- Create `frontend/src/pages/HealthAnalysisPage.tsx`：实现健康分析页面。
- Modify `frontend/src/main.tsx`：注册 `/report` 路由。
- Modify `frontend/src/components/AppShell.tsx`：健康分析导航跳转到 `/report`。
- Modify `frontend/src/styles.css`：补齐健康分析页面样式。

---

### Task 1: 写后端健康分析 API 失败测试

**Files:**
- Create: `backend/tests/test_api_health_analysis.py`

- [ ] **Step 1: 写测试文件**

```python
from datetime import datetime

from fastapi.testclient import TestClient
from sqlalchemy import text

from app.db.session import get_db
from app.main import create_app


def create_member(client: TestClient, payload: dict) -> str:
    response = client.post("/api/members", json=payload)
    assert response.status_code == 200
    return response.json()["member_id"]


def insert_ready_document(db_session, member_id: str, document_id: str = "doc_health_1") -> None:
    db_session.execute(
        text(
            """
            INSERT INTO kb_documents (
                document_id, file_name, file_path, file_size, page_count,
                status, created_at, updated_at, member_id
            ) VALUES (
                :document_id, 'report.pdf', '/tmp/report.pdf', 10, 1,
                'ready', NOW(), NOW(), :member_id
            )
            """
        ),
        {"document_id": document_id, "member_id": member_id},
    )
    db_session.commit()


def test_health_analysis_overview_returns_family_metrics(db_session):
    app = create_app()
    app.dependency_overrides[get_db] = lambda: db_session
    with TestClient(app) as client:
        mother_id = create_member(
            client,
            {
                "name": "王秀英",
                "relation": "母亲",
                "gender": "女",
                "birth_year": 1961,
                "height_cm": 158,
                "weight_kg": 70,
                "health_tags": ["高血压", "骨质疏松"],
            },
        )
        create_member(
            client,
            {
                "name": "张雨微",
                "relation": "本人",
                "gender": "女",
                "birth_year": 1994,
                "height_cm": 165,
                "weight_kg": 54,
                "health_tags": [],
            },
        )
        insert_ready_document(db_session, mother_id)

        response = client.get("/api/health-analysis/overview")

    assert response.status_code == 200
    payload = response.json()
    assert payload["family"]["name"] == "张雨微的家庭"
    assert payload["family"]["period_label"] == datetime.now().strftime("%Y-%m")
    assert 0 <= payload["metrics"]["family_score"] <= 100
    assert payload["metrics"]["report_count"] == 1
    assert payload["metrics"]["device_count"] == 2
    assert payload["metrics"]["attention_count"] >= 1
    assert len(payload["summary"]) >= 1
    assert len(payload["abnormal_items"]) <= 5
    assert len(payload["member_cards"]) == 2


def test_health_analysis_high_blood_pressure_enters_top_items(db_session):
    app = create_app()
    app.dependency_overrides[get_db] = lambda: db_session
    with TestClient(app) as client:
        member_id = create_member(
            client,
            {
                "name": "王秀英",
                "relation": "母亲",
                "gender": "女",
                "birth_year": 1961,
                "height_cm": 158,
                "weight_kg": 70,
                "health_tags": ["高血压"],
            },
        )

        response = client.get("/api/health-analysis/overview")

    assert response.status_code == 200
    payload = response.json()
    labels = [(item["member_id"], item["metric"]) for item in payload["abnormal_items"]]
    assert any(item[0] == member_id and item[1] in {"收缩压", "舒张压", "高血压"} for item in labels)
    assert payload["member_cards"][0]["health_score"] < 100


def test_health_analysis_no_members_returns_empty_overview(db_session):
    app = create_app()
    app.dependency_overrides[get_db] = lambda: db_session
    with TestClient(app) as client:
        response = client.get("/api/health-analysis/overview")

    assert response.status_code == 200
    payload = response.json()
    assert payload["metrics"] == {
        "family_score": 0,
        "family_score_delta": 0,
        "attention_count": 0,
        "report_count": 0,
        "device_count": 0,
    }
    assert payload["summary"] == []
    assert payload["abnormal_items"] == []
    assert payload["member_cards"] == []
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd backend && pytest tests/test_api_health_analysis.py -v`

Expected: FAIL，原因是 `health_analysis` 路由或 schema 不存在。

---

### Task 2: 新增后端 schema

**Files:**
- Create: `backend/app/schemas/health_analysis.py`

- [ ] **Step 1: 创建健康分析 schema**

```python
from typing import Literal

from pydantic import BaseModel, Field


HealthLevel = Literal["danger", "warning", "success", "info"]


class HealthAnalysisFamily(BaseModel):
    name: str
    period_label: str


class HealthAnalysisMetrics(BaseModel):
    family_score: int
    family_score_delta: int
    attention_count: int
    report_count: int
    device_count: int


class HealthAnalysisSummaryItem(BaseModel):
    level: HealthLevel
    text: str


class HealthAnalysisAbnormalItem(BaseModel):
    metric: str
    member_id: str
    member_name: str
    member_relation: str
    current_value: str
    status: Literal["danger", "warning"]
    status_text: str
    trend_text: str
    suggestion: str
    score_impact: int = Field(exclude=True)


class HealthAnalysisMemberCard(BaseModel):
    member_id: str
    name: str
    relation: str
    age: int
    health_score: int
    status: Literal["success", "warning", "danger"]
    status_text: str
    avatar_text: str


class HealthAnalysisOverviewResponse(BaseModel):
    family: HealthAnalysisFamily
    metrics: HealthAnalysisMetrics
    summary: list[HealthAnalysisSummaryItem]
    abnormal_items: list[HealthAnalysisAbnormalItem]
    member_cards: list[HealthAnalysisMemberCard]
```

- [ ] **Step 2: 运行测试确认仍失败但 schema 可导入**

Run: `cd backend && pytest tests/test_api_health_analysis.py -v`

Expected: FAIL，原因是路由尚未实现，而不是 schema 导入错误。

---

### Task 3: 实现 HealthAnalysisService

**Files:**
- Create: `backend/app/services/health_analysis_service.py`

- [ ] **Step 1: 创建 service 基础结构和 helper**

```python
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, datetime, timedelta

from sqlalchemy.orm import Session

from app.models.device import DeviceDailyMetric
from app.models.kb import KbDocument
from app.models.member import Member
from app.repositories.device_repository import SqlAlchemyDeviceRepository
from app.repositories.member_repository import SqlAlchemyMemberRepository
from app.schemas.health_analysis import (
    HealthAnalysisAbnormalItem,
    HealthAnalysisFamily,
    HealthAnalysisMemberCard,
    HealthAnalysisMetrics,
    HealthAnalysisOverviewResponse,
    HealthAnalysisSummaryItem,
)
from app.services.device_service import DeviceService


@dataclass(frozen=True)
class MemberAnalysis:
    member: Member
    age: int
    health_tags: list[str]
    report_count: int
    metrics: list[DeviceDailyMetric]
    score: int
    abnormalities: list[HealthAnalysisAbnormalItem]


class HealthAnalysisService:
    def __init__(self, db: Session):
        self.db = db
        self.member_repository = SqlAlchemyMemberRepository(db)
        self.device_repository = SqlAlchemyDeviceRepository(db)
        self.device_service = DeviceService(db)

    def get_overview(self, range_value: str = "this_month") -> HealthAnalysisOverviewResponse:
        members = self.member_repository.list_members()
        if not members:
            return self._empty_overview(range_value)

        analyses = [self._analyze_member(member.member_id) for member in members]
        all_abnormalities = [item for analysis in analyses for item in analysis.abnormalities]
        top_items = sorted(
            all_abnormalities,
            key=lambda item: (0 if item.status == "danger" else 1, -item.score_impact),
        )[:5]
        family_score = round(sum(item.score for item in analyses) / len(analyses))
        attention_count = len(all_abnormalities)
        report_count = sum(item.report_count for item in analyses)
        device_count = sum(1 for item in analyses if self.device_repository.get_binding(item.member.member_id) is not None)

        return HealthAnalysisOverviewResponse(
            family=HealthAnalysisFamily(
                name=self._family_name(analyses),
                period_label=self._period_label(range_value),
            ),
            metrics=HealthAnalysisMetrics(
                family_score=family_score,
                family_score_delta=self._score_delta(attention_count),
                attention_count=attention_count,
                report_count=report_count,
                device_count=device_count,
            ),
            summary=self._build_summary(analyses, all_abnormalities),
            abnormal_items=top_items,
            member_cards=[self._member_card(item) for item in analyses],
        )
```

- [ ] **Step 2: 补齐成员分析逻辑**

```python
    def _analyze_member(self, member_id: str) -> MemberAnalysis:
        member = self.member_repository.get_member(member_id)
        if member is None:
            raise ValueError("member not found")

        self.device_service.ensure_recent_7_days(member.member_id)
        metrics = self.device_repository.list_metrics_for_dates(member.member_id, self._recent_7_days())
        health_tags = self._safe_tags(member.health_tags)
        report_count = self._count_reports(member.member_id)
        age = max(0, datetime.now().year - member.birth_year)
        abnormalities = self._build_abnormalities(member, health_tags, metrics, report_count)
        score = max(0, min(100, 100 - sum(item.score_impact for item in abnormalities)))

        return MemberAnalysis(
            member=member,
            age=age,
            health_tags=health_tags,
            report_count=report_count,
            metrics=metrics,
            score=score,
            abnormalities=abnormalities,
        )

    def _build_abnormalities(
        self,
        member: Member,
        health_tags: list[str],
        metrics: list[DeviceDailyMetric],
        report_count: int,
    ) -> list[HealthAnalysisAbnormalItem]:
        items: list[HealthAnalysisAbnormalItem] = []
        averages = self._metric_averages(metrics)

        if report_count == 0:
            items.append(self._abnormal(member, "体检报告", "0 份", "warning", "缺失", "暂无近期报告", "建议上传近期体检报告", 6))

        tag_rules = {
            "高血压": ("高血压", "已标记", "warning", "风险提示", "长期关注", "建议保持低钠饮食并定期测量血压", 4),
            "糖尿病": ("糖尿病", "已标记", "warning", "风险提示", "长期关注", "建议控制精制碳水摄入并记录空腹血糖", 4),
            "高血脂": ("高血脂", "已标记", "warning", "风险提示", "长期关注", "建议减少高油脂食品摄入", 4),
            "骨质疏松": ("骨质疏松", "已标记", "warning", "风险提示", "长期关注", "建议补充钙和维生素 D，并增加日晒", 4),
            "超重": ("超重", "已标记", "warning", "风险提示", "长期关注", "建议控制总热量并增加步行", 4),
            "痛风": ("痛风", "已标记", "warning", "风险提示", "长期关注", "建议减少高嘌呤食品摄入", 4),
            "心血管": ("心血管风险", "已标记", "warning", "风险提示", "长期关注", "建议关注心率、血压并按时复查", 4),
            "胃肠": ("胃肠问题", "已标记", "warning", "风险提示", "长期关注", "建议饮食规律并减少刺激性食物", 4),
        }
        tag_penalty = 0
        for tag in health_tags:
            for keyword, rule in tag_rules.items():
                if keyword in tag and tag_penalty < 20:
                    metric, value, status, status_text, trend, suggestion, impact = rule
                    items.append(self._abnormal(member, metric, value, status, status_text, trend, suggestion, impact))
                    tag_penalty += impact
                    break

        systolic = averages.get("systolic_bp")
        if systolic is not None and systolic >= 140:
            items.append(self._abnormal(member, "收缩压", f"{round(systolic)} mmHg", "danger", "偏高", "持续偏高", "建议减少高钠饮食，并安排血压复查", 12))
        elif systolic is not None and systolic >= 130:
            items.append(self._abnormal(member, "收缩压", f"{round(systolic)} mmHg", "warning", "偏高", "略高", "建议继续观察血压变化", 6))

        diastolic = averages.get("diastolic_bp")
        if diastolic is not None and diastolic >= 90:
            items.append(self._abnormal(member, "舒张压", f"{round(diastolic)} mmHg", "danger", "偏高", "持续偏高", "建议规律测量并咨询医生", 10))
        elif diastolic is not None and diastolic >= 85:
            items.append(self._abnormal(member, "舒张压", f"{round(diastolic)} mmHg", "warning", "偏高", "略高", "建议继续观察血压变化", 5))

        sleep = averages.get("sleep_hours")
        if sleep is not None and sleep < 6:
            items.append(self._abnormal(member, "睡眠时长", f"{sleep:.1f} h/天", "danger", "不足", "持续偏低", "建议提前入睡并减少睡前屏幕时间", 8))
        elif sleep is not None and sleep <= 6.5:
            items.append(self._abnormal(member, "睡眠时长", f"{sleep:.1f} h/天", "warning", "偏少", "略低", "建议保持规律作息", 4))

        steps = averages.get("steps")
        if steps is not None and steps < 4000:
            items.append(self._abnormal(member, "步数", f"{round(steps)} 步/天", "warning", "偏少", "活动不足", "建议每天增加 20 分钟步行", 6))
        elif steps is not None and steps < 6000:
            items.append(self._abnormal(member, "步数", f"{round(steps)} 步/天", "warning", "偏少", "略低", "建议适度增加日常活动", 3))

        oxygen = averages.get("blood_oxygen")
        if oxygen is not None and oxygen < 95:
            items.append(self._abnormal(member, "血氧", f"{round(oxygen)}%", "danger", "偏低", "低于建议值", "建议复测血氧并关注呼吸状态", 10))

        bmi = self._bmi(member)
        if bmi is not None and bmi >= 28:
            items.append(self._abnormal(member, "BMI", f"{bmi:.1f}", "danger", "肥胖", "偏高", "建议控制总热量并增加运动", 8))
        elif bmi is not None and bmi >= 24:
            items.append(self._abnormal(member, "BMI", f"{bmi:.1f}", "warning", "偏高", "偏高", "建议控制主食和油脂摄入", 4))

        return items
```

- [ ] **Step 3: 补齐汇总、摘要和工具方法**

```python
    def _build_summary(
        self,
        analyses: list[MemberAnalysis],
        abnormalities: list[HealthAnalysisAbnormalItem],
    ) -> list[HealthAnalysisSummaryItem]:
        if not analyses:
            return []

        summary: list[HealthAnalysisSummaryItem] = []
        top = sorted(abnormalities, key=lambda item: (0 if item.status == "danger" else 1, -item.score_impact))
        if top:
            item = top[0]
            summary.append(HealthAnalysisSummaryItem(level=item.status, text=f"关注：{item.member_name}{item.metric}{item.status_text}，当前 {item.current_value}"))

        best = max(analyses, key=lambda item: item.score)
        summary.append(HealthAnalysisSummaryItem(level="success", text=f"稳定：{best.member.name}近期整体指标较平稳，健康分 {best.score}"))

        missing_report = next((item for item in analyses if item.report_count == 0), None)
        if missing_report is not None:
            summary.append(HealthAnalysisSummaryItem(level="warning", text=f"提醒：{missing_report.member.name}暂无已存报告，建议上传近期体检报告"))

        if top:
            summary.append(HealthAnalysisSummaryItem(level="info", text=f"建议：{top[0].suggestion}"))

        return summary[:4]

    def _member_card(self, analysis: MemberAnalysis) -> HealthAnalysisMemberCard:
        warning_count = len(analysis.abnormalities)
        if analysis.score < 70 or any(item.status == "danger" for item in analysis.abnormalities):
            status = "danger"
        elif warning_count > 0:
            status = "warning"
        else:
            status = "success"
        status_text = "健康" if warning_count == 0 else f"{warning_count}项待关注"

        return HealthAnalysisMemberCard(
            member_id=analysis.member.member_id,
            name=analysis.member.name,
            relation=analysis.member.relation,
            age=analysis.age,
            health_score=analysis.score,
            status=status,
            status_text=status_text,
            avatar_text=analysis.member.name[:1],
        )

    def _abnormal(
        self,
        member: Member,
        metric: str,
        current_value: str,
        status: str,
        status_text: str,
        trend_text: str,
        suggestion: str,
        score_impact: int,
    ) -> HealthAnalysisAbnormalItem:
        return HealthAnalysisAbnormalItem(
            metric=metric,
            member_id=member.member_id,
            member_name=member.name,
            member_relation=member.relation,
            current_value=current_value,
            status=status,
            status_text=status_text,
            trend_text=trend_text,
            suggestion=suggestion,
            score_impact=score_impact,
        )

    def _empty_overview(self, range_value: str) -> HealthAnalysisOverviewResponse:
        return HealthAnalysisOverviewResponse(
            family=HealthAnalysisFamily(name="张雨微的家庭", period_label=self._period_label(range_value)),
            metrics=HealthAnalysisMetrics(
                family_score=0,
                family_score_delta=0,
                attention_count=0,
                report_count=0,
                device_count=0,
            ),
            summary=[],
            abnormal_items=[],
            member_cards=[],
        )

    def _count_reports(self, member_id: str) -> int:
        return (
            self.db.query(KbDocument)
            .filter(KbDocument.member_id == member_id, KbDocument.status == "ready")
            .count()
        )

    @staticmethod
    def _metric_averages(metrics: list[DeviceDailyMetric]) -> dict[str, float]:
        if not metrics:
            return {}
        fields = ("steps", "avg_heart_rate", "systolic_bp", "diastolic_bp", "sleep_hours", "blood_oxygen")
        return {
            field: sum(float(getattr(metric, field)) for metric in metrics) / len(metrics)
            for field in fields
        }

    @staticmethod
    def _recent_7_days() -> list[date]:
        return [date.today() - timedelta(days=offset) for offset in range(6, -1, -1)]

    @staticmethod
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

    @staticmethod
    def _bmi(member: Member) -> float | None:
        if not member.height_cm or not member.weight_kg or member.height_cm <= 0:
            return None
        return round(member.weight_kg / ((member.height_cm / 100) ** 2), 1)

    @staticmethod
    def _family_name(analyses: list[MemberAnalysis]) -> str:
        owner = next((item.member for item in analyses if item.member.relation in {"本人", "我"}), None)
        if owner is None:
            owner = analyses[0].member
        return f"{owner.name}的家庭"

    @staticmethod
    def _period_label(range_value: str) -> str:
        if range_value == "last_3_months":
            return "近 3 月"
        if range_value == "last_6_months":
            return "近 6 月"
        if range_value == "last_12_months":
            return "近 1 年"
        return datetime.now().strftime("%Y-%m")

    @staticmethod
    def _score_delta(attention_count: int) -> int:
        if attention_count >= 4:
            return -3
        if attention_count > 0:
            return 0
        return 2
```

- [ ] **Step 4: 运行测试确认仍失败在路由**

Run: `cd backend && pytest tests/test_api_health_analysis.py -v`

Expected: FAIL，原因是 `/api/health-analysis/overview` 尚未注册。

---

### Task 4: 新增 API 并注册 router

**Files:**
- Create: `backend/app/api/health_analysis.py`
- Modify: `backend/app/main.py`

- [ ] **Step 1: 创建 API 文件**

```python
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.health_analysis import HealthAnalysisOverviewResponse
from app.services.health_analysis_service import HealthAnalysisService

router = APIRouter(prefix="/api/health-analysis", tags=["health-analysis"])


@router.get("/overview", response_model=HealthAnalysisOverviewResponse)
def get_health_analysis_overview(
    range: str = Query(default="this_month", pattern="^(this_month|last_3_months|last_6_months|last_12_months)$"),
    db: Session = Depends(get_db),
):
    return HealthAnalysisService(db).get_overview(range)
```

- [ ] **Step 2: 在 `backend/app/main.py` 注册 router**

在 import 区加入：

```python
from app.api.health_analysis import router as health_analysis_router
```

在 `create_app()` 中 `app.include_router(device_router)` 附近加入：

```python
    app.include_router(health_analysis_router)
```

- [ ] **Step 3: 运行健康分析测试**

Run: `cd backend && pytest tests/test_api_health_analysis.py -v`

Expected: PASS。

- [ ] **Step 4: 运行相关后端回归测试**

Run: `cd backend && pytest tests/test_api_health_analysis.py tests/test_api_device.py tests/test_api_members.py -v`

Expected: PASS。

- [ ] **Step 5: Commit 后端实现**

```bash
git add backend/app/api/health_analysis.py backend/app/main.py backend/app/schemas/health_analysis.py backend/app/services/health_analysis_service.py backend/tests/test_api_health_analysis.py
git commit -m "feat: add health analysis overview api"
```

如果当前环境仍无法写 `.git/index.lock`，记录为环境权限问题，不要强行处理 `.git`。

---

### Task 5: 新增前端健康分析 API

**Files:**
- Create: `frontend/src/api/healthAnalysis.ts`

- [ ] **Step 1: 创建 API 类型和请求函数**

```ts
const API_BASE = import.meta.env.VITE_API_BASE ?? '';

export type HealthAnalysisRange = 'this_month' | 'last_3_months' | 'last_6_months' | 'last_12_months';

export type HealthAnalysisOverview = {
  family: {
    name: string;
    period_label: string;
  };
  metrics: {
    family_score: number;
    family_score_delta: number;
    attention_count: number;
    report_count: number;
    device_count: number;
  };
  summary: {
    level: 'danger' | 'warning' | 'success' | 'info';
    text: string;
  }[];
  abnormal_items: {
    metric: string;
    member_id: string;
    member_name: string;
    member_relation: string;
    current_value: string;
    status: 'danger' | 'warning';
    status_text: string;
    trend_text: string;
    suggestion: string;
  }[];
  member_cards: {
    member_id: string;
    name: string;
    relation: string;
    age: number;
    health_score: number;
    status: 'success' | 'warning' | 'danger';
    status_text: string;
    avatar_text: string;
  }[];
};

async function readJson<T>(response: Response, fallback: string): Promise<T> {
  const contentType = response.headers.get('content-type') ?? '';
  if (!contentType.includes('application/json')) {
    throw new Error(fallback);
  }
  if (!response.ok) {
    const detail = await response.json().catch(() => null);
    throw new Error(detail?.detail ?? fallback);
  }
  return response.json();
}

export async function getHealthAnalysisOverview(range: HealthAnalysisRange): Promise<HealthAnalysisOverview> {
  const params = new URLSearchParams({ range });
  const response = await fetch(`${API_BASE}/api/health-analysis/overview?${params.toString()}`);
  return readJson<HealthAnalysisOverview>(response, '获取健康分析失败');
}
```

- [ ] **Step 2: 运行 TypeScript 构建确认当前页面未接入**

Run: `cd frontend && npm run build`

Expected: PASS。

---

### Task 6: 新增 HealthAnalysisPage

**Files:**
- Create: `frontend/src/pages/HealthAnalysisPage.tsx`

- [ ] **Step 1: 创建页面组件**

```tsx
import { useMemo, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Download, ExternalLink } from 'lucide-react';
import { Link, useNavigate } from 'react-router-dom';
import {
  getHealthAnalysisOverview,
  type HealthAnalysisOverview,
  type HealthAnalysisRange
} from '../api/healthAnalysis';
import { AppShell } from '../components/AppShell';

const rangeOptions: { value: HealthAnalysisRange; label: string }[] = [
  { value: 'this_month', label: '本月' },
  { value: 'last_3_months', label: '近 3 月' },
  { value: 'last_6_months', label: '近 6 月' },
  { value: 'last_12_months', label: '近 1 年' }
];

function metricTrend(delta: number): string {
  if (delta > 0) return `↑ ${delta} 较上月`;
  if (delta < 0) return `↓ ${Math.abs(delta)} 较上月`;
  return '较上月持平';
}

function statusClass(status: 'success' | 'warning' | 'danger'): string {
  if (status === 'danger') return 'tag tag-danger';
  if (status === 'warning') return 'tag tag-warning';
  return 'tag tag-success';
}

function summaryClass(level: HealthAnalysisOverview['summary'][number]['level']): string {
  return `health-summary-${level}`;
}

export function HealthAnalysisPage() {
  const navigate = useNavigate();
  const [range, setRange] = useState<HealthAnalysisRange>('this_month');
  const overviewQuery = useQuery({
    queryKey: ['health-analysis', range],
    queryFn: () => getHealthAnalysisOverview(range)
  });

  const overview = overviewQuery.data;
  const hasMembers = (overview?.member_cards.length ?? 0) > 0;

  const rows = useMemo(() => overview?.abnormal_items ?? [], [overview]);

  return (
    <AppShell title="家庭健康分析" activeId="report">
      <div className="health-analysis-head">
        <div>
          <div className="health-analysis-family">{overview?.family.name ?? '张雨微的家庭'}</div>
          <div className="health-analysis-title">
            健康分析
            <span>· {overview?.family.period_label ?? '-'}</span>
          </div>
        </div>
        <div className="health-analysis-actions">
          <select
            className="form-select health-analysis-range"
            value={range}
            onChange={(event) => setRange(event.target.value as HealthAnalysisRange)}
          >
            {rangeOptions.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
          <button className="btn-secondary" type="button">
            <Download size={16} />
            导出
          </button>
        </div>
      </div>

      {overviewQuery.isLoading && <div className="empty-state">正在加载健康分析...</div>}
      {overviewQuery.isError && <div className="error-box">健康分析加载失败</div>}

      {!overviewQuery.isLoading && !overviewQuery.isError && overview && !hasMembers && (
        <div className="empty-state">
          暂无家人档案，请先到<Link to="/members">家人页面</Link>创建档案。
        </div>
      )}

      {!overviewQuery.isLoading && !overviewQuery.isError && overview && hasMembers && (
        <>
          <div className="health-metric-grid">
            <div className="health-metric">
              <div className="health-metric-label">家庭综合分</div>
              <div className="health-metric-value">{overview.metrics.family_score}</div>
              <div className="health-metric-trend">{metricTrend(overview.metrics.family_score_delta)}</div>
            </div>
            <div className="health-metric">
              <div className="health-metric-label">待关注指标</div>
              <div className="health-metric-value danger">{overview.metrics.attention_count}</div>
              <div className="health-metric-trend">项需干预</div>
            </div>
            <div className="health-metric">
              <div className="health-metric-label">已存报告</div>
              <div className="health-metric-value">{overview.metrics.report_count}</div>
              <div className="health-metric-trend">份</div>
            </div>
            <div className="health-metric">
              <div className="health-metric-label">已绑设备</div>
              <div className="health-metric-value primary">{overview.metrics.device_count}</div>
              <div className="health-metric-trend">只手环</div>
            </div>
          </div>

          <section className="health-summary-card">
            <div className="card-title">本周家庭健康摘要（Agent 生成）</div>
            <ul>
              {overview.summary.map((item) => (
                <li key={item.text} className={summaryClass(item.level)}>
                  {item.text}
                </li>
              ))}
            </ul>
          </section>

          <section className="card">
            <div className="card-title">异常指标 Top 5</div>
            <table className="table">
              <thead>
                <tr>
                  <th>指标</th>
                  <th>家人</th>
                  <th>当前值</th>
                  <th>状态</th>
                  <th>趋势</th>
                  <th>建议</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((item) => (
                  <tr key={`${item.member_id}-${item.metric}-${item.current_value}`}>
                    <td>{item.metric}</td>
                    <td>{item.member_name}（{item.member_relation}）</td>
                    <td>{item.current_value}</td>
                    <td><span className={statusClass(item.status)}>{item.status_text}</span></td>
                    <td>{item.trend_text}</td>
                    <td>
                      <button
                        className="health-link-button"
                        onClick={() => navigate(`/chat?prompt=${encodeURIComponent(`请根据${item.member_name}的${item.metric}问题给出家庭健康建议：${item.suggestion}`)}`)}
                        type="button"
                      >
                        看建议
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </section>

          <section className="card">
            <div className="card-title">各成员健康卡</div>
            <div className="health-member-grid">
              {overview.member_cards.map((member) => (
                <button
                  className="health-member-card"
                  key={member.member_id}
                  onClick={() => navigate(`/members/${member.member_id}`)}
                  type="button"
                >
                  <div className="health-member-avatar">{member.avatar_text}</div>
                  <div className="health-member-info">
                    <div className="health-member-name">
                      <span>{member.relation} ·</span>
                      {member.name}
                      <span className={statusClass(member.status)}>{member.status_text}</span>
                    </div>
                    <div className="health-member-meta">{member.age}岁 · 健康分 {member.health_score}</div>
                  </div>
                  <ExternalLink size={16} />
                </button>
              ))}
            </div>
          </section>
        </>
      )}
    </AppShell>
  );
}
```

- [ ] **Step 2: 运行构建确认失败点**

Run: `cd frontend && npm run build`

Expected: FAIL，原因是页面尚未注册或样式类不存在不影响构建；如果 TypeScript 报错，按报错修正类型。

---

### Task 7: 注册路由和导航

**Files:**
- Modify: `frontend/src/main.tsx`
- Modify: `frontend/src/components/AppShell.tsx`

- [ ] **Step 1: 在 `frontend/src/main.tsx` 引入并注册页面**

加入 import：

```tsx
import { HealthAnalysisPage } from './pages/HealthAnalysisPage';
```

在 Routes 中加入：

```tsx
<Route path="/report" element={<HealthAnalysisPage />} />
```

- [ ] **Step 2: 修改 `AppShell` 健康分析导航**

把：

```tsx
{ id: 'report', icon: BarChart3, label: '健康分析', href: '' },
```

改为：

```tsx
{ id: 'report', icon: BarChart3, label: '健康分析', href: '/report' },
```

- [ ] **Step 3: 运行前端构建**

Run: `cd frontend && npm run build`

Expected: PASS。如果失败，按 TypeScript 报错修正 Task 6 页面代码。

---

### Task 8: 补齐页面样式

**Files:**
- Modify: `frontend/src/styles.css`

- [ ] **Step 1: 在 `.tag-info` 附近补充 danger tag**

```css
.tag-danger {
  color: #dc2626;
  background: #fef2f2;
}
```

- [ ] **Step 2: 在文件末尾加入健康分析样式**

```css
/* ===== Health Analysis ===== */

.health-analysis-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 16px;
  margin-bottom: 16px;
}

.health-analysis-family {
  font-size: 13px;
  color: #9ca3af;
}

.health-analysis-title {
  margin-top: 4px;
  color: #111827;
  font-size: 22px;
  font-weight: 700;
}

.health-analysis-title span {
  color: #9ca3af;
  font-size: 14px;
  font-weight: 400;
}

.health-analysis-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

.health-analysis-range {
  width: 140px;
}

.health-metric-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
  margin-bottom: 16px;
}

.health-metric {
  background: #ffffff;
  border: 1px solid #e5e7eb;
  border-radius: 12px;
  padding: 18px;
}

.health-metric-label {
  color: #6b7280;
  font-size: 13px;
}

.health-metric-value {
  margin-top: 8px;
  color: #111827;
  font-size: 32px;
  font-weight: 800;
  line-height: 1;
}

.health-metric-value.danger {
  color: #dc2626;
}

.health-metric-value.primary {
  color: #16a34a;
}

.health-metric-trend {
  margin-top: 8px;
  color: #9ca3af;
  font-size: 12px;
}

.health-summary-card {
  background: linear-gradient(135deg, #ecfdf5, #fef3c7);
  border: none;
  border-radius: 12px;
  padding: 20px;
  margin-bottom: 20px;
}

.health-summary-card ul {
  margin: 12px 0 0;
  padding-left: 20px;
  color: #111827;
  font-size: 14px;
  line-height: 2;
}

.health-summary-danger {
  color: #dc2626;
}

.health-summary-warning {
  color: #b45309;
}

.health-summary-success {
  color: #059669;
}

.health-summary-info {
  color: #4b5563;
}

.health-link-button {
  border: none;
  background: transparent;
  color: #16a34a;
  font: inherit;
  cursor: pointer;
  padding: 0;
}

.health-member-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}

.health-member-card {
  display: flex;
  align-items: center;
  gap: 12px;
  width: 100%;
  border: 1px solid #e5e7eb;
  border-radius: 12px;
  background: #ffffff;
  padding: 14px;
  text-align: left;
  cursor: pointer;
}

.health-member-card:hover {
  border-color: #86efac;
  background: #f7fee7;
}

.health-member-avatar {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 42px;
  height: 42px;
  border-radius: 999px;
  background: #dcfce7;
  color: #15803d;
  font-weight: 700;
}

.health-member-info {
  min-width: 0;
  flex: 1;
}

.health-member-name {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px;
  color: #111827;
  font-size: 14px;
  font-weight: 600;
}

.health-member-name > span:first-child {
  color: #6b7280;
  font-weight: 400;
}

.health-member-meta {
  margin-top: 4px;
  color: #9ca3af;
  font-size: 12px;
}

@media (max-width: 900px) {
  .health-analysis-head,
  .health-analysis-actions {
    align-items: stretch;
    flex-direction: column;
  }

  .health-metric-grid,
  .health-member-grid {
    grid-template-columns: 1fr;
  }
}
```

- [ ] **Step 3: 运行前端构建**

Run: `cd frontend && npm run build`

Expected: PASS。

- [ ] **Step 4: Commit 前端实现**

```bash
git add frontend/src/api/healthAnalysis.ts frontend/src/pages/HealthAnalysisPage.tsx frontend/src/main.tsx frontend/src/components/AppShell.tsx frontend/src/styles.css
git commit -m "feat: add health analysis page"
```

如果当前环境仍无法写 `.git/index.lock`，记录为环境权限问题，不要强行处理 `.git`。

---

### Task 9: 全量验证

**Files:**
- No file changes.

- [ ] **Step 1: 运行健康分析后端测试**

Run: `cd backend && pytest tests/test_api_health_analysis.py -v`

Expected: PASS。

- [ ] **Step 2: 运行相关后端测试**

Run: `cd backend && pytest tests/test_api_health_analysis.py tests/test_api_device.py tests/test_api_members.py -v`

Expected: PASS。

- [ ] **Step 3: 运行前端构建**

Run: `cd frontend && npm run build`

Expected: PASS。

- [ ] **Step 4: 启动本地服务做页面验证**

后端：

```bash
cd backend && uvicorn app.main:app --reload --port 8000
```

前端：

```bash
cd frontend && VITE_API_BASE=http://localhost:8000 npm run dev
```

打开：`http://localhost:5173/report`

Expected:

- 左侧导航“健康分析”高亮
- 顶部显示家庭名与周期
- 四个核心指标正常展示
- 摘要卡有 1 到 4 条内容
- 异常指标 Top 5 表格正常展示
- 成员卡点击进入成员详情页
- 周期下拉切换后页面重新请求数据

---

## Self-Review Checklist

- 设计中要求的成员资料、报告数量、设备近 7 天数据、健康标签均有任务覆盖。
- 未新增数据库表，符合第一版范围。
- API、schema、service、前端页面、路由、导航和样式均有明确任务。
- 测试覆盖有成员、高血压异常、无成员三类关键路径。
- 没有 `TBD`、`TODO`、占位步骤或未定义文件路径。
