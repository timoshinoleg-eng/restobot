"""Object storage abstraction used by menu image uploads."""

from __future__ import annotations

import os
from pathlib import Path

import aiofiles

from shared.config import get_settings

settings = get_settings()


class ObjectStorage:
    """Simple async storage abstraction with local fallback."""

    def __init__(self) -> None:
        self._root = Path(".storage")

    async def upload_bytes(self, *, key: str, body: bytes, content_type: str) -> str:
        """Persist bytes and return a stable object URL.

        The current repository does not ship an S3 SDK, so we keep a local
        fallback that mirrors the final object key shape. This keeps tests and
        local development deterministic while preserving the contract for future
        S3-compatible uploads.
        """

        target = self._root / key
        target.parent.mkdir(parents=True, exist_ok=True)
        async with aiofiles.open(target, "wb") as handle:
            await handle.write(body)
        endpoint = str(settings.YC_OBJECT_STORAGE_ENDPOINT).rstrip("/")
        bucket = settings.YC_OBJECT_STORAGE_BUCKET
        safe_key = key.replace(os.sep, "/")
        return f"{endpoint}/{bucket}/{safe_key}"


object_storage = ObjectStorage()
