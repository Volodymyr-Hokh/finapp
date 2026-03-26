"""
Base agent class with streaming support and tool execution.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, AsyncGenerator, Optional, Union
import json
import logfire
from openai import AsyncOpenAI

from services.ai_tools import AgentContext, ToolRegistry

logfire.instrument_openai()

@dataclass
class ToolCall:
    """Represents a tool call from the LLM."""
    id: str
    name: str
    arguments: dict[str, Any]


@dataclass
class AgentResponse:
    """Response from an agent execution."""
    content: str
    tool_calls: list[ToolCall] = field(default_factory=list)
    usage: dict[str, int] = field(default_factory=dict)
    finish_reason: str = "stop"


class BaseAgent(ABC):
    """
    Abstract base class for all AI agents.

    Subclasses must implement:
    - name: Agent identifier
    - description: What this agent does (used for delegation)
    - system_prompt: Instructions for the LLM
    - get_tool_registry(): Return the ToolRegistry for this agent
    """

    MODEL: str = "gpt-4o"
    MAX_TOKENS: int = 4096
    TEMPERATURE: float = 0.7
    MAX_TOOL_ITERATIONS: int = 10

    def __init__(self, client: AsyncOpenAI):
        self.client = client

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique identifier for the agent."""
        pass

    @property
    @abstractmethod
    def description(self) -> str:
        """Description of agent capabilities (used by main agent for delegation)."""
        pass

    @property
    @abstractmethod
    def system_prompt(self) -> str:
        """System prompt defining agent behavior."""
        pass

    @abstractmethod
    def get_tool_registry(self) -> ToolRegistry:
        """Return the ToolRegistry containing this agent's tools."""
        pass

    def _build_system_prompt(self, context: AgentContext) -> str:
        """Build system prompt with current date injected."""
        date_str = context.current_date.strftime("%A, %Y-%m-%d")
        return f"Current date: {date_str}\n\n{self.system_prompt}"

    def _build_messages(self, context: AgentContext, user_message: Union[str, list]) -> list[dict]:
        """Build messages list with system prompt and conversation history."""
        messages = [{"role": "system", "content": self._build_system_prompt(context)}]
        # Note: conversation_history should be passed if needed
        messages.append({"role": "user", "content": user_message})
        return messages

    async def run(
        self,
        user_message: Union[str, list],
        context: AgentContext,
        conversation_history: Optional[list[dict]] = None,
        stream: bool = False
    ) -> AsyncGenerator[str, None] | AgentResponse:
        """
        Execute agent with a user message.

        Args:
            user_message: The user's input (str for text, list for multimodal content)
            context: AgentContext with user_id, chat_id, repo
            conversation_history: Optional list of previous messages
            stream: If True, yields SSE-formatted chunks. If False, returns AgentResponse.
        """
        messages = [{"role": "system", "content": self._build_system_prompt(context)}]
        if conversation_history:
            messages.extend(conversation_history)
        messages.append({"role": "user", "content": user_message})

        registry = self.get_tool_registry()
        tools = registry.get_schemas()

        with logfire.span(f"agent.{self.name}.run", user_id=str(context.user_id), messages=messages):
            if stream:
                async for chunk in self._stream_response(messages, tools, registry, context):
                    yield chunk
            else:
                response = await self._complete_response(messages, tools, registry, context)
                yield response

    async def _stream_response(
        self,
        messages: list[dict],
        tools: list[dict],
        registry: ToolRegistry,
        context: AgentContext,
        iteration: int = 0
    ) -> AsyncGenerator[str, None]:
        """Stream response with tool call handling."""
        if iteration >= self.MAX_TOOL_ITERATIONS:
            yield f"data: {json.dumps({'type': 'error', 'message': 'Maximum tool iterations reached'}, ensure_ascii=False)}\n\n"
            yield f"data: {json.dumps({'type': 'done', 'finish_reason': 'max_iterations'}, ensure_ascii=False)}\n\n"
            return

        response = await self.client.chat.completions.create(
            model=self.MODEL,
            messages=messages,
            tools=tools if tools else None,
            tool_choice="auto" if tools else None,
            max_tokens=self.MAX_TOKENS,
            temperature=self.TEMPERATURE,
            stream=True
        )

        accumulated_content = ""
        tool_calls_buffer: dict[int, dict] = {}

        async for chunk in response:
            delta = chunk.choices[0].delta

            # Handle content streaming
            if delta.content:
                accumulated_content += delta.content
                yield f"data: {json.dumps({'type': 'content', 'content': delta.content}, ensure_ascii=False)}\n\n"

            # Handle tool calls (accumulate across chunks)
            if delta.tool_calls:
                for tc in delta.tool_calls:
                    idx = tc.index
                    if idx not in tool_calls_buffer:
                        tool_calls_buffer[idx] = {
                            "id": tc.id or "",
                            "name": tc.function.name if tc.function else "",
                            "arguments": ""
                        }
                    if tc.id:
                        tool_calls_buffer[idx]["id"] = tc.id
                    if tc.function and tc.function.name:
                        tool_calls_buffer[idx]["name"] = tc.function.name
                    if tc.function and tc.function.arguments:
                        tool_calls_buffer[idx]["arguments"] += tc.function.arguments

            # Check for finish reason
            if chunk.choices[0].finish_reason:
                finish_reason = chunk.choices[0].finish_reason

                if finish_reason == "tool_calls" and tool_calls_buffer:
                    # Execute tools and continue conversation
                    yield f"data: {json.dumps({'type': 'tool_start'}, ensure_ascii=False)}\n\n"

                    tool_results = []
                    assistant_tool_calls = []

                    for idx in sorted(tool_calls_buffer.keys()):
                        tc_data = tool_calls_buffer[idx]
                        tool_call = ToolCall(
                            id=tc_data["id"],
                            name=tc_data["name"],
                            arguments=json.loads(tc_data["arguments"]) if tc_data["arguments"] else {}
                        )

                        yield f"data: {json.dumps({'type': 'tool_call', 'tool': tool_call.name}, ensure_ascii=False)}\n\n"

                        # Execute tool
                        result = await registry.execute(
                            tool_call.name,
                            tool_call.arguments,
                            context
                        )

                        tool_results.append({
                            "tool_call_id": tool_call.id,
                            "role": "tool",
                            "content": result
                        })

                        assistant_tool_calls.append({
                            "id": tc_data["id"],
                            "type": "function",
                            "function": {
                                "name": tc_data["name"],
                                "arguments": tc_data["arguments"]
                            }
                        })

                    yield f"data: {json.dumps({'type': 'tool_end'}, ensure_ascii=False)}\n\n"

                    # Continue conversation with tool results
                    messages.append({
                        "role": "assistant",
                        "content": accumulated_content or None,
                        "tool_calls": assistant_tool_calls
                    })
                    messages.extend(tool_results)

                    # Recursive call for follow-up
                    async for follow_up in self._stream_response(
                        messages, tools, registry, context, iteration + 1
                    ):
                        yield follow_up
                    return

                yield f"data: {json.dumps({'type': 'done', 'finish_reason': finish_reason}, ensure_ascii=False)}\n\n"

    async def _complete_response(
        self,
        messages: list[dict],
        tools: list[dict],
        registry: ToolRegistry,
        context: AgentContext,
        iteration: int = 0
    ) -> AgentResponse:
        """Get complete response with tool call handling (non-streaming)."""
        if iteration >= self.MAX_TOOL_ITERATIONS:
            return AgentResponse(
                content="Maximum tool iterations reached. Please try a simpler request.",
                finish_reason="max_iterations"
            )

        response = await self.client.chat.completions.create(
            model=self.MODEL,
            messages=messages,
            tools=tools if tools else None,
            tool_choice="auto" if tools else None,
            max_tokens=self.MAX_TOKENS,
            temperature=self.TEMPERATURE
        )

        choice = response.choices[0]

        if choice.finish_reason == "tool_calls" and choice.message.tool_calls:
            # Execute tools
            tool_results = []

            for tc in choice.message.tool_calls:
                tool_call = ToolCall(
                    id=tc.id,
                    name=tc.function.name,
                    arguments=json.loads(tc.function.arguments) if tc.function.arguments else {}
                )

                result = await registry.execute(
                    tool_call.name,
                    tool_call.arguments,
                    context
                )

                tool_results.append({
                    "tool_call_id": tc.id,
                    "role": "tool",
                    "content": result
                })

            # Continue conversation
            messages.append(choice.message.model_dump())
            messages.extend(tool_results)

            return await self._complete_response(
                messages, tools, registry, context, iteration + 1
            )

        return AgentResponse(
            content=choice.message.content or "",
            usage={
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens
            } if response.usage else {},
            finish_reason=choice.finish_reason or "stop"
        )
