from __future__ import annotations

import json
from collections import OrderedDict
from datetime import date, datetime, timedelta

from sqlalchemy.orm import Session

from app.models.device import DeviceDailyMetric
from app.models.kb import KbDocument
from app.models.member import Member
from app.repositories.notice_repository import SqlAlchemyNoticeRepository
from app.schemas.notice import NoticeCounts, NoticeGroup, NoticeItem, NoticeListResponse, NoticeSummaryResponse


class NoticeService:
    def __init__(self, db: Session):
        self.db = db
        self.repository = SqlAlchemyNoticeRepository(db)

    def list_notices(self, category: str = "all") -> NoticeListResponse:
        self.ensure_rule_notices()
        filter_category = None if category == "all" else category
        notices = self.repository.list_notices(filter_category)
        return NoticeListResponse(counts=self._counts(), groups=self._groups(notices))

    def summary(self) -> NoticeSummaryResponse:
        self.ensure_rule_notices()
        return NoticeSummaryResponse(unread=self.repository.unread_count())

    def mark_read(self, notice_id: str):
        return self.repository.update_status(notice_id, "read")

    def snooze(self, notice_id: str):
        return self.repository.update_status(notice_id, "snoozed")

    def done(self, notice_id: str):
        return self.repository.update_status(notice_id, "done")

    def mark_all_read(self) -> int:
        return self.repository.mark_all_read()

    def ensure_rule_notices(self) -> None:
        created = False
        if not self.repository.has_any_notice():
            self.repository.create_notice(
                category="system",
                level="info",
                title="欢迎使用粮达健康",
                description="您的家庭健康档案已创建，添加家人并上传第一份报告开始吧！",
                source="system",
                target_type="upload",
                action_text="上传",
                dedupe_key="welcome",
            )
            created = True

        created = self._generate_report_ready_notices() or created
        created = self._generate_device_notices() or created
        created = self._generate_report_reminders() or created
        created = self._generate_recommendation_notices() or created
        if created:
            self.db.commit()

    def _generate_report_ready_notices(self) -> bool:
        created = False
        members = self._member_map()
        documents = self.db.query(KbDocument).filter(KbDocument.status == "ready").all()
        for document in documents:
            dedupe_key = f"report_ready:{document.document_id}"
            if self.repository.exists_dedupe_key(dedupe_key):
                continue
            member = members.get(document.member_id)
            member_text = member.name if member else document.patient_name or "家人"
            self.repository.create_notice(
                category="system",
                level="info",
                title="新报告已识别",
                description=f"{member_text} 的体检报告已识别完成，报告内容已归档。",
                source="system",
                member_id=document.member_id,
                target_type="report",
                target_id=document.document_id,
                action_text="查看",
                dedupe_key=dedupe_key,
                created_at=document.updated_at,
            )
            created = True
        return created

    def _generate_device_notices(self) -> bool:
        created = False
        for member in self.db.query(Member).all():
            metrics = (
                self.db.query(DeviceDailyMetric)
                .filter(DeviceDailyMetric.member_id == member.member_id)
                .order_by(DeviceDailyMetric.metric_date.desc())
                .limit(2)
                .all()
            )
            if not metrics:
                continue
            latest = metrics[0]
            if latest.systolic_bp >= 140 or latest.diastolic_bp >= 90:
                dedupe_key = f"bp_high:{member.member_id}:{latest.metric_date.isoformat()}"
                if not self.repository.exists_dedupe_key(dedupe_key):
                    self.repository.create_notice(
                        category="health_alert",
                        level="danger",
                        title=f"{member.relation}血压偏高",
                        description=(
                            f"最近一次血压为 {latest.systolic_bp}/{latest.diastolic_bp} mmHg，"
                            "已超过建议关注阈值。已为您推荐相关健康专区。"
                        ),
                        source="housekeeper",
                        member_id=member.member_id,
                        target_type="chat",
                        action_text="查看",
                        secondary_action="稍后",
                        dedupe_key=dedupe_key,
                    )
                    created = True
                continue
            if len(metrics) < 2:
                continue
            previous = metrics[1]
            if latest.systolic_bp < previous.systolic_bp and latest.diastolic_bp < previous.diastolic_bp:
                dedupe_key = f"bp_improved:{member.member_id}:{latest.metric_date.isoformat()}"
                if self.repository.exists_dedupe_key(dedupe_key):
                    continue
                self.repository.create_notice(
                    category="health_alert",
                    level="success",
                    title=f"{member.relation}血压改善",
                    description="最近一次血压较前一天下降，继续保持。",
                    source="housekeeper",
                    member_id=member.member_id,
                    target_type="devices",
                    action_text="收到",
                    dedupe_key=dedupe_key,
                )
                created = True
        return created

    def _generate_report_reminders(self) -> bool:
        created = False
        today = date.today()
        stale_before = today - timedelta(days=183)
        for member in self.db.query(Member).all():
            latest_document = (
                self.db.query(KbDocument)
                .filter(KbDocument.member_id == member.member_id)
                .order_by(KbDocument.exam_date.desc(), KbDocument.created_at.desc())
                .first()
            )
            should_remind = latest_document is None
            if latest_document and latest_document.exam_date:
                should_remind = latest_document.exam_date < stale_before
            if latest_document and latest_document.exam_date is None:
                should_remind = latest_document.created_at.date() < stale_before
            if not should_remind:
                continue
            dedupe_key = f"report_reminder:{member.member_id}:{today.isoformat()}"
            if self.repository.exists_dedupe_key(dedupe_key):
                continue
            description = f"{member.name}（{member.relation}）的最新体检报告已超过 6 个月，建议上传新报告。"
            if latest_document is None:
                description = f"{member.name}（{member.relation}）还没有体检报告，建议上传第一份报告。"
            self.repository.create_notice(
                category="reminder",
                level="info",
                title="建议补充报告",
                description=description,
                source="housekeeper",
                member_id=member.member_id,
                target_type="upload",
                action_text="上传",
                dedupe_key=dedupe_key,
            )
            created = True
        return created

    def _generate_recommendation_notices(self) -> bool:
        created = False
        today = date.today().isoformat()
        for member in self.db.query(Member).all():
            tags = self._health_tags(member.health_tags)
            if not self._has_recommendation_tag(tags):
                continue
            dedupe_key = f"mall_recommendation:{member.member_id}:{today}"
            if self.repository.exists_dedupe_key(dedupe_key):
                continue
            self.repository.create_notice(
                category="recommendation",
                level="info",
                title="3 个新推荐商品",
                description=f"根据家庭最新健康数据，管家为您推荐了适合 {member.relation} 的健康商品。",
                source="housekeeper",
                member_id=member.member_id,
                target_type="mall",
                action_text="查看",
                dedupe_key=dedupe_key,
            )
            created = True
        return created

    def _counts(self) -> NoticeCounts:
        return NoticeCounts(
            all=self.repository.count_by_category(),
            health_alert=self.repository.count_by_category("health_alert"),
            system=self.repository.count_by_category("system"),
            recommendation=self.repository.count_by_category("recommendation"),
            unread=self.repository.unread_count(),
        )

    def _groups(self, notices) -> list[NoticeGroup]:
        grouped: OrderedDict[str, list[NoticeItem]] = OrderedDict()
        for notice in notices:
            label = self._group_label(notice.created_at)
            grouped.setdefault(label, []).append(self._to_item(notice))
        return [NoticeGroup(label=label, items=items) for label, items in grouped.items()]

    def _to_item(self, notice) -> NoticeItem:
        return NoticeItem(
            notice_id=notice.notice_id,
            category=notice.category,
            level=notice.level,
            title=notice.title,
            description=notice.description,
            source=notice.source,
            source_text=self._source_text(notice.source),
            status=notice.status,
            created_at=notice.created_at,
            meta_text=f"{self._time_text(notice.created_at)} · {self._source_text(notice.source)}",
            target_url=self._target_url(notice.target_type, notice.target_id),
            action_text=notice.action_text,
            secondary_action=notice.secondary_action,
        )

    @staticmethod
    def _group_label(created_at: datetime) -> str:
        current = date.today()
        created_date = created_at.date()
        if created_date == current:
            return "今天"
        if created_date >= current - timedelta(days=6):
            return "本周"
        return "更早"

    @staticmethod
    def _source_text(source: str) -> str:
        return "来自管家" if source == "housekeeper" else "来自系统"

    @staticmethod
    def _time_text(created_at: datetime) -> str:
        now = datetime.utcnow()
        if created_at.date() == now.date():
            delta_seconds = max(0, int((now - created_at).total_seconds()))
            if delta_seconds < 3600:
                return f"{max(1, delta_seconds // 60)} 分钟前"
            return f"{delta_seconds // 3600} 小时前"
        if created_at.date() == (now.date() - timedelta(days=1)):
            return f"昨天 {created_at.strftime('%H:%M')}"
        return created_at.strftime("%Y-%m-%d")

    @staticmethod
    def _target_url(target_type: str | None, target_id: str | None) -> str | None:
        if target_type == "chat":
            return "/chat"
        if target_type == "report" and target_id:
            return f"/reports/{target_id}"
        if target_type == "upload":
            return "/reports"
        if target_type == "mall":
            return "/mall"
        if target_type == "member" and target_id:
            return f"/members/{target_id}"
        if target_type == "devices":
            return "/devices"
        return None

    def _member_map(self) -> dict[str, Member]:
        return {member.member_id: member for member in self.db.query(Member).all()}

    @staticmethod
    def _health_tags(raw: str | None) -> list[str]:
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
    def _has_recommendation_tag(tags: list[str]) -> bool:
        keywords = ("高血压", "高血脂", "糖尿病", "控糖", "低钠", "补钙", "缺钙", "骨质疏松", "低脂")
        return any(any(keyword in tag for keyword in keywords) for tag in tags)
