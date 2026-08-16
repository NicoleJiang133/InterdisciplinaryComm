# Thesis: review capacity is the bottleneck

This is the product argument. The pipeline that follows from it is in [03-architecture.md](03-architecture.md). The axes that structure the output are in [02-assumption-ledger.md](02-assumption-ledger.md).

## Review capacity

[Sundial](https://www.sundial.md/blog/announcing-sundial) states the problem as: the length of task an agent can finish on its own roughly doubles every few months, while a human's capacity to review stays constant. Closing the gap means making the work legible: what was done, by whom, and why.

That is this project's thesis, arrived at independently.

A scientist borrowing a method from another discipline cannot review every assumption it carries. Review capacity is the bottleneck — not comprehension, not access to the literature. This tool amplifies review capacity by making a borrowed result's validity conditions legible:

1. what the source result depends on
2. what that becomes in the target system
3. therefore, what to ask

The 70% reading is how that bottleneck shows up in a transferred scientific result. Fidelity is the mechanism that makes the three steps checkable.

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

## Same slot, different ontology

`isolation_unit` is the unit across which independence is assumed. Filled from papers, it is:

| Neuroimaging | Statistical physics | Optimal foraging |
|---|---|---|
| subject | oscillator, or a realisation of the noise | patch, or forager |

Same slot. Different object. Structure preserved. That is the fidelity argument as a live row, not a slogan.

If the scientist stores "split by subject", they have the 70% version of a condition that, in Kuramoto, was "do not mix realisations of the noise." A restatement that cannot carry the object's name cannot be checked. `target_restatement` exists to carry it.

n=4 extracted source-leg papers per out-of-domain run, plus the fixture. Small enough to say, specific enough to demonstrate.

## Provenance

A record of what was done, by whom, and why is what makes agent work reviewable at all. That is a design principle, not a feature list.

Every ledger claim carries `source_doc_id` and `evidence_lines`. Those two fields are the minimum a reviewer needs to check the translation against the paper rather than against the model's summary of it. Literature claims are verified against source full text via `paperclip repo commit`, with an audit trail in `repo log`. Nothing in the ledger is allowed to float free of that trail: if it cannot point at evidence, it is not written.

## What this is not

The tool generates questions, not verdicts. The source paper of the benchmark already showed that these errors cannot be caught by reading papers. Any claim that the system *detects* leakage from text is wrong. UNKNOWN with a specific, answerable `what_would_resolve_it` is a success state.

This argument was developed against one fixture (an fMRI-connectivity classifier transferred onto ICU sepsis prediction) and one survey paper. The slot-object row above is the first out-of-domain check: Kuramoto coupling → meadow flowering, and the marginal value theorem → ribosome unbinding, n=4 extracted source-leg papers each. The ontology changed; the slot did not.
