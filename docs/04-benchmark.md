# Benchmark

The labelled set of reviews is `data/ground_truth.csv`. It is human-curated and is not generated or edited by the pipeline. The runnable score line is the conformance suite `data/transfer_bench.jsonl`: 8 known cases converted from those reviews. Scored 16 Aug 2026: **5 of 8**, L2 0 of 2, one of the five hits handed over by the claim text. Environment framing, the L2 miss, and TB11 self-disclosure are in [08-transferbench.md](08-transferbench.md). The axes these labels map onto are in [02-assumption-ledger.md](02-assumption-ledger.md).

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

Seven of the eight Kapoor types appear in the suite. L3.1 does not. Do not quote a per-type rate: most types are carried by one case, so 5 of 8 and 6 of 8 differ by a single paper. Report "N of 8", never a rate.

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

B_legitimacy is the axis where cross-domain reading is supposed to matter most, and L2 is the corresponding label. The suite has two L2 cases (Filho/Ye and Arp/VulDeePecker). That is still two papers, not a sampling distribution.

The scored result is **0 of 2**. B_legitimacy fired once in 62 entries, on TB03, and on neither L2 case. Report "0 of 2", never a rate, and do not claim the tool finds legitimacy failures in general. The argument is in [08-transferbench.md](08-transferbench.md).

## Why the score line stays on this benchmark

The break-point summary is now the stronger output. A metric designed around break points was considered.

We are not switching, for one reason: scoring against a benchmark someone else built, backed by 329 surveyed papers, is defensible in a way that a metric we design to measure our own headline is not. Setting our own exam and passing it gets discounted. The ledger still exists; it just is not the only output.

What we are switching is the *name of the score*. "Recall" implies a sampling distribution we do not have. Seven of eight types in the suite are covered by one paper each, so 5 of 8 and 6 of 8 differ by a single case. The score line is a **conformance suite**: 8 known cases, does the tool surface the right question on each. The observed number is **5 of 8**, never a rate.

## H4 — claim conversion

The 20 CSV rows are review papers, not the studies they screened. Scoring needs a claim describing the named study, then a check for a matching ledger axis. That transformation is human. Vandewiele and Roberts were not chased: two PDF reads would not add L3.1, which lives only on Tu and Lyu.

8 of 20 rows were convertible. They are now `data/transfer_bench.jsonl`. `data/ground_truth.csv` is unchanged.

### Contamination procedure

If the claim texts are written while knowing the leakage label, the phrasing can telegraph the answer. An Oner claim that says "using slides from the same patients" has already given away L3.2. That is leakage in our own benchmark construction — the failure this project exists to catch.

Procedure, followed for every converted row:

1. Identify the primary study the review names (or that Kapoor §2.4 names for that row).
2. Write the claim **only** from how that study describes itself: what is predicted, in what system, from what data, and the use it claims.
3. Do not reference the review's criticism, the leakage type, or any methodological concern.
4. Do not include details that exist in the record only because a reviewer flagged them.
5. After drafting all 8, re-read each and ask: could a reader infer the labelled leakage type from the claim text alone? If yes, rewrite.

This is a methodological contribution, not a caveat. The suite is only as good as this separation.

### Arp (row 20)

One claim cannot cover six labelled types. Scoring the row as a hit on any of six would not test whether the tool surfaces the question this case poses. The entry is a **single-type conversion standing for L2**. Arp §4.2's finding on VulDeePecker is classification on tokens that are not a vulnerability signal — illegitimate features, a different L2 instantiation from Filho/Ye (treatment-as-proxy). L1.2 is already carried by Taft.

### L3.1 — uncovered type

Temporal leakage is not in the suite. It appears only on Tu et al. 2018 and Lyu et al. 2021, both unread IEEE, neither convertible from a named case in hand. The gap is recorded as `UNCOVERED_L3.1` in `data/transfer_bench.jsonl`. Under an environment framing a documented gap is an invitation, not a weakness. Do not paper over it, and do not score a rate that pretends the type was tested.

### Convertibility assessment (why 8, not 20)

A row was convertible if Kapoor §2.4 or the review named (1) a specific primary study or dataset, not just an N, (2) with enough of what is predicted, in what system, from what signal, that a human could write a transfer-style claim. Aggregate counts, or a list parked in an uningested supplement, were not enough.

**8 convertible, 2 confirmed aggregate, 10 unread and not counted.** Ceiling if Vandewiele and Roberts survived a PDF read: 10, not 20. Those two were not converted.

| row | review | types | verdict | named case |
|---|---|---|---|---|
| 1 | Bouwmeester 2012 | L1.1 | aggregate | 71-paper methods census. Read (PMC3358324). Counts of reporting items; no worked prediction claim. |
| 2 | Whelan & Garavan 2014 | L1.1;L1.3 | unread | Biological Psychiatry commentary on 14 neuroimaging papers. Not in corpus. |
| 3 | Bone 2015 | L1.4;L3.3 | converted (TB03, L3.3) | Wall et al. 2012, ADOS Module 1. Primary fetchable (PMC3337074). |
| 4 | Blagus & Lusa 2015 | L1.2 | converted (TB04) | Taft et al. 2009, ADE in labor and delivery. Primary not in corpus. |
| 5 | Ivanescu 2016 | L1.1 | unread | Four obesity-prediction papers. Not in corpus. |
| 6 | Tu 2018 | L3.1 | unread | IEEE issue-tracking. One of two L3.1 rows. |
| 7 | Alves 2019 | L1.4 | converted (TB07) | Luechtefeld RASAR. Primary fetchable (PMC6135638). |
| 8 | Nalepa 2019 | L3.2 | unread | IEEE hyperspectral segmentation, 17/17. |
| 9 | Poulin 2019 | L1.1 | unread | Four tractography ML papers. Review not in corpus. |
| 10 | Christodoulou 2019 | L1.3 | unread, likely aggregate | 71-paper ML vs logistic regression census. |
| 11 | Nakanishi 2020 | L1.1 | converted (TB11) | Kiran Kumar & Reddy 2019, SSCOR SSVEP-BCI. Primary IEEE, not in corpus. |
| 12 | Oner 2020 | L3.2 | converted (TB12) | Coudray et al. 2018, NSCLC mutation from histopathology. Primary not in Paperclip. |
| 13 | Poldrack 2020 | L1.1;L1.2 | unread, likely aggregate | 100-paper best-practices review. JAMA Psychiatry. |
| 14 | Vandewiele 2021 | L1.3;L3.2;L3.3 | unread, not chased | Title promises a case study. Not converted. |
| 15 | Roberts 2021 | L1.1;L1.4;L3.3 | unread, not chased | 62 COVID CXR/CT. Not converted. |
| 16 | Lyu 2021 | L3.1 | unread | IEEE AIOps. Other L3.1 row. |
| 17 | Filho 2021 | L2 | converted (TB17) | Ye et al. 2018, incident hypertension, Maine HIE. Primary fetchable (PMC5811646). |
| 18 | Shim 2021 | L1.3 | converted (TB18) | Zhdanov et al. 2020, EEG → escitalopram response. Primary fetchable (PMC6991244). |
| 19 | Barnett 2022 | L1.3 | aggregate | 41 studies in uningested Table S1. Read (`med_8e2e53ce6c95`). |
| 20 | Arp 2022 | six types | converted (TB20, L2 only) | VulDeePecker. Primary fetchable (`arx_1801.01681`). |

Suite coverage: L1.1 Nakanishi, L1.2 Taft, L1.3 Zhdanov, L1.4 Luechtefeld, L2 Filho and VulDeePecker, L3.2 Coudray, L3.3 Wall. **L3.1 uncovered.**

## What has been measured

Scored 16 Aug 2026 against `data/transfer_bench.jsonl`. Nothing was tuned after the run. Recorded in `runs/conformance/results.json`.

**5 of 8.** Hits: TB03 (L3.3), TB07 (L1.4), TB11 (L1.1, handed over), TB12 (L3.2), TB18 (L1.3). Misses: TB04 (L1.2, no preprocessing-before-split question), TB17 and TB20 (both L2). Status distribution: 62 entries, 1 drop, UNKNOWN 62 / SATISFIED 0 / VIOLATED 0 / NA 0.

Scoring was run ad hoc; the harness is not yet in the repository. The 5 of 8 lives only in `runs/conformance/results.json`. TB11's hit is disclosed in [08-transferbench.md](08-transferbench.md); do not quote 5 of 8 without it. L3.1 remains uncovered.

