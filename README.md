# CrossWork

Takes a scientific claim that brings a method from one field into another and emits an assumption ledger: the source result's validity conditions, restated in the target system's language.

This is a prototype, built in roughly 24 hours, exercised end to end on a single fixture claim.

Interdisciplinary input is what raises the quality of the work. A behavioural question answered with a method from statistical physics, a clinical question answered with machine learning — that is where the strongest results come from. The risk is not using another field's method. The risk is that a method's validity conditions do not travel with it, and neither side owns the interface where they should have been restated. This tool exists to make that high-value work safe to do.

That is how the 70% version of a transferred result actually fails. The source condition "the test set must be drawn from the distribution of scientific interest" is stored as "use a held-out test set". Every one of the 329 papers surveyed in Kapoor & Narayanan ([arXiv:2207.07048](https://arxiv.org/abs/2207.07048)) is compliant with the second sentence and in violation of the first.

## What it does not do

It generates questions, not verdicts. The source literature already showed these errors cannot be caught by reading papers. UNKNOWN with a specific, answerable question is a success state.

## Why this matters

**Review capacity.** [Sundial](https://www.sundial.md/blog/announcing-sundial) put the bottleneck this way: the length of task an agent can finish on its own roughly doubles every few months, while a human's capacity to review stays constant. We reached the same problem independently. A scientist applying a method from another field cannot review every assumption it carries. Review capacity is the bottleneck — not comprehension, not access to the literature. This tool makes the validity conditions legible: what the source result depends on, what that becomes in the target system, and therefore what to ask.

**Rigour without slowing the work down.** The output is not a verdict that blocks anything. It is a list of questions with citations (`source_doc_id`) and line numbers (`evidence_lines`), so the scientist can resolve them with the collaborator who actually knows.

**Confirmation bias.** A scientist who wants to apply a method is motivated to believe it transfers. Reading the source paper, they look for permission rather than for conditions. CrossWork is structurally adversarial to that in three specific ways:

- it enumerates conditions exhaustively, independent of what the reader hopes
- the default status is UNKNOWN, not SATISFIED. Confirmation bias works by treating absence of contrary evidence as confirmation; here absence renders as a visible, answerable question
- the status contract forbids SATISFIED without positive evidence in the target description (`SATISFIED` only when the target description positively states the condition is met)

This is a design hypothesis, not a measured result. No study has shown that scientists using this tool exhibit less confirmation bias, and claiming otherwise would be exactly the unearned claim this project exists to surface.

The counter-risk is automation bias: a scientist treating "it did not flag this" as clearance. UNKNOWN is not clearance. That automation-bias risk is untested.

## Architecture

### The pipeline

| Stage | Module | Tool | What the tool does here |
|---|---|---|---|
| ingest | `ingest.py` | Anthropic API (Claude) | fills the seven slots from free text. Used here and nowhere else, because Paperclip's `map` runs over papers, not arbitrary text |
| retrieve | `retrieve.py` | Paperclip (GXL) | two slot-derived `paperclip search` legs across arXiv, PMC, bioRxiv (`-s arxiv` and `-s pmc,biorxiv`) |
| align | `align.py` | Paperclip (GXL) | `paperclip map --output-schema` extracts seven structural slots per paper |
| ledger | `ledger.py` | Paperclip (GXL) | `map` again, schema-constrained, producing `LedgerEntry` objects with doc id (`source_doc_id`) and line range (`evidence_lines`) |
| report | `report.py` | jinja2 | HTML to read; Markdown as the Sundial handoff |
| front-end | `server.py`, `web/` | FastAPI | localhost; runs the five stages live, falls back to a saved run and labels it as saved |

Paperclip auth is OAuth via `paperclip login`, not an API key. Nothing in the codebase handles a Paperclip credential. (`paperclip install` installs the agent skill; it does not authenticate.)

### Where the work goes next

**Sundial — the review surface.** Sundial's shipped instrument is an editor for Markdown and LaTeX ([sundial.md/editor](https://www.sundial.md/editor)). Sun, a local-first system of record, is unreleased — the homepage describes it and offers no product. Neither generates a report, and CrossWork does not ask them to. CrossWork emits `report.md` in the handoff format: source assumption and target restatement sit adjacent as editable prose, because a scientist correcting a translation is the highest-value input this system can capture. The local front-end already persists those corrections to `corrections.json`. The Sundial editor is where that correction happens with attribution and reversibility. No integration with Sun; it is unreleased.

**BenchFlow — the evaluation environment.** This is a roadmap position. The spec exists. The port does not.

TransferBench ([docs/08-transferbench.md](docs/08-transferbench.md)) is specified as a BenchFlow-compatible agent environment — task, verifier, UNKNOWN-spam guard, and a baseline scored 5 of 8. A port would let any agent be scored against that environment, not only this pipeline; capture the full trajectory, so a failure can be attributed to a specific stage; and re-run every prompt or schema change for comparison rather than argument.

What has to happen first: the suite has to grow from 8 cases to several dozen. Seven of the eight leakage types rest on a single paper each, so a score moving from 5 to 6 cannot be distinguished from one case flipping by chance. Iterating against a suite that small would be fitting to noise — which is the failure mode of the 329 papers this project is built on. Only 8 of the 20 review rows are convertible and the ceiling is 10, so this needs a new source of cases. CrossWork does not improve itself through BenchFlow today.

## Status

| Stage | State |
|---|---|
| Front-end | Built. `transfer-audit serve` opens http://localhost:8000 after `pip install -e ".[web]"`. Live runs need Paperclip and `ANTHROPIC_API_KEY`; if either fails, a saved fixture is shown and labelled as saved. |
| `docs/demo.html` | Built. Replays saved runs with no network call. Open the file from disk. |
| Ingest, retrieve, align, ledger | Built. The alignment gate removes extraction failures (no slots recovered from the paper), not weak analogies. Unmapped slots are aggregated as break points ([architecture](docs/03-architecture.md)). |
| Report HTML + Markdown | Built. Worked example, break-point table with n in every cell, ledger grouped by axis. Committed fixture: [example-report.html](docs/example-report.html), [example-report.md](docs/example-report.md) (9/9 UNKNOWN). |
| CLI | `run --claim-file`, `run --replay`, and `serve` built. `--replay` re-renders both reports with no network call. `score` and `answer` are not built. |
| Conformance | **5 of 8** on `data/transfer_bench.jsonl`. L2 is 0 of 2. One of the five hits (TB11) was handed over by the claim text. Status: 62 UNKNOWN / 0 SATISFIED / 0 VIOLATED. Report "N of 8", never a rate. L3.1 uncovered. [TransferBench](docs/08-transferbench.md). Scored ad hoc; `eval/score.py` is not in the repo. The number lives in `runs/conformance/results.json`. |
| Round-trip fidelity check | Not built. That is a separate stage from the alignment gate. |
| Target-document input | Not built. A two-sentence claim produces 9/9 UNKNOWN, which is the correct answer given that input. |

## Documents

- [Front-end](web/index.html) — `pip install -e ".[web]"` then `transfer-audit serve`. Enter a claim; the pipeline stages render as they complete.
- [demo.html](docs/demo.html) — static walkthrough of saved runs, opens offline, no server
- [Thesis](docs/01-thesis.md) — review capacity is the bottleneck; fidelity is the mechanism
- [Assumption ledger](docs/02-assumption-ledger.md) — five axes from the 8-type leakage taxonomy
- [Architecture](docs/03-architecture.md) — ingest → retrieve → align → ledger → report
- [Benchmark](docs/04-benchmark.md) — ground-truth provenance, conformance suite, why FPR was dropped
- [Findings](docs/05-findings.md) — axis order, status semantics, convergence vs repetition
- [Roadmap](docs/06-roadmap.md) — closed loop, then evaluation
- [Implementation notes](docs/07-implementation-notes.md) — Paperclip CLI behaviour (for implementers)
- [TransferBench](docs/08-transferbench.md) — environment spec, scored 5 of 8, L2 is 0 of 2
- [Example report](docs/example-report.html) — fixture ledger, opens offline

Agent-facing build spec: [BUILD.md](BUILD.md).

## Quickstart

Requires Python 3.12 or later. `python3 --version` must report 3.12+. If it does not, call the 3.12 binary directly (on this machine: `/opt/homebrew/bin/python3.12`).

```bash
python3 -m venv .venv
.venv/bin/pip install -e ".[dev,web]"
cp .env.example .env
# set ANTHROPIC_API_KEY in .env
# paperclip must already be installed and authenticated on this machine
.venv/bin/pytest -m "not integration"

# Local product UI
.venv/bin/transfer-audit serve

# Offline: re-render HTML + Markdown from a saved run (no network)
.venv/bin/transfer-audit run --replay runs/<ts>

# Live run
.venv/bin/transfer-audit run --claim-file tests/fixtures/target_claim.txt \
  --source-discipline neuroimaging
```

Live Paperclip calls need a writable `$HOME/.paperclip`. `runs/` is gitignored. The committed fixture report is [docs/example-report.html](docs/example-report.html).
