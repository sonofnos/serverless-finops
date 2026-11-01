import uuid
import enum
from sqlalchemy import String, Text, Boolean, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import mapped_column, Mapped
from .base import Base, TimestampMixin


class OutboxEvent(Base, TimestampMixin):
    """
    Transactional outbox: events written in the same DB transaction as the
    business write and published to SQS by the background processor.
    Guarantees at-least-once delivery even if Lambda crashes before the SQS
    publish completes.
    """

    __tablename__ = "outbox_events"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    event_type: Mapped[str] = mapped_column(String(128), nullable=False)
    payload: Mapped[str] = mapped_column(Text, nullable=False)  # JSON string
    published: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    sqs_message_id: Mapped[str | None] = mapped_column(String(128), nullable=True)

    __table_args__ = (Index("ix_outbox_unpublished", "published"),)
