from typing import List, Optional

from pydantic import BaseModel, Field


class APInvoiceItem(BaseModel):
    itemCode: str = Field(..., description="SAP ItemCode")
    quantity: int = Field(..., gt=0, description="Quantity of the item")
    unitPrice: Optional[float] = Field(None, description="Unit price per item")
    taxCode: Optional[str] = Field(None, description="Tax code")


class APInvoiceIntent(BaseModel):
    action: str = Field(..., description="create | cancel | close | reopen | update | fetch")
    cardCode: Optional[str] = None
    items: Optional[List[APInvoiceItem]] = None
    docEntry: Optional[int] = None
    fetchQuery: Optional[str] = None
