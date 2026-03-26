"""
API tests for category endpoints (blueprints/categories.py).
"""
import pytest


@pytest.mark.api
class TestCreateCategory:
    """Test create category endpoint."""

    def test_create_category_success(self, test_client, auth_headers):
        """Test creating a category."""
        request, response = test_client.post(
            "/categories/",
            headers=auth_headers,
            json={
                "name": "Custom Food",
                "icon": "🍕"
            }
        )

        assert response.status_code == 201
        assert response.json["name"] == "Custom Food"
        assert response.json["icon"] == "🍕"

    def test_create_category_without_icon(self, test_client, auth_headers):
        """Test creating category without icon."""
        request, response = test_client.post(
            "/categories/",
            headers=auth_headers,
            json={"name": "No Icon Category"}
        )

        assert response.status_code == 201
        assert response.json["icon"] is None

    def test_create_category_duplicate_user_category(
        self, test_client, user_category, auth_headers
    ):
        """Test that duplicate user category names are rejected."""
        request, response = test_client.post(
            "/categories/",
            headers=auth_headers,
            json={"name": user_category.name}
        )

        assert response.status_code == 400
        assert "already have a category" in response.json["error"]

    def test_create_category_duplicate_system_category(
        self, test_client, system_category, auth_headers
    ):
        """Test that system category names cannot be reused."""
        request, response = test_client.post(
            "/categories/",
            headers=auth_headers,
            json={"name": system_category.name}
        )

        assert response.status_code == 400
        assert "system category" in response.json["error"]

    def test_create_category_unauthorized(self, test_client):
        """Test that creating category requires authentication."""
        request, response = test_client.post(
            "/categories/",
            json={"name": "New Category"}
        )

        assert response.status_code == 401


@pytest.mark.api
class TestListCategories:
    """Test list categories endpoint."""

    def test_list_categories_includes_system_and_user(
        self, test_client, system_category, user_category, auth_headers
    ):
        """Test that listing includes both system and user categories."""
        request, response = test_client.get(
            "/categories/",
            headers=auth_headers
        )

        assert response.status_code == 200
        assert "categories" in response.json
        assert isinstance(response.json["categories"], list)

        category_names = [c["name"] for c in response.json["categories"]]
        assert system_category.name in category_names
        assert user_category.name in category_names

    async def test_list_categories_excludes_other_users(
        self, app, another_user, auth_headers, repo
    ):
        """Test that other users' categories are excluded."""
        # Create category for another user
        other_category = await repo.categories.create(
            name="Other User Category",
            user_id=another_user.id
        )

        request, response = await app.asgi_client.get(
            "/categories/",
            headers=auth_headers
        )

        assert response.status_code == 200
        assert "categories" in response.json
        category_names = [c["name"] for c in response.json["categories"]]
        assert other_category.name not in category_names

    def test_list_categories_unauthorized(self, test_client):
        """Test that listing categories requires authentication."""
        request, response = test_client.get("/categories/")

        assert response.status_code == 401


@pytest.mark.api
class TestGetCategory:
    """Test get category endpoint."""

    def test_get_system_category(self, test_client, system_category, auth_headers):
        """Test getting a system category."""
        request, response = test_client.get(
            f"/categories/{system_category.id}",
            headers=auth_headers
        )

        assert response.status_code == 200
        assert response.json["name"] == system_category.name

    def test_get_user_category(self, test_client, user_category, auth_headers):
        """Test getting own user category."""
        request, response = test_client.get(
            f"/categories/{user_category.id}",
            headers=auth_headers
        )

        assert response.status_code == 200
        assert response.json["name"] == user_category.name

    async def test_get_other_user_category(
        self, app, another_user, auth_headers, repo
    ):
        """Test that other users' categories cannot be accessed."""
        other_category = await repo.categories.create(
            name="Other Category",
            user_id=another_user.id
        )

        request, response = await app.asgi_client.get(
            f"/categories/{other_category.id}",
            headers=auth_headers
        )

        assert response.status_code == 404

    def test_get_category_not_found(self, test_client, auth_headers):
        """Test getting non-existent category."""
        request, response = test_client.get(
            "/categories/99999",
            headers=auth_headers
        )

        assert response.status_code == 404


@pytest.mark.api
class TestUpdateCategory:
    """Test update category endpoint."""

    def test_update_category_name(self, test_client, user_category, auth_headers):
        """Test updating category name."""
        request, response = test_client.patch(
            f"/categories/{user_category.id}",
            headers=auth_headers,
            json={"name": "Updated Category"}
        )

        assert response.status_code == 200
        assert response.json["name"] == "Updated Category"

    def test_update_category_icon(self, test_client, user_category, auth_headers):
        """Test updating category icon."""
        request, response = test_client.patch(
            f"/categories/{user_category.id}",
            headers=auth_headers,
            json={"icon": "🎯"}
        )

        assert response.status_code == 200
        assert response.json["icon"] == "🎯"

    def test_update_category_partial(self, test_client, user_category, auth_headers):
        """Test partial update."""
        original_name = user_category.name

        request, response = test_client.patch(
            f"/categories/{user_category.id}",
            headers=auth_headers,
            json={"icon": "🔥"}
        )

        assert response.status_code == 200
        assert response.json["name"] == original_name
        assert response.json["icon"] == "🔥"

    async def test_update_category_duplicate_name(
        self, app, sample_user, auth_headers, repo
    ):
        """Test that duplicate names are rejected on update."""
        cat1 = await repo.categories.create(name="Category 1", user_id=sample_user.id)
        cat2 = await repo.categories.create(name="Category 2", user_id=sample_user.id)

        request, response = await app.asgi_client.patch(
            f"/categories/{cat2.id}",
            headers=auth_headers,
            json={"name": "Category 1"}
        )

        assert response.status_code == 400
        assert "already have a category" in response.json["error"]

    def test_update_system_category_forbidden(
        self, test_client, system_category, auth_headers
    ):
        """Test that system categories cannot be updated."""
        request, response = test_client.patch(
            f"/categories/{system_category.id}",
            headers=auth_headers,
            json={"name": "Updated System Category"}
        )

        assert response.status_code == 403
        assert "system categories" in response.json["error"]

    def test_update_category_no_changes(self, test_client, user_category, auth_headers):
        """Test update with no changes."""
        request, response = test_client.patch(
            f"/categories/{user_category.id}",
            headers=auth_headers,
            json={}
        )

        assert response.status_code == 400

    def test_update_category_not_found(self, test_client, auth_headers):
        """Test updating non-existent category."""
        request, response = test_client.patch(
            "/categories/99999",
            headers=auth_headers,
            json={"name": "Updated"}
        )

        assert response.status_code == 404


@pytest.mark.api
class TestDeleteCategory:
    """Test delete category endpoint."""

    async def test_delete_category_success(
        self, app, sample_user, auth_headers, repo
    ):
        """Test deleting a category."""
        category = await repo.categories.create(
            name="To Delete",
            user_id=sample_user.id
        )

        request, response = await app.asgi_client.delete(
            f"/categories/{category.id}",
            headers=auth_headers
        )

        assert response.status_code == 200
        assert "deleted successfully" in response.json["message"]

    def test_delete_category_not_found(self, test_client, auth_headers):
        """Test deleting non-existent category."""
        request, response = test_client.delete(
            "/categories/99999",
            headers=auth_headers
        )

        assert response.status_code == 404

    async def test_delete_category_with_transactions_nullifies_fk(
        self, app, sample_user, sample_account, auth_headers, repo
    ):
        """Test that deleting a category with linked transactions succeeds (SET NULL on FK)."""
        from schemas.enums import TransactionType
        import datetime
        from decimal import Decimal

        # Create a user category
        category = await repo.categories.create(
            name="Category With Txn",
            user_id=sample_user.id
        )

        # Create a transaction referencing this category
        txn = await repo.transactions.create(
            amount=Decimal("-25.00"),
            type=TransactionType.EXPENSE,
            user_id=sample_user.id,
            account_id=sample_account.id,
            category_id=category.id,
            transaction_date=datetime.date.today()
        )

        request, response = await app.asgi_client.delete(
            f"/categories/{category.id}",
            headers=auth_headers
        )

        # Deletion succeeds because FK uses SET NULL
        assert response.status_code == 200

        # Verify the transaction's category was set to NULL
        updated_txn = await repo.transactions.get(id=txn.id)
        assert updated_txn.category_id is None

    async def test_delete_other_user_category(
        self, app, another_user, auth_headers, repo
    ):
        """Test that users cannot delete other users' categories."""
        other_category = await repo.categories.create(
            name="Other Category",
            user_id=another_user.id
        )

        request, response = await app.asgi_client.delete(
            f"/categories/{other_category.id}",
            headers=auth_headers
        )

        assert response.status_code == 404
