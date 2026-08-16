"""T3 — TransferContext -> source document ids.

Two deliberate fan-out legs, because an audit needs both halves of the transfer:
the target-side literature (what the claim is being applied TO) and the source-side
literature (the discipline the result came FROM). Retrieving only one half produces a
ledger that can only ask questions about one half.

Queries are built from schema slots, never from a keyword string, so the query says
what the claim structurally IS rather than which words it happens to contain.

Doc ids never come from the CLI's stdout — displayed ids are truncated there
(NOTES.md section 4c). Every search is followed by `results <s_id> --save`, and the ids
are read out of that CSV. Only the s_* result id itself is read from stdout, which is
safe: it is printed in full.
"""

from __future__ import annotations

import csv
import re
import sys
import tempfile
from collections.abc import Collection
from pathlib import Path

from pydantic import BaseModel

from transfer_audit.models import TransferContext
from transfer_audit.pc import pc

# map is fast only on 3-10 papers. Raising this makes the demo time out. Do not.
MAX_DOCS = 10
PER_SEARCH = 5
MIN_DOCS = 3

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


class RetrievalError(RuntimeError):
    """Retrieval produced too little to build a ledger from."""


class SourceDoc(BaseModel):
    doc_id: str
    source: str
    title: str
    search_id: str


class Retrieval(BaseModel):
    """Doc ids plus the s_* ids T4 needs for `map --from`."""

    doc_ids: list[str]
    search_ids: list[str]
    documents: list[SourceDoc]
    queries: dict[str, str]

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


def source_query(ctx: TransferContext, source_discipline: str | None = None) -> str:
    """The validity conditions of the discipline the result was borrowed from.

    Precedence is override, then the inferred slot. The extractor supplies the slot
    only about four runs in five (NOTES.md section 12) and the model rejects a
    temperature setting, so pinning it is the only way to make this leg reproducible.
    """
    discipline = source_discipline or ctx.source_discipline_hint
    if discipline:
        # Asks for studies that STATE their validity conditions. The looser phrasing
        # "validity conditions and cohort generalisation" also returned conceptual
        # guides and interpretability reviews, which have no protocol to audit.
        return (
            f"{discipline} prediction models evaluated on an external cohort: stated "
            "inclusion criteria, train-test split by subject, and measured performance "
            "change when the model is applied to a different population"
        )
    print(
        "WARNING: no source discipline (neither --source-discipline nor an inferred "
        "source_discipline_hint). The source leg falls back to a methods framing of the "
        "target slots, which stays inside the target discipline and weakens the audit.",
        file=sys.stderr,
    )
    subject = ctx.state_variable or ctx.target_claim
    readout = _clause("from", ctx.readout)
    return (
        f"machine learning prediction of {subject} {readout}: stated inclusion "
        "criteria, train-test split, external validation, and data leakage"
    ).replace("  ", " ")


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
    for source_flag, query in legs:
        stdout = pc("search", query, "-s", source_flag, "-n", str(per_search))
        search_id = _parse_search_id(stdout)
        if not search_id:
            print(f"no results for -s {source_flag}", file=sys.stderr)
            per_leg.append([])
            continue
        search_ids.append(search_id)
        per_leg.append(
            [
                SourceDoc(
                    doc_id=row["id"],
                    source=row.get("source", "") or source_flag,
                    title=row.get("title", ""),
                    search_id=search_id,
                )
                for row in _export_rows(search_id, workdir)
                if row["id"] not in deny
            ]
        )

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

    result = Retrieval(
        doc_ids=[doc.doc_id for doc in documents],
        search_ids=search_ids,
        documents=documents,
        queries={source_flag: query for source_flag, query in legs},
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
