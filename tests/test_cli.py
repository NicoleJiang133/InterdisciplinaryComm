"""T6 — CLI. Replay is the demo safety net and must never touch the network."""

from __future__ import annotations

import shutil
from pathlib import Path

from typer.testing import CliRunner

from transfer_audit.models import (
    AlignmentReport,
    BreakPoint,
    LedgerEntry,
    PaperAlignment,
    TransferContext,
)
from transfer_audit.retrieve import Retrieval, SourceDoc

FIXTURES = Path(__file__).resolve().parent / "fixtures"
CLAIM = FIXTURES / "target_claim.txt"


def _saved_run(tmp_path: Path) -> Path:
    run = tmp_path / "saved"
    run.mkdir()
    for name in ("ledger.json", "alignment.json", "context.json"):
        shutil.copy(FIXTURES / name, run / name)
    return run


def test_replay_renders_reports_without_network(monkeypatch, tmp_path):
    from transfer_audit.cli import app
    from transfer_audit import pc as pc_module
    from transfer_audit import ingest as ingest_module

    def boom(*_args, **_kwargs):
        raise AssertionError("replay must not call paperclip or ingest")

    monkeypatch.setattr(pc_module, "pc", boom)
    monkeypatch.setattr(ingest_module, "build_context", boom)
    monkeypatch.setattr(ingest_module, "build_context_from_file", boom)

    run = _saved_run(tmp_path)
    result = CliRunner().invoke(app, ["run", "--replay", str(run)])
    assert result.exit_code == 0, result.output
    html = (run / "report.html").read_text(encoding="utf-8")
    md = (run / "report.md").read_text(encoding="utf-8")
    assert "PMC6925691" in html
    assert "UNKNOWN" in html
    assert "https://" not in html
    assert "<script" not in html.lower()
    assert "**Source assumption**" in md
    assert "PMC6925691" in md
    assert "replay" in result.output.lower() or "report.html" in result.output


def test_help_lists_run_not_score():
    from transfer_audit.cli import app

    result = CliRunner().invoke(app, ["--help"])
    assert result.exit_code == 0, result.output
    assert "run" in result.output
    assert "serve" in result.output
    assert "score" not in result.output.lower()
    assert "answer" not in result.output.lower()

    missing = CliRunner().invoke(app, ["score"])
    assert missing.exit_code != 0


def test_run_requires_claim_file_or_replay(tmp_path):
    from transfer_audit.cli import app

    neither = CliRunner().invoke(app, ["run"])
    assert neither.exit_code != 0

    both = CliRunner().invoke(
        app,
        ["run", "--claim-file", str(CLAIM), "--replay", str(tmp_path)],
    )
    assert both.exit_code != 0


def test_live_run_writes_artifacts_and_pins_source_discipline(monkeypatch, tmp_path):
    from transfer_audit import cli as cli_module
    from transfer_audit.ledger import LedgerRun

    ctx = TransferContext(
        target_claim="ICU patients will develop sepsis.",
        target_system="ICU patients",
        source_discipline_hint="neuroimaging",
    )
    retrieval = Retrieval(
        doc_ids=["arx_one", "PMC_two"],
        search_ids=["s_aaaaaa", "s_bbbbbb"],
        documents=[
            SourceDoc(doc_id="arx_one", source="arxiv", title="A", search_id="s_aaaaaa"),
            SourceDoc(doc_id="PMC_two", source="pmc", title="B", search_id="s_bbbbbb"),
        ],
        queries={"arxiv": "q", "pmc,biorxiv": "q2"},
    )
    alignment = AlignmentReport(
        papers=[
            PaperAlignment(
                doc_id="arx_one",
                title="A",
                slots=[],
                mapped=1,
                unmapped=1,
                extraction_quality=2,
                break_richness=1,
                admitted=True,
            ),
            PaperAlignment(
                doc_id="PMC_two",
                title="B",
                slots=[],
                mapped=0,
                unmapped=0,
                extraction_quality=0,
                break_richness=0,
                admitted=False,
            ),
        ],
        admitted_ids=["arx_one"],
        held_out_ids=["PMC_two"],
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
    entry = LedgerEntry(
        axis="A_isolation",
        subtype="A4",
        status="UNKNOWN",
        source_assumption="Splits are formed at the subject level.",
        target_restatement="ICU stays must not cross the split.",
        rationale="The claim is silent on partitioning.",
        evidence_lines="L12",
        what_would_resolve_it="Are train and test splits made by patient admission?",
        source_doc_id="arx_one",
    )

    seen: dict[str, object] = {}

    def fake_ingest(path, **kwargs):
        seen["claim"] = Path(path)
        return ctx

    def fake_retrieve(context, *, source_discipline=None, workdir=None, **kwargs):
        seen["source_discipline"] = source_discipline
        seen["hint"] = context.source_discipline_hint
        seen["retrieve_workdir"] = workdir
        return retrieval

    def fake_align(context, found, *, workdir=None, **kwargs):
        seen["align_ids"] = found.doc_ids
        seen["align_workdir"] = workdir
        return alignment

    def fake_map(context, doc_ids, search_ids, *, workdir=None, **kwargs):
        seen["ledger_ids"] = list(doc_ids)
        seen["search_ids"] = list(search_ids)
        seen["map_workdir"] = workdir
        return LedgerRun(entries=[entry], drops=[], map_ids=["m_deadbeef"])

    monkeypatch.setattr(cli_module, "build_context_from_file", fake_ingest)
    monkeypatch.setattr(cli_module, "retrieve", fake_retrieve)
    monkeypatch.setattr(cli_module, "score_alignment", fake_align)
    monkeypatch.setattr(cli_module, "run_map", fake_map)

    out = tmp_path / "live"
    result = CliRunner().invoke(
        cli_module.app,
        [
            "run",
            "--claim-file",
            str(CLAIM),
            "--source-discipline",
            "statistical physics",
            "--out",
            str(out),
        ],
    )
    assert result.exit_code == 0, result.output
    assert seen["source_discipline"] == "statistical physics"
    assert seen["hint"] == "statistical physics"
    assert seen["ledger_ids"] == ["arx_one"]  # admitted only
    assert seen["retrieve_workdir"] == out
    assert (out / "context.json").exists()
    assert (out / "search.json").exists()
    assert (out / "alignment.json").exists()
    assert (out / "ledger.json").exists()
    assert (out / "report.html").exists()
    assert (out / "report.md").exists()
    assert "arx_one" in (out / "report.html").read_text(encoding="utf-8")
