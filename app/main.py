from fastapi import FastAPI

from app.config import settings
from app.webhooks.routes import router as webhooks_router

app = FastAPI(title=settings.app_name)

app.include_router(webhooks_router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
