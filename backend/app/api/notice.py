from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.notice import NoticeItem, NoticeListResponse, NoticeReadAllResponse, NoticeSummaryResponse
from app.services.notice_service import NoticeService

router = APIRouter(prefix="/api/notices", tags=["notices"])


@router.get("", response_model=NoticeListResponse)
def list_notices(
    category: str = Query(default="all", pattern="^(all|health_alert|system|recommendation)$"),
    db: Session = Depends(get_db),
):
    return NoticeService(db).list_notices(category)


@router.get("/summary", response_model=NoticeSummaryResponse)
def get_notice_summary(db: Session = Depends(get_db)):
    return NoticeService(db).summary()


@router.post("/read-all", response_model=NoticeReadAllResponse)
def read_all_notices(db: Session = Depends(get_db)):
    return NoticeReadAllResponse(updated=NoticeService(db).mark_all_read())


@router.post("/{notice_id}/read", response_model=NoticeItem)
def read_notice(notice_id: str, db: Session = Depends(get_db)):
    service = NoticeService(db)
    notice = service.mark_read(notice_id)
    if notice is None:
        raise HTTPException(status_code=404, detail="通知不存在")
    return service._to_item(notice)


@router.post("/{notice_id}/snooze", response_model=NoticeItem)
def snooze_notice(notice_id: str, db: Session = Depends(get_db)):
    service = NoticeService(db)
    notice = service.snooze(notice_id)
    if notice is None:
        raise HTTPException(status_code=404, detail="通知不存在")
    return service._to_item(notice)


@router.post("/{notice_id}/done", response_model=NoticeItem)
def done_notice(notice_id: str, db: Session = Depends(get_db)):
    service = NoticeService(db)
    notice = service.done(notice_id)
    if notice is None:
        raise HTTPException(status_code=404, detail="通知不存在")
    return service._to_item(notice)
