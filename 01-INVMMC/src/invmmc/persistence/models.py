from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from invmmc.core.database import Base


def utc_now() -> datetime:
    return datetime.now(UTC)


class ProjectModel(Base):
    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    code: Mapped[str] = mapped_column(String(30), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(200))
    owner: Mapped[str] = mapped_column(String(120))
    department: Mapped[str] = mapped_column(String(120))
    budget_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    status: Mapped[str] = mapped_column(String(30), default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    expenses: Mapped[list["ExpenseRequestModel"]] = relationship(back_populates="project")
    attachments: Mapped[list["TransferAttachmentModel"]] = relationship(back_populates="project")


class ExpenseRequestModel(Base):
    __tablename__ = "expense_requests"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    requester_id: Mapped[str] = mapped_column(String(80))
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    currency: Mapped[str] = mapped_column(String(10), default="VND")
    budget_line_code: Mapped[str] = mapped_column(String(40))
    vendor_id: Mapped[str | None] = mapped_column(String(80), nullable=True)
    description: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(30), default="submitted", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, index=True)

    project: Mapped[ProjectModel] = relationship(back_populates="expenses")


class IntegrationConfigModel(Base):
    __tablename__ = "integration_configs"

    key: Mapped[str] = mapped_column(String(40), primary_key=True)
    provider: Mapped[str] = mapped_column(String(40), index=True)
    enabled: Mapped[bool] = mapped_column(default=False)
    display_name: Mapped[str] = mapped_column(String(120))
    status: Mapped[str] = mapped_column(String(30), default="not_configured")
    config_json: Mapped[str] = mapped_column(Text, default="{}")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)


class TransferAttachmentModel(Base):
    __tablename__ = "transfer_attachments"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    project_id: Mapped[str | None] = mapped_column(ForeignKey("projects.id"), nullable=True, index=True)
    source: Mapped[str] = mapped_column(String(40), default="telegram")
    telegram_file_id: Mapped[str | None] = mapped_column(String(200), nullable=True, index=True)
    telegram_chat_id: Mapped[str | None] = mapped_column(String(80), nullable=True)
    telegram_message_id: Mapped[str | None] = mapped_column(String(80), nullable=True)
    file_name: Mapped[str] = mapped_column(String(240))
    file_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    file_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    file_dhash: Mapped[str | None] = mapped_column(String(16), nullable=True)
    caption: Mapped[str] = mapped_column(Text, default="")
    amount_hint: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)
    status: Mapped[str] = mapped_column(String(30), default="unmatched", index=True)
    transaction_type: Mapped[str] = mapped_column(String(10), default="unknown")
    review_status: Mapped[str] = mapped_column(String(30), default="pending_review", index=True)
    counterparty: Mapped[str] = mapped_column(String(240), default="")
    bank_name: Mapped[str] = mapped_column(String(120), default="")
    reference: Mapped[str] = mapped_column(String(240), default="")
    transacted_at: Mapped[str] = mapped_column(String(60), default="")
    note: Mapped[str] = mapped_column(Text, default="")
    ai_summary: Mapped[str] = mapped_column(Text, default="")
    ai_payload_json: Mapped[str] = mapped_column(Text, default="{}")
    ai_confidence: Mapped[Decimal | None] = mapped_column(Numeric(5, 4), nullable=True)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, index=True)

    project: Mapped[ProjectModel | None] = relationship(back_populates="attachments")


class ChatStateModel(Base):
    """Trang thai hoi thoai Telegram: chat dang duoc bot cho nhap gi.

    Dung cho flow "gui anh xong -> bot hoi nhap noi dung -> tin text ke tiep
    duoc luu vao chung tu". Moi chat chi giu mot trang thai moi nhat.
    """

    __tablename__ = "chat_states"

    chat_id: Mapped[str] = mapped_column(String(80), primary_key=True)
    awaiting: Mapped[str] = mapped_column(String(40), default="")  # "note" | ""
    attachment_id: Mapped[str | None] = mapped_column(String(40), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )


class UserModel(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    email: Mapped[str] = mapped_column(String(240), unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String(160))
    password_hash: Mapped[str] = mapped_column(String(300))
    roles_json: Mapped[str] = mapped_column(Text, default="[]")
    status: Mapped[str] = mapped_column(String(30), default="active", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    sessions: Mapped[list["UserSessionModel"]] = relationship(back_populates="user")


class UserSessionModel(Base):
    __tablename__ = "user_sessions"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    token_hash: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    user: Mapped[UserModel] = relationship(back_populates="sessions")
