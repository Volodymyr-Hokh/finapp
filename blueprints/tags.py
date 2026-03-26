from sanic import Blueprint, Request, json
from sanic_ext import validate, openapi

from schemas.tags import (
    TagCreate,
    TagRead,
    TagUpdate
)
from schemas.shared import ErrorResponse, MessageResponse, TagListResponse, UnauthorizedResponse, ValidationErrorResponse
from services.auth import protected

tag_bp = Blueprint("Tag", url_prefix="/tags")


@tag_bp.post("/")
@openapi.summary("Create a new tag")
@openapi.description("Creates a new tag for the authenticated user. Tag name will be normalized to lowercase.")
@openapi.secured("BearerAuth")
@openapi.body({"application/json": TagCreate.model_json_schema()})
@openapi.response(201, {"application/json": TagRead.model_json_schema()}, "Tag created")
@openapi.response(400, {"application/json": ErrorResponse.model_json_schema()}, "Tag name already exists")
@openapi.response(401, {"application/json": UnauthorizedResponse.model_json_schema()}, "Unauthorized")
@openapi.response(422, {"application/json": ValidationErrorResponse.model_json_schema()}, "Validation error")
@protected
@validate(json=TagCreate)
async def create_tag(request: Request, body: TagCreate):
    """Endpoint to create a new tag linked to the user."""
    repo = request.app.ctx.repo.tags
    user_id = request.ctx.user_id

    # Normalize tag name to lowercase
    tag_name = body.name.strip().lower()

    # Check if tag already exists for this user
    existing_tag = await repo.get_by_name(tag_name, user_id)
    if existing_tag:
        return json({"error": f"Tag '{tag_name}' already exists"}, status=400)

    # Create new tag
    new_tag = await repo.create_tag(tag_name, user_id)

    return json(TagRead.model_validate(new_tag).model_dump(mode="json"), status=201)


@tag_bp.get("/")
@openapi.summary("List all user tags")
@openapi.description("Returns all tag names belonging to the authenticated user.")
@openapi.secured("BearerAuth")
@openapi.response(200, {"application/json": TagListResponse.model_json_schema()}, "List of tag names")
@openapi.response(401, {"application/json": UnauthorizedResponse.model_json_schema()}, "Unauthorized")
@protected
async def list_tags(request: Request):
    """Retrieve all tag names for the current user."""
    repo = request.app.ctx.repo.tags
    user_id = request.ctx.user_id

    tags = await repo.get_user_tags(user_id)

    return json({"tags": [tag.name for tag in tags]})


@tag_bp.get("/<tag_id:int>")
@openapi.summary("Get tag details")
@openapi.description("Fetch a single tag by ID.")
@openapi.secured("BearerAuth")
@openapi.response(200, {"application/json": TagRead.model_json_schema()})
@openapi.response(401, {"application/json": UnauthorizedResponse.model_json_schema()}, "Unauthorized")
@openapi.response(404, {"application/json": ErrorResponse.model_json_schema()}, "Tag not found")
@protected
async def get_tag(request: Request, tag_id: int):
    """Retrieve a specific tag by ID."""
    repo = request.app.ctx.repo.tags
    user_id = request.ctx.user_id

    tag = await repo.get_by_id(tag_id, user_id)

    if not tag:
        return json({"error": "Tag not found"}, status=404)

    return json(TagRead.model_validate(tag).model_dump(mode="json"))


@tag_bp.patch("/<tag_id:int>")
@openapi.summary("Update tag")
@openapi.description("Update a tag name. Name will be normalized to lowercase.")
@openapi.secured("BearerAuth")
@openapi.body({"application/json": TagUpdate.model_json_schema()})
@openapi.response(200, {"application/json": TagRead.model_json_schema()})
@openapi.response(400, {"application/json": ErrorResponse.model_json_schema()}, "Tag name already exists or no changes provided")
@openapi.response(401, {"application/json": UnauthorizedResponse.model_json_schema()}, "Unauthorized")
@openapi.response(404, {"application/json": ErrorResponse.model_json_schema()}, "Tag not found")
@openapi.response(422, {"application/json": ValidationErrorResponse.model_json_schema()}, "Validation error")
@protected
@validate(json=TagUpdate)
async def update_tag(request: Request, tag_id: int, body: TagUpdate):
    """Update tag fields if provided."""
    repo = request.app.ctx.repo.tags
    user_id = request.ctx.user_id

    # Verify existence and ownership
    tag = await repo.get_by_id(tag_id, user_id)
    if not tag:
        return json({"error": "Tag not found"}, status=404)

    update_data = body.model_dump(exclude_unset=True)
    if not update_data:
        return json({"message": "No changes provided"}, status=400)

    # Normalize tag name if being updated
    if "name" in update_data:
        new_name = update_data["name"].strip().lower()

        # Check if another tag with this name exists for this user
        existing_tag = await repo.get_by_name(new_name, user_id)
        if existing_tag and existing_tag.id != tag_id:
            return json({"error": f"Tag '{new_name}' already exists"}, status=400)

        update_data["name"] = new_name

    await repo.update(id=tag_id, **update_data)

    updated_tag = await repo.get(id=tag_id)
    return json(TagRead.model_validate(updated_tag).model_dump(mode="json"))


@tag_bp.delete("/<tag_id:int>")
@openapi.summary("Delete tag")
@openapi.description("Permanently removes a tag.")
@openapi.secured("BearerAuth")
@openapi.response(200, {"application/json": MessageResponse.model_json_schema()}, "Success message")
@openapi.response(401, {"application/json": UnauthorizedResponse.model_json_schema()}, "Unauthorized")
@openapi.response(404, {"application/json": ErrorResponse.model_json_schema()}, "Tag not found")
@protected
async def delete_tag(request: Request, tag_id: int):
    """Perform a hard delete on a user's tag."""
    repo = request.app.ctx.repo.tags
    user_id = request.ctx.user_id

    tag = await repo.get_by_id(tag_id, user_id)
    if not tag:
        return json({"error": "Tag not found"}, status=404)

    try:
        await repo.delete_tag(tag)
        return json({"message": "Tag deleted successfully"}, status=200)
    except Exception as e:
        return json({"error": f"Database error: {str(e)}"}, status=400)
