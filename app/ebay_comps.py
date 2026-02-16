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


# --- helpers for pricing + shipping normalization ---

from typing import Any, Optional

def _to_float(x: Any) -> Optional[float]:
    try:
        if x is None:
            return None
        return float(x)
    except (TypeError, ValueError):
        return None

def normalize_active_comps(raw: dict) -> list[dict]:
    """
    Turns eBay Browse itemSummaries into a stable list of comps with:
    price, shipping, delivered_total (price+shipping when available).
    """
    out: list[dict] = []
    for it in (raw.get("itemSummaries") or []):
        price = _to_float((it.get("price") or {}).get("value"))

        shipping: Optional[float] = None
        shipping_opts = it.get("shippingOptions") or []
        if shipping_opts:
            opt0 = shipping_opts[0] or {}
            ship_cost_val = (opt0.get("shippingCost") or {}).get("value")
            if ship_cost_val is not None:
                shipping = _to_float(ship_cost_val)
            else:
                # Sometimes Browse marks free shipping via shippingCostType
                if opt0.get("shippingCostType") == "FREE":
                    shipping = 0.0

        delivered_total: Optional[float] = None
        if price is not None and shipping is not None:
            delivered_total = price + shipping

        out.append({
            "itemId": it.get("itemId"),
            "title": it.get("title"),
            "condition": it.get("condition"),
            "itemWebUrl": it.get("itemWebUrl"),
            "price": price,
            "shipping": shipping,
            "delivered_total": delivered_total,
        })
    return out
