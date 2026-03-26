from sanic import Blueprint, Request, json
from sanic_ext import validate, openapi
from sanic.exceptions import BadRequest
from sqlalchemy.exc import IntegrityError

from schemas.budgets import (
    BudgetCreate,
    BudgetRead,
    BudgetUpdate,
    BudgetReadWithProgress,
    BudgetProgress,
)
from schemas.shared import ErrorResponse, MessageResponse, UnauthorizedResponse, ValidationErrorResponse
from schemas.responses import BudgetListResponse
from services.auth import protected
from services.budget_progress import budget_to_response_with_progress

budget_bp = Blueprint("Budget", url_prefix="/budgets")


@budget_bp.post("/")
@openapi.summary("Create a new budget")
@openapi.description("Creates a new budget limit for a specific category and time period.")
@openapi.secured("BearerAuth")
@openapi.body({"application/json": BudgetCreate.model_json_schema()})
@openapi.response(201, {"application/json": BudgetRead.model_json_schema()}, "Budget created")
@openapi.response(400, {"application/json": ErrorResponse.model_json_schema()}, "Budget already exists for this category/period")
@openapi.response(401, {"application/json": UnauthorizedResponse.model_json_schema()}, "Unauthorized")
@openapi.response(422, {"application/json": ValidationErrorResponse.model_json_schema()}, "Validation error")
@protected
@validate(json=BudgetCreate)
async def create_budget(request: Request, body: BudgetCreate):
    """Endpoint to create a new budget for a category."""
    repo = request.app.ctx.repo.budgets
    user_id = request.ctx.user_id

    # Use by_alias=True to get 'category_id' instead of 'category' (the field name)
    # This prevents SQLAlchemy from confusing the 'category' relationship with the FK value
    data = body.model_dump(by_alias=True)
    try:
        new_budget = await repo.create(user_id=user_id, **data)
    except IntegrityError:
        raise BadRequest(
            "Budget for this category and period already exists."
        )

    # Reload with category relationship
    budget_with_category = await repo.get_with_category(new_budget.id)

    return json(BudgetRead.model_validate(budget_with_category).model_dump(mode="json"), status=201)


@budget_bp.get("/")
@openapi.summary("List all user budgets with progress")
@openapi.description("Returns a list of all budgets belonging to the authenticated user, including spending progress.")
@openapi.secured("BearerAuth")
@openapi.response(200, {"application/json": BudgetListResponse.model_json_schema()}, "List of budgets with progress")
@openapi.response(401, {"application/json": UnauthorizedResponse.model_json_schema()}, "Unauthorized")
@protected
async def list_budgets(request: Request):
    """Retrieve all budgets for the current user with progress information."""
    repo = request.app.ctx.repo.budgets
    user_id = request.ctx.user_id

    budgets_with_progress = await repo.get_user_budgets_with_progress(user_id)

    return json({
        "budgets": [
            budget_to_response_with_progress(budget, spent, count).model_dump(mode="json")
            for budget, spent, count in budgets_with_progress
        ]
    })


@budget_bp.get("/<budget_id:int>")
@openapi.summary("Get budget details with progress")
@openapi.description("Fetch a single budget by ID with spending progress, ensuring user ownership.")
@openapi.secured("BearerAuth")
@openapi.response(200, {"application/json": BudgetReadWithProgress.model_json_schema()})
@openapi.response(401, {"application/json": UnauthorizedResponse.model_json_schema()}, "Unauthorized")
@openapi.response(404, {"application/json": ErrorResponse.model_json_schema()}, "Budget not found")
@protected
async def get_budget(request: Request, budget_id: int):
    """Retrieve a specific budget by ID with progress information."""
    repo = request.app.ctx.repo.budgets
    user_id = request.ctx.user_id

    budget, spent, count = await repo.get_budget_with_progress(budget_id, user_id)

    if not budget:
        return json({"error": "Budget not found"}, status=404)

    response = budget_to_response_with_progress(budget, spent, count)
    return json(response.model_dump(mode="json"))


@budget_bp.patch("/<budget_id:int>")
@openapi.summary("Update budget")
@openapi.description("Partially update budget details like limit amount or time period.")
@openapi.secured("BearerAuth")
@openapi.body({"application/json": BudgetUpdate.model_json_schema()})
@openapi.response(200, {"application/json": BudgetRead.model_json_schema()}, "Budget updated")
@openapi.response(400, {"application/json": ErrorResponse.model_json_schema()}, "No changes provided")
@openapi.response(401, {"application/json": UnauthorizedResponse.model_json_schema()}, "Unauthorized")
@openapi.response(404, {"application/json": ErrorResponse.model_json_schema()}, "Budget not found")
@openapi.response(422, {"application/json": ValidationErrorResponse.model_json_schema()}, "Validation error")
@protected
@validate(json=BudgetUpdate)
async def update_budget(request: Request, budget_id: int, body: BudgetUpdate):
    """Update budget fields if provided."""
    repo = request.app.ctx.repo.budgets
    user_id = request.ctx.user_id

    budget = await repo.get(id=budget_id, user_id=user_id)
    if not budget:
        return json({"error": "Budget not found"}, status=404)

    # Use by_alias=True to get 'category_id' instead of 'category' (the field name)
    update_data = body.model_dump(exclude_unset=True, by_alias=True)
    if not update_data:
        return json({"message": "No changes provided"}, status=400)

    await repo.update(id=budget_id, **update_data)

    updated_budget = await repo.get_with_category(budget_id)
    return json(BudgetRead.model_validate(updated_budget).model_dump(mode="json"))


@budget_bp.delete("/<budget_id:int>")
@openapi.summary("Delete budget")
@openapi.description("Permanently removes a budget.")
@openapi.secured("BearerAuth")
@openapi.response(200, {"application/json": MessageResponse.model_json_schema()}, "Success message")
@openapi.response(401, {"application/json": UnauthorizedResponse.model_json_schema()}, "Unauthorized")
@openapi.response(404, {"application/json": ErrorResponse.model_json_schema()}, "Budget not found")
@protected
async def delete_budget(request: Request, budget_id: int):
    """Perform a hard delete on a user's budget."""
    repo = request.app.ctx.repo.budgets
    user_id = request.ctx.user_id

    budget = await repo.get(id=budget_id, user_id=user_id)
    if not budget:
        return json({"error": "Budget not found"}, status=404)

    await repo.delete_budget(budget)
    return json({"message": "Budget deleted successfully"}, status=200)
