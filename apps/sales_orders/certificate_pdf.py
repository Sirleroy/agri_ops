"""
Traceability Certificate PDF generator.
One certificate per batch — includes QR code, farm list, compliance status.
"""
from io import BytesIO
from datetime import date
import qrcode
import qrcode.image.pil

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
from reportlab.lib.enums import TA_CENTER


DARK    = colors.HexColor("#0a0f1a")
GREEN   = colors.HexColor("#22c55e")
SLATE   = colors.HexColor("#64748b")
WHITE   = colors.white
LIGHT   = colors.HexColor("#f8fafc")


def _qr_image(url):
    """Generate QR code and return as ReportLab image."""
    from reportlab.platypus import Image
    import io
    qr = qrcode.QRCode(version=1, box_size=6, border=2)
    qr.add_data(url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    buf.seek(0)
    return Image(buf, width=35*mm, height=35*mm)


def generate_certificate(batch):
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4,
        leftMargin=18*mm, rightMargin=18*mm,
        topMargin=18*mm, bottomMargin=18*mm,
        title=f"Traceability Certificate — {batch.batch_number}"
    )

    story = []

    # ── Header ────────────────────────────────────────────────
    header_data = [[
        [
            Paragraph("AGRIOPS", ParagraphStyle("ag", fontName="Helvetica-Bold", fontSize=9, textColor=GREEN)),
            Paragraph("Traceability Certificate", ParagraphStyle("tc", fontName="Helvetica-Bold", fontSize=22, textColor=DARK, spaceAfter=5*mm)),
            Paragraph(f"Batch: {batch.batch_number}", ParagraphStyle("bn", fontName="Helvetica-Bold", fontSize=10, textColor=SLATE, spaceAfter=1*mm)),
            Paragraph(f"Commodity: {batch.commodity}  ·  {date.today().strftime('%d %B %Y')}", ParagraphStyle("cm", fontName="Helvetica", fontSize=9, textColor=SLATE)),
        ],
        _qr_image(batch.trace_url)
    ]]
    header_t = Table(header_data, colWidths=[130*mm, 40*mm])
    header_t.setStyle(TableStyle([("VALIGN", (0,0), (-1,-1), "TOP"), ("ALIGN", (1,0), (1,0), "RIGHT")]))
    story.append(header_t)
    story.append(HRFlowable(width="100%", thickness=1.5, color=GREEN, spaceAfter=6*mm, spaceBefore=4*mm))

    # ── Operator ──────────────────────────────────────────────
    story.append(Paragraph("Operator", ParagraphStyle("s", fontName="Helvetica-Bold", fontSize=11, textColor=DARK, spaceBefore=4*mm, spaceAfter=3*mm)))
    op_data = [
        ["Company", batch.company.name],
        ["Country", batch.company.country],
        ["Sales Order", batch.sales_order.order_number if batch.sales_order else "—"],
        ["Certificate Date", str(date.today())],
        ["Public Trace URL", batch.trace_url],
    ]
    op_t = Table(op_data, colWidths=[45*mm, 130*mm])
    op_t.setStyle(TableStyle([
        ("FONTNAME", (0,0), (0,-1), "Helvetica-Bold"),
        ("FONTSIZE", (0,0), (-1,-1), 9),
        ("TEXTCOLOR", (0,0), (0,-1), SLATE),
        ("GRID", (0,0), (-1,-1), 0.3, colors.HexColor("#cbd5e1")),
        ("TOPPADDING", (0,0), (-1,-1), 4),
        ("BOTTOMPADDING", (0,0), (-1,-1), 4),
        ("LEFTPADDING", (0,0), (-1,-1), 6),
        ("ROWBACKGROUNDS", (0,0), (-1,-1), [colors.HexColor("#f8fafc"), WHITE]),
    ]))
    story.append(op_t)

    # ── Farm traceability ─────────────────────────────────────
    farms = batch.farms.select_related('supplier').all()
    story.append(Paragraph(f"Farm Traceability — {farms.count()} farms", ParagraphStyle("s2", fontName="Helvetica-Bold", fontSize=11, textColor=DARK, spaceBefore=6*mm, spaceAfter=3*mm)))

    farm_data = [["Farm", "Supplier", "Location", "Area", "EUDR"]]
    for farm in farms:
        farm_data.append([
            farm.name,
            farm.supplier.name if farm.supplier else "—",
            f"{farm.country} / {farm.state_region or '—'}",
            f"{farm.area_hectares} ha" if farm.area_hectares else "—",
            "✓ Verified" if farm.is_eudr_verified else "Pending",
        ])

    if len(farm_data) == 1:
        farm_data.append(["No farms linked", "", "", "", ""])

    farm_t = Table(farm_data, colWidths=[45*mm, 45*mm, 40*mm, 20*mm, 25*mm])
    farm_t.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,0), DARK),
        ("TEXTCOLOR", (0,0), (-1,0), WHITE),
        ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"),
        ("FONTSIZE", (0,0), (-1,-1), 8),
        ("GRID", (0,0), (-1,-1), 0.3, colors.HexColor("#cbd5e1")),
        ("ROWBACKGROUNDS", (0,1), (-1,-1), [WHITE, colors.HexColor("#f8fafc")]),
        ("TOPPADDING", (0,0), (-1,-1), 4),
        ("BOTTOMPADDING", (0,0), (-1,-1), 4),
        ("LEFTPADDING", (0,0), (-1,-1), 4),
    ]))
    story.append(farm_t)

    # ── Declaration ───────────────────────────────────────────
    story.append(Spacer(1, 6*mm))
    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#cbd5e1"), spaceAfter=4*mm))
    story.append(Paragraph("Due Diligence Declaration", ParagraphStyle("s3", fontName="Helvetica-Bold", fontSize=11, textColor=DARK, spaceAfter=3*mm)))
    story.append(Paragraph(
        f"The operator <b>{batch.company.name}</b> declares that all commodities in batch "
        f"<b>{batch.batch_number}</b> have been sourced in compliance with EU Deforestation "
        f"Regulation (EU) 2023/1115. Farm-level geolocation data and risk assessments are "
        f"retained in the AgriOps platform and available for audit.",
        ParagraphStyle("body", fontName="Helvetica", fontSize=9, textColor=colors.HexColor("#334155"), spaceAfter=6*mm)
    ))

    story.append(Spacer(1, 8*mm))
    sig_data = [["Authorised Signatory", "Date"], [" " * 50, str(date.today())]]
    sig_t = Table(sig_data, colWidths=[100*mm, 75*mm])
    sig_t.setStyle(TableStyle([
        ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"),
        ("FONTSIZE", (0,0), (-1,-1), 8),
        ("TEXTCOLOR", (0,0), (-1,0), SLATE),
        ("LINEBELOW", (0,1), (0,1), 0.5, DARK),
        ("TOPPADDING", (0,0), (-1,-1), 4),
        ("BOTTOMPADDING", (0,0), (-1,-1), 12),
    ]))
    story.append(sig_t)

    story.append(Spacer(1, 4*mm))
    story.append(Paragraph(
        f"Generated by AgriOps · app.agriops.io · {date.today().strftime('%d %B %Y')} · "
        f"Scan QR code to verify: {batch.trace_url}",
        ParagraphStyle("footer", fontName="Helvetica", fontSize=7, textColor=SLATE, alignment=TA_CENTER)
    ))

    doc.build(story)
    buffer.seek(0)
    return buffer
