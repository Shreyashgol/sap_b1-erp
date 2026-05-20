import logging

from fastapi import FastAPI

from app.api import ap_invoices, purchase_orders, purchase_returns, sales
from app.config import APP_NAME
from app.db.base import init_db_pool


logging.basicConfig(level=logging.INFO)

app = FastAPI(title=APP_NAME)

app.include_router(purchase_orders.router, prefix="/purchase-orders", tags=["Purchase Orders"])
app.include_router(ap_invoices.router, prefix="/ap-invoices", tags=["AP Invoices"])
app.include_router(purchase_returns.router, prefix="/purchase-returns", tags=["Purchase Returns"])
app.include_router(sales.router, prefix="/sales", tags=["Sales"])


@app.on_event("startup")
async def startup_event():
    try:
        init_db_pool()
        print("Database pools initialized successfully.")
    except Exception as e:
        print(f"Failed to initialize database pools (is .env configured?): {e}")


@app.get("/")
def root():
    return {"message": f"{APP_NAME} is running"}
