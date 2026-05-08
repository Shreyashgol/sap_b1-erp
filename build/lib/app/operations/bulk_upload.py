import base64
import csv
import io
from collections import OrderedDict
from datetime import datetime, timedelta
from pathlib import Path
from zipfile import ZipFile
import xml.etree.ElementTree as ET


DATE_HEADERS = {"docdate", "docduedate", "taxdate", "orderdate", "duedate"}
HEADER_ALIASES = {
    "orderid": "order_id",
    "groupid": "order_id",
    "batchid": "order_id",
    "vendorcode": "card_code",
    "vendor": "card_code",
    "cardcode": "card_code",
    "docdate": "doc_date",
    "orderdate": "doc_date",
    "docduedate": "doc_due_date",
    "duedate": "doc_due_date",
    "taxdate": "tax_date",
    "itemcode": "item_code",
    "item": "item_code",
    "quantity": "quantity",
    "qty": "quantity",
    "unitprice": "unit_price",
    "price": "unit_price",
    "taxcode": "tax_code",
    "tax": "tax_code",
}
REQUIRED_HEADERS = {"card_code", "item_code", "quantity"}


def _decode_base64(content_base64: str) -> bytes:
    try:
        return base64.b64decode(content_base64, validate=True)
    except Exception as exc:
        raise ValueError("Invalid base64 file content") from exc


def _excel_serial_to_iso(value: float) -> str:
    excel_epoch = datetime(1899, 12, 30)
    converted = excel_epoch + timedelta(days=float(value))
    return converted.date().isoformat()


def _normalise_header(value: str) -> str:
    cleaned = "".join(ch for ch in value.lower() if ch.isalnum())
    return HEADER_ALIASES.get(cleaned, cleaned)


def _parse_possible_date(header: str, value):
    if value in (None, ""):
        return None

    if header not in DATE_HEADERS:
        return value

    if isinstance(value, (int, float)):
        return _excel_serial_to_iso(value)

    text = str(value).strip()
    for date_format in ("%Y-%m-%d", "%d-%m-%Y", "%m/%d/%Y", "%d/%m/%Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(text, date_format).date().isoformat()
        except ValueError:
            continue
    return text


def _parse_number(value, field_name: str) -> float:
    if value in (None, ""):
        if field_name == "quantity":
            raise ValueError("Quantity is required for each line item")
        return 0.0

    try:
        return float(str(value).strip())
    except ValueError as exc:
        raise ValueError(f"Invalid numeric value for {field_name}: {value}") from exc


def _column_index_from_ref(cell_ref: str) -> int:
    letters = "".join(ch for ch in cell_ref if ch.isalpha())
    index = 0
    for char in letters:
        index = index * 26 + (ord(char.upper()) - ord("A") + 1)
    return max(index - 1, 0)


def _get_shared_strings(workbook_zip: ZipFile) -> list[str]:
    if "xl/sharedStrings.xml" not in workbook_zip.namelist():
        return []

    namespace = {"main": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    root = ET.fromstring(workbook_zip.read("xl/sharedStrings.xml"))
    shared_strings = []
    for item in root.findall("main:si", namespace):
        text_chunks = [node.text or "" for node in item.findall(".//main:t", namespace)]
        shared_strings.append("".join(text_chunks))
    return shared_strings


def _get_first_sheet_path(workbook_zip: ZipFile) -> str:
    workbook_root = ET.fromstring(workbook_zip.read("xl/workbook.xml"))
    rels_root = ET.fromstring(workbook_zip.read("xl/_rels/workbook.xml.rels"))

    workbook_ns = {"main": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    rels_ns = {"rel": "http://schemas.openxmlformats.org/package/2006/relationships"}

    first_sheet = workbook_root.find("main:sheets/main:sheet", workbook_ns)
    if first_sheet is None:
        raise ValueError("No worksheet found in Excel file")

    rel_id = first_sheet.attrib.get("{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id")
    for relationship in rels_root.findall("rel:Relationship", rels_ns):
        if relationship.attrib.get("Id") == rel_id:
            target = relationship.attrib["Target"].lstrip("/")
            if target.startswith("xl/"):
                return target
            return f"xl/{target}"

    raise ValueError("Unable to resolve worksheet path in Excel file")


def _cell_value(cell, shared_strings: list[str]):
    cell_type = cell.attrib.get("t")
    value_node = cell.find("{http://schemas.openxmlformats.org/spreadsheetml/2006/main}v")
    inline_text = cell.find("{http://schemas.openxmlformats.org/spreadsheetml/2006/main}is")

    if inline_text is not None:
        text_parts = [node.text or "" for node in inline_text.iterfind(".//{http://schemas.openxmlformats.org/spreadsheetml/2006/main}t")]
        return "".join(text_parts)

    if value_node is None:
        return ""

    raw_value = value_node.text or ""
    if cell_type == "s":
        return shared_strings[int(raw_value)]
    if cell_type == "b":
        return raw_value == "1"
    if cell_type == "str":
        return raw_value

    try:
        numeric_value = float(raw_value)
        if numeric_value.is_integer():
            return int(numeric_value)
        return numeric_value
    except ValueError:
        return raw_value


def _xlsx_rows(file_bytes: bytes) -> list[list]:
    namespace = {"main": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    with ZipFile(io.BytesIO(file_bytes)) as workbook_zip:
        shared_strings = _get_shared_strings(workbook_zip)
        sheet_path = _get_first_sheet_path(workbook_zip)
        sheet_root = ET.fromstring(workbook_zip.read(sheet_path))

    rows = []
    for row in sheet_root.findall(".//main:sheetData/main:row", namespace):
        parsed_cells = {}
        max_col = -1
        for cell in row.findall("main:c", namespace):
            cell_ref = cell.attrib.get("r", "")
            col_index = _column_index_from_ref(cell_ref)
            parsed_cells[col_index] = _cell_value(cell, shared_strings)
            max_col = max(max_col, col_index)

        if max_col < 0:
            continue

        row_values = ["" for _ in range(max_col + 1)]
        for col_index, value in parsed_cells.items():
            row_values[col_index] = value
        rows.append(row_values)

    return rows


def _csv_rows(file_bytes: bytes) -> list[list]:
    text = file_bytes.decode("utf-8-sig")
    return list(csv.reader(io.StringIO(text)))


def _table_rows(filename: str, file_bytes: bytes) -> list[dict]:
    suffix = Path(filename).suffix.lower()
    if suffix == ".csv":
        rows = _csv_rows(file_bytes)
    elif suffix == ".xlsx":
        rows = _xlsx_rows(file_bytes)
    else:
        raise ValueError("Unsupported upload type. Upload CSV or XLSX for bulk purchase orders.")

    if not rows:
        raise ValueError("The uploaded file is empty")

    headers = [_normalise_header(str(value).strip()) for value in rows[0]]
    missing_headers = sorted(REQUIRED_HEADERS - set(headers))
    if missing_headers:
        missing_display = ", ".join(missing_headers)
        raise ValueError(f"Missing required columns: {missing_display}")

    records = []
    for row_number, row in enumerate(rows[1:], start=2):
        if not any(str(cell).strip() for cell in row):
            continue

        padded_row = list(row) + [""] * max(0, len(headers) - len(row))
        record = {"source_row": row_number}
        for header, value in zip(headers, padded_row):
            if header == "":
                continue
            record[header] = _parse_possible_date(header, value)
        records.append(record)

    if not records:
        raise ValueError("No purchase order rows found in the upload")
    return records


def parse_bulk_purchase_orders(filename: str, content_base64: str) -> list[dict]:
    file_bytes = _decode_base64(content_base64)
    rows = _table_rows(filename, file_bytes)

    orders: OrderedDict[str, dict] = OrderedDict()
    for row_index, row in enumerate(rows, start=1):
        order_key = str(row.get("order_id") or f"ROW-{row_index}")
        card_code = str(row.get("card_code", "")).strip()
        item_code = str(row.get("item_code", "")).strip()
        quantity = _parse_number(row.get("quantity"), "quantity")
        unit_price = _parse_number(row.get("unit_price"), "unit_price") if row.get("unit_price") not in (None, "") else None
        tax_code = str(row.get("tax_code", "")).strip() or None

        if not card_code:
            raise ValueError(f"Vendor code is required on source row {row['source_row']}")
        if not item_code:
            raise ValueError(f"Item code is required on source row {row['source_row']}")

        if order_key not in orders:
            orders[order_key] = {
                "orderId": order_key,
                "sourceRows": [],
                "payload": {
                    "CardCode": card_code,
                    "DocDate": row.get("doc_date"),
                    "DocDueDate": row.get("doc_due_date"),
                    "TaxDate": row.get("tax_date") or row.get("doc_due_date"),
                    "DocumentLines": [],
                },
            }

        orders[order_key]["sourceRows"].append(row["source_row"])
        orders[order_key]["payload"]["DocumentLines"].append(
            {
                "ItemCode": item_code,
                "Quantity": quantity,
                "UnitPrice": unit_price,
                "TaxCode": tax_code,
            }
        )

    return list(orders.values())


def execute_bulk_purchase_orders(repository, filename: str, content_base64: str, dry_run: bool = False) -> dict:
    orders = parse_bulk_purchase_orders(filename, content_base64)
    if dry_run:
        return {
            "mode": "preview",
            "totalOrders": len(orders),
            "totalLines": sum(len(order["payload"]["DocumentLines"]) for order in orders),
            "orders": orders,
        }

    results = []
    success_count = 0
    for order in orders:
        try:
            created = repository.create_purchase_order(order["payload"])
            success_count += 1
            results.append(
                {
                    "orderId": order["orderId"],
                    "sourceRows": order["sourceRows"],
                    "status": "created",
                    "docEntry": created.get("DocEntry"),
                    "docNum": created.get("DocNum"),
                }
            )
        except Exception as exc:
            results.append(
                {
                    "orderId": order["orderId"],
                    "sourceRows": order["sourceRows"],
                    "status": "failed",
                    "error": str(exc),
                }
            )

    return {
        "mode": "execute",
        "totalOrders": len(orders),
        "successfulOrders": success_count,
        "failedOrders": len(orders) - success_count,
        "results": results,
    }
