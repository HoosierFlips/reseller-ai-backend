from pydantic import BaseModel, Field
from typing import Any, Optional, Dict

class ItemCreate(BaseModel):
    title_guess: Optional[str] = None
    brand: Optional[str] = None
    model: Optional[str] = None
    category_guess: Optional[str] = None
    description_short: Optional[str] = None
    materials: Optional[str] = None
    color: Optional[str] = None
    markings: Optional[str] = None
    upc: Optional[str] = None
    purchase_price: Optional[float] = None
    source_location: Optional[str] = None

class ItemUpdate(BaseModel):
    status: Optional[str] = None
    purchase_price: Optional[float] = None
    fast_sale_price: Optional[float] = None
    typical_price: Optional[float] = None
    premium_price: Optional[float] = None
    comps_json: Optional[Dict[str, Any]] = None
    rarity_score: Optional[int] = None
    identification_confidence: Optional[float] = None
    ebay_title: Optional[str] = None
    ebay_description: Optional[str] = None
    ebay_item_specifics: Optional[Dict[str, Any]] = None
    ebay_category_id: Optional[str] = None

class CompsRequest(BaseModel):
    query: str = Field(..., description="Search query")
    limit: int = 25

class CategorySuggestRequest(BaseModel):
    query: str

class AspectsRequest(BaseModel):
    category_tree_id: str
    category_id: str

class ItemCategorySetRequest(BaseModel):
    category_tree_id: str
    category_id: str
    required_aspects: Dict[str, str]
