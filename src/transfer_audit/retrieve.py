"""T3 — TransferContext -> source document ids.

Two deliberate fan-out legs, because an audit needs both halves of the transfer:
the target-side literature (what the claim is being applied TO) and the source-side
literature (the discipline the result came FROM). Retrieving only one half produces a
ledger that can only ask questions about one half.

Queries are built from schema slots, never from a keyword string, so the query says
what the claim structurally IS rather than which words it happens to contain.

The source-leg query leads with the field's own objects and mechanisms, then asks
about the conditions under which the result holds — in that field's terms. A methods
vocabulary (external cohort, inclusion criteria, train-test split) is itself the
clinical-prediction cluster on arXiv; prefixing a discipline name does not leave it.
See docs/05-findings.md.

Doc ids never come from the CLI's stdout — displayed ids are truncated there
(NOTES.md section 4c). Every search is followed by `results <s_id> --save`, and the ids
are read out of that CSV. Only the s_* result id itself is read from stdout, which is
safe: it is printed in full.
"""

from __future__ import annotations

import csv
import json
import re
import sys
import tempfile
from collections.abc import Collection
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict

from transfer_audit.ingest import source_clause
from transfer_audit.ledger import MAP_TIMEOUT, WORKER, parse_map_blocks, parse_map_id, payload_json
from transfer_audit.models import TransferContext
from transfer_audit.pc import pc

# map is fast only on 3-10 papers. Raising this makes the demo time out. Do not.
MAX_DOCS = 10
PER_SEARCH = 5
MIN_DOCS = 3
IN_DISCIPLINE_FLOOR = 0.5

# Escape hatch for papers that survive the query but yield only metaphors. Pruning
# happens here, at query-construction time, and never with `paperclip filter`: filter
# rewrites the stored result set in place, which breaks `map --from` and T6 --replay
# (NOTES.md section 13d). A denied doc is still mapped, because map addresses a whole
# search id; its entry is discarded against the doc-id allowlist in ledger.py.
DEFAULT_DENY = frozenset(
    {
        # "Interpretability of Machine Learning Methods Applied to Neuroimaging" and
        # "Normative Modelling in Neuroimaging: A Practical Guide". Both are conceptual
        # guides, so the only condition they offer is spatial registration of brain
        # images, which restates as "align the vital-sign streams somehow". A metaphor,
        # not an audit finding, in two independent iterations.
        "arx_2204.07005",
        "arx_2509.07237",
    }
)

_SEARCH_ID = re.compile(r"\bs_[0-9a-f]{6,}\b")

# The vocabulary that IS the clinical-prediction cluster. A source-leg query containing
# these lands there regardless of the discipline prefix (docs/05-findings.md).
METHODS_CLUSTER = (
    "external cohort",
    "inclusion criteria",
    "train-test",
    "train test",
    "held-out",
    "held out",
    "data leakage",
    "prediction models evaluated",
)

_VALIDITY_IN_FIELD_TERMS = (
    "regimes, limits, and assumptions under which the result holds"
)

DisciplineLabel = Literal["in_discipline", "generic"]


class RetrievalError(RuntimeError):
    """Retrieval produced too little to build a ledger from."""


class SourceDoc(BaseModel):
    doc_id: str
    source: str
    title: str
    search_id: str
    discipline_label: DisciplineLabel | None = None


class SourceLegCheck(BaseModel):
    """In-discipline vs generic classification of the arxiv source leg."""

    discipline: str
    in_discipline: int
    generic: int
    unclassified: int
    labels: dict[str, DisciplineLabel]
    below_floor: bool


class _PaperLabel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    label: DisciplineLabel
    reason: str


class Retrieval(BaseModel):
    """Doc ids plus the s_* ids T4 needs for `map --from`."""

    doc_ids: list[str]
    search_ids: list[str]
    documents: list[SourceDoc]
    queries: dict[str, str]
    source_leg_check: SourceLegCheck | None = None

    @property
    def sources(self) -> set[str]:
        return {doc.source for doc in self.documents}


def _clause(prefix: str, value: str | None) -> str:
    return f"{prefix} {value}" if value else ""


def target_query(ctx: TransferContext) -> str:
    """What is being predicted, in what system, from what signal."""
    head = f"predicting {ctx.state_variable}" if ctx.state_variable else ctx.target_claim
    parts = [
        head,
        _clause("in", ctx.target_system),
        _clause("from", ctx.readout),
        _clause("after", ctx.perturbation),
    ]
    query = " ".join(p for p in parts if p)
    if ctx.constraints:
        query += "; " + "; ".join(ctx.constraints[:2])
    return query


def source_objects(ctx: TransferContext) -> str | None:
    """The source result's own objects and mechanisms, not the target's."""
    raw = ctx.source_result.strip() if ctx.source_result and ctx.source_result.strip() else None
    if raw is None:
        raw = source_clause(ctx.target_claim)
    if not raw:
        return None
    return " ".join(raw.split())


def source_query(ctx: TransferContext, source_discipline: str | None = None) -> str:
    """Subject matter of the borrowed field first; validity conditions second.

    Precedence for the discipline name is override, then the inferred slot. The
    extractor supplies the slot only about four runs in five (NOTES.md section 12)
    and the model rejects a temperature setting, so pinning it is the only way to
    make this leg reproducible.

    Validity is asked in the field's own terms (regimes, limits, assumptions), not
    in train-test vocabulary. That vocabulary is the clinical-prediction cluster;
    leading with it retrieves methodology papers regardless of the discipline prefix.
    """
    discipline = source_discipline or ctx.source_discipline_hint
    objects = source_objects(ctx)
    if discipline:
        head = f"{discipline}: {objects}" if objects else discipline
        return f"{head}. {_VALIDITY_IN_FIELD_TERMS}"
    print(
        "WARNING: no source discipline (neither --source-discipline nor an inferred "
        "source_discipline_hint). The source leg falls back to source objects if known, "
        "otherwise the target slots, and stays topically narrower. The operator should "
        "pin --source-discipline.",
        file=sys.stderr,
    )
    if objects:
        return f"{objects}. {_VALIDITY_IN_FIELD_TERMS}"
    subject = ctx.state_variable or ctx.target_claim
    readout = _clause("from", ctx.readout)
    system = _clause("in", ctx.target_system)
    return f"{subject} {system} {readout}. {_VALIDITY_IN_FIELD_TERMS}".replace("  ", " ")


def _classify_schema() -> str:
    return json.dumps(_PaperLabel.model_json_schema(), indent=2)


def _classify_query(discipline: str) -> str:
    return (
        f"The source discipline this search was aimed at is: {discipline}. "
        "Classify this paper's own subject matter. "
        "in_discipline: the paper is about this discipline's objects, mechanisms, "
        "or phenomena. "
        "generic: the contribution is how to validate, transport, shift-robustify, "
        "or evaluate a prediction model, and any domain is incidental. "
        "Judge the paper, not a target application. Domain distance is not the question."
    )


def _warn_source_leg(check: SourceLegCheck, docs: list[SourceDoc]) -> None:
    labelled = check.in_discipline + check.generic
    print(
        f"WARNING: source-leg in-discipline {check.in_discipline}/{labelled} "
        f"is below half (floor {IN_DISCIPLINE_FLOOR}) for {check.discipline!r}. "
        "The query landed in a generic methods cluster, not the pinned discipline. "
        "Break-point tables from this run are not field evidence.",
        file=sys.stderr,
    )
    by_id = {doc.doc_id: doc for doc in docs}
    for doc_id, label in check.labels.items():
        if label != "generic":
            continue
        title = by_id[doc_id].title if doc_id in by_id else ""
        print(f"  generic  {doc_id:18} {title[:80]}", file=sys.stderr)


def classify_source_leg(
    docs: list[SourceDoc],
    search_id: str,
    discipline: str,
    *,
    workdir: Path,
) -> SourceLegCheck:
    """Label each source-leg paper in-discipline or generic. Warn below the floor.

    Uses map on the existing search id. Does not call `paperclip filter`: filter
    rewrites the stored result set in place and would break replay.
    """
    empty = SourceLegCheck(
        discipline=discipline,
        in_discipline=0,
        generic=0,
        unclassified=len(docs),
        labels={},
        below_floor=False,
    )
    if not docs or not search_id:
        return empty

    stdout = pc(
        "map",
        "--worker",
        WORKER,
        "--from",
        search_id,
        "--output-schema",
        _classify_schema(),
        _classify_query(discipline),
        timeout=MAP_TIMEOUT,
    )
    map_id = parse_map_id(stdout)
    if not map_id:
        print(
            f"WARNING: source-leg discipline check produced no map id for {search_id}.",
            file=sys.stderr,
        )
        return empty

    export = workdir / f"classify-{map_id}.txt"
    pc("results", map_id, "--save", str(export))
    if not export.exists():
        print(
            f"WARNING: source-leg discipline check wrote nothing for {map_id}.",
            file=sys.stderr,
        )
        return empty

    wanted = {doc.doc_id for doc in docs}
    labels: dict[str, DisciplineLabel] = {}
    for doc_id, payload in parse_map_blocks(export.read_text(encoding="utf-8")):
        if doc_id not in wanted:
            continue
        parsed = payload_json(payload)
        if parsed is None:
            continue
        try:
            labelled = _PaperLabel.model_validate(parsed)
        except Exception as exc:
            print(f"source-leg check: invalid label for {doc_id}: {exc}", file=sys.stderr)
            continue
        labels[doc_id] = labelled.label

    in_disc = sum(1 for label in labels.values() if label == "in_discipline")
    generic = sum(1 for label in labels.values() if label == "generic")
    labelled_n = in_disc + generic
    below = labelled_n > 0 and (in_disc / labelled_n) < IN_DISCIPLINE_FLOOR
    check = SourceLegCheck(
        discipline=discipline,
        in_discipline=in_disc,
        generic=generic,
        unclassified=sum(1 for doc in docs if doc.doc_id not in labels),
        labels=labels,
        below_floor=below,
    )
    if below:
        _warn_source_leg(check, docs)
    elif labelled_n == 0:
        print(
            "WARNING: source-leg discipline check produced no labels. "
            "In-discipline rate is unknown.",
            file=sys.stderr,
        )
    return check


def _parse_search_id(stdout: str) -> str | None:
    found = _SEARCH_ID.search(stdout)
    return found.group(0) if found else None


def _export_rows(search_id: str, workdir: Path) -> list[dict[str, str]]:
    """Full, untruncated ids come from the CSV export, never from stdout."""
    path = workdir / f"{search_id}.csv"
    pc("results", search_id, "--save", str(path))
    if not path.exists():
        raise RetrievalError(f"results --save wrote nothing for {search_id}")
    with path.open(encoding="utf-8") as handle:
        return [row for row in csv.DictReader(handle) if row.get("id")]


def retrieve(
    ctx: TransferContext,
    *,
    source_discipline: str | None = None,
    deny: Collection[str] = DEFAULT_DENY,
    limit: int = MAX_DOCS,
    per_search: int = PER_SEARCH,
    workdir: Path | None = None,
) -> Retrieval:
    """Fan out by role across two source groups and return deduplicated documents."""
    limit = min(limit, MAX_DOCS)
    workdir = Path(workdir) if workdir else Path(tempfile.mkdtemp(prefix="transfer-audit-"))
    workdir.mkdir(parents=True, exist_ok=True)

    legs = [
        ("arxiv", source_query(ctx, source_discipline)),
        ("pmc,biorxiv", target_query(ctx)),
    ]

    per_leg: list[list[SourceDoc]] = []
    search_ids: list[str] = []
    source_leg_docs: list[SourceDoc] = []
    source_search_id: str | None = None
    for source_flag, query in legs:
        stdout = pc("search", query, "-s", source_flag, "-n", str(per_search))
        search_id = _parse_search_id(stdout)
        if not search_id:
            print(f"no results for -s {source_flag}", file=sys.stderr)
            per_leg.append([])
            continue
        search_ids.append(search_id)
        docs = [
            SourceDoc(
                doc_id=row["id"],
                source=row.get("source", "") or source_flag,
                title=row.get("title", ""),
                search_id=search_id,
            )
            for row in _export_rows(search_id, workdir)
            if row["id"] not in deny
        ]
        per_leg.append(docs)
        if source_flag == "arxiv":
            source_leg_docs = docs
            source_search_id = search_id

    # Round-robin so that hitting the cap cannot silently drop a whole discipline.
    documents: list[SourceDoc] = []
    seen: set[str] = set()
    for rank in range(max((len(leg) for leg in per_leg), default=0)):
        for leg in per_leg:
            if rank < len(leg) and leg[rank].doc_id not in seen and len(documents) < limit:
                seen.add(leg[rank].doc_id)
                documents.append(leg[rank])

    if len(documents) < MIN_DOCS:
        raise RetrievalError(
            f"only {len(documents)} documents retrieved, need at least {MIN_DOCS}. "
            "The context slots may be too narrow to match anything."
        )

    discipline = source_discipline or ctx.source_discipline_hint
    check: SourceLegCheck | None = None
    if discipline and source_search_id and source_leg_docs:
        check = classify_source_leg(
            source_leg_docs, source_search_id, discipline, workdir=workdir
        )
        labelled = check.labels
        documents = [
            doc.model_copy(update={"discipline_label": labelled.get(doc.doc_id)})
            for doc in documents
        ]

    result = Retrieval(
        doc_ids=[doc.doc_id for doc in documents],
        search_ids=search_ids,
        documents=documents,
        queries={source_flag: query for source_flag, query in legs},
        source_leg_check=check,
    )
    if len(result.sources) < 2:
        print(
            f"WARNING: all {len(documents)} documents came from one source "
            f"({', '.join(result.sources)}). The fan-out is not working.",
            file=sys.stderr,
        )
    return result


def find_sources(
    ctx: TransferContext,
    source_discipline: str | None = None,
    *,
    deny: Collection[str] = DEFAULT_DENY,
) -> list[str]:
    """BUILD.md T3 entry point. Use retrieve() when you also need the s_* ids."""
    return retrieve(ctx, source_discipline=source_discipline, deny=deny).doc_ids


def write_search(result: Retrieval, path: Path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(result.model_dump_json(indent=2) + "\n", encoding="utf-8")
    return path


if __name__ == "__main__":
    from transfer_audit.ingest import build_context_from_file

    source = Path(sys.argv[1] if len(sys.argv) > 1 else "tests/fixtures/target_claim.txt")
    retrieval = retrieve(build_context_from_file(source))
    print(retrieval.model_dump_json(indent=2))
