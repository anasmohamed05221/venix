import pytest
from unittest.mock import patch, MagicMock
import stripe


@pytest.mark.asyncio
async def test_stripe_webhook_invalid_signature(client):
    """Returns 400 when the Stripe signature header fails verification."""
    with patch(
        "routers.webhooks.stripe.Webhook.construct_event",
        side_effect=stripe.error.SignatureVerificationError("bad sig", "sig-header"),
    ):
        response = await client.post(
            "/webhooks/stripe",
            content=b'{"type":"checkout.session.completed"}',
            headers={"stripe-signature": "bad-sig"},
        )

    assert response.status_code == 400


@pytest.mark.asyncio
async def test_stripe_webhook_valid_event_returns_ok(client):
    """Returns 200 with status ok when event signature is valid and handler succeeds."""
    mock_event = MagicMock()
    mock_event.id = "evt_test_123"
    mock_event.__getitem__ = MagicMock(
        side_effect=lambda k: {
            "type": "checkout.session.completed",
            "data": {"object": MagicMock()},
        }[k]
    )

    with patch("routers.webhooks.stripe.Webhook.construct_event", return_value=mock_event), \
         patch("routers.webhooks.WebhookService.handle_webhook_event", return_value=None):
        response = await client.post(
            "/webhooks/stripe",
            content=b'{"type":"checkout.session.completed"}',
            headers={"stripe-signature": "valid-sig"},
        )

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}