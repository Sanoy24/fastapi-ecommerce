import io
from typing import Optional

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from app.models.order import Order


def _format_address(snapshot: Optional[dict]) -> str:
    if not snapshot:
        return "N/A"
    parts = [
        snapshot.get("street"),
        ", ".join(p for p in (snapshot.get("city"), snapshot.get("state"), snapshot.get("postal_code")) if p),
        snapshot.get("country"),
    ]
    return "<br/>".join(p for p in parts if p)


def generate_invoice_pdf(order: Order) -> bytes:
    """Render a one-page PDF invoice for an order.

    Addresses are rendered from Order.shipping_address_snapshot /
    billing_address_snapshot rather than by following shipping_address_id /
    billing_address_id to a live Address row — the snapshot is the address
    as it stood when the order was placed (see OrderCrud._address_snapshot),
    which is what an invoice needs to stay accurate even if the customer
    later edits or deletes that address, and it's the only address a guest
    order has at all.
    """
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, topMargin=0.75 * inch, bottomMargin=0.75 * inch)
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle("InvoiceTitle", parent=styles["Title"], fontSize=20, spaceAfter=4)
    heading_style = ParagraphStyle("InvoiceHeading", parent=styles["Heading3"], spaceBefore=12, spaceAfter=4)

    elements = [
        Paragraph("INVOICE", title_style),
        Paragraph(f"Order #{order.order_number}", styles["Normal"]),
        Paragraph(f"Order date: {order.order_date.strftime('%Y-%m-%d')}", styles["Normal"]),
        Paragraph(f"Payment status: {order.payment_status}", styles["Normal"]),
        Spacer(1, 0.2 * inch),
    ]

    address_table = Table(
        [
            [Paragraph("<b>Billing Address</b>", styles["Normal"]), Paragraph("<b>Shipping Address</b>", styles["Normal"])],
            [
                Paragraph(_format_address(order.billing_address_snapshot), styles["Normal"]),
                Paragraph(_format_address(order.shipping_address_snapshot), styles["Normal"]),
            ],
        ],
        colWidths=[3 * inch, 3 * inch],
    )
    address_table.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP")]))
    elements.append(address_table)

    elements.append(Paragraph("Items", heading_style))
    item_rows = [["Product", "Qty", "Unit Price", "Line Total"]]
    for item in order.order_items:
        unit_price = float(item.unit_price)
        item_rows.append(
            [
                item.product.name,
                str(item.quantity),
                f"${unit_price:.2f}",
                f"${unit_price * item.quantity:.2f}",
            ]
        )

    items_table = Table(item_rows, colWidths=[3 * inch, 0.8 * inch, 1.2 * inch, 1.2 * inch])
    items_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#4F46E5")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F3F4F6")]),
            ]
        )
    )
    elements.append(items_table)
    elements.append(Spacer(1, 0.2 * inch))

    totals_rows = [
        ["Subtotal", f"${float(order.subtotal):.2f}"],
        ["Discount", f"-${float(order.discount_amount):.2f}"],
        ["Tax", f"${float(order.tax_amount):.2f}"],
        ["Shipping", f"${float(order.shipping_amount):.2f}"],
        ["Total", f"${float(order.total_amount):.2f}"],
    ]
    totals_table = Table(totals_rows, colWidths=[4.4 * inch, 1.2 * inch])
    totals_table.setStyle(
        TableStyle(
            [
                ("ALIGN", (1, 0), (1, -1), "RIGHT"),
                ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
                ("LINEABOVE", (0, -1), (-1, -1), 1, colors.black),
            ]
        )
    )
    elements.append(totals_table)

    doc.build(elements)
    return buffer.getvalue()
