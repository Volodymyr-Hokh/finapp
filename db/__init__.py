"""
Database package for SQLAlchemy models and configuration.
"""
from .config import Base, engine, async_session_factory, metadata
from .session import get_session
from .models import (
    User,
    Category,
    Account,
    Tag,
    Transaction,
    TransactionTag,
    Budget,
    AILog,
    Chat,
    ChatMessage,
    TimestampMixin,
    SoftDeleteMixin,
)

__all__ = [
    # Config
    "Base",
    "engine",
    "async_session_factory",
    "metadata",
    # Session
    "get_session",
    # Models
    "User",
    "Category",
    "Account",
    "Tag",
    "Transaction",
    "TransactionTag",
    "Budget",
    "AILog",
    "Chat",
    "ChatMessage",
    # Mixins
    "TimestampMixin",
    "SoftDeleteMixin",
]
