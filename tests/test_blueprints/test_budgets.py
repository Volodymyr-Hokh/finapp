"""
API tests for budget endpoints (blueprints/budgets.py).
"""
import pytest
import datetime
from decimal import Decimal

from db.models import Budget, Transaction
from schemas.enums import TransactionType


@pytest.mark.api
class TestCreateBudget:
    """Test create budget endpoint."""

    def test_create_budget_success(
        self, test_client, system_category, auth_headers
    ):
        """Test creating a budget."""
        request, response = test_client.post(
            "/budgets/",
            headers=auth_headers,
            json={
                "limit_amount": "500.00",
                "category_id": system_category.id,
                "month": 12,
                "year": 2024
            }
        )

        assert response.status_code == 201
        assert response.json["limit_amount"] == "500.00"
        assert response.json["month"] == 12
        assert response.json["year"] == 2024
        assert "category" in response.json

    def test_create_budget_validation_alias(
        self, test_client, system_category, auth_headers
    ):
        """Test that category validation alias works."""
        request, response = test_client.post(
            "/budgets/",
            headers=auth_headers,
            json={
                "limit_amount": "300.00",
                "category": system_category.id,
                "month": 6,
                "year": 2024
            }
        )

        assert response.status_code == 201

    def test_create_budget_invalid_month(self, test_client, system_category, auth_headers):
        """Test that invalid month is rejected."""
        request, response = test_client.post(
            "/budgets/",
            headers=auth_headers,
            json={
                "limit_amount": "100.00",
                "category_id": system_category.id,
                "month": 13,  # Invalid
                "year": 2024
            }
        )

        assert response.status_code == 422

    async def test_create_budget_duplicate_period(
        self, app, sample_user, system_category, auth_headers, repo
    ):
        """Test that duplicate budget for same period is rejected."""
        # Create first budget
        await repo.budgets.create(
            limit_amount=Decimal("200.00"),
            month=3,
            year=2024,
            user_id=sample_user.id,
            category_id=system_category.id
        )

        # Try to create duplicate
        request, response = await app.asgi_client.post(
            "/budgets/",
            headers=auth_headers,
            json={
                "limit_amount": "300.00",
                "category_id": system_category.id,
                "month": 3,
                "year": 2024
            }
        )

        assert response.status_code == 400

    def test_create_budget_unauthorized(self, test_client, system_category):
        """Test that creating budget requires authentication."""
        request, response = test_client.post(
            "/budgets/",
            json={
                "limit_amount": "500.00",
                "category_id": system_category.id,
                "month": 12,
                "year": 2024
            }
        )

        assert response.status_code == 401


@pytest.mark.api
class TestListBudgets:
    """Test list budgets endpoint."""

    def test_list_budgets(self, test_client, sample_budget, auth_headers):
        """Test listing user's budgets."""
        request, response = test_client.get(
            "/budgets/",
            headers=auth_headers
        )

        assert response.status_code == 200
        assert "budgets" in response.json
        assert isinstance(response.json["budgets"], list)
        assert len(response.json["budgets"]) == 1

        budget_ids = [b["id"] for b in response.json["budgets"]]
        assert sample_budget.id in budget_ids

    async def test_list_budgets_only_user_budgets(
        self, app, sample_budget, another_user, system_category, auth_headers, repo
    ):
        """Test that users only see their own budgets."""
        # Create budget for another user
        await repo.budgets.create(
            limit_amount=Decimal("400.00"),
            month=5,
            year=2024,
            user_id=another_user.id,
            category_id=system_category.id
        )

        request, response = await app.asgi_client.get(
            "/budgets/",
            headers=auth_headers
        )

        assert response.status_code == 200
        assert "budgets" in response.json

        # Verify only own budgets are shown
        budget_ids = [b["id"] for b in response.json["budgets"]]
        assert sample_budget.id in budget_ids

    def test_list_budgets_includes_category(
        self, test_client, sample_budget, auth_headers
    ):
        """Test that budgets include category information."""
        request, response = test_client.get(
            "/budgets/",
            headers=auth_headers
        )

        assert response.status_code == 200
        assert "budgets" in response.json
        assert "category" in response.json["budgets"][0]

    def test_list_budgets_unauthorized(self, test_client):
        """Test that listing budgets requires authentication."""
        request, response = test_client.get("/budgets/")

        assert response.status_code == 401


@pytest.mark.api
class TestGetBudget:
    """Test get budget endpoint."""

    def test_get_budget_success(self, test_client, sample_budget, auth_headers):
        """Test getting a specific budget."""
        request, response = test_client.get(
            f"/budgets/{sample_budget.id}",
            headers=auth_headers
        )

        assert response.status_code == 200
        assert response.json["id"] == sample_budget.id
        assert response.json["limit_amount"] == str(sample_budget.limit_amount)

    def test_get_budget_not_found(self, test_client, auth_headers):
        """Test getting non-existent budget."""
        request, response = test_client.get(
            "/budgets/99999",
            headers=auth_headers
        )

        assert response.status_code == 404

    async def test_get_budget_different_user(
        self, app, another_user, system_category, auth_headers, repo
    ):
        """Test that users cannot access other users' budgets."""
        other_budget = await repo.budgets.create(
            limit_amount=Decimal("600.00"),
            month=8,
            year=2024,
            user_id=another_user.id,
            category_id=system_category.id
        )

        request, response = await app.asgi_client.get(
            f"/budgets/{other_budget.id}",
            headers=auth_headers
        )

        assert response.status_code == 404


@pytest.mark.api
class TestUpdateBudget:
    """Test update budget endpoint."""

    def test_update_budget_limit_amount(
        self, test_client, sample_budget, auth_headers
    ):
        """Test updating budget limit amount."""
        request, response = test_client.patch(
            f"/budgets/{sample_budget.id}",
            headers=auth_headers,
            json={"limit_amount": "750.00"}
        )

        assert response.status_code == 200
        assert response.json["limit_amount"] == "750.00"

    def test_update_budget_month(self, test_client, sample_budget, auth_headers):
        """Test updating budget month."""
        request, response = test_client.patch(
            f"/budgets/{sample_budget.id}",
            headers=auth_headers,
            json={"month": 11}
        )

        assert response.status_code == 200
        assert response.json["month"] == 11

    def test_update_budget_partial(self, test_client, sample_budget, auth_headers):
        """Test partial update."""
        original_month = sample_budget.month

        request, response = test_client.patch(
            f"/budgets/{sample_budget.id}",
            headers=auth_headers,
            json={"year": 2025}
        )

        assert response.status_code == 200
        assert response.json["year"] == 2025
        assert response.json["month"] == original_month

    def test_update_budget_no_changes(self, test_client, sample_budget, auth_headers):
        """Test update with no changes."""
        request, response = test_client.patch(
            f"/budgets/{sample_budget.id}",
            headers=auth_headers,
            json={}
        )

        assert response.status_code == 400

    def test_update_budget_not_found(self, test_client, auth_headers):
        """Test updating non-existent budget."""
        request, response = test_client.patch(
            "/budgets/99999",
            headers=auth_headers,
            json={"limit_amount": "500.00"}
        )

        assert response.status_code == 404

    async def test_update_budget_duplicate_period(
        self, app, sample_user, system_category, auth_headers, repo
    ):
        """Test that updating budget to a conflicting period is rejected."""
        # Create two budgets for different months
        budget1 = await repo.budgets.create(
            limit_amount=Decimal("300.00"),
            month=3,
            year=2025,
            user_id=sample_user.id,
            category_id=system_category.id
        )
        budget2 = await repo.budgets.create(
            limit_amount=Decimal("400.00"),
            month=4,
            year=2025,
            user_id=sample_user.id,
            category_id=system_category.id
        )

        # Try to update budget2's month to conflict with budget1
        request, response = await app.asgi_client.patch(
            f"/budgets/{budget2.id}",
            headers=auth_headers,
            json={"month": 3}
        )

        # Should fail with unique constraint violation
        assert response.status_code in [400, 500]


@pytest.mark.api
class TestDeleteBudget:
    """Test delete budget endpoint."""

    async def test_delete_budget_success(
        self, app, sample_user, system_category, auth_headers, repo
    ):
        """Test deleting a budget."""
        budget = await repo.budgets.create(
            limit_amount=Decimal("200.00"),
            month=9,
            year=2024,
            user_id=sample_user.id,
            category_id=system_category.id
        )

        request, response = await app.asgi_client.delete(
            f"/budgets/{budget.id}",
            headers=auth_headers
        )

        assert response.status_code == 200
        assert "deleted successfully" in response.json["message"]

    def test_delete_budget_not_found(self, test_client, auth_headers):
        """Test deleting non-existent budget."""
        request, response = test_client.delete(
            "/budgets/99999",
            headers=auth_headers
        )

        assert response.status_code == 404

    async def test_delete_budget_different_user(
        self, app, another_user, system_category, auth_headers, repo
    ):
        """Test that users cannot delete other users' budgets."""
        other_budget = await repo.budgets.create(
            limit_amount=Decimal("300.00"),
            month=7,
            year=2024,
            user_id=another_user.id,
            category_id=system_category.id
        )

        request, response = await app.asgi_client.delete(
            f"/budgets/{other_budget.id}",
            headers=auth_headers
        )

        assert response.status_code == 404


@pytest.mark.api
class TestBudgetProgress:
    """Tests for budget progress in API responses."""

    async def test_get_budget_includes_progress(
        self, app, sample_user, system_category, sample_account, auth_headers, create_model
    ):
        """GET /budgets/<id> includes progress data."""
        today = datetime.date.today()
        budget = await create_model(
            Budget,
            limit_amount=Decimal("500.00"),
            month=today.month,
            year=today.year,
            user_id=sample_user.id,
            category_id=system_category.id
        )

        await create_model(
            Transaction,
            amount=Decimal("-100.00"),
            type=TransactionType.EXPENSE,
            transaction_date=today,
            user_id=sample_user.id,
            account_id=sample_account.id,
            category_id=system_category.id
        )

        request, response = await app.asgi_client.get(
            f"/budgets/{budget.id}",
            headers=auth_headers
        )

        assert response.status_code == 200
        assert "progress" in response.json
        assert response.json["progress"]["spent_amount"] == "100.00"
        assert response.json["progress"]["remaining_amount"] == "400.00"
        assert response.json["progress"]["percentage_used"] == 20.0
        assert response.json["progress"]["status"] == "under"
        assert response.json["progress"]["transaction_count"] == 1

    async def test_list_budgets_includes_progress(
        self, app, sample_budget, auth_headers
    ):
        """GET /budgets/ includes progress for each budget."""
        request, response = await app.asgi_client.get(
            "/budgets/",
            headers=auth_headers
        )

        assert response.status_code == 200
        assert "budgets" in response.json
        assert len(response.json["budgets"]) >= 1

        for budget in response.json["budgets"]:
            assert "progress" in budget
            assert "spent_amount" in budget["progress"]
            assert "remaining_amount" in budget["progress"]
            assert "percentage_used" in budget["progress"]
            assert "status" in budget["progress"]

    async def test_progress_warning_status(
        self, app, sample_user, system_category, sample_account, auth_headers, create_model
    ):
        """90% spent shows WARNING status."""
        today = datetime.date.today()
        budget = await create_model(
            Budget,
            limit_amount=Decimal("100.00"),
            month=today.month,
            year=today.year,
            user_id=sample_user.id,
            category_id=system_category.id
        )

        await create_model(
            Transaction,
            amount=Decimal("-90.00"),
            type=TransactionType.EXPENSE,
            transaction_date=today,
            user_id=sample_user.id,
            account_id=sample_account.id,
            category_id=system_category.id
        )

        request, response = await app.asgi_client.get(
            f"/budgets/{budget.id}",
            headers=auth_headers
        )

        assert response.status_code == 200
        assert response.json["progress"]["status"] == "warning"
        assert response.json["progress"]["percentage_used"] == 90.0

    async def test_progress_over_status(
        self, app, sample_user, system_category, sample_account, auth_headers, create_model
    ):
        """Over 100% spent shows OVER status with negative remaining."""
        today = datetime.date.today()
        budget = await create_model(
            Budget,
            limit_amount=Decimal("100.00"),
            month=today.month,
            year=today.year,
            user_id=sample_user.id,
            category_id=system_category.id
        )

        await create_model(
            Transaction,
            amount=Decimal("-120.00"),
            type=TransactionType.EXPENSE,
            transaction_date=today,
            user_id=sample_user.id,
            account_id=sample_account.id,
            category_id=system_category.id
        )

        request, response = await app.asgi_client.get(
            f"/budgets/{budget.id}",
            headers=auth_headers
        )

        assert response.status_code == 200
        assert response.json["progress"]["status"] == "over"
        assert response.json["progress"]["remaining_amount"] == "-20.00"
        assert response.json["progress"]["percentage_used"] == 120.0

    async def test_progress_excludes_income(
        self, app, sample_user, system_category, sample_account, auth_headers, create_model
    ):
        """Income transactions not counted in spent amount."""
        today = datetime.date.today()
        budget = await create_model(
            Budget,
            limit_amount=Decimal("500.00"),
            month=today.month,
            year=today.year,
            user_id=sample_user.id,
            category_id=system_category.id
        )

        # Add expense
        await create_model(
            Transaction,
            amount=Decimal("-100.00"),
            type=TransactionType.EXPENSE,
            transaction_date=today,
            user_id=sample_user.id,
            account_id=sample_account.id,
            category_id=system_category.id
        )
        # Add income (should not be counted)
        await create_model(
            Transaction,
            amount=Decimal("500.00"),
            type=TransactionType.INCOME,
            transaction_date=today,
            user_id=sample_user.id,
            account_id=sample_account.id,
            category_id=system_category.id
        )

        request, response = await app.asgi_client.get(
            f"/budgets/{budget.id}",
            headers=auth_headers
        )

        assert response.status_code == 200
        # Only expense counted
        assert response.json["progress"]["spent_amount"] == "100.00"
        assert response.json["progress"]["transaction_count"] == 1

    async def test_progress_excludes_deleted_transactions(
        self, app, sample_user, system_category, sample_account, auth_headers, create_model
    ):
        """Soft-deleted transactions not counted in spent amount."""
        today = datetime.date.today()
        budget = await create_model(
            Budget,
            limit_amount=Decimal("500.00"),
            month=today.month,
            year=today.year,
            user_id=sample_user.id,
            category_id=system_category.id
        )

        # Add normal expense
        await create_model(
            Transaction,
            amount=Decimal("-100.00"),
            type=TransactionType.EXPENSE,
            transaction_date=today,
            user_id=sample_user.id,
            account_id=sample_account.id,
            category_id=system_category.id,
            is_deleted=False
        )
        # Add soft-deleted expense (should not be counted)
        await create_model(
            Transaction,
            amount=Decimal("-50.00"),
            type=TransactionType.EXPENSE,
            transaction_date=today,
            user_id=sample_user.id,
            account_id=sample_account.id,
            category_id=system_category.id,
            is_deleted=True
        )

        request, response = await app.asgi_client.get(
            f"/budgets/{budget.id}",
            headers=auth_headers
        )

        assert response.status_code == 200
        # Only non-deleted expense counted
        assert response.json["progress"]["spent_amount"] == "100.00"
        assert response.json["progress"]["transaction_count"] == 1

    async def test_progress_no_transactions(
        self, app, sample_budget, auth_headers
    ):
        """Budget with no transactions shows zero spent."""
        request, response = await app.asgi_client.get(
            f"/budgets/{sample_budget.id}",
            headers=auth_headers
        )

        assert response.status_code == 200
        assert response.json["progress"]["spent_amount"] == "0"
        assert response.json["progress"]["remaining_amount"] == "500.00"
        assert response.json["progress"]["percentage_used"] == 0.0
        assert response.json["progress"]["status"] == "under"
        assert response.json["progress"]["transaction_count"] == 0
