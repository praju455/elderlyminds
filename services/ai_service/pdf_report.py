"""Branded Bhumi PDF wellness report generator."""
from __future__ import annotations

import io
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def generate_wellness_pdf(
    *,
    user_name: str,
    user_age: int | str,
    user_language: str,
    user_region: str,
    report_data: dict[str, Any],
    medicines: list[dict[str, Any]],
    recent_alerts: list[dict[str, Any]],
    out_dir: str,
) -> str:
    """Generate a branded Bhumi wellness PDF report. Returns the filename."""
    try:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
        from reportlab.lib.units import cm, mm
        from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
    except ImportError:
        raise RuntimeError("reportlab is required for PDF generation. Install with: pip install reportlab")

    Path(out_dir).mkdir(parents=True, exist_ok=True)
    filename = f"bhumi-report-{uuid.uuid4().hex[:8]}.pdf"
    filepath = Path(out_dir) / filename

    doc = SimpleDocTemplate(
        str(filepath),
        pagesize=A4,
        topMargin=2 * cm,
        bottomMargin=2 * cm,
        leftMargin=2 * cm,
        rightMargin=2 * cm,
    )

    styles = getSampleStyleSheet()
    brand_green = colors.HexColor("#3B8C6E")
    brand_dark = colors.HexColor("#1A1A2E")
    light_bg = colors.HexColor("#F0F7F4")

    title_style = ParagraphStyle(
        "BhumiTitle", parent=styles["Title"],
        fontSize=22, textColor=brand_green, spaceAfter=6,
    )
    subtitle_style = ParagraphStyle(
        "BhumiSubtitle", parent=styles["Normal"],
        fontSize=11, textColor=colors.grey, spaceAfter=12,
    )
    heading_style = ParagraphStyle(
        "BhumiHeading", parent=styles["Heading2"],
        fontSize=14, textColor=brand_dark, spaceBefore=16, spaceAfter=8,
    )
    body_style = ParagraphStyle(
        "BhumiBody", parent=styles["Normal"],
        fontSize=10, textColor=brand_dark, spaceAfter=4, leading=14,
    )
    small_style = ParagraphStyle(
        "BhumiSmall", parent=styles["Normal"],
        fontSize=8, textColor=colors.grey, spaceAfter=2,
    )

    now = datetime.now(timezone.utc).strftime("%d %B %Y, %H:%M UTC")
    week_start = report_data.get("week_start", "")
    week_end = report_data.get("week_end", "")

    elements: list = []

    # Header / Branding
    elements.append(Paragraph("BHUMI", title_style))
    elements.append(Paragraph("Elder Wellness Report", subtitle_style))
    elements.append(Spacer(1, 4 * mm))

    # User info table
    user_info = [
        ["Name", str(user_name), "Age", str(user_age)],
        ["Language", str(user_language), "Region", str(user_region)],
        ["Report period", f"{week_start} to {week_end}", "Generated", now],
    ]
    info_table = Table(user_info, colWidths=[3 * cm, 5.5 * cm, 3 * cm, 5.5 * cm])
    info_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), light_bg),
        ("TEXTCOLOR", (0, 0), (0, -1), brand_green),
        ("TEXTCOLOR", (2, 0), (2, -1), brand_green),
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTNAME", (2, 0), (2, -1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#D0E8DC")),
        ("ROUNDEDCORNERS", [4, 4, 4, 4]),
    ]))
    elements.append(info_table)
    elements.append(Spacer(1, 6 * mm))

    # Wellness overview
    elements.append(Paragraph("Wellness Overview", heading_style))
    mood_score = report_data.get("mood_score", 0)
    sleep_hours = report_data.get("sleep_hours", 0)
    steps = report_data.get("activity_steps_per_day", 0)
    adherence = report_data.get("medicine_adherence", 0)
    alert_count = report_data.get("alert_count", 0)

    overview_data = [
        ["Mood Score", "Sleep (avg)", "Steps (avg/day)", "Medicine Adherence", "Alerts"],
        [f"{mood_score}/100", f"{sleep_hours}h", str(steps), f"{adherence}%", str(alert_count)],
    ]
    overview_table = Table(overview_data, colWidths=[3.4 * cm] * 5)
    overview_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), brand_green),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 9),
        ("FONTSIZE", (0, 1), (-1, 1), 12),
        ("FONTNAME", (0, 1), (-1, 1), "Helvetica-Bold"),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#D0E8DC")),
    ]))
    elements.append(overview_table)
    elements.append(Spacer(1, 4 * mm))

    # Mood trend
    mood_trend = report_data.get("mood_trend", [])
    if mood_trend:
        elements.append(Paragraph("Mood Trend (7 days)", heading_style))
        trend_bar = " → ".join(str(v) for v in mood_trend)
        elements.append(Paragraph(trend_bar, body_style))
        elements.append(Spacer(1, 2 * mm))

    # Health issues
    health_issues = report_data.get("health_issues", [])
    if health_issues:
        elements.append(Paragraph("Health Issues Detected", heading_style))
        for issue in health_issues:
            elements.append(Paragraph(f"• {issue}", body_style))
        elements.append(Spacer(1, 2 * mm))

    # Medicines
    if medicines:
        elements.append(Paragraph("Current Medicine Plan", heading_style))
        med_header = ["Medicine", "Dose", "Times", "Instructions"]
        med_rows = [med_header]
        for med in medicines[:10]:
            med_rows.append([
                str(med.get("name", "")),
                str(med.get("dose", "")),
                ", ".join(med.get("times", [])),
                str(med.get("instructions", "")),
            ])
        med_table = Table(med_rows, colWidths=[4.5 * cm, 3 * cm, 4.5 * cm, 5 * cm])
        med_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), brand_green),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ("LEFTPADDING", (0, 0), (-1, -1), 6),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#D0E8DC")),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, light_bg]),
        ]))
        elements.append(med_table)
        elements.append(Spacer(1, 4 * mm))

    # Recommendations
    recommendations = report_data.get("recommendations", [])
    if recommendations:
        elements.append(Paragraph("Recommendations", heading_style))
        for rec in recommendations:
            elements.append(Paragraph(f"• {rec}", body_style))
        elements.append(Spacer(1, 4 * mm))

    # Recent alerts
    if recent_alerts:
        elements.append(Paragraph("Recent Alerts", heading_style))
        for alert in recent_alerts[:6]:
            severity = alert.get("severity", "")
            msg = alert.get("message", "")
            ts = alert.get("time_created", "")
            elements.append(Paragraph(f"• [{severity}] {msg} ({ts[:16]})", body_style))
        elements.append(Spacer(1, 4 * mm))

    # Footer
    elements.append(Spacer(1, 8 * mm))
    elements.append(Paragraph(
        "This report was generated by Bhumi, an AI-powered elder care companion. "
        "It is not a medical document. Please consult a healthcare professional for clinical decisions.",
        small_style,
    ))
    elements.append(Paragraph(f"Bhumi Elder Wellness Platform | Generated {now}", small_style))

    doc.build(elements)
    return filename
