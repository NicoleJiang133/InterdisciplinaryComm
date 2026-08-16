# Thesis: the failure is fidelity, not comprehension

This is the product argument. The pipeline that follows from it is in [03-architecture.md](03-architecture.md). The axes that structure the output are in [02-assumption-ledger.md](02-assumption-ledger.md).

## The 70% version

A scientist borrowing a result from another field usually understands it. The problem is not that they cannot read the paper. The problem is that they understand it to about 70%, the missing 30% is invisible to them, and they then act on the approximation.

Worked example. The source condition is:

> The test set must be drawn from the distribution of scientific interest.

The version a reader stores is:

> Use a held-out test set.

Those two sentences are not the same. A split that reuses the same patients, the same hospital, or a test set with the borderline cases removed is fully compliant with the second and in violation of the first. Kapoor & Narayanan ([arXiv:2207.07048](https://arxiv.org/abs/2207.07048), Patterns 2023) surveyed the applied-ML literature and found 329 papers affected by leakage of this family. Every one of those papers can claim a held-out test set. The gap between the two sentences is where they failed.

## What follows

If you can state the source's condition precisely in the target's own language, you can check it. If you can only state it approximately, you cannot.

Translation fidelity is therefore not an aid to the audit. It is the mechanism of the audit.

`target_restatement` is the load-bearing field: the source condition, written so that someone working in the target system can act on it. `status` is a consequence of that restatement, judged only against what the target description actually says. A restatement that has lost information cannot support SATISFIED or VIOLATED; the honest status is UNKNOWN, and the useful output is the question that would recover the lost 30%.

Unmapped structural slots — places where the source instantiates a condition and the target has no counterpart — are not a tool failure. They are where the transfer is most likely to break, and they must be shown to the scientist. See [03-architecture.md](03-architecture.md) for the alignment gate that reports them.

## What this is not

The tool generates questions, not verdicts. The source paper of the benchmark already showed that these errors cannot be caught by reading papers. Any claim that the system *detects* leakage from text is wrong. UNKNOWN with a specific, answerable `what_would_resolve_it` is a success state.

This argument was developed against one fixture (an fMRI-connectivity classifier transferred onto ICU sepsis prediction) and one survey paper. It has not been tested on claims outside that pair. That test is on the [roadmap](06-roadmap.md).
