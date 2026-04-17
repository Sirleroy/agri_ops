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

# A4 usable width: 210mm − 18mm left − 18mm right = 174mm
PAGE_W = 174 * mm

# Reusable paragraph styles for table cells (enables text wrapping)
_CELL      = ParagraphStyle("cell",      fontName="Helvetica",      fontSize=8, textColor=colors.HexColor("#cbd5e1"), leading=11)
_CELL_BOLD = ParagraphStyle("cell_bold", fontName="Helvetica-Bold", fontSize=8, textColor=colors.HexColor("#64748b"), leading=11)
_CELL_HDR  = ParagraphStyle("cell_hdr",  fontName="Helvetica-Bold", fontSize=8, textColor=WHITE,                     leading=11)
_CELL_URL  = ParagraphStyle("cell_url",  fontName="Helvetica",      fontSize=7, textColor=colors.HexColor("#94a3b8"), leading=10, wordWrap='CJK')


def _p(text, style=None):
    """Wrap a value in a Paragraph so ReportLab reflows it inside the cell."""
    style = style or _CELL
    return Paragraph(str(text) if text else "—", style)


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
    # 174mm total: text block 134mm + QR 40mm
    header_data = [[
        [
            Paragraph("AGRIOPS", ParagraphStyle("ag", fontName="Helvetica-Bold", fontSize=9, textColor=GREEN)),
            Paragraph("Traceability Certificate", ParagraphStyle("tc", fontName="Helvetica-Bold", fontSize=22, textColor=DARK, spaceAfter=5*mm)),
            Paragraph(f"Batch: {batch.batch_number}", ParagraphStyle("bn", fontName="Helvetica-Bold", fontSize=10, textColor=SLATE, spaceAfter=1*mm)),
            Paragraph(f"Commodity: {batch.commodity}  ·  {date.today().strftime('%d %B %Y')}", ParagraphStyle("cm", fontName="Helvetica", fontSize=9, textColor=SLATE)),
        ],
        _qr_image(batch.trace_url)
    ]]
    header_t = Table(header_data, colWidths=[134*mm, 40*mm])
    header_t.setStyle(TableStyle([("VALIGN", (0,0), (-1,-1), "TOP"), ("ALIGN", (1,0), (1,0), "RIGHT")]))
    story.append(header_t)
    story.append(HRFlowable(width="100%", thickness=1.5, color=GREEN, spaceAfter=6*mm, spaceBefore=4*mm))

    # ── Operator ──────────────────────────────────────────────
    # 174mm total: label 44mm + value 130mm
    story.append(Paragraph("Operator", ParagraphStyle("s", fontName="Helvetica-Bold", fontSize=11, textColor=DARK, spaceBefore=4*mm, spaceAfter=3*mm)))
    qty_str = f"{batch.quantity_kg:,.3f} kg" if batch.quantity_kg else "Not specified"
    op_data = [
        [_p("Company",          _CELL_BOLD), _p(batch.company.name)],
        [_p("Country",          _CELL_BOLD), _p(batch.company.country)],
        [_p("Sales Order",      _CELL_BOLD), _p(batch.sales_order.order_number if batch.sales_order else "—")],
        [_p("Quantity (net mass)", _CELL_BOLD), _p(qty_str)],
        [_p("Certificate Date", _CELL_BOLD), _p(str(date.today()))],
        [_p("Public Trace URL", _CELL_BOLD), _p(batch.trace_url, _CELL_URL)],
    ]
    op_t = Table(op_data, colWidths=[44*mm, 130*mm])
    op_t.setStyle(TableStyle([
        ("FONTSIZE",       (0,0), (-1,-1), 9),
        ("GRID",           (0,0), (-1,-1), 0.3, colors.HexColor("#cbd5e1")),
        ("TOPPADDING",     (0,0), (-1,-1), 5),
        ("BOTTOMPADDING",  (0,0), (-1,-1), 5),
        ("LEFTPADDING",    (0,0), (-1,-1), 6),
        ("VALIGN",         (0,0), (-1,-1), "TOP"),
        ("ROWBACKGROUNDS", (0,0), (-1,-1), [colors.HexColor("#f8fafc"), WHITE]),
    ]))
    story.append(op_t)

    # ── Supplier chain ────────────────────────────────────────
    # 174mm total: 46+34+55+39
    farms = batch.farms.select_related('supplier').all()
    suppliers = {farm.supplier for farm in farms if farm.supplier}
    if suppliers:
        story.append(Paragraph("Supplier Chain", ParagraphStyle("s1b", fontName="Helvetica-Bold", fontSize=11, textColor=DARK, spaceBefore=6*mm, spaceAfter=3*mm)))
        sup_data = [[_p("Supplier", _CELL_HDR), _p("Country / City", _CELL_HDR), _p("Address", _CELL_HDR), _p("Email", _CELL_HDR)]]
        for sup in sorted(suppliers, key=lambda s: s.name):
            location = f"{sup.country or '—'} / {sup.city or '—'}"
            sup_data.append([_p(sup.name), _p(location), _p(sup.address or "—"), _p(sup.email or "—")])
        sup_t = Table(sup_data, colWidths=[46*mm, 34*mm, 55*mm, 39*mm])
        sup_t.setStyle(TableStyle([
            ("BACKGROUND",     (0,0), (-1,0), DARK),
            ("FONTSIZE",       (0,0), (-1,-1), 8),
            ("GRID",           (0,0), (-1,-1), 0.3, colors.HexColor("#cbd5e1")),
            ("ROWBACKGROUNDS", (0,1), (-1,-1), [WHITE, colors.HexColor("#f8fafc")]),
            ("TOPPADDING",     (0,0), (-1,-1), 5),
            ("BOTTOMPADDING",  (0,0), (-1,-1), 5),
            ("LEFTPADDING",    (0,0), (-1,-1), 5),
            ("VALIGN",         (0,0), (-1,-1), "TOP"),
        ]))
        story.append(sup_t)

    # ── Farm traceability ─────────────────────────────────────
    story.append(Paragraph(f"Farm Traceability — {farms.count()} farms", ParagraphStyle("s2", fontName="Helvetica-Bold", fontSize=11, textColor=DARK, spaceBefore=6*mm, spaceAfter=3*mm)))

    if is_eu:
        # 174mm: 32+28+28+16+14+22+34
        farm_headers = [_p(h, _CELL_HDR) for h in ["Farm", "Supplier", "Location", "Area", "Harvest", "Ref. Date", "EUDR"]]
        farm_col_w   = [32*mm, 28*mm, 28*mm, 16*mm, 14*mm, 22*mm, 34*mm]
    else:
        # 174mm: 38+36+36+18+18+28
        farm_headers = [_p(h, _CELL_HDR) for h in ["Farm", "Supplier", "Location", "Area", "Harvest", "Ref. Date"]]
        farm_col_w   = [38*mm, 36*mm, 36*mm, 18*mm, 18*mm, 28*mm]

    farm_data = [farm_headers]
    for farm in farms:
        ref_date = str(farm.deforestation_reference_date) if farm.deforestation_reference_date else "—"
        harvest  = str(farm.harvest_year) if farm.harvest_year else "—"
        location = f"{farm.country} / {farm.state_region or '—'}"
        area     = f"{farm.area_hectares} ha" if farm.area_hectares else "—"
        row = [
            _p(farm.name),
            _p(farm.supplier.name if farm.supplier else "—"),
            _p(location),
            _p(area),
            _p(harvest),
            _p(ref_date),
        ]
        if is_eu:
            if farm.is_disqualified:
                eudr_text = "✗ Disqualified"
                eudr_style = ParagraphStyle("eudr_bad", fontName="Helvetica", fontSize=8, textColor=colors.HexColor("#f87171"), leading=11)
            elif farm.is_eudr_verified:
                eudr_text = "✓ Verified"
                eudr_style = ParagraphStyle("eudr_ok", fontName="Helvetica", fontSize=8, textColor=GREEN, leading=11)
            else:
                eudr_text = "Pending"
                eudr_style = _CELL
            row.append(Paragraph(eudr_text, eudr_style))
        farm_data.append(row)

    if len(farm_data) == 1:
        farm_data.append([_p("No farms linked")] + [_p("") for _ in range(len(farm_headers) - 1)])

    farm_t = Table(farm_data, colWidths=farm_col_w)
    farm_t.setStyle(TableStyle([
        ("BACKGROUND",     (0,0), (-1,0), DARK),
        ("FONTSIZE",       (0,0), (-1,-1), 8),
        ("GRID",           (0,0), (-1,-1), 0.3, colors.HexColor("#cbd5e1")),
        ("ROWBACKGROUNDS", (0,1), (-1,-1), [WHITE, colors.HexColor("#f8fafc")]),
        ("TOPPADDING",     (0,0), (-1,-1), 5),
        ("BOTTOMPADDING",  (0,0), (-1,-1), 5),
        ("LEFTPADDING",    (0,0), (-1,-1), 5),
        ("VALIGN",         (0,0), (-1,-1), "TOP"),
    ]))
    story.append(farm_t)

    # ── Compliance Documents ──────────────────────────────────
    phyto_certs   = list(batch.phytosanitary_certs.all())
    quality_tests = list(batch.quality_tests.all())

    if phyto_certs or quality_tests:
        story.append(Paragraph("Compliance Documents", ParagraphStyle("s3cd", fontName="Helvetica-Bold", fontSize=11, textColor=DARK, spaceBefore=6*mm, spaceAfter=3*mm)))

    if phyto_certs:
        story.append(Paragraph("Phytosanitary Certificates (NAQS)", ParagraphStyle("s3ph", fontName="Helvetica", fontSize=9, textColor=SLATE, spaceBefore=2*mm, spaceAfter=2*mm)))
        # 174mm: 46+46+26+26+30
        ph_data = [[_p(h, _CELL_HDR) for h in ["Cert Number", "Issuing Office", "Issued", "Expires", "Status"]]]
        for c in phyto_certs:
            status_text  = "✓ Current" if c.is_current else "Expired"
            status_style = ParagraphStyle("ps_ok", fontName="Helvetica", fontSize=8, textColor=GREEN, leading=11) if c.is_current else _CELL
            ph_data.append([
                _p(c.certificate_number),
                _p(c.issuing_office or "—"),
                _p(str(c.issued_date) if c.issued_date else "—"),
                _p(str(c.expiry_date) if c.expiry_date else "—"),
                Paragraph(status_text, status_style),
            ])
        ph_t = Table(ph_data, colWidths=[46*mm, 46*mm, 26*mm, 26*mm, 30*mm])
        ph_t.setStyle(TableStyle([
            ("BACKGROUND",     (0,0), (-1,0), DARK),
            ("FONTSIZE",       (0,0), (-1,-1), 8),
            ("GRID",           (0,0), (-1,-1), 0.3, colors.HexColor("#cbd5e1")),
            ("ROWBACKGROUNDS", (0,1), (-1,-1), [WHITE, colors.HexColor("#f8fafc")]),
            ("TOPPADDING",     (0,0), (-1,-1), 5),
            ("BOTTOMPADDING",  (0,0), (-1,-1), 5),
            ("LEFTPADDING",    (0,0), (-1,-1), 5),
            ("VALIGN",         (0,0), (-1,-1), "TOP"),
        ]))
        story.append(ph_t)

    if quality_tests:
        story.append(Paragraph("Quality Tests (MRL / Aflatoxin)", ParagraphStyle("s3qt", fontName="Helvetica", fontSize=9, textColor=SLATE, spaceBefore=4*mm, spaceAfter=2*mm)))
        # 174mm: 42+46+36+26+24
        qt_data = [[_p(h, _CELL_HDR) for h in ["Test Type", "Laboratory", "Ref", "Date", "Result"]]]
        for t in quality_tests:
            result_text  = "✓ Pass" if t.result == 'pass' else ("✗ Fail" if t.result == 'fail' else "Pending")
            result_style = ParagraphStyle("rs_ok", fontName="Helvetica", fontSize=8, textColor=GREEN, leading=11) if t.result == 'pass' else (
                           ParagraphStyle("rs_bad", fontName="Helvetica", fontSize=8, textColor=colors.HexColor("#f87171"), leading=11) if t.result == 'fail' else _CELL)
            qt_data.append([
                _p(t.get_test_type_display()),
                _p(t.lab_name or "—"),
                _p(t.lab_certificate_ref or "—"),
                _p(str(t.test_date) if t.test_date else "—"),
                Paragraph(result_text, result_style),
            ])
        qt_t = Table(qt_data, colWidths=[42*mm, 46*mm, 36*mm, 26*mm, 24*mm])
        qt_t.setStyle(TableStyle([
            ("BACKGROUND",     (0,0), (-1,0), DARK),
            ("FONTSIZE",       (0,0), (-1,-1), 8),
            ("GRID",           (0,0), (-1,-1), 0.3, colors.HexColor("#cbd5e1")),
            ("ROWBACKGROUNDS", (0,1), (-1,-1), [WHITE, colors.HexColor("#f8fafc")]),
            ("TOPPADDING",     (0,0), (-1,-1), 5),
            ("BOTTOMPADDING",  (0,0), (-1,-1), 5),
            ("LEFTPADDING",    (0,0), (-1,-1), 5),
            ("VALIGN",         (0,0), (-1,-1), "TOP"),
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
        # 174mm: 100+74
        sig_data = [
            [_p("Authorised Signatory", _CELL_BOLD), _p("Date", _CELL_BOLD)],
            [_p(" " * 50), _p(str(date.today()))],
        ]
        sig_t = Table(sig_data, colWidths=[100*mm, 74*mm])
        sig_t.setStyle(TableStyle([
            ("FONTSIZE",      (0,0), (-1,-1), 8),
            ("LINEBELOW",     (0,1), (0,1), 0.5, DARK),
            ("TOPPADDING",    (0,0), (-1,-1), 4),
            ("BOTTOMPADDING", (0,0), (-1,-1), 12),
            ("VALIGN",        (0,0), (-1,-1), "TOP"),
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
