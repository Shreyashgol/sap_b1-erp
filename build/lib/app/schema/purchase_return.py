from typing import Optional

from pydantic import BaseModel


class PromptRequest(BaseModel):
    prompt: str


class OCRDocumentRequest(BaseModel):
    filename: str
    content_base64: str


class BulkPurchaseReturnUploadRequest(BaseModel):
    filename: str
    content_base64: str
    dryRun: bool = False
