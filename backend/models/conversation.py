import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from agent_profiles import resolve_known_agent_id
from sqlalchemy import DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db.base_class import Base

if TYPE_CHECKING:
    from models.conversation_attachment import ConversationAttachment
    from models.inspection_task import InspectionTask
    from models.message import Message


class Conversation(Base):
    __tablename__ = "conversations"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    title: Mapped[str] = mapped_column(String(200), default="新对话")
    source: Mapped[str] = mapped_column(String(20), default="web", server_default="web")
    agent_id: Mapped[str] = mapped_column(
        String(50), default="general", server_default="general"
    )
    source_task_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    source_task_run_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    source_task_trigger_type: Mapped[str | None] = mapped_column(
        String(20), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    messages: Mapped[list["Message"]] = relationship(
        back_populates="conversation",
        cascade="all, delete-orphan",
        order_by="Message.created_at",
    )
    attachments: Mapped[list["ConversationAttachment"]] = relationship(
        back_populates="conversation",
        cascade="all, delete-orphan",
        order_by="ConversationAttachment.created_at",
    )
    inspection_tasks: Mapped[list["InspectionTask"]] = relationship(
        back_populates="source_conversation",
        foreign_keys="InspectionTask.source_conversation_id",
    )

    def to_dict(self):
        return {
            "id": self.id,
            "title": self.title,
            "source": self.source,
            "agent_id": resolve_known_agent_id(
                self.agent_id,
                default_on_unknown=True,
            ),
            "source_task_id": self.source_task_id,
            "source_task_run_id": self.source_task_run_id,
            "source_task_trigger_type": self.source_task_trigger_type,
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
