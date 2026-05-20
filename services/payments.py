from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import joinedload
from models.processed_webhook_events import ProcessedWebhookEvent
from models.orders import Order
from models.order_items import OrderItem
from models.inventory_changes import InventoryChange
from models.users import User
from models.enums import PaymentStatus, OrderStatus, InventoryChangeReason
from services.cart import CartService
from tasks.emails import send_email_task
from utils.email_templates import order_confirmation_email
import stripe
from utils.logger import get_logger
from typing import Optional

logger = get_logger(__name__)

class WebhookService:
    @staticmethod
    async def handle_webhook_event(db: AsyncSession, event: stripe.Event):
        processed_event = await db.scalar(
            select(ProcessedWebhookEvent)
            .where(ProcessedWebhookEvent.event_id == event.id)
        )

        if processed_event:
            logger.info("Skipping already processed webhook event", extra={"event_id": event.id})
            return
        
        session = event["data"]["object"]
        
        if event["type"] == "checkout.session.completed":
            await WebhookService._handle_checkout_completed(db, session, event.id)
        elif event["type"] == "payment_intent.payment_failed":
            await WebhookService._handle_payment_failed(db, event)
        elif event["type"] == "charge.refunded":
            await WebhookService._handle_charge_refunded(db, event)
        else:
            return

        try:
            await db.commit()
        except Exception:
            logger.error("Webhook event commit failed", extra={"event_id": event.id})
            await db.rollback()
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
                                detail="Webhook event commit failed")

    @staticmethod
    async def _handle_checkout_completed(db: AsyncSession, session: stripe.checkout.Session, event_id: Optional[str] = None):
        order = await db.scalar(
            select(Order)
            .where(Order.stripe_checkout_session_id == session.id)
            .with_for_update()
        )
        if not order:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")
        
        if order.payment_status == PaymentStatus.PAID:
            return
        
        result = await db.execute(
            select(OrderItem)
            .options(joinedload(OrderItem.product))
            .where(OrderItem.order_id == order.id)
        )
        order_items = result.scalars().all()

        for item in order_items:
            product = item.product
            if item.quantity > product.stock:
                logger.warning("Stock insufficient at payment confirmation, triggering auto-refund saga", extra={"order_id": order.id, "product_id": product.id})
                stripe.Refund.create(payment_intent=session.payment_intent)
                order.payment_status = PaymentStatus.REFUNDED
                order.status = OrderStatus.CANCELLED
                if event_id is not None:
                    new_event = ProcessedWebhookEvent(event_id=event_id)
                    db.add(new_event)
                
                return
            
        for item in order_items:
            product = item.product
            product.stock -= item.quantity
            inv_change = InventoryChange(product_id=product.id, change_amount=-item.quantity, reason=InventoryChangeReason.SALE)
            db.add(inv_change)

        await CartService.clear_cart(db, order.user_id)
        order.payment_status = PaymentStatus.PAID
        order.status = OrderStatus.CONFIRMED
        logger.info("Order confirmed after payment", extra={"order_id": order.id})

        items = [
            {"name": item.product.name, "quantity": item.quantity, "subtotal": str(item.subtotal)}
            for item in order_items
        ]

        user = await db.scalar(select(User).where(User.id == order.user_id))
        
        send_email_task.delay(
            user.email,
            "Order Confirmation",
            order_confirmation_email(order.id, str(order.total_amount), items)
        )
        if event_id is not None:
            new_event = ProcessedWebhookEvent(event_id=event_id)
            db.add(new_event)

    @staticmethod
    async def _handle_payment_failed(db: AsyncSession, event: stripe.Event):
        payment_intent_id = event["data"]["object"]["id"]
        order = await db.scalar(
            select(Order)
            .where(Order.stripe_payment_intent_id == payment_intent_id)
        )
        if not order:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")
        
        order.payment_status = PaymentStatus.FAILED

        new_event = ProcessedWebhookEvent(event_id=event.id)
        db.add(new_event)

    @staticmethod
    async def _handle_charge_refunded(db: AsyncSession, event: stripe.Event):
        payment_intent_id = event["data"]["object"]["payment_intent"]
        order = await db.scalar(
            select(Order)
            .where(Order.stripe_payment_intent_id == payment_intent_id)
        )
        if not order:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")
        
        order.payment_status = PaymentStatus.REFUNDED

        new_event = ProcessedWebhookEvent(event_id=event.id)
        db.add(new_event)

