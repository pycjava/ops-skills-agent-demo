import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db.base_class import Base

if TYPE_CHECKING:
    from models.conversation import Conversation
    from models.inspection_task import InspectionTask


class InspectionTaskRun(Base):
    __tablename__ = "inspection_task_runs"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    task_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("inspection_tasks.id", ondelete="CASCADE")
    )
    trigger_type: Mapped[str] = mapped_column(String(20))
    status: Mapped[str] = mapped_column(String(20), default="running")
    conversation_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("conversations.id", ondelete="SET NULL"), nullable=True
    )
    started_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    task: Mapped["InspectionTask"] = relationship(back_populates="runs")
    conversation: Mapped["Conversation | None"] = relationship()

    def to_dict(self):
        return {
            "id": self.id,
            "task_id": self.task_id,
            "trigger_type": self.trigger_type,
            "status": self.status,
            "conversation_id": self.conversation_id,
            "started_at": (
                self.started_at.isoformat(timespec="milliseconds")
                if self.started_at
                else None
            ),
            "finished_at": (
                self.finished_at.isoformat(timespec="milliseconds")
                if self.finished_at
                else None
            ),
            "error_message": self.error_message,
        }
