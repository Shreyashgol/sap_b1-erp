import logging

from app.db.ap_invoice_db import fetch_ap_invoice_by_doc_entry, fetch_ap_invoice_by_doc_num, fetch_ap_invoices_by_card_code, save_ap_invoice
from app.operations.sap_client import SAPClient

logger = logging.getLogger(__name__)


class APInvoiceRepository:
    def __init__(self):
        self.client = SAPClient()

    def create_ap_invoice(self, payload: dict):
        response = self.client.create_ap_invoice(payload)

        if response and "DocEntry" in response:
            invoice_data = {**payload, **response}
            line_items = response.get("DocumentLines") or payload.get("DocumentLines", [])
            save_ap_invoice(invoice_data, line_items)
            logger.info("AP invoice saved to database: %s", response.get("DocNum"))

        return response

    def fetch_ap_invoice(self, doc_entry: int):
        return self.client.get_ap_invoice(doc_entry)

    def cancel_ap_invoice(self, doc_entry: int):
        return self.client.cancel_ap_invoice(doc_entry)

    def close_ap_invoice(self, doc_entry: int):
        return self.client.close_ap_invoice(doc_entry)

    def reopen_ap_invoice(self, doc_entry: int):
        return self.client.reopen_ap_invoice(doc_entry)

    def update_ap_invoice(self, doc_entry: int, payload: dict):
        return self.client.update_ap_invoice(doc_entry, payload)

    def get_vendor(self, card_code: str):
        return self.client.get_vendor(card_code)

    def get_item(self, item_code: str):
        return self.client.get_item(item_code)

    def get_ap_invoice_from_db(self, doc_num: int):
        return fetch_ap_invoice_by_doc_num(doc_num)

    def get_ap_invoice_by_doc_entry(self, doc_entry: int):
        return fetch_ap_invoice_by_doc_entry(doc_entry)

    def get_ap_invoices_by_card_code(self, card_code: str, limit: int = 20):
        return fetch_ap_invoices_by_card_code(card_code, limit=limit)
