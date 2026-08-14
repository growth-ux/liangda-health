from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from app.repositories.alert_rule_repository import (
    SqlAlchemySmsConfigRepository,
    SqlAlchemySmsLogRepository,
)
from app.schemas.alert import (
    SmsConfigItem,
    SmsConfigResponse,
    SmsLogItem,
    SmsLogListResponse,
    SmsTestResponse,
)

logger = logging.getLogger(__name__)


class SmsService:
    def __init__(self, db: Session):
        self.db = db
        self.config_repo = SqlAlchemySmsConfigRepository(db)
        self.log_repo = SqlAlchemySmsLogRepository(db)

    def get_config(self) -> SmsConfigResponse:
        config = self.config_repo.get_active()
        if config is None:
            return SmsConfigResponse(config=None)
        return SmsConfigResponse(config=self._to_config_item(config))

    def save_config(self, **kwargs) -> SmsConfigResponse:
        config = self.config_repo.save_config(**kwargs)
        return SmsConfigResponse(config=self._to_config_item(config))

    def test_send(self, phone: str) -> SmsTestResponse:
        config = self.config_repo.get_active()
        if not config or config.enabled != "true":
            return SmsTestResponse(status="error", message="短信配置未启用")
        # 演示模式：只记录日志，不实际调用第三方 API
        self.log_repo.create_log(
            rule_id="test",
            member_id="test",
            phone=phone,
            content=f"【{config.signature}】这是一条测试短信，用于验证短信配置是否正确。",
            status="sent",
        )
        logger.info("SMS test sent to %s (provider: %s)", phone, config.provider)
        return SmsTestResponse(status="success", message=f"测试短信已发送至 {phone}（演示模式，仅记录日志）")

    def list_logs(self, limit: int = 50) -> SmsLogListResponse:
        logs = self.log_repo.list_logs(limit=limit)
        items = [
            SmsLogItem(
                id=log.id,
                rule_id=log.rule_id,
                member_id=log.member_id,
                phone=log.phone,
                content=log.content,
                status=log.status,
                created_at=log.created_at,
            )
            for log in logs
        ]
        return SmsLogListResponse(logs=items)

    @staticmethod
    def _to_config_item(config) -> SmsConfigItem:
        return SmsConfigItem(
            id=config.id,
            provider=config.provider,
            api_key=config.api_key,
            api_secret=config.api_secret,
            signature=config.signature,
            template_id=config.template_id,
            enabled=config.enabled == "true",
            created_at=config.created_at,
        )
