async def test_get_profile_success(client, test_tenant):
    """GET /tenants/me returns all expected profile fields for the resolved tenant."""
    response = await client.get("/tenants/me")

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == str(test_tenant.id)
    assert data["name"] == test_tenant.name
    assert data["slug"] == test_tenant.slug
    assert data["owner_email"] == test_tenant.owner_email
    assert data["plan"] == test_tenant.plan.value
    assert data["is_active"] is True
    assert "is_verified" in data
    assert "created_at" in data


async def test_get_profile_no_sensitive_fields(client):
    """GET /tenants/me must never expose credentials or internal fields."""
    response = await client.get("/tenants/me")

    assert response.status_code == 200
    data = response.json()
    assert "owner_password_hash" not in data
    assert "api_key_hash" not in data
    assert "stripe_secret_key" not in data
    assert "db_url" not in data
    assert "password_change_code" not in data
    assert "verification_code" not in data


async def test_get_profile_requires_auth(client):
    """GET /tenants/me returns 401 when the API key is invalid."""
    response = await client.get("/tenants/me", headers={"X-Tenant-API-Key": "vnx_invalid_key"})

    assert response.status_code == 401
