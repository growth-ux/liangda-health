# Device Overview Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** 实现手环设备总览页闭环，包括设备 overview 接口、启动与手动同步补齐最近 7 天缺失 mock 数据、以及与 `prd/prototype/device.html` 对齐的前端页面。

**Architecture:** 后端新增 `device` 领域，沿用现有 FastAPI + SQLAlchemy 的 model / repository / service / api 分层；设备绑定与日汇总数据都落库，`create_app()` 启动时为现有成员补齐最近 7 天数据。前端新增 `/devices` 页面，通过成员列表 + overview 接口完成渲染，点击同步直接调用 sync 接口并刷新页面。

**Tech Stack:** FastAPI, SQLAlchemy, Pydantic, pytest, React 19, React Router, TanStack Query, TypeScript, Vite

---

### Task 1: 先写设备后端 API 的失败测试

**Files:**
- Create: `backend/tests/test_api_device.py`

- [x] **Step 1: 写 overview 会自动补齐最近 7 天数据的失败测试**

```python
from datetime import date, timedelta

from fastapi.testclient import TestClient

from app.db.session import get_db
from app.main import create_app


def create_member(client: TestClient) -> str:
    response = client.post(
        "/api/members",
        json={
            "name": "王建国",
            "relation": "父亲",
            "gender": "男",
            "birth_year": 1958,
            "height_cm": 170,
            "weight_kg": 68,
            "health_tags": ["高血压"],
        },
    )
    assert response.status_code == 200
    return response.json()["member_id"]


def test_device_overview_returns_recent_7_days(db_session):
    app = create_app()
    app.dependency_overrides[get_db] = lambda: db_session
    client = TestClient(app)

    member_id = create_member(client)

    response = client.get(f"/api/devices/{member_id}/overview")

    assert response.status_code == 200
    payload = response.json()
    assert payload["member"]["member_id"] == member_id
    assert payload["device"]["device_status"] == "connected"
    assert len(payload["charts"]["steps_7d"]) == 7
    assert len(payload["charts"]["heart_rate_24h"]) == 24
    assert len(payload["charts"]["sleep_7d"]) == 7
    assert len(payload["charts"]["blood_pressure_24h"]) == 24

    expected_dates = [
        (date.today() - timedelta(days=offset)).isoformat()
        for offset in range(6, -1, -1)
    ]
    assert [item["date"] for item in payload["charts"]["steps_7d"]] == expected_dates
```

- [x] **Step 2: 写手动同步只补缺失天的失败测试**

```python
from sqlalchemy import text


def test_device_sync_fills_missing_days_only(db_session):
    app = create_app()
    app.dependency_overrides[get_db] = lambda: db_session
    client = TestClient(app)

    member_id = create_member(client)
    overview_response = client.get(f"/api/devices/{member_id}/overview")
    assert overview_response.status_code == 200

    deleted_date = date.today() - timedelta(days=2)
    db_session.execute(
        text(
            """
            DELETE FROM device_daily_metrics
            WHERE member_id = :member_id AND metric_date = :metric_date
            """
        ),
        {"member_id": member_id, "metric_date": deleted_date},
    )
    db_session.commit()

    sync_response = client.post(f"/api/devices/{member_id}/sync")

    assert sync_response.status_code == 200
    payload = sync_response.json()
    assert len(payload["charts"]["steps_7d"]) == 7

    count = db_session.execute(
        text(
            """
            SELECT COUNT(*)
            FROM device_daily_metrics
            WHERE member_id = :member_id
            """
        ),
        {"member_id": member_id},
    ).scalar_one()
    assert count == 7
```

- [x] **Step 3: 写 overview 会自动创建设备绑定和 summary 取最近一天的失败测试**

```python
def test_device_overview_auto_creates_binding_and_uses_latest_day(db_session):
    app = create_app()
    app.dependency_overrides[get_db] = lambda: db_session
    client = TestClient(app)

    member_id = create_member(client)

    response = client.get(f"/api/devices/{member_id}/overview")

    assert response.status_code == 200
    payload = response.json()
    assert payload["device"]["device_name"] == "小米手环 8 Pro"
    assert payload["summary"]["steps"] == payload["charts"]["steps_7d"][-1]["value"]
    assert payload["summary"]["avg_heart_rate"] == payload["charts"]["heart_rate_24h"][-1]["value"]
```

- [x] **Step 4: 运行测试确认失败**

Run: `cd backend && pytest tests/test_api_device.py -v`
Expected: FAIL，原因是 `/api/devices/...` 路由不存在

### Task 2: 实现后端设备数据模型和 schema

**Files:**
- Create: `backend/app/models/device.py`
- Modify: `backend/app/models/__init__.py`
- Create: `backend/app/schemas/device.py`

- [x] **Step 1: 实现设备绑定和日汇总 model**

```python
from datetime import date, datetime

from sqlalchemy import Date, DateTime, Float, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class DeviceBinding(Base):
    __tablename__ = "device_bindings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    member_id: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    device_name: Mapped[str] = mapped_column(String(100), nullable=False)
    device_status: Mapped[str] = mapped_column(String(30), nullable=False)
    battery_level: Mapped[int] = mapped_column(Integer, nullable=False)
    last_sync_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )


class DeviceDailyMetric(Base):
    __tablename__ = "device_daily_metrics"
    __table_args__ = (UniqueConstraint("member_id", "metric_date", name="uq_device_member_date"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    member_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    metric_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    steps: Mapped[int] = mapped_column(Integer, nullable=False)
    avg_heart_rate: Mapped[int] = mapped_column(Integer, nullable=False)
    systolic_bp: Mapped[int] = mapped_column(Integer, nullable=False)
    diastolic_bp: Mapped[int] = mapped_column(Integer, nullable=False)
    sleep_hours: Mapped[float] = mapped_column(Float, nullable=False)
    blood_oxygen: Mapped[int] = mapped_column(Integer, nullable=False)
    sync_status: Mapped[str] = mapped_column(String(30), nullable=False)
    sync_source: Mapped[str] = mapped_column(String(30), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )
```

- [x] **Step 2: 在 `backend/app/models/__init__.py` 导出 device 模型**

```python
from app.models.device import DeviceBinding, DeviceDailyMetric

__all__ = ["DeviceBinding", "DeviceDailyMetric"]
```

- [x] **Step 3: 实现 overview 响应 schema**

```python
from datetime import datetime

from pydantic import BaseModel


class DeviceOverviewMember(BaseModel):
    member_id: str
    name: str
    relation: str


class DeviceOverviewBinding(BaseModel):
    device_name: str
    device_status: str
    battery_level: int
    last_sync_at: datetime | None = None


class DeviceSummary(BaseModel):
    steps: int
    steps_target: int
    avg_heart_rate: int
    heart_rate_range_text: str
    sleep_hours: float
    sleep_target: float
    blood_pressure: str
    blood_oxygen: int


class DeviceChartPoint(BaseModel):
    date: str
    value: float


class DeviceCharts(BaseModel):
    steps_7d: list[DeviceChartPoint]
    heart_rate_24h: list[DeviceHourlyChartPoint]
    sleep_7d: list[DeviceChartPoint]
    blood_pressure_24h: list[DeviceBloodPressureChartPoint]


class DeviceSyncLogItem(BaseModel):
    date: str
    status: str
    message: str
    time: str


class DeviceOverviewResponse(BaseModel):
    member: DeviceOverviewMember
    device: DeviceOverviewBinding
    summary: DeviceSummary
    charts: DeviceCharts
    sync_logs: list[DeviceSyncLogItem]
```

- [x] **Step 4: 运行设备测试确认仍失败但进入实现阶段**

Run: `cd backend && pytest tests/test_api_device.py::test_device_overview_returns_recent_7_days -v`
Expected: FAIL，原因是路由或 service 未实现，不应再是建表失败

### Task 3: 实现设备 repository 和 service

**Files:**
- Create: `backend/app/repositories/device_repository.py`
- Create: `backend/app/services/device_service.py`

- [x] **Step 1: 实现 repository 的最小查写能力**

```python
from datetime import date

from sqlalchemy.orm import Session

from app.models.device import DeviceBinding, DeviceDailyMetric


class SqlAlchemyDeviceRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_binding(self, member_id: str) -> DeviceBinding | None:
        return self.db.query(DeviceBinding).filter(DeviceBinding.member_id == member_id).one_or_none()

    def create_binding(self, member_id: str, battery_level: int) -> DeviceBinding:
        binding = DeviceBinding(
            member_id=member_id,
            device_name="小米手环 8 Pro",
            device_status="connected",
            battery_level=battery_level,
        )
        self.db.add(binding)
        self.db.commit()
        self.db.refresh(binding)
        return binding

    def list_metrics_for_dates(self, member_id: str, dates: list[date]) -> list[DeviceDailyMetric]:
        return (
            self.db.query(DeviceDailyMetric)
            .filter(DeviceDailyMetric.member_id == member_id, DeviceDailyMetric.metric_date.in_(dates))
            .order_by(DeviceDailyMetric.metric_date.asc())
            .all()
        )

    def create_metric(self, **kwargs) -> DeviceDailyMetric:
        metric = DeviceDailyMetric(**kwargs)
        self.db.add(metric)
        self.db.commit()
        self.db.refresh(metric)
        return metric
```

- [x] **Step 2: 实现最近 7 天补数与 overview 组装 service**

```python
from datetime import date, datetime, timedelta
from random import Random

from app.repositories.device_repository import SqlAlchemyDeviceRepository
from app.repositories.member_repository import SqlAlchemyMemberRepository
from app.schemas.device import (
    DeviceChartPoint,
    DeviceCharts,
    DeviceOverviewBinding,
    DeviceOverviewMember,
    DeviceOverviewResponse,
    DeviceSummary,
    DeviceSyncLogItem,
)


class DeviceService:
    def __init__(self, db):
        self.db = db
        self.device_repository = SqlAlchemyDeviceRepository(db)
        self.member_repository = SqlAlchemyMemberRepository(db)

    def ensure_recent_7_days(self, member_id: str) -> None:
        target_dates = [date.today() - timedelta(days=offset) for offset in range(6, -1, -1)]
        existing = {
            metric.metric_date: metric
            for metric in self.device_repository.list_metrics_for_dates(member_id, target_dates)
        }
        binding = self.device_repository.get_binding(member_id)
        if binding is None:
            battery_level = self._battery_level(member_id)
            binding = self.device_repository.create_binding(member_id, battery_level)
        for metric_date in target_dates:
            if metric_date not in existing:
                values = self._build_mock_metric(member_id, metric_date)
                self.device_repository.create_metric(
                    member_id=member_id,
                    metric_date=metric_date,
                    steps=values["steps"],
                    avg_heart_rate=values["avg_heart_rate"],
                    systolic_bp=values["systolic_bp"],
                    diastolic_bp=values["diastolic_bp"],
                    sleep_hours=values["sleep_hours"],
                    blood_oxygen=values["blood_oxygen"],
                    sync_status="success",
                    sync_source="mock",
                )
        self.device_repository.touch_binding_sync(member_id, datetime.utcnow())
```

并补充：

- `get_overview(member_id)`：调用 `ensure_recent_7_days` 后组装返回
- `_build_mock_metric(member_id, metric_date)`：根据成员年龄、日期和稳定随机种子生成数据
- `_chart_points(metrics, field_name)`：构造图表点位
- `_heart_rate_range_text(points)`：返回 `最近24小时 xx-xx 次/分`

- [x] **Step 3: 为 repository 补充更新同步时间和读取最近 7 天数据的方法**

```python
from datetime import datetime


def touch_binding_sync(self, member_id: str, synced_at: datetime) -> None:
    binding = self.get_binding(member_id)
    if binding is None:
        return
    binding.last_sync_at = synced_at
    binding.updated_at = synced_at
    self.db.commit()


def list_recent_metrics(self, member_id: str) -> list[DeviceDailyMetric]:
    return (
        self.db.query(DeviceDailyMetric)
        .filter(DeviceDailyMetric.member_id == member_id)
        .order_by(DeviceDailyMetric.metric_date.asc())
        .all()
    )
```

- [x] **Step 4: 运行设备测试确认 service 层逻辑可用**

Run: `cd backend && pytest tests/test_api_device.py -v`
Expected: FAIL 数量减少，剩余失败集中在 API 注册或响应序列化

### Task 4: 接入设备 API 和启动补数

**Files:**
- Create: `backend/app/api/device.py`
- Modify: `backend/app/main.py`

- [x] **Step 1: 实现 overview 和 sync 接口**

```python
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
    return DeviceService(db).get_overview(member_id)


@router.post("/{member_id}/sync", response_model=DeviceOverviewResponse)
def sync_device(member_id: str, db: Session = Depends(get_db)):
    if SqlAlchemyMemberRepository(db).get_member(member_id) is None:
        raise HTTPException(status_code=404, detail="家人不存在")
    service = DeviceService(db)
    service.ensure_recent_7_days(member_id)
    return service.get_overview(member_id)
```

- [x] **Step 2: 在 `create_app()` 中注册路由和加载 model**

```python
from app.api.device import router as device_router
from app.models import device as _device_models

app.include_router(device_router)
```

- [x] **Step 3: 在 `create_app()` 中为所有成员执行启动补数**

```python
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.repositories.member_repository import SqlAlchemyMemberRepository
from app.services.device_service import DeviceService


def ensure_device_seed_data() -> None:
    db: Session = SessionLocal()
    try:
        members = SqlAlchemyMemberRepository(db).list_members()
        service = DeviceService(db)
        for member in members:
            service.ensure_recent_7_days(member.member_id)
    finally:
        db.close()
```

并在 `Base.metadata.create_all(bind=engine)` 和 `ensure_schema_updates()` 之后调用 `ensure_device_seed_data()`。

- [x] **Step 4: 运行设备测试确保全部通过**

Run: `cd backend && pytest tests/test_api_device.py -v`
Expected: PASS

### Task 5: 回归后端现有成员接口和服务启动

**Files:**
- Test: `backend/tests/test_api_members.py`

- [x] **Step 1: 运行成员测试确认设备启动补数没有破坏现有功能**

Run: `cd backend && pytest tests/test_api_members.py -v`
Expected: PASS

- [x] **Step 2: 运行设备与成员组合测试**

Run: `cd backend && pytest tests/test_api_members.py tests/test_api_device.py -v`
Expected: PASS

- [ ] **Step 3: 提交后端部分**

```bash
git add backend/app/api/device.py backend/app/main.py backend/app/models/__init__.py backend/app/models/device.py backend/app/repositories/device_repository.py backend/app/schemas/device.py backend/app/services/device_service.py backend/tests/test_api_device.py
git commit -m "feat: add device overview backend"
```

### Task 6: 实现前端设备 API、类型和页面骨架

**Files:**
- Create: `frontend/src/api/device.ts`
- Create: `frontend/src/types/device.ts`
- Create: `frontend/src/pages/DevicePage.tsx`
- Modify: `frontend/src/main.tsx`
- Modify: `frontend/src/components/AppShell.tsx`

- [x] **Step 1: 定义设备页类型和 API**

```ts
export type DeviceOverviewResponse = {
  member: {
    member_id: string;
    name: string;
    relation: string;
  };
  device: {
    device_name: string;
    device_status: string;
    battery_level: number;
    last_sync_at: string | null;
  };
  summary: {
    steps: number;
    steps_target: number;
    avg_heart_rate: number;
    heart_rate_range_text: string;
    sleep_hours: number;
    sleep_target: number;
    blood_pressure: string;
    blood_oxygen: number;
  };
  charts: {
    steps_7d: { date: string; value: number }[];
    heart_rate_24h: { time: string; value: number }[];
    sleep_7d: { date: string; value: number }[];
    blood_pressure_24h: { time: string; systolic: number; diastolic: number }[];
  };
  sync_logs: {
    date: string;
    status: string;
    message: string;
    time: string;
  }[];
};
```

```ts
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000';

export async function getDeviceOverview(memberId: string): Promise<DeviceOverviewResponse> {
  const response = await fetch(`${API_BASE_URL}/api/devices/${memberId}/overview`);
  if (!response.ok) {
    throw new Error('加载设备数据失败');
  }
  return response.json();
}

export async function syncDevice(memberId: string): Promise<DeviceOverviewResponse> {
  const response = await fetch(`${API_BASE_URL}/api/devices/${memberId}/sync`, {
    method: 'POST',
  });
  if (!response.ok) {
    throw new Error('同步设备数据失败');
  }
  return response.json();
}
```

- [x] **Step 2: 在 `DevicePage.tsx` 中实现成员选择和数据请求骨架**

```tsx
import { useMemo, useState } from 'react';
import { useMutation, useQuery } from '@tanstack/react-query';
import { AppShell } from '../components/AppShell';
import { listMembers } from '../api/members';
import { getDeviceOverview, syncDevice } from '../api/device';

export function DevicePage() {
  const membersQuery = useQuery({
    queryKey: ['members'],
    queryFn: listMembers,
  });
  const [selectedMemberId, setSelectedMemberId] = useState<string | null>(null);

  const selectedId = useMemo(() => {
    if (selectedMemberId) {
      return selectedMemberId;
    }
    return membersQuery.data?.[0]?.member_id ?? null;
  }, [membersQuery.data, selectedMemberId]);

  const overviewQuery = useQuery({
    queryKey: ['device-overview', selectedId],
    queryFn: () => getDeviceOverview(selectedId!),
    enabled: Boolean(selectedId),
  });

  const syncMutation = useMutation({
    mutationFn: (memberId: string) => syncDevice(memberId),
    onSuccess: (data) => {
      overviewQuery.refetch();
    },
  });
```

- [x] **Step 3: 注册 `/devices` 路由和左侧导航入口**

```tsx
<Route path="/devices" element={<DevicePage />} />
```

并在 `AppShell` 导航中加入：

```tsx
{ label: '手环设备', path: '/devices', icon: '⌚' }
```

- [x] **Step 4: 运行前端构建确认类型通过**

Run: `cd frontend && npm run build`
Expected: PASS

### Task 7: 按原型完成设备页视觉和交互

**Files:**
- Modify: `frontend/src/pages/DevicePage.tsx`
- Modify: `frontend/src/styles.css`

- [x] **Step 1: 按原型实现页面结构**

```tsx
return (
  <AppShell title="手环设备">
    <div className="page-banner">
      <span>⌚</span>
      <span>
        为家人绑定手环，<strong>每日自动同步</strong>心率/血压/睡眠/血氧/步数。体征异常会触发聊天预警。
      </span>
    </div>
    <div className="device-role-switch">
      {membersQuery.data?.map((member) => (
        <button
          key={member.member_id}
          className={`device-role-tab ${selectedId === member.member_id ? 'active' : ''}`}
          onClick={() => setSelectedMemberId(member.member_id)}
        >
          {member.name}
        </button>
      ))}
    </div>
  </AppShell>
);
```

并继续补全：

- 设备状态卡
- 步数卡
- 心率卡
- 睡眠卡
- 2 行图表区块
- 同步记录列表
- 同步按钮 loading 状态

- [x] **Step 2: 在 `styles.css` 中增加设备页样式**

```css
.device-role-switch {
  display: flex;
  gap: 10px;
  margin-bottom: 16px;
}

.device-role-tab {
  padding: 8px 28px;
  border-radius: 8px;
  font-size: 15px;
  font-weight: 600;
  cursor: pointer;
  border: 1px solid #d1d5db;
  background: #ffffff;
  color: #111827;
}

.device-role-tab.active {
  background: #10b981;
  color: #ffffff;
  border-color: #10b981;
}
```

并继续补充对应：

- `.device-stat-grid`
- `.device-stat`
- `.device-chart-row`
- `.device-chart-card`
- `.device-sync-list`
- `.device-empty-state`

颜色、间距和层级以 `prd/prototype/device.html` 为准，不额外做风格偏移。

- [x] **Step 3: 接上同步按钮行为和空状态**

```tsx
if (!membersQuery.data?.length) {
  return (
    <AppShell title="手环设备">
      <div className="device-empty-state">请先创建家人档案</div>
    </AppShell>
  );
}
```

同步按钮：

```tsx
<button
  className="device-sync-btn"
  onClick={() => selectedId && syncMutation.mutate(selectedId)}
  disabled={!selectedId || syncMutation.isPending}
>
  {syncMutation.isPending ? '同步中...' : '↻ 同步'}
</button>
```

- [x] **Step 4: 运行前端构建确认页面通过编译**

Run: `cd frontend && npm run build`
Expected: PASS

### Task 8: 启动联调并完成最终验证

**Files:**
- Verify: `backend/app/main.py`
- Verify: `frontend/src/pages/DevicePage.tsx`

- [x] **Step 1: 启动后端服务**

Run: `cd backend && uvicorn app.main:app --reload --port 8000`
Expected: 服务启动成功，访问 `/api/health` 返回 `{"status":"ok"}`

- [x] **Step 2: 启动前端服务**

Run: `cd frontend && npm run dev -- --port 3000`
Expected: Vite 启动成功，页面可通过 `http://localhost:3000/devices` 访问

- [x] **Step 3: 验证设备页**

手动检查：

- 成员 tab 正常切换
- 首次进入页面能看到最近 7 天数据
- 点击同步后页面正常刷新
- 无成员时显示空状态
- 样式与 `prd/prototype/device.html` 结构一致

- [x] **Step 4: 运行完整目标测试**

Run: `cd backend && pytest tests/test_api_members.py tests/test_api_device.py -v`
Expected: PASS

Run: `cd frontend && npm run build`
Expected: PASS

- [ ] **Step 5: 提交前端与联调部分**

```bash
git add frontend/src/api/device.ts frontend/src/components/AppShell.tsx frontend/src/main.tsx frontend/src/pages/DevicePage.tsx frontend/src/styles.css frontend/src/types/device.ts
git commit -m "feat: add device overview page"
```
