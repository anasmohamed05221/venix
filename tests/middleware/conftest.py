import pytest
import uuid
import hashlib
from unittest.mock import AsyncMock, MagicMock
from models.tenants import Tenant
from httpx import AsyncClient, ASGITransport
from main import app

VALID_API_KEY = "vnx_testkey123"


@pytest.fixture
async def client():
    """Plain client with no default headers — lets middleware tests exercise rejection paths."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


@pytest.fixture
def mock_db():
    """Patch SessionLocal in tenant_resolver to return a controllable mock session."""
    mock_session = AsyncMock()
    mock_cm = AsyncMock()
    mock_cm.__aenter__ = AsyncMock(return_value=mock_session)
    mock_cm.__aexit__ = AsyncMock(return_value=False)

    import middleware.tenant_resolver as resolver
    resolver.SessionLocal = MagicMock(return_value=mock_cm)
    return mock_session


def _make_tenant_mock(is_active: bool) -> MagicMock:
    """Build a MagicMock Tenant with all fields required by serialize_tenant."""
    tenant = MagicMock(spec=Tenant)
    tenant.id = uuid.uuid4()
    tenant.is_active = is_active
    tenant.name = "Test Store"
    tenant.slug = "test-store"
    tenant.plan = MagicMock()
    tenant.plan.value = "free"
    tenant.api_key_hash = hashlib.sha256(VALID_API_KEY.encode()).hexdigest()
    tenant.owner_email = "owner@test.com"
    tenant.is_verified = True
    return tenant


@pytest.fixture
def valid_tenant():
    """Mock active tenant with all fields required for serialization."""
    return _make_tenant_mock(is_active=True)


@pytest.fixture
def inactive_tenant():
    """Mock inactive tenant with all fields required for serialization."""
    return _make_tenant_mock(is_active=False)