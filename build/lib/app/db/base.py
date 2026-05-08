from app.db import ap_invoice_db, purchase_order_db, purchase_return_db


def init_db_pool():
    purchase_order_db.init_db_pool()
    ap_invoice_db.init_db_pool()
    purchase_return_db.init_db_pool()


def get_db_session():
    return purchase_order_db.get_db_session()

