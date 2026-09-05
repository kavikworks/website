# Marketing and acquisition

Growth Studio owns customer acquisition within the three-job model. The owner requested campaign-level measurement of outreach, ads, and social posts on September 5, 2026. Use the private campaign ledger linked from the operating policy. Do not create another scheduler or sender.

## Campaigns and execution

Each campaign has one hypothesis, audience, offer, channel, owner, authorized budget, observation window, and decision. Each email variant, post, or ad is an asset with an immutable ID, exact copy/link, native platform ID, actual publication/send time, and state. DRAFT, BLOCKED_CONNECTION, READY, PLANNED, SCHEDULED, PUBLISHED, PAUSED, and COMPLETE are different states. Start observation only after verified publication or sending.

Before publishing, record intent keyed by campaign, asset, platform, and action. Confirm through the returned native identifier and readback. Reconcile an ambiguous result before retrying. A scheduled post is not a published asset.

Start with one small organic campaign and at most one new post per weekly Growth Studio run. Use a useful sample and one clear CTA. Publish only to a verified owned business channel through available authorized tools and recorded channel readiness. If unavailable, preserve the complete asset and one blocker; do not keep producing drafts behind the same blocker. Do not impersonate the founder, use unapproved personal profiles, send DMs, revive cold email during migration, enroll contacts, or expand the preserved vendor lane.

Paid campaigns stay off while payment/conversion verification is unavailable. New ad spend requires a recorded concrete budget and campaign decision. Measuring replies does not authorize launching outreach or spending. The ledger covers existing authorized activity and future approved campaigns.

## Tagged customer journey

New distribution URLs use all four lowercase parameters, each a nonpersonal slug of at most 64 characters:

| Parameter | Meaning |
| --- | --- |
| `utm_source` | Platform, such as `linkedin` |
| `utm_medium` | Channel, such as `organic_social`, `email`, or `paid_social` |
| `utm_campaign` | Campaign ID |
| `utm_content` | Distinct post, ad, or email asset ID |

Never put names, emails, customer/message IDs, or secrets in these parameters. Retain the exact URL in the asset record. Direct replies to email are matched to the verified original outbound message and asset; clicking is not required.

The website carries valid labels through its main marketing pages into the optional email brief. It creates no visitor profile, stores no attribution in cookies or browser storage, and collects no background click events. Visitors can omit the labels. Missing labels do not imply an organic visit or a known source.

The labels describe the current journey, not a complete first-touch or cross-device history. They are editable and shareable. Match them to a real published asset and record `tagged_link` as the method; this is attribution evidence, not proof of causal lift. Direct email, return visits without labels, disabled JavaScript, or omitted source remain unattributed without other evidence. Keep customer-reported sources separately as `self_reported`.

## Outcomes and credit

Business Desk records source, campaign, asset, attribution method, evidence, and confidence on each genuine case. Preserve the first recorded source. Primary acquisition credit goes to the last evidenced campaign touch within 30 days before the first qualified inquiry, then stays fixed for that cohort. Corrections need a reason and journal entry. Without eligible evidence use UNATTRIBUTED. Other observed touches are assists, never extra paying customers.

Deduplicate events by native message, post, order, or transaction ID plus event type. Count a new paying customer once by verified customer identity; keep repeat orders and their revenue separate. Store event dates and acquisition-cohort dates. Never compare replies with an unrelated send cohort.

Track recipients/sends, delivery evidence, human and positive replies, qualified inquiries, meetings when relevant, new paying customers, orders, collected revenue, refunds, fees, attributable spend/cost, actual founder minutes, and material delivery errors. A qualified inquiry is a real potential buyer with an in-scope need and expressed interest. Exclude warmup mail, bots, bounces, opt-outs, OOO, vendor reports, and internal tests from positive demand counts.

For social and ads retain native post/ad IDs, publication counts, impressions, clicks, and timestamps when available. Cumulative platform snapshots must be replaced or converted to a documented delta, never summed across overlapping reports. Keep vendor-qualified results separate until reconciled to actual conversations.

## Scorecard and decisions

Report raw counts, date range/cohort, source, and coverage before rates:

- Outreach reply rate: unique human responders / unique delivered recipients. If delivery is unavailable, explicitly use sent recipients and label it.
- Qualified inquiry rate: qualified inquiries / verified clicks. Without click data report inquiries per published post/ad; do not invent click conversion.
- Buyer conversion: new paying customers / qualified inquiries in the same cohort.
- Cost per qualified inquiry or customer: attributable acquisition spend / outcome count. Zero or unknown denominators produce N/A, not zero cost.
- Return on ad spend: attributed collected revenue / verified ad spend, with refund treatment and coverage stated. It is not profit.
- Contribution: collected revenue minus refunds and known payment, delivery, and acquisition costs. Show justified shared-subscription allocation and missing costs. An incomplete subtotal is not net profit.
- Founder minutes per qualified inquiry and customer: actual owner time, not agent runtime. Zero or unknown time does not imply infinite efficiency.

Review at seven days for obvious errors and 28 days for the campaign decision, or after ten qualified inquiries if earlier. Low exposure is inconclusive. Payment downtime is a funnel blocker, not evidence of unwillingness to pay. One order does not establish a winning channel.

Owner Brief records KEEP, REVISE, PAUSE, or INCONCLUSIVE, evidence, the next single change, its owner, and review date. Growth Studio reads that decision before production, executes permitted corrections, and links the resulting asset/PR. Routine copy, CTA, sample, and audience-fit explanations may improve within scope. Prices, channel authority, paid budgets, and service commitments follow the operating policy. Do not scale beyond founder-time, capacity, quality, or payment limits.
