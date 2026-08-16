# Roadmap

What is built and what is not is also summarised in the [README](../README.md). The findings that constrain the next work are in [05-findings.md](05-findings.md). This page is the plan, not a claim that the plan has been executed.

## Current state

| Component | State |
|---|---|
| Models, ingest, retrieve, align, ledger | Built |
| Report HTML + Markdown | Built. Fixture examples in `docs/example-report.html` |
| CLI (`run`, `--replay`) | Built. `score` and `answer` are not |
| Round-trip fidelity check on `target_restatement` | Not built |
| Target-document input | Not built |
| `eval/score.py` | Not built. Scored ad hoc: **5 of 8** (L2 0 of 2; TB11 handed over). The number lives in `runs/conformance/results.json`. Report "N of 8", never a rate. |
| Ground truth | 20/20 rows, 8 types, 2 rows adjudicated |
| Conformance suite | 8 converted claims in `data/transfer_bench.jsonl`. L3.1 uncovered |
| Negative controls | 4 found, 1 fetchable; FPR dropped |

The current artefact is a question list that ends when it is generated. The product loop is four steps, of which only the first exists:

1. Generate the questions
2. The scientist answers (or a target document does)
3. Status settles to SATISFIED / VIOLATED / remains UNKNOWN
4. Export something a reviewer or a PI can use

Step 2 is the split. Without it the tool stays at 9/9 UNKNOWN on a short claim, which is correct and not useful. With it, UNKNOWN converges, and the convergence is the audit record.

## Next, in order

**Target document (G1).** `transfer-audit run --claim-file claim.txt --target-doc protocol.pdf`. Upload to a run-scoped clipboard folder; do not `map` the clipboard document (`map` refuses it). Grep / `cat` the line-numbered text, pass those passages into the source-paper map query, and write `target_evidence_lines` as real line numbers in the user's file. Clean up the folder after the run. Accept: on a real protocol, at least two entries leave UNKNOWN, and the citations resolve in the user's document.

**Round-trip fidelity (M1).** After `target_restatement` is generated, take it alone — without the source paper — and ask what source condition it corresponds to. If the original `source_assumption` cannot be recovered, mark `fidelity: degraded`. Machine-checkable; does not depend on a human judge.

**Diagnose D and E (G2).** Those two axes have produced zero entries on every iteration. Decide whether the question cannot reach them, or whether they should be cut. An axis that never fires is worse than no axis.

**Close the evaluation loop (G3).** Write and run the scorer against `data/transfer_bench.jsonl`. Report conformance as "N of 8", never a rate, precision with n, and the status distribution. L3.1 is uncovered (Tu, Lyu). If entries cannot be matched to expected types, that mismatch is the finding.

**Generalise (G4).** Run the full pipeline on two claims outside neuroimaging and ICU. Expect degradation; the deliverable is where it breaks.

**Answer loop.** `transfer-audit answer --ledger …`. The scientist edits a restatement or answers a `what_would_resolve_it`. Answers go in `answers.json` with timestamp and author. They do not overwrite the machine ledger. Unanswered UNKNOWN is a legal end state.

**Export.** Pick one primary user. The stronger fit is a reviewer: a ranked list of unresolved questions is their job, not an accusation. A PI-facing preregistration appendix is the other format; do not build both halfway.

## Deliberately not built

No accounts, no server, no database, no frontend framework, no retry loop around the model, no claim that the system detects leakage. Those remain out of scope until the loop above exists.

## Three rules that stay

1. It generates questions, not verdicts.
2. Nothing is written that cannot point at evidence. A missing label costs one row; a wrong label costs every number.
3. Do not force axis diversity, status diversity, or a conformance rate. Those are observations. If an axis never fires, diagnose or delete it.

## Risks already visible

| Risk | Why it matters |
|---|---|
| B_legitimacy is the interesting axis and L2 has two labelled rows | The benchmark cannot carry that part of the argument |
| Target-document path depends on clipboard `grep`/`cat` | `map` on clipboard is a hard refusal; grep works on one probe |
| Paperclip corpus misses most IEEE/ACM conference papers | Three of four negative controls are unreachable |
| Prompt order changes the ledger | Results are not reproducible across prompt versions until prompts are versioned |
| Single fixture | The next domain may not retrieve, align, or restate the same way |
