import pytest
from unittest.mock import MagicMock
from fastapi import HTTPException

from services.payments import WebhookService
from models.orders import Order
from models.processed_webhook_events import ProcessedWebhookEvent
from models.enums import PaymentMethod, PaymentStatus, OrderStatus


# Helpers

def _mock_payment_failed_event(event_id="evt_failed_123", payment_intent_id="pi_test_123"):
    """Build a mock payment_intent.payment_failed Stripe event."""
    mock = MagicMock()
    mock.id = event_id
    mock.__getitem__ = MagicMock(
        side_effect=lambda k: {
            "type": "payment_intent.payment_failed",
            "data": {"object": {"id": payment_intent_id}},
        }[k]
    )
    return mock


def _mock_charge_refunded_event(event_id="evt_refund_123", payment_intent_id="pi_test_123"):
    """Build a mock charge.refunded Stripe event."""
    mock = MagicMock()
    mock.id = event_id
    mock.__getitem__ = MagicMock(
        side_effect=lambda k: {
            "type": "charge.refunded",
            "data": {"object": {"payment_intent": payment_intent_id}},
        }[k]
    )
    return mock


# Fixtures

@pytest.fixture
async def stripe_order_with_pi(session, verified_user, product_factory, test_address):
    """Stripe UNPAID order with stripe_payment_intent_id set."""
    await product_factory(name="Laptop", price=500.00, stock=5)
    order = Order(
        user_id=verified_user.id,
        address_id=test_address.id,
        total_amount=500.00,
        payment_method=PaymentMethod.STRIPE,
        payment_status=PaymentStatus.UNPAID,
        status=OrderStatus.PENDING,
        stripe_checkout_session_id="cs_test_pi_123",
        stripe_payment_intent_id="pi_test_123",
    )
    session.add(order)
    await session.commit()
    await session.refresh(order)
    return order


# Tests

async def test_payment_failed_marks_order_failed(session, stripe_order_with_pi):
    """payment_intent.payment_failed webhook marks the order payment status as FAILED."""
    order = stripe_order_with_pi
    mock_event = _mock_payment_failed_event(payment_intent_id="pi_test_123")

    await WebhookService._handle_payment_failed(session, mock_event)

    assert order.payment_status == PaymentStatus.FAILED

    from sqlalchemy import select
    event_record = await session.scalar(
        select(ProcessedWebhookEvent).where(ProcessedWebhookEvent.event_id == "evt_failed_123")
    )
    assert event_record is not None


async def test_payment_failed_order_not_found(session):
    """payment_intent.payment_failed with unknown payment_intent_id raises 404."""
    mock_event = _mock_payment_failed_event(payment_intent_id="pi_nonexistent")

    with pytest.raises(HTTPException) as exc:
        await WebhookService._handle_payment_failed(session, mock_event)

    assert exc.value.status_code == 404


async def test_charge_refunded_marks_order_refunded(session, stripe_order_with_pi):
    """charge.refunded webhook marks the order payment status as REFUNDED."""
    order = stripe_order_with_pi
    mock_event = _mock_charge_refunded_event(payment_intent_id="pi_test_123")

    await WebhookService._handle_charge_refunded(session, mock_event)

    assert order.payment_status == PaymentStatus.REFUNDED

    from sqlalchemy import select
    event_record = await session.scalar(
        select(ProcessedWebhookEvent).where(ProcessedWebhookEvent.event_id == "evt_refund_123")
    )
    assert event_record is not None


async def test_charge_refunded_order_not_found(session):
    """charge.refunded with unknown payment_intent_id raises 404."""
    mock_event = _mock_charge_refunded_event(payment_intent_id="pi_nonexistent")

    with pytest.raises(HTTPException) as exc:
        await WebhookService._handle_charge_refunded(session, mock_event)

    assert exc.value.status_code == 404