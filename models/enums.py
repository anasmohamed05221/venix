from enum import Enum

class OrderStatus(str, Enum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    SHIPPED = "shipped"
    COMPLETED = "completed"
    CANCELLED = "cancelled"

class InventoryChangeReason(str, Enum):
    SALE = "sale"
    RESTOCK = "restock"
    ADJUSTMENT = "adjustment"
    RETURN = "return"
    CANCELLATION = "cancellation"

class UserRole(str, Enum):
    CUSTOMER = "customer"
    ADMIN = "admin"

class PaymentMethod(str, Enum):
    COD = "cod"
    STRIPE = "stripe"

class PaymentStatus(str, Enum):
    UNPAID = "unpaid"
    PAID = "paid"
    FAILED = "failed"
    REFUNDED = "refunded"
    EXPIRED = "expired"