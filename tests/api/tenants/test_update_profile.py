from sqlalchemy import select
from models.tenants import Tenant


async def test_update_name_success(client, test_tenant, session):
    """PUT /tenants/me updates name in the response and persists the change to DB."""
    response = await client.put("/tenants/me", json={"name": "Updated Store Name"})

    assert response.status_code == 200
    assert response.json()["name"] == "Updated Store Name"

    await session.refresh(test_tenant)
    assert test_tenant.name == "Updated Store Name"


async def test_update_empty_body_is_noop(client, test_tenant, session):
    """PUT /tenants/me with an empty body returns 200 and leaves the tenant unchanged."""
    original_name = test_tenant.name
    response = await client.put("/tenants/me", json={})

    assert response.status_code == 200

    await session.refresh(test_tenant)
    assert test_tenant.name == original_name


async def test_update_name_too_long(client):
    """PUT /tenants/me with a name exceeding 100 characters returns 422."""
    response = await client.put("/tenants/me", json={"name": "a" * 101})

    assert response.status_code == 422


async def test_update_requires_auth(client):
    """PUT /tenants/me returns 401 when the API key is invalid."""
    response = await client.put(
        "/tenants/me",
        json={"name": "Hacked"},
        headers={"X-Tenant-API-Key": "vnx_invalid_key"}
    )

    assert response.status_code == 401
