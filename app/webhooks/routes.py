from fastapi import APIRouter, Header, HTTPException, Request

from app.config import settings
from app.webhooks.security import verify_signature

router = APIRouter()


@router.post("/webhooks/github")
async def github_webhook(
    request: Request,
    x_hub_signature_256: str = Header(default=""),
    x_github_event: str = Header(default=""),
    x_github_delivery: str = Header(default=""),
) -> dict[str, str]:
    body = await request.body()

    if not verify_signature(body, x_hub_signature_256, settings.github_webhook_secret):
        raise HTTPException(status_code=401, detail="Invalid webhook signature")

    return {
        "status": "received",
        "event": x_github_event,
        "delivery": x_github_delivery,
    }
