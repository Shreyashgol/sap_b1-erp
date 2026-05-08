from typing import Optional

from pydantic import BaseModel, Field


class PurchaseTeamIntent(BaseModel):
    prompt: str
    action: Optional[str] = Field(None, description="create | cancel | close | update | fetch")
    documentType: Optional[str] = Field(None, description="purchase_order | ap_invoice | purchase_return")
    docEntry: Optional[int] = None
    cardCode: Optional[str] = None
