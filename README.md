# CrossWork

Takes a scientific claim borrowed from another discipline and emits an assumption ledger: the source result's validity conditions, restated in the target system's language.

This is a prototype, built in roughly 24 hours, exercised end to end on a single fixture claim.

## Review capacity

[Sundial](https://www.sundial.md/blog/announcing-sundial) put the bottleneck this way: the length of task an agent can finish on its own roughly doubles every few months, while a human's capacity to review stays constant. We reached the same problem independently. Closing the gap means making the work legible: what was done, by whom, and why.

A scientist borrowing a method from another discipline cannot review every assumption it carries. Review capacity is the bottleneck — not comprehension, not access to the literature. This tool amplifies review capacity by making a borrowed result's validity conditions legible: what the source result depends on, what that becomes in the target system, and therefore what to ask.

That is how the 70% version of a borrowed result actually fails. The source condition "the test set must be drawn from the distribution of scientific interest" is stored as "use a held-out test set". Every one of the 329 papers surveyed in Kapoor & Narayanan ([arXiv:2207.07048](https://arxiv.org/abs/2207.07048)) is compliant with the second sentence and in violation of the first.

## What it does not do

It generates questions, not verdicts. The source literature already showed these errors cannot be caught by reading papers. UNKNOWN with a specific, answerable question is a success state.

## Architecture

`src/transfer_audit/cli.py` is the entry point. `run --claim-file` executes ingest → retrieve → align → ledger → report into a run directory; `run --replay` re-renders both reports from a saved run and does not call Paperclip or Anthropic. `src/transfer_audit/pc.py` is the Paperclip transport: every Paperclip call goes through `pc()`, which runs `subprocess.run(["paperclip", *args])`.

**The pipeline.** `src/transfer_audit/ingest.py` reads the claim file, fills a `TransferContext` via the Anthropic API, and writes `context.json`. `src/transfer_audit/retrieve.py` takes that context, runs two slot-derived `paperclip search` legs, and writes `search.json`. `src/transfer_audit/align.py` takes the context and the retrieval, extracts seven structural slots per paper with `paperclip map`, admits papers with `extraction_quality >= 1`, and writes `alignment.json`. `src/transfer_audit/ledger.py` maps `admitted_ids` into `LedgerEntry` objects and writes `ledger.json`. `src/transfer_audit/report.py` takes the ledger, alignment, and context and writes `report.html` and `report.md`.

| Stage | Module | Writes |
|---|---|---|
| ingest | `src/transfer_audit/ingest.py` | `context.json` |
| retrieve | `src/transfer_audit/retrieve.py` | `search.json` |
| align | `src/transfer_audit/align.py` | `alignment.json` |
| ledger | `src/transfer_audit/ledger.py` | `ledger.json` |
| report | `src/transfer_audit/report.py` | `report.html`, `report.md` |

**The data contract.** `TransferContext` and `LedgerEntry` are pydantic v2 models in `src/transfer_audit/models.py` with `extra="forbid"`. `data/schema/ledger_entry.json` is generated from `LedgerEntry.model_json_schema()` and its contents are passed inline to `paperclip map --output-schema` — never a path. Status `UNKNOWN` is valid only when `what_would_resolve_it` is at least 20 characters.

**Tools.** Paperclip (GXL) does literature retrieval and per-paper extraction, via the CLI through subprocess. The Python SDK is not on PyPI and is not importable. The Anthropic API is used for claim ingestion only: Paperclip has no general LLM endpoint, and `map` runs over papers, not arbitrary text, which is why the two are split. pydantic validates the schema, typer is the CLI, jinja2 renders the templates, pytest runs the tests. TransferBench is specified as a BenchFlow-compatible environment in [docs/08-transferbench.md](docs/08-transferbench.md). It is not ported to their runtime. The Markdown report is the handoff format for a Sundial human-agent editor. There is no integration with their unreleased system of record.

**What is not built.** `eval/score.py`, the round-trip fidelity check, target-document input, and the `answer` loop are not in this repository. See [docs/06-roadmap.md](docs/06-roadmap.md).

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
