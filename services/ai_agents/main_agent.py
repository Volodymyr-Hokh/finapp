"""
Main orchestrator agent that delegates to specialized sub-agents.
"""
from typing import AsyncGenerator, Optional, Union
import json
import logfire
from openai import AsyncOpenAI

from services.ai_agents.base_agent import BaseAgent, AgentResponse, ToolCall
from services.ai_agents.registry import AgentRegistry
from services.ai_tools import ToolRegistry, AgentContext, create_registry_from_tools
from services.ai_tools.delegation_tool import create_delegation_tool


class MainAgent(BaseAgent):
    """
    Orchestrator agent that routes user requests to specialized sub-agents.

    The main agent analyzes user intent and delegates to the appropriate
    sub-agent for handling. It can also answer general questions or
    provide guidance on financial management.
    """

    def __init__(
        self,
        client: AsyncOpenAI,
        agent_registry: Optional[AgentRegistry] = None
    ):
        super().__init__(client)
        self._agent_registry = agent_registry or AgentRegistry(client)

    @property
    def name(self) -> str:
        return "main_agent"

    @property
    def description(self) -> str:
        return "Main orchestrator that routes requests to specialized agents"

    @property
    def system_prompt(self) -> str:
        agent_info = self._agent_registry.get_agent_info()
        agent_list = "\n".join([
            f"- {a['name']}: {a['description']}"
            for a in agent_info
        ])

        return f"""You are a helpful financial assistant that can help users manage their personal finances.

When users ask about specific operations, delegate to the appropriate specialized agent using the delegate_to_agent tool.

Available specialized agents:
{agent_list}

Guidelines:
1. For questions about accounts/balances -> delegate to account_agent
2. For recording or searching transactions -> delegate to transaction_agent
3. For budget questions or creation -> delegate to budget_agent
4. For spending analysis, reports, trends -> delegate to analytics_agent
5. For managing categories or tags -> delegate to category_agent
6. For receipt/check images (user sends an image) -> delegate to transaction_agent with a task like "Extract transaction data from the attached receipt/check image and help the user create a transaction"

For general questions about finance or guidance that don't require data access, you can answer directly without delegation.

When delegating, provide a clear, specific task description to the sub-agent.

Be friendly and helpful. If you're unsure which agent to use, ask the user for clarification."""

    def get_tool_registry(self) -> ToolRegistry:
        agent_names = self._agent_registry.get_all_names()
        delegation_tool = create_delegation_tool(agent_names)
        return create_registry_from_tools(delegation_tool)

    async def run(
        self,
        user_message: Union[str, list],
        context: AgentContext,
        conversation_history: Optional[list[dict]] = None,
        stream: bool = False
    ) -> AsyncGenerator[str, None] | AgentResponse:
        """
        Execute main agent with delegation support.

        This overrides the base run() to handle delegation specially -
        when a delegation is detected, it executes the sub-agent and
        streams/returns its response.

        Args:
            user_message: Text string or multimodal content list (for images)
            context: AgentContext with user_id, chat_id, repo
            conversation_history: Optional list of previous messages
            stream: If True, yields SSE-formatted chunks. If False, returns AgentResponse.
        """
        messages = [{"role": "system", "content": self.system_prompt}]
        if conversation_history:
            messages.extend(conversation_history)
        messages.append({"role": "user", "content": user_message})

        registry = self.get_tool_registry()
        tools = registry.get_schemas()

        with logfire.span(f"agent.{self.name}.run", user_id=str(context.user_id), messages=messages, tools=tools):
            if stream:
                async for chunk in self._stream_with_delegation(
                    messages, tools, registry, context, user_message
                ):
                    yield chunk
            else:
                response = await self._complete_with_delegation(
                    messages, tools, registry, context, user_message
                )
                yield response

    async def _stream_with_delegation(
        self,
        messages: list[dict],
        tools: list[dict],
        registry: ToolRegistry,
        context: AgentContext,
        original_message: Union[str, list],
    ) -> AsyncGenerator[str, None]:
        """Stream response with delegation handling."""
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
                    # Check if this is a delegation
                    for idx in sorted(tool_calls_buffer.keys()):
                        tc_data = tool_calls_buffer[idx]
                        if tc_data["name"] == "delegate_to_agent":
                            args = json.loads(tc_data["arguments"]) if tc_data["arguments"] else {}
                            agent_name = args.get("agent_name")
                            task = args.get("task", original_message)

                            # If original message is multimodal (has image),
                            # build a multimodal message for the sub-agent
                            # with the delegation task text + original image
                            if isinstance(original_message, list):
                                sub_message = [
                                    {"type": "text", "text": task},
                                    *[
                                        block for block in original_message
                                        if block.get("type") == "image_url"
                                    ],
                                ]
                            else:
                                sub_message = task

                            # Signal delegation
                            yield f"data: {json.dumps({'type': 'delegation', 'agent': agent_name}, ensure_ascii=False)}\n\n"

                            # Execute sub-agent
                            sub_agent = self._agent_registry.get(agent_name)
                            if sub_agent:
                                async for sub_chunk in sub_agent.run(
                                    sub_message, context, stream=True
                                ):
                                    yield sub_chunk
                            else:
                                yield f"data: {json.dumps({'type': 'error', 'message': f'Unknown agent: {agent_name}'}, ensure_ascii=False)}\n\n"
                            return

                yield f"data: {json.dumps({'type': 'done', 'finish_reason': finish_reason}, ensure_ascii=False)}\n\n"

    async def _complete_with_delegation(
        self,
        messages: list[dict],
        tools: list[dict],
        registry: ToolRegistry,
        context: AgentContext,
        original_message: Union[str, list],
    ) -> AgentResponse:
        """Get complete response with delegation handling (non-streaming)."""
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
            # Check for delegation
            for tc in choice.message.tool_calls:
                if tc.function.name == "delegate_to_agent":
                    args = json.loads(tc.function.arguments) if tc.function.arguments else {}
                    agent_name = args.get("agent_name")
                    task = args.get("task", original_message)

                    # If original message is multimodal (has image),
                    # build a multimodal message for the sub-agent
                    if isinstance(original_message, list):
                        sub_message = [
                            {"type": "text", "text": task},
                            *[
                                block for block in original_message
                                if block.get("type") == "image_url"
                            ],
                        ]
                    else:
                        sub_message = task

                    sub_agent = self._agent_registry.get(agent_name)
                    if sub_agent:
                        # Run sub-agent and return its response
                        async for result in sub_agent.run(sub_message, context, stream=False):
                            return result
                    else:
                        return AgentResponse(
                            content=f"Error: Unknown agent '{agent_name}'",
                            finish_reason="error"
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
