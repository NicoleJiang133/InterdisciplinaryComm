# Benchmark

The labelled set is `data/ground_truth.csv`. It is human-curated and is not generated or edited by the pipeline. The scorer that would read it has not been run, so there is no recall number yet. The axes these labels map onto are in [02-assumption-ledger.md](02-assumption-ledger.md).

## Provenance

All 20 rows are leakage-type annotations read off Table 1 (`\label{table:survey}`) in the LaTeX source of [arXiv:2207.07048](https://arxiv.org/abs/2207.07048), fetched from `https://arxiv.org/src/2207.07048`. The table is real `tabular` markup, not an image. No value was inferred from a rendered PDF or from surrounding prose.

Each row's `evidence` column holds the exact LaTeX table row it came from. Column order is fixed by the header at `main.tex` line 129: cells 5–12 are L1.1, L1.2, L1.3, L1.4, L2, L3.1, L3.2, L3.3. A `$\circ$` marks the type.

## Type census

20 rows, 32 type annotations, all eight types present.

| Type | Count | Notes |
|---|---|---|
| L1.1 | 8 | no independent test set |
| L1.3 | 6 | feature selection / model selection on the test side |
| L3.2 | 4 | dependence structure |
| L3.3 | 4 | representativeness |
| L1.2 | 3 | preprocessing before the split |
| L1.4 | 3 | duplicates across groups |
| L2 | 2 | illegitimate features |
| L3.1 | 2 | temporal leakage |

Per-type recall on L2 and L3.1 will be noise. Quote whole-benchmark recall with its denominator; do not quote per-type recall for those two.

## Two adjudicated rows

Six rows were originally filled by a human reading section 2.4 of the paper, then checked against the table. Four agreed (rows 4, 12, 17, 18) and keep `annotation_source=section2.4` with the table evidence backfilled. Two did not:

| row | paper | prose label | table label | outcome |
|---|---|---|---|---|
| 3 | Bone et al. 2015 | `L3.3` | `L1.4;L3.3` | prose reading was incomplete; table taken |
| 14 | Vandewiele et al. 2021 | `L1.2` | `L1.3;L3.2;L3.3` | direct contradiction; table taken, L1.2 dropped |

Both now carry `annotation_source=table1`, `confidence=high`. Row 20 previously held the placeholder `MULTIPLE`, which is not a legal value, and was filled from the table.

## Why FPR was dropped

Four negative-control papers were identified (`data/negative_controls.csv`). Three (NC01–NC03) are IEEE papers named by Vandewiele et al. as having a sound evaluation; they are not in the Paperclip corpus. One (NC04, `arx_1807.01068`, Reisert et al. HAMLET) is fetchable.

n=1 is not a number. False-positive rate was removed from the planned score line. What replaces it is `status_distribution`: counts of SATISFIED / VIOLATED / UNKNOWN / NA on a generated ledger. A healthy ledger on a short claim is mostly UNKNOWN. A tool that marks everything VIOLATED shows up immediately, without needing a clean-control set it does not have.

The CSV is kept. It documents an honest attempt, and NC04 remains one real scored control if a later corpus change makes the other three fetchable.

## L2 thinness

B_legitimacy is the axis where cross-domain reading is supposed to matter most, and L2 is the corresponding label. It appears in two rows, one of which (row 20) is a six-type mixture. The benchmark cannot support a claim that the tool finds legitimacy failures. Say so if a number is shown.

## What has not been measured

`eval/score.py` is not in the repository. Recall, precision, and the status distribution have not been computed against this file. Until they are, the benchmark is a labelled set, not a result.
