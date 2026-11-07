"""Read two-column clipboard text, CSV, TXT and optional XLSX hyperlinks."""

import csv
import io
from pathlib import Path

from .safety import safe_filename, validate_url


def parse_text(text):
    sample = text[:4096]
    delimiter = "\t" if "\t" in sample else ("|" if "|" in sample else ",")
    rows = csv.reader(io.StringIO(text.lstrip("\ufeff")), delimiter=delimiter)
    return normalize(rows)


def normalize(rows):
    result = []
    for index, row in enumerate(rows, 1):
        if not row or not str(row[0] or "").strip():
            continue
        url = str(row[0]).strip()
        if url.lower() in {"link", "url", "đường dẫn"}:
            continue
        try:
            url = validate_url(url)
        except ValueError as exc:
            raise ValueError(f"Dòng {index}: {exc}") from exc
        name = str(row[1]).strip() if len(row) > 1 and row[1] is not None else ""
        if not name:
            from .safety import filename_from_url
            suffix = Path(filename_from_url(url)).suffix
            name = f"{len(result) + 1:03d}{suffix}"
        result.append((url, safe_filename(name)))
    return result


def read_batch(path):
    path = Path(path)
    if path.suffix.lower() == ".xlsx":
        try:
            from openpyxl import load_workbook
        except ImportError as exc:
            raise ValueError('Cài hỗ trợ Excel bằng: pip install ".[excel]"') from exc
        book = load_workbook(path, read_only=False, data_only=True, keep_links=False)
        try:
            return normalize([(row[0].hyperlink.target if row[0].hyperlink else row[0].value,
                               row[1].value if len(row) > 1 else "") for row in book.active.iter_rows()])
        finally:
            book.close()
    return parse_text(path.read_text(encoding="utf-8-sig"))
