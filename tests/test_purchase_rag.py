import unittest

from app.operations.purchase_rag import _LexicalPurchaseRagStore, _validate_generated_sql
from app.operations.sales_rag import _LexicalSalesRagStore
from app.operations.sales_rag import _validate_generated_sql as _validate_generated_sales_sql


class PurchaseRagSqlValidationTest(unittest.TestCase):
    def test_rejects_physical_balance_due_column(self):
        sql = 'SELECT "DocNum", "BalanceDue" FROM opch WHERE "DocStatus" = \'O\''

        with self.assertRaisesRegex(ValueError, "BalanceDue"):
            _validate_generated_sql(sql)

    def test_allows_derived_balance_due_alias(self):
        sql = (
            'SELECT "DocNum", ("DocTotal" - IFNULL("PaidToDate", 0)) AS "BalanceDue" '
            'FROM opch WHERE "DocStatus" = \'O\''
        )

        _validate_generated_sql(sql)


class PurchaseRagRetrievalTest(unittest.TestCase):
    def test_open_ap_invoice_pending_amount_retrieves_safe_example(self):
        store = _LexicalPurchaseRagStore()
        retrieval = store.retrieve("Show me all open AP invoices with pending amounts", top_k_schema=3, top_k_queries=2)

        schema_tables = [item["metadata"].get("table_name") for item in retrieval["schema"]]
        example_sql = "\n".join(item["metadata"].get("sql", "") for item in retrieval["queries"])

        self.assertIn("opch", schema_tables)
        self.assertIn('("DocTotal" - IFNULL("PaidToDate", 0))', example_sql)
        self.assertNotIn('COALESCE("BalanceDue"', example_sql)

    def test_ap_invoice_po_variance_retrieves_base_document_example(self):
        store = _LexicalPurchaseRagStore()
        retrieval = store.retrieve(
            "Find AP invoices where invoice amount exceeds PO amount by more than 5%",
            top_k_schema=5,
            top_k_queries=3,
        )

        example_sql = "\n".join(item["metadata"].get("sql", "") for item in retrieval["queries"])

        self.assertIn('p1."BaseType" = 22', example_sql)
        self.assertIn('p1."BaseEntry"', example_sql)
        self.assertIn('p1."BaseLine"', example_sql)
        self.assertIn('"variance_percent"', example_sql)

    def test_ap_invoice_aging_retrieves_bucket_example(self):
        store = _LexicalPurchaseRagStore()
        retrieval = store.retrieve("Generate AP invoice aging by vendor", top_k_schema=3, top_k_queries=3)

        example_sql = "\n".join(item["metadata"].get("sql", "") for item in retrieval["queries"])

        self.assertIn("DAYS_BETWEEN", example_sql)
        self.assertIn('"days_over_90"', example_sql)
        self.assertIn('("DocTotal" - IFNULL("PaidToDate", 0))', example_sql)


class SalesRagSqlValidationTest(unittest.TestCase):
    def test_rejects_physical_balance_due_column(self):
        sql = 'SELECT T0."DocNum", T0."BalanceDue" FROM OINV T0 WHERE T0."DocStatus" = \'O\''

        with self.assertRaisesRegex(ValueError, "BalanceDue"):
            _validate_generated_sales_sql(sql)

    def test_allows_derived_balance_due_alias(self):
        sql = (
            'SELECT T0."DocNum", (T0."DocTotal" - IFNULL(T0."PaidToDate", 0)) AS "BalanceDue" '
            'FROM OINV T0 WHERE T0."DocStatus" = \'O\''
        )

        _validate_generated_sales_sql(sql)

    def test_top_sales_order_item_details_retrieves_casted_numeric_example(self):
        store = _LexicalSalesRagStore()
        retrieval = store.retrieve(
            "Show me the top sales order with item-level quantity, price and delivery details",
            top_k_schema=4,
            top_k_queries=4,
        )

        example_sql = "\n".join(item["metadata"].get("sql", "") for item in retrieval["queries"])

        self.assertIn('CAST(T0."DocTotal" AS DOUBLE) AS "DocTotal"', example_sql)
        self.assertIn('CAST(T1."Quantity" AS DOUBLE) AS "Quantity"', example_sql)
        self.assertIn('CAST(T1."Price" AS DOUBLE) AS "Price"', example_sql)
        self.assertIn('CAST(T1."LineTotal" AS DOUBLE) AS "LineTotal"', example_sql)

    def test_open_sales_orders_for_product_names_retrieves_text_match_example(self):
        store = _LexicalSalesRagStore()
        retrieval = store.retrieve(
            "Show me the open sales orders for OPPO F27 PRO+ and iPhone 16 Pro Max",
            top_k_schema=5,
            top_k_queries=3,
        )

        example_sql = "\n".join(item["metadata"].get("sql", "") for item in retrieval["queries"])

        self.assertIn("LEFT JOIN OITM", example_sql)
        self.assertIn('LOWER(IFNULL(T2."ItemName", \'\')) LIKE \'%oppo f27 pro+%\'', example_sql)
        self.assertIn('LOWER(IFNULL(T1."Dscription", \'\')) LIKE \'%iphone 16 pro max%\'', example_sql)
        self.assertNotIn('"DocNum" = \'OPPO F27 PRO+\'', example_sql)

    def test_ar_invoice_sales_order_variance_retrieves_base_document_example(self):
        store = _LexicalSalesRagStore()
        retrieval = store.retrieve(
            "List AR invoices where billing amount differs from sales order amount",
            top_k_schema=5,
            top_k_queries=3,
        )

        example_sql = "\n".join(item["metadata"].get("sql", "") for item in retrieval["queries"])

        self.assertIn('T1."BaseType" = 17', example_sql)
        self.assertIn('T1."BaseEntry"', example_sql)
        self.assertIn('T1."BaseLine"', example_sql)
        self.assertIn('"variance_amount"', example_sql)

    def test_ar_invoice_aging_retrieves_bucket_example(self):
        store = _LexicalSalesRagStore()
        retrieval = store.retrieve("Show AR invoice aging by customer", top_k_schema=3, top_k_queries=3)

        example_sql = "\n".join(item["metadata"].get("sql", "") for item in retrieval["queries"])

        self.assertIn("DAYS_BETWEEN", example_sql)
        self.assertIn('"days_over_90"', example_sql)
        self.assertIn('(T0."DocTotal" - IFNULL(T0."PaidToDate", 0))', example_sql)


if __name__ == "__main__":
    unittest.main()
