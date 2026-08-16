# Assumption Ledger v0.1

Domain rationale for the five axes. Derived from the 8-type data leakage
taxonomy in Kapoor & Narayanan, arXiv:2207.07048, Patterns 2023.

A_isolation          from L1. Information that should have been held out leaked in.
  A1 no test set / no independent check
  A2 preprocessing crossed the isolation boundary
  A3 feature selection crossed the isolation boundary
  A4 duplicate entities across supposedly independent groups
B_legitimacy         from L2. A variable encodes the answer, or is unavailable
                     at decision time. The source paper gives no subtypes here:
                     judging this needs domain knowledge and is highly problem
                     specific. This is the axis where cross-domain literature
                     access adds the most value.
C_domain_of_validity from L3. The distribution the result was validated on is
                     not the distribution the claim is about.
  C1 temporal direction confounded or reversed
  C2 dependence structure: same individual, batch, phylogeny, spatial autocorrelation
  C3 representativeness: geography, institution, excluded hard cases
D_metric_alignment   from section 2.5. The source discipline's definition of
                     success is not the target's.
E_evidence_quality   from section 2.5. Missingness, sample size vs predictors,
                     outcome variable as a poor proxy.

Status values: SATISFIED / VIOLATED / UNKNOWN / NA.
UNKNOWN is a success state when accompanied by a specific what_would_resolve_it.

REFERENCE ONLY. Do not implement this prose.
