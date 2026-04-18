"""
Google Sheets helper — read and update rows.

Uses Application Default Credentials (ADC). No service account key file needed.
- On Cloud Functions: ADC is injected automatically as the function's service account.
- Locally: run `gcloud auth application-default login` once to set up credentials.
"""

import google.auth
from googleapiclient.discovery import build


SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
]


def get_sheets_service():
    """Build Sheets API service using Application Default Credentials."""
    creds, _ = google.auth.default(scopes=SCOPES)
    return build("sheets", "v4", credentials=creds)


def update_cell(service, sheet_id: str, tab: str, row: int, col: str, value: str):
    """
    Update a single cell. col is a letter like 'S' (for pipeline_status).
    """
    range_str = f"'{tab}'!{col}{row}"
    service.spreadsheets().values().update(
        spreadsheetId=sheet_id,
        range=range_str,
        valueInputOption="RAW",
        body={"values": [[value]]},
    ).execute()


def get_row(service, sheet_id: str, tab: str, row: int) -> list:
    """Read a full row."""
    range_str = f"'{tab}'!A{row}:Z{row}"
    result = service.spreadsheets().values().get(
        spreadsheetId=sheet_id, range=range_str
    ).execute()
    return result.get("values", [[]])[0]


def find_column_index(service, sheet_id: str, tab: str, column_name: str) -> str | None:
    """Find the column letter for a given header name."""
    result = service.spreadsheets().values().get(
        spreadsheetId=sheet_id, range=f"'{tab}'!1:1"
    ).execute()
    headers = result.get("values", [[]])[0]
    for i, h in enumerate(headers):
        if h.strip().lower() == column_name.strip().lower():
            return chr(ord("A") + i)
    return None
