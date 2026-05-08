from typing import Any, Dict, Optional

from pydantic import BaseModel


class PurchaseOrderActionResponse(BaseModel):
    status: str
    message: str
    docEntry: Optional[int] = None
    data: Optional[Dict[str, Any]] = None


class APInvoiceActionResponse(BaseModel):
    status: str
    message: str
    docEntry: Optional[int] = None
    data: Optional[Dict[str, Any]] = None


class PurchaseReturnActionResponse(BaseModel):
    status: str
    message: str
    docEntry: Optional[int] = None
    data: Optional[Dict[str, Any]] = None


class PurchaseTeamRoutingResponse(BaseModel):
    status: str
    message: str
    data: Dict[str, Any]

