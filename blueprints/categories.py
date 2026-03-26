from sanic import Blueprint, Request, json
from sanic_ext import validate, openapi

from schemas.categories import (
    CategoryCreate,
    CategoryRead,
    CategoryUpdate
)
from schemas.shared import CategorySummary, ErrorResponse, MessageResponse, UnauthorizedResponse, ValidationErrorResponse
from schemas.responses import CategoryListResponse
from services.auth import protected

category_bp = Blueprint("Category", url_prefix="/categories")


@category_bp.post("/")
@openapi.summary("Create a new category")
@openapi.description("Creates a new custom category for the authenticated user.")
@openapi.secured("BearerAuth")
@openapi.body({"application/json": CategoryCreate.model_json_schema()})
@openapi.response(201, {"application/json": CategoryRead.model_json_schema()}, "Category created")
@openapi.response(400, {"application/json": ErrorResponse.model_json_schema()}, "Category name already exists")
@openapi.response(401, {"application/json": UnauthorizedResponse.model_json_schema()}, "Unauthorized")
@openapi.response(422, {"application/json": ValidationErrorResponse.model_json_schema()}, "Validation error")
@protected
@validate(json=CategoryCreate)
async def create_category(request: Request, body: CategoryCreate):
    """Endpoint to create a new category linked to the user."""
    repo = request.app.ctx.repo.categories
    user_id = request.ctx.user_id

    # Validate unique name
    try:
        await repo.validate_unique_name(body.name, user_id)
    except ValueError as e:
        return json({"error": str(e)}, status=400)

    data = body.model_dump()
    new_category = await repo.create(user_id=user_id, **data)

    return json(CategoryRead.model_validate(new_category).model_dump(mode="json"), status=201)


@category_bp.get("/")
@openapi.summary("List all available categories")
@openapi.description("Returns all categories available to the user (system categories + user's custom categories).")
@openapi.secured("BearerAuth")
@openapi.response(200, {"application/json": CategoryListResponse.model_json_schema()}, "List of categories")
@openapi.response(401, {"application/json": UnauthorizedResponse.model_json_schema()}, "Unauthorized")
@protected
async def list_categories(request: Request):
    """Retrieve all categories for the current user (system + custom)."""
    repo = request.app.ctx.repo.categories
    user_id = request.ctx.user_id

    # Fetch both system categories (user_id is null) and user's custom categories
    categories = await repo.get_available_categories(user_id)

    return json({
        "categories": [
            CategorySummary.model_validate(c).model_dump(mode="json") for c in categories
        ]
    })


@category_bp.get("/<category_id:int>")
@openapi.summary("Get category details")
@openapi.description("Fetch a single category by ID.")
@openapi.secured("BearerAuth")
@openapi.response(200, {"application/json": CategoryRead.model_json_schema()})
@openapi.response(401, {"application/json": UnauthorizedResponse.model_json_schema()}, "Unauthorized")
@openapi.response(404, {"application/json": ErrorResponse.model_json_schema()}, "Category not found")
@protected
async def get_category(request: Request, category_id: int):
    """Retrieve a specific category by ID."""
    repo = request.app.ctx.repo.categories
    user_id = request.ctx.user_id

    # User can access both system categories and their own custom categories
    category = await repo.get_with_user(category_id)

    if not category:
        return json({"error": "Category not found"}, status=404)

    # Check if the category is a system category or belongs to the user
    if category.user_id is not None and str(category.user_id) != str(user_id):
        return json({"error": "Category not found"}, status=404)

    return json(CategorySummary.model_validate(category).model_dump(mode="json"))


@category_bp.patch("/<category_id:int>")
@openapi.summary("Update category")
@openapi.description("Update a custom category. System categories cannot be modified.")
@openapi.secured("BearerAuth")
@openapi.body({"application/json": CategoryUpdate.model_json_schema()})
@openapi.response(200, {"application/json": CategoryRead.model_json_schema()})
@openapi.response(400, {"application/json": ErrorResponse.model_json_schema()}, "Category name already exists or no changes provided")
@openapi.response(401, {"application/json": UnauthorizedResponse.model_json_schema()}, "Unauthorized")
@openapi.response(403, {"application/json": ErrorResponse.model_json_schema()}, "Cannot modify system categories")
@openapi.response(404, {"application/json": ErrorResponse.model_json_schema()}, "Category not found")
@openapi.response(422, {"application/json": ValidationErrorResponse.model_json_schema()}, "Validation error")
@protected
@validate(json=CategoryUpdate)
async def update_category(request: Request, category_id: int, body: CategoryUpdate):
    """Update category fields if provided. Only custom categories can be updated."""
    repo = request.app.ctx.repo.categories
    user_id = request.ctx.user_id

    # Verify existence and ownership
    category = await repo.get_with_user(category_id)
    if not category:
        return json({"error": "Category not found"}, status=404)

    # System categories cannot be modified
    if category.user_id is None:
        return json({"error": "Cannot modify system categories"}, status=403)

    # Check ownership
    if str(category.user_id) != str(user_id):
        return json({"error": "Category not found"}, status=404)

    update_data = body.model_dump(exclude_unset=True)
    if not update_data:
        return json({"message": "No changes provided"}, status=400)

    # Validate unique name if name is being updated
    if "name" in update_data:
        try:
            await repo.validate_unique_name(update_data["name"], user_id, category_id)
        except ValueError as e:
            return json({"error": str(e)}, status=400)

    await repo.update(id=category_id, **update_data)

    updated_category = await repo.get(id=category_id)
    return json(CategoryRead.model_validate(updated_category).model_dump(mode="json"))


@category_bp.delete("/<category_id:int>")
@openapi.summary("Delete category")
@openapi.description("Permanently removes a custom category.")
@openapi.secured("BearerAuth")
@openapi.response(200, {"application/json": MessageResponse.model_json_schema()}, "Success message")
@openapi.response(400, {"application/json": ErrorResponse.model_json_schema()}, "Database error")
@openapi.response(401, {"application/json": UnauthorizedResponse.model_json_schema()}, "Unauthorized")
@openapi.response(404, {"application/json": ErrorResponse.model_json_schema()}, "Category not found")
@protected
async def delete_category(request: Request, category_id: int):
    repo = request.app.ctx.repo.categories
    user_id = request.ctx.user_id

    category = await repo.get_by_id_and_user(category_id, user_id)

    if not category:
        return json({"error": "Category not found"}, status=404)

    try:
        await repo.delete_category(category)
        return json({"message": "Category deleted successfully"}, status=200)
    except Exception as e:
        return json({"error": f"Database error: {str(e)}"}, status=400)
