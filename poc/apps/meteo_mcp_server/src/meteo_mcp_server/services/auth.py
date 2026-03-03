from __future__ import annotations

import base64
import time
from dataclasses import dataclass

import httpx


@dataclass
class _TokenCache:
    access_token: str
    expires_at: float


_cache: _TokenCache | None = None
_REFRESH_BUFFER_SECONDS = 60


async def get_access_token(consumer_key: str, consumer_secret: str, oauth_url: str) -> str:
    global _cache

    if _cache and time.time() < _cache.expires_at - _REFRESH_BUFFER_SECONDS:
        return _cache.access_token

    credentials = base64.b64encode(f"{consumer_key}:{consumer_secret}".encode()).decode()

    async with httpx.AsyncClient() as client:
        response = await client.post(
            oauth_url,
            params={"grant_type": "client_credentials"},
            headers={"Authorization": f"Basic {credentials}"},
        )
        response.raise_for_status()
        data = response.json()

    _cache = _TokenCache(
        access_token=data["access_token"],
        expires_at=time.time() + int(data["expires_in"]),
    )
    return _cache.access_token
