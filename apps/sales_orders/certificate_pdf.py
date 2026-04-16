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
    is_eu = getattr(batch.sales_order, 'is_eu_export', False)

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
    qty_str = f"{batch.quantity_kg:,.3f} kg" if batch.quantity_kg else "Not specified"
    op_data = [
        ["Company", batch.company.name],
        ["Country", batch.company.country],
        ["Sales Order", batch.sales_order.order_number if batch.sales_order else "—"],
        ["Quantity (net mass)", qty_str],
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

    # ── Supplier chain ────────────────────────────────────────
    farms = batch.farms.select_related('supplier').all()
    suppliers = {farm.supplier for farm in farms if farm.supplier}
    if suppliers:
        story.append(Paragraph("Supplier Chain", ParagraphStyle("s1b", fontName="Helvetica-Bold", fontSize=11, textColor=DARK, spaceBefore=6*mm, spaceAfter=3*mm)))
        sup_data = [["Supplier", "Country / City", "Address", "Email"]]
        for sup in sorted(suppliers, key=lambda s: s.name):
            location = f"{sup.country or '—'} / {sup.city or '—'}"
            sup_data.append([sup.name, location, sup.address or "—", sup.email or "—"])
        sup_t = Table(sup_data, colWidths=[45*mm, 35*mm, 55*mm, 40*mm])
        sup_t.setStyle(TableStyle([
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
        story.append(sup_t)

    # ── Farm traceability ─────────────────────────────────────
    story.append(Paragraph(f"Farm Traceability — {farms.count()} farms", ParagraphStyle("s2", fontName="Helvetica-Bold", fontSize=11, textColor=DARK, spaceBefore=6*mm, spaceAfter=3*mm)))

    if is_eu:
        farm_data = [["Farm", "Supplier", "Location", "Area", "Harvest", "Ref. Date", "EUDR"]]
    else:
        farm_data = [["Farm", "Supplier", "Location", "Area", "Harvest", "Ref. Date"]]

    for farm in farms:
        ref_date = str(farm.deforestation_reference_date) if farm.deforestation_reference_date else "—"
        harvest = str(farm.harvest_year) if farm.harvest_year else "—"
        row = [
            farm.name,
            farm.supplier.name if farm.supplier else "—",
            f"{farm.country} / {farm.state_region or '—'}",
            f"{farm.area_hectares} ha" if farm.area_hectares else "—",
            harvest,
            ref_date,
        ]
        if is_eu:
            if farm.is_disqualified:
                eudr_status = "✗ Disqualified"
            elif farm.is_eudr_verified:
                eudr_status = "✓ Verified"
            else:
                eudr_status = "Pending"
            row.append(eudr_status)
        farm_data.append(row)

    empty_cols = [""] * (7 if is_eu else 6)
    if len(farm_data) == 1:
        farm_data.append(["No farms linked"] + empty_cols[1:])

    if is_eu:
        farm_t = Table(farm_data, colWidths=[35*mm, 35*mm, 35*mm, 17*mm, 15*mm, 22*mm, 16*mm])
    else:
        farm_t = Table(farm_data, colWidths=[40*mm, 40*mm, 40*mm, 20*mm, 20*mm, 25*mm])
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

    # ── Compliance Documents ──────────────────────────────────
    phyto_certs = list(batch.phytosanitary_certs.all())
    quality_tests = list(batch.quality_tests.all())

    if phyto_certs or quality_tests:
        story.append(Paragraph("Compliance Documents", ParagraphStyle("s3cd", fontName="Helvetica-Bold", fontSize=11, textColor=DARK, spaceBefore=6*mm, spaceAfter=3*mm)))

    if phyto_certs:
        story.append(Paragraph("Phytosanitary Certificates (NAQS)", ParagraphStyle("s3ph", fontName="Helvetica", fontSize=9, textColor=SLATE, spaceBefore=2*mm, spaceAfter=2*mm)))
        ph_data = [["Cert Number", "Issuing Office", "Issued", "Expires", "Status"]]
        for c in phyto_certs:
            ph_data.append([
                c.certificate_number,
                c.issuing_office or "—",
                str(c.issued_date) if c.issued_date else "—",
                str(c.expiry_date) if c.expiry_date else "—",
                "✓ Current" if c.is_current else "Expired",
            ])
        ph_t = Table(ph_data, colWidths=[45*mm, 45*mm, 25*mm, 25*mm, 22*mm])
        ph_t.setStyle(TableStyle([
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
        story.append(ph_t)

    if quality_tests:
        story.append(Paragraph("Quality Tests (MRL / Aflatoxin)", ParagraphStyle("s3qt", fontName="Helvetica", fontSize=9, textColor=SLATE, spaceBefore=4*mm, spaceAfter=2*mm)))
        qt_data = [["Test Type", "Laboratory", "Ref", "Date", "Result"]]
        for t in quality_tests:
            qt_data.append([
                t.get_test_type_display(),
                t.lab_name or "—",
                t.lab_certificate_ref or "—",
                str(t.test_date) if t.test_date else "—",
                "✓ Pass" if t.result == 'pass' else ("✗ Fail" if t.result == 'fail' else "Pending"),
            ])
        qt_t = Table(qt_data, colWidths=[40*mm, 45*mm, 35*mm, 25*mm, 17*mm])
        qt_t.setStyle(TableStyle([
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
        story.append(qt_t)

    # ── Declaration (EU export only) ──────────────────────────
    if is_eu:
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
