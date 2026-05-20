import warnings
from typing import Any

import requests

from app.config import SAP_BASE_URL, SAP_COMPANYDB, SAP_PASSWORD, SAP_USERNAME

warnings.filterwarnings("ignore", message="Unverified HTTPS request")


class SAPClient:
    def __init__(self):
        self.session_id: str | None = None

    def login(self):
        response = requests.post(
            f"{SAP_BASE_URL}/Login",
            json={
                "UserName": SAP_USERNAME,
                "Password": SAP_PASSWORD,
                "CompanyDB": SAP_COMPANYDB,
            },
            verify=False,
            timeout=30,
        )
        if response.status_code != 200:
            raise Exception(f"SAP Login failed (HTTP {response.status_code}): {response.text}")

        self.session_id = response.json().get("SessionId")
        if not self.session_id:
            raise Exception("SAP Login failed: response did not include SessionId")

    def _headers(self):
        if not self.session_id:
            self.login()
        return {"Cookie": f"B1SESSION={self.session_id}"}

    def _request(self, method: str, path: str, *, expected: tuple[int, ...], json: dict | None = None) -> Any:
        response = requests.request(
            method,
            f"{SAP_BASE_URL}{path}",
            json=json,
            headers=self._headers(),
            verify=False,
            timeout=30,
        )
        if response.status_code not in expected:
            raise Exception(f"SAP request failed {method} {path} (HTTP {response.status_code}): {response.text}")
        if response.status_code == 204 or not response.content:
            return {}
        return response.json()

    def create_purchase_order(self, po_data: dict):
        return self._request("POST", "/PurchaseOrders", json=po_data, expected=(201,))

    def cancel_purchase_order(self, doc_entry: int):
        self._request("POST", f"/PurchaseOrders({doc_entry})/Cancel", expected=(200, 204))
        return {"DocEntry": doc_entry, "status": "cancelled"}

    def close_purchase_order(self, doc_entry: int):
        self._request("POST", f"/PurchaseOrders({doc_entry})/Close", expected=(200, 204))
        return {"DocEntry": doc_entry, "status": "closed"}

    def update_purchase_order(self, doc_entry: int, po_data: dict):
        self._request("PATCH", f"/PurchaseOrders({doc_entry})", json=po_data, expected=(204,))
        return {"DocEntry": doc_entry}

    def get_vendor(self, card_code: str):
        try:
            data = self._request("GET", f"/BusinessPartners('{card_code}')", expected=(200,))
        except Exception:
            return None
        return data if data.get("CardType") == "S" else None

    def get_item(self, item_code: str):
        try:
            return self._request("GET", f"/Items('{item_code}')", expected=(200,))
        except Exception:
            return None

    def create_ap_invoice(self, payload: dict):
        return self._request("POST", "/PurchaseInvoices", json=payload, expected=(201,))

    def update_ap_invoice(self, doc_entry: int, payload: dict):
        self._request("PATCH", f"/PurchaseInvoices({doc_entry})", json=payload, expected=(204,))
        return {"DocEntry": doc_entry}

    def cancel_ap_invoice(self, doc_entry: int):
        self._request("POST", f"/PurchaseInvoices({doc_entry})/Cancel", expected=(200, 204))
        return {"DocEntry": doc_entry, "status": "cancelled"}

    def close_ap_invoice(self, doc_entry: int):
        self._request("POST", f"/PurchaseInvoices({doc_entry})/Close", expected=(200, 204))
        return {"DocEntry": doc_entry, "status": "closed"}

    def create_purchase_return(self, payload: dict):
        return self._request("POST", "/PurchaseReturns", json=payload, expected=(201,))

    def update_purchase_return(self, doc_entry: int, payload: dict):
        self._request("PATCH", f"/PurchaseReturns({doc_entry})", json=payload, expected=(204,))
        return {"DocEntry": doc_entry}

    def cancel_purchase_return(self, doc_entry: int):
        self._request("POST", f"/PurchaseReturns({doc_entry})/Cancel", expected=(200, 204))
        return {"DocEntry": doc_entry, "status": "cancelled"}

    def close_purchase_return(self, doc_entry: int):
        self._request("POST", f"/PurchaseReturns({doc_entry})/Close", expected=(200, 204))
        return {"DocEntry": doc_entry, "status": "closed"}
