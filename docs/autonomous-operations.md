# Autonomous operations contract

> **PROPOSED / INACTIVE:** This candidate authority remains inactive until the private operations board records `KAVIK-AUTONOMY-20260925-V1` approving the named repository commit and agent prompt hashes. The current GitHub `main` commit alone cannot broaden authority. Existing live rules continue until that activation record exists.

This document describes the public operating contract for the three scheduled Kavik Works jobs. The private operations policy and board contain connected-account status, sender identity, customer evidence, payment evidence, suppression records, and current state. Store only nonsecret references there or in sources; no secrets belong in Notion or sources. This repository contains the rules only; it is not a CRM, credential store, payment vault, or scheduler.

## Objective and boundaries

The jobs optimize for a profitable, low-maintenance service business while preserving accurate evidence and the owner's ability to intervene. Routine work should proceed under the rules below without asking the owner to re-approve an unchanged decision. The jobs may use connected business accounts that have already been authorized, but they must not invent access, expand permissions, or place new spend on an unactivated purchasing connection.

The initial product remains the $149 one-time written Workflow Blueprint for one quote-request, leasing-inquiry, or shared administrative-inbox workflow. It includes a process map, capture fields, routing rules, three editable templates, setup steps, tests, and one clarification revision within seven days. It does not include installed software, ongoing monitoring, emergency dispatch, regulated advice, or unlimited support. Scope, applicable tax, payment method, and delivery date must be confirmed from current private state before a payment request or commitment. Any price, public scope, or terms change requires a separate concrete owner decision plus matching live site, checkout, and ledger evidence.

The starting capacity is two new paid orders per week and two orders in progress. The default five-business-day delivery promise is allowed only when capacity, tools, and source material are ready. After three on-time paid, QA-passed, recipient-access-verified deliveries, no unresolved material defects or refund disputes, and a sustainable workload, Owner Brief may authorize a measured increase to five new orders per week and three in progress. That decision belongs in the private board and does not change the public price or terms by itself.

## Schedule and ownership

The existing cloud scheduler runs exactly these three business jobs. The times below are America/Denver and describe the intended schedule; the scheduler's current state remains the source of truth.

| Job | Schedule | Authority | Output |
| --- | --- | --- | --- |
| Business Desk | Daily at 08:00 and 15:00; net-new outreach weekdays only | Sole one-to-one business sender; intake, replies, bounded outreach, payment verification, delivery preparation, revisions, suppression | Case and action records, verified mail state, private deliverables, exceptional alerts |
| Growth Studio | Monday, Wednesday, and Friday at 11:00 | Selects one bounded acquisition or conversion experiment and prepares a small queue | One experiment, ready assets or recipients, evidence, and next decision |
| Owner Brief | Sunday at 17:00 | Reconciles economics, capacity, quality, incidents, and the next experiment | Concise weekly report with raw counts, unknowns, and decisions |

The repository must not add a second scheduler, sender, CRM, host, or local service. Personal and retired jobs remain separate. A normal connector error pauses only the affected action: the job continues unaffected work, records one actionable blocker, and uses bounded retries. It must not blindly re-enable an owner-paused job, bypass a platform control, or replay an uncertain side effect.

## Acquisition rules

Business Desk may execute an initial targeted US B2B sequence as part of the three-job system:

- No more than five new recipients per weekday and 25 new recipients per calendar week.
- One follow-up only, sent at least seven calendar days after the initial message; two touches total per recipient.
- Use only a verified public business email and the approved sender identity. Never guess an address, buy a list, impersonate the owner, or spam a personal profile.
- A reply, opt-out, bounce, manual message, existing draft, or suppression record stops the cold sequence for that recipient or domain as applicable. Existing customer conversations continue through the appropriate service path.
- Verify the actual sender, full thread, recipient, domain suppression state, address requirements, unsubscribe handling, and commercial-message requirements from current private state before sending.
- Record a deduplicated PLANNED intent before the send and CONFIRMED only after Gmail readback. If the result is uncertain, mark UNKNOWN and reconcile before retrying.
- Stop all new outbound when a complaint or provider warning occurs, or when two hard bounces appear in the last 25 outbound attempts. Preserve inbound and existing-customer handling, record the blocker, investigate the cause, and require an actual correction plus verified safe restoration before resuming.

Growth Studio owns the hypothesis, audience, copy, and evidence queue. It selects one experiment per run and keeps the queue small enough to execute within the caps. It may prepare or publish up to three organic business posts per week when an owned business channel is actually connected and verified. If that channel is unavailable, it should use the targeted-email or website fallback and record the blocker; it must not wait indefinitely for a social scheduler or keep producing blocked drafts.

Paid campaigns and new paid tools remain off until a separate private decision verifies payment access, budget, conversion tracking, and the applicable terms. Card placeholder information is never stored in this repository or used as a purchasing instruction.

## Sales, delivery, and quality

Business Desk may handle routine intake, quote explanation, existing verified checkout, live payment verification, delivery preparation, and the included clarification revision. Before requesting payment or promising delivery, preflight the cloud-connected checkout, payment readback, and private artifact-delivery capabilities; a local Mac being available is not proof of cloud capability. A message claiming that payment was made is not payment evidence. Confirm a paid order only from a successful final provider state matching the customer, order, amount, currency, and immutable provider ID. A raw bank deposit is not sufficient by itself to match an order.

Every paid delivery requires a recorded separate QA pass before release. For the first three paid deliveries, Growth Studio prioritizes `READY_FOR_QA` work before marketing and performs an independent QA pass in a separate task context from Business Desk's drafting run; it may use another fresh reviewer if callable. Growth Studio writes `PASS` or the exact corrections, and Business Desk waits for that result before delivery. If a fresh independent reviewer is unavailable, hold only the delivery and prepare the exact fix; do not add a fourth job or a founder routine gate. After three verified successes, a distinct second source-based pass may be used as the documented fallback when a fresh reviewer is unavailable. The pass checks source fidelity, scope and terms, format and readability, privacy, placeholders, routing rules, stop conditions, duplicate behavior, failure handling, recipient access, and private artifact readback.

Routine authority covers normal in-scope actions. Escalate only after preparing the concrete draft, evidence, and proposed fix when the issue involves credentials, a legal or sensitive decision, an irreversible action, an unsupported commitment, or a disputed or out-of-policy financial action. Unchanged policy does not require a new owner approval on each run.

## Evidence and measurement

The private operations board is the record of policy, cases, intents, experiments, blockers, and decisions. Gmail proves sent mail and full-thread state. Existing private Drive holds customer deliverables. Public files must never contain private message IDs, customer details, credentials, card data, or account evidence. Notion is not an atomic lock; establish a single nonoverlapping execution for a sender and campaign before a send, and block sends if that cannot be established. A claim followed by a reread does not prove a lock.

Use the intent states `PLANNED`, `CONFIRMED`, and `UNKNOWN` for every external side effect. Deduplicate by immutable message, thread, post, order, or transaction identifiers plus action type. Do not replay a `PLANNED` or `UNKNOWN` action until the external system has been reconciled. Do not treat a draft, vendor label, open checkout, or email claim as a completed outcome.

Owner Brief reports date range, raw counts, coverage, known costs, collected revenue, refunds and fees when available, founder minutes, delivery errors, revisions, capacity, and blockers. Unknown values stay UNKNOWN and are never converted to zero. Give an experiment at least seven days and evidence of 20–40 unique delivered recipients where delivery is verified before making a first decision. Count attempted, sent, delivered, and unknown separately. If delivery receipts are unavailable, use a clearly labeled sent-recipient fallback; never call those recipients delivered or fabricate unknown delivery. Low exposure is inconclusive. A single order does not establish a winning channel.

The public website remains a static, reviewable intake bridge. It may explain the current offer and capture a visitor-initiated email brief, but it must not claim payment, delivery, analytics, or backend capability that has not been verified. Run the repository checks for every website change and verify the deployed public content separately.
