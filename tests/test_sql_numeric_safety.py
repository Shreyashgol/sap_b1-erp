import unittest
from decimal import Decimal

from app.operations.sql_numeric_safety import make_numeric_select_json_safe, normalize_result_rows


class SqlNumericSafetyTest(unittest.TestCase):
    def test_casts_sales_order_item_level_numeric_columns(self):
        sql = (
            'SELECT T0."DocEntry", T0."DocTotal", T1."Quantity", T1."Price", T1."LineTotal", '
            'T1."ShipDate" FROM ORDR T0 JOIN RDR1 T1 ON T1."DocEntry" = T0."DocEntry"'
        )

        safe_sql = make_numeric_select_json_safe(sql)

        self.assertIn('CAST(T0."DocTotal" AS DOUBLE) AS "DocTotal"', safe_sql)
        self.assertIn('CAST(T1."Quantity" AS DOUBLE) AS "Quantity"', safe_sql)
        self.assertIn('CAST(T1."Price" AS DOUBLE) AS "Price"', safe_sql)
        self.assertIn('CAST(T1."LineTotal" AS DOUBLE) AS "LineTotal"', safe_sql)
        self.assertIn('T1."ShipDate"', safe_sql)

    def test_casts_purchase_ap_invoice_numeric_columns(self):
        sql = (
            'SELECT "DocNum", "DocTotal", "PaidToDate", '
            '("DocTotal" - IFNULL("PaidToDate", 0)) AS "pending_amount" FROM opch'
        )

        safe_sql = make_numeric_select_json_safe(sql)

        self.assertIn('CAST("DocTotal" AS DOUBLE) AS "DocTotal"', safe_sql)
        self.assertIn('CAST("PaidToDate" AS DOUBLE) AS "PaidToDate"', safe_sql)
        self.assertIn('CAST(("DocTotal" - IFNULL("PaidToDate", 0)) AS DOUBLE) AS "pending_amount"', safe_sql)

    def test_casts_aggregate_numeric_aliases(self):
        sql = (
            'SELECT T0."CardCode", SUM(T0."DocTotal") AS "total_order_value", '
            'COUNT(*) AS "order_count" FROM ORDR T0 GROUP BY T0."CardCode"'
        )

        safe_sql = make_numeric_select_json_safe(sql)

        self.assertIn('CAST(SUM(T0."DocTotal") AS DOUBLE) AS "total_order_value"', safe_sql)
        self.assertIn('COUNT(*) AS "order_count"', safe_sql)

    def test_does_not_cast_date_aggregates(self):
        sql = 'SELECT MAX(T0."DocDate") AS "latest_date" FROM ORDR T0'

        self.assertEqual(make_numeric_select_json_safe(sql), sql)

    def test_does_not_cast_due_date_columns(self):
        sql = (
            'SELECT T0."DocNum", T0."DocDueDate", T1."OpenQty", T1."LineTotal" '
            'FROM ORDR T0 JOIN RDR1 T1 ON T1."DocEntry" = T0."DocEntry"'
        )

        safe_sql = make_numeric_select_json_safe(sql)

        self.assertIn('T0."DocDueDate"', safe_sql)
        self.assertNotIn('CAST(T0."DocDueDate" AS DOUBLE)', safe_sql)
        self.assertIn('CAST(T1."OpenQty" AS DOUBLE) AS "OpenQty"', safe_sql)
        self.assertIn('CAST(T1."LineTotal" AS DOUBLE) AS "LineTotal"', safe_sql)

    def test_is_idempotent_for_existing_casts(self):
        sql = 'SELECT CAST(T1."Quantity" AS DOUBLE) AS "Quantity", T1."ItemCode" FROM RDR1 T1'

        self.assertEqual(make_numeric_select_json_safe(sql), sql)

    def test_normalizes_decimal_and_wrapped_values(self):
        rows = [
            {
                "DocTotal": Decimal("125.50"),
                "Quantity": {"value": "3.000000"},
                "Price": {"VALUE": 79999},
                "LineTotal": {"nested": {"amount": Decimal("42.00")}},
            }
        ]

        normalized = normalize_result_rows(rows)

        self.assertEqual(normalized[0]["DocTotal"], 125.5)
        self.assertEqual(normalized[0]["Quantity"], "3.000000")
        self.assertEqual(normalized[0]["Price"], 79999)
        self.assertEqual(normalized[0]["LineTotal"]["nested"], 42)


if __name__ == "__main__":
    unittest.main()
