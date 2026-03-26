from datetime import datetime
from typing import Optional, List, Any
from uuid import UUID

from pydantic import Field

from .base import BaseSchema, TimestampSchema


class ChatCreate(BaseSchema):
    """Request to create a new chat."""

    name: Optional[str] = Field(
        None,
        max_length=255,
        description="Optional chat name. If not provided, will auto-generate from first message.",
    )


class ChatUpdate(BaseSchema):
    """Request to update chat metadata."""

    name: str = Field(..., min_length=1, max_length=255, description="New chat name")


class ChatSummary(TimestampSchema):
    """Summary view of a chat (for listing)."""

    id: UUID
    name: str
    message_count: Optional[int] = Field(None, description="Number of messages in chat")
    last_message_at: Optional[datetime] = Field(
        None, description="Timestamp of last message"
    )


class ChatMessageRead(TimestampSchema):
    """Individual message in a chat."""

    id: int
    role: str = Field(..., description="Message role: 'user' or 'assistant'")
    content: str = Field(
        ..., description="Message content (text only, extracted from message_json)"
    )
    sequence_number: int
    message_data: Optional[Any] = Field(
        None, description="Full Pydantic AI message structure"
    )


class ChatRead(TimestampSchema):
    """Full chat view with messages."""

    id: UUID
    name: str
    messages: List[ChatMessageRead] = Field(default_factory=list)


class ChatListResponse(BaseSchema):
    """Response for listing user's chats."""

    chats: List[ChatSummary]
    total: int


class ImageAttachment(BaseSchema):
    """Image attachment for chat messages."""

    data: str = Field(
        ..., description="Base64-encoded image data", max_length=7_000_000
    )
    mime_type: str = Field(
        ...,
        description="MIME type of the image",
        pattern=r"^image/(jpeg|png|webp|gif)$",
    )


class SendMessageRequest(BaseSchema):
    """Request to send a message in a chat."""

    message: str = Field(
        ..., min_length=1, max_length=4000, description="User's message"
    )
    image: Optional[ImageAttachment] = Field(
        None, description="Optional image attachment (receipt/check photo)"
    )


class SendMessageResponse(BaseSchema):
    """Response after sending a message."""

    chat_id: UUID
    user_message: ChatMessageRead
    assistant_message: ChatMessageRead


class QuickChatRequest(BaseSchema):
    """Request to create a chat and send first message."""

    message: str = Field(
        ..., min_length=1, max_length=4000, description="First message"
    )
    name: Optional[str] = Field(
        None,
        max_length=255,
        description="Optional chat name. Auto-generated from message if not provided.",
    )
    image: Optional[ImageAttachment] = Field(
        None, description="Optional image attachment (receipt/check photo)"
    )


class QuickChatResponse(BaseSchema):
    """Response for quick chat creation."""

    chat_id: UUID
    chat_name: str
    response: str
