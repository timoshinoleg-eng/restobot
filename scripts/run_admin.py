"""Container entrypoint for the admin API."""

import os

import uvicorn


if __name__ == "__main__":
    uvicorn.run(
        "apps.admin_api.main:app",
        host="0.0.0.0",
        port=int(os.getenv("PORT", "8000")),
    )
