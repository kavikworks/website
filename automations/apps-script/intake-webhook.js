/**
 * Kavik Works — Intake Form Webhook (Google Apps Script)
 *
 * Deploy as a Web App (Execute as: Me, Access: Anyone).
 * Set the resulting URL as GOOGLE_APPS_SCRIPT_URL in intake.html.
 *
 * This script:
 *   1. Receives the form POST from intake.html
 *   2. Logs the submission to a Google Sheet
 *   3. Sends a notification email to contact@kavikworks.com
 *   4. Triggers the Cloud Function to generate the feasibility report
 */

// ── Configuration ────────────────────────────────────────────
const CONFIG = {
  SHEET_ID: '1mbknvaua8n_imAmeg2GcpcJqteShRwYuJGNvDjyY-Ak',
  SHEET_TAB: 'Intake Submissions',
  NOTIFICATION_EMAIL: 'contact@kavikworks.com',
  CLOUD_FUNCTION_URL: 'https://kavik-intake-h4cyvrrvlq-uc.a.run.app',
  DRIVE_FOLDER_ID: '10kNDc0gR6ar-9AvlDYZ7wO0u4dE8m8pW',
};

// ── Main Handler ─────────────────────────────────────────────

function doPost(e) {
  try {
    const data = JSON.parse(e.postData.contents);
    const timestamp = new Date().toISOString();

    // 1. Log to Google Sheet
    const rowIndex = logToSheet(data, timestamp);

    // 2. Save raw JSON to Drive
    saveJsonToDrive(data, timestamp);

    // 3. Send notification email
    sendNotification(data, timestamp);

    // 4. Trigger Cloud Function for report generation
    triggerReportGeneration(data, timestamp, rowIndex);

    return ContentService
      .createTextOutput(JSON.stringify({ status: 'ok', row: rowIndex }))
      .setMimeType(ContentService.MimeType.JSON);

  } catch (err) {
    console.error('Intake webhook error:', err);
    return ContentService
      .createTextOutput(JSON.stringify({ status: 'error', message: err.toString() }))
      .setMimeType(ContentService.MimeType.JSON);
  }
}

// Also handle GET for CORS preflight / health checks
function doGet(e) {
  return ContentService
    .createTextOutput(JSON.stringify({ status: 'ok', service: 'kavik-intake-webhook' }))
    .setMimeType(ContentService.MimeType.JSON);
}

// ── Sheet Logging ────────────────────────────────────────────

function logToSheet(data, timestamp) {
  const ss = SpreadsheetApp.openById(CONFIG.SHEET_ID);
  let sheet = ss.getSheetByName(CONFIG.SHEET_TAB);

  // Create sheet with headers if it doesn't exist
  if (!sheet) {
    sheet = ss.insertSheet(CONFIG.SHEET_TAB);
    sheet.appendRow([
      'timestamp',
      'contact_name',
      'contact_email',
      'contact_phone',
      'contact_method',
      'business_name',
      'business_website',
      'industry',
      'team_size',
      'pain_points',
      'workflow_description',
      'volume',
      'hours_per_week',
      'tools',
      'pricing_tier',
      'timeline',
      'additional_notes',
      'referral_source',
      'pipeline_status',
    ]);
    // Bold the header row
    sheet.getRange(1, 1, 1, 19).setFontWeight('bold');
  }

  const row = [
    timestamp,
    data.contact_name || '',
    data.contact_email || '',
    data.contact_phone || '',
    data.contact_method || '',
    data.business_name || '',
    data.business_website || '',
    data.industry || '',
    data.team_size || '',
    Array.isArray(data.pain_points) ? data.pain_points.join(', ') : (data.pain_points || ''),
    data.workflow_description || '',
    data.volume || '',
    data.hours_per_week || '',
    Array.isArray(data.tools) ? data.tools.join(', ') : (data.tools || ''),
    data.pricing_tier || '',
    data.timeline || '',
    data.additional_notes || '',
    data.referral_source || '',
    'received',  // pipeline_status
  ];

  sheet.appendRow(row);
  return sheet.getLastRow();
}

// ── Drive Backup ─────────────────────────────────────────────

function saveJsonToDrive(data, timestamp) {
  if (!CONFIG.DRIVE_FOLDER_ID) return;

  const folder = DriveApp.getFolderById(CONFIG.DRIVE_FOLDER_ID);
  const slug = (data.business_name || 'unknown')
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '_')
    .replace(/^_|_$/g, '');
  const dateStr = timestamp.slice(0, 10);
  const filename = `${slug}_intake_${dateStr}.json`;

  folder.createFile(filename, JSON.stringify(data, null, 2), 'application/json');
}

// ── Email Notification ───────────────────────────────────────

function sendNotification(data, timestamp) {
  const painPoints = Array.isArray(data.pain_points)
    ? data.pain_points.join(', ')
    : (data.pain_points || 'none listed');

  const tools = Array.isArray(data.tools)
    ? data.tools.join(', ')
    : (data.tools || 'none listed');

  const subject = `New Intake: ${data.business_name || 'Unknown Business'}`;

  const body = [
    `New intake form submission received at ${timestamp}`,
    '',
    `CONTACT`,
    `  Name: ${data.contact_name || 'N/A'}`,
    `  Email: ${data.contact_email || 'N/A'}`,
    `  Phone: ${data.contact_phone || 'N/A'}`,
    `  Preferred: ${data.contact_method || 'N/A'}`,
    '',
    `BUSINESS`,
    `  Name: ${data.business_name || 'N/A'}`,
    `  Website: ${data.business_website || 'N/A'}`,
    `  Industry: ${data.industry || 'N/A'}`,
    `  Team size: ${data.team_size || 'N/A'}`,
    '',
    `WORKFLOW`,
    `  Pain points: ${painPoints}`,
    `  Volume: ${data.volume || 'N/A'}`,
    `  Hours/week: ${data.hours_per_week || 'N/A'}`,
    `  Tools: ${tools}`,
    '',
    `  Description:`,
    `  ${data.workflow_description || 'None provided'}`,
    '',
    `ENGAGEMENT`,
    `  Tier interest: ${data.pricing_tier || 'N/A'}`,
    `  Timeline: ${data.timeline || 'N/A'}`,
    `  Referral: ${data.referral_source || 'N/A'}`,
    '',
    data.additional_notes ? `NOTES\n  ${data.additional_notes}` : '',
    '',
    '---',
    'Feasibility report generation has been triggered.',
    'You will receive a follow-up email with the PDF once it is ready.',
  ].join('\n');

  MailApp.sendEmail({
    to: CONFIG.NOTIFICATION_EMAIL,
    subject: subject,
    body: body,
  });
}

// ── Cloud Function Trigger ───────────────────────────────────

function triggerReportGeneration(data, timestamp, rowIndex) {
  if (!CONFIG.CLOUD_FUNCTION_URL) {
    console.log('Cloud Function URL not configured — skipping report trigger');
    return;
  }

  const payload = {
    intake_data: data,
    timestamp: timestamp,
    sheet_row: rowIndex,
    pipeline: 'kavik-intake',
  };

  const options = {
    method: 'post',
    contentType: 'application/json',
    payload: JSON.stringify(payload),
    muteHttpExceptions: true,
    headers: {
      // OAuth token from the script runner's account (josh@kavikworks.com)
      // That account has Owner on the GCP project, so it can invoke the function
      'Authorization': 'Bearer ' + ScriptApp.getOAuthToken(),
    },
  };

  try {
    const response = UrlFetchApp.fetch(CONFIG.CLOUD_FUNCTION_URL, options);
    console.log('Cloud Function response:', response.getContentText());
  } catch (err) {
    console.error('Failed to trigger Cloud Function:', err);
    // Don't throw — the intake is already logged, report gen is best-effort
  }
}
