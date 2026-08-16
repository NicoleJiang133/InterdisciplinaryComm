from __future__ import annotations

from pathlib import Path

from transfer_audit.models import AlignmentReport, BreakPoint, LedgerEntry, PaperAlignment
from transfer_audit.report import (
    FIXTURE_SLOT_OBJECTS,
    pick_worked_example,
    render_fixture,
    render_report,
    write_report,
)

FIXTURES = Path(__file__).resolve().parent / "fixtures"


def _entry(**overrides: object) -> LedgerEntry:
    payload = {
        "axis": "A_isolation",
        "subtype": "A4",
        "status": "UNKNOWN",
        "source_assumption": "Training and test partitions are formed at the subject level.",
        "target_restatement": "ICU windows from one stay must not cross the split.",
        "rationale": "The two-sentence target is silent on how streams are partitioned.",
        "evidence_lines": "L12-L18",
        "what_would_resolve_it": "Are train and test splits made by patient admission?",
        "source_doc_id": "arx_example",
        **overrides,
    }
    return LedgerEntry.model_validate(payload)


def test_worked_example_prefers_legitimacy_over_isolation_cluster():
    isolation = _entry()
    legitimacy = _entry(
        axis="B_legitimacy",
        subtype=None,
        source_assumption="Sepsis onset is the time of antibiotic administration.",
        source_doc_id="PMC6925691",
        what_would_resolve_it=(
            "Were sepsis labels defined independently of antibiotic initiation?"
        ),
    )
    picked = pick_worked_example([isolation, legitimacy])
    assert picked is not None
    assert picked.source_doc_id == "PMC6925691"


def test_html_is_self_contained_and_shows_n_in_break_cells():
    entries = [
        _entry(),
        _entry(
            axis="B_legitimacy",
            subtype=None,
            source_doc_id="PMC6925691",
            source_assumption="Onset is the antibiotic timestamp.",
        ),
    ]
    alignment = AlignmentReport(
        papers=[
            PaperAlignment(
                doc_id="arx_example",
                title="A paper",
                slots=[],
                mapped=3,
                unmapped=1,
                extraction_quality=4,
                break_richness=1,
                admitted=True,
            )
        ],
        admitted_ids=["arx_example"],
        held_out_ids=["arx_held"],
        break_points=[
            BreakPoint(
                slot="isolation_unit",
                papers_stating=1,
                extracted=1,
                target_states_it=False,
                paper_values=["subject"],
            )
        ],
        min_extraction_quality=1,
    )
    rendered = render_report(entries, alignment=alignment)
    html = rendered.html
    assert "https://" not in html
    assert "http://" not in html
    assert "<script" not in html.lower()
    assert "1 / n=1" in html
    assert "arx_example" in html
    assert "L12-L18" in html
    assert "oscillator" not in html  # not injected unless requested
    assert "Why this is the question" in html
    assert rendered.metrics.unknown == 2


def test_markdown_puts_assumption_and_restatement_adjacent():
    rendered = render_report(
        [
            _entry(
                source_assumption="Independence is assumed across subjects.",
                target_restatement="Independence would have to hold across ICU stays.",
            )
        ]
    )
    md = rendered.markdown
    assert "**Source assumption**" in md
    assert "Independence is assumed across subjects." in md
    assert "**Target restatement**" in md
    assert "Independence would have to hold across ICU stays." in md
    src_at = md.index("**Source assumption**")
    tgt_at = md.index("**Target restatement**")
    assert src_at < tgt_at
    assert tgt_at - src_at < 200


def test_fixture_report_opens_offline_and_ports_canvas_layout(tmp_path):
    rendered = render_fixture()
    html_path, md_path = write_report(
        rendered, tmp_path / "report.html", tmp_path / "report.md"
    )
    html = html_path.read_text(encoding="utf-8")
    md = md_path.read_text(encoding="utf-8")
    assert rendered.metrics.n_entries == 9
    assert rendered.metrics.unknown == 9
    assert "PMC6925691" in html
    assert "antibiotic" in html.lower()
    assert "oscillator" in html
    assert "patch" in html
    assert "subject" in html
    assert " / n=9" in html
    assert "isolation_unit" in html
    assert "UNKNOWN" in html
    assert "https://" not in html
    assert "<script" not in html.lower()
    assert "### 1. What the source result depends on" in md
    assert "### 2. What that becomes in the target system" in md
    assert "### 3. Therefore, what to ask" in md
    assert any(obj["object"] == "oscillator" for obj in FIXTURE_SLOT_OBJECTS)
    assert html_path.exists() and md_path.exists()
