"""
Category and tag management tools for AI agents.
"""
from typing import Annotated, Optional

from services.ai_tools import ai_tool, ToolParam, AgentContext


@ai_tool
async def get_categories(ctx: AgentContext) -> dict:
    """Get all available categories (system categories + user's custom categories)."""
    categories = await ctx.repo.categories.get_available_categories(ctx.user_id)

    return {
        "categories": [
            {
                "id": c.id,
                "name": c.name,
                "icon": c.icon,
                "is_system": c.user_id is None
            }
            for c in categories
        ],
        "count": len(categories)
    }


@ai_tool
async def create_category(
    ctx: AgentContext,
    name: Annotated[str, ToolParam("Category name, e.g., 'Groceries', 'Entertainment'")],
    icon: Annotated[Optional[str], ToolParam("Optional emoji icon for the category")] = None
) -> dict:
    """Create a new custom category for the user."""
    # Validate unique name
    is_valid, error = await ctx.repo.categories.validate_unique_name(name, ctx.user_id, None)
    if not is_valid:
        return {"error": error}

    category = await ctx.repo.categories.create(
        name=name,
        icon=icon,
        user_id=ctx.user_id
    )

    return {
        "success": True,
        "category": {
            "id": category.id,
            "name": category.name,
            "icon": category.icon
        },
        "message": f"Category '{name}' created successfully"
    }


@ai_tool
async def delete_category(
    ctx: AgentContext,
    category_id: Annotated[int, ToolParam("The category ID to delete")]
) -> dict:
    """Delete a user's custom category. System categories cannot be deleted."""
    category = await ctx.repo.categories.get_by_id_and_user(category_id, ctx.user_id)
    if not category:
        return {"error": f"Category with ID {category_id} not found or is a system category"}

    name = category.name
    await ctx.repo.categories.delete_category(category)

    return {
        "success": True,
        "category_id": category_id,
        "message": f"Category '{name}' deleted successfully"
    }


@ai_tool
async def get_tags(ctx: AgentContext) -> dict:
    """Get all tags created by the user."""
    tags = await ctx.repo.tags.get_user_tags(ctx.user_id)

    return {
        "tags": [
            {
                "id": t.id,
                "name": t.name
            }
            for t in tags
        ],
        "count": len(tags)
    }


@ai_tool
async def create_tags(
    ctx: AgentContext,
    names: Annotated[list[str], ToolParam("List of tag names to create")]
) -> dict:
    """Create one or more tags. Tags that already exist will be returned without error."""
    tags = await ctx.repo.tags.get_or_create_tags(ctx.user_id, names)

    return {
        "success": True,
        "tags": [
            {
                "id": t.id,
                "name": t.name
            }
            for t in tags
        ],
        "count": len(tags),
        "message": f"Created/retrieved {len(tags)} tag(s)"
    }


@ai_tool
async def delete_tag(
    ctx: AgentContext,
    tag_id: Annotated[int, ToolParam("The tag ID to delete")]
) -> dict:
    """Delete a tag. This will remove the tag from all transactions."""
    tag = await ctx.repo.tags.get_by_id(tag_id, ctx.user_id)
    if not tag:
        return {"error": f"Tag with ID {tag_id} not found"}

    name = tag.name
    await ctx.repo.tags.delete_tag(tag)

    return {
        "success": True,
        "tag_id": tag_id,
        "message": f"Tag '{name}' deleted successfully"
    }
