from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.repositories.member_repository import SqlAlchemyMemberRepository
from app.schemas.device import DeviceOverviewResponse
from app.services.device_service import DeviceService

router = APIRouter(prefix="/api/devices", tags=["devices"])


@router.get("/{member_id}/overview", response_model=DeviceOverviewResponse)
def get_device_overview(member_id: str, db: Session = Depends(get_db)):
    if SqlAlchemyMemberRepository(db).get_member(member_id) is None:
        raise HTTPException(status_code=404, detail="家人不存在")
    try:
        return DeviceService(db).get_overview(member_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="设备数据不存在")


@router.post("/{member_id}/sync", response_model=DeviceOverviewResponse)
def sync_device(member_id: str, db: Session = Depends(get_db)):
    if SqlAlchemyMemberRepository(db).get_member(member_id) is None:
        raise HTTPException(status_code=404, detail="家人不存在")
    return DeviceService(db).sync_and_get_overview(member_id)
