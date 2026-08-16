# BUILD.md — transfer-audit

Agent-facing build spec. Read this fully before writing any code.

Companion documents (human-facing, start at `README.md`):
- `docs/01-thesis.md` — product thesis. `target_restatement` is load-bearing.
- `docs/02-assumption-ledger.md` — domain rationale. Reference only. Do not implement its prose.
- `docs/07-implementation-notes.md` — probed Paperclip CLI behaviour.
- `data/ground_truth.csv` — review-row labels. Human-curated. Never generate or edit this file.
- `data/transfer_bench.jsonl` — 8-case conformance suite. Human-converted. Do not rewrite claims to telegraph leakage types.

## 0. What this is

A CLI that takes a scientific claim borrowed from another discipline and emits an
assumption ledger: a structured audit of whether the source result's validity
conditions still hold in the target system.

Product thesis. The failure mode is not incomprehension. A competent scientist
understands a borrowed result to about 70%, and the missing 30% is invisible to
them. They then act on the approximation. The source condition "the test set
must be drawn from the distribution of scientific interest" is stored as "use a
held-out test set"; every one of the 329 Kapoor & Narayanan papers is compliant
with the 70% version and in violation of the real one.

TRANSLATION FIDELITY IS NOT AN AID TO THE AUDIT. IT IS THE MECHANISM OF THE
AUDIT. If you can state the source's condition precisely in the target's own
language, you can check it. If you can only state it approximately, you cannot.
target_restatement is therefore the load-bearing field. status is a consequence
of it. Unmapped structural slots — places where the source condition has no
counterpart in the target — are not a tool failure; they are where the transfer
is most likely to break, and they must be reported to the scientist.

It does NOT detect errors. It GENERATES THE QUESTIONS that would surface them,
and it reports where a precise question cannot be formed. See section 7.

Hackathon deliverable, ~12 working hours, 2-3 people. Optimise for a working demo
and one benchmark number. Nothing else.

## 1. Hard scope

In scope:
- One Python package, one CLI entry point
- Paperclip CLI via subprocess for all literature access
- JSON files on disk for all state
- One static HTML report
- One script producing three numbers

Out of scope — do not build these:
- Authentication, user accounts, sessions
- Any web server, API, or backend service
- Any database, SQLite included
- Any frontend framework
- Async job queues, workers, schedulers
- Docker, CI, deployment config
- Retry/self-correction loops around the LLM
- A chat interface
- Logging frameworks — print() to stderr is fine

If a task seems to require something out of scope, stop and flag it.

## 2. Stack

Python 3.12
pydantic v2, typer, jinja2, pytest
anthropic  # ingest only. Paperclip has no general LLM endpoint.
           # Key from ANTHROPIC_API_KEY env var, never hardcoded.

Paperclip: shell out to the `paperclip` CLI via subprocess.
The SDK is NOT pip-installable and NOT importable from our venv.
Never import gxl_paperclip. The CLI is already installed and authenticated.
The Paperclip agent skill is at .cursor/skills/paperclip/SKILL.md — read it
before writing any paperclip-touching code.

No other dependencies without justification.

## 3. Repo layout

transfer-audit/
  README.md
  BUILD.md
  docs/              human-facing argument; start at 01-thesis.md
  NOTES.md           stub → docs/07-implementation-notes.md
  ROADMAP.md         stub → docs/06-roadmap.md
  assumption-ledger-v0.1.md  stub → docs/02-assumption-ledger.md
  pyproject.toml
  .gitignore
  .env.example
  src/transfer_audit/
    __init__.py
    models.py      T1 — pydantic models, the data contract
    pc.py          Paperclip subprocess layer
    ingest.py      T2 — target description -> TransferContext
    retrieve.py    T3 — Paperclip search, cross-source
    align.py       M2 — structural slot alignment, gates T4
    ledger.py      T4 — Paperclip map -> LedgerEntry[]
    report.py      T5 — Ledger -> HTML
    cli.py         T6 — typer entry point
  data/
    ground_truth.csv          HUMAN-CURATED. Read-only for the agent.
    transfer_bench.jsonl      HUMAN-CONVERTED. 8-case conformance suite.
    schema/ledger_entry.json  generated from models.py
  eval/score.py    T7
  runs/            gitignored
  tests/

## 4. Data contracts

Define these first. Then every other task is independently buildable.

TransferContext (produced by ingest.py):
  target_claim: str
  target_system: str
  state_variable: str | None
  perturbation: str | None
  readout: str | None
  constraints: list[str] = []
  source_discipline_hint: str | None = None
  source_result: str | None = None  # source half of the claim; objects/mechanisms
  failure_mode: str | None = None
  isolation_unit: str | None = None

The last two are alignment slots, not claim-extraction slots. A short claim
almost never states them; a protocol often does. Leaving them null is correct
and is itself a finding: the target has no stated counterpart for that slot.

LedgerEntry (produced by ledger.py, drives paperclip map --output-schema):
  model_config = ConfigDict(extra="forbid")
  axis: Literal["A_isolation","B_legitimacy","C_domain_of_validity",
                "D_metric_alignment","E_evidence_quality"]
  subtype: Literal["A1","A2","A3","A4","C1","C2","C3"] | None = None
  status: Literal["SATISFIED","VIOLATED","UNKNOWN","NA"]
  source_assumption: str
  target_restatement: str | None = None
  rationale: str
  evidence_lines: str | None = None
  what_would_resolve_it: str | None = None
  source_doc_id: str

Validator: if status == "UNKNOWN" then what_would_resolve_it must be non-empty
and at least 20 characters. This is the anti-gaming rule — see section 7.

Status contract. source_assumption describes the SOURCE paper. status and
target_restatement describe the TARGET, and are judged only against what the
target description actually says:
  SATISFIED  the target description positively states the condition is met, and
             the rationale names the part of it that does.
  VIOLATED   the target description positively shows the condition fails. A
             difference in subject, population or modality between source and
             target is NOT evidence of violation. Inferring failure from domain
             distance is invention, not audit.
  UNKNOWN    the default and the expected majority. The target is a short claim
             and is usually silent on method. Requires a specific answerable
             what_would_resolve_it — the question a reviewer would put to the
             team, not "more information is needed".
  NA         the axis genuinely cannot apply to this transfer.
A ledger that is entirely SATISFIED, or entirely VIOLATED, is a failed audit:
status was set by framing rather than evidence. Both failure modes have been
observed on the fixture — see NOTES.md section 13c.

Emit the JSON Schema from the pydantic model via LedgerEntry.model_json_schema(),
write it to data/schema/ledger_entry.json.

T4 must read data/schema/ledger_entry.json off disk and pass its CONTENTS
inline: --output-schema "$(cat data/schema/ledger_entry.json)". The flag does
NOT accept a file path. The file is still generated from the pydantic model
and never hand-written.

Run output: every run writes runs/<timestamp>/ containing
  context.json, search.json, alignment.json, ledger.json, report.html

Paperclip access layer, src/transfer_audit/pc.py:

  def pc(*args, timeout=300) -> str
  Runs the paperclip CLI. Ignores stderr. RAISES PaperclipError if stdout
  starts with 'ERR:' or if returncode != 0. The CLI reports real failures as
  text on stdout while exiting 0, so returncode alone is not sufficient.
  Returns stdout as a string. No JSON parsing — no probed command emits JSON.

Runs subprocess.run(["paperclip", *args], capture_output=True, text=True,
timeout=timeout). Ignore stderr entirely — the CLI emits a NotOpenSSLWarning
there. Every Paperclip call in the codebase goes through pc(). No exceptions.
Never pass the API key as an argument; auth comes from the ambient OAuth session.

Reading results:
Never parse the human-readable stdout of search or map. Displayed doc ids
are truncated. Always follow a search or map with
`paperclip results <id> --save <path>` and read that file: search saves CSV
with full ids, map saves untruncated doc_id next to each JSON payload.
The model will populate source_doc_id with the paper TITLE rather than its
id. T4 must overwrite source_doc_id with the id known from the search step.
Provenance correctness is a demo-critical property.

## 5. Tasks

Build in order. Each has an acceptance test that must pass before moving on.

T1 models.py — define the models above, emit data/schema/ledger_entry.json.
Accept: pytest proves a valid entry parses, an entry with an extra field is
rejected, and an UNKNOWN entry with empty what_would_resolve_it is rejected.

T2 ingest.py — build_context(text) -> TransferContext. One call that fills the
slots. Missing slots become None, not guesses.
Accept: runs on tests/fixtures/target_claim.txt, writes valid context.json.

T3 retrieve.py — find_sources(ctx, source_discipline=None) -> list[str] doc ids.
Query by schema slot, not keywording.

Fan out by ROLE, not by venue. Splitting one query across two source flags was
tried and rejected: it returns the same discipline from different journals, so
the audit only ever sees the target half of the transfer. See NOTES.md section
11 for the probe. The two legs ask different questions:

  source leg — queries the source field's own objects and mechanisms first, then
  the conditions under which that result holds, in the field's terms, on arxiv:
    paperclip search "<discipline>: <source objects>; regimes, limits, and
    assumptions under which the result holds" -s arxiv -n 5
  Do not lead with external-cohort / inclusion-criteria / train-test language.
  That vocabulary is the clinical-prediction cluster; a discipline prefix does
  not leave it. See docs/05-findings.md. After search, classify each source-leg
  paper in-discipline or generic and warn on stderr when in-discipline < half.
  Below that floor, the break-point table is not field evidence.

  target leg — queries the target slots (state_variable, target_system, readout,
  perturbation, constraints) for the literature the claim is applied TO:
    paperclip search "<target slots>" -s pmc,biorxiv -n 5

source_discipline_hint is load-bearing for this and the extractor infers it only
~4 runs in 5 (NOTES.md section 12), so it is operator-overridable: find_sources
takes source_discipline=, and T6 exposes --source-discipline. Precedence is
override, then the inferred slot. With neither, the source leg falls back to the
source objects if known, otherwise the target slots, still without methods
vocabulary, and warns loudly on stderr — that run still returns two sources but
is topically narrower, and the operator should know.

Prune weak retrievals at query-construction time, never with `paperclip filter`:
filter rewrites the stored result set in place, which breaks `map --from` and so
breaks T6 --replay (NOTES.md section 13d). Do not prune by asking for inclusion
criteria and train-test splits: that language retrieves a methods genre, not
auditable source papers, once the pin leaves ML-adjacent fields. Weak papers
that survive are held out by align (extraction_quality 0). A doc-id denylist
(retrieve.DEFAULT_DENY, overridable via deny=) is the escape hatch.

Cap total at 10 documents. Paperclip docs are explicit that map is fast only on
3-10 papers. Do not raise this cap; it will make the demo time out. Merge the
legs round-robin so hitting the cap cannot drop a whole discipline. Denied docs
lower the total rather than being backfilled, because over-fetching would push
the number of papers map processes above the cap.
Accept: returns 3-10 doc ids from at least two distinct sources.

M2 align.py — score_alignment(ctx, retrieval) -> AlignmentReport.
Sits between T3 and T4. For each retrieved paper, extract the seven structural
slots (system, state_variable, perturbation, readout, constraints,
failure_mode, isolation_unit) from the paper itself via map, then compare
each slot against the target context. Slot names are stable; their meanings
in the extract prompt are roles, not ML terms. isolation_unit is the unit
across which independence is assumed (subject, oscillator, forager), not
specifically a train/test split. perturbation is what is varied or driven
(an intervention, a control parameter, a depletion schedule). ML phrasing
is one example among several. Comparison is deterministic:

  mapped    paper instantiates the slot AND the target has a counterpart
  unmapped  paper instantiates the slot AND the target has no counterpart
  absent    the paper does not instantiate the slot

Two scores:
  extraction_quality  mapped + unmapped. Gates. Zero means nothing was
                      extracted and the paper does not enter T4.
  break_richness      unmapped count. Does not gate. Higher is more useful.

Unmapped slots are aggregated across extracted papers into a break-point
summary, ranked by how often the source literature states a slot the target
leaves silent. That summary is first-class run output, printed before the
ledger. Per-paper repetition of the same unmapped slot is not a finding.

The old mapped>=3 cut is retired: on this fixture it was structurally
untestable (see docs/03-architecture.md).
Accept: on the fixture, an all-null extraction is held out; the break-point
summary ranks isolation_unit first; at least one ICU paper and one
neuroimaging prediction paper are extracted.

T4 ledger.py — build_ledger(ctx, doc_ids) -> list[LedgerEntry].
paperclip map --from <s_id> --output-schema data/schema/ledger_entry.json
Parse, validate, drop invalid entries and count them.
Do not build a retry loop. Paperclip already gives one correction attempt.
Accept: >=5 valid entries covering >=3 distinct axes on the fixture. Prints drops.

T5 report.py — jinja2, single self-contained HTML, inline CSS, no CDN, no JS build.
Five sections, one per axis. Colour by status. Every entry shows source_doc_id
and evidence_lines.
Accept: opens in a browser offline and renders the fixture ledger.

T6 cli.py — typer:
  transfer-audit run --claim-file path.txt --out runs/<ts>
    [--source-discipline "neuroimaging"]   pins the T3 source leg
  transfer-audit score --ledger runs/<ts>/ledger.json
  transfer-audit run --replay runs/<ts>
Accept: run completes end to end in under 4 minutes, produces all four files.

T7 eval/score.py — not in the repository. The suite was scored 16 Aug 2026
by the verifier in docs/08-transferbench.md, recorded in
runs/conformance/results.json. Observed: 5 of 8, never a rate. L2 is 0 of 2.
One of the five hits (TB11) was handed over by the claim text. Status
distribution: 62 UNKNOWN / 0 SATISFIED / 0 VIOLATED / 0 NA, n=62, 1 drop.
Uncovered: L3.1 (Tu 2018, Lyu 2021 unread). If a scorer is later written it
must print "5 of 8" (never 0.625), then the four-way status distribution,
and must not quietly bank TB11. Seven of eight types are one paper each;
a rate implies a sampling distribution the suite does not have.

FPR was dropped. H2 produced four negative controls, of which one is fetchable
(NC04). n=1 is not a number. status_distribution measures the same property —
whether the tool knows when to stay quiet — with no ground truth. A healthy
ledger is mostly UNKNOWN with specific what_would_resolve_it values, some
SATISFIED, and few VIOLATED. A tool that marks everything VIOLATED shows up
immediately. data/negative_controls.csv is kept: NC04 is one real scored
control and the file documents an honest attempt.

## 6. Human-only tasks — do not assign to the coding agent

H1 data/ground_truth.csv. CLOSED. 20/20 rows labelled from Table 1; two
adjudicated. File is read-only.

H2 Clean negative controls. CLOSED. Four papers found, one fetchable
(NC04 / arx_1807.01068). IEEE controls are paywalled. FPR dropped from T7
(n=1 is not a number); replaced by status_distribution. Keep
data/negative_controls.csv.

H3 Precision judgement. Judge and score 10 generated entries as meaningful or not.
Cannot be automated in 12 hours. Say n=10 on stage.

H4 Claim conversion. CLOSED. 8 of 20 review rows converted to
data/transfer_bench.jsonl. Claims written from how each primary study
describes itself, not from the review's criticism (contamination procedure
in docs/04-benchmark.md). Arp stands for L2 only. L3.1 is uncovered
(UNCOVERED_L3.1 in the suite file). Vandewiele and Roberts not chased.
data/ground_truth.csv is unchanged. Critical path for T7.

## 7. Two rules that must not be violated

The tool generates questions, not verdicts. The source paper proves these errors
cannot be caught by reading papers. Any code, prompt, or copy that claims to
DETECT leakage from text is wrong and will not survive judging. UNKNOWN with a
good what_would_resolve_it is a success state, not a failure.

Guard against UNKNOWN-spam. An agent maximising conformance will mark every axis
UNKNOWN. The mandatory specific what_would_resolve_it field is the structural
guard; reporting precision and status_distribution alongside the 8-case count
is the reported guard. Never report a rate. Never report conformance alone.

## 8. Demo path

The only path that must work flawlessly. Pre-compute everything else.

1. Paste a real target claim from the team's domain scientist
2. transfer-audit run — under 4 minutes, live
3. Report opens: five axes, mixed statuses, every claim traceable to a doc id
4. Point at one VIOLATED entry — this is the finding
5. transfer-audit score — conformance as "N of 8", precision, and the status distribution, shown from file. L3.1 is uncovered.

Build the --replay flag early, not at 10am on Sunday.
