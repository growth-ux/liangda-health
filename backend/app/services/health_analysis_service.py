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
    HealthAnalysisAdvice,
    HealthAnalysisBloodPressurePoint,
    HealthAnalysisFamily,
    HealthAnalysisIndicator,
    HealthAnalysisMemberCard,
    HealthAnalysisMemberResponse,
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
        device_count = sum(
            1 for item in analyses if self.device_repository.get_binding(item.member.member_id) is not None
        )

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

    def get_member_analysis(self, member_id: str) -> HealthAnalysisMemberResponse:
        analysis = self._analyze_member(member_id)
        return HealthAnalysisMemberResponse(
            member_card=self._member_card(analysis),
            indicators=self._member_indicators(analysis),
            blood_pressure_7d=[
                HealthAnalysisBloodPressurePoint(
                    date=metric.metric_date.isoformat(),
                    systolic=metric.systolic_bp,
                    diastolic=metric.diastolic_bp,
                )
                for metric in analysis.metrics
            ],
            abnormalities=sorted(
                analysis.abnormalities,
                key=lambda item: (0 if item.status == "danger" else 1, -item.score_impact),
            ),
            advice=self._member_advice(analysis),
        )

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
            items.append(
                self._abnormal(
                    member,
                    "体检报告",
                    "0 份",
                    "warning",
                    "缺失",
                    "暂无近期报告",
                    "建议上传近期体检报告",
                    6,
                )
            )

        tag_rules = {
            "高血压": ("高血压", "已标记", "warning", "风险提示", "长期关注", "建议保持低钠饮食并定期测量血压"),
            "糖尿病": ("糖尿病", "已标记", "warning", "风险提示", "长期关注", "建议控制精制碳水摄入并记录空腹血糖"),
            "高血脂": ("高血脂", "已标记", "warning", "风险提示", "长期关注", "建议减少高油脂食品摄入"),
            "骨质疏松": ("骨质疏松", "已标记", "warning", "风险提示", "长期关注", "建议补充钙和维生素 D，并增加日晒"),
            "超重": ("超重", "已标记", "warning", "风险提示", "长期关注", "建议控制总热量并增加步行"),
            "痛风": ("痛风", "已标记", "warning", "风险提示", "长期关注", "建议减少高嘌呤食品摄入"),
            "心血管": ("心血管风险", "已标记", "warning", "风险提示", "长期关注", "建议关注心率、血压并按时复查"),
            "胃肠": ("胃肠问题", "已标记", "warning", "风险提示", "长期关注", "建议饮食规律并减少刺激性食物"),
        }
        tag_penalty = 0
        for tag in health_tags:
            for keyword, rule in tag_rules.items():
                if keyword in tag and tag_penalty < 20:
                    metric, value, status, status_text, trend, suggestion = rule
                    impact = min(4, 20 - tag_penalty)
                    items.append(self._abnormal(member, metric, value, status, status_text, trend, suggestion, impact))
                    tag_penalty += impact
                    break

        systolic = averages.get("systolic_bp")
        if systolic is not None and systolic >= 140:
            items.append(
                self._abnormal(
                    member,
                    "收缩压",
                    f"{round(systolic)} mmHg",
                    "danger",
                    "偏高",
                    "持续偏高",
                    "建议减少高钠饮食，并安排血压复查",
                    12,
                )
            )
        elif systolic is not None and systolic >= 130:
            items.append(
                self._abnormal(
                    member,
                    "收缩压",
                    f"{round(systolic)} mmHg",
                    "warning",
                    "偏高",
                    "略高",
                    "建议继续观察血压变化",
                    6,
                )
            )

        diastolic = averages.get("diastolic_bp")
        if diastolic is not None and diastolic >= 90:
            items.append(
                self._abnormal(
                    member,
                    "舒张压",
                    f"{round(diastolic)} mmHg",
                    "danger",
                    "偏高",
                    "持续偏高",
                    "建议规律测量并咨询医生",
                    10,
                )
            )
        elif diastolic is not None and diastolic >= 85:
            items.append(
                self._abnormal(
                    member,
                    "舒张压",
                    f"{round(diastolic)} mmHg",
                    "warning",
                    "偏高",
                    "略高",
                    "建议继续观察血压变化",
                    5,
                )
            )

        sleep = averages.get("sleep_hours")
        if sleep is not None and sleep < 6:
            items.append(
                self._abnormal(
                    member,
                    "睡眠时长",
                    f"{sleep:.1f} h/天",
                    "danger",
                    "不足",
                    "持续偏低",
                    "建议提前入睡并减少睡前屏幕时间",
                    8,
                )
            )
        elif sleep is not None and sleep <= 6.5:
            items.append(
                self._abnormal(
                    member,
                    "睡眠时长",
                    f"{sleep:.1f} h/天",
                    "warning",
                    "偏少",
                    "略低",
                    "建议保持规律作息",
                    4,
                )
            )

        steps = averages.get("steps")
        if steps is not None and steps < 4000:
            items.append(
                self._abnormal(
                    member,
                    "步数",
                    f"{round(steps)} 步/天",
                    "warning",
                    "偏少",
                    "活动不足",
                    "建议每天增加 20 分钟步行",
                    6,
                )
            )
        elif steps is not None and steps < 6000:
            items.append(
                self._abnormal(
                    member,
                    "步数",
                    f"{round(steps)} 步/天",
                    "warning",
                    "偏少",
                    "略低",
                    "建议适度增加日常活动",
                    3,
                )
            )

        oxygen = averages.get("blood_oxygen")
        if oxygen is not None and oxygen < 95:
            items.append(
                self._abnormal(
                    member,
                    "血氧",
                    f"{round(oxygen)}%",
                    "danger",
                    "偏低",
                    "低于建议值",
                    "建议复测血氧并关注呼吸状态",
                    10,
                )
            )

        bmi = self._bmi(member)
        if bmi is not None and bmi >= 28:
            items.append(
                self._abnormal(
                    member,
                    "BMI",
                    f"{bmi:.1f}",
                    "danger",
                    "肥胖",
                    "偏高",
                    "建议控制总热量并增加运动",
                    8,
                )
            )
        elif bmi is not None and bmi >= 24:
            items.append(
                self._abnormal(
                    member,
                    "BMI",
                    f"{bmi:.1f}",
                    "warning",
                    "偏高",
                    "偏高",
                    "建议控制主食和油脂摄入",
                    4,
                )
            )

        return items

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
            summary.append(
                HealthAnalysisSummaryItem(
                    level=item.status,
                    text=f"关注：{item.member_name}{item.metric}{item.status_text}，当前 {item.current_value}",
                )
            )

        best = max(analyses, key=lambda item: item.score)
        summary.append(
            HealthAnalysisSummaryItem(level="success", text=f"稳定：{best.member.name}近期整体指标较平稳，健康分 {best.score}")
        )

        missing_report = next((item for item in analyses if item.report_count == 0), None)
        if missing_report is not None:
            summary.append(
                HealthAnalysisSummaryItem(
                    level="warning",
                    text=f"提醒：{missing_report.member.name}暂无已存报告，建议上传近期体检报告",
                )
            )

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

    def _member_indicators(self, analysis: MemberAnalysis) -> list[HealthAnalysisIndicator]:
        averages = self._metric_averages(analysis.metrics)
        report_status = "success" if analysis.report_count > 0 else "warning"
        report_status_text = "已归档" if analysis.report_count > 0 else "待上传"
        indicators = [
            self._indicator(
                "systolic_bp",
                "收缩压",
                self._rounded_value(averages.get("systolic_bp")),
                "mmHg",
                self._threshold_status(averages.get("systolic_bp"), warning=130, danger=140),
                "偏高" if (averages.get("systolic_bp") or 0) >= 130 else "正常",
            ),
            self._indicator(
                "diastolic_bp",
                "舒张压",
                self._rounded_value(averages.get("diastolic_bp")),
                "mmHg",
                self._threshold_status(averages.get("diastolic_bp"), warning=85, danger=90),
                "偏高" if (averages.get("diastolic_bp") or 0) >= 85 else "正常",
            ),
            self._indicator(
                "heart_rate",
                "心率",
                self._rounded_value(averages.get("avg_heart_rate")),
                "bpm",
                "success",
                "正常",
            ),
            self._indicator(
                "sleep",
                "睡眠",
                self._decimal_value(averages.get("sleep_hours")),
                "h",
                self._low_threshold_status(averages.get("sleep_hours"), warning=6.5, danger=6),
                "不足" if (averages.get("sleep_hours") or 99) <= 6.5 else "正常",
            ),
            self._indicator(
                "blood_oxygen",
                "血氧",
                self._rounded_value(averages.get("blood_oxygen")),
                "%",
                self._low_threshold_status(averages.get("blood_oxygen"), warning=95, danger=95),
                "偏低" if (averages.get("blood_oxygen") or 100) < 95 else "正常",
            ),
            self._indicator(
                "bmi",
                "BMI",
                self._decimal_value(self._bmi(analysis.member)),
                None,
                self._threshold_status(self._bmi(analysis.member), warning=24, danger=28),
                "偏高" if (self._bmi(analysis.member) or 0) >= 24 else "正常",
            ),
            self._indicator(
                "report_count",
                "报告数量",
                str(analysis.report_count),
                "份",
                report_status,
                report_status_text,
            ),
            self._indicator(
                "health_tags",
                "健康标签",
                str(len(analysis.health_tags)),
                "个",
                "warning" if analysis.health_tags else "success",
                "需关注" if analysis.health_tags else "正常",
            ),
        ]
        return indicators

    def _member_advice(self, analysis: MemberAnalysis) -> HealthAnalysisAdvice:
        top_items = sorted(
            analysis.abnormalities,
            key=lambda item: (0 if item.status == "danger" else 1, -item.score_impact),
        )
        if not top_items:
            return HealthAnalysisAdvice(
                title="管家长期建议",
                lines=[
                    f"{analysis.member.name}当前健康指标整体平稳。",
                    "建议保持规律作息、适度运动，并持续补充体检报告。",
                ],
                prompt=f"请根据成员 {analysis.member.member_id} 的健康数据，给出长期家庭健康建议",
            )

        primary = top_items[0]
        lines = [
            f"{analysis.member.name}当前重点关注：{primary.metric}{primary.status_text}。",
            primary.suggestion,
            "建议结合手环趋势和体检报告持续观察，必要时安排复查。",
        ]
        return HealthAnalysisAdvice(
            title="管家长期建议",
            lines=lines,
            prompt=f"请根据成员 {analysis.member.member_id} 的{primary.metric}问题，给出长期家庭健康建议",
        )

    @staticmethod
    def _indicator(
        key: str,
        label: str,
        value: str,
        unit: str | None,
        status: str,
        status_text: str,
    ) -> HealthAnalysisIndicator:
        return HealthAnalysisIndicator(
            key=key,
            label=label,
            value=value,
            unit=unit,
            status=status,
            status_text=status_text,
        )

    @staticmethod
    def _rounded_value(value: float | None) -> str:
        if value is None:
            return "-"
        return str(round(value))

    @staticmethod
    def _decimal_value(value: float | None) -> str:
        if value is None:
            return "-"
        return f"{value:.1f}"

    @staticmethod
    def _threshold_status(value: float | None, *, warning: float, danger: float) -> str:
        if value is None:
            return "info"
        if value >= danger:
            return "danger"
        if value >= warning:
            return "warning"
        return "success"

    @staticmethod
    def _low_threshold_status(value: float | None, *, warning: float, danger: float) -> str:
        if value is None:
            return "info"
        if value < danger:
            return "danger"
        if value <= warning:
            return "warning"
        return "success"

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
        return {field: sum(float(getattr(metric, field)) for metric in metrics) / len(metrics) for field in fields}

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
