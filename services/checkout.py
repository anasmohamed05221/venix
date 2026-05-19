from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import joinedload
from models.orders import Order
from models.order_items import OrderItem
from models.cart_items import CartItem
from models.products import Product
from models.addresses import Address
from services.cart import CartService
from models.inventory_changes import InventoryChange
from models.enums import InventoryChangeReason, PaymentMethod, OrderStatus, PaymentStatus
from utils.logger import get_logger
import stripe
from core.config import settings

stripe.api_key = settings.STRIPE_SECRET_KEY

logger = get_logger(__name__)

class CheckoutService:
    @staticmethod
    async def _validate_cart(db: AsyncSession, user_id: int) -> list[CartItem]:
        """Fetch cart items and verify cart is non-empty with sufficient stock.

        Raises:
            HTTPException 400: If cart is empty.
            HTTPException 409: If any item exceeds available stock.
        """
        cart_items = await CartService.get_cart(db, user_id)
        if len(cart_items)==0:
            logger.warning("Checkout attempted with empty cart", extra={"user_id": user_id})
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, 
                                detail="Can't checkout while cart is empty")
        
        for item in cart_items:
            product = item.product
            if item.quantity > product.stock:
                logger.warning(
                    "Checkout blocked by insufficient stock",
                    extra={"user_id": user_id, "product_id": product.id, 
                        "available_stock": product.stock, "requested": item.quantity}
                )
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, 
                                    detail={"message": "Not enough stock available",
                                                    "product_id": product.id,
                                                    "product_name": product.name,
                                                    "available_stock": product.stock})
        return cart_items


    @staticmethod
    async def _process_cart_items(db: AsyncSession, user_id: int, cart_items: list[CartItem], order: Order) -> tuple[list[OrderItem], list[InventoryChange]]:
        """Create order items and inventory change records from cart items.

        Snapshots product price at time of purchase, decrements product stock,
        and records each stock change as an inventory audit entry.
        """
        order_items = []
        inventory_changes = []
        for item in cart_items:
            # Handle race condition (Pessimistic Lock)
            product = await db.scalar(select(Product).where(Product.id==item.product_id).with_for_update())
            if item.quantity > product.stock:
                logger.warning(
                    "Checkout blocked by insufficient stock",
                    extra={"user_id": user_id, "product_id": product.id, 
                        "available_stock": product.stock, "requested": item.quantity}
                )
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, 
                                    detail={"message": "Not enough stock available",
                                                    "product_id": product.id,
                                                    "product_name": product.name,
                                                    "available_stock": product.stock})
            
            order_item = OrderItem(order_id=order.id, product_id=product.id, price_at_time=product.price, 
                                   quantity=item.quantity, subtotal=(product.price*item.quantity))
            order_items.append(order_item)
            inventory_change = InventoryChange(product_id=product.id, change_amount=-item.quantity, reason=InventoryChangeReason.SALE)
            inventory_changes.append(inventory_change)
            product.stock -= item.quantity
        return (order_items, inventory_changes)
    

    @staticmethod
    async def _create_stripe_session(db: AsyncSession, user_id: int, order: Order, cart_items: list[CartItem]) -> Order:
        """Create a Stripe Checkout Session for the given order and attach the session ID.

        On success: saves the session ID to the order and returns the order with checkout_url set.
        On Stripe failure: marks the order as FAILED, commits, and raises 502.
        """
        line_items = [{
                    "price_data": {"currency": "egp", "unit_amount": int(item.product.price * 100),
                    "product_data": {"name": item.product.name}},
                    "quantity": item.quantity
                    } for item in cart_items]

        try:
            session = stripe.checkout.Session.create(
                payment_method_types=["card"],
                line_items=line_items,
                mode="payment",
                success_url=settings.FRONTEND_SUCCESS_URL + "?session_id={CHECKOUT_SESSION_ID}",
                cancel_url=settings.FRONTEND_CANCEL_URL,
                metadata={"order_id": order.id},
                idempotency_key=f"checkout-{order.id}"
            )
            order.stripe_checkout_session_id = session.id
            try:
                await db.commit()
            except Exception:
                logger.error("Stripe session commit failed", extra={"order_id": order.id})
                await db.rollback()
                raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Checkout failed, please try again")
            order_eagered = await db.scalar(select(Order).options(joinedload(Order.items).joinedload(OrderItem.product)).where(Order.id==order.id))
            order_eagered.checkout_url = session.url
            return order_eagered
        except stripe.StripeError as e:
            order.payment_status = PaymentStatus.FAILED
            try:
                await db.commit()
            except Exception:
                logger.error("Failed to persist FAILED status after Stripe error", extra={"order_id": order.id})
                await db.rollback()
            logger.error("Stripe session creation failed", extra={"order_id": order.id, "error": str(e)})
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Payment provider unavailable, please try again later")
        


    @staticmethod
    async def checkout(db: AsyncSession, user_id: int, address_id: int, payment_method: PaymentMethod) -> Order:
        """Execute the full checkout flow as a single atomic transaction.

        Validates cart, creates order with items, decrements stock,
        logs inventory changes, and clears the cart.
        """
        # Address ownership validation
        address = await db.scalar(select(Address).where(Address.id == address_id, Address.user_id == user_id))
        if address is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Address not found.")
        
        # Fetch user's cart items
        cart_items = await CheckoutService._validate_cart(db, user_id)

        # reuse-if-valid check for stripe session
        if payment_method == PaymentMethod.STRIPE:
            existing_order = await db.scalar(
                select(Order)
                .options(joinedload(Order.items).joinedload(OrderItem.product))
                .where(
                    Order.user_id == user_id,
                    Order.payment_method == PaymentMethod.STRIPE,
                    Order.payment_status == PaymentStatus.UNPAID,
                    Order.stripe_checkout_session_id.isnot(None)
                )
            )
            if existing_order:
                session = stripe.checkout.Session.retrieve(existing_order.stripe_checkout_session_id)
                if session.status == "open":
                    existing_order.checkout_url = session.url
                    return existing_order

        # Create order
        total_amount = CartService.calculate_cart_total_price(cart_items)
        order = Order(
            user_id=user_id, 
            total_amount=total_amount, 
            status=OrderStatus.PENDING, 
            address_id=address_id, 
            payment_method=payment_method
        )
        db.add(order)
        await db.flush()

        if payment_method == PaymentMethod.STRIPE:
            stripe_order = await CheckoutService._create_stripe_session(db, user_id, order, cart_items)
            return stripe_order

        # Create order items and inventory changes
        order_items, inventory_changes = await CheckoutService._process_cart_items(db, user_id, cart_items, order)
        
        # Checkout
        for order_item, inventory_change, cart_item in zip(order_items, inventory_changes, cart_items):
            db.add(order_item)
            db.add(inventory_change)
            await db.delete(cart_item)
        
        try:
            await db.commit()
        except Exception:
            logger.error("Checkout commit failed", extra={"user_id": user_id})
            await db.rollback()
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
                                detail="Checkout commit failed")
        order_eagered = await db.scalar(select(Order).options(joinedload(Order.items).joinedload(OrderItem.product)).where(Order.id==order.id))
        return order_eagered

        