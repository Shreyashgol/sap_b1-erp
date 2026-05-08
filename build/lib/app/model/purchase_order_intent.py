from typing import List, Optional

from pydantic import BaseModel, Field


class PurchaseOrderItem(BaseModel):
    itemCode: str = Field(..., description="SAP ItemCode")
    quantity: int = Field(..., gt=0, description="Quantity of the item")
    unitPrice: Optional[float] = Field(None, description="Unit price per item")
    taxCode: Optional[str] = Field(None, description="Tax code")


class PurchaseOrderIntent(BaseModel):
    action: str = Field(..., description="create | cancel | close | update | fetch")
    cardCode: Optional[str] = None
    docDate: Optional[str] = None
    docDueDate: Optional[str] = None
    taxDate: Optional[str] = None
    items: Optional[List[PurchaseOrderItem]] = None
    docEntry: Optional[int] = None
    mobileNumber: Optional[str] = None
    fetchQuery: Optional[str] = None
