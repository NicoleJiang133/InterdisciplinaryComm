from __future__ import annotations

import json
from pathlib import Path

import pytest

from transfer_audit import ledger as ledger_module
from transfer_audit.models import LedgerEntry, TransferContext
from transfer_audit.ledger import (
    Drop,
    LedgerError,
    build_ledger,
    build_query,
    load_schema_text,
    run_map,
    write_ledger,
)

CTX = TransferContext(
    target_claim=(
        "the same connectivity-based approach should predict which ICU patients "
        "will develop sepsis from their continuous vital-sign monitoring streams"
    ),
    target_system="ICU patients",
    state_variable="development of sepsis",
    readout="continuous vital-sign monitoring streams",
    source_discipline_hint="neuroimaging",
)

DOC_IDS = ["arx_2103.16685", "PMC6925691"]
SEARCH_IDS = ["s_403f175a"]

# The worker fills source_doc_id with the TITLE, as observed in NOTES.md section 4c.
GOOD_PAYLOAD = {
    "axis": "C_domain_of_validity",
    "subtype": "C3",
    "status": "VIOLATED",
    "source_assumption": "The cohort was recruited at a single academic memory clinic.",
    "target_restatement": "ICU admissions would have to resemble that clinic population.",
    "rationale": "Recruitment was site-restricted, so case mix does not carry over.",
    "evidence_lines": "L120-L134",
    "what_would_resolve_it": None,
    "source_doc_id": "Normative Modelling in Neuroimaging",
}
UNKNOWN_NO_RESOLUTION = {**GOOD_PAYLOAD, "status": "UNKNOWN", "what_would_resolve_it": ""}
EXTRA_FIELD = {**GOOD_PAYLOAD, "confidence": 0.9}


def _export(*blocks: tuple[str, str, object]) -> str:
    """Reproduces the `results <m_id> --save` layout: header, doc_id, JSON payload."""
    out = []
    for index, (state, doc_id, payload) in enumerate(blocks, 1):
        body = payload if isinstance(payload, str) else json.dumps(payload)
        out.append(f"--- [{index}] [{state}] Some Paper Title ---\ndoc_id: {doc_id}\n{body}\n")
    return "\n".join(out)


# stdout shows a TRUNCATED id; nothing may be read from it.
MAP_STDOUT = """Map complete: 2/2 papers
Results ID: m_6cdc3b5c

  ✓ Normative Modelling in Neuroimaging
    arx_2103.16 · 2469ms
    {"axis": "C_domain_of_validity"}

[4.0s, saved to m_6cdc3b5c]
"""


class FakePc:
    def __init__(self, export: str):
        self.export = export
        self.calls: list[tuple[str, ...]] = []

    def __call__(self, *args: str, timeout: int = 300) -> str:
        self.calls.append(args)
        if args[0] == "map":
            return MAP_STDOUT
        if args[0] == "results":
            Path(args[3]).write_text(self.export, encoding="utf-8")
            return "saved\n"
        raise AssertionError(f"unexpected paperclip call: {args}")

    @property
    def map_call(self) -> tuple[str, ...]:
        return next(call for call in self.calls if call[0] == "map")


@pytest.fixture
def fake_pc(monkeypatch):
    def install(export: str) -> FakePc:
        fake = FakePc(export)
        monkeypatch.setattr(ledger_module, "pc", fake)
        return fake

    return install


def test_query_is_built_from_context_slots():
    query = build_query(CTX)
    assert "ICU patients" in query
    assert "development of sepsis" in query
    assert "continuous vital-sign monitoring streams" in query
    assert "not stated" in query  # perturbation is absent from the fixture


def test_output_schema_is_passed_as_contents_not_a_path(fake_pc, tmp_path):
    fake = fake_pc(_export(("success", DOC_IDS[0], GOOD_PAYLOAD)))
    run_map(CTX, DOC_IDS, SEARCH_IDS, workdir=tmp_path)
    schema_arg = fake.map_call[fake.map_call.index("--output-schema") + 1]
    assert json.loads(schema_arg)["properties"]["axis"]
    assert not schema_arg.endswith(".json")


def test_json_flag_is_never_passed_to_map(fake_pc, tmp_path):
    fake = fake_pc(_export(("success", DOC_IDS[0], GOOD_PAYLOAD)))
    run_map(CTX, DOC_IDS, SEARCH_IDS, workdir=tmp_path)
    assert "--json" not in fake.map_call


def test_map_runs_from_the_search_id(fake_pc, tmp_path):
    fake = fake_pc(_export(("success", DOC_IDS[0], GOOD_PAYLOAD)))
    run_map(CTX, DOC_IDS, SEARCH_IDS, workdir=tmp_path)
    call = fake.map_call
    assert call[call.index("--from") + 1] == "s_403f175a"
    assert call[-1] == build_query(CTX)  # query is positional and last


def test_default_worker_is_the_only_one_this_account_may_use(fake_pc, tmp_path):
    fake = fake_pc(_export(("success", DOC_IDS[0], GOOD_PAYLOAD)))
    run_map(CTX, DOC_IDS, SEARCH_IDS, workdir=tmp_path)
    call = fake.map_call
    assert call[call.index("--worker") + 1] == "quick-reader"


def test_source_doc_id_is_overwritten_with_the_known_id(fake_pc, tmp_path):
    fake_pc(_export(("success", DOC_IDS[0], GOOD_PAYLOAD)))
    run = run_map(CTX, DOC_IDS, SEARCH_IDS, workdir=tmp_path)
    assert run.entries[0].source_doc_id == "arx_2103.16685"


def test_ids_are_never_taken_from_map_stdout(fake_pc, tmp_path):
    fake_pc(_export(("success", DOC_IDS[0], GOOD_PAYLOAD)))
    run = run_map(CTX, DOC_IDS, SEARCH_IDS, workdir=tmp_path)
    assert all(entry.source_doc_id != "arx_2103.16" for entry in run.entries)


def test_results_are_read_from_the_saved_export(fake_pc, tmp_path):
    fake = fake_pc(_export(("success", DOC_IDS[0], GOOD_PAYLOAD)))
    run = run_map(CTX, DOC_IDS, SEARCH_IDS, workdir=tmp_path)
    results_call = next(call for call in fake.calls if call[0] == "results")
    assert results_call[1] == "m_6cdc3b5c" == run.map_ids[0]
    assert results_call[2] == "--save"


def test_invalid_entries_are_dropped_and_counted(fake_pc, tmp_path):
    fake_pc(
        _export(
            ("success", DOC_IDS[0], GOOD_PAYLOAD),
            ("success", DOC_IDS[1], EXTRA_FIELD),
        )
    )
    run = run_map(CTX, DOC_IDS, SEARCH_IDS, workdir=tmp_path)
    assert len(run.entries) == 1
    assert [drop.doc_id for drop in run.drops] == [DOC_IDS[1]]
    assert "confidence" in run.drops[0].reason


def test_unknown_without_resolution_is_dropped(fake_pc, tmp_path):
    fake_pc(_export(("success", DOC_IDS[0], UNKNOWN_NO_RESOLUTION)))
    run = run_map(CTX, DOC_IDS, SEARCH_IDS, workdir=tmp_path)
    assert run.entries == []
    assert "what_would_resolve_it" in run.drops[0].reason


def test_unparseable_payload_is_dropped(fake_pc, tmp_path):
    fake_pc(_export(("failed", DOC_IDS[0], "error: paper has no loadable full text")))
    run = run_map(CTX, DOC_IDS, SEARCH_IDS, workdir=tmp_path)
    assert run.entries == []
    assert run.drops == [Drop(doc_id=DOC_IDS[0], reason="no JSON object in map output")]


def test_documents_outside_the_capped_set_are_ignored(fake_pc, tmp_path):
    fake_pc(
        _export(
            ("success", DOC_IDS[0], GOOD_PAYLOAD),
            ("success", "arx_9999.99999", GOOD_PAYLOAD),
        )
    )
    run = run_map(CTX, DOC_IDS, SEARCH_IDS, workdir=tmp_path)
    assert [entry.source_doc_id for entry in run.entries] == [DOC_IDS[0]]
    assert run.drops == []  # trimmed by T3, not a failure


def test_a_paper_is_only_entered_once(fake_pc, tmp_path):
    fake_pc(
        _export(
            ("success", DOC_IDS[0], GOOD_PAYLOAD),
            ("success", DOC_IDS[0], GOOD_PAYLOAD),
        )
    )
    run = run_map(CTX, DOC_IDS, SEARCH_IDS, workdir=tmp_path)
    assert len(run.entries) == 1


def test_drop_count_is_printed(fake_pc, tmp_path, capsys):
    fake_pc(_export(("success", DOC_IDS[0], EXTRA_FIELD)))
    run_map(CTX, DOC_IDS, SEARCH_IDS, workdir=tmp_path)
    assert "0 valid entries, 1 dropped" in capsys.readouterr().err


def test_no_search_ids_raises(fake_pc, tmp_path):
    fake_pc("")
    with pytest.raises(LedgerError, match="--from"):
        run_map(CTX, DOC_IDS, [], workdir=tmp_path)


def test_build_ledger_returns_plain_entries(fake_pc, tmp_path):
    fake_pc(_export(("success", DOC_IDS[0], GOOD_PAYLOAD)))
    entries = build_ledger(CTX, DOC_IDS, SEARCH_IDS)
    assert all(isinstance(entry, LedgerEntry) for entry in entries)


def test_schema_text_is_the_generated_file_contents():
    schema = json.loads(load_schema_text())
    assert schema["additionalProperties"] is False
    assert "axis" in schema["required"]


def test_write_ledger_round_trips(fake_pc, tmp_path):
    fake_pc(_export(("success", DOC_IDS[0], GOOD_PAYLOAD)))
    entries = run_map(CTX, DOC_IDS, SEARCH_IDS, workdir=tmp_path).entries
    path = write_ledger(entries, tmp_path / "run" / "ledger.json")
    written = json.loads(path.read_text(encoding="utf-8"))
    assert [LedgerEntry.model_validate(item) for item in written] == entries


@pytest.mark.integration
def test_live_ledger_meets_acceptance(tmp_path):
    from transfer_audit.retrieve import retrieve

    found = retrieve(CTX, source_discipline="neuroimaging", workdir=tmp_path)
    run = run_map(CTX, found.doc_ids, found.search_ids, workdir=tmp_path)
    assert len(run.entries) >= 5, f"only {len(run.entries)} valid entries"
    assert len(run.axes) >= 3, f"axes covered: {run.axes}"
    assert all(entry.source_doc_id in found.doc_ids for entry in run.entries)
