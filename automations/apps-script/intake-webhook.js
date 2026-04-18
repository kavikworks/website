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
};

// Use Haiku — cheapest model, ~$0.06-0.10 per report at 8192 tokens (Haiku max)
const CLAUDE = {
  API_URL: 'https://api.anthropic.com/v1/messages',
  MODEL: 'claude-haiku-4-5-20251001',
  MAX_TOKENS: 8192,
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
      'contact_method', 'business_name', 'business_website', 'industry',
      'team_size', 'pain_points', 'workflow_description', 'volume',
      'hours_per_week', 'tools', 'pricing_tier', 'timeline',
      'additional_notes', 'referral_source', 'pipeline_status',
    ]);
    sheet.getRange(1, 1, 1, 19).setFontWeight('bold');
  }

  sheet.appendRow([
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
  const painPoints = Array.isArray(data.pain_points) ? data.pain_points.join(', ') : (data.pain_points || 'none listed');
  const tools = Array.isArray(data.tools) ? data.tools.join(', ') : (data.tools || 'none listed');

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
      `  Preferred: ${data.contact_method || 'N/A'}`,
      '',
      'BUSINESS',
      `  Name: ${data.business_name || 'N/A'}`,
      `  Website: ${data.business_website || 'N/A'}`,
      `  Industry: ${data.industry || 'N/A'}`,
      `  Team size: ${data.team_size || 'N/A'}`,
      '',
      'WORKFLOW',
      `  Pain points: ${painPoints}`,
      `  Volume: ${data.volume || 'N/A'}`,
      `  Hours/week: ${data.hours_per_week || 'N/A'}`,
      `  Tools: ${tools}`,
      `  Description: ${data.workflow_description || 'None provided'}`,
      '',
      'ENGAGEMENT',
      `  Tier interest: ${data.pricing_tier || 'N/A'}`,
      `  Timeline: ${data.timeline || 'N/A'}`,
      `  Referral: ${data.referral_source || 'N/A'}`,
      data.additional_notes ? `\nNOTES\n  ${data.additional_notes}` : '',
      '',
      '---',
      'AI feasibility report is being generated and will be sent to josh@kavikworks.com shortly.',
    ].join('\n'),
  });
}

// ── AI Report Generation ──────────────────────────────────────

function generateAndSendReport(data, timestamp, rowIndex) {
  try {
    const reportHtml = callClaudeAPI(data);
    if (!reportHtml) {
      console.error('No report content returned from Claude API');
      return;
    }

    // Save report HTML to Drive
    const slug = makeSlug(data.business_name);
    const dateStr = timestamp.slice(0, 10);
    const reportFilename = `${slug}_feasibility_${dateStr}.html`;
    if (CONFIG.DRIVE_FOLDER_ID) {
      const folder = DriveApp.getFolderById(CONFIG.DRIVE_FOLDER_ID);
      folder.createFile(reportFilename, reportHtml, 'text/html');
    }

    // Email report to josh@
    const subject = `Feasibility Report: ${data.business_name || 'New Client'}`;
    const emailHtml = `
      <div style="font-family:Arial,sans-serif;max-width:640px;margin:0 auto;">
        <div style="background:#1a1a2e;color:white;padding:12px 20px;font-size:13px;">
          <strong>Kavik Works</strong> — Lead Response Automation feasibility report
        </div>
        ${reportHtml}
        <div style="background:#f5f5f5;padding:12px 20px;font-size:12px;color:#888;margin-top:8px;">
          Submitted ${timestamp} &nbsp;|&nbsp;
          ${data.contact_name || 'N/A'} &lt;${data.contact_email || 'N/A'}&gt; &nbsp;|&nbsp;
          Report saved to Drive as ${reportFilename}
        </div>
      </div>`;

    MailApp.sendEmail({
      to: CONFIG.REPORT_EMAIL,
      subject: subject,
      htmlBody: emailHtml,
    });

    // Update Sheet status
    updateSheetStatus(rowIndex, 'report_sent');

    console.log('Report generated and sent:', reportFilename);

  } catch (err) {
    console.error('generateAndSendReport error:', err);
    // Don't throw — intake is already logged
  }
}

function callClaudeAPI(intakeData) {
  const apiKey = PropertiesService.getScriptProperties().getProperty('ANTHROPIC_API_KEY');
  if (!apiKey) {
    console.error('ANTHROPIC_API_KEY not set in Script Properties');
    return null;
  }

  const painPoints = Array.isArray(intakeData.pain_points)
    ? intakeData.pain_points.join(', ')
    : (intakeData.pain_points || 'N/A');
  const tools = Array.isArray(intakeData.tools)
    ? intakeData.tools.join(', ')
    : (intakeData.tools || 'N/A');

  // Kavik Works pricing — single core product + high-ticket add-ons
  // Must match intake.html select values: core, addons, not_sure
  const PRICING = {
    core:     { label: 'Lead Response Automation', setup: '$997', monthly: '$497/mo' },
    addons:   { label: 'Core + Add-on Modules',    setup: '$997 core + $2,500/module', monthly: '$497 + $400/mo per module' },
    not_sure: { label: 'Exploring',                setup: '$997 (core estimate)',       monthly: '$497/mo (core estimate)' },
  };
  const tier = PRICING[intakeData.pricing_tier] || PRICING.not_sure;
  const wantsAddons = intakeData.pricing_tier === 'addons';

  const prompt = `You are a senior automation consultant at Kavik Works reviewing a new client intake. Your job is to assess fit for one specific product and give Josh an honest, actionable recommendation.

KAVIK WORKS CORE PRODUCT: "Lead Response Automation"
- What it does: Monitors a business inbox, classifies incoming leads using AI, extracts contact details, sends a personalized acknowledgement within minutes, routes to the right person, and logs everything
- Ideal fit: businesses receiving 10+ inbound inquiries/week via email, losing deals to slow response times, using Gmail or Outlook
- Clear wins: professional services, agencies, contractors, real estate, healthcare admin, trades — anyone where a slow response means a lost deal
- Price: $997 one-time setup + $497/mo (includes automation, monitoring, and monthly automated ROI report emailed to client)
- What's included in monthly: the running automation, system monitoring, email support, and one automated monthly metrics email to the client showing: leads handled, avg response time vs. 42-hr industry average, estimated hours saved, $ value of time saved, system health status
- No quarterly reviews, no scheduled calls — the system runs autonomously
- Add-on modules: CRM sync, invoice automation, SMS/Slack/multi-channel, custom dashboards — each starts at $2,500 setup + $400/mo, scoped individually after core is live

POOR FIT signals (be direct — do not recommend if these apply):
- Fewer than 10 inbound inquiries/week (retainer doesn't pay back quickly enough)
- Leads arrive by phone only — no email-based inquiry workflow
- Industry with strict outbound communication compliance (e.g., legal advice, medical treatment decisions)
- Client expects personal relationship management, not automation
- Inbox response time already under 1 hour consistently

CLIENT INTAKE:
- Business: ${intakeData.business_name || 'N/A'} | Industry: ${intakeData.industry || 'N/A'} | Team size: ${intakeData.team_size || 'N/A'}
- Hours on manual tasks/week: ${intakeData.hours_per_week || 'N/A'} | Transaction volume: ${intakeData.volume || 'N/A'}
- Current tools: ${tools}
- Pain points: ${painPoints}
- Workflow description: ${intakeData.workflow_description || 'N/A'}
- Pricing interest: ${tier.label} | Timeline: ${intakeData.timeline || 'N/A'}
- Add-on modules interest: ${wantsAddons ? 'Yes' : 'No'}
- Additional notes: ${intakeData.additional_notes || 'None'}

Generate a professional feasibility report as HTML. No html/head/body tags -- just inner content with inline CSS, max 620px wide, suitable for embedding in an email.

REQUIRED SECTIONS:

1. HEADER: Business name, today's date, "Lead Response Automation -- Feasibility Report", and a FIT SCORE badge (1-10; 8-10 green #2ecc71, 5-7 orange #f39c12, 1-4 red #e74c3c).

2. SUITABILITY VERDICT: Styled callout box in fit score color. One of:
   STRONG FIT: "Recommend onboarding. Clear use case, good volume, straightforward implementation."
   CONDITIONAL FIT: "Viable with caveats: [specific issue to resolve before committing]."
   POOR FIT: "Do not pursue. [Honest 1-2 sentence reason.]"

3. EXECUTIVE SUMMARY: 2-3 sentences. For poor fit: why the ROI math doesn't work. For good fit: what the automation does for this specific business and what metric improves most.

4. CORE PRODUCT FIT ANALYSIS: A table with these exact rows:
   Factor | Assessment | Notes
   Inbound inquiry volume | High / Medium / Low | based on their volume & hours data
   Email-based workflow | Confirmed / Likely / Unclear | based on tools & description
   Response time problem | Confirmed / Likely / Unclear | based on pain points & notes
   Tool API availability | Available / Limited / Unknown | based on their tools list
   Regulatory constraints | None / Possible / High | based on industry
   Implementation complexity | Simple / Moderate / Complex | overall effort estimate

5. PROPOSED SCOPE (only if fit score >= 5): Be specific to this client:
   - Exactly what gets automated based on their workflow description
   - Which tools get connected
   - What their automated monthly report will show them
   - Investment: ${tier.setup} setup + ${tier.monthly} ongoing
   - Typical timeline: 1-2 weeks from signed agreement to go-live

6. ROI ANALYSIS: Table focused on lead response:
   Metric | Before | After
   Avg response time | [estimate] | Under 5 minutes
   Inquiries handled manually/week | [from volume] | 0
   Hours/week saved | -- | [estimate based on volume & hours]
   Monthly labor cost saved (@ $35/hr) | -- | $[amount]
   Kavik Works retainer | -- | $497/mo
   Net monthly gain | -- | $[savings minus $497]
   Setup payback period | -- | [months = $997 / net monthly gain]
   If volume is too low to produce a positive net monthly gain, say so plainly.

7. INDUSTRY BENCHMARKS (always include for lead response):
   - MIT/InsideSales: 21x higher lead qualification when responding within 5 minutes vs. 30 minutes
   - Harvard Business Review: 78% of deals go to the first vendor to respond
   - InsideSales Research: average business response time is 42 hours
   Add one industry-specific stat if relevant.

8. RISK FLAGS: Only list real risks:
   - Specific tools with no API or limited integration
   - Industry compliance concerns (be specific)
   - Volume concern: if under 10 leads/week, state the payback math explicitly
   - Anything in workflow description requiring per-message human judgment
   If none: "No significant risks -- standard implementation."

${wantsAddons
  ? `9. ADD-ON MODULES: Client indicated interest. Based on their pain points (${painPoints}), assess each relevant module:
   - Name | What it automates for this client | Setup (from $2,500) | Monthly (+$400/mo) | Readiness (ready now / after core is proven)
   Only list modules with a clear ROI case. Be selective.`
  : `9. ADD-ON POTENTIAL: One sentence only per relevant module based on pain points. Don't oversell -- just note what's a natural next step once core is running.`}

10. RECOMMENDED NEXT STEP:
   If fit >= 5: "Reply to this email or contact us at contact@kavikworks.com to move forward. We can typically go live within 2 weeks of a signed agreement."
   If poor fit: What specifically would need to change (volume, channel, compliance) for this to make sense later.

STYLE: Primary #1a1a2e, accent #e94560, success #2ecc71, warning #f39c12. Clean sans-serif. Navy section headers with left red border accent. All structured data in tables. Compact and scannable. Honest internal tone -- written for Josh, not the client.

Return ONLY the HTML with inline styles. No markdown, no code fences.`;

  const response = UrlFetchApp.fetch(CLAUDE.API_URL, {
    method: 'post',
    contentType: 'application/json',
    headers: {
      'x-api-key': apiKey,
      'anthropic-version': '2023-06-01',
    },
    payload: JSON.stringify({
      model: CLAUDE.MODEL,
      max_tokens: CLAUDE.MAX_TOKENS,
      messages: [{ role: 'user', content: prompt }],
    }),
    muteHttpExceptions: true,
  });

  const result = JSON.parse(response.getContentText());

  if (result.error) {
    console.error('Claude API error:', JSON.stringify(result.error));
    return null;
  }

  console.log('Claude API usage -- input:', result.usage.input_tokens, 'output:', result.usage.output_tokens);
  return result.content[0].text;
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
