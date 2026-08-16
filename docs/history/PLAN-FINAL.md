# PLAN-FINAL.md — submission plan

Two hours. Read this fully before writing any code. Also read BUILD.md.

Five tasks, A through E, in order. Stop after each and report. Do not start the
next until told.

---

## 0. The repositioning — read this first, it changes the framing of everything

Sundial (sundial.md), a research lab studying human-agent collaboration, states
the problem as:

> Model autonomy doubles every few months. Our capacity to review stays fixed.
> Closing the gap means making the work legible: what was done, by whom, and why.

That is this project's thesis, arrived at independently.

A scientist borrowing a method from another discipline cannot review every
assumption it carries. Review capacity is the bottleneck — not comprehension,
not access to the literature. This tool amplifies review capacity by making a
borrowed result's validity conditions legible: what the source result depends
on, what that becomes in the target system, and therefore what to ask.

Everything below serves that sentence.

---

## 1. Hard scope for these two hours

**In scope:** tasks A–E below.

**Out of scope, do not touch:**
- Converting the 8 convertible benchmark rows (T7 stays unrun)
- G1 target-document input
- M1 round-trip fidelity check
- Ledger deduplication
- D/E axis diagnosis, perturbation over-extraction, C-axis monoculture
- Any port to the BenchFlow runtime
- Anything touching Sundial's "Sun" — it is unreleased. Do not build against it.

If a task seems to need something on that list, stop and flag it.

---

## Task A — T5 report, HTML and Markdown (~50 min)

Build `src/transfer_audit/report.py`. Jinja2. No CDN, no JS build.

**HTML output** — one self-contained file, inline CSS. Port the layout from the
`source-leg-rerun` canvas. Do not redesign:

- metric row at top (large numbers, labels underneath)
- break-point summary table, **n visible in every cell**
- the slot-object comparison panel (oscillator / patch / subject)
- ledger entries grouped by axis: status, the question, `source_doc_id`,
  `evidence_lines`
- status distribution summary

Large question text, minimal chrome. This gets projected.

**Markdown output** — `runs/<ts>/report.md`, same content, clean Markdown.

This is the handoff format for a human-agent editor. Structure each ledger entry
so `source_assumption` and `target_restatement` sit adjacent and read as
editable prose. A scientist correcting a translation is the highest-value human
input this system can capture, and Markdown is where that correction happens.

**Worked-example panel**, at the top of both formats. Take the strongest entry
and show the full chain in three steps:

1. what the source result depends on
2. what that becomes in the target system
3. therefore, what to ask

This panel is the answer to "why is this the recommendation". It is the single
most important thing on the page.

**Commit rendered examples** at `docs/example-report.html` and
`docs/example-report.md` so anyone opening the repo sees output immediately.

**Accept:** both open offline and render the current fixture ledger.

---

## Task B — Minimal CLI (~20 min)

Two commands only:

```
transfer-audit run --claim-file path.txt [--source-discipline X]
transfer-audit run --replay runs/<ts>
```

`--replay` reads a saved run and re-renders both reports with **no network
call**. Build `--replay` first; it is the demo safety net.

Wire the console script in `pyproject.toml`. Verify `transfer-audit --help`
works after `pip install -e .`.

Do not build `score` or `answer`.

**Accept:** `--replay` renders a saved run offline.

---

## Task C — Repositioning (~15 min)

Rewrite the opening of `README.md` and `docs/01-thesis.md` around the review-
capacity framing in section 0.

Order in the README:
1. One sentence: what it does
2. Prototype disclosure — built in roughly 24 hours, exercised on a single
   fixture claim
3. **Review capacity.** Autonomy scales, review does not. Cite Sundial's
   framing and note we reached it independently. Then the 70% example: the
   source condition "the test set must be drawn from the distribution of
   scientific interest" is stored as "use a held-out test set", and every one
   of the 329 papers in Kapoor & Narayanan is compliant with the second and in
   violation of the first.
4. What it does not do: generates questions, not verdicts
5. Status table
6. Links into docs/
7. Quickstart

Add a short **Provenance** section to `docs/01-thesis.md`. State it as a design
principle, not a feature list: every ledger claim carries `source_doc_id` and
`evidence_lines`; literature claims are verified against source full text via
`paperclip repo commit` with an audit trail in `repo log`. The reason is that a
record of what was done, by whom, and why is what makes agent work reviewable
at all.

**Accept:** a reader reaches the argument in the first screen.

---

## Task D — BenchFlow environment spec (~15 min)

Write `docs/08-transferbench.md`. **Documentation only. Do not port to the
BenchFlow runtime.**

Frame the conformance suite as an agent environment:

```
Task      given a claim borrowed from another discipline plus literature tool
          access, produce an assumption ledger surfacing the source result's
          validity conditions

Verifier  does the ledger contain a question that, honestly answered, would
          surface the leakage type the review identified

Guard     UNKNOWN-spam. An agent maximising coverage marks every axis UNKNOWN.
          Structural guard: mandatory specific what_would_resolve_it.
          Reported guard: status distribution alongside any coverage number.

Baseline  our pipeline, not yet scored
```

**Rename the metric.** It is a conformance suite, not recall — seven of eight
leakage types are covered by exactly one paper each, so two adjacent scores
differ by a single case. Report "N of 8", never a rate. Update
`docs/04-benchmark.md`, `BUILD.md` T7, and the README accordingly.

**State honestly, in the document itself:** 8 of 20 rows convertible, ceiling
10, conversion not done, L3.1 (temporal leakage) uncovered because it lives only
on two unread IEEE papers. A documented gap in an environment is an invitation,
not a weakness.

**Also record the contamination protocol** for whenever the 8 do get converted:
claim texts must be written only from how the original study describes itself —
what is predicted, in what system, from what data — never referencing the
review's criticism or the leakage type, because phrasing that telegraphs the
answer would be leakage in our own benchmark construction.

**Add the three skill-failure findings** from `docs/05-findings.md` as evidence
that this environment measures something real: the cross-domain vocabulary
assumption, the axis-ordering monoculture, and the extractor ontology bias.

---

## Task E — Ship (~10 min)

- Update the README status table to reflect A–D
- `git status`, confirm no `.env`, `.venv/`, `runs/`
- Commit and push to origin main
- Report the final tree and the README verbatim

---

## Three rules that hold throughout

1. **It generates questions, not verdicts.** The source literature proved these
   errors cannot be caught by reading papers. UNKNOWN with a specific,
   answerable question is a success state.
2. **Nothing gets written that cannot point at evidence.** Ledger entries,
   benchmark labels, report claims — same standard.
3. **No tuning for appearance.** Axis distribution, status distribution, and
   coverage counts are observations, not targets.
