"""
AI Chat SSE streaming endpoints.
"""
from uuid import UUID

from sanic import Blueprint, Request
from sanic.response import ResponseStream
from sanic_ext import validate, openapi

from schemas.chats import SendMessageRequest, QuickChatRequest
from schemas.shared import ErrorResponse, UnauthorizedResponse, ValidationErrorResponse
from services.auth import protected
from services.chat_service import ChatService


ai_chat_bp = Blueprint("AI_Chat", url_prefix="/ai")


def get_chat_service(request: Request) -> ChatService:
    """Get or create ChatService instance."""
    if not hasattr(request.app.ctx, "chat_service"):
        request.app.ctx.chat_service = ChatService(request.app.ctx.repo)
    return request.app.ctx.chat_service


@ai_chat_bp.post("/chats/<chat_id:uuid>/message")
@openapi.summary("Send message to chat (SSE)")
@openapi.description("""
Send a message to an existing chat and receive streaming AI response via Server-Sent Events.

The response is a stream of SSE events with the following types:
- `content`: Text content chunk from the AI
- `delegation`: AI is delegating to a specialized agent
- `tool_start`: AI is starting to execute tools
- `tool_call`: A specific tool is being called
- `tool_end`: Tool execution completed
- `done`: Response complete
- `error`: An error occurred
""")
@openapi.secured("BearerAuth")
@openapi.body({"application/json": SendMessageRequest.model_json_schema()})
@openapi.response(200, description="SSE stream of AI response")
@openapi.response(401, {"application/json": UnauthorizedResponse.model_json_schema()}, "Unauthorized")
@openapi.response(404, {"application/json": ErrorResponse.model_json_schema()}, "Chat not found")
@openapi.response(422, {"application/json": ValidationErrorResponse.model_json_schema()}, "Validation error")
@protected
@validate(json=SendMessageRequest)
async def send_message(request: Request, chat_id: UUID, body: SendMessageRequest):
    """Send a message to a chat and stream the response."""
    user_id = request.ctx.user_id
    service = get_chat_service(request)

    image_data = None
    if body.image:
        image_data = {"data": body.image.data, "mime_type": body.image.mime_type}

    async def stream_response(response):
        async for chunk in service.send_message_stream(chat_id, user_id, body.message, image_data=image_data):
            await response.write(chunk)

    return ResponseStream(
        stream_response,
        content_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable proxy buffering
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "Content-Type, Authorization",
        }
    )


@ai_chat_bp.post("/quick-chat/stream")
@openapi.summary("Quick chat (SSE)")
@openapi.description("""
Send a one-off message without creating a persistent chat session.
Useful for quick questions. Response is streamed via Server-Sent Events.

SSE event types:
- `content`: Text content chunk from the AI
- `delegation`: AI is delegating to a specialized agent
- `tool_start`: AI is starting to execute tools
- `tool_call`: A specific tool is being called
- `tool_end`: Tool execution completed
- `done`: Response complete
- `error`: An error occurred
""")
@openapi.secured("BearerAuth")
@openapi.body({"application/json": QuickChatRequest.model_json_schema()})
@openapi.response(200, description="SSE stream of AI response")
@openapi.response(401, {"application/json": UnauthorizedResponse.model_json_schema()}, "Unauthorized")
@openapi.response(422, {"application/json": ValidationErrorResponse.model_json_schema()}, "Validation error")
@protected
@validate(json=QuickChatRequest)
async def quick_chat(request: Request, body: QuickChatRequest):
    """Quick chat without persistent session."""
    user_id = request.ctx.user_id
    service = get_chat_service(request)

    image_data = None
    if body.image:
        image_data = {"data": body.image.data, "mime_type": body.image.mime_type}

    async def stream_response(response):
        async for chunk in service.quick_chat_stream(user_id, body.message, image_data=image_data):
            await response.write(chunk)

    return ResponseStream(
        stream_response,
        content_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "Content-Type, Authorization",
        }
    )


@ai_chat_bp.post("/quick-chat/create")
@openapi.summary("Quick chat with session")
@openapi.description("""
Create a new chat session and send the first message.
Response is streamed via Server-Sent Events.
The chat ID is included in a special SSE event at the start.

SSE event types:
- `chat_created`: Contains the new chat_id
- `content`: Text content chunk from the AI
- `delegation`: AI is delegating to a specialized agent
- `tool_start`: AI is starting to execute tools
- `tool_call`: A specific tool is being called
- `tool_end`: Tool execution completed
- `done`: Response complete
- `error`: An error occurred
""")
@openapi.secured("BearerAuth")
@openapi.body({"application/json": QuickChatRequest.model_json_schema()})
@openapi.response(200, description="SSE stream with chat_id and AI response")
@openapi.response(401, {"application/json": UnauthorizedResponse.model_json_schema()}, "Unauthorized")
@openapi.response(422, {"application/json": ValidationErrorResponse.model_json_schema()}, "Validation error")
@protected
@validate(json=QuickChatRequest)
async def quick_chat_create(request: Request, body: QuickChatRequest):
    """Create a new chat and send the first message with streaming response."""
    import json as json_module
    user_id = request.ctx.user_id
    service = get_chat_service(request)

    # Create the chat first
    name = body.name or "New Chat"
    chat = await service.create_chat(user_id, name)
    chat_id = UUID(chat["id"])

    async def stream_response(response):
        # Send chat creation event first
        await response.write(
            f"data: {json_module.dumps({'type': 'chat_created', 'chat_id': str(chat_id), 'name': chat['name']}, ensure_ascii=False)}\n\n"
        )

        image_data = None
        if body.image:
            image_data = {"data": body.image.data, "mime_type": body.image.mime_type}

        # Stream the AI response
        async for chunk in service.send_message_stream(chat_id, user_id, body.message, image_data=image_data):
            await response.write(chunk)

    return ResponseStream(
        stream_response,
        content_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "Content-Type, Authorization",
        }
    )
