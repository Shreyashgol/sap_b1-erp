import requests
import warnings

from app.config import SAP_BASE_URL, SAP_COMPANYDB, SAP_PASSWORD, SAP_USERNAME

warnings.filterwarnings("ignore", message="Unverified HTTPS request")


class SAPClient:
    def __init__(self):
        self.session_id = None

    def login(self):
        payload = {
            "UserName": SAP_USERNAME,
            "Password": SAP_PASSWORD,
            "CompanyDB": SAP_COMPANYDB,
        }
        response = requests.post(f"{SAP_BASE_URL}/Login", json=payload, verify=False)
        if response.status_code == 200:
            self.session_id = response.json().get("SessionId")
            return
        raise Exception(f"SAP Login failed: {response.text}")

    def _headers(self):
        if not self.session_id:
            self.login()
        return {"Cookie": f"B1SESSION={self.session_id}"}

    def create_purchase_order(self, po_data: dict):
        response = requests.post(
            f"{SAP_BASE_URL}/PurchaseOrders",
            json=po_data,
            headers=self._headers(),
            verify=False,
        )
        if response.status_code == 201:
            return response.json()
        raise Exception(f"Purchase Order creation failed: {response.text}")

    def cancel_purchase_order(self, doc_entry: int):
        response = requests.post(
            f"{SAP_BASE_URL}/PurchaseOrders({doc_entry})/Cancel",
            headers=self._headers(),
            verify=False,
        )
        if response.status_code in (200, 204):
            return {"DocEntry": doc_entry, "status": "cancelled"}
        raise Exception(f"Purchase Order cancel failed (HTTP {response.status_code}): {response.text}")

    def close_purchase_order(self, doc_entry: int):
        response = requests.post(
            f"{SAP_BASE_URL}/PurchaseOrders({doc_entry})/Close",
            headers=self._headers(),
            verify=False,
        )
        if response.status_code in (200, 204):
            return {"DocEntry": doc_entry, "status": "closed"}
        raise Exception(f"Purchase Order close failed (HTTP {response.status_code}): {response.text}")

    def update_purchase_order(self, doc_entry: int, po_data: dict):
        response = requests.patch(
            f"{SAP_BASE_URL}/PurchaseOrders({doc_entry})",
            json=po_data,
            headers=self._headers(),
            verify=False,
        )
        if response.status_code == 204:
            return {"DocEntry": doc_entry}
        raise Exception(f"Purchase Order update failed: {response.text}")

    def get_vendor(self, card_code: str):
        response = requests.get(
            f"{SAP_BASE_URL}/BusinessPartners('{card_code}')",
            headers=self._headers(),
            verify=False,
        )
        if response.status_code == 200:
            data = response.json()
            if data.get("CardType") == "S":
                return data
        return None

    def get_item(self, item_code: str):
        response = requests.get(
            f"{SAP_BASE_URL}/Items('{item_code}')",
            headers=self._headers(),
            verify=False,
        )
        return response.json() if response.status_code == 200 else None
