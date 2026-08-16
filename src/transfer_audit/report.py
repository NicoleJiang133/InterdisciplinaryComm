"""T5 — ledger -> self-contained HTML and Markdown reports.

Layout is ported from the source-leg-rerun canvas: metric row, break-point table
with n in every cell, slot-object panel (oscillator / patch / subject), ledger
grouped by axis, status distribution. The worked-example panel sits at the top
of both formats: source condition, target restatement, therefore the question.
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from jinja2 import Environment, FileSystemLoader
from pydantic import BaseModel, ConfigDict

from transfer_audit.models import (
    AlignmentReport,
    Axis,
    LedgerEntry,
    Status,
    TransferContext,
)

TEMPLATES = Path(__file__).resolve().parent / "templates"
AXIS_ORDER: tuple[Axis, ...] = (
    "A_isolation",
    "B_legitimacy",
    "C_domain_of_validity",
    "D_metric_alignment",
    "E_evidence_quality",
)
STATUS_ORDER: tuple[Status, ...] = ("SATISFIED", "VIOLATED", "UNKNOWN", "NA")

# Documented G4 / thesis row. Used when rendering the committed fixture example.
# n=4 extracted source-leg papers per out-of-domain run; see docs/01-thesis.md.
FIXTURE_SLOT_OBJECTS: tuple[dict[str, str | int], ...] = (
    {
        "discipline": "neuroimaging",
        "object": "subject",
        "n": "fixture",
        "note": "n from the fMRI fixture",
    },
    {
        "discipline": "statistical physics",
        "object": "oscillator",
        "n": 4,
        "note": "or a realisation of the noise",
    },
    {
        "discipline": "optimal foraging",
        "object": "patch",
        "n": 4,
        "note": "or a forager",
    },
)

# Prefer the axes that findings.md names as the strongest individual findings.
_WORKED_AXIS_RANK = {
    "B_legitimacy": 0,
    "C_domain_of_validity": 1,
    "D_metric_alignment": 2,
    "E_evidence_quality": 3,
    "A_isolation": 4,
}


class ReportMetrics(BaseModel):
    model_config = ConfigDict(extra="forbid")

    n_entries: int
    unknown: int
    n_axes: int
    extracted: int
    held: int


class RenderedReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    html: str
    markdown: str
    metrics: ReportMetrics


def _env() -> Environment:
    return Environment(
        loader=FileSystemLoader(TEMPLATES),
        autoescape=lambda name: bool(name and name.endswith(".html.j2")),
        trim_blocks=True,
        lstrip_blocks=True,
    )


def pick_worked_example(entries: list[LedgerEntry]) -> LedgerEntry | None:
    """The strongest entry: a specific question a reviewer can act on.

    B_legitimacy and non-A axes outrank the isolation cluster. UNKNOWN with a
    resolution question outranks a verdict, because the two-sentence fixture
    is silent on method.
    """
    if not entries:
        return None

    def key(entry: LedgerEntry) -> tuple[int, int, int]:
        unknown = 0 if entry.status == "UNKNOWN" else 1
        axis = _WORKED_AXIS_RANK.get(entry.axis, 9)
        specific = 0 if (entry.what_would_resolve_it or "") else 1
        return (unknown, axis, specific)

    return sorted(entries, key=key)[0]


def status_rows(entries: list[LedgerEntry]) -> list[dict[str, str | int]]:
    counts = Counter(entry.status for entry in entries)
    return [{"status": status, "count": counts.get(status, 0)} for status in STATUS_ORDER]


def group_by_axis(entries: list[LedgerEntry]) -> list[tuple[str, list[LedgerEntry]]]:
    buckets: dict[str, list[LedgerEntry]] = {axis: [] for axis in AXIS_ORDER}
    for entry in entries:
        buckets.setdefault(entry.axis, []).append(entry)
    return [(axis, items) for axis, items in buckets.items() if items]


def slot_objects_from_alignment(alignment: AlignmentReport) -> list[dict[str, str | int]]:
    """Unique isolation_unit values from extracted papers, for a run-specific panel."""
    seen: list[dict[str, str | int]] = []
    used: set[str] = set()
    for paper in alignment.papers:
        if not paper.admitted:
            continue
        for slot in paper.slots:
            if slot.slot != "isolation_unit" or not slot.paper_value:
                continue
            value = slot.paper_value.strip()
            if value in used:
                continue
            used.add(value)
            seen.append(
                {
                    "discipline": paper.doc_id,
                    "object": value,
                    "n": 1,
                    "note": "",
                }
            )
    return seen


def _view(
    entries: list[LedgerEntry],
    *,
    alignment: AlignmentReport | None,
    context: TransferContext | None,
    slot_objects: list[dict[str, str | int]] | None,
    title: str,
) -> dict:
    extracted = len(alignment.admitted_ids) if alignment else len(entries)
    held = len(alignment.held_out_ids) if alignment else 0
    objects = slot_objects
    if objects is None and alignment is not None:
        objects = slot_objects_from_alignment(alignment)
    return {
        "title": title,
        "context": context,
        "worked": pick_worked_example(entries),
        "metrics": ReportMetrics(
            n_entries=len(entries),
            unknown=sum(1 for entry in entries if entry.status == "UNKNOWN"),
            n_axes=len({entry.axis for entry in entries}),
            extracted=extracted,
            held=held,
        ),
        "break_points": alignment.break_points if alignment else [],
        "extracted_n": extracted,
        "slot_objects": objects or [],
        "status_rows": status_rows(entries),
        "grouped": group_by_axis(entries),
    }


def render_report(
    entries: list[LedgerEntry],
    *,
    alignment: AlignmentReport | None = None,
    context: TransferContext | None = None,
    slot_objects: list[dict[str, str | int]] | None = None,
    title: str = "Assumption ledger",
) -> RenderedReport:
    view = _view(
        entries,
        alignment=alignment,
        context=context,
        slot_objects=slot_objects,
        title=title,
    )
    env = _env()
    html = env.get_template("report.html.j2").render(**view)
    markdown = env.get_template("report.md.j2").render(**view)
    return RenderedReport(html=html, markdown=markdown, metrics=view["metrics"])


def load_entries(path: Path) -> list[LedgerEntry]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    return [LedgerEntry.model_validate(row) for row in payload]


def load_alignment(path: Path) -> AlignmentReport:
    return AlignmentReport.model_validate_json(Path(path).read_text(encoding="utf-8"))


def load_context(path: Path) -> TransferContext:
    return TransferContext.model_validate_json(Path(path).read_text(encoding="utf-8"))


def write_report(
    rendered: RenderedReport,
    html_path: Path,
    markdown_path: Path,
) -> tuple[Path, Path]:
    html_path = Path(html_path)
    markdown_path = Path(markdown_path)
    html_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    html_path.write_text(rendered.html, encoding="utf-8")
    markdown_path.write_text(rendered.markdown, encoding="utf-8")
    return html_path, markdown_path


def render_fixture(
    *,
    ledger_path: Path | None = None,
    alignment_path: Path | None = None,
    context_path: Path | None = None,
) -> RenderedReport:
    """Render the committed fixture (9/9 UNKNOWN fMRI → ICU ledger)."""
    root = Path(__file__).resolve().parents[2]
    fixtures = root / "tests" / "fixtures"
    entries = load_entries(ledger_path or fixtures / "ledger.json")
    alignment = load_alignment(alignment_path or fixtures / "alignment.json")
    context = load_context(context_path or fixtures / "context.json")
    return render_report(
        entries,
        alignment=alignment,
        context=context,
        slot_objects=list(FIXTURE_SLOT_OBJECTS),
        title="Assumption ledger — fixture",
    )


if __name__ == "__main__":
    import sys

    rendered = render_fixture()
    root = Path(__file__).resolve().parents[2]
    html_out = Path(sys.argv[1]) if len(sys.argv) > 1 else root / "docs" / "example-report.html"
    md_out = Path(sys.argv[2]) if len(sys.argv) > 2 else root / "docs" / "example-report.md"
    write_report(rendered, html_out, md_out)
    print(f"wrote {html_out}")
    print(f"wrote {md_out}")
    print(
        f"{rendered.metrics.unknown} / {rendered.metrics.n_entries} UNKNOWN, "
        f"{rendered.metrics.n_axes} axes"
    )
