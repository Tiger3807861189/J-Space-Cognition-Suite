# J-Space Cognition Suite SV1

[Simplified Chinese](README.zh-CN.md)

[![Concept DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.21971181.svg)](https://doi.org/10.5281/zenodo.21971181)

J-Space is an inference-time workspace and control suite for complex reasoning, repository
engineering, coordinated agents, and authorized security analysis. You install one skill,
load relevant modules, and keep long-task decisions connected to durable evidence.

Its thirteen modules share one premise and one routing entry. Standard-library Python
scripts persist state, reread actual source text, detect stale maps and evidence, and return
blocking results when a required condition is missing. The host supplies tools and agents.

## Quick start

You need a host that can load a local `SKILL.md` and retrieve its supporting files.
Python 3.10+ is needed for executable controllers and validation; low/medium can use the
documented prose fallback. No pip dependencies or background service are required.

1. Copy the complete [`j-space/`](j-space/) directory into your host's Skills directory.
   Obtain that directory from the host's own configuration; no universal location or
   invocation syntax applies to every host. Keep `SKILL.md`, `modules/`, `references/`,
   and `scripts/` together; avoid an extra nested `j-space/j-space/` directory.
   Copy `LICENSE` and `THIRD_PARTY_NOTICES.md` alongside the installed `SKILL.md` when
   distributing the standalone skill. Use an empty destination to avoid mixing installs.
2. Use Python 3.10 or later to verify the installed directory:

   ```text
   <python-command> <skill-root>/scripts/verify_suite.py
   ```

3. Reload the host if it discovers skills only at startup. Select `j-space` through its
   skill UI. Use `$j-space` or `/j-space` only if that host documents the syntax; otherwise
   ask it to read the installed `SKILL.md` explicitly. Confirm it can retrieve one routed
   module and execute the installed controller's `--help` if you need strict gates.
4. Give it the task and its acceptance conditions:

   ```text
   Use j-space to modify this repository. Inspect the existing contracts, maintain a
   source-backed map, delegate independent work where useful, and verify the final behavior.
   ```

Replace `<python-command>` with your available `python`, `python3`, or `py -3` command.
Resolve `<skill-root>` to the installed directory. Keep the task directory as the working
directory, or pass `--root TASK_DIRECTORY` before a controller subcommand.

For a path with spaces in Bash:

```bash
python3 "/path with spaces/j-space/scripts/control.py" --root "/task directory" status
```

For a quoted interpreter path in PowerShell:

```powershell
& "C:\Python313\python.exe" "C:\Skills\j-space\scripts\control.py" --root "D:\Task Directory" status
```

Run `status` after initializing the task. UTF-8 input supports English and Chinese task
content; use the language requested by the user for deliverables.
Run controllers in the target project's task directory, not the installed skill directory.
Installing the files does not automatically register hooks, launch agents, or grant tool access.

> **Intended use.** This suite is designed for real engineering and production-oriented
> projects with contracts, dependencies, verification, and recovery needs. It is not aimed
> at toy demonstrations such as “a pelican riding a bicycle.” Its suitability for serious
> work is a design focus, not a guarantee that any untested deployment is production-ready.

## Operating levels

| Level | Use | Control |
|---|---|---|
| `low` | A direct answer checkable at a glance | Fast pass; no persistent setup |
| `medium` | A bounded deliverable with a few dependent steps | Full pass; selective modules and delivery audit |
| `high` | Multi-file, multi-stage, or persistent work | Loop; shared state, source refresh, evidence checks |
| `xhigh` | Difficult integration or competing approaches that benefit from a team | Loop plus bounded agents, second consideration, and independent review |

`media` is an accepted alias for `medium`. Raise the level when the task's uncertainty or
dependencies require it. Use agents proactively when independent work justifies coordination.
When the host lacks agents, record the limitation and perform sequential checks.

## A short tutorial for all four levels

Select the skill first. In commands below, replace `<python-command>` and `<skill-root>`
with your installed interpreter and skill directory, quote paths containing spaces, and
work in the target task directory. The example artifact names refer to files you create
from actual work and checks; do not create empty or fabricated evidence just to pass a gate.

### low — a bounded check inside engineering work

Ask: “Use j-space at low to check whether this configuration change preserves the timeout
unit. State the conclusion and its evidence; do not expand the task.” Read the relevant
input, check the one constraint, and return the result. No state initialization is required.
Escalate if the check exposes cross-file dependencies or unresolved uncertainty.

### medium — a small deliverable with dependent steps

Ask: “Use j-space at medium to update this API example and verify its parameters against
the implementation. Keep a short record of the goal, uncertainty, and observed checks.”
Optionally use the lightweight ledger:

```text
<python-command> <skill-root>/scripts/jspace.py note --goal "API example matches implementation" --next "Inspect the endpoint"
<python-command> <skill-root>/scripts/jspace.py note --open "Does the example cover required inputs?" --settled-by "Inspect the endpoint and run the example"
<python-command> <skill-root>/scripts/jspace.py seam
```

Inspect and run the example, then record the actual outcome with
`note --check "Observed result" --by "manual inspection of each input and execution of the reported case" --close 1`.
Write `answer.md`, then run `jspace.py ship answer.md`. This audits text heuristically;
findings are advisory, while unreadable/oversized input is rejected. It does not prove the
API behavior. Do not maintain this ledger alongside the strict controller for the same task.

### high — repository work from inspection to delivery

Ask: “Use j-space at high to repair this repository issue. Preserve public contracts, keep
a source-backed map, run the relevant tests, and finish with evidence against each requirement.”
Follow the **Shared control** section to initialize, read sources, create/sync/view the map,
and pass the work gate. Perform the work; record real verification in `evidence/root.txt`
and a separate acceptance checklist in `evidence/completion.txt`. Keep `src/router.py` below
only if it is a material source dependency; substitute your actual sources and repeat `--source` as needed.

```text
<python-command> <skill-root>/scripts/control.py pulse --event checkpoint
<python-command> <skill-root>/scripts/control.py report --agent root --round 1 --summary "Observed repair and coverage" --evidence evidence/root.txt --completion evidence/completion.txt --source src/router.py --next "Deliver checked result"
<python-command> <skill-root>/scripts/control.py repo sync --map repo-map.json
<python-command> <skill-root>/scripts/control.py repo view --agent root
<python-command> <skill-root>/scripts/control.py repo check
<python-command> <skill-root>/scripts/control.py check --stage ship
```

Update the map's meaning before that final sync. Creating report/checklist files changes
the inventory too. Resolve open questions and security candidates before shipment. Exit 0
allows delivery; a nonzero result names an unmet condition. Repair that condition before
checking again; identical retries without changed evidence are not recovery.

### xhigh — actual independent work and integration

Ask: “Use j-space at xhigh for this integration. Assign an independent contract review to
a real child agent, request its second consideration, reproduce material findings, and
retain disagreements until a discriminating check resolves them.” From an initialized high
task, route before creating reports for the current scope:

```text
<python-command> <skill-root>/scripts/control.py route --level xhigh --module modules/repository.md --reason "Independent integration review"
<python-command> <skill-root>/scripts/control.py read --agent root
<python-command> <skill-root>/scripts/control.py agent add --id reviewer --parent root --task "Inspect the integration contract" --owns src
<python-command> <skill-root>/scripts/control.py pulse --event resume --agent reviewer
<python-command> <skill-root>/scripts/control.py repo view --agent reviewer
<python-command> <skill-root>/scripts/control.py check --stage work --agent reviewer
```

The host must actually launch that child and deliver its own pulse output; an ID is not an
independent model. The child writes distinct `evidence/review-1.txt` and `evidence/review-2.txt`
after two substantive passes, then submits each through `report --agent reviewer --round 1`
and `--round 2`, supplying `--summary`, `--evidence`, `--source`, and `--next` each time.
Root independently checks the finding and writes a separate `evidence/acceptance.txt`:

```text
<python-command> <skill-root>/scripts/control.py review --agent root --target reviewer --verdict accepted --evidence evidence/acceptance.txt
```

Root writes and submits its own report and completion checklist as in high. After all
artifacts are stable, update/sync the map, have **every active agent** run its own `read`
and `repo view`, then run the root ship gate. Goal/core/route changes require fresh report
cycles and reviews. A lost child uses `agent retire` with a reason and active successor,
followed by fresh root completion. If the host truly lacks delegation, record
`note --solo-reason "Specific unavailable capability and resulting review limit"`; do not
simulate independence by driving two identities yourself.

## Shared control

Initialize a repository task with its relevant module:

```text
<python-command> <skill-root>/scripts/control.py init --goal "Acceptance criteria" --next "Inspect entry points" --level high --module modules/repository.md
<python-command> <skill-root>/scripts/control.py read --agent root
```

Maintain a semantic map as a task file, for example `repo-map.json`:

```json
{
  "summary": "Service boundaries and validation routes",
  "areas": [{"path": "src", "purpose": "Request handling and business rules"}],
  "facts": [{"claim": "Requests enter through the router", "evidence": "src/router.py"}],
  "dependencies": [{"from": "src/router.py", "to": "src/service.py", "contract": "Validated request"}],
  "tests": [{"path": "tests", "covers": "Request validation and service behavior"}],
  "unknowns": [{"question": "How do retries affect writes?", "settled_by": "Inspect transaction boundaries and test repeated requests"}]
}
```

Replace example paths and claims with inspected files in your actual task. Then:

```text
<python-command> <skill-root>/scripts/control.py repo sync --map repo-map.json
<python-command> <skill-root>/scripts/control.py repo view --agent root
<python-command> <skill-root>/scripts/control.py check --stage work --agent root
<python-command> <skill-root>/scripts/control.py pulse --event tool --agent root
<python-command> <skill-root>/scripts/control.py note --next "Validate the changed behavior"
```

Read the map before edits. Update its semantic claims after source changes and verification,
then sync and view it again. A fingerprint checks freshness; source inspection and tests
establish whether the claims are true. The controller writes `.jspace/control.json` under a
process lock and derives the shared `.jspace/CONTROL.md` view from that canonical state.

| Capability | Runtime behavior |
|---|---|
| Source refresh | Reads current entry/module files, emits their actual text, and records per-agent hashes and times |
| Pulse schedule | Refreshes on recovery and phase events, configured call count, or elapsed interval |
| Repository memory | Stores a semantic map and content inventory, detects changes, and records map views |
| Durable collaboration | Records bounded ownership, rounds of reports, evidence fingerprints, and independent reviews |
| Security evidence | Tracks candidate, confirmed, rejected, and fixed dispositions with reproduction and controls |
| Work/delivery gates | Returns nonzero when required state, source receipts, map, or evidence is missing or stale |

Read [the controller reference](j-space/references/controller.md) for complete commands,
schemas, evidence rules, budget semantics, and recovery. The optional
[`jspace.py`](j-space/scripts/jspace.py) provides a small standalone ledger and heuristic
text audit for bounded work. Its `ship` output is advisory; use `control.py` for strict gates.

Use `route --level xhigh --module modules/repository.md --reason "Integration needs independent review"`
to raise the level or change active optional modules while preserving task state. Record
checkpoints with `note --check "Claim" --by "Method and coverage" --evidence PATH`.
When checkpoints, questions, or core anchors exist, a changed goal needs `--inherit` (same task
reworded) or `--new-task` with `--next` (archive the previous state and start clean).
Before shipment, root submits `report` with `--completion PATH` containing the goal-by-goal
acceptance check; each delegate supplies its reports and independent review. Then run
`check --stage ship`. The controller reference contains the complete argument sequence.

## Host integration and refresh

To make invocation automatic, wire your host's events to
[`host_bridge.py`](j-space/scripts/host_bridge.py), feed its returned context to the agent,
and honor its `allow` decision. [Host integration](j-space/references/host-integration.md)
defines the JSON contract, event mapping, a minimal adapter, and a connection test.

Default source refresh is five tool events or ten minutes, whichever is encountered first,
with immediate refresh at relevant phase and recovery events. These are configurable
engineering defaults; measure drift and input cost for your host. Time-based refresh runs
when an event arrives, and the scripts do not inject into an idle model on their own.

With no native hooks, call the same commands at explicit boundaries and describe the setup
as cooperative control. With no Python or filesystem, keep a restated conversation ledger
and retrieve source text with available tools. Report the missing executable safeguards.

## Agents, repositories, and security

- [Orchestration](j-space/modules/orchestration.md): give every child the complete skill,
  register its ownership and parent, and require its own source reads. Preserve reports in
  the shared record, return to the same child for a focused second pass, and independently
  check the resulting evidence. Resolve competing proposals through tests, retaining dissent.
- [Repository](j-space/modules/repository.md): map contracts, entry points, dependencies,
  test routes, and unknown areas. Read before editing and synchronize after verification.
  Use separate candidate checkouts when multiple approaches need conflicting writes.
- [Cyber](j-space/modules/cyber.md): trace controlled input to a violated property within
  the authorized environment. Preserve reproduction, expected/observed behavior, a negative
  control, and a supported disposition. Verify repairs at the underlying invariant.
- [Epistemics](j-space/modules/epistemics.md): distinguish observation, inference, and
  uncertainty; recover tacit constraints and turn newly exposed gaps into specific probes.

The existing workspace operations—introspection, directed focus, reasoning bridges, broadcast,
capacity, monitoring, shorthand, markers, and empirics—route into these engineering modules.
Keep one or two ideas active and persist the rest. A child gets the complete suite while
loading only what its current phase requires.

## Validation and evaluation

Run from the repository root:

```text
<python-command> j-space/scripts/verify_suite.py
<python-command> -m unittest discover -s tests -v
```

CI configures Windows, Linux, and macOS. The integrity check covers the entry, shared
premise, module structure, routes, local links, and Python syntax. Regression tests exercise
state, input validation, Unicode, persistence, freshness, coordination, and host events.

Repository gates revalidate explicitly cited map facts even in inventory-excluded directories.
Every active participant must view the final map; goal/core/route changes require fresh
reports and reviews. Use `agent retire` to preserve an abandoned registration's history and
handoff while root reassesses completion. For large trees, configure the trusted bridge's
`--timeout-seconds` and outer host deadline based on measured gate latency. Full content
hashing remains in force. See [the controller contract](j-space/references/controller.md).

Tests establish the implemented behaviors they cover; they do not establish universal model
performance gains or guarantee a host honors the protocol. Check CI results for the exact
commit and environment you plan to use.

## Project layout

```text
J-Space Cognition Suite SV1/
├── .github/workflows/verify.yml
├── .gitignore
├── CITATION.cff
├── CONTRIBUTING.md
├── LICENSE
├── README.md
├── README.zh-CN.md
├── THIRD_PARTY_NOTICES.md
├── tests/
└── j-space/
    ├── SKILL.md
    ├── modules/                  # Thirteen selectively loaded protocols
    ├── references/               # Science, evidence, examples, and runtime contracts
    └── scripts/
        ├── control.py            # Persistent gates, maps, agents, and evidence
        ├── host_bridge.py        # Portable event/context adapter
        ├── jspace.py             # Standalone lightweight ledger and text audit
        ├── workspace-ledger.md   # Lightweight ledger contract
        └── verify_suite.py       # Authoring integrity checks
```

## Research and claim boundaries

[Engineering evidence](j-space/references/engineering-evidence.md) links the primary sources
for J-space, the four knowledge quadrants, LLM-as-a-Verifier, team reconciliation, repository
wikis, and re-reading. [The science reference](j-space/references/j-space-science.md) preserves
the suite's research terminology and source excerpts.

The suite acts through instructions, tools, external state, and host event handling. It
does not modify model weights, measure neural workspace size, or guarantee activation of
different MoE experts. Use sparse routing, broad review, and retained contrary evidence as
engineering patterns; establish their value through observable results.

SV1 is an architectural upgrade. SV1's data and conclusions stand on their own stated
measurement basis; nothing is carried forward from an earlier version.

## Contributors and license

Community contributors include [@forever-ivy](https://github.com/forever-ivy),
[@lanting200](https://github.com/lanting200), [@afeer123](https://github.com/afeer123),
[@ShaneLau2](https://github.com/ShaneLau2), [@menoxz](https://github.com/menoxz), and
[@raelldottin](https://github.com/raelldottin).

J-Space uses [Apache License 2.0](LICENSE). Preserve attribution and the
[third-party notices](THIRD_PARTY_NOTICES.md); external materials retain their own terms.
When redistributing only `j-space/`, include copies of both files. The concept DOI covers
the project; Zenodo mints the SV1 version DOI when the release is archived.
