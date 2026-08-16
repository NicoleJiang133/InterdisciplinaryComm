# BUILD.md — transfer-audit

Agent-facing build spec. Read this fully before writing any code.

Companion documents:
- `assumption-ledger-v0.1.md` — domain rationale. Reference only. Do not implement its prose.
- `data/ground_truth.csv` — benchmark labels. Human-curated. Never generate or edit this file.

## 0. What this is

A CLI that takes a scientific claim borrowed from another discipline and emits an
assumption ledger: a structured audit of whether the source result's validity
conditions still hold in the target system.

It does NOT detect errors. It GENERATES THE QUESTIONS that would surface them.
This distinction is load-bearing — see section 7.

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
  NOTES.md
  assumption-ledger-v0.1.md
  pyproject.toml
  .gitignore
  .env.example
  src/transfer_audit/
    __init__.py
    models.py      T1 — pydantic models, the data contract
    pc.py          Paperclip subprocess layer
    ingest.py      T2 — target description -> TransferContext
    retrieve.py    T3 — Paperclip search, cross-source
    ledger.py      T4 — Paperclip map -> LedgerEntry[]
    report.py      T5 — Ledger -> HTML
    cli.py         T6 — typer entry point
  data/
    ground_truth.csv          HUMAN-CURATED. Read-only for the agent.
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

Emit the JSON Schema from the pydantic model via LedgerEntry.model_json_schema(),
write it to data/schema/ledger_entry.json.

T4 must read data/schema/ledger_entry.json off disk and pass its CONTENTS
inline: --output-schema "$(cat data/schema/ledger_entry.json)". The flag does
NOT accept a file path. The file is still generated from the pydantic model
and never hand-written.

Run output: every run writes runs/<timestamp>/ containing
  context.json, search.json, ledger.json, report.html

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

T3 retrieve.py — find_sources(ctx) -> list[str] doc ids. Query by schema slot,
not keywording. Fan out deliberately across sources:
  paperclip search "<q>" -s arxiv -n 5
  paperclip search "<q>" -s pmc,biorxiv -n 5
Cap total at 10 documents. Paperclip docs are explicit that map is fast only on
3-10 papers. Do not raise this cap; it will make the demo time out.
Accept: returns 3-10 doc ids from at least two distinct sources.

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
  transfer-audit score --ledger runs/<ts>/ledger.json
  transfer-audit run --replay runs/<ts>
Accept: run completes end to end in under 4 minutes, produces all four files.

T7 eval/score.py — reads data/ground_truth.csv and a ledger, prints exactly:
  recall     fraction of labelled leakage types for which a matching
             axis/subtype entry was generated
  precision  fraction of generated entries judged meaningful, see section 6 H3
  fpr        fraction of clean-control cases where any entry is VIOLATED
Accept: prints three numbers with the denominator alongside each, e.g.
"recall 0.71 (12/17)". Small-n is fine; hiding it is not.

## 6. Human-only tasks — do not assign to the coding agent

H1 data/ground_truth.csv. Seeded from arXiv:2207.07048 Table 1. The 14 rows
marked TODO must be read off the PDF by a human. Critical path for T7.

H2 Clean negative controls. Five papers reviewed in the same fields and found
clean. Needed for fpr. Without these the benchmark is not credible.

H3 Precision judgement. Judge and score 10 generated entries as meaningful or not.
Cannot be automated in 12 hours. Say n=10 on stage.

## 7. Two rules that must not be violated

The tool generates questions, not verdicts. The source paper proves these errors
cannot be caught by reading papers. Any code, prompt, or copy that claims to
DETECT leakage from text is wrong and will not survive judging. UNKNOWN with a
good what_would_resolve_it is a success state, not a failure.

Guard against UNKNOWN-spam. An agent maximising recall will mark every axis
UNKNOWN. The mandatory specific what_would_resolve_it field is the structural
guard; reporting precision and fpr alongside recall is the reported guard.
Never report recall alone.

## 8. Demo path

The only path that must work flawlessly. Pre-compute everything else.

1. Paste a real target claim from the team's domain scientist
2. transfer-audit run — under 4 minutes, live
3. Report opens: five axes, mixed statuses, every claim traceable to a doc id
4. Point at one VIOLATED entry — this is the finding
5. transfer-audit score — the three numbers, shown from file

Build the --replay flag early, not at 10am on Sunday.
