from __future__ import annotations

import logging
from operator import ge, gt, le, lt

from sqlalchemy.orm import Session

from app.core.demo import real_only
from app.models.alert import AlertRule
from app.models.device import DeviceDailyMetric
from app.models.health_fact import HealthFact
from app.models.member import Member
from app.repositories.alert_rule_repository import (
    SqlAlchemyAlertRuleRepository,
    SqlAlchemySmsConfigRepository,
    SqlAlchemySmsLogRepository,
)
from app.repositories.notice_repository import SqlAlchemyNoticeRepository
from app.schemas.alert import AlertRuleItem, AlertRuleListResponse

logger = logging.getLogger(__name__)

METRIC_TYPE_LABELS = {
    "systolic_bp": "收缩压",
    "diastolic_bp": "舒张压",
    "heart_rate": "心率",
    "steps": "步数",
    "sleep_hours": "睡眠时长",
    "blood_oxygen": "血氧",
    "health_fact": "报告异常指标",
    "health_trend": "AI 趋势分析",
    "recheck": "复诊提醒",
}

# AI 主动预警类型，不需要 operator/threshold
AI_METRIC_TYPES = {"health_fact", "health_trend", "recheck"}

OPERATOR_FNS = {
    ">": gt,
    "<": lt,
    ">=": ge,
    "<=": le,
}


class AlertRuleService:
    def __init__(self, db: Session):
        self.db = db
        self.rule_repo = SqlAlchemyAlertRuleRepository(db)
        self.sms_config_repo = SqlAlchemySmsConfigRepository(db)
        self.sms_log_repo = SqlAlchemySmsLogRepository(db)
        self.notice_repo = SqlAlchemyNoticeRepository(db)

    def list_rules(self) -> AlertRuleListResponse:
        rules = self.rule_repo.list_rules()
        members = self._member_map()
        items = [self._to_item(rule, members) for rule in rules]
        coverage = {
            m.member_id: self.rule_repo.member_has_rule(m.member_id)
            for m in members.values()
        }
        return AlertRuleListResponse(rules=items, member_coverage=coverage)

    def create_rule(self, **kwargs) -> AlertRuleItem:
        rule = self.rule_repo.create_rule(**kwargs)
        members = self._member_map()
        return self._to_item(rule, members)

    def update_rule(self, rule_id: str, **kwargs) -> AlertRuleItem | None:
        rule = self.rule_repo.update_rule(rule_id, **kwargs)
        if rule is None:
            return None
        members = self._member_map()
        return self._to_item(rule, members)

    def delete_rule(self, rule_id: str) -> bool:
        return self.rule_repo.delete_rule(rule_id)

    def evaluate_rules(self) -> list[dict]:
        """评估所有启用规则，返回触发的预警列表。"""
        rules = self.rule_repo.get_enabled_rules()
        if not rules:
            return []
        members = self._member_map()
        triggered = []
        for rule in rules:
            member = members.get(rule.member_id)
            if not member:
                continue
            if rule.metric_type in AI_METRIC_TYPES:
                result = self._evaluate_ai_rule(rule, member)
                if result:
                    triggered.append(result)
            else:
                result = self._evaluate_device_rule(rule, member)
                if result:
                    triggered.append(result)
        return triggered

    def _evaluate_device_rule(self, rule: AlertRule, member: Member) -> dict | None:
        """评估手环硬件指标规则。"""
        latest_metric = self._latest_metric(rule.member_id)
        if not latest_metric:
            return None
        value = self._get_metric_value(latest_metric, rule.metric_type)
        if value is None:
            return None
        op_fn = OPERATOR_FNS.get(rule.operator)
        if not op_fn:
            return None
        if op_fn(value, rule.threshold):
            return {
                "rule": rule,
                "member": member,
                "metric_value": value,
                "metric_label": METRIC_TYPE_LABELS.get(rule.metric_type, rule.metric_type),
                "alert_type": "device",
            }
        return None

    def _evaluate_ai_rule(self, rule: AlertRule, member: Member) -> dict | None:
        """评估 AI 主动预警规则。"""
        if rule.metric_type == "health_fact":
            return self._evaluate_health_fact_rule(rule, member)
        if rule.metric_type == "health_trend":
            return self._evaluate_health_trend_rule(rule, member)
        if rule.metric_type == "recheck":
            return self._evaluate_recheck_rule(rule, member)
        return None

    def _evaluate_health_fact_rule(self, rule: AlertRule, member: Member) -> dict | None:
        """报告异常指标：检查是否有 danger/warning 级别的健康事实。"""
        danger_facts = (
            self.db.query(HealthFact)
            .filter(
                HealthFact.member_id == member.member_id,
                HealthFact.status.in_(["danger", "warning"]),
            )
            .order_by(HealthFact.created_at.desc())
            .limit(3)
            .all()
        )
        if not danger_facts:
            return None
        names = "、".join(set(f.name for f in danger_facts))
        return {
            "rule": rule,
            "member": member,
            "metric_value": names,
            "metric_label": "报告异常指标",
            "alert_type": "health_fact",
            "detail_facts": danger_facts,
        }

    def _evaluate_health_trend_rule(self, rule: AlertRule, member: Member) -> dict | None:
        """AI 趋势分析：检查血压是否连续 3 天上升。"""
        recent_metrics = (
            self.db.query(DeviceDailyMetric)
            .filter(DeviceDailyMetric.member_id == member.member_id)
            .order_by(DeviceDailyMetric.metric_date.desc())
            .limit(5)
            .all()
        )
        if len(recent_metrics) < 3:
            return None
        # 检查收缩压是否连续 3 天上升
        sorted_metrics = sorted(recent_metrics[:3], key=lambda m: m.metric_date)
        rising = all(
            sorted_metrics[i].systolic_bp < sorted_metrics[i + 1].systolic_bp
            for i in range(len(sorted_metrics) - 1)
        )
        if not rising:
            return None
        trend_text = " → ".join(
            f"{m.metric_date.strftime('%m/%d')} {m.systolic_bp}mmHg"
            for m in sorted_metrics
        )
        return {
            "rule": rule,
            "member": member,
            "metric_value": trend_text,
            "metric_label": "AI 趋势分析",
            "alert_type": "health_trend",
            "trend_detail": f"收缩压连续 3 天上升：{trend_text}",
        }

    def _evaluate_recheck_rule(self, rule: AlertRule, member: Member) -> dict | None:
        """复诊提醒：检查是否有 recheck 类型的健康事实。"""
        recheck_facts = (
            self.db.query(HealthFact)
            .filter(
                HealthFact.member_id == member.member_id,
                HealthFact.fact_type == "recheck",
            )
            .order_by(HealthFact.created_at.desc())
            .limit(3)
            .all()
        )
        if not recheck_facts:
            return None
        names = "、".join(set(f.name for f in recheck_facts))
        return {
            "rule": rule,
            "member": member,
            "metric_value": names,
            "metric_label": "复诊提醒",
            "alert_type": "recheck",
            "detail_facts": recheck_facts,
        }

    def generate_alert_notices(self) -> bool:
        """根据规则触发结果生成通知，供 NoticeService 调用。"""
        triggered = self.evaluate_rules()
        if not triggered:
            return False
        created = False
        for item in triggered:
            rule: AlertRule = item["rule"]
            member: Member = item["member"]
            value = item["metric_value"]
            label = item["metric_label"]
            alert_type = item.get("alert_type", "device")
            from app.core.time import utc_now
            today = utc_now().date().isoformat()
            dedupe_key = f"alert_rule:{rule.rule_id}:{today}"
            if self.notice_repo.exists_dedupe_key(dedupe_key):
                continue
            title, description, level = self._build_notice_content(
                member, label, value, alert_type, item
            )
            self.notice_repo.create_notice(
                category="health_alert",
                level=level,
                title=title,
                description=description,
                source="housekeeper",
                member_id=member.member_id,
                target_type="chat",
                action_text="查看",
                secondary_action="稍后",
                dedupe_key=dedupe_key,
            )
            created = True
            if rule.channel in ("sms", "both"):
                self._send_sms_alert(rule, member, label, value)
        if created:
            self.db.commit()
        return created

    @staticmethod
    def _build_notice_content(
        member: Member, label: str, value, alert_type: str, item: dict
    ) -> tuple[str, str, str]:
        """根据预警类型生成不同的通知内容。"""
        if alert_type == "health_fact":
            facts = item.get("detail_facts", [])
            fact_details = "、".join(
                f"{f.name}({f.value or ''}{f.unit or ''})" for f in facts[:3]
            )
            return (
                f"{member.relation}体检报告异常提醒",
                f"AI 管家发现{member.name}（{member.relation}）的体检报告中有异常指标：{fact_details}。建议及时关注并与医生沟通。",
                "danger",
            )
        if alert_type == "health_trend":
            trend = item.get("trend_detail", f"指标持续变化")
            return (
                f"{member.relation}健康趋势预警",
                f"AI 管家检测到{member.name}（{member.relation}）{trend}。建议调整饮食和作息，必要时就医。",
                "warning",
            )
        if alert_type == "recheck":
            return (
                f"{member.relation}复诊提醒",
                f"根据{member.name}（{member.relation}）的体检报告，医生建议复查项目：{value}。请及时预约复诊。",
                "warning",
            )
        # 硬件指标预警
        return (
            f"{member.relation}{label}预警",
            f"{member.name}（{member.relation}）最近一次{label}为 {value}，触发预警规则。请及时关注。",
            "danger",
        )

    def _send_sms_alert(self, rule: AlertRule, member: Member, label: str, value) -> None:
        """发送短信预警（记录日志，实际调用由 SmsService 封装）。"""
        phone = member.phone
        if not phone:
            return
        sms_config = self.sms_config_repo.get_active()
        if not sms_config or sms_config.enabled != "true":
            return
        content = f"【{sms_config.signature}】{member.name}（{member.relation}）{label}为{value}，请及时关注。"
        self.sms_log_repo.create_log(
            rule_id=rule.rule_id,
            member_id=member.member_id,
            phone=phone,
            content=content,
            status="sent",
        )
        logger.info("SMS sent to %s: %s", phone, content)

    def _latest_metric(self, member_id: str) -> DeviceDailyMetric | None:
        return (
            self.db.query(DeviceDailyMetric)
            .filter(DeviceDailyMetric.member_id == member_id)
            .order_by(DeviceDailyMetric.metric_date.desc())
            .first()
        )

    @staticmethod
    def _get_metric_value(metric: DeviceDailyMetric, metric_type: str) -> int | float | None:
        mapping = {
            "systolic_bp": metric.systolic_bp,
            "diastolic_bp": metric.diastolic_bp,
            "heart_rate": metric.avg_heart_rate,
            "steps": metric.steps,
            "sleep_hours": metric.sleep_hours,
            "blood_oxygen": metric.blood_oxygen,
        }
        return mapping.get(metric_type)

    def _member_map(self) -> dict[str, Member]:
        return {
            m.member_id: m
            for m in self.db.query(Member).filter(real_only(Member.member_id)).all()
        }

    @staticmethod
    def _to_item(rule: AlertRule, members: dict[str, Member]) -> AlertRuleItem:
        member = members.get(rule.member_id)
        return AlertRuleItem(
            rule_id=rule.rule_id,
            member_id=rule.member_id,
            member_name=member.name if member else None,
            member_relation=member.relation if member else None,
            metric_type=rule.metric_type,
            metric_type_text=METRIC_TYPE_LABELS.get(rule.metric_type, rule.metric_type),
            operator=rule.operator,
            threshold=rule.threshold,
            channel=rule.channel,
            enabled=rule.enabled == "true",
            created_at=rule.created_at,
        )
