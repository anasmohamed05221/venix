from core.database import Base
from sqlalchemy import Column, String, Enum, Boolean, DateTime
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from uuid6 import uuid7
from .enums import PlanTier
from .mixins import CreatedAtMixin

class Tenant(Base, CreatedAtMixin):
    __tablename__= "tenants"

    #pk
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid7)

    #relationships
    users = relationship("User", back_populates="tenant")
    products = relationship("Product", back_populates="tenant")
    categories = relationship("Category", back_populates="tenant")
    orders = relationship("Order", back_populates="tenant")
    cart_items = relationship("CartItem", back_populates="tenant")
    addresses = relationship("Address", back_populates="tenant")
    processed_webhook_events = relationship("ProcessedWebhookEvent", back_populates="tenant")

    name = Column(String(100), nullable=False)
    owner_email = Column(String(255), nullable=False, index=True)
    owner_password_hash = Column(String(255), nullable=False)
    db_url = Column(String(500), nullable=True)
    slug = Column(String(50), unique=True, nullable=False, index=True)
    plan = Column(Enum(PlanTier, values_callable=lambda obj: [e.value for e in obj], name="plantier"), default=PlanTier.FREE, nullable=False)
    api_key_hash = Column(String(64), unique=True, nullable=True, index=True)
    is_active = Column(Boolean, default=True, nullable=False)
    is_verified = Column(Boolean, default=False, nullable=False)
    verification_code = Column(String(6), nullable=True)
    verification_code_expires_at = Column(DateTime(timezone=True), nullable=True)
    password_change_code = Column(String(64), nullable=True)
    password_change_code_expires_at = Column(DateTime(timezone=True), nullable=True)
    stripe_secret_key = Column(String(500), nullable=True)
    stripe_webhook_secret = Column(String(500), nullable=True)