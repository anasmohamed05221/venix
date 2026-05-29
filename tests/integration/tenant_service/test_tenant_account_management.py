from datetime import datetime, timedelta, timezone
from sqlalchemy import select
from models.tenants import Tenant
from models.users import User
from models.enums import UserRole
from services.tenants import TenantService
from utils.hashing import hash_token, get_password_hash, verify_password

HASHED_TEST_PASSWORD = get_password_hash("TestPassword123!")
PLAIN_CODE = "847291"


async def test_verify_email_clears_code_fields(session, test_tenant):
    """After verify_email, both code fields are NULL in DB."""
    test_tenant.verification_code = "123456"
    test_tenant.verification_code_expires_at = datetime.now(timezone.utc) + timedelta(minutes=10)
    await session.commit()

    await TenantService.verify_email(session, test_tenant, "123456")

    db_tenant = await session.scalar(select(Tenant).where(Tenant.id == test_tenant.id))
    assert db_tenant.is_verified is True
    assert db_tenant.verification_code is None
    assert db_tenant.verification_code_expires_at is None


async def test_change_password_code_cryptographic_contract(session, test_tenant):
    """password_change_code stored in DB must be SHA256 of the dispatched plaintext — never plaintext itself."""
    test_tenant.password_change_code = hash_token(PLAIN_CODE)
    test_tenant.password_change_code_expires_at = datetime.now(timezone.utc) + timedelta(minutes=15)
    await session.commit()

    await TenantService.change_password(session, test_tenant, PLAIN_CODE, "NewSecurePass456!")

    db_tenant = await session.scalar(select(Tenant).where(Tenant.id == test_tenant.id))
    assert db_tenant.password_change_code is None
    assert verify_password("NewSecurePass456!", db_tenant.owner_password_hash)


async def test_change_password_syncs_admin_user(session, test_tenant):
    """change_password applies the new hash to both tenant and the admin User atomically."""
    admin = User(
        tenant_id=test_tenant.id,
        email="admin_sync@test.com",
        first_name="Admin",
        last_name="Sync",
        hashed_password=HASHED_TEST_PASSWORD,
        role=UserRole.ADMIN,
        is_verified=True,
    )
    session.add(admin)
    test_tenant.password_change_code = hash_token(PLAIN_CODE)
    test_tenant.password_change_code_expires_at = datetime.now(timezone.utc) + timedelta(minutes=15)
    await session.commit()

    await TenantService.change_password(session, test_tenant, PLAIN_CODE, "NewSecurePass456!")

    db_tenant = await session.scalar(select(Tenant).where(Tenant.id == test_tenant.id))
    db_admin = await session.scalar(select(User).where(User.id == admin.id))

    assert db_tenant.owner_password_hash == db_admin.hashed_password
    assert verify_password("NewSecurePass456!", db_admin.hashed_password)


async def test_deactivate_sets_is_active_false(session, test_tenant):
    """deactivate sets is_active=False on the tenant row in DB."""
    test_tenant.is_verified = True
    await session.commit()

    await TenantService.deactivate(session, test_tenant, "TestPassword123!")

    db_tenant = await session.scalar(select(Tenant).where(Tenant.id == test_tenant.id))
    assert db_tenant.is_active is False
