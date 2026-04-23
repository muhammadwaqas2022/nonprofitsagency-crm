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
