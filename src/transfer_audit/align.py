"""M2 — structural alignment between a retrieved paper and the target.

T3 returns papers. T4 used to generate an entry for every one of them. The two
metaphor papers we later denylisted are the symptom of that missing gate: they
had no structural counterpart in the target, so the only restatement possible
was a metaphor, and a metaphor is an untrustworthy translation.

This step asks, for each of seven slots, whether the paper instantiates it and
whether the target has a counterpart. Comparison is deterministic once the
paper-side values are extracted. Unmapped slots are the finding — they are
where a precise restatement cannot be formed, which is where the 70% reading
silently drops the 30%.
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

from pydantic import BaseModel, ConfigDict, field_validator

from transfer_audit.ledger import (
    MAP_TIMEOUT,
    WORKER,
    parse_map_blocks,
    parse_map_id,
    payload_json,
)
from transfer_audit.models import (
    ALIGNMENT_SLOTS,
    AlignmentReport,
    PaperAlignment,
    SlotAlignment,
    TransferContext,
)
from transfer_audit.pc import pc
from transfer_audit.retrieve import Retrieval, SourceDoc

MIN_MAPPED = 3

_EXTRACT_QUERY = """\
Read this paper and fill the seven structural slots of ITS OWN study. \
Use the paper's wording. Use null for any slot the paper does not instantiate. \
Do not describe the target. Do not invent a counterpart.

  system: the population, cohort, organism or setting the result is about.
  state_variable: the variable whose state is predicted, classified or measured.
  perturbation: the intervention or manipulation, if any.
  readout: the signal, instrument or data source the result is read from.
  constraints: stated inclusion criteria, exclusions, eligibility, or stated \
limits, as one short string. Null if none are stated.
  failure_mode: what going wrong looks like in this paper (a missed converter, \
a false alarm, a wrong class). Null if the paper does not define one.
  isolation_unit: the unit that must not appear on both sides of a train/test \
or discovery/validation split (subject, patient, admission, site, scan, \
family, batch). Null if the paper does not say.
"""


class PaperSlots(BaseModel):
    """The seven structural slots extracted from one source paper."""

    model_config = ConfigDict(extra="forbid")

    system: str | None = None
    state_variable: str | None = None
    perturbation: str | None = None
    readout: str | None = None
    constraints: str | None = None
    failure_mode: str | None = None
    isolation_unit: str | None = None

    @field_validator("*", mode="before")
    @classmethod
    def _blank_null_strings(cls, value):
        if isinstance(value, str) and value.strip().lower() in {"", "null", "none", "n/a"}:
            return None
        return value


def target_slots(ctx: TransferContext) -> dict[str, str | None]:
    """The target's value for each alignment slot. Null means no counterpart."""
    constraints = "; ".join(ctx.constraints) if ctx.constraints else None
    return {
        "system": ctx.target_system or None,
        "state_variable": ctx.state_variable,
        "perturbation": ctx.perturbation,
        "readout": ctx.readout,
        "constraints": constraints,
        "failure_mode": ctx.failure_mode,
        "isolation_unit": ctx.isolation_unit,
    }


def _filled(value: str | None) -> bool:
    return bool(value and str(value).strip() and str(value).strip().lower() != "null")


def judge_slot(slot: str, paper_value: str | None, target_value: str | None) -> SlotAlignment:
    """Deterministic: counterpart exists or it does not. No similarity score."""
    paper = paper_value.strip() if _filled(paper_value) else None
    target = target_value.strip() if _filled(target_value) else None
    if paper is None:
        return SlotAlignment(slot=slot, judgement="absent", paper_value=None, target_value=target)
    if target is None:
        return SlotAlignment(
            slot=slot,
            judgement="unmapped",
            paper_value=paper,
            target_value=None,
            note=(
                f"the source instantiates {slot} ({paper}); the target states no counterpart. "
                "A precise restatement cannot be formed. This is where the transfer is "
                "most likely to break."
            ),
        )
    return SlotAlignment(
        slot=slot,
        judgement="mapped",
        paper_value=paper,
        target_value=target,
        note=f"both sides instantiate {slot}; the condition can be stated in the target's language.",
    )


def score_paper(doc: SourceDoc, paper: PaperSlots, ctx: TransferContext) -> PaperAlignment:
    target = target_slots(ctx)
    slots = [
        judge_slot(name, getattr(paper, name), target[name]) for name in ALIGNMENT_SLOTS
    ]
    mapped = sum(1 for slot in slots if slot.judgement == "mapped")
    unmapped = sum(1 for slot in slots if slot.judgement == "unmapped")
    denom = mapped + unmapped
    score = mapped / denom if denom else 0.0
    admitted = mapped >= MIN_MAPPED
    weak = admitted and unmapped >= mapped
    return PaperAlignment(
        doc_id=doc.doc_id,
        title=doc.title,
        slots=slots,
        mapped=mapped,
        unmapped=unmapped,
        score=round(score, 3),
        admitted=admitted,
        weak=weak,
    )


def _extract_schema() -> str:
    return json.dumps(PaperSlots.model_json_schema(), indent=2)


def extract_slots(
    retrieval: Retrieval,
    *,
    workdir: Path | None = None,
) -> dict[str, PaperSlots]:
    """One map per search leg. Paper-side slots only; no target in the query."""
    workdir = Path(workdir) if workdir else Path(tempfile.mkdtemp(prefix="transfer-audit-"))
    workdir.mkdir(parents=True, exist_ok=True)
    schema = _extract_schema()
    known = {doc.doc_id: doc for doc in retrieval.documents}
    extracted: dict[str, PaperSlots] = {}

    for search_id in retrieval.search_ids:
        stdout = pc(
            "map",
            "--worker",
            WORKER,
            "--from",
            search_id,
            "--output-schema",
            schema,
            _EXTRACT_QUERY,
            timeout=MAP_TIMEOUT,
        )
        map_id = parse_map_id(stdout)
        if not map_id:
            print(f"alignment map returned no id for {search_id}", file=sys.stderr)
            continue
        export = workdir / f"align-{map_id}.txt"
        pc("results", map_id, "--save", str(export))
        if not export.exists():
            continue
        for doc_id, payload in parse_map_blocks(export.read_text(encoding="utf-8")):
            if doc_id not in known or doc_id in extracted:
                continue
            parsed = payload_json(payload)
            if parsed is None:
                print(f"alignment: no JSON for {doc_id}", file=sys.stderr)
                continue
            try:
                extracted[doc_id] = PaperSlots.model_validate(parsed)
            except Exception as exc:
                print(f"alignment: invalid slots for {doc_id}: {exc}", file=sys.stderr)
    return extracted


def score_alignment(
    ctx: TransferContext,
    retrieval: Retrieval,
    *,
    extracted: dict[str, PaperSlots] | None = None,
    workdir: Path | None = None,
) -> AlignmentReport:
    """Score every T3 document. T4 should receive report.admitted_ids only."""
    extracted = extracted if extracted is not None else extract_slots(retrieval, workdir=workdir)
    papers: list[PaperAlignment] = []
    for doc in retrieval.documents:
        paper_slots = extracted.get(doc.doc_id, PaperSlots())
        papers.append(score_paper(doc, paper_slots, ctx))

    admitted = [paper.doc_id for paper in papers if paper.admitted]
    held = [paper.doc_id for paper in papers if not paper.admitted]
    print(
        f"alignment: {len(admitted)} admitted, {len(held)} held out "
        f"(gate: {MIN_MAPPED} mapped slots)",
        file=sys.stderr,
    )
    for paper in papers:
        flag = "ADMIT" if paper.admitted else "HOLD"
        if paper.weak:
            flag = "WEAK"
        breaks = ",".join(slot.slot for slot in paper.break_points) or "-"
        print(
            f"  {flag:5} {paper.doc_id:18} mapped={paper.mapped} "
            f"unmapped={paper.unmapped} breaks={breaks}",
            file=sys.stderr,
        )
    return AlignmentReport(
        papers=papers,
        admitted_ids=admitted,
        held_out_ids=held,
        threshold_mapped=MIN_MAPPED,
    )


def write_alignment(report: AlignmentReport, path: Path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(report.model_dump_json(indent=2) + "\n", encoding="utf-8")
    return path
