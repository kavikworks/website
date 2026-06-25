---
title: Build Concepts — Content Plan
type: analysis
created: 2026-06-24
updated: 2026-06-24
tags: [SEO, content, website, build-concepts]
status: draft
---

# Build Concepts — Content Plan

SEO-driven reference library. Each article covers one industry + one workflow. Two sections per article: **Concept** (public SEO content) + **Execution Plan** (internal reference, deployable).

## Directory

```
kavikworks-site/
├── build-concepts/
│   ├── index.html                              ← Listing page
│   ├── law-firm-client-intake.html             ← Article 1
│   ├── hvac-lead-response.html                 ← Article 2
│   ├── property-management-inquiries.html       ← Article 3
│   ├── cpa-client-intake-triage.html           ← Article 4
│   └── insurance-quote-claims-routing.html     ← Article 5
```

Footer link: "Build Concepts" → `/build-concepts/`

## Article Template

Each article follows this structure:

1. **Title:** "How [Industry] Can Automate [Workflow]" 
2. **Meta description:** 150-160 char SEO summary
3. **The Problem** (200-300 words) — specific pain, real scenario
4. **How It Breaks Today** (200-300 words) — manual process, cost of delay
5. **The Automated Pipeline** (300-400 words) — step-by-step workflow diagram in text
6. **Expected Metrics** (100-200 words) — response time, capture rate, hours saved
7. **Execution Plan** (300-400 words) — tools, APIs, taxonomy, routing rules, templates

Total: ~1,500 words each

## Article 1: Law Firm Client Intake

- **Industry:** Small/boutique law firms (1-10 attorneys)
- **Workflow:** Client inquiry intake + lead response
- **Primary keyword:** "AI email automation for law firms"
- **Secondary:** "law firm client intake automation", "legal lead response"
- **Pain scenario:** Potential client emails on Friday at 4pm. No response until Monday. Client hired the firm that answered Saturday morning.

## Article 2: HVAC Lead Response

- **Industry:** HVAC + home services (roofing, plumbing, electrical)
- **Workflow:** Lead routing + quote follow-up
- **Primary keyword:** "HVAC lead response automation"
- **Secondary:** "home services email automation", "contractor lead routing"
- **Pain scenario:** 20+ inbound quote requests/day hitting a shared office@ inbox. Owner manually forwards to the right tech. 3+ hour average response time.

## Article 3: Property Management Inquiries

- **Industry:** Property management companies (50-500 units)
- **Workflow:** Tenant inquiry + maintenance request routing
- **Primary keyword:** "property management email automation"
- **Secondary:** "tenant inquiry routing", "maintenance request automation"
- **Pain scenario:** Late-night tenant maintenance emergency. Email sits until office opens. Water damage gets worse. Also: prospective tenant inquiries lost in the shuffle.

## Article 4: CPA Client Intake

- **Industry:** CPA firms + accounting practices
- **Workflow:** Client intake during tax season + ongoing triage
- **Primary keyword:** "accounting firm workflow automation"
- **Secondary:** "CPA client intake automation", "tax season email triage"
- **Pain scenario:** Tax season. 50+ client emails/day. Which are new prospects, which are existing clients with urgent docs, which are general questions? Manual triage means high-value prospects wait behind low-priority messages.

## Article 5: Insurance Quote + Claims Routing

- **Industry:** Independent insurance agencies
- **Workflow:** Quote request intake + claims routing
- **Primary keyword:** "insurance agency automation"
- **Secondary:** "insurance quote routing", "claims automation for agencies"
- **Pain scenario:** Mix of commercial quotes, personal lines quotes, and claims all hit the same inbox. Claims should route to adjusters instantly. Quotes should go to the agent specializing in that line. Manual sorting = slow quotes = lost business.

## File Naming Convention

- URL-friendly slug based on industry + workflow
- All lowercase, hyphens
- `.html` extension (static site, no build step)

## Styling

All articles inherit from the same CSS architecture as the main site. Use consistent `.mono` headers, dark theme, Inter + JetBrains Mono fonts. Articles are self-contained HTML files that link the same Google Fonts and reference the shared style inline (not external CSS — simpler for Cloudflare Pages).

## Keywords Target Summary

| Article | Primary Keyword | Long-Tail Variants |
|---------|----------------|---------------------|
| 1 | AI email automation for law firms | legal client intake automation, law firm lead response |
| 2 | HVAC lead response automation | contractor email routing, home services lead automation |
| 3 | property management email automation | tenant inquiry routing, maintenance request automation |
| 4 | accounting firm workflow automation | CPA client intake, tax season email triage |
| 5 | insurance agency automation | insurance quote routing, claims automation for agencies |
