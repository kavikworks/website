# Offline buying-intent validation

`scripts/buying_intent_validator.py` normalizes reviewer-annotated local JSON and
evaluates research gates with Python's standard library. It does not discover
sources or verify assertions on the internet. Its output is research evidence
for review, and every document and row has `send_ready: false`. The module always
reports `collector_ready: false` and `pilot_started: false`; fixture success
cannot start or complete a live pilot.

The three existing jobs remain Business Desk, Growth Studio and Owner Brief.
Business Desk remains the sole sender with its existing exclusive mail control,
suppression, intent and reconciliation gates. This module has no network
adapter, API call, scraping, Gmail operation, external classifier, scheduler,
production integration or site dependency. The USD149 one-workflow written
Blueprint offer, static site, hosting, capacity and spending controls remain
governed by the existing runbooks. Jev is optional future work requiring a
separate justified decision; it is not a dependency.

## Run locally

```sh
python3 scripts/buying_intent_validator.py /private/path/input.json
# Or supply the same document on stdin:
python3 scripts/buying_intent_validator.py < /private/path/input.json
python3 -m unittest discover -s tests -p 'test_buying_intent_validator.py' -v
python3 scripts/check_site.py
node --test tests/workflow-check.test.cjs
```

The command writes JSON to stdout and never writes the input. Invalid JSON,
duplicate JSON keys, unsupported versions, unexpected fields, invalid enums,
types, URLs or dates fail with exit status 2 and a JSON error on stderr. Error
messages report schema paths without echoing input values. Valid documents exit
0 even when every research gate is held or blocked; examine each row's `gate`.
There is no implicit current clock: the caller supplies a frozen `as_of`.

Only wholly invented `TEST_ONLY` data and reserved `.example` domains belong in
the public fixtures. Real research, suppression evidence, contact or message
IDs, private operational URLs, credentials and customer data belong in existing
private records, never this checkout or a PR. Keep real inputs and redirected
outputs outside the public checkout. The module cannot determine whether a
caller's free text contains sensitive data; publication still requires review.

To exercise the fixture's base document without storing generated output:

```sh
python3 -c 'import json; print(json.dumps(json.load(open("tests/fixtures/buying-intent-synthetic.json"))["base_document"]))' | python3 scripts/buying_intent_validator.py
```

## Input contract: schema 1.0

The top-level object has exactly five keys:

| Key | Contract |
| --- | --- |
| `schema_version` | `"1.0"` |
| `as_of` | ISO date or timezone-aware ISO datetime; required |
| `run_id` | Nonempty local run label; required, no secrets |
| `access_mode` | `MANUAL` or `AUTOMATED`; eligibility scenario only, never an instruction to fetch |
| `records` | Array of reviewer-annotated records; an empty array is valid |

`RECORD_SCHEMA` in the script is the closed field/type/enum definition. The
fixture's `base_document` is a complete synthetic input example. Unknown keys
are rejected. Missing nullable fields become JSON `null`; missing or null enums
become `UNKNOWN` (suppression defaults to `NOT_CHECKED`). Reviewer assertions are
not silently filled in. Default `synthetic_fixture` is false; all committed
fixture inputs explicitly set it true.

| Group | Fields and meaning |
| --- | --- |
| `source` | Original `url`, nullable `record_id`, `type` (`COMPANY_STATEMENT`, `JOB_LISTING`, `REVIEW`, `FORUM`, `AGGREGATOR`, `INTAKE_FEATURE`, `VENDOR`, `UNKNOWN`) |
| `source.permission` | `state`: `ALLOWED` / `DENIED` / `UNKNOWN`; `purpose`: `BUYING_INTENT_RESEARCH` / `OTHER` / `UNKNOWN`; `basis_url`, `checked_at`, `reviewer`, `restrictions` list |
| Access | Independent `source.manual_access_state` and `automated_access_state`: `ALLOWED`, `DENIED`, `UNVERIFIED`, `NOT_ATTEMPTED`, `UNKNOWN`; `access_method`: `MANUAL_READER`, `MANUAL_DIRECT`, `APPROVED_API`, `SYNTHETIC`, `UNKNOWN`; nullable `license_reference`, `access_constraints` list and `constraints_state` (`VERIFIED`, `UNVERIFIED`, `UNKNOWN`) |
| `dates` | Nullable `observed_at`, `retrieved_at`, `source_updated_at`, `snapshot_at`, `direct_verified_at`, `expires_at` |
| `identity` | `business_name`, canonical `domain`, `state` (`VERIFIED`, `UNVERIFIED`, `UNKNOWN`), `confidence` (`HIGH`, `MEDIUM`, `LOW`, `UNKNOWN`), `evidence_url`, `author_role`, `author_state`, `author_evidence_url` |
| Author | Role: `OWNER`, `MANAGER`, `BUSINESS_REPRESENTATIVE`, `CUSTOMER`, `THIRD_PARTY`, `ANONYMOUS`, `UNKNOWN`; author state has the same verification enum as identity |
| `fit` | `sector`, `sector_evidence_url`, nullable `sector_exclusion_reason`, `location_claim`, `geography` (`ELIGIBLE`, `OUTSIDE`, `UNKNOWN`), `geographic_basis_url`, `scope` (`IN_SCOPE`, `REGULATED`, `EMERGENCY`, `OUTSIDE`, `UNKNOWN`) |
| `evidence` | Short `text`, `kind` (`OBSERVED`, `INFERRED`, `UNKNOWN`), `category`, `workflow`, nullable boolean `explicit_help_request` and `concrete_problem`, `attribution_state`, `original_state`, `verification_state`, `verification_url`, `uncertainty_reasons` list |
| Evidence annotations | Category: `BUYER_REQUEST`, `OPERATIONAL_PAIN`, `THIRD_PARTY_COMPLAINT`, `STAFFING`, `INTAKE_FEATURE`, `VENDOR_PROMOTION`, `OTHER`, `UNKNOWN`; verification and attribution use `VERIFIED`, `UNVERIFIED`, `UNKNOWN`, with `CONFLICT` also allowed for verification |
| Inference | Nullable `service_hypothesis` is separate from observed evidence and never raises strength |
| `suppression` | `state`: `CLEAR`, `SUPPRESSED`, `UNKNOWN`, `NOT_CHECKED`; `checked_at`, private `evidence_reference` (synthetic placeholder only in fixtures) |
| `lineage` | Nullable `original_source_url` and `original_source_record_id`; boolean `is_repost` |
| `access_error` | `code`: `NONE`, `429`, `TIMEOUT`, `ROBOTS_REJECTED`; nonnegative `attempts` up to 2; `retry_state`: `NOT_ATTEMPTED`, `DEFERRED`, `EXHAUSTED`, `DO_NOT_RETRY`; nullable nonnegative `retry_after_seconds` |
| `measurement` | Nullable `query_id`, `source_hit_count`, `review_minutes_actual`, `cost_observed`, `currency`; `source_hit_coverage`, `review_time_coverage`, `cost_coverage`: `COMPLETE`, `PARTIAL`, `UNKNOWN` |

Numeric observations must be finite and nonnegative, and counts must be
integers. Integer values are limited to 2^53−1 for JSON interoperability.
Null cost/time remains null with its coverage; it is never zero.
The evaluator deliberately leaves cost/time summary totals null with
`NOT_AGGREGATED` coverage because independent observations may overlap. It does
not invent cost per lead, time savings, reply counts or payments.

Dates are either `YYYY-MM-DD` or timezone-aware ISO timestamps. Datetimes are
compared in UTC; date-only `as_of` and expiry values mean the end of that UTC
day. Freshness uses calendar days. Retrieval time is when evidence was returned;
observed time is the source statement's date. Neither retrieval, crawl/snapshot,
page update nor direct verification time substitutes for an absent statement
date. Future provenance/check dates and retrieval/direct verification predating
the statement hold qualification. Compare exact UTC instants when both
assertions are timestamps; otherwise compare calendar days.

## Evidence rubric and gates

Reviewers choose the category based on the short observed claim and source
evidence. This is a transparent annotation evaluator, not a natural-language
intent detector. The evaluator cannot authenticate an author, confirm licenses,
measure distance or consult suppression records itself.

| Class | Strength | Anchor |
| --- | --- | --- |
| `EXPLICIT_BUYER_REQUEST` | 3 | Verified attributable owner/manager explicitly requests help with a supported workflow; original evidence verified |
| `DEMONSTRATED_OPERATIONAL_PAIN` | 2 | Verified business representative describes a concrete attributable workflow problem; original evidence verified; purchasing is not inferred |
| `INDIRECT_EVIDENCE` | 1 | Permitted, attributable customer or third-party complaint describes a concrete workflow problem; hypothesis requiring independent business verification |
| `INSUFFICIENT_SIGNAL` | 0 | Ordinary staffing/intake features, promotion, anonymous/unresolved authors or businesses, inference, unresolved workflows, unverified evidence, stale/expired claims or contradictory sources |

Supported sectors: `HVAC`, `PLUMBING`, `ELECTRICAL`, `ROOFING`, `RESTORATION`,
`LANDSCAPING_EXTERIOR`. Other sectors are excluded; unknown sectors are held.
The initial territory is northeast Denver and nearby service-business territory
at approximately five miles. `ELIGIBLE` requires a reviewer-recorded location
and geographic basis; a general claim to serve Denver cannot establish it.
Supported workflows: `ESTIMATE_FOLLOW_UP`, `SCHEDULING`, `DISPATCH`,
`LEAD_RESPONSE`, `INBOX_HANDLING`, `CALLBACK`. Regulated advice, emergency
response implementation and other excluded service scope block qualification.
An otherwise strong request keeps its factual strength when fit or suppression
excludes it. Fit never increases evidence strength.

Provisional freshness: 0–30 days `CURRENT`, 31–90 `RECHECK_REQUIRED`, over 90
`STALE`, undated/future `UNKNOWN`. Explicit expiry produces `EXPIRED` and current
original-source contradiction produces `CONFLICT` before considering age. Stale,
expired and conflicting evidence has strength 0; otherwise undated pain can
retain class/strength 2 while its research gate is held. These age windows are
conservative implementation defaults, not empirically optimized thresholds.

Qualification requires strength 2 or 3, verified high-confidence business and
applicable author, observed original evidence with verification URLs, current
statement, permitted research purpose, permission basis/reviewer/check date,
selected access mode allowed, known access method, retrieval and direct
verification dates, approved sector and territory with evidence, in-scope
workflow, no unresolved uncertainty, and suppression `CLEAR` with a private
reference checked on the `as_of` day. Restrictions/constraints must have
`constraints_state: VERIFIED` when present; the reviewer must actually apply
them. Automated eligibility also requires a license reference. An allowed
manual reader does not imply automated or commercial reuse permission. The
recorded method must match the selected mode: manual reader/direct for manual,
approved API for automated. `SYNTHETIC` is accepted only with the fixture flag.

Denied use, denied selected access, or purpose `OTHER` emits only permission and
access audit metadata with no identity, claim or hypothesis. Unknown permission
also emits audit metadata and holds the row. Simulated access errors emit only
audit metadata and the exact code/attempt/retry state. `ROBOTS_REJECTED` requires
`DO_NOT_RETRY`; recording a retry state never performs a retry. The module never
fabricates evidence from a failed access attempt.

Output `gate` is `PASS` (qualified for research review), `HOLD` (research needed)
or `BLOCK` (excluded, denied, duplicate or failed access). Dispositions are
`RESEARCH_QUALIFIED`, `RESEARCH_NEEDED`, `EXCLUDED`, `AUDIT_ONLY`,
`MANUAL_REVIEW_ONLY`, `DUPLICATE` or `ACCESS_ERROR`. Required unknowns never pass.
Automated access unknown with allowed manual access yields `MANUAL_REVIEW_ONLY`.
Reasons are stable machine-readable codes, including every held/excluded gate.
No disposition creates a mailing queue or authorizes an external action.

## Identity, duplicates and measurement

Normalization lowercases domains/URL hostnames, removes leading `www.`, default
ports, fragments, known click IDs and `utm_*` parameters, and sorts remaining
query pairs. It preserves original URLs, meaningful queries, scheme, path case,
trailing slash and claim text. It does not guess redirects, aliases or company
mergers. These must be resolved privately by a reviewer.

Stable IDs hash canonical business domain, original source URL and optional
source record ID, observed date and whitespace-normalized claim. Reposts declare
their original source identity and receive `duplicate_of` links. A lone repost
is held until the original evidence is present. Equivalent repeats prefer an
original, passing, canonically spelled URL as representative; suppression and
contradiction in any duplicate cannot be discarded to manufacture a pass.
Unknown required gates in a duplicate conservatively hold the representative.
Expiry in any identical duplicate also overrides its strength and freshness.
Denied or unknown source permission on the same accessed canonical URL strips
all its claims to audit metadata until reconciled. Incomplete source-purpose/access-policy
annotations also hold otherwise qualified claims at the same accessed URL.
Domain suppression applies
across all claims for that domain: any suppression blocks the business; unknown,
missing or outdated suppression holds its otherwise qualified claims.

A newer dated claim from the same business/source creates a new ID with
`supersedes` links. Older claims remain visible and need rechecking. Retrieval
time alone never creates a new claim. Repeated identical inputs are idempotent;
this module keeps no external state. Cross-run deduplication requires retaining
the prior records and evaluating them together. Qualified business yield counts
each canonical domain once even when several signals qualify.

Only qualified research rows are ranked by descending evidence strength and
deterministic signal ID. All qualified rows already have currentness, high
identity confidence and approved workflow/geographic fit; these gates cannot
add strength. `summary` includes input/unique/duplicate rows, gate and reason
counts, and separate synthetic and nonsynthetic qualified research counts.
These are counts of assertions processed, not independently discovered demand.
Public fixture counts must never be reported as real positive sample yield.

## Fixture coverage and remaining acceptance

The fixture file contains a shared complete `base_document` plus named cases.
The tests recursively merge each case's `record_overrides` onto its base record;
`additional_record_overrides` describe duplicate/newer records based on that
same base. Each contract asserts class, strength, gate, disposition, freshness
and reason membership; batch cases additionally assert deduplication and yield.
The fixture wrapper itself is not evaluator input.

The 45 deterministic synthetic contracts cover owner/manager requests,
callback/dispatch pain, two third-party complaints, dispatcher/CSR staffing,
intake features, promotion, anonymous identity, conflicting snippets, expired
aggregators, undated pain, territory/sector/service exclusions, source denial,
manual versus automated permissions, suppression, canonical/repost duplicates,
newer-claim lineage, simulated 429/timeout/robots rejection, recency boundaries,
required unknowns, inference and unresolved constraints. Additional tests cover
missing required fields, invalid schema, conservative duplicate gates, original
URLs, independent fit/strength, null economics, business yield, no network calls,
CLI behavior and repeatability.

Passing these tests validates the offline contract only. Live source permission,
license/robots/rate/cost review, authentic source and identity verification,
private suppression reconciliation, measured sample precision/yield and an
authorized collector remain separate acceptance gates. No two-week observation
window starts here. The next step is private review of this implementation and
an authorized offline manual-ingestion sample; a network collector requires its
own cleared source-access path. Repository checks also verify the existing
static-site contract without modifying the site.
