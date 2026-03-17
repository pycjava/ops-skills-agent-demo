import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from agent_profiles import resolve_known_agent_id
from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db.base_class import Base

if TYPE_CHECKING:
    from models.conversation import Conversation


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    conversation_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("conversations.id", ondelete="CASCADE")
    )
    role: Mapped[str] = mapped_column(String(20))
    content: Mapped[str] = mapped_column(Text, default="")
    type: Mapped[str] = mapped_column(
        String(20), default="text"
    )  # text / tool_call / tool_result / error
    agent_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    tool_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    tool_input: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    attachments_snapshot: Mapped[list[dict] | None] = mapped_column(JSON, nullable=True)
    thinking: Mapped[str | None] = mapped_column(Text, nullable=True)
    asset_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    asset_mime_type: Mapped[str | None] = mapped_column(String(255), nullable=True)
    asset_source: Mapped[str | None] = mapped_column(String(100), nullable=True)
    asset_alt: Mapped[str | None] = mapped_column(Text, nullable=True)
    asset_width: Mapped[int | None] = mapped_column(Integer, nullable=True)
    asset_height: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.now, server_default=func.now()
    )

    conversation: Mapped["Conversation"] = relationship(back_populates="messages")

    def to_dict(self):
        asset_url = None
        if self.asset_path:
            from services.assistant_images import build_assistant_image_asset_url

            asset_url = build_assistant_image_asset_url(
                self.conversation_id,
                self.id,
            )

        return {
            "id": self.id,
            "conversation_id": self.conversation_id,
            "role": self.role,
            "content": self.content,
            "type": self.type,
            "agent_id": resolve_known_agent_id(
                self.agent_id,
                allow_none=True,
                default_on_unknown=True,
            ),
            "tool_name": self.tool_name,
            "tool_input": self.tool_input,
            "attachments_snapshot": self.attachments_snapshot,
            "thinking": self.thinking,
            "asset_path": self.asset_path,
            "asset_url": asset_url,
            "asset_mime_type": self.asset_mime_type,
            "asset_source": self.asset_source,
            "asset_alt": self.asset_alt,
            "asset_width": self.asset_width,
            "asset_height": self.asset_height,
            "created_at": (
                self.created_at.isoformat(timespec="milliseconds")
                if self.created_at
                else None
            ),
        }
