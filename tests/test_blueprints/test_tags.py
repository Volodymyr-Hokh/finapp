"""
API tests for tag endpoints (blueprints/tags.py).
"""
import pytest


@pytest.mark.api
class TestCreateTag:
    """Test create tag endpoint."""

    def test_create_tag_success(self, test_client, auth_headers):
        """Test creating a tag."""
        request, response = test_client.post(
            "/tags/",
            headers=auth_headers,
            json={"name": "groceries"}
        )

        assert response.status_code == 201
        assert response.json["name"] == "groceries"

    def test_create_tag_normalizes_to_lowercase(self, test_client, auth_headers):
        """Test that tag names are normalized to lowercase."""
        request, response = test_client.post(
            "/tags/",
            headers=auth_headers,
            json={"name": "UPPERCASE"}
        )

        assert response.status_code == 201
        assert response.json["name"] == "uppercase"

    def test_create_tag_trims_whitespace(self, test_client, auth_headers):
        """Test that whitespace is trimmed."""
        request, response = test_client.post(
            "/tags/",
            headers=auth_headers,
            json={"name": "  spaces  "}
        )

        assert response.status_code == 201
        assert response.json["name"] == "spaces"

    def test_create_tag_duplicate_name(self, test_client, sample_tag, auth_headers):
        """Test that duplicate tag names are rejected."""
        request, response = test_client.post(
            "/tags/",
            headers=auth_headers,
            json={"name": sample_tag.name}
        )

        assert response.status_code == 400
        assert "already exists" in response.json["error"]

    def test_create_tag_unauthorized(self, test_client):
        """Test that creating tag requires authentication."""
        request, response = test_client.post(
            "/tags/",
            json={"name": "test"}
        )

        assert response.status_code == 401


@pytest.mark.api
class TestListTags:
    """Test list tags endpoint."""

    def test_list_tags(self, test_client, sample_tags, auth_headers):
        """Test listing user's tags."""
        request, response = test_client.get(
            "/tags/",
            headers=auth_headers
        )

        assert response.status_code == 200
        assert "tags" in response.json
        assert isinstance(response.json["tags"], list)
        assert len(response.json["tags"]) >= len(sample_tags)

        # Verify it returns tag names
        tag_names = response.json["tags"]
        assert all(isinstance(name, str) for name in tag_names)

    async def test_list_tags_only_user_tags(
        self, app, sample_tag, another_user, auth_headers, repo
    ):
        """Test that users only see their own tags."""
        # Create tag for another user
        await repo.tags.create(name="other", user_id=another_user.id)

        request, response = await app.asgi_client.get(
            "/tags/",
            headers=auth_headers
        )

        assert response.status_code == 200
        assert "tags" in response.json
        assert sample_tag.name in response.json["tags"]
        assert "other" not in response.json["tags"]

    def test_list_tags_empty_for_new_user(self, test_client, another_user, app, repo):
        """Test that new user has no tags."""
        # Create token for another_user who has no tags
        from services.auth import create_access_token

        token = create_access_token(
            user_id=str(another_user.id),
            secret=app.config.SECRET.get_secret_value()
        )

        request, response = test_client.get(
            "/tags/",
            headers={"Authorization": f"Bearer {token}"}
        )

        assert response.status_code == 200
        assert "tags" in response.json
        assert response.json["tags"] == []

    def test_list_tags_unauthorized(self, test_client):
        """Test that listing tags requires authentication."""
        request, response = test_client.get("/tags/")

        assert response.status_code == 401


@pytest.mark.api
class TestGetTag:
    """Test get tag endpoint."""

    def test_get_tag_success(self, test_client, sample_tag, auth_headers):
        """Test getting a specific tag."""
        request, response = test_client.get(
            f"/tags/{sample_tag.id}",
            headers=auth_headers
        )

        assert response.status_code == 200
        assert response.json["id"] == sample_tag.id
        assert response.json["name"] == sample_tag.name

    def test_get_tag_not_found(self, test_client, auth_headers):
        """Test getting non-existent tag."""
        request, response = test_client.get(
            "/tags/99999",
            headers=auth_headers
        )

        assert response.status_code == 404

    async def test_get_tag_different_user(
        self, app, another_user, auth_headers, repo
    ):
        """Test that users cannot access other users' tags."""
        other_tag = await repo.tags.create(name="other", user_id=another_user.id)

        request, response = await app.asgi_client.get(
            f"/tags/{other_tag.id}",
            headers=auth_headers
        )

        assert response.status_code == 404


@pytest.mark.api
class TestUpdateTag:
    """Test update tag endpoint."""

    def test_update_tag_name(self, test_client, sample_tag, auth_headers):
        """Test updating tag name."""
        request, response = test_client.patch(
            f"/tags/{sample_tag.id}",
            headers=auth_headers,
            json={"name": "updated"}
        )

        assert response.status_code == 200
        assert response.json["name"] == "updated"

    def test_update_tag_normalizes_name(self, test_client, sample_tag, auth_headers):
        """Test that updated name is normalized."""
        request, response = test_client.patch(
            f"/tags/{sample_tag.id}",
            headers=auth_headers,
            json={"name": "UPDATED"}
        )

        assert response.status_code == 200
        assert response.json["name"] == "updated"

    async def test_update_tag_duplicate_name(
        self, app, sample_user, auth_headers, repo
    ):
        """Test that duplicate names are rejected on update."""
        tag1 = await repo.tags.create(name="tag1", user_id=sample_user.id)
        tag2 = await repo.tags.create(name="tag2", user_id=sample_user.id)

        request, response = await app.asgi_client.patch(
            f"/tags/{tag2.id}",
            headers=auth_headers,
            json={"name": "tag1"}
        )

        assert response.status_code == 400
        assert "already exists" in response.json["error"]

    def test_update_tag_same_name_allowed(self, test_client, sample_tag, auth_headers):
        """Test that updating to same name is allowed."""
        request, response = test_client.patch(
            f"/tags/{sample_tag.id}",
            headers=auth_headers,
            json={"name": sample_tag.name}
        )

        # Updating to the same name should succeed
        assert response.status_code == 200

    def test_update_tag_no_changes(self, test_client, sample_tag, auth_headers):
        """Test update with no changes."""
        request, response = test_client.patch(
            f"/tags/{sample_tag.id}",
            headers=auth_headers,
            json={}
        )

        assert response.status_code == 400

    def test_update_tag_not_found(self, test_client, auth_headers):
        """Test updating non-existent tag."""
        request, response = test_client.patch(
            "/tags/99999",
            headers=auth_headers,
            json={"name": "updated"}
        )

        assert response.status_code == 404


@pytest.mark.api
class TestDeleteTag:
    """Test delete tag endpoint."""

    async def test_delete_tag_success(self, app, sample_user, auth_headers, repo):
        """Test deleting a tag."""
        tag = await repo.tags.create(name="to_delete", user_id=sample_user.id)

        request, response = await app.asgi_client.delete(
            f"/tags/{tag.id}",
            headers=auth_headers
        )

        assert response.status_code == 200
        assert "deleted successfully" in response.json["message"]

    async def test_delete_tag_removes_from_transactions(
        self, app, sample_transaction, sample_tag, auth_headers, repo, setup_database
    ):
        """Test that deleting tag removes it from transactions."""
        from db.models import Transaction
        from sqlalchemy import select
        from sqlalchemy.orm import selectinload
        
        # Add tag to transaction within a session
        async with setup_database() as session:
            stmt = select(Transaction).options(selectinload(Transaction.tags)).filter_by(id=sample_transaction.id)
            result = await session.execute(stmt)
            tx = result.scalar_one()
            tx.tags.append(sample_tag)
            await session.commit()

        # Delete tag
        request, response = await app.asgi_client.delete(
            f"/tags/{sample_tag.id}",
            headers=auth_headers
        )

        assert response.status_code == 200

        # Verify tag was removed from transaction
        transaction = await repo.transactions.get_with_relations(sample_transaction.id)
        tag_ids = [tag.id for tag in transaction.tags]
        assert sample_tag.id not in tag_ids

    def test_delete_tag_not_found(self, test_client, auth_headers):
        """Test deleting non-existent tag."""
        request, response = test_client.delete(
            "/tags/99999",
            headers=auth_headers
        )

        assert response.status_code == 404

    async def test_delete_tag_different_user(
        self, app, another_user, auth_headers, repo
    ):
        """Test that users cannot delete other users' tags."""
        other_tag = await repo.tags.create(name="other", user_id=another_user.id)

        request, response = await app.asgi_client.delete(
            f"/tags/{other_tag.id}",
            headers=auth_headers
        )

        assert response.status_code == 404
