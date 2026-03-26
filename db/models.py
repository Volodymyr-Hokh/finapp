import datetime
import uuid
from decimal import Decimal
from typing import Optional, List

from sqlalchemy import (
    String,
    DateTime,
    Boolean,
    Integer,
    Text,
    Numeric,
    Date,
    Float,
    ForeignKey,
    Enum,
    UniqueConstraint,
    CheckConstraint,
    Index,
    event,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .config import Base
from schemas.enums import TransactionType


class TimestampMixin:
    """
    Reusable timestamp fields for models.
    updated_at is automatically updated via SQLAlchemy events.
    """

    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.datetime.now(datetime.UTC),
        index=True,
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.datetime.now(datetime.UTC),
        index=True,
    )


class SoftDeleteMixin:
    """
    Soft-delete fields for models.
    """

    is_deleted: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        index=True,
    )
    deleted_at: Mapped[Optional[datetime.datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
    )


class User(TimestampMixin, Base):
    """
    Application user.
    """

    __tablename__ = "users"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    email: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255))
    base_currency: Mapped[str] = mapped_column(String(3), default="UAH")

    # Relationships
    categories: Mapped[List["Category"]] = relationship(
        back_populates="user", lazy="noload"
    )
    accounts: Mapped[List["Account"]] = relationship(
        back_populates="user", lazy="noload"
    )
    tags: Mapped[List["Tag"]] = relationship(back_populates="user", lazy="noload")
    transactions: Mapped[List["Transaction"]] = relationship(
        back_populates="user", lazy="noload"
    )
    budgets: Mapped[List["Budget"]] = relationship(back_populates="user", lazy="noload")
    ai_logs: Mapped[List["AILog"]] = relationship(back_populates="user", lazy="noload")
    chats: Mapped[List["Chat"]] = relationship(back_populates="user", lazy="noload")


class Category(TimestampMixin, Base):
    """
    Transaction category. System categories have NULL user_id.
    """

    __tablename__ = "categories"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(50), index=True)
    icon: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)

    user_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    user: Mapped[Optional["User"]] = relationship(
        back_populates="categories", lazy="noload"
    )
    transactions: Mapped[List["Transaction"]] = relationship(
        back_populates="category", lazy="noload"
    )


class Account(TimestampMixin, Base):
    """
    User account/wallet information.
    """

    __tablename__ = "accounts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), index=True)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    currency: Mapped[str] = mapped_column(String(3), default="UAH", index=True)
    balance: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        default=Decimal("0.00"),
    )

    user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
    )

    user: Mapped["User"] = relationship(back_populates="accounts", lazy="noload")
    transactions: Mapped[List["Transaction"]] = relationship(
        back_populates="account", lazy="noload"
    )


class TransactionTag(Base):
    """
    Through table for the ManyToMany relationship between Transaction and Tag.
    """

    __tablename__ = "transaction_tags"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    transaction_id: Mapped[int] = mapped_column(
        ForeignKey("transactions.id", ondelete="CASCADE"),
        index=True,
    )
    tag_id: Mapped[int] = mapped_column(
        ForeignKey("tags.id", ondelete="CASCADE"),
        index=True,
    )


class Tag(TimestampMixin, Base):
    """
    Normalized tag model rather than storing tags as a plain string on Transaction.
    """

    __tablename__ = "tags"
    __table_args__ = (
        UniqueConstraint("user_id", "name", name="uq_tags_user_name"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(64), index=True)

    user_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    user: Mapped[Optional["User"]] = relationship(back_populates="tags", lazy="noload")
    transactions: Mapped[List["Transaction"]] = relationship(
        secondary="transaction_tags",
        back_populates="tags",
        lazy="noload",
    )


class Transaction(TimestampMixin, SoftDeleteMixin, Base):
    """
    Financial transaction entity.
    """

    __tablename__ = "transactions"
    __table_args__ = (
        CheckConstraint("amount <> 0", name="ck_transactions_amount_nonzero"),
        Index(
            "ix_transactions_budget_query",
            "user_id",
            "category_id",
            "transaction_date",
            "type",
            "is_deleted",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    type: Mapped[TransactionType] = mapped_column(Enum(TransactionType), index=True)

    description: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    raw_input: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    ai_confidence: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    is_reviewed: Mapped[bool] = mapped_column(Boolean, default=False, index=True)

    transaction_date: Mapped[datetime.date] = mapped_column(
        Date,
        default=datetime.date.today,
        index=True,
    )

    user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
    )

    account_id: Mapped[int] = mapped_column(
        ForeignKey("accounts.id", ondelete="RESTRICT"),
        index=True,
    )

    category_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("categories.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    user: Mapped["User"] = relationship(back_populates="transactions", lazy="noload")
    account: Mapped["Account"] = relationship(
        back_populates="transactions", lazy="noload"
    )
    category: Mapped[Optional["Category"]] = relationship(
        back_populates="transactions", lazy="noload"
    )
    tags: Mapped[List["Tag"]] = relationship(
        secondary="transaction_tags",
        back_populates="transactions",
        lazy="noload",
    )


class Budget(TimestampMixin, Base):
    """
    Budget constraints per user, category and period (month/year).
    """

    __tablename__ = "budgets"
    __table_args__ = (
        UniqueConstraint(
            "user_id", "category_id", "month", "year", name="uq_budget_user_cat_period"
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    limit_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    month: Mapped[int] = mapped_column(Integer, index=True)
    year: Mapped[int] = mapped_column(Integer, index=True)

    user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
    )
    category_id: Mapped[int] = mapped_column(
        ForeignKey("categories.id", ondelete="RESTRICT"),
        index=True,
    )

    user: Mapped["User"] = relationship(back_populates="budgets", lazy="noload")
    category: Mapped["Category"] = relationship(lazy="noload")


class AILog(TimestampMixin, Base):
    """
    Logging of AI prompts/responses for audit and analytics.
    """

    __tablename__ = "ai_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    prompt: Mapped[str] = mapped_column(Text)
    response: Mapped[str] = mapped_column(Text)
    ai_model: Mapped[str] = mapped_column(String(50), index=True)
    tokens_used: Mapped[int] = mapped_column(Integer, default=0)
    execution_time: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
    )

    user: Mapped["User"] = relationship(back_populates="ai_logs", lazy="noload")


class Chat(TimestampMixin, SoftDeleteMixin, Base):
    """
    Chat/Conversation session for a user.
    Supports soft delete so users can recover deleted chats.
    """

    __tablename__ = "chats"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    name: Mapped[str] = mapped_column(String(255), index=True)

    user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
    )

    user: Mapped["User"] = relationship(back_populates="chats", lazy="noload")
    messages: Mapped[List["ChatMessage"]] = relationship(
        back_populates="chat",
        lazy="noload",
        cascade="all, delete-orphan",
    )


class ChatMessage(TimestampMixin, Base):
    """
    Individual message in a chat, storing serialized Pydantic AI message format.
    """

    __tablename__ = "chat_messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    message_json: Mapped[str] = mapped_column(Text)
    role: Mapped[str] = mapped_column(String(20), index=True)
    sequence_number: Mapped[int] = mapped_column(Integer, index=True)
    token_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    chat_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("chats.id", ondelete="CASCADE"),
        index=True,
    )

    chat: Mapped["Chat"] = relationship(back_populates="messages", lazy="noload")


# Event handlers for automatic timestamp updates
def _before_insert_listener(mapper, connection, target):
    """Set timestamps on insert."""
    now = datetime.datetime.now(datetime.UTC)
    if hasattr(target, "created_at") and target.created_at is None:
        target.created_at = now
    if hasattr(target, "updated_at"):
        target.updated_at = now


def _before_update_listener(mapper, connection, target):
    """Update updated_at timestamp and manage deleted_at on update."""
    target.updated_at = datetime.datetime.now(datetime.UTC)

    # Handle soft delete: sync deleted_at with is_deleted
    if hasattr(target, "is_deleted") and hasattr(target, "deleted_at"):
        if target.is_deleted and target.deleted_at is None:
            target.deleted_at = datetime.datetime.now(datetime.UTC)
        elif not target.is_deleted:
            target.deleted_at = None


# Register listeners for all models with timestamps
_timestamped_models = [
    User,
    Category,
    Account,
    Tag,
    Transaction,
    Budget,
    AILog,
    Chat,
    ChatMessage,
]

for _model in _timestamped_models:
    event.listen(_model, "before_insert", _before_insert_listener)
    event.listen(_model, "before_update", _before_update_listener)
