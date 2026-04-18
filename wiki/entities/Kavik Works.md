---
title: Kavik Works
type: entity
created: 2026-04-18
updated: 2026-04-18
tags: [company, operations, strategy, product]
sources: []
status: solid
---

# Kavik Works

Kavik Works is a one-person automation consultancy operated by [[Josh Lynch]]. It builds and manages AI-powered workflow automations for small and mid-sized businesses, with a focus on clean, autonomous systems that require minimal ongoing intervention.

## Mission

Turn repetitive, inbox-based business workflows into self-running systems — without custom enterprise scopes, quarterly reviews, or babysitting from either side.

## Core Product

**[[Lead Response Automation]]** is the single productized offering.

- **What it does:** Monitors a business inbox, classifies incoming leads using AI, extracts contact details, sends a personalized acknowledgement within minutes, routes to the right person, and logs everything.
- **Pricing:** $997 one-time setup + $497/mo recurring
- **Included in monthly:** Running automation, system monitoring, email support, and one automated monthly ROI report emailed to the client
- **No scheduled calls or quarterly reviews** — the system reports on itself

## Add-on Modules

High-ticket add-ons scoped individually after the core is live. Each starts at $2,500 setup + $400/mo. Current modules:

- CRM & pipeline sync
- Invoice & accounts receivable automation
- Multi-channel (SMS, Slack, web chat)
- Custom ROI dashboards

Add-ons are priced to be worth it for both parties — not cheap experiments.

## Ideal Client Profile

- 10+ inbound email inquiries per week
- Losing deals to slow response times
- Using Gmail or Outlook
- Professional services, agencies, contractors, real estate, healthcare admin, trades

## Operations Model

Autonomous by design. No quarterly reviews, no scheduled touchpoints. Clients receive a monthly automated metrics email showing leads handled, response time vs. 42-hr industry average, hours/$ saved, and system health. At 20 clients that's 20 automated emails, not 80 scheduled calls per year.

## Technical Stack

- **Intake pipeline:** HTML intake form → Google Apps Script Web App → Claude Haiku API → Google Sheets (logging) + Google Drive (backups) + Gmail (reports)
- **AI model:** Claude Haiku (`claude-haiku-4-5-20251001`) — cheapest model, ~$0.06–0.10/report at 8,192 tokens
- **Hosting:** Static site (GitHub → deployment)
- **Repo:** `kavikworks/website` on GitHub

## Related Pages

- [[Lead Response Automation]]
- [[Pricing Strategy]]
- [[AI Intake Pipeline]]
- [[Josh Lynch]]
