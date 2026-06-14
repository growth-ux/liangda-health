from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.repositories.member_repository import SqlAlchemyMemberRepository
from app.schemas.health_analysis import HealthAnalysisMemberResponse, HealthAnalysisOverviewResponse
from app.services.health_analysis_service import HealthAnalysisService

router = APIRouter(prefix="/api/health-analysis", tags=["health-analysis"])


@router.get("/overview", response_model=HealthAnalysisOverviewResponse)
def get_health_analysis_overview(
    range: str = Query(default="this_month", pattern="^(this_month|last_3_months|last_6_months|last_12_months)$"),
    db: Session = Depends(get_db),
):
    return HealthAnalysisService(db).get_overview(range)


@router.get("/members/{member_id}", response_model=HealthAnalysisMemberResponse)
def get_member_health_analysis(member_id: str, db: Session = Depends(get_db)):
    if SqlAlchemyMemberRepository(db).get_member(member_id) is None:
        raise HTTPException(status_code=404, detail="家人不存在")
    return HealthAnalysisService(db).get_member_analysis(member_id)
