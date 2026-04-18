#!/usr/bin/env python3
"""
Kavik Works — Feasibility Study Generator

Takes intake form data and produces a professional PDF feasibility study.

Usage:
    python generate_feasibility.py --input intake_data.json --output study.pdf

Input JSON format matches the intake form field names:
{
    "contact_name": "Jane Smith",
    "contact_email": "jane@company.com",
    "contact_phone": "(555) 123-4567",
    "contact_method": "email",
    "business_name": "Acme Corp",
    "business_website": "https://acme.com",
    "industry": "real_estate",
    "team_size": "6-15",
    "pain_points": ["inbox_management", "lead_response", "data_entry"],
    "workflow_description": "A lead emails our info@ address...",
    "volume": "11-50",
    "hours_per_week": "5-10",
    "tools": ["gmail", "spreadsheets", "crm"],
    "pricing_tier": "pilot",
    "timeline": "asap",
    "additional_notes": "We tried Zapier but it didn't work well.",
    "referral_source": "search"
}
"""

import json
import argparse
import textwrap
from datetime import datetime, timedelta
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.lib.colors import HexColor
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, PageBreak,
    Table, TableStyle, HRFlowable
)
from reportlab.pdfgen import canvas
from reportlab.lib import colors


# ── Design Tokens ──────────────────────────────────────────────

DARK = HexColor("#0a0a0a")
GRAY_800 = HexColor("#262626")
GRAY_600 = HexColor("#525252")
GRAY_500 = HexColor("#737373")
GRAY_400 = HexColor("#a3a3a3")
GRAY_200 = HexColor("#e5e5e5")
WHITE = HexColor("#ffffff")
ACCENT = HexColor("#2563eb")  # Blue for highlights
GREEN = HexColor("#16a34a")
AMBER = HexColor("#d97706")
RED = HexColor("#dc2626")

FONT_BODY = "Helvetica"
FONT_BOLD = "Helvetica-Bold"
FONT_MONO = "Courier"

PAGE_W, PAGE_H = letter
MARGIN = 0.85 * inch


# ── Lookup Tables ──────────────────────────────────────────────

INDUSTRY_LABELS = {
    "real_estate": "Real Estate",
    "legal": "Legal / Law Firm",
    "healthcare": "Healthcare / Medical",
    "financial": "Financial Services / Insurance",
    "construction": "Construction / Trades",
    "professional_services": "Professional Services / Consulting",
    "marketing": "Marketing / Creative Agency",
    "ecommerce": "E-commerce / Retail",
    "saas": "SaaS / Technology",
    "hospitality": "Hospitality / Food Service",
    "nonprofit": "Nonprofit",
    "other": "Other",
}

PAIN_LABELS = {
    "inbox_management": "Inbox / email management",
    "lead_response": "Responding to leads",
    "data_entry": "Data entry / admin",
    "scheduling": "Scheduling / coordination",
    "document_processing": "Document processing",
    "customer_followup": "Customer follow-ups",
    "reporting": "Reporting / summaries",
    "other": "Something else",
}

TOOL_LABELS = {
    "gmail": "Gmail / Google Workspace",
    "outlook": "Outlook / Microsoft 365",
    "slack": "Slack / Teams",
    "crm": "CRM (Salesforce, HubSpot, etc.)",
    "spreadsheets": "Google Sheets / Excel",
    "quickbooks": "QuickBooks / Accounting",
    "project_mgmt": "Asana / Monday / Trello",
    "other": "Other",
}

TIER_LABELS = {
    "pilot": "Pilot ($0–1K, 30-day proof of value)",
    "standard": "Standard ($500–900/mo)",
    "growth": "Growth ($900–1,750/mo)",
    "not_sure": "Not yet determined",
}

VOLUME_LABELS = {
    "1-10": "1–10 per day",
    "11-50": "11–50 per day",
    "51-200": "51–200 per day",
    "200+": "200+ per day",
    "not_sure": "Unknown",
}

HOURS_LABELS = {
    "1-2": "1–2 hours/week",
    "3-5": "3–5 hours/week",
    "5-10": "5–10 hours/week",
    "10-20": "10–20 hours/week",
    "20+": "20+ hours/week",
}

# Automation feasibility scores per pain point (0-100)
FEASIBILITY_SCORES = {
    "inbox_management": 90,
    "lead_response": 95,
    "data_entry": 85,
    "scheduling": 75,
    "document_processing": 80,
    "customer_followup": 88,
    "reporting": 82,
    "other": 50,
}

# Estimated time savings multiplier per pain point
TIME_SAVINGS_PCT = {
    "inbox_management": 0.70,
    "lead_response": 0.80,
    "data_entry": 0.75,
    "scheduling": 0.50,
    "document_processing": 0.65,
    "customer_followup": 0.70,
    "reporting": 0.60,
    "other": 0.40,
}

HOURS_MIDPOINTS = {
    "1-2": 1.5,
    "3-5": 4,
    "5-10": 7.5,
    "10-20": 15,
    "20+": 25,
}


# ── Styles ─────────────────────────────────────────────────────

def make_styles():
    return {
        "title": ParagraphStyle(
            "Title", fontName=FONT_BOLD, fontSize=28, leading=34,
            textColor=DARK, spaceAfter=6
        ),
        "subtitle": ParagraphStyle(
            "Subtitle", fontName=FONT_BODY, fontSize=12, leading=16,
            textColor=GRAY_500, spaceAfter=24
        ),
        "h1": ParagraphStyle(
            "H1", fontName=FONT_BOLD, fontSize=18, leading=24,
            textColor=DARK, spaceBefore=24, spaceAfter=10
        ),
        "h2": ParagraphStyle(
            "H2", fontName=FONT_BOLD, fontSize=13, leading=18,
            textColor=GRAY_800, spaceBefore=16, spaceAfter=6
        ),
        "body": ParagraphStyle(
            "Body", fontName=FONT_BODY, fontSize=10, leading=15,
            textColor=GRAY_600, spaceAfter=8
        ),
        "body_bold": ParagraphStyle(
            "BodyBold", fontName=FONT_BOLD, fontSize=10, leading=15,
            textColor=DARK, spaceAfter=8
        ),
        "small": ParagraphStyle(
            "Small", fontName=FONT_BODY, fontSize=8.5, leading=12,
            textColor=GRAY_500, spaceAfter=4
        ),
        "mono": ParagraphStyle(
            "Mono", fontName=FONT_MONO, fontSize=8, leading=11,
            textColor=GRAY_500, spaceAfter=4
        ),
        "bullet": ParagraphStyle(
            "Bullet", fontName=FONT_BODY, fontSize=10, leading=15,
            textColor=GRAY_600, leftIndent=20, bulletIndent=8,
            spaceAfter=4
        ),
        "metric_value": ParagraphStyle(
            "MetricValue", fontName=FONT_BOLD, fontSize=22, leading=26,
            textColor=DARK
        ),
        "metric_label": ParagraphStyle(
            "MetricLabel", fontName=FONT_BODY, fontSize=9, leading=12,
            textColor=GRAY_500
        ),
        "table_header": ParagraphStyle(
            "TableHeader", fontName=FONT_BOLD, fontSize=9, leading=12,
            textColor=GRAY_600
        ),
        "table_cell": ParagraphStyle(
            "TableCell", fontName=FONT_BODY, fontSize=9, leading=13,
            textColor=GRAY_600
        ),
        "footer": ParagraphStyle(
            "Footer", fontName=FONT_BODY, fontSize=7.5, leading=10,
            textColor=GRAY_400, alignment=TA_CENTER
        ),
    }


# ── Analysis Logic ─────────────────────────────────────────────

def analyze_intake(data):
    """Produce structured analysis from intake form data."""
    pain_points = data.get("pain_points", [])
    tools = data.get("tools", [])
    volume = data.get("volume", "not_sure")
    hours = data.get("hours_per_week", "5-10")
    workflow_desc = data.get("workflow_description", "")
    industry = data.get("industry", "other")
    team_size = data.get("team_size", "2-5")

    # Score each pain point for feasibility
    scored_pains = []
    for pp in pain_points:
        score = FEASIBILITY_SCORES.get(pp, 50)
        savings = TIME_SAVINGS_PCT.get(pp, 0.40)
        label = PAIN_LABELS.get(pp, pp)

        # Boost score if relevant tools are present
        tool_boost = 0
        if pp in ("inbox_management", "lead_response") and ("gmail" in tools or "outlook" in tools):
            tool_boost = 5
        if pp == "data_entry" and "spreadsheets" in tools:
            tool_boost = 5
        if pp == "customer_followup" and "crm" in tools:
            tool_boost = 5

        scored_pains.append({
            "key": pp,
            "label": label,
            "score": min(score + tool_boost, 100),
            "savings_pct": savings,
            "rating": "High" if score >= 85 else ("Medium" if score >= 70 else "Low"),
        })

    # Sort by score descending
    scored_pains.sort(key=lambda x: x["score"], reverse=True)

    # Identify the recommended starting workflow
    recommended = scored_pains[0] if scored_pains else {
        "key": "inbox_management",
        "label": "Inbox / email management",
        "score": 90,
        "savings_pct": 0.70,
        "rating": "High",
    }

    # Total hours reported across all workflows
    hours_mid = HOURS_MIDPOINTS.get(hours, 5)

    # Distribute hours proportionally across pain points by weight,
    # then calculate savings per pain point
    total_weight = sum(FEASIBILITY_SCORES.get(pp, 50) for pp in pain_points) or 1
    total_hours_saved = 0.0
    for sp in scored_pains:
        weight = sp["score"] / total_weight
        sp["est_hours_weekly"] = round(hours_mid * weight, 1)
        sp["est_hours_saved"] = round(sp["est_hours_weekly"] * sp["savings_pct"], 1)
        total_hours_saved += sp["est_hours_saved"]

    total_hours_saved = round(total_hours_saved, 1)
    total_monthly_saved = round(total_hours_saved * 4.3, 0)

    # Calculate recommended-workflow-only savings for pilot scope
    rec_hours_saved = recommended.get("est_hours_saved", round(hours_mid * 0.25 * recommended["savings_pct"], 1))
    rec_monthly_saved = round(rec_hours_saved * 4.3, 0)

    # Determine recommended tier
    if len(pain_points) >= 3 or hours in ("10-20", "20+"):
        rec_tier = "standard"
    elif len(pain_points) >= 5:
        rec_tier = "growth"
    else:
        rec_tier = "pilot"

    # Build tool integration map
    integrations = []
    for tool in tools:
        label = TOOL_LABELS.get(tool, tool)
        if tool == "gmail":
            integrations.append({"tool": label, "method": "Gmail API (OAuth2)", "complexity": "Low"})
        elif tool == "outlook":
            integrations.append({"tool": label, "method": "Microsoft Graph API", "complexity": "Low"})
        elif tool == "slack":
            integrations.append({"tool": label, "method": "Slack Bot / Webhooks", "complexity": "Low"})
        elif tool == "crm":
            integrations.append({"tool": label, "method": "CRM REST API", "complexity": "Medium"})
        elif tool == "spreadsheets":
            integrations.append({"tool": label, "method": "Google Sheets API / CSV export", "complexity": "Low"})
        elif tool == "quickbooks":
            integrations.append({"tool": label, "method": "QuickBooks API", "complexity": "Medium"})
        elif tool == "project_mgmt":
            integrations.append({"tool": label, "method": "Project management API", "complexity": "Medium"})
        else:
            integrations.append({"tool": label, "method": "TBD — needs scoping", "complexity": "Unknown"})

    # Check if lead_response is among pain points (for stats callout)
    has_lead_response = "lead_response" in pain_points

    return {
        "scored_pains": scored_pains,
        "recommended": recommended,
        "integrations": integrations,
        "est_hours_saved_weekly": total_hours_saved,
        "est_hours_saved_monthly": total_monthly_saved,
        "rec_hours_saved_weekly": rec_hours_saved,
        "rec_monthly_saved": rec_monthly_saved,
        "rec_tier": rec_tier,
        "hours_current": hours_mid,
        "has_lead_response": has_lead_response,
    }


# ── PDF Builder ────────────────────────────────────────────────

class FooterCanvas(canvas.Canvas):
    """Custom canvas that adds footer to every page."""
    def __init__(self, *args, **kwargs):
        self._business_name = kwargs.pop("business_name", "")
        canvas.Canvas.__init__(self, *args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for i, state in enumerate(self._saved_page_states):
            self.__dict__.update(state)
            self._draw_footer(i + 1, num_pages)
            canvas.Canvas.showPage(self)
        canvas.Canvas.save(self)

    def _draw_footer(self, page_num, total_pages):
        self.saveState()
        self.setFont(FONT_BODY, 7.5)
        self.setFillColor(GRAY_400)

        y = 0.5 * inch
        # Left: Kavik Works
        self.drawString(MARGIN, y, "Kavik Works — Feasibility Study")
        # Center: confidential
        self.drawCentredString(PAGE_W / 2, y, f"Confidential — Prepared for {self._business_name}")
        # Right: page number
        self.drawRightString(PAGE_W - MARGIN, y, f"Page {page_num} of {total_pages}")

        # Separator line
        self.setStrokeColor(GRAY_200)
        self.setLineWidth(0.5)
        self.line(MARGIN, y + 14, PAGE_W - MARGIN, y + 14)

        self.restoreState()


def build_pdf(data, analysis, output_path):
    """Build the feasibility study PDF."""
    styles = make_styles()
    today = datetime.now()
    business = data.get("business_name", "Client")
    contact = data.get("contact_name", "")
    industry_label = INDUSTRY_LABELS.get(data.get("industry", "other"), "Other")

    def make_canvas(*args, **kwargs):
        return FooterCanvas(*args, business_name=business, **kwargs)

    doc = SimpleDocTemplate(
        output_path,
        pagesize=letter,
        leftMargin=MARGIN, rightMargin=MARGIN,
        topMargin=MARGIN, bottomMargin=MARGIN,
        title=f"Feasibility Study — {business}",
        author="Kavik Works",
    )

    story = []

    # ── Cover Page ────────────────────────────────────────────
    story.append(Spacer(1, 1.5 * inch))
    story.append(Paragraph("KAVIK WORKS", ParagraphStyle(
        "Cover_Mono", fontName=FONT_MONO, fontSize=10, leading=14,
        textColor=GRAY_500, spaceAfter=24,
        tracking=300,
    )))
    story.append(Paragraph("Feasibility Study", styles["title"]))
    story.append(Paragraph(
        f"AI Workflow Automation Assessment for {business}",
        styles["subtitle"]
    ))
    story.append(Spacer(1, 24))

    # Divider
    story.append(HRFlowable(
        width="100%", thickness=1, color=GRAY_200, spaceAfter=24
    ))

    # Cover details
    cover_data = [
        ["PREPARED FOR", f"{contact}, {business}"],
        ["INDUSTRY", industry_label],
        ["PREPARED BY", "Josh Lynch, Kavik Works"],
        ["DATE", today.strftime("%B %d, %Y")],
        ["VALID THROUGH", (today + timedelta(days=30)).strftime("%B %d, %Y")],
    ]
    for label, value in cover_data:
        story.append(Paragraph(
            f'<font face="{FONT_MONO}" size="8" color="#{GRAY_500.hexval()[2:]}">{label}</font>',
            styles["small"]
        ))
        story.append(Paragraph(value, styles["body_bold"]))
        story.append(Spacer(1, 6))

    story.append(PageBreak())

    # ── 1. Executive Summary ─────────────────────────────────
    story.append(Paragraph("1. Executive Summary", styles["h1"]))
    story.append(HRFlowable(width="100%", thickness=0.5, color=GRAY_200, spaceAfter=12))

    rec = analysis["recommended"]
    hours_saved = analysis["est_hours_saved_weekly"]
    monthly_saved = analysis["est_hours_saved_monthly"]
    hourly_rate = 35

    exec_text = (
        f"We identified <b>{len(analysis['scored_pains'])} workflow areas</b> with strong automation "
        f"potential across {business}'s operations. Together, these represent an estimated "
        f"<b>{hours_saved} hours per week</b> ({int(monthly_saved)} hours/month) in recoverable time — "
        f"approximately <b>${int(monthly_saved * hourly_rate):,}/month</b> at a blended $35/hr rate. "
        f"We recommend starting with <b>{rec['label'].lower()}</b> as a focused pilot to demonstrate "
        f"measurable ROI before expanding."
    )
    story.append(Paragraph(exec_text, styles["body"]))
    story.append(Spacer(1, 12))

    # Key metrics row
    metrics = [
        [Paragraph(f"{hours_saved} hrs", styles["metric_value"]),
         Paragraph(f"{int(monthly_saved)} hrs", styles["metric_value"]),
         Paragraph(f"${int(monthly_saved * hourly_rate):,}", styles["metric_value"]),
         Paragraph(f"{len(analysis['scored_pains'])}", styles["metric_value"])],
        [Paragraph("Est. weekly time saved", styles["metric_label"]),
         Paragraph("Est. monthly time saved", styles["metric_label"]),
         Paragraph("Est. monthly cost savings", styles["metric_label"]),
         Paragraph("Workflows identified", styles["metric_label"])],
    ]
    metric_table = Table(metrics, colWidths=[1.5 * inch] * 4)
    metric_table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("LINEABOVE", (0, 0), (-1, 0), 1, GRAY_200),
        ("LINEBELOW", (0, -1), (-1, -1), 1, GRAY_200),
    ]))
    story.append(metric_table)
    story.append(Spacer(1, 12))

    # ── 2. Current Workflow Analysis ─────────────────────────
    story.append(Paragraph("2. Current Workflow Analysis", styles["h1"]))
    story.append(HRFlowable(width="100%", thickness=0.5, color=GRAY_200, spaceAfter=12))

    workflow_desc = data.get("workflow_description", "No description provided.")
    story.append(Paragraph(
        f'<i>"{workflow_desc}"</i>',
        ParagraphStyle("Quote", parent=styles["body"], textColor=GRAY_600,
                       leftIndent=12, rightIndent=12, spaceAfter=12,
                       borderPadding=8)
    ))

    # Current volume and time
    vol_label = VOLUME_LABELS.get(data.get("volume", "not_sure"), "Unknown")
    hours_key = data.get("hours_per_week", "")
    hrs_label = HOURS_LABELS.get(hours_key, hours_key if hours_key else "Not specified")
    team_label = data.get("team_size", "Not specified")
    story.append(Paragraph(
        f"Task volume: <b>{vol_label}</b> · Time spent: <b>{hrs_label}</b> · Team size: <b>{team_label}</b>",
        styles["body"]
    ))
    story.append(Spacer(1, 8))

    story.append(Paragraph("Identified Pain Points", styles["h2"]))
    for sp in analysis["scored_pains"]:
        color = "#16a34a" if sp["rating"] == "High" else ("#d97706" if sp["rating"] == "Medium" else "#dc2626")
        story.append(Paragraph(
            f'<bullet>&bull;</bullet> {sp["label"]} — '
            f'<font color="{color}"><b>{sp["rating"]} feasibility ({sp["score"]}%)</b></font>',
            styles["bullet"]
        ))
    story.append(Spacer(1, 8))

    # ── Lead Response Time Statistics (if lead_response is a pain point) ──
    if analysis["has_lead_response"]:
        story.append(Paragraph("Why Speed to Lead Matters", styles["h2"]))
        story.append(Paragraph(
            "Your intake identified lead response as a key bottleneck. Research consistently shows "
            "that response time is one of the strongest predictors of whether a lead converts:",
            styles["body"]
        ))
        lead_stats = [
            "Leads contacted within <b>5 minutes</b> are <b>21× more likely</b> to qualify than those contacted after 30 minutes (MIT / InsideSales.com)",
            "<b>78% of customers</b> buy from the first company that responds (Lead Connect)",
            "Responding in the first minute increases conversions by <b>391%</b> (Velocify)",
            "The average B2B response time is <b>42 hours</b> — most businesses are leaving revenue on the table",
        ]
        for stat in lead_stats:
            story.append(Paragraph(
                f'<bullet>&bull;</bullet> {stat}',
                styles["bullet"]
            ))
        story.append(Spacer(1, 4))
        story.append(Paragraph(
            "Automating lead response doesn't just save time — it fundamentally changes your "
            "conversion rate by getting prospects a reply in seconds instead of hours.",
            ParagraphStyle("LeadCallout", parent=styles["body"], textColor=DARK,
                           fontName=FONT_BOLD, fontSize=10)
        ))

    # ── 3. Automation Opportunity Assessment ──────────────────
    story.append(PageBreak())
    story.append(Paragraph("3. Automation Opportunity Assessment", styles["h1"]))
    story.append(HRFlowable(width="100%", thickness=0.5, color=GRAY_200, spaceAfter=12))

    story.append(Paragraph(
        "Each pain point has been evaluated for automation feasibility based on "
        "the nature of the work, your current tools, and industry patterns.",
        styles["body"]
    ))
    story.append(Spacer(1, 8))

    # Feasibility table
    table_data = [[
        Paragraph("Workflow Area", styles["table_header"]),
        Paragraph("Feasibility", styles["table_header"]),
        Paragraph("Score", styles["table_header"]),
        Paragraph("Est. Time Savings", styles["table_header"]),
    ]]
    for sp in analysis["scored_pains"]:
        color = "#16a34a" if sp["rating"] == "High" else ("#d97706" if sp["rating"] == "Medium" else "#dc2626")
        savings_str = f"{int(sp['savings_pct'] * 100)}% of current time"
        table_data.append([
            Paragraph(sp["label"], styles["table_cell"]),
            Paragraph(f'<font color="{color}"><b>{sp["rating"]}</b></font>', styles["table_cell"]),
            Paragraph(f'{sp["score"]}%', styles["table_cell"]),
            Paragraph(savings_str, styles["table_cell"]),
        ])

    col_widths = [2.2 * inch, 1.2 * inch, 0.8 * inch, 1.8 * inch]
    ftable = Table(table_data, colWidths=col_widths)
    ftable.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), HexColor("#f5f5f5")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("GRID", (0, 0), (-1, -1), 0.5, GRAY_200),
    ]))
    story.append(ftable)
    story.append(Spacer(1, 16))

    # Tool integrations
    if analysis["integrations"]:
        story.append(Paragraph("Tool Integration Map", styles["h2"]))
        int_data = [[
            Paragraph("Tool", styles["table_header"]),
            Paragraph("Integration Method", styles["table_header"]),
            Paragraph("Complexity", styles["table_header"]),
        ]]
        for integ in analysis["integrations"]:
            int_data.append([
                Paragraph(integ["tool"], styles["table_cell"]),
                Paragraph(integ["method"], styles["table_cell"]),
                Paragraph(integ["complexity"], styles["table_cell"]),
            ])
        int_table = Table(int_data, colWidths=[2.2 * inch, 2.5 * inch, 1.3 * inch])
        int_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), HexColor("#f5f5f5")),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ("LEFTPADDING", (0, 0), (-1, -1), 8),
            ("RIGHTPADDING", (0, 0), (-1, -1), 8),
            ("GRID", (0, 0), (-1, -1), 0.5, GRAY_200),
        ]))
        story.append(int_table)

    # ── 4. Recommended Starting Workflow ─────────────────────
    story.append(Spacer(1, 16))
    story.append(Paragraph("4. Recommended Starting Workflow", styles["h1"]))
    story.append(HRFlowable(width="100%", thickness=0.5, color=GRAY_200, spaceAfter=12))

    story.append(Paragraph(
        f'We recommend beginning with <b>{rec["label"].lower()}</b> as the first automation target. '
        f'This area scored <b>{rec["score"]}%</b> on our feasibility assessment and represents the '
        f'highest-impact opportunity based on your current workflow description.',
        styles["body"]
    ))
    story.append(Spacer(1, 8))

    story.append(Paragraph("Why this workflow first:", styles["h2"]))
    reasons = [
        f"Highest automation feasibility score ({rec['score']}%) among your identified pain points",
        f"Estimated {int(rec['savings_pct'] * 100)}% time reduction on this process alone",
        "Clear, measurable success metrics (response time, processing time, error rate)",
        "Low integration complexity with your existing tools",
        "Results visible within the first 30 days",
    ]
    for reason in reasons:
        story.append(Paragraph(f"<bullet>&bull;</bullet> {reason}", styles["bullet"]))

    # ── 5. Estimated Impact ──────────────────────────────────
    story.append(PageBreak())
    story.append(Paragraph("5. Estimated Impact", styles["h1"]))
    story.append(HRFlowable(width="100%", thickness=0.5, color=GRAY_200, spaceAfter=12))

    story.append(Paragraph(
        "Projections based on your reported volume and time investment. "
        "Actual results will be validated during the pilot.",
        styles["body"]
    ))
    story.append(Spacer(1, 8))

    # Impact metrics table — total across all workflows
    monthly_cost_saved = round(monthly_saved * hourly_rate, 0)
    annual_cost_saved = round(monthly_cost_saved * 12, 0)

    impact_data = [
        [Paragraph("Metric", styles["table_header"]),
         Paragraph("Current", styles["table_header"]),
         Paragraph("After Automation", styles["table_header"]),
         Paragraph("Savings", styles["table_header"])],
        [Paragraph("Weekly time (all workflows)", styles["table_cell"]),
         Paragraph(f"{analysis['hours_current']} hours", styles["table_cell"]),
         Paragraph(f"{round(analysis['hours_current'] - hours_saved, 1)} hours", styles["table_cell"]),
         Paragraph(f'<b>{hours_saved} hours/week</b>', styles["table_cell"])],
        [Paragraph("Monthly time", styles["table_cell"]),
         Paragraph(f"{round(analysis['hours_current'] * 4.3, 0):.0f} hours", styles["table_cell"]),
         Paragraph(f"{round((analysis['hours_current'] - hours_saved) * 4.3, 0):.0f} hours", styles["table_cell"]),
         Paragraph(f'<b>{int(monthly_saved)} hours/month</b>', styles["table_cell"])],
        [Paragraph(f"Est. labor cost (at ${hourly_rate}/hr)", styles["table_cell"]),
         Paragraph(f"${analysis['hours_current'] * hourly_rate * 4.3:,.0f}/mo", styles["table_cell"]),
         Paragraph(f"${(analysis['hours_current'] - hours_saved) * hourly_rate * 4.3:,.0f}/mo", styles["table_cell"]),
         Paragraph(f'<b>${monthly_cost_saved:,.0f}/mo</b>', styles["table_cell"])],
        [Paragraph("Annual labor cost", styles["table_cell"]),
         Paragraph(f"${analysis['hours_current'] * hourly_rate * 4.3 * 12:,.0f}/yr", styles["table_cell"]),
         Paragraph(f"${(analysis['hours_current'] - hours_saved) * hourly_rate * 4.3 * 12:,.0f}/yr", styles["table_cell"]),
         Paragraph(f'<b>${annual_cost_saved:,.0f}/yr</b>', styles["table_cell"])],
    ]
    impact_table = Table(impact_data, colWidths=[1.7 * inch, 1.3 * inch, 1.3 * inch, 1.7 * inch])
    impact_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), HexColor("#f5f5f5")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("GRID", (0, 0), (-1, -1), 0.5, GRAY_200),
    ]))
    story.append(impact_table)
    story.append(Spacer(1, 6))

    story.append(Paragraph(
        f'<font size="8" color="#{GRAY_500.hexval()[2:]}">Cost estimates use a blended rate of '
        f'${hourly_rate}/hour for illustration. Your actual rate may differ. '
        f'These figures reflect total potential across all identified workflows — '
        f'the pilot will target the highest-impact area first.</font>',
        styles["small"]
    ))

    # ── 6. Proposed Approach ─────────────────────────────────
    story.append(Spacer(1, 16))
    story.append(Paragraph("6. Proposed Approach", styles["h1"]))
    story.append(HRFlowable(width="100%", thickness=0.5, color=GRAY_200, spaceAfter=12))

    rec_tier = analysis["rec_tier"]
    tier_label = TIER_LABELS.get(rec_tier, "Pilot")
    story.append(Paragraph(f"Recommended tier: <b>{tier_label}</b>", styles["body_bold"]))
    story.append(Spacer(1, 8))

    phase_data = [
        [Paragraph("Phase", styles["table_header"]),
         Paragraph("Timeline", styles["table_header"]),
         Paragraph("What Happens", styles["table_header"])],
        [Paragraph("Discovery", styles["table_cell"]),
         Paragraph("Week 1–2", styles["table_cell"]),
         Paragraph("Map workflow, configure integrations, define success metrics", styles["table_cell"])],
        [Paragraph("Build & Test", styles["table_cell"]),
         Paragraph("Week 2–3", styles["table_cell"]),
         Paragraph("Develop AI pipeline (classification, extraction, routing). Test with historical data", styles["table_cell"])],
        [Paragraph("Deploy", styles["table_cell"]),
         Paragraph("Week 3–4", styles["table_cell"]),
         Paragraph("Go live with human-in-the-loop review. Monitor and tune on real traffic", styles["table_cell"])],
        [Paragraph("Measure", styles["table_cell"]),
         Paragraph("Week 4+", styles["table_cell"]),
         Paragraph("Compile ROI report. Discuss expansion to additional workflows", styles["table_cell"])],
    ]
    phase_table = Table(phase_data, colWidths=[1.2 * inch, 1.0 * inch, 3.8 * inch])
    phase_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), HexColor("#f5f5f5")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("GRID", (0, 0), (-1, -1), 0.5, GRAY_200),
    ]))
    story.append(phase_table)

    # ── 7. Next Steps ────────────────────────────────────────
    story.append(Spacer(1, 16))
    story.append(Paragraph("7. Next Steps", styles["h1"]))
    story.append(HRFlowable(width="100%", thickness=0.5, color=GRAY_200, spaceAfter=12))

    steps = [
        "<b>Schedule a 30-minute scoping call</b> to walk through this study and confirm the recommended workflow.",
        "<b>Provide tool access</b> (API keys, test account credentials) so we can validate integrations.",
        "<b>Agree on success metrics</b> — what does 'working' look like for your team?",
        "<b>Kick off the pilot</b> with a clear timeline and weekly check-ins.",
    ]
    for i, step in enumerate(steps, 1):
        story.append(Paragraph(f"{i}. {step}", styles["body"]))
    story.append(Spacer(1, 16))

    story.append(Paragraph(
        f"To schedule a call or ask questions about this study, reach out to "
        f"<b>contact@kavikworks.com</b>.",
        styles["body_bold"]
    ))
    story.append(Spacer(1, 24))

    story.append(HRFlowable(width="100%", thickness=0.5, color=GRAY_200, spaceAfter=12))
    story.append(Paragraph(
        "Kavik Works — AI Workflow Automation for Business",
        ParagraphStyle("Closer", fontName=FONT_BOLD, fontSize=10,
                       textColor=GRAY_500, alignment=TA_CENTER)
    ))
    story.append(Paragraph(
        "kavikworks.com | contact@kavikworks.com | Denver, CO",
        ParagraphStyle("CloserSub", fontName=FONT_BODY, fontSize=8,
                       textColor=GRAY_400, alignment=TA_CENTER)
    ))

    # Build
    doc.build(story, canvasmaker=make_canvas)
    return output_path


# ── CLI ────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Generate a Kavik Works feasibility study PDF")
    parser.add_argument("--input", "-i", required=True, help="Path to intake JSON file")
    parser.add_argument("--output", "-o", default=None, help="Output PDF path (default: <business_name>_feasibility.pdf)")
    args = parser.parse_args()

    with open(args.input, "r") as f:
        data = json.load(f)

    analysis = analyze_intake(data)

    if args.output:
        output_path = args.output
    else:
        safe_name = data.get("business_name", "client").replace(" ", "_").lower()
        output_path = f"{safe_name}_feasibility_study.pdf"

    build_pdf(data, analysis, output_path)
    print(f"Feasibility study generated: {output_path}")


if __name__ == "__main__":
    main()
