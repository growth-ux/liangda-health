from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.alert import (
    AlertRuleCreateRequest,
    AlertRuleItem,
    AlertRuleListResponse,
    AlertRuleUpdateRequest,
    SmsConfigResponse,
    SmsConfigSaveRequest,
    SmsLogListResponse,
    SmsTestRequest,
    SmsTestResponse,
)
from app.services.common.alert_rule_service import AlertRuleService
from app.services.common.sms_service import SmsService

router = APIRouter(prefix="/api/settings", tags=["settings"])


# ── 预警规则 ──────────────────────────────────────────────────────────────


@router.get("/alert-rules", response_model=AlertRuleListResponse)
def list_alert_rules(db: Session = Depends(get_db)):
    return AlertRuleService(db).list_rules()


@router.post("/alert-rules", response_model=AlertRuleItem)
def create_alert_rule(request: AlertRuleCreateRequest, db: Session = Depends(get_db)):
    return AlertRuleService(db).create_rule(
        member_id=request.member_id,
        metric_type=request.metric_type,
        operator=request.operator,
        threshold=request.threshold,
        channel=request.channel,
    )


@router.put("/alert-rules/{rule_id}", response_model=AlertRuleItem)
def update_alert_rule(rule_id: str, request: AlertRuleUpdateRequest, db: Session = Depends(get_db)):
    data = request.model_dump(exclude_none=True)
    result = AlertRuleService(db).update_rule(rule_id, **data)
    if result is None:
        raise HTTPException(status_code=404, detail="预警规则不存在")
    return result


@router.delete("/alert-rules/{rule_id}")
def delete_alert_rule(rule_id: str, db: Session = Depends(get_db)):
    ok = AlertRuleService(db).delete_rule(rule_id)
    if not ok:
        raise HTTPException(status_code=404, detail="预警规则不存在")
    return {"deleted": True}


# ── 短信配置 ──────────────────────────────────────────────────────────────


@router.get("/sms-config", response_model=SmsConfigResponse)
def get_sms_config(db: Session = Depends(get_db)):
    return SmsService(db).get_config()


@router.post("/sms-config", response_model=SmsConfigResponse)
def save_sms_config(request: SmsConfigSaveRequest, db: Session = Depends(get_db)):
    return SmsService(db).save_config(
        provider=request.provider,
        api_key=request.api_key,
        api_secret=request.api_secret,
        signature=request.signature,
        template_id=request.template_id,
        enabled=request.enabled,
    )


@router.post("/sms-config/test", response_model=SmsTestResponse)
def test_sms_config(request: SmsTestRequest, db: Session = Depends(get_db)):
    return SmsService(db).test_send(request.phone)


@router.get("/sms-logs", response_model=SmsLogListResponse)
def list_sms_logs(db: Session = Depends(get_db)):
    return SmsService(db).list_logs()
