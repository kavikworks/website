"""
Kavik Works — Intake Pipeline Cloud Function

Entrypoint for Google Cloud Functions (2nd gen / Cloud Run).
Triggered by a Pub/Sub topic — no HTTP auth headaches.

Deploy:
    # One-time: create the topic
    gcloud pubsub topics create kavik-intake-submissions --project studious-set-493416-f1

    # Deploy (Pub/Sub trigger)
    gcloud functions deploy kavik-intake \
        --gen2 \
        --runtime python312 \
        --region us-central1 \
        --trigger-topic kavik-intake-submissions \
        --entry-point handle_intake \
        --source . \
        --set-env-vars GOOGLE_SHEET_ID=...,GOOGLE_DRIVE_FOLDER_ID=...,GMAIL_APP_PASSWORD=...
"""

import base64
import json
import os
import tempfile
import traceback
from datetime import datetime
from pathlib import Path

import yaml
import functions_framework

# Shared helpers
from shared.gmail import send_email
from shared.drive import get_drive_service, upload_file
from shared.sheets import get_sheets_service, update_cell, find_column_index

# Local report generator
from kavik_intake.generate_feasibility import analyze_intake, build_pdf


# ── Configuration ─────────────────────────────────────────────

def load_config() -> dict:
    """Load pipeline config from YAML, with env var substitution."""
    config_path = Path(__file__).resolve().parent.parent / "pipelines" / "kavik-intake.yaml"
    with open(config_path) as f:
        raw = f.read()

    # Substitute ${ENV_VAR} references
    for key, value in os.environ.items():
        raw = raw.replace(f"${{{key}}}", value)

    return yaml.safe_load(raw)


# ── Validation ────────────────────────────────────────────────

def validate_intake(data: dict, config: dict) -> list[str]:
    """Check required fields. Returns list of missing field names."""
    required = []
    for step in config.get("steps", []):
        if step.get("action") == "validate":
            required = step.get("required_fields", [])
            break

    missing = [f for f in required if not data.get(f)]
    return missing


# ── Email Template ────────────────────────────────────────────

def render_summary_email(data: dict, analysis: dict, report_drive_link: str) -> str:
    """Render the HTML summary email for the team."""
    template_path = Path(__file__).resolve().parent / "templates" / "summary_email.html"

    if template_path.exists():
        html = template_path.read_text()
    else:
        # Fallback plain template
        html = _default_template()

    # Simple token replacement
    replacements = {
        "{{contact_name}}": data.get("contact_name", "N/A"),
        "{{contact_email}}": data.get("contact_email", "N/A"),
        "{{contact_phone}}": data.get("contact_phone", "N/A"),
        "{{business_name}}": data.get("business_name", "N/A"),
        "{{business_website}}": data.get("business_website", "N/A"),
        "{{industry}}": data.get("industry", "N/A"),
        "{{team_size}}": data.get("team_size", "N/A"),
        "{{pain_points}}": ", ".join(data.get("pain_points", [])),
        "{{workflow_description}}": data.get("workflow_description", "N/A"),
        "{{volume}}": data.get("volume", "N/A"),
        "{{hours_per_week}}": data.get("hours_per_week", "N/A"),
        "{{tools}}": ", ".join(data.get("tools", [])),
        "{{pricing_tier}}": data.get("pricing_tier", "N/A"),
        "{{timeline}}": data.get("timeline", "N/A"),
        "{{additional_notes}}": data.get("additional_notes", "None"),
        "{{referral_source}}": data.get("referral_source", "N/A"),
        "{{num_pain_points}}": str(len(analysis.get("scored_pains", []))),
        "{{est_hours_saved_weekly}}": str(analysis.get("est_hours_saved_weekly", 0)),
        "{{est_hours_saved_monthly}}": str(int(analysis.get("est_hours_saved_monthly", 0))),
        "{{recommended_workflow}}": analysis.get("recommended", {}).get("label", "N/A"),
        "{{recommended_tier}}": analysis.get("rec_tier", "N/A"),
        "{{report_drive_link}}": report_drive_link,
        "{{date}}": datetime.now().strftime("%B %d, %Y"),
    }

    for token, value in replacements.items():
        html = html.replace(token, value)

    return html


def _default_template() -> str:
    return """
    <h2>New Intake: {{business_name}}</h2>
    <p><strong>Contact:</strong> {{contact_name}} ({{contact_email}})</p>
    <p><strong>Pain points:</strong> {{pain_points}}</p>
    <p><strong>Est. savings:</strong> {{est_hours_saved_weekly}} hrs/week</p>
    <p><strong>Recommended start:</strong> {{recommended_workflow}}</p>
    <p><a href="{{report_drive_link}}">View report in Drive</a></p>
    <hr>
    <p style="color:#888;font-size:12px;">
        Feasibility study is attached. Review and forward to the client when ready.
    </p>
    """


# ── Main Handler ──────────────────────────────────────────────

@functions_framework.cloud_event
def handle_intake(cloud_event):
    """
    Cloud Function Pub/Sub entrypoint.
    Triggered by a message on the 'kavik-intake-submissions' topic.
    Message data (base64-encoded JSON) must contain:
        intake_data, timestamp, sheet_row, pipeline
    """
    try:
        # Decode the Pub/Sub message
        raw = base64.b64decode(cloud_event.data["message"]["data"]).decode("utf-8")
        payload = json.loads(raw)

        intake_data = payload.get("intake_data")
        sheet_row = payload.get("sheet_row")
        timestamp = payload.get("timestamp", datetime.now().isoformat())

        if not intake_data:
            print("ERROR: No intake_data in Pub/Sub message payload")
            return  # Pub/Sub functions return None; errors are logged

        config = load_config()

        # Step 1: Validate
        missing = validate_intake(intake_data, config)
        if missing:
            print(f"ERROR: Missing required fields: {', '.join(missing)}")
            return  # Log and exit; don't nack so Pub/Sub doesn't retry bad data

        # Step 2: Generate report
        analysis = analyze_intake(intake_data)

        with tempfile.TemporaryDirectory() as tmpdir:
            # Build filename from config template
            slug = (intake_data.get("business_name", "client")
                    .lower().replace(" ", "_").replace("'", ""))
            date_str = datetime.now().strftime("%Y-%m-%d")
            pdf_filename = f"{slug}_feasibility_{date_str}.pdf"
            pdf_path = str(Path(tmpdir) / pdf_filename)

            build_pdf(intake_data, analysis, pdf_path)

            # Also save the raw JSON
            json_filename = f"{slug}_intake_{date_str}.json"
            json_path = str(Path(tmpdir) / json_filename)
            with open(json_path, "w") as f:
                json.dump(intake_data, f, indent=2)

            # Step 3: Upload to Drive (uses ADC — no key file needed)
            folder_id = os.environ.get("GOOGLE_DRIVE_FOLDER_ID", "")
            report_drive_link = ""

            if folder_id:
                drive_svc = get_drive_service()

                # Upload PDF
                pdf_result = upload_file(drive_svc, pdf_path, folder_id, pdf_filename)
                report_drive_link = pdf_result.get("webViewLink", "")

                # Upload raw JSON backup
                upload_file(drive_svc, json_path, folder_id, json_filename)

            # Step 4: Send notification email (uses SMTP App Password)
            notify_cfg = config.get("notify", {})
            app_password = os.environ.get("GMAIL_APP_PASSWORD", "")
            if app_password and notify_cfg.get("to"):
                html_body = render_summary_email(intake_data, analysis, report_drive_link)

                subject = notify_cfg.get("subject_template", "New intake: {business_name}").format(
                    business_name=intake_data.get("business_name", "Unknown")
                )

                send_email(
                    sender=notify_cfg["from"],
                    app_password=app_password,
                    to=notify_cfg["to"],
                    subject=subject,
                    html_body=html_body,
                    attachments=[{"path": pdf_path, "filename": pdf_filename}],
                )

            # Step 5: Update Sheet status (uses ADC — no key file needed)
            sheet_id = os.environ.get("GOOGLE_SHEET_ID", "")
            if sheet_id and sheet_row:
                sheets_svc = get_sheets_service()
                tab = config.get("google", {}).get("sheet_tab", "Intake Submissions")
                status_col = find_column_index(sheets_svc, sheet_id, tab, "pipeline_status")
                if status_col:
                    update_cell(sheets_svc, sheet_id, tab, sheet_row, status_col, "report_sent")

        print(f"SUCCESS: report={pdf_filename}, drive_link={report_drive_link}")

    except Exception as e:
        # Re-raise so Cloud Functions marks the message as failed and retries
        traceback.print_exc()
        raise
