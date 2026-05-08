from pydantic import BaseModel, Field


class PromptRequest(BaseModel):
    prompt: str


class Base64FileRequest(BaseModel):
    filename: str = Field(..., description="Original file name including extension")
    content_base64: str = Field(..., description="Base64 encoded file bytes")


class OCRDocumentRequest(Base64FileRequest):
    pass


class BulkPurchaseOrderUploadRequest(Base64FileRequest):
    dryRun: bool = Field(False, description="When true, validate and preview without creating POs in SAP")
