# Findings

Things learned on the fixture that anyone building this kind of audit would hit. Each claim below is from one fixture (fMRI-connectivity → ICU sepsis) unless stated otherwise. The thesis these findings serve is in [01-thesis.md](01-thesis.md). CLI-level probes are in [07-implementation-notes.md](07-implementation-notes.md).

## Axis order decides the ledger's monoculture

The map prompt lists the five axes and says "pick the one that fits." With the list in order A, B, C, D, E, the same ten papers produced **10 entries, all `C_domain_of_validity`**. Four of them said only that brain images are not vital signs — true, and not an audit finding. C is the attractor because "would this hold in a different setting" is definitionally a domain question.

Reordering the menu to A, B, D, E, C, and marking C last resort, produced A_isolation 7 / C 2 / B 1 on those same papers. The entries became specific (quantile normalisation fitted before the split; ADNI's "first w/train" protocol; exclusion of windows at or after first vasopressor).

The attractor then moved. Seven of nine later entries asked the same question: are the splits made by patient admission? Every retrieved paper reports its split, so A is always the first axis with concrete evidence, and "stop at the first axis" locks it in.

Axis diversity is an observation, not a target. Forcing the model to cover D and E to look balanced would be the same mistake in the other direction. D and E have still never fired; that is a diagnosis, not a prompt-tuning task ([02-assumption-ledger.md](02-assumption-ledger.md)).

## Status describes the target, and most answers are UNKNOWN

The same ten papers, two prompts:

| Frame | Result |
|---|---|
| Does this paper's condition hold in the target? | 9 VIOLATED / 1 SATISFIED |
| Does this paper's own result rest on a well-conducted condition? | 10 SATISFIED |

Both are internally consistent. Neither is the product question. Status describes whether the **target** can satisfy the analogous condition, judged only against what the target description says. Domain distance is not evidence of violation. Inventing failure from "the fields differ" is the 10/10 C ledger again.

On the two-sentence fixture the result is **9/9 UNKNOWN**. That is the correct answer: the claim states no method. A ledger of all SATISFIED or all VIOLATED is a failed audit. The contract is in [02-assumption-ledger.md](02-assumption-ledger.md).

Resolving UNKNOWN to SATISFIED or VIOLATED needs a target artefact (protocol, preregistration, methods draft). That path is not built.

## Convergence is not repetition

Seven independently retrieved papers, across arXiv, PMC, and bioRxiv, and across neuroimaging and ICU, pointed at the same validity condition: split by the unit of the individual (subject, patient, admission), not by window or slice.

Scattered across nine rows that looks thin. It is the same finding with a support count of seven. Merging those rows is not lossy compression; it is the evidence. Do not split them apart to manufacture axis diversity.

The two entries that were *not* about splits were the strongest individual findings: sepsis onset defined as antibiotic-administration time (B, `PMC6925691`), and a transductive method that requires auxiliary factors to be known for test subjects in advance (C, `arx_2410.00946`). Those should stay separate.

## What we pruned, and what replaced the prune

Two papers (`arx_2204.07005`, interpretability of ML in neuroimaging; `arx_2509.07237`, a normative-modelling guide) produced only metaphors: "brain images are spatially registered, so ICU streams need some analogous alignment." They were first removed by a hand denylist.

The alignment gate now holds them out with mapped=0, denylist empty, on one live run. That is the mechanism the denylist was faking. The denylist remains as an escape hatch, not as the design.

## Role-split retrieval assumes a shared methodological vocabulary. It does not have one

The source-leg query was written as if every discipline discusses validity the way ML and clinical prediction do: external cohorts, inclusion criteria, train-test split. Prefix the field name, keep that vocabulary, and you have queried the source half of the transfer.

That assumption is false outside ML-adjacent fields. The same template, classified by whether the paper's subject matter is the pinned discipline or a generic methods paper:

| Run | Pin | In-discipline | Generic |
|---|---|---|---|
| Fixture | `neuroimaging` | 5/5 | 0/5 |
| Run A | `statistical physics` | 0/5 | 5/5 |

Run A asked for Kuramoto, oscillators, synchronisation. It returned none of those. It returned clinical-prediction methodology papers. The same paper, `arx_2604.16537` (robustifying prognostic models), appeared in three unrelated runs — A (physics → phenology), B (foraging → ribosome), and C (lensing → cryo-EM). That repetition is the fingerprint: the query language *is* the clinical-prediction cluster on arXiv, and the discipline prefix does not move you out of it.

Statistical physics has validity conditions. They live in the physics — regimes, limits, assumptions on the coupling — not in a separate methods genre about generalisation. A query that can only hear "train-test split" cannot retrieve them. The role-split design then silently audits the wrong literature, and the break-point table reports a property of clinical prediction, not of the field the result was borrowed from.

This was caught by hand. An automatic in-discipline check on the source leg is the cheap guard; rewriting the query so the field's objects lead and validity conditions follow, in that field's terms, is the fix. The finding is the broken assumption, not the missing guard.

The same assumption was baked into extraction. After the source-leg rewrite, run A went from 0/5 to 5/5 in-discipline Kuramoto papers — and **3/5 of those papers extracted nothing**, as did 3/5 of the foraging papers on run B. A 60% failure rate on papers that state their assumptions. The seven-slot schema is ML ontology: `isolation_unit` is defined as the thing that must not cross a train/test split. A Kuramoto paper has coupling strength, a noise term, and a critical point. It has no training set, so the extractor returns nulls, `extraction_quality` is 0, and the paper is held out. Fixing retrieval exposed the bias; it did not remove it.

`isolation_unit`'s absence from those break-point tables is therefore not evidence about physics or foraging. It is extraction failure. Do not report it as a field property. The slot's role — the unit across which independence is assumed — exists in those fields (the oscillator, the ensemble member, the realisation of the noise; the forager, the patch). The prompt could not hear it.

## Constraints that are not findings about the domain

These shaped the code and will shape anyone else's:

- Paperclip `map` reads papers, not arbitrary text. Ingest therefore uses Anthropic. Clipboard uploads are searchable and `cat`-able, and `map` still refuses them (`no loadable full text`).
- `--output-schema` takes inline JSON, not a path. `--json` on `map` is swallowed into the query string.
- Displayed doc ids are truncated. Full ids come from `results <id> --save`.
- `filter` rewrites a search result in place and must not be used if replay matters.
- `claude-sonnet-5` rejects `temperature`. Slot stability cannot be obtained by turning a sampling knob.

Detail and transcripts: [07-implementation-notes.md](07-implementation-notes.md).
