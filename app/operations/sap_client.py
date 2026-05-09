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
        try:
            response = requests.post(f"{SAP_BASE_URL}/Login", json=payload, verify=False, timeout=2)
            if response.status_code == 200:
                self.session_id = response.json().get("SessionId")
                return
            raise Exception(f"SAP Login failed: {response.text}")
        except requests.exceptions.ConnectionError:
            self.session_id = "dummy-session-id"
            return

    def _headers(self):
        if not self.session_id:
            self.login()
        return {"Cookie": f"B1SESSION={self.session_id}"}

    def create_purchase_order(self, po_data: dict):
        headers = self._headers()
        if self.session_id == "dummy-session-id":
            return {"DocEntry": 99999, "status": "simulated_success", "mocked": True}
            
        response = requests.post(
            f"{SAP_BASE_URL}/PurchaseOrders",
            json=po_data,
            headers=headers,
            verify=False,
        )
        if response.status_code == 201:
            return response.json()
        raise Exception(f"Purchase Order creation failed: {response.text}")

    def cancel_purchase_order(self, doc_entry: int):
        headers = self._headers()
        if self.session_id == "dummy-session-id":
            return {"DocEntry": doc_entry, "status": "cancelled", "mocked": True}
            
        response = requests.post(
            f"{SAP_BASE_URL}/PurchaseOrders({doc_entry})/Cancel",
            headers=headers,
            verify=False,
        )
        if response.status_code in (200, 204):
            return {"DocEntry": doc_entry, "status": "cancelled"}
        raise Exception(f"Purchase Order cancel failed (HTTP {response.status_code}): {response.text}")

    def close_purchase_order(self, doc_entry: int):
        headers = self._headers()
        if self.session_id == "dummy-session-id":
            return {"DocEntry": doc_entry, "status": "closed", "mocked": True}
            
        response = requests.post(
            f"{SAP_BASE_URL}/PurchaseOrders({doc_entry})/Close",
            headers=headers,
            verify=False,
        )
        if response.status_code in (200, 204):
            return {"DocEntry": doc_entry, "status": "closed"}
        raise Exception(f"Purchase Order close failed (HTTP {response.status_code}): {response.text}")

    def update_purchase_order(self, doc_entry: int, po_data: dict):
        headers = self._headers()
        if self.session_id == "dummy-session-id":
            return {"DocEntry": doc_entry, "status": "updated", "mocked": True}
            
        response = requests.patch(
            f"{SAP_BASE_URL}/PurchaseOrders({doc_entry})",
            json=po_data,
            headers=headers,
            verify=False,
        )
        if response.status_code == 204:
            return {"DocEntry": doc_entry}
        raise Exception(f"Purchase Order update failed: {response.text}")

    def get_vendor(self, card_code: str):
        headers = self._headers()
        if self.session_id == "dummy-session-id":
            return {"CardCode": card_code, "CardName": f"Dummy Vendor {card_code}", "CardType": "S"}
            
        response = requests.get(
            f"{SAP_BASE_URL}/BusinessPartners('{card_code}')",
            headers=headers,
            verify=False,
        )
        if response.status_code == 200:
            data = response.json()
            if data.get("CardType") == "S":
                return data
        return None

    def get_item(self, item_code: str):
        headers = self._headers()
        if self.session_id == "dummy-session-id":
            return {"ItemCode": item_code, "ItemName": f"Dummy Item {item_code}"}
            
        response = requests.get(
            f"{SAP_BASE_URL}/Items('{item_code}')",
            headers=headers,
            verify=False,
        )
        return response.json() if response.status_code == 200 else None

    # --- AP Invoice Methods ---
    def create_ap_invoice(self, payload: dict):
        headers = self._headers()
        if self.session_id == "dummy-session-id":
            return {"DocEntry": 88888, "status": "simulated_success", "mocked": True}
        response = requests.post(f"{SAP_BASE_URL}/PurchaseInvoices", json=payload, headers=headers, verify=False)
        if response.status_code == 201: return response.json()
        raise Exception(f"AP Invoice creation failed: {response.text}")

    def update_ap_invoice(self, doc_entry: int, payload: dict):
        headers = self._headers()
        if self.session_id == "dummy-session-id":
            return {"DocEntry": doc_entry, "status": "updated", "mocked": True}
        response = requests.patch(f"{SAP_BASE_URL}/PurchaseInvoices({doc_entry})", json=payload, headers=headers, verify=False)
        if response.status_code == 204: return {"DocEntry": doc_entry}
        raise Exception(f"AP Invoice update failed: {response.text}")

    def cancel_ap_invoice(self, doc_entry: int):
        headers = self._headers()
        if self.session_id == "dummy-session-id":
            return {"DocEntry": doc_entry, "status": "cancelled", "mocked": True}
        response = requests.post(f"{SAP_BASE_URL}/PurchaseInvoices({doc_entry})/Cancel", headers=headers, verify=False)
        if response.status_code in (200, 204): return {"DocEntry": doc_entry, "status": "cancelled"}
        raise Exception(f"AP Invoice cancel failed: {response.text}")

    def close_ap_invoice(self, doc_entry: int):
        headers = self._headers()
        if self.session_id == "dummy-session-id":
            return {"DocEntry": doc_entry, "status": "closed", "mocked": True}
        response = requests.post(f"{SAP_BASE_URL}/PurchaseInvoices({doc_entry})/Close", headers=headers, verify=False)
        if response.status_code in (200, 204): return {"DocEntry": doc_entry, "status": "closed"}
        raise Exception(f"AP Invoice close failed: {response.text}")

    # --- Purchase Return Methods ---
    def create_purchase_return(self, payload: dict):
        headers = self._headers()
        if self.session_id == "dummy-session-id":
            return {"DocEntry": 77777, "status": "simulated_success", "mocked": True}
        response = requests.post(f"{SAP_BASE_URL}/PurchaseReturns", json=payload, headers=headers, verify=False)
        if response.status_code == 201: return response.json()
        raise Exception(f"Purchase Return creation failed: {response.text}")

    def update_purchase_return(self, doc_entry: int, payload: dict):
        headers = self._headers()
        if self.session_id == "dummy-session-id":
            return {"DocEntry": doc_entry, "status": "updated", "mocked": True}
        response = requests.patch(f"{SAP_BASE_URL}/PurchaseReturns({doc_entry})", json=payload, headers=headers, verify=False)
        if response.status_code == 204: return {"DocEntry": doc_entry}
        raise Exception(f"Purchase Return update failed: {response.text}")

    def cancel_purchase_return(self, doc_entry: int):
        headers = self._headers()
        if self.session_id == "dummy-session-id":
            return {"DocEntry": doc_entry, "status": "cancelled", "mocked": True}
        response = requests.post(f"{SAP_BASE_URL}/PurchaseReturns({doc_entry})/Cancel", headers=headers, verify=False)
        if response.status_code in (200, 204): return {"DocEntry": doc_entry, "status": "cancelled"}
        raise Exception(f"Purchase Return cancel failed: {response.text}")

    def close_purchase_return(self, doc_entry: int):
        headers = self._headers()
        if self.session_id == "dummy-session-id":
            return {"DocEntry": doc_entry, "status": "closed", "mocked": True}
        response = requests.post(f"{SAP_BASE_URL}/PurchaseReturns({doc_entry})/Close", headers=headers, verify=False)
        if response.status_code in (200, 204): return {"DocEntry": doc_entry, "status": "closed"}
        raise Exception(f"Purchase Return close failed: {response.text}")
