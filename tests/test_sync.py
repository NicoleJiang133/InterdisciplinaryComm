"""Markdown round-trip: report.md edits come back as corrections.json."""

from __future__ import annotations

import json
from pathlib import Path

from transfer_audit.models import LedgerEntry
from transfer_audit.report import entry_anchor_id, render_report, write_report


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
        "source_doc_id": "arx_2104.10995",
        **overrides,
    }
    return LedgerEntry.model_validate(payload)


def _run_with_report(tmp_path: Path, entries: list[LedgerEntry]) -> Path:
    run = tmp_path / "20260101T120000Z"
    run.mkdir()
    (run / "ledger.json").write_text(
        json.dumps([entry.model_dump() for entry in entries], indent=2) + "\n",
        encoding="utf-8",
    )
    rendered = render_report(entries)
    write_report(rendered, run / "report.html", run / "report.md")
    return run


def test_sync_writes_markdown_correction_and_preserves_web_rows(tmp_path):
    from transfer_audit.sync import sync_run

    original = "ICU windows from one stay must not cross the split."
    corrected = "Splits must be formed at the ICU-stay level, not the window level."
    entry = _entry(target_restatement=original)
    other = _entry(
        source_doc_id="PMC6925691",
        axis="B_legitimacy",
        subtype=None,
        source_assumption="Onset is the antibiotic timestamp.",
        target_restatement="Labels must not be defined by the treatment timestamp.",
        what_would_resolve_it="Were sepsis labels defined independently of antibiotic initiation?",
    )
    run = _run_with_report(tmp_path, [entry, other])
    web_row = {
        "source_doc_id": "PMC6925691",
        "axis": "B_legitimacy",
        "target_restatement": "web already captured this one",
        "source": "web",
        "timestamp": "2026-01-01T00:00:00Z",
    }
    (run / "corrections.json").write_text(
        json.dumps([web_row], indent=2) + "\n", encoding="utf-8"
    )
    md = (run / "report.md").read_text(encoding="utf-8")
    (run / "report.md").write_text(md.replace(original, corrected), encoding="utf-8")

    result = sync_run(run)

    assert result.unchanged == 1
    assert result.corrected == 1
    assert result.corrections[0].source == "markdown"
    assert result.corrections[0].previous == original
    assert result.corrections[0].target_restatement == corrected
    assert result.corrections[0].entry_id == entry_anchor_id(entry)
    saved = json.loads((run / "corrections.json").read_text(encoding="utf-8"))
    assert saved[0] == web_row
    assert saved[0]["source"] == "web"
    markdown_rows = [row for row in saved if row["source"] == "markdown"]
    assert len(markdown_rows) == 1
    assert markdown_rows[0]["target_restatement"] == corrected
    assert markdown_rows[0]["timestamp"]


def test_sync_is_idempotent_when_the_markdown_correction_already_exists(tmp_path):
    from transfer_audit.sync import sync_run

    original = "ICU windows from one stay must not cross the split."
    corrected = "Splits must be formed at the ICU-stay level."
    run = _run_with_report(tmp_path, [_entry(target_restatement=original)])
    md = (run / "report.md").read_text(encoding="utf-8")
    (run / "report.md").write_text(md.replace(original, corrected), encoding="utf-8")

    first = sync_run(run)
    second = sync_run(run)

    assert first.corrected == 1
    assert second.corrected == 1
    saved = json.loads((run / "corrections.json").read_text(encoding="utf-8"))
    assert len(saved) == 1


def test_sync_reads_an_external_report_path(tmp_path):
    from transfer_audit.sync import sync_run

    original = "ICU windows from one stay must not cross the split."
    corrected = "Splits must be formed at the ICU-stay level."
    run = _run_with_report(tmp_path, [_entry(target_restatement=original)])
    sundial = tmp_path / "sundial" / "report.md"
    sundial.parent.mkdir()
    md = (run / "report.md").read_text(encoding="utf-8")
    sundial.write_text(md.replace(original, corrected), encoding="utf-8")

    result = sync_run(run, report=sundial)

    assert result.corrected == 1
    assert result.corrections[0].target_restatement == corrected
    # The run copy was not edited; sync still captured the Sundial file.
    assert original in (run / "report.md").read_text(encoding="utf-8")
