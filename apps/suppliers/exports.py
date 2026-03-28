"""
Supplier app exports — Farmer Registry and Farm Registry.
Produces branded CSV and PDF downloads for tenant data.
"""
import csv
from io import BytesIO
from datetime import date

from django.http import HttpResponse

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
)
from reportlab.lib.enums import TA_CENTER, TA_RIGHT


# ── Shared colour palette (matches AgriOps design system) ─────────────────────
DARK     = colors.HexColor("#0a0f1a")
SURFACE  = colors.HexColor("#131f2e")
GREEN    = colors.HexColor("#22c55e")
SLATE_700 = colors.HexColor("#334155")
SLATE_500 = colors.HexColor("#64748b")
SLATE_300 = colors.HexColor("#cbd5e1")
WHITE    = colors.white
GREEN_LIGHT  = colors.HexColor("#dcfce7")
YELLOW_LIGHT = colors.HexColor("#fef9c3")
RED_LIGHT    = colors.HexColor("#fee2e2")
ORANGE_LIGHT = colors.HexColor("#ffedd5")


def _styles():
    return {
        "brand": ParagraphStyle("brand", fontName="Helvetica-Bold", fontSize=9,
                                textColor=GREEN),
        "title": ParagraphStyle("title", fontName="Helvetica-Bold", fontSize=18,
                                textColor=DARK, spaceAfter=1*mm),
        "subtitle": ParagraphStyle("subtitle", fontName="Helvetica", fontSize=9,
                                   textColor=SLATE_500, spaceAfter=5*mm),
        "meta": ParagraphStyle("meta", fontName="Helvetica", fontSize=8,
                               textColor=SLATE_500),
        "footer": ParagraphStyle("footer", fontName="Helvetica", fontSize=7,
                                 textColor=SLATE_500, alignment=TA_CENTER),
    }


def _page_footer(canvas, doc):
    """Page number + branding in the footer margin."""
    canvas.saveState()
    canvas.setFont("Helvetica", 7)
    canvas.setFillColor(SLATE_500)
    canvas.drawCentredString(
        A4[0] / 2, 10*mm,
        f"AgriOps · app.agriops.io · Page {doc.page}"
    )
    canvas.restoreState()


def _page_footer_landscape(canvas, doc):
    canvas.saveState()
    canvas.setFont("Helvetica", 7)
    canvas.setFillColor(SLATE_500)
    canvas.drawCentredString(
        landscape(A4)[0] / 2, 10*mm,
        f"AgriOps · app.agriops.io · Page {doc.page}"
    )
    canvas.restoreState()


def _doc_header(company, title, subtitle, st):
    """Standard AgriOps branded header block."""
    # Use a nested single-column table for the left side to avoid
    # ReportLab's unreliable list-in-cell rendering.
    left_rows = [
        [Paragraph("AGRIOPS", st["brand"])],
        [Paragraph(title, st["title"])],
        [Paragraph(subtitle, st["subtitle"])],
    ]
    left_t = Table(left_rows, colWidths=[118*mm])
    left_t.setStyle(TableStyle([
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
    ]))

    right_text = (
        f"Company: {company.name}<br/>"
        f"Generated: {date.today().strftime('%d %B %Y')}<br/>"
        f"<b>CONFIDENTIAL</b>"
    )
    right_para = Paragraph(
        right_text,
        ParagraphStyle("meta_r", fontName="Helvetica", fontSize=8,
                       textColor=SLATE_500, alignment=TA_RIGHT)
    )

    t = Table([[left_t, right_para]], colWidths=[120*mm, 55*mm])
    t.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    return t


def _table_style(col_count):
    """Standard data table style."""
    return TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), DARK),
        ("TEXTCOLOR", (0, 0), (-1, 0), WHITE),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
        ("TEXTCOLOR", (0, 1), (-1, -1), SLATE_700),
        ("GRID", (0, 0), (-1, -1), 0.3, SLATE_300),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [WHITE, colors.HexColor("#f8fafc")]),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ])


# ── FARMER REGISTRY ───────────────────────────────────────────────────────────

def farmer_registry_csv(company):
    """Returns an HttpResponse with the farmer registry as a CSV download."""
    from .models import Farmer
    farmers = Farmer.objects.filter(company=company).prefetch_related('farms').order_by('name')

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = (
        f'attachment; filename="AgriOps_Farmer_Registry_{date.today()}.csv"'
    )

    writer = csv.writer(response)
    writer.writerow([
        'Full Name', 'Phone', 'Village', 'LGA', 'NIN',
        'Number of Farms', 'Registered Date'
    ])

    for f in farmers:
        writer.writerow([
            f.name,
            f.phone or '—',
            f.village or '—',
            f.lga or '—',
            f.nin or '—',
            f.farms.count(),
            f.created_at.strftime('%d %B %Y'),
        ])

    return response


def farmer_registry_pdf(company):
    """Returns an HttpResponse with the farmer registry as a branded PDF download."""
    from .models import Farmer
    farmers = Farmer.objects.filter(company=company).prefetch_related('farms').order_by('name')

    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4,
        leftMargin=18*mm, rightMargin=18*mm,
        topMargin=18*mm, bottomMargin=20*mm,
        title=f"Farmer Registry — {company.name}",
    )

    st = _styles()
    story = []

    story.append(_doc_header(
        company,
        "Farmer Registry",
        f"Complete farmer onboarding register · {farmers.count()} farmer{'s' if farmers.count() != 1 else ''} · {date.today().strftime('%d %B %Y')}",
        st,
    ))
    story.append(HRFlowable(width="100%", thickness=1, color=GREEN, spaceAfter=5*mm))

    if farmers.exists():
        data = [["Full Name", "Phone", "Village", "LGA", "NIN", "Farms", "Registered"]]
        for f in farmers:
            data.append([
                f.name,
                f.phone or "—",
                f.village or "—",
                f.lga or "—",
                f.nin or "—",
                str(f.farms.count()),
                f.created_at.strftime("%d %b %Y"),
            ])

        col_widths = [42*mm, 25*mm, 28*mm, 28*mm, 28*mm, 13*mm, 24*mm]
        t = Table(data, colWidths=col_widths, repeatRows=1)
        t.setStyle(_table_style(len(col_widths)))
        story.append(t)
    else:
        story.append(Paragraph("No farmers registered.", st["meta"]))

    story.append(Spacer(1, 8*mm))
    story.append(Paragraph(
        "This document contains confidential farmer data. Handle in accordance with your data protection policy.",
        st["footer"]
    ))

    doc.build(story, onFirstPage=_page_footer, onLaterPages=_page_footer)
    buffer.seek(0)

    response = HttpResponse(buffer, content_type='application/pdf')
    response['Content-Disposition'] = (
        f'attachment; filename="AgriOps_Farmer_Registry_{date.today()}.pdf"'
    )
    return response


# ── FARM REGISTRY ─────────────────────────────────────────────────────────────

def farm_registry_csv(company):
    """Returns an HttpResponse with the farm registry as a CSV download."""
    from .models import Farm
    farms = Farm.objects.filter(company=company).select_related(
        'supplier', 'farmer'
    ).order_by('name')

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = (
        f'attachment; filename="AgriOps_Farm_Registry_{date.today()}.csv"'
    )

    writer = csv.writer(response)
    writer.writerow([
        'Farm / Plot Name', 'Farmer', 'Supplier', 'Commodity',
        'Area (ha)', 'Country', 'State / Region',
        'Deforestation Risk', 'EUDR Status', 'Verification Expiry',
        'Harvest Year', 'Mapping Date',
    ])

    STATUS_LABELS = {
        'compliant': 'Verified',
        'expired': 'Expired',
        'high_risk': 'High Risk',
        'disqualified': 'Disqualified',
        'pending': 'Pending',
    }

    for farm in farms:
        writer.writerow([
            farm.name,
            farm.farmer.name if farm.farmer else '—',
            farm.supplier.name if farm.supplier else '—',
            farm.commodity,
            farm.area_hectares or '—',
            farm.country,
            farm.state_region or '—',
            farm.get_deforestation_risk_status_display(),
            STATUS_LABELS.get(farm.compliance_status, 'Pending'),
            farm.verification_expiry.strftime('%d %B %Y') if farm.verification_expiry else '—',
            farm.harvest_year or '—',
            farm.mapping_date.strftime('%d %B %Y') if farm.mapping_date else '—',
        ])

    return response


def farm_registry_pdf(company):
    """Returns an HttpResponse with the farm registry as a branded PDF download."""
    from .models import Farm
    farms = Farm.objects.filter(company=company).select_related(
        'supplier', 'farmer'
    ).order_by('name')

    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=landscape(A4),
        leftMargin=18*mm, rightMargin=18*mm,
        topMargin=18*mm, bottomMargin=20*mm,
        title=f"Farm Registry — {company.name}",
    )

    st = _styles()
    story = []

    story.append(_doc_header(
        company,
        "Farm Registry",
        f"EUDR farm & geolocation register · {farms.count()} farm{'s' if farms.count() != 1 else ''} · {date.today().strftime('%d %B %Y')}",
        st,
    ))
    story.append(HRFlowable(width="100%", thickness=1, color=GREEN, spaceAfter=5*mm))

    STATUS_LABELS = {
        'compliant': 'Verified',
        'expired': 'Expired',
        'high_risk': 'High Risk',
        'disqualified': 'Disqualified',
        'pending': 'Pending',
    }
    STATUS_COLORS = {
        'compliant': GREEN_LIGHT,
        'expired': ORANGE_LIGHT,
        'high_risk': RED_LIGHT,
        'disqualified': RED_LIGHT,
        'pending': YELLOW_LIGHT,
    }

    if farms.exists():
        data = [[
            "Farm / Plot Name", "Farmer", "Supplier", "Commodity",
            "Area (ha)", "Country / State", "EUDR Status", "Expiry"
        ]]
        for farm in farms:
            data.append([
                farm.name,
                farm.farmer.name if farm.farmer else "—",
                farm.supplier.name if farm.supplier else "—",
                farm.commodity,
                str(farm.area_hectares) if farm.area_hectares else "—",
                f"{farm.country}" + (f" / {farm.state_region}" if farm.state_region else ""),
                STATUS_LABELS.get(farm.compliance_status, "Pending"),
                farm.verification_expiry.strftime("%d %b %Y") if farm.verification_expiry else "—",
            ])

        col_widths = [48*mm, 32*mm, 38*mm, 24*mm, 16*mm, 38*mm, 22*mm, 22*mm]
        t = Table(data, colWidths=col_widths, repeatRows=1)
        style = _table_style(len(col_widths))

        # Colour-code EUDR status column (index 6) per row
        for i, farm in enumerate(farms, start=1):
            bg = STATUS_COLORS.get(farm.compliance_status, YELLOW_LIGHT)
            style.add("BACKGROUND", (6, i), (6, i), bg)

        t.setStyle(style)
        story.append(t)
    else:
        story.append(Paragraph("No farms registered.", st["meta"]))

    story.append(Spacer(1, 8*mm))
    story.append(Paragraph(
        "This document contains confidential farm and geolocation data. Handle in accordance with your EUDR compliance obligations.",
        st["footer"]
    ))

    doc.build(story, onFirstPage=_page_footer_landscape, onLaterPages=_page_footer_landscape)
    buffer.seek(0)

    response = HttpResponse(buffer, content_type='application/pdf')
    response['Content-Disposition'] = (
        f'attachment; filename="AgriOps_Farm_Registry_{date.today()}.pdf"'
    )
    return response
