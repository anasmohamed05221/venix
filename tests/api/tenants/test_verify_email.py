from datetime import datetime, timedelta, timezone


async def test_verify_email_success(client, test_tenant, session):
    """Valid code marks is_verified=True in DB and clears the code fields."""
    test_tenant.verification_code = "123456"
    test_tenant.verification_code_expires_at = datetime.now(timezone.utc) + timedelta(minutes=10)
    await session.commit()

    response = await client.post("/tenants/me/verify-email", json={"code": "123456"})

    assert response.status_code == 200
    assert "verified" in response.json()["message"].lower()

    await session.refresh(test_tenant)
    assert test_tenant.is_verified is True
    assert test_tenant.verification_code is None
    assert test_tenant.verification_code_expires_at is None


async def test_verify_email_invalid_code(client, test_tenant, session):
    """Wrong code returns 400 and leaves is_verified unchanged."""
    test_tenant.verification_code = "123456"
    test_tenant.verification_code_expires_at = datetime.now(timezone.utc) + timedelta(minutes=10)
    await session.commit()

    response = await client.post("/tenants/me/verify-email", json={"code": "000000"})

    assert response.status_code == 400
    assert "invalid" in response.json()["detail"].lower()

    await session.refresh(test_tenant)
    assert test_tenant.is_verified is False


async def test_verify_email_expired_code(client, test_tenant, session):
    """Expired code returns 400."""
    test_tenant.verification_code = "123456"
    test_tenant.verification_code_expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    await session.commit()

    response = await client.post("/tenants/me/verify-email", json={"code": "123456"})

    assert response.status_code == 400
    assert "expired" in response.json()["detail"].lower()


async def test_verify_email_already_verified(client, test_tenant, session):
    """Calling verify-email on an already verified tenant returns 400."""
    test_tenant.is_verified = True
    await session.commit()

    response = await client.post("/tenants/me/verify-email", json={"code": "123456"})

    assert response.status_code == 400
    assert "already verified" in response.json()["detail"].lower()


async def test_verify_email_requires_auth(client):
    """POST /tenants/me/verify-email returns 401 when the API key is invalid."""
    response = await client.post(
        "/tenants/me/verify-email",
        json={"code": "123456"},
        headers={"X-Tenant-API-Key": "vnx_invalid_key"}
    )

    assert response.status_code == 401
