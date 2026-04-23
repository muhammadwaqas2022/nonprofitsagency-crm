"""PDF rendering for dispute letters. Uses reportlab (pure Python)."""

from io import BytesIO

from reportlab.lib.pagesizes import LETTER
from reportlab.pdfgen import canvas

PAGE_WIDTH, PAGE_HEIGHT = LETTER
LEFT_MARGIN = 72          # 1 inch
TOP_MARGIN = 72
BOTTOM_MARGIN = 72
LINE_HEIGHT = 12
FONT_NAME = "Courier"
FONT_SIZE = 10
MAX_CHARS_PER_LINE = 80   # Courier 10pt on a 6.5" text column fits ~78


def _wrap(line: str, width: int = MAX_CHARS_PER_LINE) -> list[str]:
    """Wrap a single line to `width` chars, preserving leading indent."""
    if len(line) <= width:
        return [line]
    indent = len(line) - len(line.lstrip(" "))
    prefix = " " * indent
    words = line.split(" ")
    out: list[str] = []
    current = prefix
    for word in words:
        if not current.strip() and word == "":
            continue
        candidate = word if current == prefix else current + " " + word
        if len(candidate) > width and current.strip():
            out.append(current)
            current = prefix + word
        else:
            current = candidate if current != prefix else prefix + word
    if current.strip() or not out:
        out.append(current)
    return out


def letter_to_pdf_bytes(text: str) -> bytes:
    """Render a plain-text letter to a PDF byte string."""
    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=LETTER)
    c.setFont(FONT_NAME, FONT_SIZE)

    y = PAGE_HEIGHT - TOP_MARGIN
    for raw_line in text.split("\n"):
        for line in _wrap(raw_line):
            if y < BOTTOM_MARGIN:
                c.showPage()
                c.setFont(FONT_NAME, FONT_SIZE)
                y = PAGE_HEIGHT - TOP_MARGIN
            c.drawString(LEFT_MARGIN, y, line)
            y -= LINE_HEIGHT

    c.showPage()
    c.save()
    return buf.getvalue()


def invoice_to_pdf_bytes(
    invoice: dict,
    client: dict,
    line_items: list[dict],
    agency: dict,
) -> bytes:
    """Render an invoice to a simple single-page PDF."""
    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=LETTER)
    width = PAGE_WIDTH

    # Header / agency info (top right)
    c.setFont("Helvetica-Bold", 20)
    c.drawString(LEFT_MARGIN, PAGE_HEIGHT - 72, "INVOICE")

    c.setFont("Helvetica", 10)
    y = PAGE_HEIGHT - 72
    right_x = width - LEFT_MARGIN
    for line in [
        agency.get("agency_name", "Credit Repair Cloud"),
        agency.get("address", ""),
        (
            f"{agency.get('city','')}"
            f"{', ' if agency.get('city') and agency.get('state') else ''}"
            f"{agency.get('state','')} {agency.get('zip','')}"
        ).strip(),
        agency.get("phone", ""),
        agency.get("contact_email", ""),
    ]:
        if line.strip():
            c.drawRightString(right_x, y, line)
            y -= 13

    # Meta row
    c.setFont("Helvetica-Bold", 10)
    y = PAGE_HEIGHT - 160
    c.drawString(LEFT_MARGIN, y, "Invoice #:")
    c.drawString(LEFT_MARGIN + 260, y, "Period:")
    c.drawString(LEFT_MARGIN + 430, y, "Status:")
    c.setFont("Helvetica", 10)
    y -= 14
    c.drawString(LEFT_MARGIN, y, str(invoice.get("invoice_number") or f"#{invoice['id']}"))
    period = f"{invoice.get('period_start') or '—'} → {invoice.get('period_end') or '—'}"
    c.drawString(LEFT_MARGIN + 260, y, period)
    c.drawString(LEFT_MARGIN + 430, y, str(invoice.get("status") or "Draft"))

    # Bill-to block
    y -= 30
    c.setFont("Helvetica-Bold", 10)
    c.drawString(LEFT_MARGIN, y, "Bill to")
    c.setFont("Helvetica", 10)
    y -= 14
    c.drawString(LEFT_MARGIN, y, client["name"])
    y -= 13
    if client.get("address"):
        c.drawString(LEFT_MARGIN, y, client["address"])
        y -= 13
    addr_line = (
        f"{client.get('city','')}"
        f"{', ' if client.get('city') and client.get('state') else ''}"
        f"{client.get('state','')} {client.get('zip','')}"
    ).strip()
    if addr_line:
        c.drawString(LEFT_MARGIN, y, addr_line)
        y -= 13
    if client.get("email"):
        c.drawString(LEFT_MARGIN, y, client["email"])
        y -= 13

    # Line items table
    y -= 20
    c.setFont("Helvetica-Bold", 10)
    c.line(LEFT_MARGIN, y + 14, width - LEFT_MARGIN, y + 14)
    c.drawString(LEFT_MARGIN, y, "Description")
    c.drawRightString(LEFT_MARGIN + 360, y, "Qty")
    c.drawRightString(LEFT_MARGIN + 430, y, "Unit")
    c.drawRightString(width - LEFT_MARGIN, y, "Amount")
    c.line(LEFT_MARGIN, y - 4, width - LEFT_MARGIN, y - 4)
    y -= 18

    c.setFont("Helvetica", 10)
    subtotal = 0.0
    for li in line_items:
        if y < 120:
            c.showPage()
            y = PAGE_HEIGHT - 72
            c.setFont("Helvetica", 10)
        c.drawString(LEFT_MARGIN, y, str(li.get("description", "")))
        c.drawRightString(LEFT_MARGIN + 360, y, f"{li.get('quantity') or 1:g}")
        c.drawRightString(LEFT_MARGIN + 430, y, f"${li.get('unit_price') or 0:,.2f}")
        amount = float(li.get("amount") or 0)
        subtotal += amount
        c.drawRightString(width - LEFT_MARGIN, y, f"${amount:,.2f}")
        y -= 14

    # Totals
    y -= 10
    c.line(LEFT_MARGIN + 300, y + 10, width - LEFT_MARGIN, y + 10)
    c.setFont("Helvetica-Bold", 11)
    c.drawRightString(LEFT_MARGIN + 430, y, "Total")
    c.drawRightString(width - LEFT_MARGIN, y, f"${subtotal:,.2f}")

    if invoice.get("notes"):
        y -= 40
        c.setFont("Helvetica-Bold", 10)
        c.drawString(LEFT_MARGIN, y, "Notes")
        c.setFont("Helvetica", 10)
        y -= 14
        for line in str(invoice["notes"]).split("\n"):
            for wrapped in _wrap(line, 95):
                c.drawString(LEFT_MARGIN, y, wrapped)
                y -= 12

    c.showPage()
    c.save()
    return buf.getvalue()
