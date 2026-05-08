import base64
import subprocess
import tempfile
from pathlib import Path


SUPPORTED_TEXT_EXTENSIONS = {".txt", ".csv", ".json", ".md", ".log"}
SUPPORTED_OCR_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg", ".tif", ".tiff", ".heic"}


def _decode_base64(content_base64: str) -> bytes:
    try:
        return base64.b64decode(content_base64, validate=True)
    except Exception as exc:
        raise ValueError("Invalid base64 file content") from exc


def _read_text_payload(filename: str, file_bytes: bytes) -> str:
    for encoding in ("utf-8", "utf-8-sig", "latin-1"):
        try:
            return file_bytes.decode(encoding).strip()
        except UnicodeDecodeError:
            continue
    raise ValueError(f"Unable to decode text document: {filename}")


def _run_native_ocr(file_path: Path) -> str:
    script_path = Path(__file__).resolve().with_name("ocr_reader.swift")
    process = subprocess.run(
        ["/usr/bin/swift", str(script_path), str(file_path)],
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )

    if process.returncode != 0:
        stderr = process.stderr.strip() or process.stdout.strip() or "OCR execution failed"
        raise ValueError(stderr)

    extracted_text = process.stdout.strip()
    if not extracted_text:
        raise ValueError("No text could be extracted from the uploaded document")
    return extracted_text


def extract_document_text(filename: str, content_base64: str) -> str:
    suffix = Path(filename).suffix.lower()
    file_bytes = _decode_base64(content_base64)

    if suffix in SUPPORTED_TEXT_EXTENSIONS:
        return _read_text_payload(filename, file_bytes)

    if suffix not in SUPPORTED_OCR_EXTENSIONS:
        raise ValueError(
            "Unsupported document type. Upload PDF, PNG, JPG, JPEG, TIFF, HEIC, TXT, CSV, JSON, or MD."
        )

    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir) / Path(filename).name
        temp_path.write_bytes(file_bytes)
        return _run_native_ocr(temp_path)
