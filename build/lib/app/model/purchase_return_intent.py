from typing import List, Optional

from pydantic import BaseModel, Field


class PurchaseReturnItem(BaseModel):
    itemCode: str = Field(..., description="SAP ItemCode")
    quantity: int = Field(..., gt=0, description="Quantity of the item")
    unitPrice: Optional[float] = Field(None, description="Unit price per item")
    taxCode: Optional[str] = Field(None, description="Tax code")
    baseEntry: Optional[int] = Field(None, description="Base AP invoice or goods receipt DocEntry")
    baseLine: Optional[int] = Field(None, description="Base document line number")


class PurchaseReturnIntent(BaseModel):
    action: str = Field(..., description="create | cancel | close | reopen | update | fetch")
    cardCode: Optional[str] = None
    docDate: Optional[str] = None
    docDueDate: Optional[str] = None
    taxDate: Optional[str] = None
    items: Optional[List[PurchaseReturnItem]] = None
    docEntry: Optional[int] = None
    fetchQuery: Optional[str] = None
    comments: Optional[str] = None
