# The assumption ledger

Five axes for asking whether a source result's validity conditions still hold after the result is transferred. Derived from the 8-type data-leakage taxonomy in Kapoor & Narayanan, [arXiv:2207.07048](https://arxiv.org/abs/2207.07048), Patterns 2023. The product argument that makes `target_restatement` load-bearing is in [01-thesis.md](01-thesis.md). How the labels were read off Table 1 is in [04-benchmark.md](04-benchmark.md).

This page is the domain rationale. It is not a prompt and it is not an implementation spec.

## Why these axes

Kapoor & Narayanan group leakage into three families (L1 isolation, L2 legitimacy, L3 domain of validity) plus a methods discussion in their section 2.5 (metric choice and evidence quality). The ledger keeps that shape and names the families so a generated entry can be matched back to a labelled type.

| Axis | Source | What it asks |
|---|---|---|
| A_isolation | L1 | Did information that should have been held out leak in? |
| B_legitimacy | L2 | Does a variable encode the answer, or is it unavailable at decision time? |
| C_domain_of_validity | L3 | Is the distribution the result was validated on the distribution the claim is about? |
| D_metric_alignment | §2.5 | Is the source discipline's definition of success the target's? |
| E_evidence_quality | §2.5 | Missingness, sample size against predictors, outcome as a poor proxy. |

## Subtypes

A and C have subtypes because the source taxonomy does. B, D, and E do not.

**A_isolation**

- A1 — no test set / no independent check
- A2 — preprocessing crossed the isolation boundary
- A3 — feature selection crossed the isolation boundary
- A4 — duplicate entities across supposedly independent groups

**C_domain_of_validity**

- C1 — temporal direction confounded or reversed
- C2 — dependence structure (same individual, batch, phylogeny, spatial autocorrelation)
- C3 — representativeness (geography, institution, excluded hard cases)

**B_legitimacy** has no subtypes in the source paper. Judging it needs domain knowledge and is highly problem-specific. It is the axis where reading across disciplines is supposed to add the most value. It is also the thinnest part of the benchmark: L2 appears in only two of twenty rows. See [04-benchmark.md](04-benchmark.md).

## Status

`SATISFIED` / `VIOLATED` / `UNKNOWN` / `NA`.

Status describes the **target**, not the source paper. It is judged only against what the target description actually says.

- SATISFIED — the target description positively states the condition is met, and the rationale names the part of it that does.
- VIOLATED — the target description positively shows the condition fails. A difference in subject, population, or modality is not evidence of violation.
- UNKNOWN — the default. The target is usually a short claim and is silent on method. Requires a specific, answerable `what_would_resolve_it` (at least 20 characters). That constraint is the anti-gaming rule.
- NA — the axis cannot apply to this transfer.

A ledger that is entirely SATISFIED, or entirely VIOLATED, is a failed audit: status was set by framing rather than evidence. Both failure modes were observed on the same ten fixture papers. The decision and the two failed frames are in [05-findings.md](05-findings.md).

`source_assumption` describes the source paper. `target_restatement` and `status` describe the target. The restatement is the load-bearing field; status is a consequence of it ([01-thesis.md](01-thesis.md)).

## What has actually fired

On the ICU / neuroimaging fixture, after the axis menu was ordered A, B, D, E, C:

- A_isolation has been the majority
- B_legitimacy has produced one concrete entry (sepsis onset defined as the moment antibiotics were given)
- C_domain_of_validity appears when it is not suppressed
- D_metric_alignment and E_evidence_quality have produced **zero** entries across every iteration

An axis that never fires is worse than no axis. Whether D and E are unreachable from the current question, or wrongly specified, is an open diagnosis ([06-roadmap.md](06-roadmap.md)). Do not treat five axes as a demonstrated coverage of the taxonomy.
