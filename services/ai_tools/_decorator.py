"""The @ai_tool decorator and related utilities."""
import functools
import inspect
from typing import (
    Annotated,
    Any,
    Callable,
    Union,
    get_args,
    get_origin,
    get_type_hints,
)

from ._types import AgentContext, ToolDefinition, ToolParam
from ._registry import ToolRegistry, _global_registry


def _python_type_to_json_schema(python_type: type) -> dict:
    """Convert Python type hint to JSON Schema type."""
    origin = get_origin(python_type)

    # Handle Optional[X] which is Union[X, None]
    if origin is Union:
        args = get_args(python_type)
        # Filter out NoneType
        non_none_args = [a for a in args if a is not type(None)]
        if len(non_none_args) == 1:
            return _python_type_to_json_schema(non_none_args[0])

    # Handle list[X]
    if origin is list:
        args = get_args(python_type)
        item_type = args[0] if args else str
        return {
            "type": "array",
            "items": _python_type_to_json_schema(item_type)
        }

    # Basic type mapping
    type_map = {
        str: {"type": "string"},
        int: {"type": "integer"},
        float: {"type": "number"},
        bool: {"type": "boolean"},
    }

    return type_map.get(python_type, {"type": "string"})


def _extract_tool_param(annotation: Any) -> ToolParam | None:
    """Extract ToolParam from Annotated type if present."""
    if get_origin(annotation) is Annotated:
        args = get_args(annotation)
        for arg in args[1:]:  # Skip the first arg (the actual type)
            if isinstance(arg, ToolParam):
                return arg
    return None


def _get_base_type(annotation: Any) -> type:
    """Get the base type from an annotation (handles Annotated and Optional)."""
    # Handle Annotated[T, ...]
    if get_origin(annotation) is Annotated:
        annotation = get_args(annotation)[0]

    # Handle Optional[T] which is Union[T, None]
    origin = get_origin(annotation)
    if origin is Union:
        args = get_args(annotation)
        non_none_args = [a for a in args if a is not type(None)]
        if len(non_none_args) == 1:
            return non_none_args[0]

    return annotation


def ai_tool(func: Callable) -> Callable:
    """
    Decorator that registers an async function as an AI tool.

    Auto-generates OpenAI function calling schema from:
    - Function name -> tool name
    - Docstring -> tool description
    - Annotated parameters with ToolParam -> parameter schema
    - Type hints -> JSON Schema types
    - Default values -> required vs optional

    The first parameter must be AgentContext (auto-injected, not exposed to LLM).

    Example:
        @ai_tool
        async def get_transactions(
            ctx: AgentContext,
            from_date: Annotated[Optional[str], ToolParam("Start date YYYY-MM-DD")] = None,
            limit: Annotated[int, ToolParam("Max results")] = 20,
        ) -> dict:
            '''Search user transactions with filters.'''
            ...
    """
    if not inspect.iscoroutinefunction(func):
        raise TypeError(f"@ai_tool requires an async function, got {func}")

    # Get function signature and type hints
    sig = inspect.signature(func)
    hints = get_type_hints(func, include_extras=True)

    # Extract tool metadata
    tool_name = func.__name__
    tool_description = (func.__doc__ or "").strip()

    # Build parameter schema
    properties: dict[str, dict] = {}
    required: list[str] = []

    params = list(sig.parameters.items())

    # Skip first parameter (AgentContext)
    for param_name, param in params[1:]:  # Skip ctx
        annotation = hints.get(param_name, str)

        # Get ToolParam metadata
        tool_param = _extract_tool_param(annotation)
        if not tool_param:
            # Skip parameters without ToolParam annotation
            continue

        # Get base type for JSON schema
        base_type = _get_base_type(annotation)
        type_schema = _python_type_to_json_schema(base_type)

        # Build property schema
        prop_schema = {
            **type_schema,
            "description": tool_param.description
        }

        if tool_param.enum:
            prop_schema["enum"] = tool_param.enum

        properties[param_name] = prop_schema

        # Check if required (no default value)
        if param.default is inspect.Parameter.empty:
            required.append(param_name)

    # Build OpenAI tool schema
    schema = {
        "type": "function",
        "function": {
            "name": tool_name,
            "description": tool_description,
            "parameters": {
                "type": "object",
                "properties": properties,
                "required": required,
                "additionalProperties": False
            }
        }
    }

    # Create tool definition
    tool_def = ToolDefinition(
        name=tool_name,
        description=tool_description,
        schema=schema,
        func=func
    )

    # Register in global registry
    _global_registry.register(tool_def)

    @functools.wraps(func)
    async def wrapper(ctx: AgentContext, **kwargs):
        return await func(ctx, **kwargs)

    # Attach metadata to wrapper
    wrapper._tool_definition = tool_def

    return wrapper


def create_registry_from_tools(*tool_funcs: Callable) -> ToolRegistry:
    """
    Create a new ToolRegistry from a list of @ai_tool decorated functions.

    This is useful for creating agent-specific registries with a subset of tools.

    Example:
        from services.ai_tools.account_tools import get_accounts, create_account

        registry = create_registry_from_tools(get_accounts, create_account)
    """
    registry = ToolRegistry()
    for func in tool_funcs:
        if hasattr(func, '_tool_definition'):
            registry.register(func._tool_definition)
        else:
            raise ValueError(f"{func.__name__} is not decorated with @ai_tool")
    return registry
