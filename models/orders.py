from core.database import Base
from sqlalchemy.orm import relationship
from sqlalchemy import (Column, Integer, ForeignKey ,Numeric, Enum, String)
from .mixins import CreatedAtMixin, UpdatedAtMixin
from .enums import OrderStatus, PaymentMethod, PaymentStatus

class Order(Base, CreatedAtMixin, UpdatedAtMixin):
    __tablename__ = "orders"

    #pk
    id = Column(Integer, primary_key=True, index=True)

    #fk
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    address_id = Column(Integer, ForeignKey("addresses.id", ondelete="RESTRICT"), nullable=False)

    #relationships
    user = relationship("User", back_populates="orders")
    items = relationship("OrderItem", back_populates="order")
    address = relationship("Address", back_populates="orders")

    total_amount = Column(Numeric(10, 2), nullable=False)
    status = Column(Enum(OrderStatus, values_callable=lambda obj: [e.value for e in obj], name="order_status"), default=OrderStatus.PENDING, nullable=False)
    payment_method = Column(Enum(PaymentMethod, values_callable=lambda obj: [e.value for e in obj], name="payment_method"), nullable=False)
    payment_status = Column(Enum(PaymentStatus, values_callable=lambda obj: [e.value for e in obj], name="payment_status"), default=PaymentStatus.UNPAID , nullable=False)
    stripe_checkout_session_id = Column(String, nullable=True)