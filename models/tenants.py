from core.database import Base
from sqlalchemy import Column, String, Enum, Boolean
from sqlalchemy.dialects.postgresql import UUID
from uuid6 import uuid7
from .enums import PlanTier
from .mixins import CreatedAtMixin

class Tenant(Base, CreatedAtMixin):
    __tablename__= "tenants"

    #pk
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid7)

    name = Column(String(100), nullable=False)
    owner_email = Column(String(255), unique=True, nullable=False, index=True)
    owner_password_hash = Column(String(255), nullable=False)
    db_url = Column(String(500), nullable=True)
    slug = Column(String(50), unique=True, nullable=False, index=True)
    plan = Column(Enum(PlanTier, values_callable=lambda obj: [e.value for e in obj], name="plantier"), default=PlanTier.FREE, nullable=False)
    api_key_hash = Column(String(64), unique=True, nullable=False, index=True)
    is_active = Column(Boolean, default=True, nullable=False)
    stripe_secret_key = Column(String(500), nullable=True)
    stripe_webhook_secret = Column(String(500), nullable=True)