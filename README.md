# transfer-audit

Takes a scientific claim borrowed from another discipline and emits an assumption ledger: the source result's validity conditions, restated in the target system's language.

## The problem

A competent scientist understands a borrowed result to about 70%. The missing 30% is invisible, and they act on the approximation. The source condition "the test set must be drawn from the distribution of scientific interest" is stored as "use a held-out test set". Every one of the 329 papers surveyed in Kapoor & Narayanan ([arXiv:2207.07048](https://arxiv.org/abs/2207.07048)) is compliant with the second sentence and in violation of the first.

## What it does not do

It generates questions, not verdicts. The source literature already showed these errors cannot be caught by reading papers. UNKNOWN with a specific, answerable question is a success state.

## Status

| Stage | State |
|---|---|
| Ingest, retrieve, align, ledger | Built. Alignment is a gate (mapped slots ≥ 3). The round-trip fidelity check on `target_restatement` is not built. |
| Report HTML, CLI, scorer | Not built. The recall number against `data/ground_truth.csv` does not exist yet. |
| Target-document input | Not built. A two-sentence claim produces 9/9 UNKNOWN, which is the correct answer given that input. |

## Documents

- [Thesis](docs/01-thesis.md) — fidelity is the mechanism, not an aid
- [Assumption ledger](docs/02-assumption-ledger.md) — five axes from the 8-type leakage taxonomy
- [Architecture](docs/03-architecture.md) — ingest → retrieve → align → ledger
- [Benchmark](docs/04-benchmark.md) — ground-truth provenance, why FPR was dropped
- [Findings](docs/05-findings.md) — axis order, status semantics, convergence vs repetition
- [Roadmap](docs/06-roadmap.md) — closed loop, then evaluation
- [Implementation notes](docs/07-implementation-notes.md) — Paperclip CLI behaviour (for implementers)

Agent-facing build spec: [BUILD.md](BUILD.md).

## Quickstart

```
python3.12 -m venv .venv && .venv/bin/pip install -e ".[dev]"
cp .env.example .env          # set ANTHROPIC_API_KEY
# paperclip must already be installed and authenticated on this machine
pytest -m "not integration"
python -m transfer_audit.ingest tests/fixtures/target_claim.txt
```

There is no `transfer-audit` CLI yet. Stages are invoked as modules. Live Paperclip calls need a writable `$HOME/.paperclip`.
