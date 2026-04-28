"""Public API placeholder for widget/guest routes."""

from __future__ import annotations

from fastapi import FastAPI

from apps.public_api.middleware import guest_session_middleware
from apps.public_api.routes import widget
from shared.config import get_settings

settings = get_settings()

app = FastAPI(
    title="RestoBot Public API",
    version=settings.APP_VERSION,
)
app.middleware("http")(guest_session_middleware)
app.include_router(widget.router)


@app.get("/health")
async def health() -> dict[str, str]:
    """Health probe."""

    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("apps.public_api.main:app", host="0.0.0.0", port=8011, reload=False)  # nosec B104


def main() -> None:
    import uvicorn

    uvicorn.run("apps.public_api.main:app", host="0.0.0.0", port=8011, reload=False)  # nosec B104
