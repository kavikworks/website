"""
Google Drive helper — upload files to a shared folder.

Uses Application Default Credentials (ADC). No service account key file needed.
- On Cloud Functions: ADC is injected automatically as the function's service account.
- Locally: run `gcloud auth application-default login` once to set up credentials.
"""

from pathlib import Path

import google.auth
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload


SCOPES = [
    "https://www.googleapis.com/auth/drive.file",
]


def get_drive_service():
    """Build Drive API service using Application Default Credentials."""
    creds, _ = google.auth.default(scopes=SCOPES)
    return build("drive", "v3", credentials=creds)


def upload_file(
    service,
    local_path: str,
    folder_id: str,
    filename: str | None = None,
    mime_type: str | None = None,
) -> dict:
    """
    Upload a file to a Drive folder. Returns dict with 'id' and 'webViewLink'.
    """
    filepath = Path(local_path)
    filename = filename or filepath.name

    if mime_type is None:
        ext = filepath.suffix.lower()
        mime_map = {
            ".pdf": "application/pdf",
            ".json": "application/json",
            ".csv": "text/csv",
            ".html": "text/html",
        }
        mime_type = mime_map.get(ext, "application/octet-stream")

    file_metadata = {
        "name": filename,
        "parents": [folder_id],
    }

    media = MediaFileUpload(str(filepath), mimetype=mime_type)
    result = service.files().create(
        body=file_metadata, media_body=media, fields="id,webViewLink"
    ).execute()

    return result
