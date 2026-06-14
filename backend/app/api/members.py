from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.repositories.member_repository import SqlAlchemyMemberRepository
from app.schemas.kb import DocumentListItem
from app.schemas.member import MemberCreateRequest, MemberDetail, MemberListItem, MemberUpdateRequest

router = APIRouter(prefix="/api/members", tags=["members"])


@router.get("", response_model=list[MemberListItem])
def list_members(db: Session = Depends(get_db)):
    return SqlAlchemyMemberRepository(db).list_members()


@router.post("", response_model=MemberDetail)
def create_member(request: MemberCreateRequest, db: Session = Depends(get_db)):
    return SqlAlchemyMemberRepository(db).create_member(request)


@router.get("/{member_id}", response_model=MemberDetail)
def get_member(member_id: str, db: Session = Depends(get_db)):
    repository = SqlAlchemyMemberRepository(db)
    member = repository.get_member_detail(member_id)
    if member is None:
        raise HTTPException(status_code=404, detail="家人不存在")
    return member


@router.put("/{member_id}", response_model=MemberDetail)
def update_member(member_id: str, request: MemberUpdateRequest, db: Session = Depends(get_db)):
    repository = SqlAlchemyMemberRepository(db)
    member = repository.update_member(member_id, request)
    if member is None:
        raise HTTPException(status_code=404, detail="家人不存在")
    return member


@router.delete("/{member_id}", status_code=204)
def delete_member(member_id: str, db: Session = Depends(get_db)):
    repository = SqlAlchemyMemberRepository(db)
    if repository.get_member(member_id) is None:
        raise HTTPException(status_code=404, detail="家人不存在")
    if repository.count_documents(member_id) > 0:
        raise HTTPException(status_code=400, detail="该家人已有报告，不能删除")
    repository.delete_member(member_id)
    return Response(status_code=204)


@router.get("/{member_id}/documents", response_model=list[DocumentListItem])
def list_member_documents(member_id: str, db: Session = Depends(get_db)):
    repository = SqlAlchemyMemberRepository(db)
    if repository.get_member(member_id) is None:
        raise HTTPException(status_code=404, detail="家人不存在")
    return repository.list_documents(member_id)
