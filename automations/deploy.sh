#!/usr/bin/env bash
set -euo pipefail

# ── Kavik Works — Deploy Automation Pipeline ──────────────────
#
# Usage:
#   ./deploy.sh                    # Deploy with defaults
#   ./deploy.sh --project my-gcp-project --region us-central1
#
# Prerequisites:
#   1. gcloud CLI installed and authenticated
#   2. GCP project with Cloud Functions API enabled
#   3. Service account key JSON for Google Workspace APIs
#   4. Environment variables set (or .env file in this directory)

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ENV_FILE="${SCRIPT_DIR}/.env"

# Load .env if present
if [[ -f "$ENV_FILE" ]]; then
  echo "Loading environment from .env"
  set -a
  source "$ENV_FILE"
  set +a
fi

# Defaults
GCP_PROJECT="${GCP_PROJECT:-}"
GCP_REGION="${GCP_REGION:-us-central1}"
FUNCTION_NAME="${FUNCTION_NAME:-kavik-intake}"
PUBSUB_TOPIC="${PUBSUB_TOPIC:-kavik-intake-submissions}"

# Parse arguments
while [[ $# -gt 0 ]]; do
  case $1 in
    --project) GCP_PROJECT="$2"; shift 2 ;;
    --region) GCP_REGION="$2"; shift 2 ;;
    --name) FUNCTION_NAME="$2"; shift 2 ;;
    --topic) PUBSUB_TOPIC="$2"; shift 2 ;;
    *) echo "Unknown arg: $1"; exit 1 ;;
  esac
done

# Validate
if [[ -z "$GCP_PROJECT" ]]; then
  echo "Error: Set GCP_PROJECT env var or pass --project"
  exit 1
fi

for var in GOOGLE_SHEET_ID GOOGLE_DRIVE_FOLDER_ID GMAIL_APP_PASSWORD; do
  if [[ -z "${!var:-}" ]]; then
    echo "Error: $var is not set"
    exit 1
  fi
done

echo "Deploying ${FUNCTION_NAME} to ${GCP_PROJECT} (${GCP_REGION})"
echo "Pub/Sub topic: ${PUBSUB_TOPIC}"
echo ""

# Create Pub/Sub topic if it doesn't exist (idempotent)
echo "Ensuring Pub/Sub topic exists..."
gcloud pubsub topics describe "$PUBSUB_TOPIC" \
  --project "$GCP_PROJECT" &>/dev/null \
  || gcloud pubsub topics create "$PUBSUB_TOPIC" --project "$GCP_PROJECT"

echo ""

gcloud functions deploy "$FUNCTION_NAME" \
  --project "$GCP_PROJECT" \
  --gen2 \
  --runtime python312 \
  --region "$GCP_REGION" \
  --trigger-topic "$PUBSUB_TOPIC" \
  --entry-point handle_intake \
  --source "$SCRIPT_DIR" \
  --set-env-vars "GOOGLE_SHEET_ID=${GOOGLE_SHEET_ID},GOOGLE_DRIVE_FOLDER_ID=${GOOGLE_DRIVE_FOLDER_ID},GMAIL_APP_PASSWORD=${GMAIL_APP_PASSWORD}" \
  --memory 512MB \
  --timeout 120s

echo ""
echo "Deployed. The function is now triggered by Pub/Sub topic: ${PUBSUB_TOPIC}"
echo ""
echo "Next: redeploy the Apps Script web app with the updated intake-webhook.js"
echo "(Editor → Deploy → Manage deployments → edit the existing deployment)"
