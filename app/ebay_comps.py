import httpx
from .ebay_tokens import get_app_token


async def search_active_listings(query: str, limit: int = 25):
    token = await get_app_token()
    url = "https://api.ebay.com/buy/browse/v1/item_summary/search"
    headers = {"Authorization": f"Bearer {token}"}
    params = {"q": query, "limit": min(max(limit, 1), 50)}

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(url, headers=headers, params=params)
        r.raise_for_status()
        return r.json()
