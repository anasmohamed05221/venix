from pydantic import BaseModel
from models.enums import OrderStatus, PaymentMethod, PaymentStatus
from decimal import Decimal
from datetime import datetime
from typing import Optional


class OrderProductOut(BaseModel):
    id: int
    name: str
    price: Decimal
    image_url: Optional[str] = None

    model_config = {
        "from_attributes": True
    }


class OrderItemOut(BaseModel):
    id: int
    product: OrderProductOut
    price_at_time: Decimal
    quantity: int
    subtotal: Decimal

    model_config = {
        'from_attributes': True
    }
    

class OrderOut(BaseModel):
    id: int
    total_amount: Decimal
    status: OrderStatus
    items: list[OrderItemOut]
    payment_method: PaymentMethod
    payment_status: PaymentStatus
    checkout_url: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = {
        'from_attributes': True
    }


class OrderSummaryOut(BaseModel):
    id: int
    total_amount: Decimal
    status: OrderStatus
    created_at: datetime

    model_config = {
        'from_attributes': True
    }


class OrderListOut(BaseModel):
    items: list[OrderSummaryOut]
    limit: int
    offset: int
    total: int


class AdminOrderSummaryOut(OrderSummaryOut):
    user_id: int


class AdminOrderListOut(BaseModel):
    items: list[AdminOrderSummaryOut]
    limit: int
    offset: int
    total: int


class AdminOrderOut(OrderOut):
    user_id: int
    

class OrderStatusUpdate(BaseModel):
    status: OrderStatus


class CheckoutRequest(BaseModel):
    address_id: int
    payment_method: PaymentMethod