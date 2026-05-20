from fastapi import APIRouter, status, Request, HTTPException
from services.payments import WebhookService
from utils.deps import db_dependency
from core.config import settings
from utils.logger import get_logger
import stripe

logger = get_logger(__name__)

router = APIRouter(
    prefix="/webhooks",
    tags=["webhooks"]
)

@router.post("/stripe", status_code=status.HTTP_200_OK)
async def stripe_webhook(request: Request, db: db_dependency):
    """Receive and process Stripe webhook events. Verifies signature before dispatching."""
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")
    try:
        event = stripe.Webhook.construct_event(payload, sig_header, settings.STRIPE_WEBHOOK_SECRET)
    except stripe.error.SignatureVerificationError:
        logger.warning("Invalid Stripe webhook signature", extra={"sig_header": sig_header})
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST)
    await WebhookService.handle_webhook_event(db, event)
    return {"status": "ok"}
