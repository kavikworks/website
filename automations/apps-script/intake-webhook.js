/**
 * Kavik Works — Intake Form Webhook (Google Apps Script)
 *
 * Deploy as a Web App (Execute as: Me, Access: Anyone).
 * Set the resulting URL as GOOGLE_APPS_SCRIPT_URL in intake.html.
 *
 * This script:
 *   1. Receives the form POST from intake.html
 *   2. Logs the submission to a Google Sheet (8 columns)
 *   3. Saves raw JSON to Drive
 *   4. Sends a notification email to contact@kavikworks.com
 *   5. Sends intake data to VPS pipeline via webhook
 *   6. Updates the Sheet row status to 'pipeline_triggered'
 *
 * The VPS pipeline (port 9092) runs a 4-stage process:
 *   - LLM analysis of workflow description
 *   - Company research via web search
 *   - Relevant industry stats selection
 *   - Draft email generation in Josh's voice, saved to Gmail drafts
 */

// ── Configuration ────────────────────────────────────────────

const CONFIG = {
  SHEET_ID: '1mbknvaua8n_imAmeg2GcpcJqteShRwYuJGNvDjyY-Ak',
  SHEET_TAB: 'Intake Submissions',
  NOTIFICATION_EMAIL: 'contact@kavikworks.com',
  DRIVE_FOLDER_ID: '10kNDc0gR6ar-9AvlDYZ7wO0u4dE8m8pW',
  // VPS intake pipeline — generates draft email with AI analysis + research
  VPS_WEBHOOK_URL: 'http://167.235.152.228:9092/intake',
  VPS_WEBHOOK_TOKEN: 'kavik-intake-2024-secure-webhook',
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

    // 4. Send to VPS pipeline for AI analysis + draft generation
    triggerVPSPipeline(data, rowIndex);

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

// Handle GET for health checks
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
  folder.createFile(slug + '_intake_' + dateStr + '.json', JSON.stringify(data, null, 2), 'application/json');
}

// ── Notification Email (contact@) ────────────────────────────

function sendNotification(data, timestamp) {
  MailApp.sendEmail({
    to: CONFIG.NOTIFICATION_EMAIL,
    subject: 'New Intake: ' + (data.business_name || 'Unknown Business'),
    body: [
      'New intake form submission received at ' + timestamp,
      '',
      'CONTACT',
      '  Name: ' + (data.contact_name || 'N/A'),
      '  Email: ' + (data.contact_email || 'N/A'),
      '  Phone: ' + (data.contact_phone || 'N/A'),
      '',
      'BUSINESS',
      '  Name: ' + (data.business_name || 'N/A'),
      '  Industry: ' + (data.industry || 'N/A'),
      '',
      'WORKFLOW',
      '  Description: ' + (data.workflow_description || 'None provided'),
      '  Referral: ' + (data.referral_source || 'N/A'),
      '',
      '---',
      'VPS pipeline is generating a draft outreach email. Check josh@kavikworks.com drafts.',
    ].join('\n'),
  });
}

// ── VPS Pipeline Trigger ─────────────────────────────────────

function triggerVPSPipeline(data, rowIndex) {
  try {
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

    const code = response.getResponseCode();
    const body = response.getContentText();
    console.log('VPS pipeline response: ' + code + ' ' + body);

    if (code === 202 || code === 200) {
      updateSheetStatus(rowIndex, 'pipeline_triggered');
    } else {
      updateSheetStatus(rowIndex, 'vps_error_' + code);
    }
  } catch (err) {
    console.error('VPS pipeline trigger error:', err);
    updateSheetStatus(rowIndex, 'vps_connection_failed');
    // Don't throw — intake is already logged and notification sent
  }
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
 * testFullPipeline — exercises ALL steps exactly like a real form submission:
 *   1. Logs to Google Sheet (pipeline_status: received -> pipeline_triggered)
 *   2. Saves raw JSON to Drive
 *   3. Sends plain-text notification to contact@kavikworks.com
 *   4. Sends intake data to VPS pipeline webhook
 * Use this to verify the complete end-to-end pipeline.
 */
function testFullPipeline() {
  const testData = {
    contact_name: 'Jane Smith',
    contact_email: 'jane@acme.com',
    contact_phone: '(555) 123-4567',
    business_name: 'Acme Corp (Full Pipeline Test)',
    industry: 'professional_services',
    workflow_description: 'Sales team manually follows up on leads 2-3 days after inquiry. We get 30-40 leads per week through our website and Google. Someone on the team reads each one, decides if it is a real inquiry, then forwards it to the right salesperson. This takes hours and leads fall through the cracks.',
    referral_source: 'test',
    submitted_at: new Date().toISOString(),
  };
  const timestamp = new Date().toISOString();

  console.log('Step 1: Logging to Sheet...');
  const rowIndex = logToSheet(testData, timestamp);
  console.log('Sheet row: ' + rowIndex);

  console.log('Step 2: Saving JSON to Drive...');
  saveJsonToDrive(testData, timestamp);

  console.log('Step 3: Sending notification to contact@...');
  sendNotification(testData, timestamp);

  console.log('Step 4: Triggering VPS pipeline...');
  triggerVPSPipeline(testData, rowIndex);

  console.log('Full pipeline test complete. Check: Sheet row ' + rowIndex + ' | Drive JSON | contact@ email | VPS logs | josh@ drafts');
}

/**
 * testWebhookOnly — sends test data directly to the VPS pipeline.
 * Does NOT log to Sheet, Drive, or send notification email.
 * Use this to test the VPS pipeline without side effects.
 */
function testWebhookOnly() {
  const testData = {
    contact_name: 'Mike Kowalski',
    contact_email: 'mike@testcompany.com',
    contact_phone: '(843) 555-0192',
    business_name: 'Test Company Inc',
    industry: 'construction',
    workflow_description: 'We get 40+ leads a day through our website and Google. Our office manager reads each one, decides if it is a real inquiry, then forwards it to the right salesperson. This takes 2-3 hours every morning and leads fall through the cracks during busy season.',
    referral_source: 'test',
    submitted_at: new Date().toISOString(),
  };

  triggerVPSPipeline(testData, null);
  console.log('Webhook test sent. Check VPS logs and josh@ drafts.');
}
