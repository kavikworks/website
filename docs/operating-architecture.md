# Kavikworks Operating Architecture

This document is the canonical, version-controlled description of how Kavikworks
work moves between local and cloud agents. It is intentionally kept in GitHub
with the technical system of record. If another description conflicts with this
document, update this document first and follow the change-control process below.

## Purpose and non-negotiable rule

Kavikworks must remain operable by a new agent or a new conversation that has no
access to prior chat history. Conversation memory is transient context, not
project state. Durable state is written to the appropriate system of record and
linked across systems. A session is not complete until a new agent could answer
"what is happening, what changed, and what should happen next?" from those
records alone.

The operating workspace in Notion is named **Kavikworks HQ**. Agents should use
that exact name when locating the operational workspace; do not create a second
HQ merely because a search result is incomplete.

## Four systems of record

Each system has a distinct authority. Store a link or short reference across
systems, not a second conflicting copy of the underlying record.

| System | Authority | Put here | Do not treat it as |
| --- | --- | --- | --- |
| **GitHub** | Technical source of truth | Source code, automation logic, prompts, reusable templates, tests, technical architecture, agent instructions, integration contracts, and versioned technical docs | The current business pipeline, a replacement for a Notion task, or a vault of secrets |
| **Notion — Kavikworks HQ** | Operational source of truth | Objectives, projects, tasks, prospect pipeline, decisions, experiments, current status, blockers, next actions, cross-agent handoffs, and concise session notes | A code repository or a place to store large binary artifacts |
| **Google Drive** | Artifact source of truth | Prospect research and assessments, customer-facing documents, proposals, presentations, business spreadsheets, reports, and other durable deliverables | The canonical home for code, reusable prompts, or operational status |
| **Local PC** | Execution environment | Secrets and credentials (in approved local secret stores), runtime environments, browser sessions, temporary data, development tools, and uncommitted work | Durable organizational memory or a reliable handoff destination |

### Local Obsidian wiki boundary

The local Obsidian wiki (`wiki/` in this repository or the companion local
vault) is a **local cache and context layer**. It is useful for summaries,
source notes, cross-links, and working analysis, but it is not cross-agent
operational authority. An entry in the wiki cannot override a current Notion
status, a GitHub file, or a Drive artifact. When a wiki note contains a durable
decision or current status, promote it to the appropriate system and link back
to the authoritative record. Do not assume another agent can see the local
vault.

## Information placement rules

- A reusable assessment-generation template belongs in GitHub; a generated
  assessment belongs in Drive; its status and next action belong in Notion.
- A qualification-criteria decision belongs in Notion; code implementing the
  resulting workflow belongs in GitHub.
- A generated proposal or presentation belongs in Drive; the task, owner,
  status, and Drive reference belong in Notion.
- Keep large content in its authoritative home. Cross-link with stable names,
  record IDs, commit/PR references, or file names as appropriate.
- Do not use a local file, browser tab, or chat transcript as the only copy of
  an important result.

## Notion operating model

Use the existing **Kavikworks HQ** content when it already covers the need.
Reuse or extend existing databases rather than creating parallel databases with
the same purpose. Keep the schema small enough for a human and a fresh agent to
query reliably.

### Databases and minimum fields

The following are the intended initial databases. Property names may be
implemented as Notion property types (title, select, date, checkbox, relation,
URL, or rich text) while retaining these meanings.

#### Projects

Tracks meaningful Kavikworks initiatives.

Minimum fields: `Project` (title), `Status`, `Priority`, `Objective`, `Owner /
Environment`, `Start Date`, `Target Date`, `Next Action`, `Last Updated`, plus
relations to `Tasks`, `Decisions`, `Experiments`, and `Prospects` where useful.
Keep `GitHub URL` and `Drive URL` only when a canonical reference exists.

#### Tasks

The actionable cross-agent work queue.

Minimum fields: `Task` (title), `Status`, `Priority`, `Project`, `Work Type`,
`Execution Environment`, `Due Date`, `Blocked`, `Blocker`, `Next Action`,
`Last Updated`. Add `GitHub Reference`, `Drive Reference`, and `Prospect`
relations or URLs when relevant.

`Execution Environment` must support at least `Cloud Work`, `Local Codex`,
`Either`, and `Human/User`. It is an execution constraint, not an owner field.

#### Prospects

Supports low-volume, deeply researched outreach rather than mass outbound.

Minimum fields: `Company` (title), `Website`, `Location`, `Distance / Locality`,
`Industry`, `Size / Fit Indicators`, `Fit Score`, `Pipeline Stage`, `Research
Status`, `Primary Contact`, `Contact Information`, `Assessment Status`,
`Outreach Status`, `Last Contact`, `Next Follow-Up`, `Next Action`, `Research
Notes`, `Disqualification Reason`, and `Last Updated`.

Use `Drive Folder / Assessment URL`, `Related Tasks`, and `Related
Project` when they exist. Negative reviews are not a qualification gate; a
missing or neutral review signal must not by itself disqualify a prospect.

#### Decisions

Prevents important decisions from disappearing into chat history.

Minimum fields: `Decision` (title), `Date`, `Project`, `Context`, `Decision
Made`, `Rationale`, `Alternatives Considered`, `Consequences`, `Revisit Date`,
and relevant `GitHub Reference` / `Drive Reference`.

#### Experiments

Accumulates outcomes from business and technical experiments.

Minimum fields: `Experiment` (title), `Hypothesis`, `Project`, `Status`, `Start
Date`, `End Date`, `Method`, `Success Metric`, `Result`, `Conclusion`,
`Decision / Follow-Up`, and relevant GitHub or Drive references.

#### Agent Handoffs / Session Notes

Provides operational continuity without storing transcripts or private
reasoning.

Minimum fields: `Session / Handoff Title` (title), `Timestamp`, `Environment`,
`Project`, `Objective`, `Status`, `Summary`, `Decisions Made`, `GitHub
References`, `Drive References`, `Notion Records Changed`, `Blockers`,
`Recommended Next Action`, and `Related Tasks`.

`Environment` supports `Business / Local Codex`, `Personal / Cloud Work`,
`Human/User`, and `Other Agent`. A handoff is a concise
operational summary, not a transcript, activity dump, or chain-of-thought.

### Shared status vocabulary

Use the smallest vocabulary that still distinguishes work. If an existing HQ
database has equivalent values, map to these meanings instead of adding near
duplicates.

| Field | Recommended values |
| --- | --- |
| Project status | `Planned`, `Active`, `Blocked`, `On Hold`, `Complete` |
| Task status | `Backlog`, `Ready`, `In Progress`, `Blocked`, `Done` |
| Priority | `Low`, `Medium`, `High` |
| Prospect pipeline stage | `Research Queue`, `Qualified`, `Assessment Ready`, `Ready for Outreach`, `Contacted`, `Follow-Up Due`, `Replied`, `Disqualified` |
| Research status | `Not Started`, `In Progress`, `Complete`, `Needs Refresh` |
| Assessment status | `Not Started`, `Draft`, `Ready`, `Sent`, `Not Needed` |
| Outreach status | `Not Started`, `Draft Ready`, `Sent`, `Follow-Up`, `Replied`, `Closed` |
| Experiment status | `Planned`, `Running`, `Complete`, `Stopped` |
| Handoff status | `Completed`, `Needs Continuation`, `Blocked` |
| Blocked | Checkbox plus a short `Blocker` explanation; do not encode blockers only in prose |

Dates should use the actual event or target date, not the date an agent happens
to rediscover the record. `Last Updated` is refreshed whenever material state
changes.

### Useful, limited views

Create these only in the existing relevant database and remove redundant views:

- **Tasks:** `Active`, `Local Codex`, `Cloud Work`, `Blocked`, `High Priority`.
- **Prospects:** `Research Queue`, `Qualified`, `Assessment Ready`, `Ready for
  Outreach`, `Follow-Up Due`, `Disqualified`.
- **Projects:** `Active`, `Blocked`, `Recently Updated`.
- **Agent Handoffs / Session Notes:** `Recent Sessions`, `Needs Continuation`,
  `Local → Cloud`, `Cloud → Local`.

Views are navigation aids, not additional sources of truth. A filter should
derive from the fields above; do not maintain status separately in a view title.

### Relationships

Use relations where they improve retrieval and continuity:

- `Projects ↔ Tasks`
- `Projects ↔ Decisions`
- `Projects ↔ Experiments`
- `Projects ↔ Prospects`
- `Tasks ↔ Prospects`
- `Tasks ↔ Agent Handoffs / Session Notes`

Do not add a relation merely because Notion permits it. A relation should answer
an expected agent question such as "what remains for this project?" or "which
handoff explains this blocked task?".

## Google Drive artifact rules

Drive is the durable home for business artifacts. Before creating a new folder
or file, search the existing Kavikworks Drive structure and reuse a matching
location. Avoid reorganizing existing artifacts solely to match this document.

- Use a stable, human-readable name with a date or version when revisions need
  to be distinguished (for example, `2026-08 Prospect Assessment — Company`).
- Keep source material, working drafts, and final deliverables distinguishable;
  do not silently replace a final artifact with an unreviewed draft.
- Put the canonical Drive file or folder reference on the related Notion record.
  Put reusable generation logic or templates in GitHub, not Drive.
- Grant only the access needed for the work. Do not publish sensitive customer,
  prospect, financial, or credential material in a public repository.
- Drive links in Notion are references, not duplicated content. If a file moves,
  repair the canonical reference in Notion and the relevant handoff.
- Generated customer-facing artifacts require human review before external use;
  the review state should be visible in Notion.

## Secrets, privacy, and safe references

- Never commit API keys, OAuth tokens, passwords, private keys, session cookies,
  `.env` files, or raw credentials to GitHub. Keep them in the approved local
  secret store or runtime secret manager and commit only redacted examples.
- Do not put secrets in Notion, Drive artifacts, wiki notes, session notes, or
  task descriptions. A secret's existence may be noted without recording its
  value or retrieval instructions.
- Minimize personal and customer data. Store only what is needed for the work,
  use restricted access for sensitive records, and avoid copying contact data
  into multiple systems.
- Public repository documentation must not contain private Notion or Drive URLs,
  internal IDs, access tokens, or other information that grants access. Use the
  named workspace/database/file and a short human-readable reference instead.
- Session notes record observable work and decisions only. Never store private
  reasoning, hidden reasoning traces, or raw conversation transcripts.

## Synchronization protocol

### Session start

For substantive Kavikworks work, an agent must:

1. Read the repository `AGENTS.md` and this canonical architecture document.
2. Locate **Kavikworks HQ** in Notion and inspect the relevant project, task,
   prospect, decision, experiment, and/or handoff records.
3. Inspect current GitHub state (branch, working tree, relevant files) when
   technical work is involved.
4. Retrieve the relevant Drive artifact or folder when the task depends on a
   business deliverable.
5. Check the local Obsidian wiki only as supporting cache/context, and reconcile
   any durable claim against its authoritative system.
6. Confirm the current objective, acceptance criteria, blockers, and next action
   before starting. If records conflict, record the conflict and escalate the
   decision rather than silently choosing a source.

Agents should retrieve available context themselves. Do not ask the user to
re-explain state that is already recorded in Notion, GitHub, or Drive.

### During the session

Respect the boundaries above. Typical updates are:

- Pipeline stage, task status, blockers, decisions, and next actions → Notion.
- Code, prompt changes, templates, tests, and automation logic → GitHub.
- Assessments, proposals, presentations, reports, and durable spreadsheets →
  Drive.
- Temporary files, credentials, browser sessions, and uncommitted experiments →
  local PC until their durable result is externalized.

Link records rather than pasting large duplicate bodies. If a result changes the
plan, update the relevant Notion record while the context is fresh.

### Session end

For substantive work, complete the following before declaring the session done:

1. **GitHub:** save code, prompts, templates, automation logic, technical docs,
   and architecture changes. Commit/push according to the repository workflow;
   include the commit or PR reference in Notion when available.
2. **Notion:** update current status, completed and newly discovered tasks,
   decisions, blockers, next actions, execution environment, and GitHub/Drive
   references.
3. **Drive:** save durable business artifacts and link their canonical location
   from the relevant Notion record.
4. **Handoff:** create or update a session note when project state materially
   changed or another agent may need to continue it.

Use this test: **Could a completely new Kavikworks agent continue without
reading this conversation?** If not, externalize the missing context before
stopping.

## Session note standard

A normal handoff/session note contains:

- Timestamp and environment
- Objective
- Work completed and key findings
- Decisions made
- Artifacts created or changed
- GitHub commits/PRs
- Notion records affected
- Drive artifacts
- Blockers
- Recommended next action and execution environment

Keep it concise and factual. A note is not a transcript, a verbose log, or a
chain-of-thought record. Never store private reasoning or hidden reasoning
traces. If there was no material state change, a handoff may be unnecessary;
do not create noise merely to satisfy a cadence.

## Cross-agent handoffs

### Cloud Work → Local Codex

When cloud/mobile work needs the local machine:

1. Create or update the relevant Task in **Kavikworks HQ**.
2. Set `Execution Environment = Local Codex`, set status to `Ready` or
   `Blocked` as appropriate, and state the acceptance criteria in `Next Action`.
3. Record the context, blocker, relevant GitHub/Drive references, and any
   required inputs without exposing secrets.
4. Create a concise handoff when the task spans sessions or the context is not
   obvious from the task record.

### Local Codex → Cloud Work

When local work finishes:

1. Persist technical changes in GitHub and durable business artifacts in Drive.
2. Update the Task and relevant Project, Prospect, or Experiment in Notion.
3. Link commits, PRs, and Drive artifacts; mark the acceptance criteria and
   blockers accurately.
4. Create a concise session note and set the next action and execution
   environment (`Cloud Work`, `Local Codex`, `Either`, or `Human/User`).

The same protocol applies to future agent environments. A handoff is successful
only when the receiving agent can act from the records, not from a private
message or the originating conversation.

## Architecture change control

This file is the canonical architecture description.

For a material change:

1. Update this document in GitHub first, including the reason and the affected
   system boundaries or schema.
2. Update `AGENTS.md` only when bootstrap instructions or links need to change;
   do not duplicate the architecture there.
3. Update the Notion schema, relations, or views if the change requires it.
4. Record a material architecture decision in the `Decisions` database in
   **Kavikworks HQ**, with rationale, consequences, and references.
5. Update relevant handoff/session notes so agents do not act on stale
   instructions.

Do not maintain competing architecture documents. If a conflict is discovered,
mark the affected record as needing review, follow the newest version-controlled
document, and resolve the Notion decision explicitly.

## Cold-start checklist

Use this checklist whenever a fresh conversation or agent enters the project:

- [ ] Read `AGENTS.md` and this document.
- [ ] Find **Kavikworks HQ** in Notion; inspect active projects, ready/blocked
      tasks, recent handoffs, and relevant prospect/decision/experiment records.
- [ ] Inspect the current GitHub branch and working tree; identify uncommitted
      work before editing.
- [ ] Open the linked Drive artifact or folder for any deliverable-dependent
      task; verify whether the file is draft, reviewed, or final.
- [ ] Treat the local Obsidian wiki as cache/context only; verify current claims
      in Notion, GitHub, or Drive.
- [ ] Confirm objective, acceptance criteria, owner/environment, and next action.
- [ ] During work, write material state changes to the proper system of record.
- [ ] At the end, update records and create a concise handoff if continuation is
      possible or state changed.

If any required source is unavailable, state the limitation in the relevant
Notion task or handoff and continue only with clearly bounded, reversible work.

## Bootstrap and maintenance expectations

When populating **Kavikworks HQ**, capture existing active work only when it is
supported by authoritative GitHub, Notion, Drive, or clearly identified local
source material. Do not invent projects, history, metrics, or prospect records
to make a database look complete. Record assumptions and unresolved gaps in a
Decision or handoff.

Keep the operating system lightweight: few required fields, concise notes,
useful relations, manageable views, and links instead of duplicated content.
Review stale claims, orphaned records, contradictory statuses, and broken
references as part of normal maintenance; flag uncertainty instead of silently
overwriting it.
