import pytest
from unittest.mock import patch, MagicMock
from sqlalchemy import select
from fastapi import HTTPException

from services.payments import WebhookService
from models.orders import Order
from models.order_items import OrderItem
from models.inventory_changes import InventoryChange
from models.processed_webhook_events import ProcessedWebhookEvent
from models.enums import PaymentMethod, PaymentStatus, OrderStatus


# Helpers

def _mock_stripe_session(session_id="cs_test_123", payment_intent_id="pi_test_123"):
    """Build a minimal mock Stripe checkout.Session object."""
    mock = MagicMock()
    mock.id = session_id
    mock.payment_intent = payment_intent_id
    return mock


def _mock_event(event_id, event_type, session_obj):
    """Build a minimal mock Stripe Event with dict-key access."""
    mock = MagicMock()
    mock.id = event_id
    mock.__getitem__ = MagicMock(
        side_effect=lambda k: {
            "type": event_type,
            "data": {"object": session_obj},
        }[k]
    )
    return mock


# Fixtures

@pytest.fixture
async def stripe_order(session, verified_user, product_factory, test_address):
    """Stripe UNPAID order with one OrderItem (stock=10, qty=2)."""
    product = await product_factory(name="Laptop", price=1000.00, stock=10)
    order = Order(
        user_id=verified_user.id,
        address_id=test_address.id,
        total_amount=2000.00,
        payment_method=PaymentMethod.STRIPE,
        payment_status=PaymentStatus.UNPAID,
        status=OrderStatus.PENDING,
        stripe_checkout_session_id="cs_test_123",
        stripe_payment_intent_id="pi_test_123",
    )
    session.add(order)
    await session.flush()

    order_item = OrderItem(
        order_id=order.id,
        product_id=product.id,
        price_at_time=1000.00,
        quantity=2,
        subtotal=2000.00,
    )
    session.add(order_item)
    await session.commit()
    await session.refresh(order)
    await session.refresh(product)
    return order, product


# Tests

async def test_checkout_completed_success(session, stripe_order):
    """Payment confirmation marks order PAID, decrements stock, logs inventory change."""
    order, product = stripe_order
    mock_session = _mock_stripe_session(session_id="cs_test_123")
    mock_event = _mock_event("evt_test_123", "checkout.session.completed", mock_session)

    await WebhookService.handle_webhook_event(session, mock_event)

    assert order.payment_status == PaymentStatus.PAID
    assert order.status == OrderStatus.CONFIRMED

    await session.refresh(product)
    assert product.stock == 8

    inv_change = await session.scalar(
        select(InventoryChange).where(InventoryChange.product_id == product.id)
    )
    assert inv_change is not None
    assert inv_change.change_amount == -2

    event_record = await session.scalar(
        select(ProcessedWebhookEvent).where(ProcessedWebhookEvent.event_id == "evt_test_123")
    )
    assert event_record is not None


async def test_checkout_completed_idempotent(session, stripe_order):
    """Duplicate webhook with same event_id is skipped — order remains unchanged."""
    order, _ = stripe_order
    already_processed = ProcessedWebhookEvent(event_id="evt_duplicate")
    session.add(already_processed)
    await session.commit()

    mock_session = _mock_stripe_session(session_id="cs_test_123")
    mock_event = _mock_event("evt_duplicate", "checkout.session.completed", mock_session)

    await WebhookService.handle_webhook_event(session, mock_event)

    assert order.payment_status == PaymentStatus.UNPAID


async def test_checkout_completed_already_paid(session, stripe_order):
    """_handle_checkout_completed returns early if order is already PAID."""
    order, product = stripe_order
    order.payment_status = PaymentStatus.PAID
    await session.commit()

    mock_session = _mock_stripe_session(session_id="cs_test_123")
    await WebhookService._handle_checkout_completed(session, mock_session)

    await session.refresh(product)
    assert product.stock == 10


async def test_checkout_completed_insufficient_stock_triggers_refund(session, stripe_order):
    """Stock runs out between checkout and payment — refund is triggered, order is cancelled."""
    order, product = stripe_order
    product.stock = 0
    await session.commit()

    mock_session = _mock_stripe_session(session_id="cs_test_123", payment_intent_id="pi_test_123")

    with patch("services.payments.stripe.Refund.create") as mock_refund:
        await WebhookService._handle_checkout_completed(session, mock_session)
        mock_refund.assert_called_once_with(payment_intent="pi_test_123")

    assert order.payment_status == PaymentStatus.REFUNDED
    assert order.status == OrderStatus.CANCELLED