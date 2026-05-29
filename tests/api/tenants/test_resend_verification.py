from datetime import datetime, timedelta, timezone


async def test_resend_verification_success(client, test_tenant, session):
    """Resend overwrites the old code with a new one in DB."""
    test_tenant.verification_code = "111111"
    test_tenant.verification_code_expires_at = datetime.now(timezone.utc) + timedelta(minutes=5)
    await session.commit()

    response = await client.post("/tenants/me/resend-verification")

    assert response.status_code == 200
    assert "sent" in response.json()["message"].lower()

    await session.refresh(test_tenant)
    assert test_tenant.verification_code is not None
    assert test_tenant.verification_code != "111111"


async def test_resend_already_verified(client, test_tenant, session):
    """Resending to an already verified tenant returns 400."""
    test_tenant.is_verified = True
    await session.commit()

    response = await client.post("/tenants/me/resend-verification")

    assert response.status_code == 400
    assert "already verified" in response.json()["detail"].lower()


async def test_resend_requires_auth(client):
    """POST /tenants/me/resend-verification returns 401 when the API key is invalid."""
    response = await client.post(
        "/tenants/me/resend-verification",
        headers={"X-Tenant-API-Key": "vnx_invalid_key"}
    )

    assert response.status_code == 401
