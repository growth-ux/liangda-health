from datetime import date, datetime

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
        return binding

    def touch_binding_sync(self, member_id: str, synced_at: datetime) -> DeviceBinding | None:
        binding = self.get_binding(member_id)
        if binding is None:
            return None
        binding.last_sync_at = synced_at
        binding.updated_at = synced_at
        return binding

    def list_metrics_for_dates(self, member_id: str, dates: list[date]) -> list[DeviceDailyMetric]:
        if not dates:
            return []
        return (
            self.db.query(DeviceDailyMetric)
            .filter(DeviceDailyMetric.member_id == member_id, DeviceDailyMetric.metric_date.in_(dates))
            .order_by(DeviceDailyMetric.metric_date.asc())
            .all()
        )

    def create_metric(
        self,
        *,
        member_id: str,
        metric_date: date,
        steps: int,
        avg_heart_rate: int,
        systolic_bp: int,
        diastolic_bp: int,
        sleep_hours: float,
        blood_oxygen: int,
        sync_status: str,
        sync_source: str,
    ) -> DeviceDailyMetric:
        metric = DeviceDailyMetric(
            member_id=member_id,
            metric_date=metric_date,
            steps=steps,
            avg_heart_rate=avg_heart_rate,
            systolic_bp=systolic_bp,
            diastolic_bp=diastolic_bp,
            sleep_hours=sleep_hours,
            blood_oxygen=blood_oxygen,
            sync_status=sync_status,
            sync_source=sync_source,
        )
        self.db.add(metric)
        return metric
