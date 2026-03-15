import io
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_RIGHT, TA_LEFT
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer,
    Table, TableStyle, HRFlowable, KeepTogether
)
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus.flowables import Flowable
from billing.models import Purchase

PAGE_W, PAGE_H = A4

# ── Colors ───
C_DARK       = colors.HexColor("#1B2A4A")   # Dark navy
C_PRIMARY    = colors.HexColor("#2563EB")   # Blue
C_ACCENT     = colors.HexColor("#F59E0B")   # Amber
C_SUCCESS    = colors.HexColor("#10B981")   # Green
C_LIGHT      = colors.HexColor("#F1F5F9")   # Light gray bg
C_BORDER     = colors.HexColor("#CBD5E1")   # Border gray
C_TEXT       = colors.HexColor("#1E293B")   # Main text
C_MUTED      = colors.HexColor("#64748B")   # Muted text
C_WHITE      = colors.white
C_ROW_ALT    = colors.HexColor("#EFF6FF")   # Light blue alt row


# ── Custom Flowables ───

class ColorRect(Flowable):
    """A simple colored rectangle block — used for header/footer bands."""
    def __init__(self, width, height, fill_color, radius=0):
        super().__init__()
        self.width = width
        self.height = height
        self.fill_color = fill_color
        self.radius = radius

    def draw(self):
        self.canv.setFillColor(self.fill_color)
        if self.radius:
            self.canv.roundRect(
                0, 0, self.width, self.height,
                self.radius, fill=1, stroke=0
            )
        else:
            self.canv.rect(0, 0, self.width, self.height, fill=1, stroke=0)


class HeaderBanner(Flowable):
    """
    Full-width header banner with:
    - Shopping bag logo
    - ShopBill brand name
    - INVOICE label + meta info
    """
    def __init__(self, width, purchase):
        super().__init__()
        self.width = width
        self.height = 48 * mm
        self.purchase = purchase

    def draw(self):
        c = self.canv
        w, h = self.width, self.height

        # Background
        c.setFillColor(C_DARK)
        c.roundRect(0, 0, w, h, 4*mm, fill=1, stroke=0)

        # Accent left strip
        c.setFillColor(C_ACCENT)
        c.roundRect(0, 0, 3*mm, h, 2*mm, fill=1, stroke=0)

        # ── Shopping Bag Icon ──
        bx, by = 12*mm, h/2 - 8*mm
        # Bag body
        c.setFillColor(C_ACCENT)
        c.roundRect(bx, by, 16*mm, 13*mm, 2.5*mm, fill=1, stroke=0)
        # Handle
        c.setStrokeColor(C_WHITE)
        c.setLineWidth(2)
        c.setFillColor(colors.transparent)
        c.bezier(
            bx + 4*mm, by + 13*mm,
            bx + 4*mm, by + 19*mm,
            bx + 12*mm, by + 19*mm,
            bx + 12*mm, by + 13*mm,
        )
        # Bag lines
        c.setStrokeColor(C_DARK)
        c.setLineWidth(1)
        c.line(bx+4*mm, by+8*mm, bx+12*mm, by+8*mm)
        c.line(bx+4*mm, by+5.5*mm, bx+12*mm, by+5.5*mm)

        # ── Brand Name ──
        c.setFillColor(C_WHITE)
        c.setFont("Helvetica-Bold", 24)
        c.drawString(32*mm, h/2 + 3*mm, "ShopBill")

        # ── Tagline ──
        c.setFillColor(C_ACCENT)
        c.setFont("Helvetica-Oblique", 8.5)
        c.drawString(32*mm, h/2 - 4*mm, "Your Trusted Billing Partner")

        # ── Divider ──
        c.setStrokeColor(colors.HexColor("#334E7A"))
        c.setLineWidth(0.5)
        c.line(w/2, 6*mm, w/2, h - 6*mm)

        # ── Right: INVOICE label ──
        c.setFillColor(C_WHITE)
        c.setFont("Helvetica-Bold", 30)
        c.drawRightString(w - 10*mm, h/2 + 6*mm, "INVOICE")

        # ── Invoice meta ──
        meta = [
            ("Invoice No", f"#{self.purchase.id:05d}"),
            ("Date",       self.purchase.created_at.strftime("%d %B %Y")),
            ("Time",       self.purchase.created_at.strftime("%I:%M %p")),
        ]
        my = h/2 - 4*mm
        for label, value in meta:
            c.setFillColor(colors.HexColor("#94A3B8"))
            c.setFont("Helvetica", 7.5)
            c.drawRightString(w - 10*mm, my, f"{label}:")
            c.setFillColor(C_WHITE)
            c.setFont("Helvetica-Bold", 7.5)
            c.drawRightString(w - 10*mm, my - 4.5*mm, value)
            my -= 11*mm


class SectionTitle(Flowable):
    """Section title with left accent bar."""
    def __init__(self, text, width):
        super().__init__()
        self.text = text
        self.width = width
        self.height = 8*mm

    def draw(self):
        c = self.canv
        # Accent bar
        c.setFillColor(C_PRIMARY)
        c.roundRect(0, 1*mm, 3*mm, 5*mm, 1*mm, fill=1, stroke=0)
        # Text
        c.setFillColor(C_DARK)
        c.setFont("Helvetica-Bold", 11)
        c.drawString(6*mm, 2.5*mm, self.text)
        # Bottom line
        c.setStrokeColor(C_BORDER)
        c.setLineWidth(0.5)
        c.line(0, 0, self.width, 0)


class BillToBox(Flowable):
    """Customer info + paid badge side by side."""
    def __init__(self, width, purchase):
        super().__init__()
        self.width = width
        self.height = 22*mm
        self.purchase = purchase

    def draw(self):
        c = self.canv
        w, h = self.width, self.height

        # Left box
        c.setFillColor(C_LIGHT)
        c.setStrokeColor(C_BORDER)
        c.setLineWidth(0.5)
        c.roundRect(0, 0, w * 0.6, h, 2*mm, fill=1, stroke=1)

        c.setFillColor(C_MUTED)
        c.setFont("Helvetica", 7.5)
        c.drawString(4*mm, h - 6*mm, "BILL TO")

        c.setFillColor(C_PRIMARY)
        c.setFont("Helvetica-Bold", 9)
        c.drawString(4*mm, h - 12*mm, "Customer Email")

        c.setFillColor(C_TEXT)
        c.setFont("Helvetica", 9)
        c.drawString(4*mm, h - 18*mm, self.purchase.customer_email)

        # Right: status badges
        rx = w * 0.65

        # PAID badge
        c.setFillColor(C_SUCCESS)
        c.roundRect(rx, h - 11*mm, 35*mm, 9*mm, 2*mm, fill=1, stroke=0)
        c.setFillColor(C_WHITE)
        c.setFont("Helvetica-Bold", 9)
        c.drawCentredString(rx + 17.5*mm, h - 6.5*mm, "PAID")

        # Invoice count
        c.setFillColor(C_LIGHT)
        c.setStrokeColor(C_BORDER)
        c.roundRect(rx, h - 22*mm, 35*mm, 9*mm, 2*mm, fill=1, stroke=1)
        c.setFillColor(C_MUTED)
        c.setFont("Helvetica", 8)
        c.drawCentredString(
            rx + 17.5*mm, h - 17*mm,
            f"Bill #{self.purchase.id:05d}"
        )


# ── Main Generator ───

def generate_invoice_pdf(purchase: Purchase) -> bytes:
    """
    Generates a professional A4 invoice PDF using Platypus flowables.
    All items are rendered dynamically — no hardcoded row limits.
    Returns raw PDF bytes.
    """
    buffer = io.BytesIO()

    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=12*mm,
        leftMargin=12*mm,
        topMargin=10*mm,
        bottomMargin=20*mm,
    )

    content_width = PAGE_W - 24*mm
    story = []

    # ── 1. Header ──
    story.append(HeaderBanner(content_width, purchase))
    story.append(Spacer(1, 6*mm))

    # ── 2. Bill To ──
    story.append(BillToBox(content_width, purchase))
    story.append(Spacer(1, 6*mm))

    # ── 3. Items Section ──
    story.append(SectionTitle("ITEMS PURCHASED", content_width))
    story.append(Spacer(1, 3*mm))
    story.append(_build_items_table(purchase, content_width))
    story.append(Spacer(1, 6*mm))

    # ── 4. Summary ──
    story.append(KeepTogether([
        SectionTitle("BILL SUMMARY", content_width),
        Spacer(1, 3*mm),
        _build_summary_table(purchase, content_width),
    ]))
    story.append(Spacer(1, 6*mm))

    # ── 5. Thank you note ──
    story.append(_build_footer_note(content_width))

    doc.build(story)
    return buffer.getvalue()


# ── Table Builders ──

def _build_items_table(purchase: Purchase, width: float) -> Table:
    """Builds the items purchased table — handles any number of rows."""

    # Styles
    th = ParagraphStyle(
        "th", fontSize=8, textColor=C_WHITE,
        fontName="Helvetica-Bold", alignment=TA_CENTER
    )
    td_center = ParagraphStyle(
        "tdc", fontSize=8.5, textColor=C_TEXT,
        fontName="Helvetica", alignment=TA_CENTER
    )
    td_left = ParagraphStyle(
        "tdl", fontSize=8.5, textColor=C_TEXT,
        fontName="Helvetica", alignment=TA_LEFT
    )
    td_bold = ParagraphStyle(
        "tdb", fontSize=8.5, textColor=C_PRIMARY,
        fontName="Helvetica-Bold", alignment=TA_CENTER
    )

    # Header row
    data = [[
        Paragraph("PRODUCT NAME", th),
        Paragraph("UNIT PRICE", th),
        Paragraph("QTY", th),
        Paragraph("PURCHASE PRICE", th),
        Paragraph("TAX %", th),
        Paragraph("TAX AMOUNT", th),
        Paragraph("TOTAL PRICE", th),
    ]]

    # Data rows — all items rendered
    items = list(purchase.items.select_related("product").all())
    for item in items:
        data.append([
            Paragraph(item.product.name, td_left),
            Paragraph(f"Rs.{item.unit_price:.2f}", td_center),
            Paragraph(str(item.quantity), td_center),
            Paragraph(f"Rs.{item.purchase_price:.2f}", td_center),
            Paragraph(f"{item.tax_percentage}%", td_center),
            Paragraph(f"Rs.{item.tax_amount:.2f}", td_center),
            Paragraph(f"Rs.{item.total_price:.2f}", td_bold),
        ])

    col_widths = [
        width * 0.26,   # Product name — wider
        width * 0.13,   # Unit price
        width * 0.07,   # Qty
        width * 0.15,   # Purchase price
        width * 0.09,   # Tax %
        width * 0.13,   # Tax amount
        width * 0.17,   # Total price
    ]

    # Alternating row colors
    row_styles = []
    for i in range(1, len(data)):
        bg = C_ROW_ALT if i % 2 == 0 else C_WHITE
        row_styles.append(("BACKGROUND", (0, i), (-1, i), bg))

    table = Table(data, colWidths=col_widths, repeatRows=1)
    table.setStyle(TableStyle([
        # Header
        ("BACKGROUND", (0, 0), (-1, 0), C_PRIMARY),
        ("TOPPADDING",    (0, 0), (-1, 0), 8),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 8),
        # Data rows
        ("TOPPADDING",    (0, 1), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 1), (-1, -1), 7),
        ("LEFTPADDING",   (0, 0), (-1, -1), 6),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 6),
        # Borders
        ("LINEBELOW",  (0, 0), (-1, -1), 0.4, C_BORDER),
        ("BOX",        (0, 0), (-1, -1), 0.8, C_BORDER),
        ("VALIGN",     (0, 0), (-1, -1), "MIDDLE"),
        # Last column highlight
        ("BACKGROUND", (-1, 0), (-1, 0), C_DARK),
        *row_styles,
    ]))
    return table


def _build_summary_table(purchase: Purchase, width: float) -> Table:
    """Builds the bill summary table — right aligned."""
    label_style = ParagraphStyle(
        "sl", fontSize=9, textColor=C_MUTED,
        fontName="Helvetica", alignment=TA_RIGHT
    )
    value_style = ParagraphStyle(
        "sv", fontSize=9, textColor=C_TEXT,
        fontName="Helvetica-Bold", alignment=TA_RIGHT
    )
    total_label = ParagraphStyle(
        "tl", fontSize=10, textColor=C_WHITE,
        fontName="Helvetica-Bold", alignment=TA_RIGHT
    )
    total_value = ParagraphStyle(
        "tv", fontSize=11, textColor=C_ACCENT,
        fontName="Helvetica-Bold", alignment=TA_RIGHT
    )

    rows = [
        (label_style, value_style,
         "Total without tax",      f"Rs.{purchase.total_without_tax:.2f}"),
        (label_style, value_style,
         "Total tax payable",      f"Rs.{purchase.total_tax:.2f}"),
        (label_style, value_style,
         "Net price of items",     f"Rs.{purchase.net_total:.2f}"),
        (label_style, value_style,
         "Rounded total",          f"Rs.{purchase.rounded_total:.2f}"),
        (label_style, value_style,
         "Cash paid by customer",  f"Rs.{purchase.cash_paid:.2f}"),
        (total_label, total_value,
         "Balance Returned to Customer",
         f"Rs.{purchase.balance_returned:.2f}"),
    ]

    data = [
        [Paragraph(label, ls), Paragraph(value, vs)]
        for ls, vs, label, value in rows
    ]

    col_widths = [width * 0.75, width * 0.25]
    table = Table(data, colWidths=col_widths)

    table.setStyle(TableStyle([
        # All rows
        ("TOPPADDING",    (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LEFTPADDING",   (0, 0), (-1, -1), 8),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 8),
        ("LINEBELOW", (0, 0), (-1, -2), 0.4, C_BORDER),
        ("BACKGROUND", (0, 0), (-1, -2), C_LIGHT),
        # Last row — highlighted balance
        ("BACKGROUND", (0, -1), (-1, -1), C_DARK),
        ("TOPPADDING",    (0, -1), (-1, -1), 9),
        ("BOTTOMPADDING", (0, -1), (-1, -1), 9),
        ("ROUNDEDCORNERS", [3, 3, 3, 3]),
    ]))
    return table


def _build_footer_note(width: float) -> Table:
    """Builds a thank you note footer."""
    style_center = ParagraphStyle(
        "fc", fontSize=9, textColor=C_WHITE,
        fontName="Helvetica-Bold", alignment=TA_CENTER
    )
    style_sub = ParagraphStyle(
        "fs", fontSize=8, textColor=colors.HexColor("#94A3B8"),
        fontName="Helvetica-Oblique", alignment=TA_CENTER
    )

    data = [[
        Paragraph("Thank you for shopping with us!", style_center),
        Paragraph("ShopBill  |  Your Trusted Billing Partner", style_sub),
    ]]

    table = Table(data, colWidths=[width * 0.55, width * 0.45])
    table.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, -1), C_DARK),
        ("TOPPADDING",    (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ("LEFTPADDING",   (0, 0), (-1, -1), 10),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 10),
        ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
        ("LINEABOVE",     (0, 0), (-1, -1), 2, C_ACCENT),
    ]))
    return table