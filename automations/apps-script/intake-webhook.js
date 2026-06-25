/**
 * Kavik Works — Intake Form Webhook (Google Apps Script)
 *
 * Deploy as a Web App (Execute as: Me, Access: Anyone).
 * Set the resulting URL as GOOGLE_APPS_SCRIPT_URL in intake.html.
 *
 * This script:
 *   1. Receives the form POST from intake.html
 *   2. Logs the submission to a Google Sheet
 *   3. Saves raw JSON to Drive
 *   4. Sends a notification email to contact@kavikworks.com
 *   5. Calls Claude API to generate an AI feasibility report
 *   6. Emails the report to josh@kavikworks.com
 *   7. Saves the report HTML to Drive
 *   8. Updates the Sheet row status to 'report_sent'
 *
 * Setup:
 *   - In Apps Script → Project Settings → Script Properties:
 *     Add property: ANTHROPIC_API_KEY = <your key from console.anthropic.com>
 */

// ── Configuration ────────────────────────────────────────────

const CONFIG = {
  SHEET_ID: '1mbknvaua8n_imAmeg2GcpcJqteShRwYuJGNvDjyY-Ak',
  SHEET_TAB: 'Intake Submissions',
  NOTIFICATION_EMAIL: 'contact@kavikworks.com',
  REPORT_EMAIL: 'josh@kavikworks.com',
  DRIVE_FOLDER_ID: '10kNDc0gR6ar-9AvlDYZ7wO0u4dE8m8pW',
  // VPS intake pipeline webhook — generates draft email with AI analysis + research
  VPS_WEBHOOK_URL: 'https://kavikworks.com:9092/intake',
  VPS_WEBHOOK_TOKEN: 'kavik-...re',
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

    // 3. Send basic notification to contact@
    sendNotification(data, timestamp);

    // 4. Generate AI report and email to josh@
    generateAndSendReport(data, timestamp, rowIndex);

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

// Handle GET for CORS preflight / health checks
function doGet(e) {
  return ContentService
    .createTextOutput(JSON.stringify({ status: 'ok', service: 'kavik-intake-webhook' }))
    .setMimeType(ContentService.MimeType.JSON);
}

// ── Sheet Logging ────────────────────────────────────────────

function logToSheet(data, timestamp) {
  const ss = SpreadsheetApp.openById(CONFIG.SHEET_ID);
  let sheet = ss.getSheetByName(CONFIG.SHEET_TAB);

  if (!sheet) {
    sheet = ss.insertSheet(CONFIG.SHEET_TAB);
    sheet.appendRow([
      'timestamp', 'contact_name', 'contact_email', 'contact_phone',
      'business_name', 'industry', 'workflow_description',
      'referral_source', 'pipeline_status',
    ]);
    sheet.getRange(1, 1, 1, 9).setFontWeight('bold');
  }

  sheet.appendRow([
    timestamp,
    data.contact_name || '',
    data.contact_email || '',
    data.contact_phone || '',
    data.business_name || '',
    data.industry || '',
    data.workflow_description || '',
    data.referral_source || '',
    'received',
  ]);

  return sheet.getLastRow();
}

// ── Drive Backup ─────────────────────────────────────────────

function saveJsonToDrive(data, timestamp) {
  if (!CONFIG.DRIVE_FOLDER_ID) return;
  const folder = DriveApp.getFolderById(CONFIG.DRIVE_FOLDER_ID);
  const slug = makeSlug(data.business_name);
  const dateStr = timestamp.slice(0, 10);
  folder.createFile(`${slug}_intake_${dateStr}.json`, JSON.stringify(data, null, 2), 'application/json');
}

// ── Notification Email (contact@) ────────────────────────────

function sendNotification(data, timestamp) {
  MailApp.sendEmail({
    to: CONFIG.NOTIFICATION_EMAIL,
    subject: `New Intake: ${data.business_name || 'Unknown Business'}`,
    body: [
      `New intake form submission received at ${timestamp}`,
      '',
      'CONTACT',
      `  Name: ${data.contact_name || 'N/A'}`,
      `  Email: ${data.contact_email || 'N/A'}`,
      `  Phone: ${data.contact_phone || 'N/A'}`,
      '',
      'BUSINESS',
      `  Name: ${data.business_name || 'N/A'}`,
      `  Industry: ${data.industry || 'N/A'}`,
      '',
      'WORKFLOW',
      `  Description: ${data.workflow_description || 'None provided'}`,
      `  Referral: ${data.referral_source || 'N/A'}`,
      '',
      '---',
      'VPS pipeline is generating a draft outreach email. Check josh@kavikworks.com drafts.',
    ].join('\n'),
  });
}

// ── VPS Pipeline Trigger ─────────────────────────────────────

function generateAndSendReport(data, timestamp, rowIndex) {
  try {
    // Send intake data to VPS pipeline for AI analysis + research + draft generation
    triggerVPSPipeline(data);
    updateSheetStatus(rowIndex, 'pipeline_triggered');
    console.log('VPS pipeline triggered for:', data.business_name);
  } catch (err) {
    console.error('VPS pipeline trigger error:', err);
    // Don't throw — intake is already logged
  }
}

function triggerVPSPipeline(data) {
  if (!CONFIG.VPS_WEBHOOK_URL || !CONFIG.VPS_WEBHOOK_TOKEN) {
    console.error('VPS webhook URL or token not configured');
    return;
  }

  const response = UrlFetchApp.fetch(CONFIG.VPS_WEBHOOK_URL, {
    method: 'post',
    contentType: 'application/json',
    headers: {
      'Authorization': 'Bearer ' + CONFIG.VPS_WEBHOOK_TOKEN,
    },
    payload: JSON.stringify(data),
    muteHttpExceptions: true,
  });

  console.log('VPS pipeline response:', response.getResponseCode(), response.getContentText());
}

// ── Sheet Status Update ───────────────────────────────────────

function updateSheetStatus(rowIndex, status) {
  if (!rowIndex) return;
  try {
    const ss = SpreadsheetApp.openById(CONFIG.SHEET_ID);
    const sheet = ss.getSheetByName(CONFIG.SHEET_TAB);
    if (!sheet) return;
    const headers = sheet.getRange(1, 1, 1, sheet.getLastColumn()).getValues()[0];
    const statusCol = headers.indexOf('pipeline_status') + 1;
    if (statusCol > 0) sheet.getRange(rowIndex, statusCol).setValue(status);
  } catch (err) {
    console.error('updateSheetStatus error:', err);
  }
}

// ── Helpers ───────────────────────────────────────────────────

function makeSlug(name) {
  return (name || 'unknown')
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '_')
    .replace(/^_|_$/g, '');
}

// ── Test Helpers (run from editor to verify) ──────────────────

/**
 * testFullPipeline — exercises ALL four steps exactly like a real form submission:
 *   1. Logs to Google Sheet (pipeline_status: received → report_sent)
 *   2. Saves raw JSON to Drive
 *   3. Sends plain-text notification to contact@kavikworks.com
 *   4. Generates AI report and emails to josh@kavikworks.com
 * Use this to verify the complete end-to-end pipeline.
 */
function testFullPipeline() {
  const testData = {
    contact_name: 'Jane Smith',
    contact_email: 'jane@acme.com',
    business_name: 'Acme Corp (Full Pipeline Test)',
    industry: 'Professional Services',
    team_size: '11-50',
    hours_per_week: '20+',
    volume: '50-200',
    tools: ['Gmail', 'HubSpot', 'QuickBooks'],
    pain_points: ['lead_followup', 'invoicing', 'reporting'],
    workflow_description: 'Sales team manually follows up on leads 2-3 days after inquiry. Invoices are created manually in QuickBooks after each project. Monthly reports are assembled by hand from multiple spreadsheets.',
    pricing_tier: 'core',
    timeline: '1-3 months',
    referral_source: 'test',
    additional_notes: 'FULL PIPELINE TEST — verify sheet row, Drive JSON, notification email, and AI report all complete.',
  };
  const timestamp = new Date().toISOString();

  console.log('Step 1: Logging to Sheet...');
  const rowIndex = logToSheet(testData, timestamp);
  console.log('Sheet row:', rowIndex);

  console.log('Step 2: Saving JSON to Drive...');
  saveJsonToDrive(testData, timestamp);

  console.log('Step 3: Sending notification to contact@...');
  sendNotification(testData, timestamp);

  console.log('Step 4: Generating AI report...');
  generateAndSendReport(testData, timestamp, rowIndex);

  console.log('Full pipeline test complete. Check: Sheet row', rowIndex, '| Drive JSON | contact@ email | josh@ report');
}

/**
 * testReport — exercises ONLY the AI report generation (steps 3-4).
 * Does NOT log to Sheet, Drive, or send notification email.
 * Use this to iterate on the Claude prompt without polluting the Sheet.
 */
function testReport() {
  const testData = {
    contact_name: 'Jane Smith',
    contact_email: 'jane@acme.com',
    business_name: 'Acme Corp',
    industry: 'Professional Services',
    team_size: '11-50',
    hours_per_week: '20+',
    volume: '50-200',
    tools: ['Gmail', 'HubSpot', 'QuickBooks'],
    pain_points: ['lead_followup', 'invoicing', 'reporting'],
    workflow_description: 'Sales team manually follows up on leads 2-3 days after inquiry. Invoices are created manually in QuickBooks after each project. Monthly reports are assembled by hand from multiple spreadsheets.',
    pricing_tier: 'core',
    timeline: '1-3 months',
    additional_notes: 'We lose deals to competitors who respond faster.',
  };
  generateAndSendReport(testData, new Date().toISOString(), null);
}

/**
 * testPoorFit — exercises ONLY the AI report for a poor-fit client.
 * Does NOT log to Sheet, Drive, or send notification email.
 */
function testPoorFit() {
  const testData = {
    contact_name: 'Bob Carpenter',
    contact_email: 'bob@bobscarpentry.com',
    business_name: "Bob's Carpentry",
    industry: 'Construction / Trades',
    team_size: '1-5',
    hours_per_week: '1-5',
    volume: '<10',
    tools: ['Gmail'],
    pain_points: ['scheduling'],
    workflow_description: 'I get maybe 2-3 calls a week from customers asking for estimates. I call them back when I can.',
    pricing_tier: 'not_sure',
    timeline: 'flexible',
    additional_notes: 'Not sure if I need this.',
  };
  generateAndSendReport(testData, new Date().toISOString(), null);
}
