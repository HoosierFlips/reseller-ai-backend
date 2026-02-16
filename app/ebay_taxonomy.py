import httpx
from .ebay_tokens import get_app_token


async def get_default_category_tree_id(marketplace_id: str = "EBAY_US") -> str:
    token = await get_app_token()
    url = "https://api.ebay.com/commerce/taxonomy/v1/get_default_category_tree_id"
    headers = {
        "Authorization": f"Bearer {token}",
        "X-EBAY-C-MARKETPLACE-ID": marketplace_id,
    }

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(url, headers=headers, params={"marketplace_id": marketplace_id})

        r.raise_for_status()
        return r.json()["categoryTreeId"]


async def get_category_suggestions(category_tree_id: str, query: str):
    token = await get_app_token()
    url = f"https://api.ebay.com/commerce/taxonomy/v1/category_tree/{category_tree_id}/get_category_suggestions"
    headers = {"Authorization": f"Bearer {token}"}
    params = {"q": query}

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(url, headers=headers, params=params)
        r.raise_for_status()
        return r.json()


async def get_item_aspects_for_category(category_tree_id: str, category_id: str):
    token = await get_app_token()
    url = f"https://api.ebay.com/commerce/taxonomy/v1/category_tree/{category_tree_id}/get_item_aspects_for_category"
    headers = {"Authorization": f"Bearer {token}"}
    params = {"category_id": category_id}

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(url, headers=headers, params=params)
        r.raise_for_status()
        return r.json()
