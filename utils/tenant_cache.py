from models.tenants import Tenant
import json
from uuid import UUID

def serialize_tenant(tenant: Tenant) -> str:
    """Serialize a Tenant instance to a JSON string for Redis storage."""
    data = {
        "id": str(tenant.id),
        "name": tenant.name,
        "slug": tenant.slug,
        "plan": tenant.plan.value,
        "is_active": tenant.is_active,
        "is_verified": tenant.is_verified,
        "api_key_hash": tenant.api_key_hash,
        "owner_email": tenant.owner_email
    }
    return json.dumps(data)

def deserialize_tenant(data: str) -> Tenant:
    """Reconstruct a detached Tenant instance from a Redis-stored JSON string."""
    data = json.loads(data)
    tenant = Tenant(
        id=UUID(data["id"]),
        name=data["name"],
        slug=data["slug"],
        plan=data["plan"],
        is_active=data["is_active"],
        is_verified=data["is_verified"],
        api_key_hash=data["api_key_hash"],
        owner_email=data["owner_email"]
    )
    return tenant