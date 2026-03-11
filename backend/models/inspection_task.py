import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db.base_class import Base

if TYPE_CHECKING:
    from models.conversation import Conversation
    from models.inspection_task_run import InspectionTaskRun


class InspectionTask(Base):
    __tablename__ = "inspection_tasks"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    name: Mapped[str] = mapped_column(String(200))
    source_conversation_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("conversations.id", ondelete="SET NULL"), nullable=True
    )
    agent_id: Mapped[str] = mapped_column(String(50), default="general")
    skill_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    prompt_template: Mapped[str] = mapped_column(Text)
    target_payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    schedule_type: Mapped[str] = mapped_column(String(20), default="cron")
    cron_expr: Mapped[str] = mapped_column(String(100))
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, server_default="1")
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    next_run_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_status: Mapped[str] = mapped_column(String(20), default="idle")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    source_conversation: Mapped["Conversation | None"] = relationship(
        back_populates="inspection_tasks",
        foreign_keys=[source_conversation_id],
    )
    runs: Mapped[list["InspectionTaskRun"]] = relationship(
        back_populates="task",
        cascade="all, delete-orphan",
        order_by="InspectionTaskRun.started_at.desc()",
    )

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "source_conversation_id": self.source_conversation_id,
            "agent_id": self.agent_id,
            "skill_id": self.skill_id,
            "prompt_template": self.prompt_template,
            "target_payload": self.target_payload,
            "schedule_type": self.schedule_type,
            "cron_expr": self.cron_expr,
            "enabled": self.enabled,
            "last_run_at": (
                self.last_run_at.isoformat(timespec="milliseconds")
                if self.last_run_at
                else None
            ),
            "next_run_at": (
                self.next_run_at.isoformat(timespec="milliseconds")
                if self.next_run_at
                else None
            ),
            "last_status": self.last_status,
            "created_at": (
                self.created_at.isoformat(timespec="milliseconds")
                if self.created_at
                else None
            ),
            "updated_at": (
                self.updated_at.isoformat(timespec="milliseconds")
                if self.updated_at
                else None
            ),
        }
