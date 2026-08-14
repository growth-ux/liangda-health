from uuid import uuid4

from sqlalchemy.orm import Session

from app.core.time import utc_now
from app.models.alert import AlertRule, SmsConfig, SmsLog


class SqlAlchemyAlertRuleRepository:
    def __init__(self, db: Session):
        self.db = db

    def list_rules(self, member_id: str | None = None) -> list[AlertRule]:
        query = self.db.query(AlertRule)
        if member_id:
            query = query.filter(AlertRule.member_id == member_id)
        return query.order_by(AlertRule.created_at.desc()).all()

    def get_rule(self, rule_id: str) -> AlertRule | None:
        return self.db.query(AlertRule).filter(AlertRule.rule_id == rule_id).one_or_none()

    def create_rule(
        self,
        *,
        member_id: str,
        metric_type: str,
        operator: str,
        threshold: int,
        channel: str = "in_app",
    ) -> AlertRule:
        rule = AlertRule(
            rule_id=f"rule_{uuid4().hex}",
            member_id=member_id,
            metric_type=metric_type,
            operator=operator,
            threshold=threshold,
            channel=channel,
            enabled="true",
            created_at=utc_now(),
            updated_at=utc_now(),
        )
        self.db.add(rule)
        self.db.commit()
        self.db.refresh(rule)
        return rule

    def update_rule(self, rule_id: str, **kwargs) -> AlertRule | None:
        rule = self.get_rule(rule_id)
        if rule is None:
            return None
        for key, value in kwargs.items():
            if value is not None and hasattr(rule, key):
                if key == "enabled":
                    setattr(rule, key, "true" if value else "false")
                else:
                    setattr(rule, key, value)
        rule.updated_at = utc_now()
        self.db.commit()
        self.db.refresh(rule)
        return rule

    def delete_rule(self, rule_id: str) -> bool:
        rule = self.get_rule(rule_id)
        if rule is None:
            return False
        self.db.delete(rule)
        self.db.commit()
        return True

    def get_enabled_rules(self) -> list[AlertRule]:
        return (
            self.db.query(AlertRule)
            .filter(AlertRule.enabled == "true")
            .all()
        )

    def member_has_rule(self, member_id: str) -> bool:
        return (
            self.db.query(AlertRule.id)
            .filter(AlertRule.member_id == member_id, AlertRule.enabled == "true")
            .first()
            is not None
        )


class SqlAlchemySmsConfigRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_active(self) -> SmsConfig | None:
        return self.db.query(SmsConfig).order_by(SmsConfig.id.desc()).first()

    def save_config(self, **kwargs) -> SmsConfig:
        existing = self.get_active()
        if existing:
            for key, value in kwargs.items():
                if key == "enabled":
                    setattr(existing, key, "true" if value else "false")
                elif hasattr(existing, key):
                    setattr(existing, key, value)
            existing.updated_at = utc_now()
            self.db.commit()
            self.db.refresh(existing)
            return existing
        config = SmsConfig(
            provider=kwargs.get("provider", ""),
            api_key=kwargs.get("api_key", ""),
            api_secret=kwargs.get("api_secret", ""),
            signature=kwargs.get("signature", ""),
            template_id=kwargs.get("template_id", ""),
            enabled="true" if kwargs.get("enabled", True) else "false",
            created_at=utc_now(),
            updated_at=utc_now(),
        )
        self.db.add(config)
        self.db.commit()
        self.db.refresh(config)
        return config


class SqlAlchemySmsLogRepository:
    def __init__(self, db: Session):
        self.db = db

    def create_log(self, *, rule_id: str, member_id: str, phone: str, content: str, status: str = "sent") -> SmsLog:
        log = SmsLog(
            rule_id=rule_id,
            member_id=member_id,
            phone=phone,
            content=content,
            status=status,
            created_at=utc_now(),
        )
        self.db.add(log)
        self.db.commit()
        self.db.refresh(log)
        return log

    def list_logs(self, limit: int = 50) -> list[SmsLog]:
        return (
            self.db.query(SmsLog)
            .order_by(SmsLog.created_at.desc())
            .limit(limit)
            .all()
        )
