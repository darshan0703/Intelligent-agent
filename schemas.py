from pydantic import BaseModel
from typing import Optional

class OrderIntent(BaseModel):
    action: str
    item_name: Optional[str] = None
    category: Optional[str] = None