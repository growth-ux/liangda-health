from __future__ import annotations

import hashlib
import json
from datetime import date, datetime, timedelta
from random import Random

from app.repositories.device_repository import SqlAlchemyDeviceRepository
from app.repositories.member_repository import SqlAlchemyMemberRepository
from app.core.time import utc_now
from app.schemas.device import (
    DeviceBloodPressureChartPoint,
    DeviceChartPoint,
    DeviceCharts,
    DeviceHourlyChartPoint,
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
        member = self.member_repository.get_member(member_id)
        if member is None:
            return

        target_dates = self._recent_7_days()
        existing_by_date = {
            metric.metric_date: metric
            for metric in self.device_repository.list_metrics_for_dates(member_id, target_dates)
        }

        binding = self.device_repository.get_binding(member_id)
        if binding is None:
            binding = self.device_repository.create_binding(member_id, self._battery_level(member_id))

        for metric_date in target_dates:
            values = self._build_mock_metric(
                member.birth_year,
                member.member_id,
                metric_date,
                self._safe_health_tags(member.health_tags),
            )
            if metric_date in existing_by_date:
                metric = existing_by_date[metric_date]
                if metric.sync_source == "mock":
                    metric.steps = values["steps"]
                    metric.avg_heart_rate = values["avg_heart_rate"]
                    metric.systolic_bp = values["systolic_bp"]
                    metric.diastolic_bp = values["diastolic_bp"]
                    metric.sleep_hours = values["sleep_hours"]
                    metric.blood_oxygen = values["blood_oxygen"]
                continue
            metric = self.device_repository.create_metric(
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
            existing_by_date[metric_date] = metric

        self.device_repository.touch_binding_sync(member_id, utc_now())
        self.db.commit()

    def get_overview(self, member_id: str) -> DeviceOverviewResponse:
        self.ensure_recent_7_days(member_id)

        member = self.member_repository.get_member(member_id)
        if member is None:
            raise ValueError("member not found")

        binding = self.device_repository.get_binding(member_id)
        metrics = self.device_repository.list_metrics_for_dates(member_id, self._recent_7_days())
        if binding is None or len(metrics) != 7:
            raise ValueError("device data not ready")
        latest = metrics[-1]
        heart_rate_24h = self._heart_rate_24h_points(member_id, latest)
        blood_pressure_24h = self._blood_pressure_24h_points(member_id, latest)

        return DeviceOverviewResponse(
            member=DeviceOverviewMember(
                member_id=member.member_id,
                name=member.name,
                relation=member.relation,
            ),
            device=DeviceOverviewBinding(
                device_name=binding.device_name,
                device_status=binding.device_status,
                battery_level=binding.battery_level,
                last_sync_at=binding.last_sync_at,
            ),
            summary=DeviceSummary(
                steps=latest.steps,
                steps_target=10000,
                avg_heart_rate=latest.avg_heart_rate,
                heart_rate_range_text=self._heart_rate_range_text(heart_rate_24h),
                sleep_hours=round(latest.sleep_hours, 1),
                sleep_target=8.0,
                blood_pressure=f"{latest.systolic_bp}/{latest.diastolic_bp}",
                blood_oxygen=latest.blood_oxygen,
            ),
            charts=DeviceCharts(
                steps_7d=self._chart_points(metrics, "steps"),
                heart_rate_24h=heart_rate_24h,
                sleep_7d=self._chart_points(metrics, "sleep_hours"),
                blood_pressure_24h=blood_pressure_24h,
            ),
            sync_logs=self._build_sync_logs(binding.last_sync_at, metrics),
        )

    @staticmethod
    def _recent_7_days() -> list[date]:
        return [date.today() - timedelta(days=offset) for offset in range(6, -1, -1)]

    @staticmethod
    def _chart_points(metrics, field_name: str) -> list[DeviceChartPoint]:
        points: list[DeviceChartPoint] = []
        for metric in metrics:
            value = getattr(metric, field_name)
            if isinstance(value, float):
                value = round(value, 1)
            points.append(DeviceChartPoint(date=metric.metric_date.isoformat(), value=value))
        return points

    @staticmethod
    def _recent_24_hours() -> list[datetime]:
        current_hour = datetime.now().replace(minute=0, second=0, microsecond=0)
        return [current_hour - timedelta(hours=offset) for offset in range(23, -1, -1)]

    @staticmethod
    def _hourly_rng(member_id: str, metric_name: str, hour_at: datetime) -> Random:
        seed_text = f"{member_id}:{metric_name}:{hour_at.strftime('%Y-%m-%dT%H')}"
        seed = int(hashlib.sha256(seed_text.encode("utf-8")).hexdigest()[:16], 16)
        return Random(seed)

    @classmethod
    def _heart_rate_24h_points(cls, member_id: str, latest) -> list[DeviceHourlyChartPoint]:
        points: list[DeviceHourlyChartPoint] = []
        for hour_at in cls._recent_24_hours():
            rng = cls._hourly_rng(member_id, "heart_rate", hour_at)
            hour = hour_at.hour
            resting_adjustment = -4 if 0 <= hour <= 5 else 0
            daytime_adjustment = 3 if 9 <= hour <= 20 else 0
            value = latest.avg_heart_rate + resting_adjustment + daytime_adjustment + rng.randint(-5, 5)
            points.append(
                DeviceHourlyChartPoint(
                    time=hour_at.strftime("%H:%M"),
                    value=max(58, min(112, value)),
                )
            )
        return points

    @classmethod
    def _blood_pressure_24h_points(cls, member_id: str, latest) -> list[DeviceBloodPressureChartPoint]:
        points: list[DeviceBloodPressureChartPoint] = []
        for hour_at in cls._recent_24_hours():
            rng = cls._hourly_rng(member_id, "blood_pressure", hour_at)
            hour = hour_at.hour
            resting_adjustment = -5 if 0 <= hour <= 5 else 0
            daytime_adjustment = 4 if 8 <= hour <= 21 else 0
            systolic = latest.systolic_bp + resting_adjustment + daytime_adjustment + rng.randint(-4, 4)
            diastolic = latest.diastolic_bp + resting_adjustment // 2 + daytime_adjustment // 2 + rng.randint(-3, 3)
            points.append(
                DeviceBloodPressureChartPoint(
                    time=hour_at.strftime("%H:%M"),
                    systolic=max(105, min(166, systolic)),
                    diastolic=max(65, min(104, diastolic)),
                )
            )
        return points

    @staticmethod
    def _heart_rate_range_text(points: list[DeviceHourlyChartPoint]) -> str:
        values = [int(point.value) for point in points]
        return f"最近24小时 {min(values)}-{max(values)} 次/分"

    @staticmethod
    def _build_sync_logs(last_sync_at: datetime | None, metrics) -> list[DeviceSyncLogItem]:
        if last_sync_at is None:
            return []

        seen_dates = set()
        logs = [
            DeviceSyncLogItem(
                date=last_sync_at.date().isoformat(),
                status="success",
                message="每日自动同步成功",
                time=last_sync_at.strftime("%H:%M"),
            )
        ]
        seen_dates.add(last_sync_at.date().isoformat())
        for metric in reversed(metrics[-3:]):
            metric_date = metric.metric_date.isoformat()
            if metric_date in seen_dates:
                continue
            logs.append(
                DeviceSyncLogItem(
                    date=metric_date,
                    status="success",
                    message="每日自动同步成功",
                    time="08:30",
                )
            )
            seen_dates.add(metric_date)
        return logs[:4]

    def sync_and_get_overview(self, member_id: str) -> DeviceOverviewResponse:
        self.ensure_recent_7_days(member_id)
        return self.get_overview(member_id)

    @staticmethod
    def _battery_level(member_id: str) -> int:
        digest = hashlib.sha256(f"battery:{member_id}".encode("utf-8")).hexdigest()
        return 55 + (int(digest[:2], 16) % 41)

    @staticmethod
    def _safe_health_tags(raw: str | None) -> list[str]:
        if not raw:
            return []
        try:
            value = json.loads(raw)
        except json.JSONDecodeError:
            return []
        if not isinstance(value, list):
            return []
        return [str(item) for item in value]

    @staticmethod
    def _has_tag(health_tags: list[str], keywords: tuple[str, ...]) -> bool:
        return any(any(keyword in tag for keyword in keywords) for tag in health_tags)

    @classmethod
    def _build_mock_metric(
        cls,
        birth_year: int,
        member_id: str,
        metric_date: date,
        health_tags: list[str],
    ) -> dict[str, int | float]:
        age = max(0, date.today().year - birth_year)
        seed = int(hashlib.sha256(f"{member_id}:{metric_date.isoformat()}".encode("utf-8")).hexdigest()[:16], 16)
        rng = Random(seed)
        weekend = 1 if metric_date.weekday() >= 5 else 0

        steps = 4200 + rng.randint(0, 5200) - max(0, age - 60) * 18 + weekend * 900
        avg_heart_rate = 64 + rng.randint(0, 16) + max(0, age - 60) // 8
        systolic_bp = 118 + rng.randint(0, 14) + max(0, age - 60) // 4
        diastolic_bp = 72 + rng.randint(0, 10) + max(0, age - 60) // 8
        sleep_hours = 6.0 + rng.random() * 1.8 + weekend * 0.4
        blood_oxygen = 96 + rng.randint(0, 3)

        if cls._has_tag(health_tags, ("高血压",)):
            systolic_bp += 12 + rng.randint(0, 10)
            diastolic_bp += 6 + rng.randint(0, 6)
            avg_heart_rate += rng.randint(0, 3)

        if cls._has_tag(health_tags, ("糖尿病", "高血脂", "超重")):
            steps -= 800 + rng.randint(0, 1200)
            avg_heart_rate += 3 + rng.randint(0, 5)
            systolic_bp += rng.randint(3, 8)
            sleep_hours -= 0.3 + rng.random() * 0.5

        if cls._has_tag(health_tags, ("心血管",)):
            avg_heart_rate += 7 + rng.randint(0, 8)
            systolic_bp += rng.randint(4, 10)
            blood_oxygen -= rng.randint(1, 2)

        if cls._has_tag(health_tags, ("痛风", "骨质疏松", "胃肠")):
            steps -= 500 + rng.randint(0, 900)
            sleep_hours -= 0.2 + rng.random() * 0.6

        return {
            "steps": max(3000, min(12000, steps)),
            "avg_heart_rate": max(62, min(108, avg_heart_rate)),
            "systolic_bp": max(118, min(158, systolic_bp)),
            "diastolic_bp": max(72, min(100, diastolic_bp)),
            "sleep_hours": round(max(5.0, min(8.6, sleep_hours)), 1),
            "blood_oxygen": max(93, min(99, blood_oxygen)),
        }
