import logging

from app.db.purchase_return_db import save_purchase_return
from app.operations.sap_client import SAPClient


logger = logging.getLogger(__name__)


class PurchaseReturnRepository:
    def __init__(self):
        self.client = SAPClient()

    def create_purchase_return(self, payload: dict):
        response = self.client.create_purchase_return(payload)
        if response and "DocEntry" in response:
            line_items = response.get("DocumentLines") or payload.get("DocumentLines", [])
            save_purchase_return({**payload, **response}, line_items)
            logger.info("Purchase return saved to database: %s", response.get("DocNum"))
        return response

    def cancel_purchase_return(self, doc_entry: int):
        return self.client.cancel_purchase_return(doc_entry)

    def close_purchase_return(self, doc_entry: int):
        return self.client.close_purchase_return(doc_entry)

    def reopen_purchase_return(self, doc_entry: int):
        return self.client.reopen_purchase_return(doc_entry)

    def update_purchase_return(self, doc_entry: int, payload: dict):
        return self.client.update_purchase_return(doc_entry, payload)

    def get_vendor(self, card_code: str):
        return self.client.get_vendor(card_code)
