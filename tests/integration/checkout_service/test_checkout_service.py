import pytest
from unittest.mock import patch, MagicMock
from sqlalchemy import select, func
from fastapi import HTTPException
import stripe
from services.checkout import CheckoutService
from services.cart import CartService
from models.cart_items import CartItem
from models.inventory_changes import InventoryChange
from models.enums import PaymentMethod, PaymentStatus


async def test_checkout_success(session, verified_user, product_factory, test_address):
    """Full checkout flow creates order, decrements stock, logs inventory change, and clears cart."""
    product = await product_factory(name="Laptop", price=1000.00, stock=10)
    await CartService.add_to_cart(db=session, user_id=verified_user.id, product_id=product.id, quantity=2)

    order = await CheckoutService.checkout(db=session, user_id=verified_user.id, address_id=test_address.id, payment_method=PaymentMethod.COD)

    # Order created with correct total
    assert order is not None
    assert order.user_id == verified_user.id
    assert float(order.total_amount) == 2000.00
    assert order.status == "pending"
    # Order items created with price snapshot
    items = order.items
    assert len(items) == 1
    assert items[0].product_id == product.id
    assert items[0].quantity == 2
    assert float(items[0].price_at_time) == 1000.00
    assert float(items[0].subtotal) == 2000.0
    # Stock decremented
    await session.refresh(product)
    assert product.stock == 8
    # Inventory change recorded
    inv_change = await session.scalar(select(InventoryChange).where(InventoryChange.product_id == product.id))
    assert inv_change is not None
    assert inv_change.change_amount == -2
    assert inv_change.reason == "sale"
    # Cart cleared
    cart_count = await session.scalar(
        select(func.count()).select_from(CartItem).where(CartItem.user_id == verified_user.id)
    )
    assert cart_count == 0


async def test_checkout_cart_empty(session, verified_user, test_address):
    """Checkout with no cart items raises 400."""
    with pytest.raises(HTTPException) as exc:
        await CheckoutService.checkout(db=session, user_id=verified_user.id, address_id=test_address.id, payment_method=PaymentMethod.COD)
    assert exc.value.status_code == 400
    assert exc.value.detail == "Can't checkout while cart is empty"


async def test_checkout_stock_insufficient(session, verified_user, product_factory, test_address):
    """Checkout raises 409 when a cart item quantity exceeds current stock."""
    product = await product_factory(name="Laptop", price=1000.00, stock=10)
    await CartService.add_to_cart(db=session, user_id=verified_user.id, product_id=product.id, quantity=2)
    product.stock = 1
    await session.commit()

    with pytest.raises(HTTPException) as exc:
        await CheckoutService.checkout(db=session, user_id=verified_user.id, address_id=test_address.id, payment_method=PaymentMethod.COD)
    assert exc.value.status_code == 409
    assert exc.value.detail["message"] == "Not enough stock available"


async def test_checkout_multiple_cart_items(session, verified_user, product_factory, test_address):
    """Checkout with multiple products creates all order items and clears the full cart."""
    product1 = await product_factory(name="Laptop", price=1000.00, stock=10)
    product2 = await product_factory(name="Monitor", price=500.00, stock=7)
    product3 = await product_factory(name="Keyboard", price=60.00, stock=5)

    await CartService.add_to_cart(db=session, user_id=verified_user.id, product_id=product1.id, quantity=2)
    await CartService.add_to_cart(db=session, user_id=verified_user.id, product_id=product2.id, quantity=1)
    await CartService.add_to_cart(db=session, user_id=verified_user.id, product_id=product3.id, quantity=3)

    order = await CheckoutService.checkout(db=session, user_id=verified_user.id, address_id=test_address.id, payment_method=PaymentMethod.COD)

    assert order is not None
    assert order.user_id == verified_user.id
    assert float(order.total_amount) == 2680.00
    assert order.status == "pending"
    assert len(order.items) == 3
    # Stock decremented for all 3 products
    await session.refresh(product1)
    await session.refresh(product2)
    await session.refresh(product3)
    assert product1.stock == 8
    assert product2.stock == 6
    assert product3.stock == 2
    # Inventory change recorded for each product
    inv_change1 = await session.scalar(select(InventoryChange).where(InventoryChange.product_id == product1.id))
    inv_change2 = await session.scalar(select(InventoryChange).where(InventoryChange.product_id == product2.id))
    inv_change3 = await session.scalar(select(InventoryChange).where(InventoryChange.product_id == product3.id))
    assert inv_change1 is not None
    assert inv_change1.change_amount == -2
    assert inv_change1.reason == "sale"
    assert inv_change2 is not None
    assert inv_change2.change_amount == -1
    assert inv_change2.reason == "sale"
    assert inv_change3 is not None
    assert inv_change3.change_amount == -3
    assert inv_change3.reason == "sale"
    # Cart cleared
    cart_count = await session.scalar(
        select(func.count()).select_from(CartItem).where(CartItem.user_id == verified_user.id)
    )
    assert cart_count == 0


async def test_checkout_stock_equivalent(session, verified_user, product_factory, test_address):
    """Checkout succeeds when quantity exactly matches available stock, leaving stock at zero."""
    product = await product_factory(name="Laptop", price=1000.00, stock=10)
    await CartService.add_to_cart(db=session, user_id=verified_user.id, product_id=product.id, quantity=10)

    order = await CheckoutService.checkout(db=session, user_id=verified_user.id, address_id=test_address.id, payment_method=PaymentMethod.COD)

    assert order is not None
    assert order.user_id == verified_user.id
    assert float(order.total_amount) == 10000.00
    assert order.status == "pending"
    # Stock hits exactly zero
    await session.refresh(product)
    assert product.stock == 0


def _mock_stripe_session(session_id="cs_test_123", url="https://checkout.stripe.com/pay/cs_test_123"):
    mock_session = MagicMock()
    mock_session.id = session_id
    mock_session.url = url
    return mock_session


async def test_stripe_checkout_creates_order_without_decrementing_stock(session, verified_user, product_factory, test_address):
    """Stripe checkout creates an UNPAID order with session ID but does not decrement stock or clear cart."""
    product = await product_factory(name="Laptop", price=1000.00, stock=10)
    await CartService.add_to_cart(db=session, user_id=verified_user.id, product_id=product.id, quantity=2)

    with patch("services.checkout.stripe.checkout.Session.create", return_value=_mock_stripe_session()):
        order = await CheckoutService.checkout(db=session, user_id=verified_user.id, address_id=test_address.id, payment_method=PaymentMethod.STRIPE)

    assert order.payment_method == PaymentMethod.STRIPE
    assert order.payment_status == PaymentStatus.UNPAID
    assert order.stripe_checkout_session_id == "cs_test_123"
    assert order.checkout_url == "https://checkout.stripe.com/pay/cs_test_123"
    # Stock not decremented
    await session.refresh(product)
    assert product.stock == 10
    # Cart not cleared
    cart_count = await session.scalar(
        select(func.count()).select_from(CartItem).where(CartItem.user_id == verified_user.id)
    )
    assert cart_count == 1


async def test_stripe_checkout_failure_marks_order_failed(session, verified_user, product_factory, test_address):
    """When Stripe API raises StripeError, the order is marked FAILED and 502 is raised."""
    product = await product_factory(name="Laptop", price=1000.00, stock=10)
    await CartService.add_to_cart(db=session, user_id=verified_user.id, product_id=product.id, quantity=1)

    with patch("services.checkout.stripe.checkout.Session.create", side_effect=stripe.StripeError("Stripe unavailable")):
        with pytest.raises(HTTPException) as exc:
            await CheckoutService.checkout(db=session, user_id=verified_user.id, address_id=test_address.id, payment_method=PaymentMethod.STRIPE)

    assert exc.value.status_code == 502
    # Stock not decremented
    await session.refresh(product)
    assert product.stock == 10


async def test_stripe_reuse_if_valid_returns_existing_order(session, verified_user, product_factory, test_address):
    """If an UNPAID Stripe order with a session already exists, it is returned without creating a new order."""
    product = await product_factory(name="Laptop", price=1000.00, stock=10)
    await CartService.add_to_cart(db=session, user_id=verified_user.id, product_id=product.id, quantity=1)

    with patch("services.checkout.stripe.checkout.Session.create", return_value=_mock_stripe_session()):
        first_order = await CheckoutService.checkout(db=session, user_id=verified_user.id, address_id=test_address.id, payment_method=PaymentMethod.STRIPE)

    with patch("services.checkout.stripe.checkout.Session.retrieve", return_value=_mock_stripe_session()):
        second_order = await CheckoutService.checkout(db=session, user_id=verified_user.id, address_id=test_address.id, payment_method=PaymentMethod.STRIPE)

    assert first_order.id == second_order.id
    assert second_order.checkout_url == "https://checkout.stripe.com/pay/cs_test_123"
