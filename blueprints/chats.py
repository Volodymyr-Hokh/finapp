"""
Chat CRUD endpoints for managing chat sessions.
"""
from uuid import UUID

from sanic import Blueprint, Request, json
from sanic_ext import validate, openapi

from schemas.chats import (
    ChatCreate,
    ChatUpdate,
    ChatSummary,
    ChatRead,
    ChatListResponse,
    ChatMessageRead,
)
from schemas.shared import ErrorResponse, UnauthorizedResponse, ValidationErrorResponse
from services.auth import protected
from services.chat_service import ChatService


chat_bp = Blueprint("Chats", url_prefix="/chats")


def get_chat_service(request: Request) -> ChatService:
    """Get or create ChatService instance."""
    if not hasattr(request.app.ctx, "chat_service"):
        request.app.ctx.chat_service = ChatService(request.app.ctx.repo)
    return request.app.ctx.chat_service


@chat_bp.post("/")
@openapi.summary("Create a new chat")
@openapi.description("Creates a new chat session for the authenticated user.")
@openapi.secured("BearerAuth")
@openapi.body({"application/json": ChatCreate.model_json_schema()})
@openapi.response(201, {"application/json": ChatSummary.model_json_schema()}, "Chat created")
@openapi.response(401, {"application/json": UnauthorizedResponse.model_json_schema()}, "Unauthorized")
@openapi.response(422, {"application/json": ValidationErrorResponse.model_json_schema()}, "Validation error")
@protected
@validate(json=ChatCreate)
async def create_chat(request: Request, body: ChatCreate):
    """Create a new chat session."""
    user_id = request.ctx.user_id
    service = get_chat_service(request)

    name = body.name or "New Chat"
    chat = await service.create_chat(user_id, name)

    return json(chat, status=201)


@chat_bp.get("/")
@openapi.summary("List user's chats")
@openapi.description("Get all chat sessions for the authenticated user, ordered by most recent.")
@openapi.secured("BearerAuth")
@openapi.parameter("limit", int, "query", description="Maximum number of chats to return")
@openapi.response(200, {"application/json": ChatListResponse.model_json_schema()}, "List of chats")
@openapi.response(401, {"application/json": UnauthorizedResponse.model_json_schema()}, "Unauthorized")
@protected
async def list_chats(request: Request):
    """List all chats for the user."""
    user_id = request.ctx.user_id
    limit_str = request.args.get("limit")
    limit = int(limit_str) if limit_str else None
    service = get_chat_service(request)

    chats = await service.get_user_chats(user_id, limit=limit)

    return json({
        "chats": chats,
        "total": len(chats)
    })


@chat_bp.get("/<chat_id:uuid>")
@openapi.summary("Get chat details")
@openapi.description("Get a specific chat with its messages.")
@openapi.secured("BearerAuth")
@openapi.parameter("limit", int, "query", description="Maximum number of messages to return")
@openapi.response(200, {"application/json": ChatRead.model_json_schema()}, "Chat details with messages")
@openapi.response(401, {"application/json": UnauthorizedResponse.model_json_schema()}, "Unauthorized")
@openapi.response(404, {"application/json": ErrorResponse.model_json_schema()}, "Chat not found")
@protected
async def get_chat(request: Request, chat_id: UUID):
    """Get a specific chat with messages."""
    user_id = request.ctx.user_id
    limit_str = request.args.get("limit")
    limit = int(limit_str) if limit_str else None
    service = get_chat_service(request)

    # Check chat exists and belongs to user
    chat = await request.app.ctx.repo.chats.get_by_id_and_user(chat_id, user_id)
    if not chat:
        return json({"error": "Chat not found"}, status=404)

    messages = await service.get_chat_messages(chat_id, user_id, limit=limit)

    return json({
        "id": str(chat.id),
        "name": chat.name,
        "created_at": str(chat.created_at),
        "updated_at": str(chat.updated_at),
        "messages": messages
    })


@chat_bp.patch("/<chat_id:uuid>")
@openapi.summary("Update chat")
@openapi.description("Update chat metadata (name).")
@openapi.secured("BearerAuth")
@openapi.body({"application/json": ChatUpdate.model_json_schema()})
@openapi.response(200, {"application/json": ChatSummary.model_json_schema()}, "Updated chat")
@openapi.response(401, {"application/json": UnauthorizedResponse.model_json_schema()}, "Unauthorized")
@openapi.response(404, {"application/json": ErrorResponse.model_json_schema()}, "Chat not found")
@openapi.response(422, {"application/json": ValidationErrorResponse.model_json_schema()}, "Validation error")
@protected
@validate(json=ChatUpdate)
async def update_chat(request: Request, chat_id: UUID, body: ChatUpdate):
    """Update a chat's name."""
    user_id = request.ctx.user_id
    service = get_chat_service(request)

    result = await service.rename_chat(chat_id, user_id, body.name)
    if not result:
        return json({"error": "Chat not found"}, status=404)

    return json(result)


@chat_bp.delete("/<chat_id:uuid>")
@openapi.summary("Delete chat")
@openapi.description("Soft delete a chat (can be restored later).")
@openapi.secured("BearerAuth")
@openapi.response(200, description="Chat deleted successfully")
@openapi.response(401, {"application/json": UnauthorizedResponse.model_json_schema()}, "Unauthorized")
@openapi.response(404, {"application/json": ErrorResponse.model_json_schema()}, "Chat not found")
@protected
async def delete_chat(request: Request, chat_id: UUID):
    """Delete a chat."""
    user_id = request.ctx.user_id
    service = get_chat_service(request)

    success = await service.delete_chat(chat_id, user_id)
    if not success:
        return json({"error": "Chat not found"}, status=404)

    return json({"message": "Chat deleted successfully"})


@chat_bp.post("/<chat_id:uuid>/generate-title")
@openapi.summary("Generate chat title")
@openapi.description("Use AI to generate a title based on conversation content.")
@openapi.secured("BearerAuth")
@openapi.response(200, description="Generated title")
@openapi.response(401, {"application/json": UnauthorizedResponse.model_json_schema()}, "Unauthorized")
@openapi.response(404, {"application/json": ErrorResponse.model_json_schema()}, "Chat not found")
@protected
async def generate_title(request: Request, chat_id: UUID):
    """Generate a title for the chat based on its content."""
    user_id = request.ctx.user_id
    service = get_chat_service(request)

    title = await service.generate_chat_title(chat_id, user_id)
    if not title:
        return json({"error": "Chat not found or has no messages"}, status=404)

    return json({"title": title})
