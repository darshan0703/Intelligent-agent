from pydantic import BaseModel
from typing import Optional

class OrderIntent(BaseModel):
    action: str  # add_item | show_menu | checkout | unknown
    item_name: Optional[str] = None