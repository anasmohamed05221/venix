import pytest
from services.token import TokenService
from core.redis_client import redis_client

DUMMY_TENANT_ID = "00000000-0000-0000-0000-000000000001"
VALID_API_KEY = "vnx_testkey123"


async def test_bypass_health_passes_through(client):
    """Health endpoint must not be blocked by tenant resolution."""
    response = await client.get("/health")
    assert response.status_code == 200


async def test_bypass_tenant_register_passes_through(client):
    """Tenant registration endpoint must reach request validation, not middleware rejection."""
    response = await client.post("/tenants/register", json={})
    assert response.status_code == 422


async def test_valid_api_key_resolves_tenant(client, mock_db, valid_tenant):
    """A valid API key must resolve the tenant and let the request reach the route handler."""
    mock_db.scalar.return_value = valid_tenant
    response = await client.get("/users/me", headers={"X-Tenant-API-Key": VALID_API_KEY})
    assert response.status_code == 401
    assert response.json()["detail"] != "Tenant could not be resolved"


async def test_invalid_api_key_returns_401(client, mock_db):
    """An unrecognized API key must be rejected before reaching any route handler."""
    mock_db.scalar.return_value = None
    response = await client.get("/users/me", headers={"X-Tenant-API-Key": "vnx_badkey"})
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid API Key"


async def test_invalid_api_key_increments_redis_counter(client, mock_db):
    """Each failed API key lookup must increment the IP failure counter in Redis."""
    mock_db.scalar.return_value = None
    await client.get("/users/me", headers={"X-Tenant-API-Key": "vnx_badkey"})
    redis_client.redis.incr.assert_called_once()


async def test_ip_rate_limit_returns_429(client):
    """An IP that has exceeded the failure threshold must be blocked before any DB query."""
    redis_client.redis.get.return_value = "10"
    response = await client.get("/users/me", headers={"X-Tenant-API-Key": VALID_API_KEY})
    assert response.status_code == 429
    assert response.json()["detail"] == "Too many failed attempts"


async def test_valid_jwt_resolves_tenant(client, mock_db, valid_tenant):
    """A JWT carrying a valid tenant_id must resolve the tenant via the JWT path."""
    mock_db.scalar.return_value = valid_tenant
    token = TokenService.create_access_token(
        tenant_id=DUMMY_TENANT_ID,
        email="user@example.com",
        user_id=1,
        role="customer"
    )
    response = await client.get("/users/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 404
    assert response.json()["detail"] == "User not found"


async def test_conflict_guard_returns_403(client, mock_db, valid_tenant):
    """API key and JWT resolving to different tenants must be rejected with a mismatch error."""
    import uuid
    from unittest.mock import MagicMock
    from models.tenants import Tenant

    other_tenant = MagicMock(spec=Tenant)
    other_tenant.id = uuid.uuid4()
    other_tenant.is_active = True
    other_tenant.name = "Other Store"
    other_tenant.slug = "other-store"
    other_tenant.plan = MagicMock()
    other_tenant.plan.value = "free"
    other_tenant.api_key_hash = "otherhash"
    other_tenant.owner_email = "other@test.com"
    other_tenant.is_verified = True

    mock_db.scalar.side_effect = [valid_tenant, other_tenant]

    token = TokenService.create_access_token(
        tenant_id=DUMMY_TENANT_ID,
        email="user@example.com",
        user_id=1,
        role="customer"
    )
    response = await client.get(
        "/users/me",
        headers={
            "X-Tenant-API-Key": VALID_API_KEY,
            "Authorization": f"Bearer {token}"
        }
    )
    assert response.status_code == 403
    assert response.json()["detail"] == "Tenant mismatch"


async def test_inactive_tenant_returns_403(client, mock_db, inactive_tenant):
    """A deactivated tenant must be rejected regardless of which resolution path was used."""
    mock_db.scalar.return_value = inactive_tenant
    response = await client.get("/users/me", headers={"X-Tenant-API-Key": VALID_API_KEY})
    assert response.status_code == 403
    assert response.json()["detail"] == "Tenant is deactivated"


async def test_no_headers_returns_401(client):
    """A request carrying neither an API key nor a JWT must be rejected at the middleware level."""
    response = await client.get("/users/me")
    assert response.status_code == 401
    assert response.json()["detail"] == "Tenant could not be resolved"