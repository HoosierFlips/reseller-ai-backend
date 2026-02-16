from fastapi import FastAPI, Header, HTTPException, Depends
from typing import Optional

from .config import APP_API_KEY, EBAY_MARKETPLACE_ID
from .db import supabase
from .schemas import (
    ItemCreate,
    ItemUpdate,
    CompsRequest,
    CategorySuggestRequest,
    AspectsRequest,
    ItemCategorySetRequest,
)
from .ebay_taxonomy import (
    get_default_category_tree_id,
    get_category_suggestions,
    get_item_aspects_for_category,
)
from .ebay_comps import search_active_listings

app = FastAPI(title="Reseller AI Backend", version="0.1.0")


def require_api_key(
    authorization: Optional[str] = Header(default=None),
    x_api_key: Optional[str] = Header(default=None, alias="X-API-Key"),
):
    """
    Accepts either:
      - Authorization: Bearer <APP_API_KEY>
      - Authorization: <APP_API_KEY>
      - X-API-Key: <APP_API_KEY>   (Swagger-friendly)
    """
    token = None

    # Preferred: Authorization header
    if authorization:
        token = authorization.strip()
        if token.lower().startswith("bearer "):
            token = token.split(" ", 1)[1].strip()

    # Fallback: X-API-Key header
    if not token and x_api_key:
        token = x_api_key.strip()

    if not token:
        raise HTTPException(status_code=401, detail="Missing API key")

    if token != APP_API_KEY:
        raise HTTPException(status_code=403, detail="Invalid API key")


@app.get("/health")
def health():
    return {"ok": True}


@app.post("/inventory/items")
def create_item(payload: ItemCreate, _: None = Depends(require_api_key)):
    res = supabase.table("items").insert(payload.model_dump(exclude_none=True)).execute()
    item = res.data[0]

    supabase.table("item_events").insert(
        {
            "item_id": item["id"],
            "event_type": "analyzed",
            "payload": payload.model_dump(exclude_none=True),
        }
    ).execute()

    return {"item": item}


@app.get("/inventory/items/{item_id}")
def get_item(item_id: str, _: None = Depends(require_api_key)):
    res = supabase.table("items").select("*").eq("id", item_id).single().execute()
    return {"item": res.data}


@app.patch("/inventory/items/{item_id}")
def update_item(item_id: str, payload: ItemUpdate, _: None = Depends(require_api_key)):
    data = payload.model_dump(exclude_none=True)

    res = supabase.table("items").update(data).eq("id", item_id).execute()

    supabase.table("item_events").insert(
        {"item_id": item_id, "event_type": "edited", "payload": data}
    ).execute()

    return {"item": res.data[0]}


@app.post("/ebay/active_comps")
async def active_comps(req: CompsRequest, _: None = Depends(require_api_key)):
    raw = await search_active_listings(req.query, req.limit)
    return {"raw": raw}


@app.get("/ebay/default_category_tree")
async def default_category_tree(_: None = Depends(require_api_key)):
    tree_id = await get_default_category_tree_id(EBAY_MARKETPLACE_ID)
    return {"category_tree_id": tree_id}


@app.post("/ebay/category_suggestions")
async def category_suggestions(req: CategorySuggestRequest, _: None = Depends(require_api_key)):
    tree_id = await get_default_category_tree_id(EBAY_MARKETPLACE_ID)
    suggestions = await get_category_suggestions(tree_id, req.query)
    return {"category_tree_id": tree_id, "suggestions": suggestions}


@app.get("/ebay/required_aspects")
async def required_aspects(category_tree_id: str, category_id: str, _: None = Depends(require_api_key)):
    raw = await get_item_aspects_for_category(category_tree_id, category_id)

    aspects = raw.get("aspects", [])
    if isinstance(aspects, dict):
        aspects = aspects.get("aspects", [])

    required = []
    for a in aspects:
        constraint = a.get("aspectConstraint", {}) or {}
        if constraint.get("aspectRequired") is True:
            values = [
                v.get("localizedValue")
                for v in (a.get("aspectValues") or [])
                if v.get("localizedValue")
            ]

            required.append(
                {
                    "name": a.get("localizedAspectName"),
                    "required": True,
                    "use_typeahead": len(values) > 200,
                    "value_count": len(values),
                    "values": [] if len(values) > 200 else values,
                }
            )

    return {
        "category_tree_id": category_tree_id,
        "category_id": category_id,
        "required_aspects": required,
    }


@app.get("/ebay/aspect_values")
async def aspect_values(
    category_tree_id: str,
    category_id: str,
    aspect_name: str,
    q: str = "",
    limit: int = 25,
    _: None = Depends(require_api_key),
):
    raw = await get_item_aspects_for_category(category_tree_id, category_id)

    aspects = raw.get("aspects", [])
    if isinstance(aspects, dict):
        aspects = aspects.get("aspects", [])

    # Find the aspect
    target = None
    for a in aspects:
        if (a.get("localizedAspectName") or "").lower() == aspect_name.lower():
            target = a
            break

    if not target:
        return {"values": []}

    values = [v.get("localizedValue") for v in (target.get("aspectValues") or []) if v.get("localizedValue")]

    # Filter by q
    qq = (q or "").strip().lower()
    if qq:
        values = [v for v in values if qq in v.lower()]

    return {"values": values[: max(1, min(limit, 200))]}


@app.post("/inventory/items/{item_id}/category")
async def set_item_category(item_id: str, req: ItemCategorySetRequest, _: None = Depends(require_api_key)):
    raw = await get_item_aspects_for_category(req.category_tree_id, req.category_id)

    aspects = raw.get("aspects", [])
    if isinstance(aspects, dict):
        aspects = aspects.get("aspects", [])

    required_names = [
        a.get("localizedAspectName")
        for a in aspects
        if (a.get("aspectConstraint") or {}).get("aspectRequired") is True
    ]

    missing = [name for name in required_names if not req.required_aspects.get(name)]
    if missing:
        raise HTTPException(status_code=422, detail={"missing_required_aspects": missing})

    update = {
        "category_tree_id": req.category_tree_id,
        "category_id": req.category_id,
        "required_aspects": req.required_aspects,
        "required_aspects_status": "complete",
    }

    res = supabase.table("items").update(update).eq("id", item_id).execute()
    if not res.data:
        raise HTTPException(status_code=404, detail="Item not found")

    supabase.table("item_events").insert(
        {"item_id": item_id, "event_type": "category_set", "payload": update}
    ).execute()

    return {"item": res.data[0]}


@app.post("/ebay/generate_listing/{item_id}")
async def generate_listing(item_id: str, _: None = Depends(require_api_key)):
    import re
    from collections import Counter

    # 1) Load item
    res = supabase.table("items").select("*").eq("id", item_id).single().execute()
    item = res.data
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")

    required_aspects = item.get("required_aspects") or {}
    if item.get("required_aspects_status") != "complete":
        raise HTTPException(status_code=422, detail="required_aspects_status is not complete")

    brand = (required_aspects.get("Brand") or item.get("brand") or "").strip()
    size = (required_aspects.get("US Shoe Size") or "").strip()
    color = (required_aspects.get("Color") or "").strip()
    dept = (required_aspects.get("Department") or "").strip()

    # 2) Optional: infer a simple model hint from comps titles
    model_hint = ""
    comps = item.get("comps_json") or {}
    titles = []
    try:
        titles = [x.get("title", "") for x in (comps.get("itemSummaries") or []) if x.get("title")]
    except Exception:
        titles = []

    if titles:
        stop = {
            "mens","men","men's","women","women's","shoe","shoes","sneaker","sneakers",
            "athletic","running","trainer","trainers","new","box","with","without",
            "preowned","pre-owned","used","size","sz","black","white","blue","red","gray","grey",
            "orange","pink","green","brown","tan","beige","ivory","silver","gold","multi","multicolor",
        }
        if brand:
            stop.add(brand.lower())

        # tokenize and build bigrams
        tokens_per_title = []
        for t in titles[:25]:
            t2 = re.sub(r"[^A-Za-z0-9\s]", " ", t).lower()
            t2 = re.sub(r"\b\d+(\.\d+)?\b", " ", t2)  # remove numbers
            words = [w for w in t2.split() if len(w) >= 2 and w not in stop]
            tokens_per_title.append(words)

        bigrams = []
        for words in tokens_per_title:
            bigrams += [" ".join(words[i:i+2]) for i in range(len(words)-1)]

        c = Counter(bigrams)
        top = c.most_common(1)
        if top and top[0][1] >= 3:
            model_hint = top[0][0].title()
        else:
            # fallback to top single token if bigram not strong
            singles = Counter([w for ws in tokens_per_title for w in ws])
            top1 = singles.most_common(1)
            if top1 and top1[0][1] >= 4:
                model_hint = top1[0][0].title()

    # 3) Build title (max 80 chars for eBay)
    parts = []
    if brand:
        parts.append(brand)
    if model_hint:
        parts.append(model_hint)
    if dept:
        parts.append(dept)
    parts.append("Athletic Shoes")
    if size:
        parts.append(f"Size {size}")
    if color:
        parts.append(color)

    title = " ".join(parts)
    title = re.sub(r"\s+", " ", title).strip()
    if len(title) > 80:
        # drop the generic phrase first
        title2 = title.replace(" Athletic Shoes", "").strip()
        title = title2 if len(title2) <= 80 else title[:80].rstrip()

    # 4) Description + specifics
    suggested_price = item.get("typical_price")

    desc_lines = [
        f"Brand: {brand}" if brand else None,
        f"Department: {dept}" if dept else None,
        f"US Shoe Size: {size}" if size else None,
        f"Color: {color}" if color else None,
        "",
        "Item specifics are based on the selected eBay category requirements.",
        "Please verify condition, style, and exact model from the photos before listing.",
    ]
    description = "\n".join([x for x in desc_lines if x is not None]).strip()

    item_specifics = required_aspects  # Option A: store as JSONB dict

    update = {
        "ebay_title": title,
        "ebay_description": description,
        "ebay_item_specifics": item_specifics,
        "ebay_category_id": item.get("category_id"),
    }

    upd = supabase.table("items").update(update).eq("id", item_id).execute()
    if not upd.data:
        raise HTTPException(status_code=404, detail="Item not found")

    supabase.table("item_events").insert(
        {"item_id": item_id, "event_type": "listing_generated", "payload": update}
    ).execute()

    return {
        "item_id": item_id,
        "ebay_title": title,
        "ebay_description": description,
        "ebay_item_specifics": item_specifics,
        "suggested_price": suggested_price,
    }

