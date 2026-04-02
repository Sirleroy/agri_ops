"""
AgriOps Compliance Report — PDF Generator
Produces a full EUDR traceability report for a given company.
Uses ReportLab. Called from the reports view.
"""
from io import BytesIO
from datetime import date

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable, KeepTogether
)
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT


# ── Colour palette ────────────────────────────────────────────
DARK        = colors.HexColor("#0a0f1a")
SURFACE     = colors.HexColor("#131f2e")
GREEN       = colors.HexColor("#22c55e")
GREEN_LIGHT = colors.HexColor("#dcfce7")
SLATE_700   = colors.HexColor("#334155")
SLATE_500   = colors.HexColor("#64748b")
SLATE_300   = colors.HexColor("#cbd5e1")
WHITE       = colors.white
RED_LIGHT   = colors.HexColor("#fee2e2")
RED         = colors.HexColor("#ef4444")
YELLOW_LIGHT= colors.HexColor("#fef9c3")
ORANGE_LIGHT= colors.HexColor("#ffedd5")


def _styles():
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle(
            "title", fontName="Helvetica-Bold", fontSize=20,
            textColor=DARK, spaceBefore=2*mm, spaceAfter=3*mm
        ),
        "subtitle": ParagraphStyle(
            "subtitle", fontName="Helvetica", fontSize=10,
            textColor=SLATE_500, spaceAfter=6*mm
        ),
        "section": ParagraphStyle(
            "section", fontName="Helvetica-Bold", fontSize=11,
            textColor=DARK, spaceBefore=6*mm, spaceAfter=3*mm
        ),
        "body": ParagraphStyle(
            "body", fontName="Helvetica", fontSize=9,
            textColor=SLATE_700, spaceAfter=2*mm
        ),
        "small": ParagraphStyle(
            "small", fontName="Helvetica", fontSize=8,
            textColor=SLATE_500
        ),
        "footer": ParagraphStyle(
            "footer", fontName="Helvetica", fontSize=7,
            textColor=SLATE_500, alignment=TA_CENTER
        ),
    }


def _header_table(company, generated_by, st):
    """Top header — company name + report metadata."""
    left_rows = [
        [Paragraph("AGRIOPS", ParagraphStyle("ag", fontName="Helvetica-Bold",
                   fontSize=9, textColor=GREEN))],
        [Paragraph("EUDR Compliance Report", st["title"])],
        [Paragraph(f"Operator: {company.name}  ·  {company.city}, {company.country}", st["subtitle"])],
    ]
    left_t = Table(left_rows, colWidths=[118*mm])
    left_t.setStyle(TableStyle([
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 1), (0, 1), 9),  # space below title to clear subtitle
    ]))

    right_text = (
        f"Generated: {date.today().strftime('%d %B %Y')}<br/>"
        f"By: {generated_by}<br/>"
        f"<b>CONFIDENTIAL</b>"
    )
    right_para = Paragraph(
        right_text,
        ParagraphStyle("conf_r", fontName="Helvetica", fontSize=8,
                       textColor=SLATE_500, alignment=TA_RIGHT)
    )

    t = Table([[left_t, right_para]], colWidths=[120*mm, 60*mm])
    t.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    return t


def _kv_table(rows, col_widths=None):
    """Two-column key-value table."""
    if col_widths is None:
        col_widths = [55*mm, 120*mm]
    st = _styles()
    data = [[Paragraph(k, st["small"]), Paragraph(str(v), st["body"])] for k, v in rows]
    t = Table(data, colWidths=col_widths)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (0,-1), colors.HexColor("#f8fafc")),
        ("FONTNAME", (0,0), (0,-1), "Helvetica-Bold"),
        ("FONTSIZE", (0,0), (-1,-1), 8),
        ("TEXTCOLOR", (0,0), (0,-1), SLATE_500),
        ("TEXTCOLOR", (1,0), (1,-1), SLATE_700),
        ("GRID", (0,0), (-1,-1), 0.3, SLATE_300),
        ("TOPPADDING", (0,0), (-1,-1), 3),
        ("BOTTOMPADDING", (0,0), (-1,-1), 3),
        ("LEFTPADDING", (0,0), (-1,-1), 4),
    ]))
    return t


def _farm_status_color(farm):
    status = farm.compliance_status
    if status == "compliant":
        return GREEN_LIGHT, GREEN
    elif status == "high_risk":
        return RED_LIGHT, RED
    elif status == "expired":
        return ORANGE_LIGHT, colors.HexColor("#f97316")
    return YELLOW_LIGHT, colors.HexColor("#ca8a04")


def generate_compliance_report(company, user, filters=None):
    """
    Generate a PDF compliance report for the given company.
    Accepts optional filters dict:
      - sales_order: SalesOrder instance — filter to a single order
      - date_from: date — filter purchase/sales orders from this date
      - date_to: date — filter purchase/sales orders to this date
    Returns a BytesIO buffer ready to stream as HTTP response.
    """
    if filters is None:
        filters = {}
    from apps.suppliers.models import Supplier, Farm
    from apps.purchase_orders.models import PurchaseOrder
    from apps.sales_orders.models import SalesOrder

    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4,
        leftMargin=18*mm, rightMargin=18*mm,
        topMargin=18*mm, bottomMargin=18*mm,
        title=f"EUDR Compliance Report — {company.name}"
    )

    st = _styles()
    story = []

    # ── Header ────────────────────────────────────────────────
    story.append(_header_table(company, user.get_full_name() or user.username, st))
    story.append(HRFlowable(width="100%", thickness=1, color=GREEN, spaceAfter=4*mm))

    # Filter summary banner
    if filters:
        filter_parts = []
        if filters.get('sales_order'):
            filter_parts.append(f"Sales Order: {filters['sales_order'].order_number}")
        if filters.get('customer_name'):
            filter_parts.append(f"Buyer: {filters['customer_name']}")
        if filters.get('date_from'):
            filter_parts.append(f"From: {filters['date_from']}")
        if filters.get('date_to'):
            filter_parts.append(f"To: {filters['date_to']}")
        if filter_parts:
            story.append(Paragraph(
                f"Filter applied: {' · '.join(filter_parts)}",
                ParagraphStyle("filter", fontName="Helvetica", fontSize=9,
                               textColor=GREEN, spaceAfter=4*mm)
            ))

    # ── Company summary ───────────────────────────────────────
    story.append(Paragraph("1. Operator Details", st["section"]))
    story.append(_kv_table([
        ("Company Name", company.name),
        ("Country", company.country),
        ("City / Region", company.city or "—"),
        ("Contact Email", company.email or "—"),
        ("Contact Phone", company.phone or "—"),
        ("Report Date", date.today().strftime("%d %B %Y")),
    ]))

    # ── Supplier summary ──────────────────────────────────────
    suppliers = Supplier.objects.filter(company=company, is_active=True)
    story.append(Paragraph("2. Supplier Network", st["section"]))
    story.append(Paragraph(
        f"Total active suppliers: <b>{suppliers.count()}</b>", st["body"]
    ))

    if suppliers.exists():
        sup_data = [["Supplier", "Category", "Email", "Country", "Address"]]
        for s in suppliers:
            sup_data.append([
                s.name,
                s.get_category_display(),
                s.email or "—",
                s.country or "—",
                s.address or s.city or "—",
            ])
        sup_t = Table(sup_data, colWidths=[52*mm, 28*mm, 42*mm, 26*mm, 26*mm])
        sup_t.setStyle(TableStyle([
            ("BACKGROUND", (0,0), (-1,0), DARK),
            ("TEXTCOLOR", (0,0), (-1,0), WHITE),
            ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"),
            ("FONTSIZE", (0,0), (-1,-1), 8),
            ("GRID", (0,0), (-1,-1), 0.3, SLATE_300),
            ("ROWBACKGROUNDS", (0,1), (-1,-1), [WHITE, colors.HexColor("#f8fafc")]),
            ("TOPPADDING", (0,0), (-1,-1), 3),
            ("BOTTOMPADDING", (0,0), (-1,-1), 3),
            ("LEFTPADDING", (0,0), (-1,-1), 4),
        ]))
        story.append(sup_t)

    # ── Farm traceability ─────────────────────────────────────
    farms = Farm.objects.filter(company=company).select_related("supplier", "mapped_by", "verified_by")
    story.append(Paragraph("3. Farm Traceability Records", st["section"]))
    story.append(Paragraph(
        f"Total farms registered: <b>{farms.count()}</b>  ·  "
        f"EUDR Verified: <b>{farms.filter(is_eudr_verified=True).count()}</b>  ·  "
        f"Pending: <b>{farms.filter(is_eudr_verified=False).count()}</b>",
        st["body"]
    ))
    story.append(Spacer(1, 3*mm))

    for farm in farms:
        bg, accent = _farm_status_color(farm)
        block = []
        block.append(Paragraph(f"Farm: {farm.name}", ParagraphStyle(
            "fh", fontName="Helvetica-Bold", fontSize=10, textColor=DARK
        )))
        farmer_display = (
            farm.farmer.full_name if farm.farmer
            else farm.farmer_name or "—"
        )
        cleared = farm.land_cleared_after_cutoff
        cleared_display = "YES — DISQUALIFIED ⚠" if cleared is True else ("NO" if cleared is False else "—")
        block.append(_kv_table([
            ("Supplier",                    farm.supplier.name if farm.supplier else "—"),
            ("Farmer",                      farmer_display),
            ("Commodity",                   farm.commodity),
            ("Country / Region",            f"{farm.country} / {farm.state_region or '—'}"),
            ("Area",                        f"{farm.area_hectares} ha" if farm.area_hectares else "—"),
            ("Harvest Year",                str(farm.harvest_year) if farm.harvest_year else "—"),
            ("Deforestation Ref. Date",     str(farm.deforestation_reference_date) if farm.deforestation_reference_date else "—"),
            ("Land Cleared After Cutoff",   cleared_display),
            ("Risk Classification",         farm.get_deforestation_risk_status_display()),
            ("Mapping Date",                str(farm.mapping_date) if farm.mapping_date else "—"),
            ("Mapped By",                   str(farm.mapped_by) if farm.mapped_by else "—"),
            ("EUDR Verified",               "YES" if farm.is_eudr_verified else "NO"),
            ("Verified By",                 str(farm.verified_by) if farm.verified_by else "—"),
            ("Verification Date",           str(farm.verified_date) if farm.verified_date else "—"),
            ("Verification Expiry",         str(farm.verification_expiry) if farm.verification_expiry else "—"),
            ("Compliance Status",           farm.compliance_status.upper()),
            ("GeoJSON Present",             "YES" if farm.geolocation else "NO"),
        ]))
        story.append(KeepTogether(block))
        story.append(Spacer(1, 4*mm))

    # ── Purchase orders ───────────────────────────────────────
    # ── Apply filters to orders ───────────────────────────────
    po_qs = PurchaseOrder.objects.filter(company=company).select_related("supplier").order_by("-created_at")
    so_qs = SalesOrder.objects.filter(company=company).order_by("-created_at")

    if filters.get('sales_order'):
        so_qs = so_qs.filter(pk=filters['sales_order'].pk)
        po_qs = po_qs.none()

    elif filters.get('customer_name'):
        # Scope to a single buyer: filter SOs, then resolve farms via Batch links
        so_qs = so_qs.filter(customer_name=filters['customer_name'])
        from apps.sales_orders.models import Batch
        farm_ids = (
            Batch.objects
            .filter(company=company, sales_order__in=so_qs)
            .values_list('farms', flat=True)
            .distinct()
        )
        farms = farms.filter(pk__in=farm_ids)

    if filters.get('date_from'):
        po_qs = po_qs.filter(order_date__gte=filters['date_from'])
        so_qs = so_qs.filter(order_date__gte=filters['date_from'])

    if filters.get('date_to'):
        po_qs = po_qs.filter(order_date__lte=filters['date_to'])
        so_qs = so_qs.filter(order_date__lte=filters['date_to'])

    pos = po_qs[:20]
    story.append(Paragraph("4. Recent Purchase Orders", st["section"]))

    if pos.exists():
        po_data = [["Order Number", "Supplier", "Status", "Order Date"]]
        for po in pos:
            po_data.append([
                po.order_number,
                po.supplier.name if po.supplier else "—",
                po.get_status_display(),
                str(po.order_date),
            ])
        po_t = Table(po_data, colWidths=[45*mm, 65*mm, 30*mm, 35*mm])
        po_t.setStyle(TableStyle([
            ("BACKGROUND", (0,0), (-1,0), DARK),
            ("TEXTCOLOR", (0,0), (-1,0), WHITE),
            ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"),
            ("FONTSIZE", (0,0), (-1,-1), 8),
            ("GRID", (0,0), (-1,-1), 0.3, SLATE_300),
            ("ROWBACKGROUNDS", (0,1), (-1,-1), [WHITE, colors.HexColor("#f8fafc")]),
            ("TOPPADDING", (0,0), (-1,-1), 3),
            ("BOTTOMPADDING", (0,0), (-1,-1), 3),
            ("LEFTPADDING", (0,0), (-1,-1), 4),
        ]))
        story.append(po_t)
    else:
        story.append(Paragraph("No purchase orders recorded.", st["body"]))

    # ── Batch / DDS summary ───────────────────────────────────
    from apps.sales_orders.models import Batch
    batch_qs = Batch.objects.filter(company=company).select_related('sales_order').prefetch_related('farms').order_by('-created_at')
    if filters.get('sales_order'):
        batch_qs = batch_qs.filter(sales_order=filters['sales_order'])
    story.append(Paragraph("5. Batch Traceability & DDS Summary", st["section"]))
    story.append(Paragraph(
        f"Total batches: <b>{batch_qs.count()}</b>  ·  "
        f"Locked (submitted): <b>{batch_qs.filter(is_locked=True).count()}</b>  ·  "
        f"Pending: <b>{batch_qs.filter(is_locked=False).count()}</b>",
        st["body"]
    ))
    story.append(Spacer(1, 3*mm))
    if batch_qs.exists():
        batch_data = [["Batch Number", "Commodity", "Qty (kg)", "Linked Farms", "Sales Order", "Status"]]
        for b in batch_qs[:30]:
            farm_names = ", ".join(f.name for f in b.farms.all()) or "—"
            so_ref = b.sales_order.order_number if b.sales_order else "—"
            batch_data.append([
                b.batch_number,
                b.commodity,
                str(b.quantity_kg) if b.quantity_kg else "—",
                farm_names,
                so_ref,
                "LOCKED" if b.is_locked else "Open",
            ])
        b_t = Table(batch_data, colWidths=[38*mm, 22*mm, 18*mm, 42*mm, 28*mm, 18*mm])
        b_t.setStyle(TableStyle([
            ("BACKGROUND", (0,0), (-1,0), DARK),
            ("TEXTCOLOR", (0,0), (-1,0), WHITE),
            ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"),
            ("FONTSIZE", (0,0), (-1,-1), 8),
            ("GRID", (0,0), (-1,-1), 0.3, SLATE_300),
            ("ROWBACKGROUNDS", (0,1), (-1,-1), [WHITE, colors.HexColor("#f8fafc")]),
            ("TOPPADDING", (0,0), (-1,-1), 3),
            ("BOTTOMPADDING", (0,0), (-1,-1), 3),
            ("LEFTPADDING", (0,0), (-1,-1), 4),
        ]))
        story.append(b_t)
    else:
        story.append(Paragraph("No batches recorded.", st["body"]))

    # ── Sales orders ──────────────────────────────────────────
    sos = so_qs[:20]
    story.append(Paragraph("6. Recent Sales Orders", st["section"]))
    if sos.exists():
        so_data = [["Order Number", "Customer", "Status", "Order Date"]]
        for so in sos:
            so_data.append([
                so.order_number,
                so.customer_name,
                so.get_status_display(),
                str(so.order_date),
            ])
        so_t = Table(so_data, colWidths=[45*mm, 65*mm, 30*mm, 35*mm])
        so_t.setStyle(TableStyle([
            ("BACKGROUND", (0,0), (-1,0), DARK),
            ("TEXTCOLOR", (0,0), (-1,0), WHITE),
            ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"),
            ("FONTSIZE", (0,0), (-1,-1), 8),
            ("GRID", (0,0), (-1,-1), 0.3, SLATE_300),
            ("ROWBACKGROUNDS", (0,1), (-1,-1), [WHITE, colors.HexColor("#f8fafc")]),
            ("TOPPADDING", (0,0), (-1,-1), 3),
            ("BOTTOMPADDING", (0,0), (-1,-1), 3),
            ("LEFTPADDING", (0,0), (-1,-1), 4),
        ]))
        story.append(so_t)
    else:
        story.append(Paragraph("No sales orders recorded.", st["body"]))

    # ── Declaration ───────────────────────────────────────────
    story.append(Spacer(1, 6*mm))
    story.append(HRFlowable(width="100%", thickness=0.5, color=SLATE_300, spaceAfter=4*mm))
    story.append(Paragraph("7. Due Diligence Declaration", st["section"]))
    story.append(Paragraph(
        f"The operator <b>{company.name}</b> hereby declares that to the best of their knowledge, "
        "all commodities listed in this report have been sourced in compliance with the EU Deforestation "
        "Regulation (EU) 2023/1115. Farm-level geolocation data, risk assessments, and supporting "
        "documentation have been collected and are retained in the AgriOps platform for audit purposes.",
        st["body"]
    ))
    story.append(Spacer(1, 8*mm))

    sig_data = [
        ["Authorised Signatory", "Date", "Position"],
        [" " * 40, str(date.today()), user.job_title or user.get_full_name() or user.username],
    ]
    sig_t = Table(sig_data, colWidths=[80*mm, 45*mm, 55*mm])
    sig_t.setStyle(TableStyle([
        ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"),
        ("FONTSIZE", (0,0), (-1,-1), 8),
        ("TEXTCOLOR", (0,0), (-1,0), SLATE_500),
        ("BOX", (0,1), (0,1), 0.5, SLATE_300),
        ("LINEBELOW", (0,1), (0,1), 0.5, DARK),
        ("TOPPADDING", (0,0), (-1,-1), 4),
        ("BOTTOMPADDING", (0,0), (-1,-1), 8),
    ]))
    story.append(sig_t)

    # ── Footer note ───────────────────────────────────────────
    story.append(Spacer(1, 4*mm))
    story.append(Paragraph(
        f"Generated by AgriOps · app.agriops.io · {date.today().strftime('%d %B %Y')} · "
        "This document is produced from data held in the AgriOps platform and is intended for "
        "EU buyer compliance submissions under EUDR Regulation 2023/1115.",
        st["footer"]
    ))

    doc.build(story)
    buffer.seek(0)
    return buffer
