# TransferBench — a conformance environment

Documentation of an agent environment. **Not a port to the BenchFlow runtime.** The runnable claims are `data/transfer_bench.jsonl`. The scored result is `runs/conformance/results.json` (summary in `runs/conformance/summary.txt`). Ground-truth provenance is in [04-benchmark.md](04-benchmark.md).

## Environment

| | |
|---|---|
| **Task** | Given a claim borrowed from another discipline, plus literature-tool access, produce an assumption ledger that surfaces the source result's validity conditions. |
| **Verifier** | Does the ledger contain a question that, honestly answered, would surface the leakage type the review identified? Subtype tags are evidence, not the score. |
| **Guard** | UNKNOWN-spam. An agent maximising coverage marks every axis UNKNOWN. Structural guard: mandatory specific `what_would_resolve_it`. Reported guard: status distribution alongside any coverage number. Never a rate. Never coverage alone. |
| **Baseline** | This pipeline, scored 16 Aug 2026, nothing tuned after the run. **5 of 8**, with one of those five handed over by the claim text. L2 is 0 of 2. |

It is a **conformance suite**, not recall. Seven of eight leakage types are covered by exactly one paper each, so two adjacent scores differ by a single case. Report "N of 8", never a rate.

## Result: 5 of 8

All 8 claims ran end to end. Criterion: a case hits if the ledger contains a question that, honestly answered, would surface the labelled type.

| id | type | pin | hit | note |
|---|---|---|---|---|
| TB03 | L3.3 | autism diagnostics | yes | C3: outside-clinic vs clinical ADOS cohorts |
| TB04 | L1.2 | obstetrics | no | no preprocessing-before-split question |
| TB07 | L1.4 | toxicology | yes | A4 on the RASAR primary: chemicals already in the similarity matrix |
| TB11 | L1.1 | SSVEP | yes | A1, handed over — see below |
| TB12 | L3.2 | histopathology | yes | patient-level slide/tile split (tagged A4, not C2; the question is the score) |
| TB17 | L2 | EHR | no | nobody asked if features encode the outcome |
| TB18 | L1.3 | psychiatric EEG | yes | A3 on the Zhdanov primary: feature ranking nested in folds |
| TB20 | L2 | software security | no | nobody asked if gadget tokens are a signal |

**5 of 8.** One of the five (TB11) the claim text helped produce. Do not bank all five quietly.

Status distribution across all runs: 62 entries, 1 drop. UNKNOWN 62, SATISFIED 0, VIOLATED 0, NA 0. Short claims silent on method make UNKNOWN the expected majority. A tool that marked everything VIOLATED would show up here.

Axis counts, 62 entries: A_isolation 42, C_domain_of_validity 16, E_evidence_quality 2, D_metric_alignment 1, B_legitimacy 1.

`eval/score.py` is not in the repository. This number was judged against the verifier above, from ledgers the pipeline wrote. It is a result, not a script.

## L2 is 0 of 2

This is the finding that matters more than the score.

B_legitimacy fired once across 62 entries, on TB03 (ADOS items outside clinic), and on **neither labelled L2 case**. TB17 (Ye / Maine HIE) did not ask whether predictors include treatments recorded because of the outcome. TB20 (VulDeePecker) did not ask whether code-gadget tokens are a vulnerability signal.

L2 is the axis this project claims is most valuable. Kapoor & Narayanan give it no subtypes because judging feature legitimacy needs domain knowledge and is highly problem-specific ([02-assumption-ledger.md](02-assumption-ledger.md)). Cross-domain literature access is supposed to close that gap: a reader in the target field cannot see that an EHR feature is a treatment, or that a token is not a vulnerability, without being shown the source condition in their own language ([01-thesis.md](01-thesis.md)).

Our own benchmark says we do not close it.

A project that builds an instrument to test its central claim and then publishes the negative result is worth more than one that reports a good number. L2 remains 2 papers, not a sampling distribution — "0 of 2", never a rate. The number is still the test we set.

## TB11 — the hit the claim helped produce

TB11 is the suite member closest to telegraphing its own label. The claim says a spatial filter is "fit to a subject's SSVEP templates" and then used to detect which of 40 targets that subject is attending to. Fitting and detection already share a subject. The ledger asked whether calibration templates were built from held-out spelling blocks — the question that phrasing invites.

Retrieved SSVEP papers do discuss leave-one-block-out CV, so the axis was not invented. The mapping onto the target was handed over by the claim text.

The honest reading is **5 of 8 with one hit the claim text helped produce**.

The contamination protocol below is the rule that was supposed to prevent this. TB11 shows the rule is necessary and that one draft still leaked.

## Limits of the suite

8 of 20 review rows were convertible. Ceiling if Vandewiele and Roberts survived a PDF read: 10, not 20. Those two were not chased. L3.1 (temporal leakage) is uncovered: it lives only on Tu 2018 and Lyu 2021, both unread IEEE. Recorded as `UNCOVERED_L3.1` in the suite file. A documented gap in an environment is an invitation, not a weakness. Do not score a rate that pretends the type was tested.

Arp (TB20) is a single-type conversion standing for L2. The Kapoor row carries six types; scoring a hit on any of six would not test the question this case poses.

Convertibility, adjudication, and the type census are in [04-benchmark.md](04-benchmark.md).

## Contamination protocol

If claim texts are written while knowing the leakage label, the phrasing can telegraph the answer. That is leakage in our own benchmark construction — the failure this project exists to catch.

Whenever a row is converted:

1. Identify the primary study the review names.
2. Write the claim **only** from how that study describes itself: what is predicted, in what system, from what data, and the use it claims.
3. Do not reference the review's criticism, the leakage type, or any methodological concern.
4. Do not include details that exist in the record only because a reviewer flagged them.
5. Re-read and ask: could a reader infer the labelled type from the claim text alone? If yes, rewrite.

TB11 is the case that failed step 5 and still entered the suite. The self-disclosure above is the correction; rewriting the claim after seeing the score would be tuning.

## This environment measures something real

Three skill failures from the fixture and out-of-domain runs, recorded in [05-findings.md](05-findings.md). They are why a conformance suite is not a trivia quiz: the same pipeline can retrieve the wrong literature, lock onto one axis, or extract nothing from papers that state their assumptions.

**Cross-domain vocabulary assumption.** Role-split retrieval was written as if every discipline discusses validity the way ML and clinical prediction do (external cohorts, inclusion criteria, train-test split). Prefix a field name, keep that vocabulary, and the query stays in the clinical-prediction cluster on arXiv. Statistical physics → phenology returned 0/5 in-discipline papers until the field's objects led the query.

**Axis-ordering monoculture.** The map prompt says pick the first axis with evidence. Menu order A, B, C, D, E produced 10/10 `C_domain_of_validity`. Reordering C to last resort moved the attractor to A_isolation. Axis diversity is an observation, not a target.

**Extractor ontology bias.** After the source-leg rewrite, Kuramoto papers were in-discipline — and 3/5 extracted nothing. The seven-slot schema is ML ontology: `isolation_unit` as the thing that must not cross a train/test split. A paper with coupling strength and a noise term has no training set, so `extraction_quality` is 0 and it is held out. Absence of that slot from a physics break-point table is extraction failure, not a field property.

The scored 5 of 8 sits on top of those failure modes. Isolation questions dominate because isolation is what the prompt and the schema can hear. L2 is 0 of 2 for the same reason B barely fires: legitimacy is the question that needs the source field's objects, and that is the question the instrument is worst at asking.
