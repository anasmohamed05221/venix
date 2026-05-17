import pytest
from unittest.mock import patch, MagicMock
import stripe


def _mock_stripe_session(session_id="cs_test_123", url="https://checkout.stripe.com/pay/cs_test_123"):
    mock_session = MagicMock()
    mock_session.id = session_id
    mock_session.url = url
    return mock_session


# Authentication

@pytest.mark.asyncio
async def test_checkout_requires_auth(client):
    """Checkout endpoint requires authentication."""
    response = await client.post("/orders/")

    assert response.status_code == 401


# COD path

@pytest.mark.asyncio
async def test_checkout_success(client, user_token, product_factory, test_address):
    """Successful checkout returns 201 with full order and item details."""
    product = await product_factory(name="Laptop", price=1000.00, stock=10)

    await client.post("/cart/", json={"product_id": product.id, "quantity": 2},
                      headers={"Authorization": f"Bearer {user_token}"})

    response = await client.post(
        "/orders/",
        json={"address_id": test_address.id, "payment_method": "cod"},
        headers={"Authorization": f"Bearer {user_token}"}
    )

    assert response.status_code == 201
    data = response.json()
    # Order fields
    assert float(data["total_amount"]) == 2000.00
    assert data["status"] == "pending"
    assert data["payment_method"] == "cod"
    # Items with product details
    assert len(data["items"]) == 1
    item = data["items"][0]
    assert float(item["price_at_time"]) == 1000.00
    assert item["quantity"] == 2
    assert float(item["subtotal"]) == 2000.00
    assert item["product"]["name"] == "Laptop"


@pytest.mark.asyncio
async def test_checkout_empty_cart(client, user_token, test_address):
    """Checkout with an empty cart returns 400."""
    response = await client.post(
        "/orders/",
        json={"address_id": test_address.id, "payment_method": "cod"},
        headers={"Authorization": f"Bearer {user_token}"}
    )

    assert response.status_code == 400


@pytest.mark.asyncio
async def test_checkout_insufficient_stock(client, user_token, session, product_factory, test_address):
    """Checkout raises 409 when stock drops below cart quantity before checkout."""
    product = await product_factory(name="Laptop", price=1000.00, stock=10)

    # Add to cart when stock is sufficient
    await client.post("/cart/", json={"product_id": product.id, "quantity": 5},
                      headers={"Authorization": f"Bearer {user_token}"})

    # Simulate stock dropping before checkout
    product.stock = 2
    await session.commit()

    response = await client.post(
        "/orders/",
        json={"address_id": test_address.id, "payment_method": "cod"},
        headers={"Authorization": f"Bearer {user_token}"}
    )

    assert response.status_code == 409
    assert response.json()["detail"]["message"] == "Not enough stock available"


@pytest.mark.asyncio
async def test_checkout_response_schema(client, user_token, product_factory, test_address):
    """Response includes all expected fields from OrderOut schema."""
    product = await product_factory(name="Mouse", price=50.00, stock=5)

    await client.post("/cart/", json={"product_id": product.id, "quantity": 1},
                      headers={"Authorization": f"Bearer {user_token}"})

    response = await client.post(
        "/orders/",
        json={"address_id": test_address.id, "payment_method": "cod"},
        headers={"Authorization": f"Bearer {user_token}"}
    )

    assert response.status_code == 201
    data = response.json()
    # Top-level order fields
    assert "id" in data
    assert "total_amount" in data
    assert "status" in data
    assert "payment_method" in data
    assert "created_at" in data
    assert "updated_at" in data
    assert "items" in data
    # Item fields
    item = data["items"][0]
    assert "id" in item
    assert "price_at_time" in item
    assert "quantity" in item
    assert "subtotal" in item
    assert "product" in item
    # Nested product fields
    assert "id" in item["product"]
    assert "name" in item["product"]
    assert "price" in item["product"]


@pytest.mark.asyncio
async def test_checkout_clears_cart(client, user_token, product_factory, test_address):
    """Cart is empty after a successful checkout."""
    product = await product_factory(name="Keyboard", price=60.00, stock=5)

    await client.post("/cart/", json={"product_id": product.id, "quantity": 1},
                      headers={"Authorization": f"Bearer {user_token}"})

    await client.post(
        "/orders/",
        json={"address_id": test_address.id, "payment_method": "cod"},
        headers={"Authorization": f"Bearer {user_token}"}
    )

    cart_response = await client.get("/cart/", headers={"Authorization": f"Bearer {user_token}"})
    assert cart_response.json()["cart_items"] == []


@pytest.mark.asyncio
async def test_checkout_invalid_address(client, user_token, product_factory):
    """Checkout returns 404 when address_id does not belong to the user."""
    product = await product_factory(name="Laptop", price=1000.00, stock=10)

    await client.post("/cart/", json={"product_id": product.id, "quantity": 1},
                      headers={"Authorization": f"Bearer {user_token}"})

    response = await client.post(
        "/orders/",
        json={"address_id": 99999, "payment_method": "cod"},
        headers={"Authorization": f"Bearer {user_token}"}
    )

    assert response.status_code == 404


# Stripe path

@pytest.mark.asyncio
async def test_stripe_checkout_returns_checkout_url(client, user_token, product_factory, test_address):
    """Stripe checkout returns 201 with a checkout_url and empty items (stock not decremented yet)."""
    product = await product_factory(name="Laptop", price=1000.00, stock=10)

    await client.post("/cart/", json={"product_id": product.id, "quantity": 1},
                      headers={"Authorization": f"Bearer {user_token}"})

    with patch("services.checkout.stripe.checkout.Session.create", return_value=_mock_stripe_session()):
        response = await client.post(
            "/orders/",
            json={"address_id": test_address.id, "payment_method": "stripe"},
            headers={"Authorization": f"Bearer {user_token}"}
        )

    assert response.status_code == 201
    data = response.json()
    assert data["payment_method"] == "stripe"
    assert data["payment_status"] == "unpaid"
    assert data["checkout_url"] == "https://checkout.stripe.com/pay/cs_test_123"
    assert data["items"] == []


@pytest.mark.asyncio
async def test_stripe_checkout_failure_returns_502(client, user_token, product_factory, test_address):
    """Stripe checkout returns 502 when the Stripe API is unavailable."""
    product = await product_factory(name="Laptop", price=1000.00, stock=10)

    await client.post("/cart/", json={"product_id": product.id, "quantity": 1},
                      headers={"Authorization": f"Bearer {user_token}"})

    with patch("services.checkout.stripe.checkout.Session.create", side_effect=stripe.StripeError("unavailable")):
        response = await client.post(
            "/orders/",
            json={"address_id": test_address.id, "payment_method": "stripe"},
            headers={"Authorization": f"Bearer {user_token}"}
        )

    assert response.status_code == 502
