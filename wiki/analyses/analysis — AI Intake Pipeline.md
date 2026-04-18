---
title: AI Intake Pipeline
type: analysis
created: 2026-04-18
updated: 2026-04-18
tags: [operations, product, technical]
sources: []
status: solid
---

# Analysis: AI Intake Pipeline

The technical system that processes new client inquiries end-to-end — from form submission to AI feasibility report in ~35 seconds, with no manual work.

## Pipeline Overview

```
intake.html → Apps Script Web App → Claude Haiku API → Gmail + Drive + Sheets
```

### Step by Step

1. **Prospect submits** `intake.html` (hosted on kavikworks.com)
2. **Form POSTs** to Google Apps Script Web App URL (deployed as: Execute as Me, Access Anyone)
3. **Apps Script** (`intake-webhook.js`):
   - Logs submission to Google Sheet ("Intake Submissions" tab)
   - Saves raw JSON to Google Drive folder
   - Sends plain-text notification to `contact@kavikworks.com`
   - Calls Claude Haiku API with a 10-section feasibility report prompt
   - Emails full HTML report to `josh@kavikworks.com`
   - Saves report HTML to Drive
   - Updates Sheet row status to `report_sent`

## AI Model Config

| Setting | Value |
|---------|-------|
| Model | `claude-haiku-4-5-20251001` |
| MAX_TOKENS | 8,192 (Haiku max) |
| Avg input tokens | ~1,580–1,612 |
| Avg output tokens | ~3,749–4,651 |
| Cost per report | ~$0.06–0.10 |
| Execution time | ~31 seconds |

Good fit reports use ~4,600 tokens; poor fit reports use ~3,700 (no Proposed Scope or full ROI table).

## Report Structure (10 Sections)

1. **Header** — business name, date, fit score badge (1–10, color-coded green/orange/red)
2. **Suitability Verdict** — Strong Fit / Conditional Fit / Poor Fit callout box
3. **Executive Summary** — 2–3 sentences specific to this client
4. **Core Product Fit Analysis** — 6-row table: volume, email workflow, response time problem, API availability, regulatory constraints, implementation complexity
5. **Proposed Scope** — specific automation plan (only if fit ≥ 5)
6. **ROI Analysis** — before/after table with net monthly gain and setup payback
7. **Industry Benchmarks** — MIT 21x, HBR 78%, InsideSales 42hr avg
8. **Risk Flags** — specific blockers or concerns
9. **Add-on Potential** — brief note on natural next steps (expanded if client selected add-ons tier)
10. **Recommended Next Step** — onboarding CTA or what would need to change for poor fit

## Fit Score Logic

Claude determines a 1–10 score based on:
- Volume (10+ leads/week = high, <10 = poor fit)
- Email-based workflow confirmed
- Response time pain point confirmed
- Tool API availability (Gmail/Outlook = easy, legacy systems = harder)
- Regulatory constraints (e.g., legal/medical = flag)
- Implementation complexity

Score thresholds: 8–10 = green (Strong Fit), 5–7 = orange (Conditional Fit), 1–4 = red (Poor Fit).

## Deployment

- Deployed as Google Apps Script Web App — Version 8 (Apr 18, 2026)
- Same Deployment ID / URL is preserved across versions — intake.html doesn't need updating on each deploy
- New version required for each code change (Deploy → Manage Deployments → pencil → New version → Deploy)

## Test Functions

| Function | Scenario |
|----------|----------|
| `testReport()` | Acme Corp — professional services, 50–200 leads/week, Gmail + HubSpot, `pricing_tier: 'core'` |
| `testPoorFit()` | Bob's Carpentry — 2–3 calls/week, phone-based, `pricing_tier: 'not_sure'` |

## Alternative: Cloud Function Pipeline

A Python-based pipeline (`automations/kavik_intake/`) exists as an alternative deployment via Google Cloud Functions + Cloud Run. Shares the same logic but runs on GCP infrastructure rather than Apps Script. Currently not the primary implementation — Apps Script is simpler to maintain for one-person operation.

## Related Pages

- [[Kavik Works]]
- [[Lead Response Automation]]
