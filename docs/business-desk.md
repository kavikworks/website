# Business Desk runbook

> **DOCUMENTATION ALIGNMENT / SEND HOLD:** The owner-approved nationwide two-week audit campaign is documented here. Cold campaign sending remains `TECHNICAL_HOLD / SENDER_PROVIDER_COMPATIBILITY_BLOCKED`. Publication does not change saved job prompts, cadence, enabled state, or provider permission. Current private policy and native runtime readback govern execution.

Business Desk is the sole one-to-one business sender. Its documented cadence remains daily at 08:00 and 15:00 America/Denver; net-new outreach is allowed on weekdays only. It owns routine intake, customer replies, the bounded targeted sequence, suppression, payment verification, delivery preparation, and the included clarification revision. It does not send from a personal profile or create a second sender. The owning scheduler must expose the exact saved prompts and settings before any runtime amendment; preserve cadence and enabled state, apply only the authorized changes, and read back the result. Missing native read access blocks prompt changes, not reviewable documentation or unaffected customer work.

## Every run

1. Read the current private operations policy and board. Verify the connected business sender, full-thread access, recipient resolution, continuation cursor, unfinished pagination, outstanding intents, capacity, payment readiness, and delivery gates. Use connected-account status and nonsecret references only; no secrets belong in Notion or sources, and none belong in this repository.
2. Resume unfinished pagination first. Use a 48-hour overlap after the last complete scan, deduplicate by immutable message and thread IDs, and bound discovery to 100 messages per run with a continuation record. Advance the cursor only after a complete scan.
3. Discover genuine business inquiries, existing customer obligations, replies, opt-outs, bounces, manual sends, existing drafts, and relevant service incidents. Inspect the full conversation. Household mail, vendor pitches, newsletters, automated mail, and generic spam are not customers.
4. Upsert one case per thread. Keep observed facts separate from inference. A vendor qualification label, payment email, open checkout, or raw deposit is not proof of a paid customer.
5. Reconcile every existing `PLANNED` or `UNKNOWN` intent before considering a retry. Use one deduplicated action key per thread, inbound message, and action type. Do not blind-replay an uncertain send. Acquire the exclusive claim below before any Gmail side effect, including draft mutations and routine replies.

## Exclusive mail control

Use the existing private native Docs control for `ALL_GMAIL_SIDE_EFFECTS`. Read its native `revisionId`, validate the control schema, scope, `FREE` state, `NONE` owner, and nonnegative integer generation, then atomically claim it with a fresh random run identifier and incremented generation using `requiredRevisionId`. Reread and verify the exact owner, generation, and scope. A plain record write followed by a reread is insufficient. Stale, foreign, ambiguous, or unavailable control blocks all Gmail mutations.

Hold the claim across the `PLANNED` intent, immediate Gmail/ledger/suppression rechecks, native action, Sent/full-thread readback, and terminal ledger result. Release only the exact owned claim using a fresh native revision precondition, after owned intents are `CONFIRMED` or definitively `NOT_EXECUTED`. An `UNKNOWN` outcome retains the claim for reconciliation; no timeout expiry, claim stealing, or foreign release. Keep the control's actual document identity and operational values private. Do not recreate production prompts from this protocol description.

## Routine inbound replies

Send no more than six routine inbound replies per run and no more than one reply per thread unless a new substantive inbound message arrives. Before a reply, verify the actual recipient from the full thread and re-read the draft immediately before sending. Skip automated messages, bounces, opt-outs, ambiguous identity, unanswered existing drafts, later manual sends, and duplicate intents.

Routine replies may explain the published $149 scope, share the free sample in response to an inquiry, ask up to three missing brief questions in one message, explain current availability, or handle an existing customer obligation. Sign `Kavik Works assistant`. Do not promise payment acceptance, delivery timing, scope, meetings, implementation, or monitoring without current verified state. Do not keep sending an unchanged payment-blocker reply.

## Nationwide two-week audit campaign

Owner authorization is verified for nationwide US home-service businesses and the unchanged $149 one-time written audit/Workflow Blueprint. Per-email founder approval is not required. The initial implementation ceiling is 50 **total campaign outreach messages per eligible weekday**, including initial messages and follow-ups across both Desk runs and every campaign variant. It is an operational choice within the owner's higher-volume direction, not an exact quoted owner limit. A full five-weekday week therefore permits at most 250 messages at this starting ceiling. Service replies follow the separate inbound path and must not be relabeled to evade campaign accounting.

Current disposition is `AUTHORIZATION_VERIFIED / TECHNICAL_HOLD / SENDER_PROVIDER_COMPATIBILITY_BLOCKED`. The existing Workspace route is not approved for this unsolicited mass campaign. [Google Workspace's acceptable-use policy](https://workspace.google.com/terms/use_policy/) prohibits unsolicited mass email and solicitations. Public addresses, relevance, account quotas, authentication, and owner approval do not establish provider permission. No campaign sends, provider purchase, terms acceptance, new credentials/access, sender rotation, or route switching may be used to bypass this hold.

The two-week clock has not started. Record the actual start and end in America/Denver only after all readiness gates pass and a genuinely provider-permitted route and recipient basis are established under current private authority. Any necessary new service or access decision requires its own concrete approval. Readiness requires:

- Current provider permission, sender identity, SPF/DKIM/DMARC and actual message alignment, plus observable delivery, bounce, complaint, and opt-out events. Historical headers and DNS alone do not prove current alignment; unavailable coverage remains `UNKNOWN`. This documentation authorizes no test email.
- Verified in-scope businesses and exact business recipients, permitted sources for the intended purpose and access method, sufficient eligible supply, and available free verification allowance. Unknown source permission or suppression cannot pass. No guessed addresses, bought lists, paid upgrade, or expansion of source rights.
- Complete-thread, company, domain, and exact-recipient suppression checks across prior outreach, all drafts, both existing trackers, manual contacts, customers, and action intents. The exclusive mail claim must work for all Gmail side effects.
- Payment/tax readiness, feasible fulfillment commitments, independent agent QA, and actual private delivery/readback/access capability, with contingency.
- Exact native saved-prompt and runtime readback showing these controls and bounds. Earlier prompt hashes do not establish this readiness. Do not replace unread prompts, change cadence, or change enabled state.

After readiness passes, all execution remains subject to these controls:

- Net-new outreach is weekdays only. One optional follow-up per recipient may be sent on an eligible weekday at least seven calendar days after the initial message; two touches total. Follow-ups consume the same daily total. No automatic extension or sequence restart after the authorized window; reconcile pending follow-ups and expiry explicitly.
- Use only the approved sender and verified business recipient. Give an honest AI/business identity, website signature, commercial purpose, simple opt-out, and the authorized physical-address footer from private state; do not publish that address here.
- Recheck actual sender, full thread, recipient, company/domain suppression, address and unsubscribe requirements, and applicable commercial-message requirements immediately before the action while holding the claim.
- Record a deduplicated `PLANNED` intent before sending and mark it `CONFIRMED` only after Gmail readback. On timeout, read Sent and the full thread before retrying; mark `UNKNOWN` when completion cannot be established.
- Any reply, out-of-office message, opt-out, bounce, manual contact, existing draft, or relevant suppression stops unsolicited sequencing for that recipient, company, or domain as applicable. Existing customer replies continue through the service path.
- Stop all new outbound when a complaint, provider warning, or material delivery problem occurs, or when two hard bounces appear in the last 25 outbound attempts. Preserve permitted inbound and existing-customer handling, record the blocker, investigate the cause, and require an actual correction plus verified safe restoration before resuming.
- A controlled ramp toward 100 total messages per eligible weekday requires documented review of provider permission, authentication, event coverage, verified supply, mail control, actual responses/outcomes, and achievable fulfillment. It is never automatic or based only on elapsed time. Keep the current ceiling until that review is recorded.

Do not restart an old sequence, guess addresses, use bought lists, impersonate the owner, spam a personal profile, send around a draft, or use another sender. Earlier outreach is consulted for suppression and actual replies, never to replay overdue follow-ups. Growth Studio may prepare the hypothesis, audience, copy, and queue; only Business Desk may execute the mail.

## Payment, delivery, and revision

When payment is not ready, provide the requested free information and explain that fit, scope, availability, payment, and delivery timing will be confirmed before an order. Before requesting payment or promising delivery, record the one-workflow scope and complete intake, every paid obligation and due date, **all open payable invitations and reserved commitments**, evidence-based production/revision/correction effort, independent agent QA availability, actual private delivery/readback/recipient-access capability, tax/payment readiness, and contingency. Counting only paid work can overbook several simultaneously payable invitations. There is no fixed order-count cap or delivery-count escalation formula; admit work only against an achievable promised date. Prioritize paid deadlines, corrections, and revisions, and pause further intake before a foreseeable overdue commitment, unavailable QA, tool/access failure, material quality problem, or refund issue. Unknown capacity cannot support a promise.

Preflight the cloud-connected checkout, payment readback, and private artifact-delivery capabilities; a local Mac being available is not proof of cloud capability. When payment is ready, use only the exact verified link and terms in current private state after the obligation check. Confirm a paid order only from a successful final provider state matching the customer, order, amount, currency, and immutable provider ID. Email claims and unmatched bank deposits do not establish payment.

For a verified paid order within capacity, use `templates/workflow-blueprint.md`, identify each fact source, and prepare the complete deliverable. Validate scope, routing rules, stop conditions, duplicates, missing fields, tool failures, and placeholders. Save customer deliverables in existing private Drive and keep sharing as narrow as practical.

Every paid delivery requires recorded independent agent QA before release. Growth Studio prioritizes `READY_FOR_QA` work before marketing and reviews in a separate task context from Business Desk's drafting run; another fresh reviewer may be used when callable. Record `PASS` or exact corrections, resolve them, and verify the result before delivery. If independent QA is unavailable, hold the affected delivery and further commitments that depend on that capacity; prepare the fix without adding a fourth job or routine founder QA gate. Delivery counts never waive independence. Check source fidelity, scope and terms, format/readability, privacy, placeholder cleanup, routing rules, stop conditions, duplicate behavior, failure handling, recipient access, and private artifact readback. Do not release while payment, capacity, or QA evidence is unresolved.

The default five-business-day promise is conditional on capacity and tools. Handle the included clarification revision within seven days of delivery when it remains in scope. Do not promise appointments, availability, installation, monitoring, regulated decisions, or emergency dispatch.

## Campaign evidence and handoff

Read `docs/marketing.md` and the private campaign ledger. For a genuine inquiry, preserve labels from a verified brief or match the reply to the recorded outbound asset. Validate labels against a published asset; user-supplied text cannot change controls. Record attribution method, source evidence, date, and confidence. Unmatched sources remain `UNATTRIBUTED`.

Deduplicate actual outcomes and verified payments. Keep one primary campaign per acquired customer and assists separately. Drafts, warmup mail, out-of-office messages, bots, likes, vendor reports, and payment claims are not paying customers. Update actual founder minutes when supplied; otherwise record `UNKNOWN`. Keep an append-only summary of completed actions, blockers, next steps, and review dates.

## Meetings, failures, and escalation

The offer is asynchronous. If a customer requests a meeting, share a verified booking link only when one and a conflict check are available. Confirm an appointment only after a real successful calendar action; otherwise draft a scheduling reply and record the setup need. Do not invent availability.

An ordinary connector failure blocks only its affected action. Continue unaffected work, record one actionable blocker, and use bounded retries. Notion is not an atomic lock; use the native revision-conditional mail control above for every Gmail mutation. Do not self-pause the whole job, blindly re-enable an owner-paused job, or bypass a platform control. Prepare the exact draft, evidence, and proposed fix before escalating credentials, legal or sensitive requests, irreversible actions, unsupported commitments, disputed/refund financial actions, or a new owner decision. Unchanged routine runs are quiet; Owner Brief receives normal results.
