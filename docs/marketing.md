# Marketing and acquisition

> **PROPOSED / INACTIVE:** This candidate authority remains inactive until the private operations board records `KAVIK-AUTONOMY-20260925-V1` approving the named repository commit and agent prompt hashes. The current GitHub `main` commit alone cannot broaden authority. Existing live rules continue until that activation record exists.

Growth Studio owns the acquisition hypothesis and evidence queue within the three-job model. It runs Monday, Wednesday, and Friday at 11:00 America/Denver. Business Desk is the only one-to-one sender and runs daily at 08:00 and 15:00 America/Denver; net-new outreach is weekdays only. Do not create another scheduler or sender. Store only connected-account status and nonsecret references in Notion or sources; no secrets belong in Notion or sources.

## Campaigns and execution

Each experiment has one hypothesis, audience, offer, channel, owner, authorized budget, observation window, and decision. Each email variant, post, or ad is an asset with an immutable ID, exact copy/link, native platform ID when available, actual publication/send time, and state. `DRAFT`, `BLOCKED_CONNECTION`, `READY`, `PLANNED`, `SCHEDULED`, `PUBLISHED`, `PAUSED`, and `COMPLETE` are different states. Start observation only after verified publication or sending.

Before a send or publication, record an intent keyed by campaign, asset, platform, and action. Confirm through the returned native identifier, Gmail readback, or other authoritative external readback. Reconcile ambiguous results before retrying. A scheduled post is not a published asset, and a draft is not outreach.

Each Growth Studio run selects one bounded experiment and fills only a small execution queue. Before marketing production, it prioritizes any `READY_FOR_QA` paid delivery for independent review and writes the QA result; Business Desk waits for that result. It may publish up to three organic business posts per week when an owned business channel is actually connected and verified. If that channel is unavailable, use the targeted-email or website fallback and record one blocker; do not wait indefinitely for Metricool or keep producing drafts behind the same connection failure.

Business Desk may send an initial targeted US B2B sequence of no more than five new recipients per weekday and 25 per week, with one follow-up at least seven calendar days later and two touches total. Use only verified public business email and the approved sender. Replies, opt-outs, bounces, manual messages, existing drafts, and applicable domain suppressions stop the cold sequence. A complaint or provider warning, or two hard bounces in the last 25 outbound attempts, stops all new outbound; investigate the cause and require an actual correction plus verified safe restoration before resuming. No old sequence restart, guessed addresses, bought lists, personal-profile spam, impersonation, or second sender. See `docs/business-desk.md` for send gates and the full-thread requirement.

Paid campaigns and new paid tools stay off until a separate private decision verifies payment access, budget, conversion evidence, and terms. Measuring replies does not authorize spending. Card placeholder information never belongs in this repository.

## Tagged customer journey

New distribution URLs use all four lowercase parameters, each a nonpersonal slug of at most 64 characters:

| Parameter | Meaning |
| --- | --- |
| `utm_source` | Platform, such as `linkedin` |
| `utm_medium` | Channel, such as `organic_social`, `email`, or `paid_social` |
| `utm_campaign` | Campaign ID |
| `utm_content` | Distinct post, ad, or email asset ID |

Never put names, emails, customer/message IDs, or secrets in these parameters. Retain the exact URL in the asset record. Direct replies to email are matched to the verified original outbound message and asset; clicking is not required.

The website carries valid labels through its main marketing pages into the optional email brief. It creates no visitor profile, stores no attribution in cookies or browser storage, and collects no background click events. Visitors can omit labels. Missing labels do not imply an organic visit or a known source.

The labels describe the current journey, not a complete first-touch or cross-device history. They are editable and shareable. Match them to a real published asset and record `tagged_link` as the method; this is attribution evidence, not proof of causal lift. Direct email, return visits without labels, disabled JavaScript, or omitted source remain unattributed without other evidence. Keep customer-reported sources separately as `self_reported`.

## Outcomes and credit

Business Desk records source, campaign, asset, attribution method, evidence, and confidence on each genuine case. Preserve the first recorded source. Primary acquisition credit goes to the last evidenced campaign touch within 30 days before the first qualified inquiry, then stays fixed for that cohort. Corrections need a reason and journal entry. Without eligible evidence use `UNATTRIBUTED`. Other observed touches are assists, never extra paying customers.

Deduplicate events by native message, post, order, or transaction ID plus event type. Count a new paying customer once by verified customer identity; keep repeat orders and their revenue separate. Store event dates and acquisition-cohort dates. Never compare replies with an unrelated send cohort.

Track new recipients, sends, delivery evidence, human and positive replies, qualified inquiries, meetings when relevant, new paying customers, orders, collected revenue, refunds, fees, attributable spend/cost, actual founder minutes, and material delivery errors. A qualified inquiry is a real potential buyer with an in-scope need and expressed interest. Exclude warmup mail, bots, bounces, opt-outs, OOO, vendor reports, and internal tests from positive demand counts.

For social and ads retain native post/ad IDs, publication counts, impressions, clicks, and timestamps when available. Cumulative platform snapshots must be replaced or converted to a documented delta, never summed across overlapping reports. Keep vendor-qualified results separate until reconciled to actual conversations and immutable payment evidence.

## Scorecard and decisions

Report raw counts, date range/cohort, source, and coverage before rates:

- Outreach reply rate: unique human responders / unique delivered recipients where delivery is verified. If delivery receipts are unavailable, use a clearly labeled sent-recipient fallback; count attempted, sent, delivered, and unknown separately and never fabricate unknown delivery.
- Qualified inquiry rate: qualified inquiries / verified clicks. Without click data report inquiries per published post/ad or delivered prospect; do not invent click conversion.
- Buyer conversion: new paying customers / qualified inquiries in the same cohort.
- Cost per qualified inquiry or customer: attributable acquisition spend / outcome count. Zero or unknown denominators produce `N/A`, not zero cost.
- Return on ad spend: attributed collected revenue / verified ad spend, with refund treatment and coverage stated. It is not profit.
- Contribution: collected revenue minus refunds and known payment, delivery, and acquisition costs. Show justified shared-subscription allocation and missing costs. An incomplete subtotal is not net profit.
- Founder minutes per qualified inquiry and customer: actual owner time, not agent runtime. Zero or unknown time does not imply infinite efficiency.

Give an experiment at least seven days and evidence of 20–40 unique delivered recipients where delivery is verified before the first decision. Count attempted, sent, delivered, and unknown separately. If delivery receipts are unavailable, use a clearly labeled sent-recipient fallback; never call those recipients delivered or fabricate unknown delivery. Review obvious errors at seven days and the experiment decision at 28 days or when the evidence gate is reached. Low exposure is inconclusive. Payment downtime is a funnel blocker, not evidence of unwillingness to pay. One order does not establish a winning channel.

Owner Brief records `KEEP`, `REVISE`, `PAUSE`, or `INCONCLUSIVE`, the evidence, one next change, its owner, and review date. Growth Studio reads that decision before production and executes permitted corrections. Routine copy, CTA, sample, and audience-fit explanations may improve within scope. The public offer remains $149; any price, public scope, or terms change requires a separate concrete owner decision plus matching live site, checkout, and ledger evidence. Channel authority, paid budgets, and service commitments follow the operating policy. Do not scale beyond founder-time, capacity, quality, payment, or evidence limits.
