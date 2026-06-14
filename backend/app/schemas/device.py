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


class DeviceHourlyChartPoint(BaseModel):
    time: str
    value: float


class DeviceBloodPressureChartPoint(BaseModel):
    time: str
    systolic: int
    diastolic: int


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
