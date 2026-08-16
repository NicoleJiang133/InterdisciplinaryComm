# Architecture

The pipeline is four built stages and several that are specified but not built. The argument that makes `target_restatement` the load-bearing field is in [01-thesis.md](01-thesis.md). Paperclip CLI constraints that shaped the seams are in [07-implementation-notes.md](07-implementation-notes.md).

```
claim text
    → ingest     TransferContext (seven slots)
    → retrieve   source papers, role-split across disciplines
    → align      structural slot comparison; gates the ledger
    → ledger     one LedgerEntry per admitted paper
    → report     not built
```

Literature access is the `paperclip` CLI via subprocess. The one thing Paperclip cannot do is run a model over arbitrary user text, so ingest is the only stage that calls the Anthropic API. Everything that reads papers stays in Paperclip.

## Ingest

`build_context(text) -> TransferContext`

Fills `target_claim`, `target_system`, `state_variable`, `perturbation`, `readout`, `constraints`, `source_discipline_hint`. `failure_mode` and `isolation_unit` are alignment slots: a short claim almost never states them, and leaving them null is a finding.

Slots the text does not state come back null. Inventing a slot is worse than leaving it empty, because retrieve queries the corpus by slot and align compares by slot.

`source_discipline_hint` is inferred only about four runs in five on the fixture, and `claude-sonnet-5` rejects a `temperature` parameter. The slot is therefore operator-overridable (`source_discipline=`). That is demo safety, not a claim that the extractor is stable.

## Retrieve

`find_sources(ctx) -> list[str]`

Two search legs, split by **role**, not by venue. Searching one query against `arxiv` and against `pmc,biorxiv` returns the same discipline from different journals. The audit then only ever sees the target half of the transfer.

- Source leg: queries the source field's objects and mechanisms, then the regimes, limits, and assumptions under which the result holds, on `arxiv`. Classifies each hit as in-discipline or generic; warns when in-discipline falls below half.
- Target leg: queries the target slots, on `pmc,biorxiv`.

Cap 10 documents, merged round-robin. Doc ids are read from `paperclip results <s_id> --save` CSVs, never from stdout, where they are truncated. `paperclip filter` is not used: it rewrites the stored result set in place and would break replay.

A doc-id denylist exists as an escape hatch. It is not the mechanism that holds out weak papers; that is align.

## Align

`score_alignment(ctx, retrieval) -> AlignmentReport`

Built. This is the missing step that retrieve-then-ledger did not have.

Each retrieved paper is mapped for seven slots (system, state_variable, perturbation, readout, constraints, failure_mode, isolation_unit). The extract prompt defines each slot by role, with ML as one example among several — `isolation_unit` is the unit across which independence is assumed, not specifically a train/test split. Comparison against the target context is deterministic:

- **mapped** — paper instantiates the slot and the target has a counterpart. A precise restatement is possible.
- **unmapped** — paper instantiates the slot and the target is silent. A break point.
- **absent** — the paper does not instantiate the slot.

Two scores, not one:

- **extraction_quality** — mapped + unmapped: did we get structure out of this paper at all. This gates. A paper with extraction_quality 0 (every slot absent) cannot be audited and does not enter the ledger.
- **break_richness** — unmapped count. This does not gate. Higher is more useful: more slots where the source states something the target leaves silent.

Unmapped slots are aggregated across extracted papers, not listed per paper, and printed before the ledger. Ranked by how universally the source literature specifies a slot the target does not. On the fixture that top row is `isolation_unit`.

The previous cut of mapped ≥ 3 was chosen by inspection on a single fixture and is retired. On that fixture, mapped counts were only 0 or 3: the target instantiates exactly three slots, so any prediction paper filling system + state_variable + readout scores 3 and an extraction failure scores 0. Values of 1 and 2 would require a paper instantiating a proper subset of those three. The threshold was not undertested by sample size — it is structurally untestable against this fixture. The gate that remains is extraction_quality ≥ 1.

On the fixture, with the denylist empty, the normative-modelling guide (`arx_2509.07237`) extracted nothing and was held out. That is one run, one fixture.

The round-trip fidelity check (take `target_restatement` alone, recover the source condition, mark `fidelity: high | degraded`) is **not built**.

## Ledger

`build_ledger(ctx, doc_ids, search_ids) -> list[LedgerEntry]`

One `paperclip map` per search id, schema passed as file contents inline, never as a path, never with `--json`. Each entry is validated against `LedgerEntry`; invalid rows are dropped and counted. No retry loop.

`source_doc_id` is overwritten with the id known from retrieve. The map worker fills it with the paper title.

Status is about the target. On the two-sentence fixture the ledger is 9/9 UNKNOWN, which is the correct answer given that input. Resolving those entries to SATISFIED or VIOLATED needs a target document the claim does not contain. That path is not built ([06-roadmap.md](06-roadmap.md)).

## Not built

- HTML report (T5). Do not design from scratch. The live canvas — slot-object comparison (oscillator / patch / subject), break-point tables with n in the figure, extraction rates — is the layout to port.
- CLI (`run`, `score`, `--replay`)
- `eval/score.py` — recall against `data/ground_truth.csv` has never been computed
- Target-document ingest (protocol / preregistration / README)
- Round-trip fidelity field
- Answer loop that lets a scientist edit a restatement and persist the correction
