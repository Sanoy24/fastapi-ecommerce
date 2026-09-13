import csv
import io
from typing import Any, Dict, Iterable, List

from app.models.product import Product

# Deliberately a subset of Product's columns: enough to round-trip a
# catalog through export -> edit -> import, without dragging in sale
# windows (sale_starts_at/sale_ends_at) or SEO fields whose datetime/long-
# text shapes add CSV-parsing edge cases out of proportion to how often a
# bulk edit actually touches them.
PRODUCT_CSV_FIELDS = [
    "id", "name", "description", "price", "sale_price", "compare_at_price",
    "stock_quantity", "sku", "category_id", "brand_id", "status", "image_url",
]

_INT_FIELDS = {"id", "stock_quantity", "category_id", "brand_id"}
_FLOAT_FIELDS = {"price", "sale_price", "compare_at_price"}


def products_to_csv(products: Iterable[Product]) -> str:
    """Render products as CSV text using PRODUCT_CSV_FIELDS — the same
    column set parse_product_csv reads back, so an unedited export
    round-trips through import as all-updates with no changes."""
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=PRODUCT_CSV_FIELDS)
    writer.writeheader()
    for product in products:
        writer.writerow(
            {
                "id": product.id,
                "name": product.name,
                "description": product.description or "",
                "price": float(product.price),
                "sale_price": float(product.sale_price) if product.sale_price is not None else "",
                "compare_at_price": (
                    float(product.compare_at_price) if product.compare_at_price is not None else ""
                ),
                "stock_quantity": product.stock_quantity,
                "sku": product.sku or "",
                "category_id": product.category_id if product.category_id is not None else "",
                "brand_id": product.brand_id if product.brand_id is not None else "",
                "status": product.status,
                "image_url": product.image_url or "",
            }
        )
    return buffer.getvalue()


def parse_product_csv(content: str) -> List[Dict[str, Any]]:
    """Parse CSV text into one dict per data row, coercing PRODUCT_CSV_FIELDS'
    int/float columns and dropping blank cells entirely (rather than passing
    through "") so the row can be fed straight into ProductCreate/ProductUpdate
    and rely on their own defaults / exclude_unset semantics.

    Each dict always carries "_row_number" (1-indexed, header is row 1, so
    the first data row is 2 — matching what a spreadsheet would show). A row
    whose numeric columns fail to parse gets "_error" set instead of the
    unparseable fields, so the caller can record it as a failed row without
    aborting the rest of the import.
    """
    reader = csv.DictReader(io.StringIO(content))
    rows: List[Dict[str, Any]] = []
    for row_number, raw_row in enumerate(reader, start=2):
        row: Dict[str, Any] = {"_row_number": row_number}
        for key, value in raw_row.items():
            if key is None or value is None:
                continue
            value = value.strip()
            if value == "":
                continue
            if key in _INT_FIELDS:
                try:
                    row[key] = int(value)
                except ValueError:
                    row["_error"] = f"'{key}' must be an integer, got {value!r}"
                    break
            elif key in _FLOAT_FIELDS:
                try:
                    row[key] = float(value)
                except ValueError:
                    row["_error"] = f"'{key}' must be a number, got {value!r}"
                    break
            else:
                row[key] = value
        rows.append(row)
    return rows
