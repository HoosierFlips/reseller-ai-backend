import base64
import httpx
import time
from .config import EBAY_CLIENT_ID, EBAY_CLIENT_SECRET

_token_cache = {"access_token": None, "expires_at": 0}


async def get_app_token() -> str:
    now = int(time.time())
    if _token_cache["access_token"] and now < _token_cache["expires_at"] - 60:
        return _token_cache["access_token"]

    creds = f"{EBAY_CLIENT_ID}:{EBAY_CLIENT_SECRET}".encode("utf-8")
    b64 = base64.b64encode(creds).decode("utf-8")

    url = "https://api.ebay.com/identity/v1/oauth2/token"
    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "Authorization": f"Basic {b64}",
    }
    data = {
        "grant_type": "client_credentials",
        "scope": "https://api.ebay.com/oauth/api_scope",
    }

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(url, headers=headers, data=data)
        r.raise_for_status()
        payload = r.json()

    _token_cache["access_token"] = payload["access_token"]
    _token_cache["expires_at"] = now + int(payload.get("expires_in", 7200))
    return _token_cache["access_token"]
