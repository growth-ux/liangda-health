# Members Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现家人功能闭环，包括家人增改查、报告归属家人、家人详情查看关联报告，以及报告页基于真实成员筛选。

**Architecture:** 后端新增 `members` 领域，沿用现有 FastAPI + SQLAlchemy repository 结构；报告通过 `kb_documents.member_id` 直接关联成员。前端新增 members 页面与 API，并在上传弹窗和报告页中接入成员数据，替换姓名正则归类。

**Tech Stack:** FastAPI, SQLAlchemy, Pydantic, React 19, React Router, TanStack Query, TypeScript, Vite

---

### Task 1: 写后端成员 API 的失败测试

**Files:**
- Create: `backend/tests/test_api_members.py`
- Modify: `backend/tests/conftest.py`

- [ ] **Step 1: 写成员列表和创建接口的失败测试**

```python
from fastapi.testclient import TestClient

from app.db.session import get_db
from app.main import create_app


def test_members_create_and_list():
    app = create_app()
    client = TestClient(app)

    create_response = client.post(
        "/members",
        json={
            "name": "王秀英",
            "relation": "母亲",
            "gender": "女",
            "birth_year": 1961,
            "height_cm": 158,
            "weight_kg": 60,
            "health_tags": ["高血压"],
            "allergies": "忌辛辣",
            "taste_preferences": "偏清淡",
        },
    )

    assert create_response.status_code == 200

    list_response = client.get("/members")

    assert list_response.status_code == 200
    assert list_response.json()[0]["name"] == "王秀英"
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd backend && pytest tests/test_api_members.py::test_members_create_and_list -v`
Expected: FAIL，原因是 `/members` 路由不存在

- [ ] **Step 3: 写详情、更新、删除限制、成员报告列表的失败测试**

```python
def test_members_detail_update_and_documents():
    app = create_app()
    client = TestClient(app)

    created = client.post(
        "/members",
        json={
            "name": "张建国",
            "relation": "父亲",
            "gender": "男",
            "birth_year": 1958,
            "health_tags": ["高血压"],
        },
    ).json()

    member_id = created["member_id"]

    detail_response = client.get(f"/members/{member_id}")
    assert detail_response.status_code == 200

    update_response = client.put(
        f"/members/{member_id}",
        json={
            "name": "张建国",
            "relation": "父亲",
            "gender": "男",
            "birth_year": 1958,
            "health_tags": ["高血压", "高血脂"],
        },
    )
    assert update_response.status_code == 200

    documents_response = client.get(f"/members/{member_id}/documents")
    assert documents_response.status_code == 200
    assert documents_response.json() == []
```

- [ ] **Step 4: 运行测试确认失败**

Run: `cd backend && pytest tests/test_api_members.py -v`
Expected: FAIL，原因是 `/members` 路由不存在

### Task 2: 实现最小成员后端使测试转绿

**Files:**
- Create: `backend/app/models/member.py`
- Create: `backend/app/schemas/member.py`
- Create: `backend/app/repositories/member_repository.py`
- Create: `backend/app/api/members.py`
- Modify: `backend/app/main.py`

- [ ] **Step 1: 实现成员 model**

```python
from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class Member(Base):
    __tablename__ = "members"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    member_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    relation: Mapped[str] = mapped_column(String(50), nullable=False)
    gender: Mapped[str] = mapped_column(String(10), nullable=False)
    birth_year: Mapped[int] = mapped_column(Integer, nullable=False)
    phone: Mapped[str | None] = mapped_column(String(30), nullable=True)
    height_cm: Mapped[int | None] = mapped_column(Integer, nullable=True)
    weight_kg: Mapped[int | None] = mapped_column(Integer, nullable=True)
    health_tags: Mapped[str | None] = mapped_column(Text, nullable=True)
    allergies: Mapped[str | None] = mapped_column(String(255), nullable=True)
    taste_preferences: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )
```

- [ ] **Step 2: 实现成员 schema、repository 和 API**

```python
@router.post("", response_model=MemberDetail)
def create_member(request: MemberCreateRequest, db: Session = Depends(get_db)):
    repository = SqlAlchemyMemberRepository(db)
    return repository.create_member(request)
```

- [ ] **Step 3: 注册路由并加载 model**

```python
from app.api.members import router as members_router
from app.models import member as _member_models

app.include_router(members_router)
```

- [ ] **Step 4: 运行成员 API 测试**

Run: `cd backend && pytest tests/test_api_members.py -v`
Expected: PASS

### Task 3: 先写报告关联成员的失败测试

**Files:**
- Modify: `backend/tests/test_api_kb.py`

- [ ] **Step 1: 写上传必须带 member_id 的失败测试**

```python
def test_kb_upload_requires_member_id():
    app = create_app()
    app.dependency_overrides[get_db] = lambda: FakeDb()
    client = TestClient(app)

    response = client.post(
        "/kb/upload",
        files={"file": ("report.pdf", b"%PDF-1.4 fake", "application/pdf")},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "请选择家人"
```

- [ ] **Step 2: 写文档列表返回成员信息的失败测试**

```python
def test_kb_document_list_contains_member_info():
    app = create_app()
    app.dependency_overrides[get_db] = lambda: FakeDb()
    client = TestClient(app)

    response = client.get("/kb/documents")

    assert response.status_code == 200
    assert response.json()[0]["member_id"] == "mem_1"
    assert response.json()[0]["member_name"] == "王秀英"
```

- [ ] **Step 3: 运行 KB 测试确认失败**

Run: `cd backend && pytest tests/test_api_kb.py -v`
Expected: FAIL，原因是缺少成员校验或返回字段

### Task 4: 实现 KB 成员关联

**Files:**
- Modify: `backend/app/models/kb.py`
- Modify: `backend/app/schemas/kb.py`
- Modify: `backend/app/repositories/kb_repository.py`
- Modify: `backend/app/services/kb_service.py`
- Modify: `backend/app/api/kb.py`
- Modify: `backend/app/main.py`

- [ ] **Step 1: 为文档模型和 schema 增加成员字段**

```python
member_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
```

- [ ] **Step 2: 修改上传接口要求 member_id，并校验成员存在**

```python
member_id: str = Form(...)
if not member_id.strip():
    raise HTTPException(status_code=400, detail="请选择家人")
```

- [ ] **Step 3: 修改 repository 列表和详情返回成员信息**

```python
return self.db.query(KbDocument).order_by(KbDocument.created_at.desc()).all()
```

并补充 `member_name`、`member_relation` 的序列化来源。

- [ ] **Step 4: 运行 KB 测试**

Run: `cd backend && pytest tests/test_api_kb.py -v`
Expected: PASS

### Task 5: 写前端 members API 和页面的最小失败验证

**Files:**
- Create: `frontend/src/api/members.ts`
- Modify: `frontend/src/main.tsx`
- Modify: `frontend/src/components/AppShell.tsx`

- [ ] **Step 1: 新增 members API 定义**

```ts
export async function listMembers(): Promise<MemberListItem[]> {
  const response = await fetch(`${API_BASE}/members`);
  if (!response.ok) throw new Error('获取家人列表失败');
  return response.json();
}
```

- [ ] **Step 2: 注册 members 路由占位页**

```tsx
<Route path="/members" element={<MembersPage />} />
```

- [ ] **Step 3: 将侧边栏家人导航改为可点击链接**

```ts
{ id: 'members', icon: Users, label: '家人', href: '/members' }
```

### Task 6: 实现家人页面与上传弹窗联动

**Files:**
- Create: `frontend/src/pages/MembersPage.tsx`
- Create: `frontend/src/pages/MemberFormPage.tsx`
- Create: `frontend/src/pages/MemberDetailPage.tsx`
- Create: `frontend/src/components/members/MemberCard.tsx`
- Create: `frontend/src/components/members/MemberForm.tsx`
- Modify: `frontend/src/components/UploadReportDialog.tsx`
- Modify: `frontend/src/pages/ReportsPage.tsx`
- Modify: `frontend/src/api/kb.ts`
- Modify: `frontend/src/components/ReportToolbar.tsx`
- Modify: `frontend/src/components/ReportCard.tsx`
- Modify: `frontend/src/styles.css`

- [ ] **Step 1: 实现家人列表页，先拉通列表展示**

```tsx
const membersQuery = useQuery({ queryKey: ['members'], queryFn: listMembers });
```

- [ ] **Step 2: 实现新增/编辑表单页**

```tsx
const mutation = useMutation({ mutationFn: createMember })
```

- [ ] **Step 3: 实现详情页与成员报告列表**

```tsx
const documentsQuery = useQuery({ queryKey: ['member-documents', memberId], queryFn: () => listMemberDocuments(memberId!) })
```

- [ ] **Step 4: 改造上传弹窗支持成员必选**

```tsx
onUpload({ file, memberId })
```

- [ ] **Step 5: 改造报告页按真实成员筛选**

```tsx
const [memberId, setMemberId] = useState<string>('all')
```

- [ ] **Step 6: 运行前端构建**

Run: `cd frontend && npm run build`
Expected: PASS

### Task 7: 全量验证

**Files:**
- Modify: `docs/superpowers/specs/2026-06-13-members-design.md`

- [ ] **Step 1: 运行后端测试**

Run: `cd backend && pytest`
Expected: PASS

- [ ] **Step 2: 运行前端构建**

Run: `cd frontend && npm run build`
Expected: PASS

- [ ] **Step 3: 更新 spec 中的实现状态说明（如有必要）**

```md
本设计已按实现计划落地，实际代码以当前仓库状态为准。
```
