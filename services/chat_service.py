"""
Chat service for orchestrating AI chat sessions with streaming and persistence.
"""
from typing import AsyncGenerator, Optional
from uuid import UUID
import json
import logfire
from openai import AsyncOpenAI

from repositories.container import RepositoryContainer
from services.ai_agents.main_agent import MainAgent
from services.ai_tools import AgentContext
from settings import settings


class ChatService:
    """
    High-level service for managing AI chat sessions.

    Handles:
    - Chat creation and management
    - Message persistence
    - Streaming responses via SSE
    - Conversation history management
    """

    def __init__(
        self,
        repo: RepositoryContainer,
        client: Optional[AsyncOpenAI] = None,
        main_agent: Optional[MainAgent] = None
    ):
        self.repo = repo
        self.client = client or AsyncOpenAI(api_key=settings.openai_api_key.get_secret_value())
        self.main_agent = main_agent or MainAgent(self.client)

    async def create_chat(self, user_id: UUID, name: str = "New Chat") -> dict:
        """Create a new chat session for a user."""
        chat = await self.repo.chats.create_for_user(user_id, name)
        return {
            "id": str(chat.id),
            "name": chat.name,
            "created_at": str(chat.created_at),
            "updated_at": str(chat.updated_at)
        }

    async def get_user_chats(
        self,
        user_id: UUID,
        limit: Optional[int] = None
    ) -> list[dict]:
        """Get all chats for a user."""
        chats = await self.repo.chats.get_user_chats(user_id, limit=limit)
        return [
            {
                "id": str(c.id),
                "name": c.name,
                "created_at": str(c.created_at),
                "updated_at": str(c.updated_at)
            }
            for c in chats
        ]

    async def get_chat_messages(
        self,
        chat_id: UUID,
        user_id: UUID,
        limit: Optional[int] = None
    ) -> list[dict]:
        """Get messages for a chat, validating user ownership."""
        messages = await self.repo.chat_messages.get_messages_by_chat_and_user(
            chat_id, user_id, limit=limit
        )
        return [
            {
                "id": m.id,
                "role": m.role,
                "content": json.loads(m.message_json).get("content", ""),
                "sequence_number": m.sequence_number,
                "created_at": str(m.created_at)
            }
            for m in messages
        ]

    async def _get_conversation_history(
        self,
        chat_id: UUID,
        limit: int = 20
    ) -> list[dict]:
        """
        Get conversation history formatted for OpenAI.

        Returns messages in the format expected by the chat completion API.
        """
        messages = await self.repo.chat_messages.get_latest_messages(chat_id, limit=limit)

        history = []
        for m in messages:
            content_data = json.loads(m.message_json)

            if m.role == "user":
                history.append({
                    "role": "user",
                    "content": content_data.get("content", "")
                })
            elif m.role == "assistant":
                msg = {
                    "role": "assistant",
                    "content": content_data.get("content", "")
                }
                # Include tool calls if present
                if "tool_calls" in content_data:
                    msg["tool_calls"] = content_data["tool_calls"]
                history.append(msg)
            elif m.role == "tool":
                history.append({
                    "role": "tool",
                    "tool_call_id": content_data.get("tool_call_id"),
                    "content": content_data.get("content", "")
                })

        return history

    async def _save_user_message(
        self,
        chat_id: UUID,
        content: str
    ) -> None:
        """Save a user message to the chat."""
        message_json = json.dumps({
            "content": content
        })
        await self.repo.chat_messages.create_message(
            chat_id=chat_id,
            message_json=message_json,
            role="user"
        )

    async def _save_assistant_message(
        self,
        chat_id: UUID,
        content: str,
        tool_calls: Optional[list] = None,
        token_count: Optional[int] = None
    ) -> None:
        """Save an assistant message to the chat."""
        message_data = {"content": content}
        if tool_calls:
            message_data["tool_calls"] = tool_calls

        message_json = json.dumps(message_data)
        await self.repo.chat_messages.create_message(
            chat_id=chat_id,
            message_json=message_json,
            role="assistant",
            token_count=token_count
        )

    def _build_user_message_content(
        self,
        message: str,
        image_data: Optional[dict] = None,
    ) -> str | list:
        """Build user message content, optionally with image for multimodal input."""
        if not image_data:
            return message

        return [
            {"type": "text", "text": message},
            {
                "type": "image_url",
                "image_url": {
                    "url": f"data:{image_data['mime_type']};base64,{image_data['data']}",
                    "detail": "high",
                },
            },
        ]

    async def send_message_stream(
        self,
        chat_id: UUID,
        user_id: UUID,
        message: str,
        image_data: Optional[dict] = None,
    ) -> AsyncGenerator[str, None]:
        """
        Send a message and stream the response via SSE.

        This is the main entry point for the AI chat endpoint.
        Messages are persisted to the database.

        Args:
            chat_id: The chat session ID
            user_id: The authenticated user ID
            message: The user's text message
            image_data: Optional dict with 'data' (base64) and 'mime_type' keys
        """
        # Validate chat ownership
        chat = await self.repo.chats.get_by_id_and_user(chat_id, user_id)
        if not chat:
            yield f"data: {json.dumps({'type': 'error', 'message': 'Chat not found'}, ensure_ascii=False)}\n\n"
            return

        with logfire.span("chat_service.send_message", chat_id=str(chat_id), user_id=str(user_id), message=message):
            # Get conversation history FIRST (before saving new message to avoid duplicates)
            history = await self._get_conversation_history(chat_id)

            # Save user message (text only, not the image)
            await self._save_user_message(chat_id, message)

            # Create agent context
            context = AgentContext(
                user_id=user_id,
                chat_id=chat_id,
                repo=self.repo
            )

            # Build user message content (with image if provided)
            user_message_content = self._build_user_message_content(message, image_data)

            # Stream response
            accumulated_content = ""
            saved = False

            try:
                async for chunk in self.main_agent.run(
                    user_message=user_message_content,
                    context=context,
                    conversation_history=history,
                    stream=True
                ):
                    # Parse chunk BEFORE yielding so we can save on "done"
                    if chunk.startswith("data: "):
                        try:
                            data = json.loads(chunk[6:].strip())
                            if data.get("type") == "content":
                                accumulated_content += data.get("content", "")
                            elif data.get("type") == "done":
                                # Save BEFORE yielding "done" — after yield
                                # the client closes the connection and the
                                # generator gets abandoned (GeneratorExit)
                                if accumulated_content and not saved:
                                    try:
                                        await self._save_assistant_message(chat_id, accumulated_content)
                                        saved = True
                                    except Exception as e:
                                        logfire.error(f"Failed to save assistant message: {e}")
                                try:
                                    await self.repo.chats.touch(chat_id, user_id)
                                except Exception as e:
                                    logfire.error(f"Failed to touch chat: {e}")
                        except json.JSONDecodeError:
                            pass

                    yield chunk

            except Exception as e:
                logfire.error(f"Chat error: {e}")
                if accumulated_content and not saved:
                    try:
                        await self._save_assistant_message(chat_id, accumulated_content)
                    except Exception as save_err:
                        logfire.error(f"Failed to save partial response: {save_err}")
                yield f"data: {json.dumps({'type': 'error', 'message': str(e)}, ensure_ascii=False)}\n\n"

    async def quick_chat_stream(
        self,
        user_id: UUID,
        message: str,
        image_data: Optional[dict] = None,
    ) -> AsyncGenerator[str, None]:
        """
        Quick chat without creating/using a persistent chat session.

        Creates a temporary context for one-off questions.
        No message persistence.

        Args:
            user_id: The authenticated user ID
            message: The user's text message
            image_data: Optional dict with 'data' (base64) and 'mime_type' keys
        """
        # Create a temporary chat_id for the context (not persisted)
        from uuid import uuid4
        temp_chat_id = uuid4()

        context = AgentContext(
            user_id=user_id,
            chat_id=temp_chat_id,
            repo=self.repo
        )

        # Build user message content (with image if provided)
        user_message_content = self._build_user_message_content(message, image_data)

        with logfire.span("chat_service.quick_chat", user_id=str(user_id), message=message):
            try:
                async for chunk in self.main_agent.run(
                    user_message=user_message_content,
                    context=context,
                    stream=True
                ):
                    yield chunk
            except Exception as e:
                logfire.error(f"Quick chat error: {e}")
                yield f"data: {json.dumps({'type': 'error', 'message': str(e)}, ensure_ascii=False)}\n\n"

    async def rename_chat(
        self,
        chat_id: UUID,
        user_id: UUID,
        new_name: str
    ) -> Optional[dict]:
        """Rename a chat."""
        chat = await self.repo.chats.update_name(chat_id, user_id, new_name)
        if chat:
            return {
                "id": str(chat.id),
                "name": chat.name,
                "updated_at": str(chat.updated_at)
            }
        return None

    async def delete_chat(
        self,
        chat_id: UUID,
        user_id: UUID
    ) -> bool:
        """Soft delete a chat."""
        return await self.repo.chats.soft_delete(chat_id, user_id)

    async def generate_chat_title(
        self,
        chat_id: UUID,
        user_id: UUID
    ) -> Optional[str]:
        """
        Generate a title for the chat based on its content.

        Uses the AI to create a concise, descriptive title.
        """
        chat = await self.repo.chats.get_by_id_and_user(chat_id, user_id)
        if not chat:
            return None

        # Get first few messages for context
        messages = await self.repo.chat_messages.get_messages_by_chat(chat_id, limit=4)
        if not messages:
            return None

        # Build context from messages
        context_text = ""
        for m in messages:
            content = json.loads(m.message_json).get("content", "")
            if content:
                context_text += f"{m.role}: {content[:200]}\n"

        # Ask AI to generate title
        response = await self.client.chat.completions.create(
            model="gpt-4o-mini",  # Use faster model for title generation
            messages=[
                {
                    "role": "system",
                    "content": "Generate a very short (3-5 words) title for this conversation. Only output the title, nothing else."
                },
                {
                    "role": "user",
                    "content": context_text
                }
            ],
            max_tokens=20,
            temperature=0.7
        )

        title = response.choices[0].message.content.strip()

        # Update chat name
        await self.repo.chats.update_name(chat_id, user_id, title)

        return title
