import pytest
from unittest.mock import patch, MagicMock
from contextlib import asynccontextmanager
from datetime import datetime, timezone, timedelta

from tasks.reconciliation import sweep_stale_stripe_orders
from models.orders import Order
from models.enums import PaymentMethod, PaymentStatus, OrderStatus


# Fixture

@pytest.fixture
async def stale_stripe_order(session, verified_user, test_address):
    """Stripe UNPAID order with created_at 1 hour ago so reconciliation picks it up."""
    order = Order(
        user_id=verified_user.id,
        address_id=test_address.id,
        total_amount=500.00,
        payment_method=PaymentMethod.STRIPE,
        payment_status=PaymentStatus.UNPAID,
        status=OrderStatus.PENDING,
        stripe_checkout_session_id="cs_test_stale_123",
    )
    session.add(order)
    await session.commit()
    await session.refresh(order)

    order.created_at = datetime.now(timezone.utc) - timedelta(hours=1)
    await session.commit()
    await session.refresh(order)
    return order


# Helpers

def _run_reconciliation(session, mock_stripe_session):
    """
    Execute the reconciliation task inside the test event loop.

    asyncio.run() cannot be called from a running event loop (pytest-asyncio).
    Strategy: patch asyncio.run to capture the coroutine, then await it
    inside the patch context so async_sessionmaker and stripe are still mocked.
    Returns the captured coroutine (already awaited by the caller).
    """
    captured = {}

    def mock_asyncio_run(coro):
        captured["coro"] = coro

    @asynccontextmanager
    async def _test_session_ctx():
        yield session

    return captured, mock_asyncio_run, _test_session_ctx


# Tests

async def test_reconciliation_confirms_completed_session(session, stale_stripe_order):
    """Stale order whose Stripe session is 'complete' is confirmed via reconciliation."""
    order = stale_stripe_order

    mock_stripe_session = MagicMock()
    mock_stripe_session.status = "complete"
    mock_stripe_session.id = "cs_test_stale_123"

    captured = {}

    def mock_asyncio_run(coro):
        captured["coro"] = coro

    @asynccontextmanager
    async def _test_session_ctx():
        yield session

    with patch("tasks.reconciliation.asyncio.run", side_effect=mock_asyncio_run), \
         patch("tasks.reconciliation.async_sessionmaker", return_value=_test_session_ctx()), \
         patch("tasks.reconciliation.stripe.checkout.Session.retrieve", return_value=mock_stripe_session):
        sweep_stale_stripe_orders()
        assert "coro" in captured
        await captured["coro"]

    await session.refresh(order)
    assert order.payment_status == PaymentStatus.PAID
    assert order.status == OrderStatus.CONFIRMED


async def test_reconciliation_expires_stale_order(session, stale_stripe_order):
    """Stale order whose Stripe session is 'expired' is cancelled via reconciliation."""
    order = stale_stripe_order

    mock_stripe_session = MagicMock()
    mock_stripe_session.status = "expired"

    captured = {}

    def mock_asyncio_run(coro):
        captured["coro"] = coro

    @asynccontextmanager
    async def _test_session_ctx():
        yield session

    with patch("tasks.reconciliation.asyncio.run", side_effect=mock_asyncio_run), \
         patch("tasks.reconciliation.async_sessionmaker", return_value=_test_session_ctx()), \
         patch("tasks.reconciliation.stripe.checkout.Session.retrieve", return_value=mock_stripe_session):
        sweep_stale_stripe_orders()
        assert "coro" in captured
        await captured["coro"]

    await session.refresh(order)
    assert order.payment_status == PaymentStatus.EXPIRED
    assert order.status == OrderStatus.CANCELLED


async def test_reconciliation_skips_open_session(session, stale_stripe_order):
    """Stale order whose Stripe session is still 'open' is left unchanged."""
    order = stale_stripe_order

    mock_stripe_session = MagicMock()
    mock_stripe_session.status = "open"

    captured = {}

    def mock_asyncio_run(coro):
        captured["coro"] = coro

    @asynccontextmanager
    async def _test_session_ctx():
        yield session

    with patch("tasks.reconciliation.asyncio.run", side_effect=mock_asyncio_run), \
         patch("tasks.reconciliation.async_sessionmaker", return_value=_test_session_ctx()), \
         patch("tasks.reconciliation.stripe.checkout.Session.retrieve", return_value=mock_stripe_session):
        sweep_stale_stripe_orders()
        assert "coro" in captured
        await captured["coro"]

    await session.refresh(order)
    assert order.payment_status == PaymentStatus.UNPAID
    assert order.status == OrderStatus.PENDING
