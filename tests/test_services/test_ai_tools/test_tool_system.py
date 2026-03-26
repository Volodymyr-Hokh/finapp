"""
Tests for the @ai_tool decorator, ToolRegistry, and ToolParam.
"""
import pytest
from typing import Annotated, Optional
from uuid import uuid4

from services.ai_tools import (
    ai_tool,
    ToolParam,
    ToolRegistry,
    AgentContext,
    ToolDefinition,
    create_registry_from_tools,
    get_global_registry,
)


class TestToolParam:
    """Tests for ToolParam dataclass."""

    def test_tool_param_with_description_only(self):
        """Test creating ToolParam with just a description."""
        param = ToolParam("A test parameter")

        assert param.description == "A test parameter"
        assert param.enum is None

    def test_tool_param_with_enum(self):
        """Test creating ToolParam with enum values."""
        param = ToolParam("Type of transaction", enum=["income", "expense"])

        assert param.description == "Type of transaction"
        assert param.enum == ["income", "expense"]


class TestAgentContext:
    """Tests for AgentContext dataclass."""

    def test_agent_context_creation(self, repo):
        """Test creating AgentContext."""
        user_id = uuid4()
        chat_id = uuid4()

        ctx = AgentContext(
            user_id=user_id,
            chat_id=chat_id,
            repo=repo
        )

        assert ctx.user_id == user_id
        assert ctx.chat_id == chat_id
        assert ctx.repo == repo


class TestAiToolDecorator:
    """Tests for the @ai_tool decorator."""

    def test_decorator_registers_tool_globally(self):
        """Test that @ai_tool registers the tool in global registry."""
        @ai_tool
        async def test_tool_global(ctx: AgentContext) -> dict:
            """A test tool for global registration."""
            return {"result": "success"}

        registry = get_global_registry()
        tool = registry.get("test_tool_global")

        assert tool is not None
        assert tool.name == "test_tool_global"

    def test_decorator_extracts_docstring(self):
        """Test that @ai_tool extracts the docstring as description."""
        @ai_tool
        async def documented_tool(ctx: AgentContext) -> dict:
            """This is the tool description."""
            return {}

        assert documented_tool._tool_definition.description == "This is the tool description."

    def test_decorator_generates_schema_from_params(self):
        """Test that @ai_tool generates correct schema from parameters."""
        @ai_tool
        async def param_tool(
            ctx: AgentContext,
            name: Annotated[str, ToolParam("The name")],
            count: Annotated[int, ToolParam("The count")] = 10,
        ) -> dict:
            """Tool with parameters."""
            return {}

        schema = param_tool._tool_definition.schema
        params = schema["function"]["parameters"]

        assert "name" in params["properties"]
        assert "count" in params["properties"]
        assert params["properties"]["name"]["type"] == "string"
        assert params["properties"]["count"]["type"] == "integer"
        assert "name" in params["required"]
        assert "count" not in params["required"]  # Has default

    def test_decorator_handles_optional_params(self):
        """Test that @ai_tool handles Optional types correctly."""
        @ai_tool
        async def optional_tool(
            ctx: AgentContext,
            query: Annotated[Optional[str], ToolParam("Optional query")] = None,
        ) -> dict:
            """Tool with optional param."""
            return {}

        schema = optional_tool._tool_definition.schema
        params = schema["function"]["parameters"]

        assert "query" in params["properties"]
        assert params["properties"]["query"]["type"] == "string"
        assert "query" not in params["required"]

    def test_decorator_handles_enum(self):
        """Test that @ai_tool includes enum values in schema."""
        @ai_tool
        async def enum_tool(
            ctx: AgentContext,
            type: Annotated[str, ToolParam("Transaction type", enum=["income", "expense"])],
        ) -> dict:
            """Tool with enum."""
            return {}

        schema = enum_tool._tool_definition.schema
        params = schema["function"]["parameters"]

        assert params["properties"]["type"]["enum"] == ["income", "expense"]

    def test_decorator_handles_list_params(self):
        """Test that @ai_tool handles list types."""
        @ai_tool
        async def list_tool(
            ctx: AgentContext,
            tags: Annotated[list[str], ToolParam("List of tags")],
        ) -> dict:
            """Tool with list param."""
            return {}

        schema = list_tool._tool_definition.schema
        params = schema["function"]["parameters"]

        assert params["properties"]["tags"]["type"] == "array"
        assert params["properties"]["tags"]["items"]["type"] == "string"

    def test_decorator_rejects_sync_functions(self):
        """Test that @ai_tool rejects non-async functions."""
        with pytest.raises(TypeError, match="requires an async function"):
            @ai_tool
            def sync_tool(ctx: AgentContext) -> dict:
                """Sync tool."""
                return {}

    def test_decorator_attaches_tool_definition(self):
        """Test that @ai_tool attaches _tool_definition to the function."""
        @ai_tool
        async def attached_tool(ctx: AgentContext) -> dict:
            """Test tool."""
            return {}

        assert hasattr(attached_tool, "_tool_definition")
        assert isinstance(attached_tool._tool_definition, ToolDefinition)


class TestToolRegistry:
    """Tests for ToolRegistry class."""

    def test_registry_register_and_get(self):
        """Test registering and retrieving tools."""
        registry = ToolRegistry()

        async def dummy_tool(ctx, **kwargs):
            return {}

        tool = ToolDefinition(
            name="test_tool",
            description="Test",
            schema={"type": "function", "function": {"name": "test_tool"}},
            func=dummy_tool
        )

        registry.register(tool)

        assert registry.get("test_tool") == tool
        assert registry.get("nonexistent") is None

    def test_registry_get_all(self):
        """Test getting all tools."""
        registry = ToolRegistry()

        async def dummy1(ctx, **kwargs):
            return {}

        async def dummy2(ctx, **kwargs):
            return {}

        tool1 = ToolDefinition("tool1", "Desc1", {}, dummy1)
        tool2 = ToolDefinition("tool2", "Desc2", {}, dummy2)

        registry.register(tool1)
        registry.register(tool2)

        all_tools = registry.get_all()

        assert len(all_tools) == 2
        assert tool1 in all_tools
        assert tool2 in all_tools

    def test_registry_get_schemas(self):
        """Test getting OpenAI schemas for all tools."""
        registry = ToolRegistry()

        async def dummy(ctx, **kwargs):
            return {}

        schema1 = {"type": "function", "function": {"name": "tool1"}}
        schema2 = {"type": "function", "function": {"name": "tool2"}}

        registry.register(ToolDefinition("tool1", "Desc1", schema1, dummy))
        registry.register(ToolDefinition("tool2", "Desc2", schema2, dummy))

        schemas = registry.get_schemas()

        assert len(schemas) == 2
        assert schema1 in schemas
        assert schema2 in schemas

    @pytest.mark.asyncio
    async def test_registry_execute_tool(self, repo):
        """Test executing a tool through the registry."""
        registry = ToolRegistry()

        async def add_tool(ctx: AgentContext, a: int, b: int) -> dict:
            return {"sum": a + b}

        tool = ToolDefinition(
            name="add",
            description="Add numbers",
            schema={},
            func=add_tool
        )
        registry.register(tool)

        ctx = AgentContext(user_id=uuid4(), chat_id=uuid4(), repo=repo)
        result = await registry.execute("add", {"a": 2, "b": 3}, ctx)

        import json
        assert json.loads(result) == {"sum": 5}

    @pytest.mark.asyncio
    async def test_registry_execute_unknown_tool(self, repo):
        """Test executing an unknown tool returns error."""
        registry = ToolRegistry()

        ctx = AgentContext(user_id=uuid4(), chat_id=uuid4(), repo=repo)
        result = await registry.execute("unknown", {}, ctx)

        import json
        assert "error" in json.loads(result)
        assert "Unknown tool" in json.loads(result)["error"]

    @pytest.mark.asyncio
    async def test_registry_execute_handles_exceptions(self, repo):
        """Test that registry handles tool exceptions gracefully."""
        registry = ToolRegistry()

        async def failing_tool(ctx: AgentContext) -> dict:
            raise ValueError("Tool failed!")

        tool = ToolDefinition("failing", "Fails", {}, failing_tool)
        registry.register(tool)

        ctx = AgentContext(user_id=uuid4(), chat_id=uuid4(), repo=repo)
        result = await registry.execute("failing", {}, ctx)

        import json
        assert "error" in json.loads(result)
        assert "Tool failed!" in json.loads(result)["error"]


class TestCreateRegistryFromTools:
    """Tests for create_registry_from_tools helper."""

    def test_creates_registry_from_decorated_functions(self):
        """Test creating registry from @ai_tool decorated functions."""
        @ai_tool
        async def tool_a(ctx: AgentContext) -> dict:
            """Tool A."""
            return {}

        @ai_tool
        async def tool_b(ctx: AgentContext) -> dict:
            """Tool B."""
            return {}

        registry = create_registry_from_tools(tool_a, tool_b)

        assert registry.get("tool_a") is not None
        assert registry.get("tool_b") is not None
        assert len(registry.get_all()) == 2

    def test_raises_for_non_decorated_functions(self):
        """Test that create_registry_from_tools raises for non-decorated functions."""
        async def plain_func(ctx: AgentContext) -> dict:
            return {}

        with pytest.raises(ValueError, match="not decorated"):
            create_registry_from_tools(plain_func)
