# SV1 controller CLI

You use `scripts/control.py` to bind source reads, repository knowledge, delegated work,
and security assessments to persistent evidence. You use Python 3.10 or later and the
standard library. The controller executes no shell commands and makes no network requests.
Invoke it from your task directory, or put `--root TASK_DIRECTORY` **before** the command.
Quote paths and text containing spaces in both PowerShell and bash. Output is UTF-8.

The controller returns **0** on success and **2** on a blocked gate, invalid input, missing
file, malformed state, or failed persistence. Your host must honor nonzero exits and deliver
the returned context to the requesting agent. A skill cannot independently intercept tools,
schedule itself, spawn agents, or prove that a model understood an emitted document.
Argparse usage errors also return 2. Unexpected internal programming errors retain a
traceback and a nonzero exit distinct from an ordinary `BLOCK`; the host must fail closed
on every nonzero result, not just exit 2.

You can keep a short task at `low` or `medium` without initializing this controller.
Once you initialize it, explicit `check` commands enforce their documented requirements at
every level. `high` and `xhigh` additionally require second-thinking reports from delegates.
The lightweight `jspace.py` ledger remains available; it does not satisfy controller gates.

## Start and refresh

```text
python PATH_TO_SKILL/scripts/control.py init --goal "Observable completion criteria" --next "Inspect entry points" --level high --module modules/repository.md
python PATH_TO_SKILL/scripts/control.py pulse --event resume --agent root
python PATH_TO_SKILL/scripts/control.py repo sync --map architecture.json
python PATH_TO_SKILL/scripts/control.py repo view --agent root
python PATH_TO_SKILL/scripts/control.py repo check
python PATH_TO_SKILL/scripts/control.py check --stage work --agent root
```

`init` requires nonempty `--goal`, `--next`, and `--level low|medium|high|xhigh`.
`media` normalizes to `medium`. Initialization refuses to overwrite existing state.
Use `note --goal "..." --next "..."` to update either or both fields. You can provide
`--solo-reason "Host delegation is unavailable because ..."` to `init` or `note` when an
`xhigh` task cannot use actual agents. Record the unavailable capability and resulting
verification limit; this is an explicit degraded mode, not independent verification.
When core, checkpoints, or questions are recorded, a `note --goal` that differs from the current goal
must say which change it is. `--inherit` marks the same task reworded and keeps everything. `--new-task`
marks a new task: the previous state is archived verbatim to `.jspace/control-<timestamp>.json`, and core,
checkpoints, and questions are cleared while security findings stay. A new task requires `--next` and
refuses `--supersede`, `--close`, and `--reopen` in the same command. Without either flag the change is
refused. To undo an archive, copy it back to `.jspace/control.json`.

You can repeat `--module` to select skill-relative source files. The default active modules
are `self-monitoring.md` for low/medium, `capacity.md` and `broadcast.md` for high, and
`capacity.md` and `orchestration.md` for xhigh, all under `modules/`. The entry `SKILL.md`
is always required. Select repository, cyber, epistemics, or another module when the task
needs it. Active sources must be existing skill-contained Markdown files. The option name
is historical: `--module references/controller.md` is also valid when you need a reference
reloaded at each pulse. The thirteen-module entry table is the normal routing menu, not
an allowlist that forbids references.

Use `route --level xhigh --module modules/repository.md --reason "Independent integration review"`
to raise the level or change phase without resetting state. Omit `--level` to retain it.
The command replaces optional active sources with the supplied `--module` list, retains
the level's defaults, records the routing reason, and invalidates every agent's source
receipt until its next full read or pulse. Re-list every optional source needed in the
new phase. A route cannot lower an active level to evade outstanding obligations. Once a
repository map exists, removing its module does not disable its freshness checks.

You can configure these positive integer options during initialization:

| Option | Default | Meaning |
|---|---:|---|
| `--pulse-count` | 5 | Tool events between source injections, per agent |
| `--pulse-seconds` | 600 | Elapsed seconds before the next observed event reinjects sources |
| `--read-ttl` | 1800 | Maximum source receipt age in seconds |
| `--max-agents` | 8 | Total registered agents, including root |
| `--max-depth` | 2 | Maximum child depth; root is depth zero |
| `--budget` | 100 | Shared registration, report, and review credits |

These intervals are configurable engineering defaults, not experimentally optimal values.
The timer is checked when you call `pulse`; it does not run in the background.

Tune a running task with `tune --pulse-count 3 --pulse-seconds 300 --reason "Two observed stale-context incidents"`.
You may also change `--read-ttl`; omitted settings remain unchanged. Values must be positive.
The controller preserves previous settings and the reason, keeps task state intact, and
requires a full refresh for every agent before more work. Use recorded drift and input cost
to choose the settings; this command does not estimate an optimum or change agent budgets.

`read [SKILL_RELATIVE_PATH ...] --agent ID` opens the actual files, emits their full text,
and records each content SHA-256 and read time for that agent. Its output also includes the
current goal, next action, core, recent active checkpoints, questions, and report summaries.
Omitting paths reads the
entry and every active module. Recalling content or reading on behalf of another agent
does not establish that agent's receipt. Partial reads do not clear a pending full broadcast.

`pulse --event tool|checkpoint|handoff|failure|resume|compact --agent ID` records the event.
Tool pulses inject full current sources when the count, elapsed interval, stale receipt,
or pending broadcast requires it. All other event types inject immediately. Every injection
includes the current goal, next action, participating agent IDs, entry, and active modules.
A changed goal or core, changed repository fingerprint, or root `handoff`, `failure`,
`resume`, or `compact` event marks every child as needing its own new full read or pulse.
Root checkpoints and routine count/time injections refresh root without invalidating child
receipts. Your host delivers each child's output to that child; printing it only in the
parent's context is insufficient. After final repository synchronization, refresh pending
children once before the root shipment hook.

Every pulse, including a tool event where source injection is not due, emits the current
goal, next step, core, recent active checkpoints, open questions, latest report summaries,
and pending broadcasts. Inspect the complete shared Markdown for older records.

## Maintain the shared workspace

```text
python PATH_TO_SKILL/scripts/control.py note --core "Storage contract: writes are idempotent"
python PATH_TO_SKILL/scripts/control.py note --open "Does retry preserve idempotency?" --settled-by "A duplicate-request test"
python PATH_TO_SKILL/scripts/control.py note --check "Retry preserves the tested contract" --by "Local duplicate-request fixture; same key and payload" --evidence evidence/retry.txt --close Q1 --next "Inspect timeout handling"
```

`--core` appends one active anchor; adding a third parks the oldest and keeps two active.
Duplicate anchors move to the most recent position without duplicating active entries.
Parked anchors remain in `parked_core` and the shared Markdown; you can restore one by
passing its text to `--core` again. Keep larger inventories in the semantic map.
A checkpoint requires `--check`, `--by` describing
the method and coverage, and a nonempty `--evidence` file. Open questions require
`--open` and `--settled-by`, and receive stable IDs `Q1`, `Q2`, and so on. Closing an ID
with `--close` requires a new evidence-backed checkpoint in the same command. Both work
and shipment gates recheck the evidence of each closed question. If evidence changes,
use `note --reopen Q1`, investigate, and close it with a new checkpoint. The old checkpoint
and closure history remain available; you do not have to restore stale evidence. Shipment
blocks on open questions. If an uncertainty cannot be settled within scope, document the
boundary and its delivery consequence in evidence before explicitly closing it as a
known limitation. All these records live in the same canonical JSON and derived Markdown.

Both gates also validate every active standalone checkpoint's evidence. To replace a
standalone checkpoint, add `--supersede ID` to a new evidence-backed `note --check` command.
This retains the earlier record as inactive and binds its replacement by ID. A checkpoint
supporting a closed question cannot be superseded. Reopen that question and close it with
a new checkpoint instead; do not use `--supersede` on the retired checkpoint. Reopening retires its former checkpoint
when no other closed question depends on it; historical evidence is preserved without
being presented as an active verified claim.

## Repository knowledge

You maintain a semantic JSON map inside the task directory. A minimal valid map is:

```json
{
  "summary": "The application receives jobs and stores their results.",
  "areas": [
    {
      "path": "src",
      "purpose": "Job parsing, validation, execution, and persistence",
      "dependencies": ["storage adapter"],
      "tests": ["python -m unittest discover -s tests"],
      "coverage": "Entry points and callers inspected; production load unmeasured"
    }
  ],
  "facts": [
    {"claim": "Input validation precedes dispatch", "evidence": "src/dispatch.py"}
  ],
  "unknowns": ["Behavior when the storage service times out"]
}
```

`summary` must be nonempty. `areas` must be a nonempty array, and every area requires an
existing task-relative `path` and nonempty `purpose`. Optional `facts` entries require a
`claim` and task-relative evidence file. The controller attaches a SHA-256 receipt to each
fact and revalidates it at every repository check/view and work/ship gate, including facts
citing inventory-excluded directories. Missing or changed cited files block until you
update the map and synchronize it. Additional fields are retained: record dependencies, contracts, test routes, coverage,
owners, and unresolved questions where useful. Test routes are data; the controller never
executes them. You must assess whether each cited file actually supports its semantic claim.

`repo sync --map PATH` loads your semantic map and records a content inventory, map-source
hash, and branch marker. It does not infer architecture or update your prose for you.
Repository gates apply after you explicitly synchronize a map, or when `repository.md`
or `cyber.md` is an active module. Non-repository reasoning tasks do not require a map.
`repo view --agent ID` checks freshness, emits the map and inventory, and records that this
agent viewed that exact fingerprint. `repo check` returns nonzero when content, map source,
or the observed Git branch marker has changed.

Before editing, run `repo view` and `check --stage work`. After editing, update semantic
facts and run `repo sync`. Every active agent must view the final map before shipment;
re-reading skill sources alone does not refresh a map-view receipt. Sync does
not create a view receipt. A changed fingerprint invalidates an earlier view; an unchanged
sync preserves it. Evidence files and map files are part of the inventory, so adding a
report or review artifact also requires synchronization before a gate can pass.

The inventory excludes directories named `.git`, `.jspace`, `node_modules`, `.venv`,
`venv`, `__pycache__`, `.pytest_cache`, `.mypy_cache`, `vendor`, `dist`, and `build`.
These reserved directory names are compared case-insensitively on every platform.
You must inspect dependencies separately when they are in scope. Symbolic links and Windows
junctions and other Windows reparse points are skipped rather than followed, including
on Python 3.10. File content is hashed in bounded chunks. Ordinary Git repositories expose their `HEAD`
marker; linked external Git directories are not followed. Inventory content still detects
working-tree changes. This is an observation at gate time, not a filesystem transaction
that prevents a concurrent editor from making subsequent changes.

Each repository check hashes all included file contents plus explicitly cited fact files.
Cost therefore grows with file count, byte volume, and filesystem latency; no constant-time
or maximum repository size guarantee applies. Measure gate latency on your actual checkout.
For slow trees, set the trusted bridge `--timeout-seconds` above measured worst-case latency
with headroom, and increase the outer host deadline too. The inventory deliberately does
not reuse size/mtime-only caches: matching metadata does not prove unchanged bytes.

## Shared agents and acceptance

```text
python PATH_TO_SKILL/scripts/control.py agent add --id implementer --parent root --task "Inspect the storage contract" --owns src/storage --owns tests/storage
python PATH_TO_SKILL/scripts/control.py pulse --event resume --agent implementer
python PATH_TO_SKILL/scripts/control.py repo view --agent implementer
python PATH_TO_SKILL/scripts/control.py report --agent implementer --summary "Observed contract and coverage" --evidence evidence/first.txt --source src/storage.py --next "Challenge assumptions" --round 1
python PATH_TO_SKILL/scripts/control.py report --agent implementer --summary "Reconsidered boundary and retained limitation" --evidence evidence/second.txt --source src/storage.py --next "Independent review" --round 2
python PATH_TO_SKILL/scripts/control.py review --agent root --target implementer --verdict accepted --evidence evidence/review.txt
```

`agent add` registers a bounded task and one or more ownership paths; your host must
actually launch the agent. Paths may identify files that the agent will create. The same
ownership may be assigned to multiple agents for review or competing proposals; ownership
is coordination metadata, not an operating-system write lock. Isolate competing edits in
host-managed copies and reconcile their evidence before integration. All agents use the
same `--root` for this canonical control state.

If the host never launched a registration or its scope is abandoned, stop its actual process
and run `agent retire --id ID --reason "Observed reason" [--handoff-to ACTIVE_ID]`.
The successor defaults to the registered parent. Retire active children first; root cannot
retire. The record retains task, ownership, reports, reviews, reason, successor, and time.
Transfer unfinished work to the successor; retirement is not acceptance of an unfinished
deliverable. Root must submit a fresh completion report covering that integration decision.
Retired agents cannot read, work, submit reports/reviews, or register children. Their reports
are excluded from shipment and pending broadcasts; earlier reviews they authored remain
auditable and valid if their bound evidence is current. Retiring does not refund credits,
free a lifetime registration slot, erase findings/questions, or prove the host stopped the
process. If only root remains at xhigh, you still need an explicit solo limitation.

Every registration, report, and review spends one shared credit. Failed commands spend
none. Limits bound controller participation, not tokens, wall time, or unobserved host calls.
You cannot silently extend these limits through the CLI; agree a fresh task scope when the
budget is exhausted. `status` shows limits, remaining task state, and a delegation limitation
when only root is registered. It emits JSON followed by that human-readable limitation in
the root-only case; do not treat its entire output as a JSON API response.

`report` requires current source receipts, a nonempty summary and next action, and a
nonempty evidence file. Round two must immediately follow the **same agent's** round one
and cite a different evidence path while keeping the first artifact unchanged. Describe what was challenged, what changed,
and what remains uncertain; a different hash alone does not establish a better assessment.
You can start a fresh round one after revising work. All reports remain in shared history.

Use repeatable `--source PATH` options to bind every material source dependency to its
current content hash. At least one source dependency is required when repository gates
are enabled. A changed cited source invalidates the report and blocks its review or
shipment even if the report text did not change. Cite complete relevant coverage: the
controller cannot discover an omitted dependency. Sources must be separate from report
and completion artifacts. Root additionally supplies `--completion PATH` with a distinct
artifact checking the goal item by item, applicable tests, delivery contents, and limitations.
Every active agent's report binds to the current goal, core anchors, level, and active source
route. Changing that contract requires a fresh root completion report and a fresh delegate
report cycle with independent acceptance. Round two cannot continue a round one under an
obsolete contract. This conservative rule also rechecks delegates whose scope appears unchanged.

`review` requires a registered reviewer with current reads, a latest target report with
unchanged evidence, `--verdict accepted|revise`, and a separate review evidence artifact.
You cannot review your own report. Acceptance binds to the exact latest report and its
evidence; a new report requires a new review. Delegated reviewers also deliver their own
reports for shipping, and root or another agent reviews them.

`check --stage ship` requires a root report with current completion evidence, accepted
latest reports from **every active delegate**, current report/source/review evidence, and fresh
source reads and applicable map views for all active agents. `high` and `xhigh` require each delegate's latest report to
be round two. Root remains responsible for final acceptance and can work independently
at `high`. A root-only `xhigh` task must record `--solo-reason` or shipment blocks.
You must use an actual independent reviewer for delegated work; registering a second
identity for yourself does not satisfy the protocol.

## Security evidence

```text
python PATH_TO_SKILL/scripts/control.py security add --id F1 --claim "Input crosses a validation boundary" --scope "Authorized local fixture" --repro evidence/repro.txt --expected "Reject malformed input" --observed "Malformed input accepted" --negative evidence/control.txt
python PATH_TO_SKILL/scripts/control.py security resolve --id F1 --status confirmed --disposition remediate --evidence evidence/assessment.txt
python PATH_TO_SKILL/scripts/control.py security resolve --id F1 --status fixed --evidence evidence/fix-verification.txt
```

`security add` creates a `candidate`, never a confirmed vulnerability. You provide a
nonempty claim, authorized scope, expected and observed behavior, reproduction artifact,
and a distinct negative-control artifact. The controller records hashes without executing
the reproduction. `security resolve` accepts `confirmed|rejected|fixed` only with current
original evidence and a separate nonempty assessment or fix-verification artifact.
Resolution history preserves the distinction between the initial assessment and later fix.
`--disposition report|remediate` defaults to `remediate`. An audit-only task can explicitly
choose `report` to deliver a confirmed finding without claiming it is fixed. A `fixed`
assessment requires a prior `confirmed` assessment and distinct new fix evidence.
The fix binds to that latest confirmed assessment; its evidence must remain current when
you record the fix and when you ship. If the assessment changes, record a fresh confirmed
assessment and new fix verification instead of reusing an obsolete confirmation.

You decide whether the evidence proves the claim. Describe the tested environment, exact
local inputs, controls, outcome, coverage, and limitations in those artifacts. A `fixed`
assessment requires rerunning the original reproduction against the fix and checking the
negative control and relevant regressions. A receipt proves byte identity, not vulnerability
validity. Candidates block shipment. A confirmed finding blocks shipment unless its
explicit disposition is `report`; rejected and fixed findings can ship. All allowed final
assessments require unchanged reproduction, negative-control, and resolution evidence.

## Persistence and failure handling

`.jspace/control.json` is authoritative. `.jspace/CONTROL.md` is a derived shared view that
contains the goal, next step, complete agent reports and reviews, semantic map, and findings.
Task strings are rendered as quoted data in fixed section order, so embedded headings or
newlines cannot supply top-level view structure. Canonical JSON preserves their exact text.
Do not hand-edit either file. Mutating commands take an OS-managed cross-process lock;
the lock is released if the process dies. Writes use a temporary file, flush and `fsync`,
then atomic replacement. JSON commits before Markdown. A crash between replacements can
leave a stale Markdown view; the next successful command regenerates it from JSON.
An error after the JSON commit may mean the command took effect despite its nonzero exit;
inspect canonical state before retrying a registration, report, or review.

`status`, `check`, and `repo check` do not rewrite canonical JSON or advance its generation.
They briefly lock to read a validated snapshot, release the lock while inspecting files,
then lock again to compare the exact canonical bytes before returning. A concurrent state
change blocks the result and asks for a retry; the CLI does not retry indefinitely.
A missing or stale Markdown projection is repaired under this final lock without changing
canonical state. Ordinary successful read-only calls do not rewrite an already-current view.
`repo sync` and `repo view` still hold the lock while computing their mutation/receipt;
serialize those operations for large trees. Snapshot checks do not freeze external editors
or prove the filesystem remains unchanged after the observation.

Malformed canonical state fails closed and is never reset automatically. Restore a known
good task-state backup after diagnosing corruption. A lock wait times out after 15 seconds.
Task evidence and maps must be nonempty regular files within the task root, outside
`.jspace` under a case-insensitive reserved-name comparison; absolute paths, traversal,
symbolic links, and junctions are rejected. Skill
reads have the same containment rule relative to the installed skill directory.

Use [the orchestration protocol](../modules/orchestration.md),
[repository protocol](../modules/repository.md), and [security protocol](../modules/cyber.md)
to supply the human or agent judgments that structural gates cannot infer.
