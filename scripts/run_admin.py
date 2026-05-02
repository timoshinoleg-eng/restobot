"""Container entrypoint for the admin API."""

import os
import pathlib
import sys

import uvicorn

PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


if __name__ == "__main__":
    uvicorn.run(
        "apps.admin_api.main:app",
        host="0.0.0.0",
        port=int(os.getenv("PORT", "8000")),
    )
