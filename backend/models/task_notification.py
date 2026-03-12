import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db.base_class import Base

if TYPE_CHECKING:
    from models.conversation import Conversation
    from models.inspection_task import InspectionTask
    from models.inspection_task_run import InspectionTaskRun


class TaskNotification(Base):
    __tablename__ = "task_notifications"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    task_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("inspection_tasks.id", ondelete="CASCADE")
    )
    task_run_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("inspection_task_runs.id", ondelete="CASCADE")
    )
    conversation_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("conversations.id", ondelete="SET NULL"), nullable=True
    )
    status: Mapped[str] = mapped_column(String(20))
    title: Mapped[str] = mapped_column(String(200))
    summary: Mapped[str] = mapped_column(Text)
    report_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    report_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    read_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.now, server_default=func.now()
    )

    task: Mapped["InspectionTask"] = relationship()
    task_run: Mapped["InspectionTaskRun"] = relationship()
    conversation: Mapped["Conversation | None"] = relationship()

    def to_dict(self):
        return {
            "id": self.id,
            "task_id": self.task_id,
            "task_run_id": self.task_run_id,
            "conversation_id": self.conversation_id,
            "status": self.status,
            "title": self.title,
            "summary": self.summary,
            "report_name": self.report_name,
            "report_path": self.report_path,
            "read_at": self.read_at.isoformat(timespec="milliseconds") if self.read_at else None,
            "created_at": (
                self.created_at.isoformat(timespec="milliseconds")
                if self.created_at
                else None
            ),
        }
