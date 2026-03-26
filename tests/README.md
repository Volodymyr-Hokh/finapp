# Finance Analysis API - Test Suite

Comprehensive test suite for the finance analysis REST API.

## Test Structure

```
tests/
├── conftest.py                  # Shared fixtures and test configuration
├── test_models.py               # Database model tests
├── test_services/
│   └── test_auth.py            # Authentication service tests
├── test_repositories/
│   ├── test_base.py            # Base repository tests
│   └── test_repositories.py    # Specific repository tests
├── test_schemas/
│   └── test_schemas.py         # Pydantic schema validation tests
└── test_blueprints/
    ├── test_users.py           # User API endpoint tests
    ├── test_accounts.py        # Account API endpoint tests
    ├── test_transactions.py    # Transaction API endpoint tests
    ├── test_categories.py      # Category API endpoint tests
    ├── test_budgets.py         # Budget API endpoint tests
    └── test_tags.py            # Tag API endpoint tests
```

## Installation

Install test dependencies:

```bash
pip install -r requirements-test.txt
```

## Running Tests

### Run all tests
```bash
pytest
```

### Run with coverage report
```bash
pytest --cov=. --cov-report=html
```

### Run specific test categories
```bash
# Unit tests only
pytest -m unit

# Integration tests only
pytest -m integration

# API tests only
pytest -m api
```

### Run specific test files
```bash
pytest tests/test_services/test_auth.py
pytest tests/test_blueprints/test_users.py
```

### Run specific test classes or methods
```bash
pytest tests/test_services/test_auth.py::TestPasswordHashing
pytest tests/test_blueprints/test_users.py::TestUserRegistration::test_register_user_success
```

### Run tests with verbose output
```bash
pytest -v
```

### Run tests and stop at first failure
```bash
pytest -x
```

## Test Coverage

The test suite provides comprehensive coverage across:

### 1. **Authentication & Security** (test_services/test_auth.py)
- Password hashing and verification
- JWT token generation and validation
- Token expiration handling
- Protected decorator authorization

### 2. **Database Models** (test_models.py)
- Model creation and relationships
- Unique constraints
- Soft delete functionality
- Timestamp mixins
- Cascade delete behavior
- Many-to-many relationships

### 3. **Repositories** (test_repositories/)
- Generic CRUD operations
- User-specific data filtering
- Specialized repository methods
- Tag normalization
- Budget period validation
- Category uniqueness enforcement

### 4. **Schema Validation** (test_schemas/)
- Pydantic model validation
- Email validation
- Required vs optional fields
- Default values
- Validation aliases
- Enum validation

### 5. **API Endpoints** (test_blueprints/)
- All 6 blueprint endpoints:
  - Users (register, login, profile)
  - Accounts (CRUD operations)
  - Transactions (CRUD with tags, soft delete)
  - Categories (CRUD with system/user categories)
  - Budgets (CRUD with period constraints)
  - Tags (CRUD with normalization)
- Authentication requirements
- Authorization (data ownership)
- Error handling
- HTTP status codes
- Request/response validation

## Test Markers

Tests are organized with markers for selective execution:

- `@pytest.mark.unit` - Fast, isolated unit tests
- `@pytest.mark.integration` - Database integration tests
- `@pytest.mark.api` - API endpoint tests

## Fixtures

Key fixtures available in `conftest.py`:

### Application & Client
- `app` - Configured Sanic app
- `test_client` - Synchronous test client
- `repo` - Repository container

### Database
- `setup_database` - Database setup/teardown (auto-used)

### Users
- `sample_user` - Test user
- `another_user` - Second user for isolation tests
- `auth_token` - Valid JWT token
- `expired_token` - Expired JWT token
- `auth_headers` - Authorization headers

### Accounts
- `sample_account` - Default account
- `another_account` - Additional account

### Categories
- `system_category` - System-wide category
- `user_category` - User-specific category

### Tags
- `sample_tag` - Single tag
- `sample_tags` - Multiple tags

### Transactions
- `sample_transaction` - Test transaction
- `income_transaction` - Income transaction

### Budgets
- `sample_budget` - Test budget

## Coverage Goals

Target coverage metrics:
- **Overall**: 80-90%
- **Critical paths** (auth, repositories): 95%+
- **API endpoints**: 85%+
- **Schemas**: 70%+
- **Models**: 60%+

## Continuous Integration

Tests should be run on:
- Every commit
- Pull request creation
- Before deployment

Recommended CI configuration:
```yaml
- name: Run tests
  run: |
    pip install -r requirements.txt
    pip install -r requirements-test.txt
    pytest --cov=. --cov-report=xml

- name: Check coverage
  run: |
    pytest --cov-fail-under=80
```

## Writing New Tests

### Test Naming Convention
- Files: `test_*.py`
- Classes: `Test*`
- Functions: `test_*`

### Example Test
```python
@pytest.mark.api
class TestMyEndpoint:
    """Test my endpoint functionality."""

    def test_endpoint_success(self, test_client, auth_headers):
        """Test successful endpoint call."""
        request, response = test_client.get(
            "/my-endpoint",
            headers=auth_headers
        )

        assert response.status_code == 200
        assert "expected_field" in response.json
```

### Best Practices
1. **Use descriptive test names** that explain what is being tested
2. **One assertion concept per test** when possible
3. **Use fixtures** to avoid code duplication
4. **Test both success and failure cases**
5. **Test edge cases** (empty data, invalid data, boundary conditions)
6. **Test authorization** (ensure users can't access other users' data)
7. **Clean up test data** using fixtures with proper teardown

## Troubleshooting

### Database connection errors
Ensure database URL is configured correctly in test environment.

### Fixture not found
Check that fixture is imported in `conftest.py` or test file.

### Async test failures
Ensure `@pytest.mark.asyncio` is used and `pytest-asyncio` is installed.

### Import errors
Verify all dependencies are installed from `requirements-test.txt`.
