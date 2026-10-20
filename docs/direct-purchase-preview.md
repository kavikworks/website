# Direct-purchase Workflow Blueprint: private preview

**Local fake demonstration only. Not approved for live purchases or public launch.**
The public site, its existing email intake, live payment configuration, three
business jobs and sender hold are unchanged. Draft PRs for offline research and
campaign policy remain separate. This preview neither requires nor enables cold
outreach. It cannot charge a card, send email, create credentials or deploy itself.

## Confirmed offer and provisional terms

The canonical private operating policy confirms a **$149 USD one-time Workflow
Blueprint** for one quote-request, leasing-inquiry or shared administrative-inbox
workflow: one workflow map, capture fields and routing rules, three editable
templates, setup instructions/tests and one clarification revision requested
within seven days of delivery. Implementation, account access, monitoring,
regulated decisions and emergency dispatch are excluded. Independent agent QA
remains required; there is no routine founder approval gate or fixed order cap.

The preview uses **Workflow Blueprint** throughout. It does not borrow the
published Website Audit 48-hour refund category. The public refund page currently
also has a Workflow Blueprints / AI-Generated Content seven-day category; the
direct-purchase naming and exact terms must be reconciled before launch. No public
policy has been edited by this work.

The [terms and hosting review packet](direct-purchase-review-packet.md) contains
the complete proposed refund/privacy copy, current official pricing, minimal
Cloudflare design, port/testing scope and decisions required before setup.
It is a draft for review; its terms, retention windows and processors are not
approved or published merely because the packet exists.

Draft customer copy, for approval rather than use as live terms:

> Buy your $149 Workflow Blueprint. Describe one administrative workflow; review
> the scope, available delivery date and final price before hosted checkout.
> No account, sales call or account access is required. The written plan includes
> one clarification revision requested within seven days of delivery.

> Draft cancellation and exception treatment: cancel before first delivery for a
> full refund. If we cannot deliver the agreed scope by the agreed date, choose a
> newly agreed date or a full refund. If an unsupported request is identified after
> payment, offer a full refund. If delivered work materially misses
> the agreed brief and is reported within seven days, let the customer choose correction or
> refund under the final approved policy. These are proposed business terms, not
> approved promises or an implemented refund process.

| Launch decision | Current preview | Evidence/decision required before live checkout |
| --- | --- | --- |
| Product and price | Workflow Blueprint, one workflow, $149 USD, quantity one | Approve consistent product naming across site, checkout, receipt, terms and refund policy; retain scope and one-time price |
| Tax | Fake zero tax; displayed as provisional | Determine applicable jurisdictions/registrations and inclusive/exclusive treatment; verify tax code, registrations and actual checkout calculation; do not infer that zero means exempt |
| Cancellation/refunds | Proposed wording above; no refund API | Approve before-first-delivery cancellation, unsupported-after-payment, non-delivery/late delivery and material scope-mismatch handling, deadlines and original-method refunds |
| Turnaround | Exact sample date computed from fictional capacity | Import a complete, current obligation inventory and actual effort estimates/QA slots; prove a feasible date with contingency, including payable invitations and revisions; no blanket five-day promise |
| Privacy | Only fictional local records, no external processor | Approve named payment/hosting/storage/AI/delivery processors, purpose/minimization, retention and deletion windows, legally required payment retention, access/recovery and incident handling; update actual notice before collecting real briefs |
| Provider environment | Only fake provider; no available authorized sandbox was exposed | An existing authorized isolated sandbox, or separate approval for required access; then real webhook signature verification and authoritative retrieval tests. Never test this against a live payment link |
| Production infrastructure | Loopback Python/SQLite demonstration | Approve the minimal durable intake/event/portal implementation on authorized infrastructure, HTTPS/session security, backups, encrypted storage, monitoring and secret management; no paid provisioning is included here |
| Fulfillment | Local case/report state, simulated independent roles | Connect the sole Desk's existing case/action controls and actual independent agent QA/private artifact readback and recipient access; verify exact native job definitions before amendment; preserve cadence/enabled state |
| Launch | Unactivated draft PR and private local preview | Review final terms and evidence, then obtain a concrete launch decision; no merge or production deployment is implied |

## Run the private preview

Python 3.10+ with standard library and timezone data is sufficient. No npm
installation, Stripe SDK, API key, new provider account or live payment resource
is needed. Start from the checkout root:

```sh
python3 -B scripts/serve_purchase_preview.py \
  --data-dir /private/path/outside-every-git-checkout \
  --port 8765
```

Open `http://127.0.0.1:8765`. Use **Try a fictional example**. All amounts,
capacity, dates, payments, reports and operator actions are samples. No card data
or contact information is requested. The support email path is optional; the
complete local flow uses neither email nor an account. Store only fictional,
non-sensitive input here.

The server binds only `127.0.0.1`. The private directory must be outside Git and
owned by the current user; it uses mode 0700 and mode 0600 database/token files.
`operator.token` is a local-only secret, generated on first start and never printed.
Use it on `/operator` to simulate drafting, separate-role QA, delivery and delayed
payment settlement. Never put this token or a recovery code in a URL, screenshot,
PR, command-line argument or public file. Operator buttons are a simulation, not
independent review of actual customer work.

The private recovery code restores the same stored order via a POST body. It is
an accountless bearer credential: anyone holding it can access that fictional
order. Keep it private. A refresh in the same browser recovers the persisted brief
without local storage. The preview intentionally has no production credential
recovery, customer identity verification or retention automation.

Explicitly reconcile the local fake provider without relying on a browser return:

```sh
python3 -B scripts/serve_purchase_preview.py \
  --data-dir /private/path/outside-every-git-checkout \
  --port 0 --reconcile-once
```

Stop the server when done. The private data remains for review; remove only your
own disposable fictional-data directory when its evidence is no longer needed.
No real customer records belong in this prototype database.

## Components and lifecycle

`preview/purchase/model.py` contains the domain state machine, durable SQLite
transactions, fictional capacity calendar and local fake provider.
`preview/purchase/server.py` is a loopback HTTP adapter. The three files under
`preview/purchase/web/` are a same-origin, accessible interface. The public site's
HTML, JavaScript, URLs, hosting configuration and static asset allowlist are
unchanged; `preview/`, scripts, tests, docs and private data are excluded from the
production asset upload. No old Apps Script route is referenced or reactivated.

1. Validate the closed brief schema and supported administrative workflow. Reject
   missing fields; route other/vague/contradictory scope to review and block
   implementation, sensitive, emergency or decision-making requests. This bounded
   rule set cannot prove arbitrary free text is safe and is not a semantic or
   external classifier. Real admission needs a validated scope control appropriate
   to the eventual product; acknowledgments alone are not sufficient evidence.
2. Persist the minimal brief and an opaque order ID. An idempotency ledger prevents
   duplicate submissions and stale retries from overwriting edited scope. Before
   the first checkout, editing reuses the same order and atomically replans its
   capacity. Once a checkout has existed, scope is locked for reconciliation.
3. In a `BEGIN IMMEDIATE` transaction, subtract paid work, existing open payable
   invitations/reserved commitments and this preview's active allocations from
   dated production/QA capacity. Reserve production, corrections, contingency,
   independent QA and revision/QA effort. Dates start at the conditional five
   business-day default and move later if necessary. Unknown, stale, incomplete,
   overbooked or incident-affected inventory cannot produce an offer. There is no
   fixed two-per-week/two-WIP cap or success-count escalation formula.
4. Hold a provisional reservation for 30 minutes; recheck current readiness before
   making checkout payable. First checkout creates a new 30-minute session while
   retaining the same allocated work. Repeated checkout creation returns the same
   session without extending it. This mirrors the lower bound on real hosted
   Checkout expiration; no provider is contacted here.
5. Fake payment events are wake-ups. Re-read the fake provider's persisted final
   state and verify mode, order/session association, product, exact amount,
   currency, quantity, tax and immutable payment identifier. A button or success
   page is not proof. Final successful payment creates exactly one fulfillment
   case, protected by database uniqueness and serialized reconciliation. Events
   can be duplicated, reordered, delayed or missed; startup and explicit
   reconciliation recover persisted provider state without a page return.
6. An abandoned open session continues to reserve capacity. Release only after
   authoritative non-payable expiry or final failure. Processing or unverifiable
   payment retains the reservation beyond the checkout timer. Retry obtains a new
   feasible reservation on the same order only after the previous attempt is
   definitively closed. Older failure/expiry events cannot undo a new attempt.
7. Newly observed paid evidence against released capacity, a past schedule or lost
   readiness creates one `PAYMENT_REVIEW` obligation, never an automatic promise
   against obsolete availability. Payment mismatches/incidents hold intake and
   require explicit reconciliation; they are not silently retried or erased.
8. A paid case moves through drafting, independent-role QA and private delivery.
   A failed QA pass requires correction and a new pass. The report is unavailable
   before delivery. One in-scope clarification request is allowed within seven
   days of delivery and goes through its own drafting/QA/delivery path. The
   previously published report remains visible while an unapproved revision is
   prepared. The local report is generic fictional content, not a commissioned
   report or evidence of actual production delivery.

For a future authorized provider adapter, [Stripe's fulfillment guide](https://docs.stripe.com/checkout/fulfillment)
requires webhooks, authoritative session retrieval and once-only fulfillment,
including delayed payment success. Event signatures must be verified before
dispatch and both completed and asynchronous terminal outcomes reconciled; no
webhook endpoint is exposed by this fake implementation. See also
[limited inventory and Checkout](https://docs.stripe.com/payments/checkout/managing-limited-inventory).
A production adapter still needs provider-specific outbox/idempotency and
reconciliation. The UI's fake provider and SQLite share a transaction. The
separate offline fault harness below exercises two local database boundaries;
neither demonstrates real provider outage behavior or distributed atomicity.
The existing live link is deliberately absent and unchanged.

### Offline event-boundary fixture

`preview/purchase/fixture_events.py` tests the raw-byte signature/timestamp and
event-dispatch boundary without adding an HTTP route. It accepts only explicit
fixture markers, nonlive envelopes, `TEST_ONLY_` keys and local `fake_cs_` session
IDs and the configured synthetic account/environment. Tests cover body/header tampering, stale/future timestamps, rotating v1
signatures, duplicate keys, oversized bodies, event replays/order and payment
labels that contradict authoritative provider state. No real key is generated,
stored or accepted, and no provider is contacted. The server does not import or
expose this fixture handler.

This closes those local boundary contracts, not real webhook readiness. A future
authorized integration must use the official provider SDK with the selected
event format/version, actual account/environment binding, real endpoint secret,
HTTPS delivery, durable event/outbox processing and sandbox end-to-end tests.
The fixture verifier is intentionally unsuitable for live traffic.

### Durable offline outbox and ambiguous outcomes

`preview/purchase/durable_outbox.py` is an explicitly invoked fault harness,
separate from the HTTP/UI flow. It accepts only its exact local `FakeEndpoint`,
`TEST_ONLY_` operation/binding markers, fake resource IDs and fictional reports.
There is no worker process, scheduler, provider adapter or network operation.
Application intent and fake endpoint effects commit to **separate SQLite
databases outside Git**, both mode 0600.

The durable states are `PENDING`, `IN_FLIGHT`, `UNKNOWN`, `CONFIRMED` and
`REVIEW_REQUIRED`. Stable operation keys and immutable payload hashes survive
restarts. A worker claims a 60-second lease, commits it before the endpoint call,
and reconciles endpoint readback before execution. Only this fake endpoint's
authoritative absence permits execution; an unavailable lookup is not absence.
A lost response after a committed effect recovers the same receipt without a
second checkout/artifact. Concurrent or stale workers cannot overwrite another
claim's result. Retry delay doubles from 60 seconds to at most 30 minutes, with
five attempts; exhaustion requires explicit readback-only reconciliation rather
than automatic re-execution. The caller must separately decide any correction.

Unknown creation, expiry or delivery cannot claim released capacity or delivery.
Expiry of a paid/processing fake session retains capacity. Delivery requires
matching artifact-hash readback. Receipts must match configured account and
environment, operation, payload and resource. Optional explicit retirement
removes confirmed payload content after a caller-selected positive window while
retaining the key/hash/result for dedupe; unresolved payloads and historically
confirmed deliveries/expiries with unavailable current readback are preserved.

These are mocked contracts. Real APIs may have finite idempotency windows,
eventual consistency, missing lookup-by-key or ambiguous nonpayable states. The
harness's receipt/absence guarantees cannot be assumed for Stripe or Drive.
Its flags are evidence for tests, not actual admission control or a private
customer delivery system. The UI has not been switched onto this harness.

### Configured payment identity, recovery and retention

`payment_contracts.py` matches authoritative fake snapshots against the fixed
synthetic account/environment and the stored order/session, product, integer
amount/quantity/tax and currency. The model separately requires complete final
paid evidence and checks immutable payment uniqueness, including retired payment
hashes. A signed event and a snapshot agreeing with each other cannot override
the configured identity. Old fake snapshots without the new binding fields are
held for review; migration does not invent provider evidence. Use a fresh
fictional database for this revision rather than repurposing historical samples.

`maintenance.py` adds backward-compatible fields/tables to the existing local
model. `Store.rotate_recovery(old_token, proposed_new_token)` atomically revokes
the old session, changes CSRF and transfers order ownership. The caller retains
the proposed replacement before the request, so loss of its response is
recoverable; an identical retry proves both exact tokens. Only hashes are stored
in its rotation ledger. Rotation is a local Python method, with no new HTTP
route or customer UI. It does not supply production identity verification,
lost-key recovery or email/SMS delivery.

`Store.apply_retention(RetentionPolicy(...))` performs explicit local logical
deletion. All three windows (`unpaid_days`, `delivered_days`,
`empty_session_days`) default to `None` / disabled. Positive integer windows are
test configuration, **not approved public retention terms**. Holds override
deletion. Open/processing/unknown payments, unresolved incidents, undelivered
paid cases and pending revisions remain. Closed unpaid attempts require current
authoritative readback of every attempt. Paid deletion waits until the later of
the revision deadline and latest delivery, plus the selected window. Edits and
new payment attempts restart unpaid inactivity. Legacy activity of unknown age
gets a fresh conservative clock. Empty-session cleanup never removes an owned
order's session.

Cleanup removes brief/report/request content and linked local records, retaining
only hashed submission/event/session/payment replay tombstones. It never
deletes an unrelated order. `Store.retention_hold(order_id, True)` preserves a
local case until explicitly released. This is SQLite logical deletion, not
secure erasure: filesystem remnants, journals, backups, accounting retention,
disputes, processor deletion and legal holds require the eventual production
design and approved terms. No cleanup timer or new job is installed.

## Privacy and isolation controls

Brief text, report content and operator/recovery tokens never enter URLs,
analytics or access logs. Fixed same-origin API routes use JSON bodies, bounded
input, exact Host/Origin checks, CSRF tokens, HttpOnly SameSite cookies, no-store
responses, no-referrer and a restrictive CSP. Text is rendered using safe DOM
text/value operations. Report/recovery access is scoped to the authenticated
opaque session; operator access uses a separate private token and cookie.

HTTP cookies are intentionally local HTTP-only; production requires HTTPS,
Secure cookies and production-grade authentication/authorization. Python's
development HTTP server, raw local SQLite storage, fixed simulated reviewer
identities, local bearer recovery and absence of real webhook verification make
this unsuitable for real customers. Nothing auto-registers a route, scheduler,
worker, webhook, payment link or sender. There is no internet-facing bind option.

## Verification

```sh
python3 -B -m unittest discover -s tests -p 'test_purchase*.py' -v
python3 scripts/check_site.py
node --test tests/workflow-check.test.cjs tests/static-assets.test.cjs tests/cost-worksheet.test.cjs
```

The HTTP tests need permission to bind ephemeral loopback sockets. They use only
fictional data and temporary private directories. Coverage includes supported,
unsupported/vague/decision scope, missing fields, concurrent capacity admission,
open invitations, expiry, failed/processing/delayed and duplicate/reordered
payments, missed browser returns, persistent intake and private recovery,
once-only cases, same-order retries/edits, QA failures, report publication,
revision states/window and HTTP access/privacy controls. Browser QA should cover
desktop and mobile layouts, labels/focus/errors, blocked states, fake checkout,
private report/revision and same-origin-only requests. Keep screenshots/traces
and any local operator/recovery data outside the public checkout.

The extended suite includes 18 synthetic event-boundary/payment-binding tests,
22 separate-database outbox/fault/retry tests and 14 migration/recovery/retention
tests, alongside the original 41 model/loopback HTTP tests (95 total). They
exercise only local fake adapters and fictional records. Passing them does not
establish Stripe integration, a working sandbox, production readiness or approved
customer policies.
