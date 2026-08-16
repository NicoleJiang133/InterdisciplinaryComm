from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from transfer_audit import retrieve as retrieve_module
from transfer_audit.models import TransferContext
from transfer_audit.retrieve import (
    DEFAULT_DENY,
    IN_DISCIPLINE_FLOOR,
    MAX_DOCS,
    METHODS_CLUSTER,
    RetrievalError,
    find_sources,
    retrieve,
    source_query,
    target_query,
    write_search,
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
    source_result=(
        "A random-forest classifier trained on resting-state fMRI connectivity "
        "matrices predicts conversion to Alzheimer's disease with 92% accuracy"
    ),
)

# stdout deliberately carries TRUNCATED ids, as the real CLI does.
ARXIV_STDOUT = """Found 2 papers  [s_403f175a]

  1. Deep Learning in current Neuroimaging
     arx_2103.16... · arXiv · 2021
"""
PMC_STDOUT = """Found 2 papers  [s_72ddd280]

  1. Machine Learning Models for Analysis of Vital Signs Dynamics
     PMC69256... · PMC · 2019
"""
ROWS = {
    "s_403f175a": [
        {"id": "arx_2103.16685", "source": "arXiv", "title": "Deep Learning in Neuroimaging"},
        {"id": "arx_2410.00946", "source": "arXiv", "title": "Spectral Graph Sample Weighting"},
    ],
    "s_72ddd280": [
        {"id": "PMC6925691", "source": "PMC", "title": "Vital Sign Dynamics"},
        {"id": "bio_5e4102086c00", "source": "bioRxiv", "title": "Hypotensive Events in ICU"},
    ],
}


MAP_STDOUT = """Map complete: 2/2 papers
Results ID: m_6cdc3b5c

[1.0s, saved to m_6cdc3b5c]
"""


class FakePc:
    """Stands in for the paperclip CLI: prints truncated ids, exports full ones."""

    def __init__(self, stdouts=None, rows=None, labels=None):
        self.stdouts = list(stdouts if stdouts is not None else [ARXIV_STDOUT, PMC_STDOUT])
        self.rows = rows if rows is not None else ROWS
        self.labels = labels or "in_discipline"
        self.calls: list[tuple[str, ...]] = []
        self._search_count = 0

    def __call__(self, *args: str, timeout: int = 300) -> str:
        self.calls.append(args)
        if args[0] == "search":
            # cycles, so one fake can serve several retrieve() calls in a test
            stdout = self.stdouts[self._search_count % len(self.stdouts)]
            self._search_count += 1
            return stdout
        if args[0] == "map":
            return MAP_STDOUT
        if args[0] == "results":
            result_id, path = args[1], Path(args[3])
            if result_id.startswith("m_"):
                path.write_text(self._classify_export(), encoding="utf-8")
                return f"Saved to {path}\n"
            with path.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=["title", "id", "source"])
                writer.writeheader()
                writer.writerows(self.rows.get(result_id, []))
            return f"Saved to {path}\n"
        raise AssertionError(f"unexpected paperclip call: {args}")

    def _classify_export(self) -> str:
        rows = self.rows.get("s_403f175a", [])
        blocks = []
        for index, row in enumerate(rows, 1):
            label = self.labels[row["id"]] if isinstance(self.labels, dict) else self.labels
            payload = json.dumps({"label": label, "reason": "test"})
            blocks.append(
                f"--- [{index}] [success] {row['title']} ---\n"
                f"doc_id: {row['id']}\n"
                f"{payload}\n"
            )
        return "\n".join(blocks)


@pytest.fixture
def fake_pc(monkeypatch):
    fake = FakePc()
    monkeypatch.setattr(retrieve_module, "pc", fake)
    return fake


def test_queries_are_built_from_slots_not_keywords():
    target = target_query(CTX)
    assert "development of sepsis" in target
    assert "ICU patients" in target
    assert "continuous vital-sign monitoring streams" in target
    # the source leg asks about the discipline being borrowed from
    assert CTX.source_discipline_hint in source_query(CTX)


def test_source_query_falls_back_when_no_discipline_hint(capsys):
    ctx = CTX.model_copy(update={"source_discipline_hint": None})
    query = source_query(ctx)
    assert "neuroimaging" not in query
    assert "resting-state fMRI" in query
    assert "no source discipline" in capsys.readouterr().err
    lowered = query.lower()
    assert not any(term in lowered for term in METHODS_CLUSTER)


def test_source_query_falls_back_to_target_slots_without_source_objects(capsys):
    ctx = CTX.model_copy(update={"source_discipline_hint": None, "source_result": None})
    query = source_query(ctx)
    assert "development of sepsis" in query
    assert "no source discipline" in capsys.readouterr().err


def test_operator_override_beats_the_inferred_hint():
    query = source_query(CTX, "labour economics")
    assert "labour economics" in query
    assert "neuroimaging" not in query


def test_override_rescues_a_run_where_the_extractor_returned_no_hint(capsys):
    ctx = CTX.model_copy(update={"source_discipline_hint": None})
    query = source_query(ctx, "neuroimaging")
    assert "neuroimaging" in query
    assert capsys.readouterr().err == ""


def test_retrieve_passes_the_override_into_the_source_leg(fake_pc, tmp_path):
    retrieve(CTX, source_discipline="labour economics", workdir=tmp_path)
    source_leg = next(call for call in fake_pc.calls if call[0] == "search")
    assert "labour economics" in source_leg[1]


def test_find_sources_accepts_the_override(fake_pc, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    find_sources(CTX, "labour economics")
    source_leg = next(call for call in fake_pc.calls if call[0] == "search")
    assert "labour economics" in source_leg[1]


def test_denied_docs_are_dropped_before_the_ledger_sees_them(fake_pc, tmp_path):
    result = retrieve(CTX, deny={"arx_2103.16685"}, workdir=tmp_path)
    assert "arx_2103.16685" not in result.doc_ids
    assert "arx_2410.00946" in result.doc_ids


def test_denylist_lowers_the_total_rather_than_backfilling(fake_pc, tmp_path):
    kept = retrieve(CTX, deny=frozenset(), workdir=tmp_path).doc_ids
    pruned = retrieve(CTX, deny={"arx_2103.16685"}, workdir=tmp_path).doc_ids
    assert len(pruned) == len(kept) - 1


def test_the_two_metaphor_papers_are_denied_by_default():
    assert {"arx_2204.07005", "arx_2509.07237"} <= set(DEFAULT_DENY)


def test_source_query_leads_with_discipline_and_source_objects():
    query = source_query(CTX)
    assert query.startswith("neuroimaging:")
    assert "resting-state fMRI" in query
    assert "regimes, limits, and assumptions" in query
    lowered = query.lower()
    assert not any(term in lowered for term in METHODS_CLUSTER)


def test_source_query_does_not_use_train_test_vocabulary_outside_ml():
    ctx = CTX.model_copy(
        update={
            "source_discipline_hint": "statistical physics",
            "source_result": (
                "Kuramoto mean-field coupling of noisy oscillators predicts "
                "the onset of firefly flash synchrony"
            ),
        }
    )
    query = source_query(ctx, "statistical physics")
    assert query.startswith("statistical physics:")
    assert "Kuramoto" in query
    assert "noisy oscillators" in query
    lowered = query.lower()
    assert not any(term in lowered for term in METHODS_CLUSTER)


def test_ids_come_from_the_csv_not_from_stdout(fake_pc, tmp_path):
    doc_ids = retrieve(CTX, workdir=tmp_path).doc_ids
    assert "arx_2103.16685" in doc_ids
    assert "PMC6925691" in doc_ids
    assert not any(doc_id.endswith("...") for doc_id in doc_ids)


def test_fans_out_across_both_source_groups(fake_pc, tmp_path):
    result = retrieve(CTX, workdir=tmp_path)
    searches = [call for call in fake_pc.calls if call[0] == "search"]
    assert [call[call.index("-s") + 1] for call in searches] == ["arxiv", "pmc,biorxiv"]
    assert result.sources == {"arXiv", "PMC", "bioRxiv"}


def test_every_search_is_followed_by_a_results_export(fake_pc, tmp_path):
    result = retrieve(CTX, workdir=tmp_path)
    exported = [call[1] for call in fake_pc.calls if call[0] == "results" and call[1].startswith("s_")]
    assert exported == result.search_ids == ["s_403f175a", "s_72ddd280"]


def test_search_ids_are_retained_for_map_from(fake_pc, tmp_path):
    result = retrieve(CTX, workdir=tmp_path)
    assert all(doc.search_id in result.search_ids for doc in result.documents)


def test_respects_the_ten_document_cap(monkeypatch, tmp_path):
    rows = {
        "s_403f175a": [
            {"id": f"arx_{n}", "source": "arXiv", "title": f"A{n}"} for n in range(8)
        ],
        "s_72ddd280": [{"id": f"PMC{n}", "source": "PMC", "title": f"P{n}"} for n in range(8)],
    }
    monkeypatch.setattr(retrieve_module, "pc", FakePc(rows=rows))
    result = retrieve(CTX, workdir=tmp_path, limit=99)
    assert len(result.doc_ids) == MAX_DOCS
    # round-robin keeps both disciplines alive when the cap bites
    assert len(result.sources) == 2


def test_deduplicates_documents_returned_by_both_legs(monkeypatch, tmp_path):
    shared = {"id": "arx_2103.16685", "source": "arXiv", "title": "Shared"}
    rows = {
        "s_403f175a": [shared, {"id": "arx_2410.00946", "source": "arXiv", "title": "B"}],
        "s_72ddd280": [shared, {"id": "PMC6925691", "source": "PMC", "title": "C"}],
    }
    monkeypatch.setattr(retrieve_module, "pc", FakePc(rows=rows))
    doc_ids = retrieve(CTX, workdir=tmp_path).doc_ids
    assert doc_ids.count("arx_2103.16685") == 1
    assert len(doc_ids) == 3


def test_one_empty_leg_is_tolerated(monkeypatch, tmp_path):
    rows = {
        "s_72ddd280": [{"id": f"PMC{n}", "source": "PMC", "title": f"P{n}"} for n in range(3)]
    }
    fake = FakePc(stdouts=["No papers found.\n", PMC_STDOUT], rows=rows)
    monkeypatch.setattr(retrieve_module, "pc", fake)
    result = retrieve(CTX, workdir=tmp_path)
    assert result.search_ids == ["s_72ddd280"]
    assert len(result.doc_ids) == 3


def test_too_few_documents_raises(monkeypatch, tmp_path):
    rows = {"s_403f175a": [], "s_72ddd280": []}
    monkeypatch.setattr(retrieve_module, "pc", FakePc(rows=rows))
    with pytest.raises(RetrievalError, match="at least"):
        retrieve(CTX, workdir=tmp_path)


def test_single_source_result_is_flagged(monkeypatch, tmp_path, capsys):
    rows = {
        "s_403f175a": [
            {"id": f"arx_{n}", "source": "arXiv", "title": f"A{n}"} for n in range(4)
        ],
        "s_72ddd280": [],
    }
    monkeypatch.setattr(retrieve_module, "pc", FakePc(rows=rows))
    retrieve(CTX, workdir=tmp_path)
    assert "one source" in capsys.readouterr().err


def test_find_sources_returns_plain_doc_ids(fake_pc, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    doc_ids = find_sources(CTX)
    assert isinstance(doc_ids, list)
    assert all(isinstance(doc_id, str) for doc_id in doc_ids)


def test_write_search_persists_ids_for_t4(fake_pc, tmp_path):
    result = retrieve(CTX, workdir=tmp_path)
    path = write_search(result, tmp_path / "run" / "search.json")
    written = path.read_text(encoding="utf-8")
    assert "s_403f175a" in written
    assert "arx_2103.16685" in written


def test_source_leg_is_classified_and_recorded(fake_pc, tmp_path):
    result = retrieve(CTX, workdir=tmp_path)
    assert result.source_leg_check is not None
    assert result.source_leg_check.in_discipline == 2
    assert result.source_leg_check.generic == 0
    assert result.source_leg_check.below_floor is False
    arxiv = [doc for doc in result.documents if doc.search_id == "s_403f175a"]
    assert all(doc.discipline_label == "in_discipline" for doc in arxiv)
    assert any(call[0] == "map" for call in fake_pc.calls)


def test_generic_majority_warns_loudly(monkeypatch, tmp_path, capsys):
    fake = FakePc(labels="generic")
    monkeypatch.setattr(retrieve_module, "pc", fake)
    result = retrieve(CTX, workdir=tmp_path)
    err = capsys.readouterr().err
    assert "below half" in err
    assert "not field evidence" in err
    assert result.source_leg_check is not None
    assert result.source_leg_check.below_floor is True
    assert result.source_leg_check.in_discipline / (
        result.source_leg_check.in_discipline + result.source_leg_check.generic
    ) < IN_DISCIPLINE_FLOOR


def test_even_split_does_not_warn(monkeypatch, tmp_path, capsys):
    fake = FakePc(
        labels={"arx_2103.16685": "in_discipline", "arx_2410.00946": "generic"}
    )
    monkeypatch.setattr(retrieve_module, "pc", fake)
    result = retrieve(CTX, workdir=tmp_path)
    err = capsys.readouterr().err
    assert "below half" not in err
    assert result.source_leg_check is not None
    assert result.source_leg_check.below_floor is False
    assert result.source_leg_check.in_discipline == 1
    assert result.source_leg_check.generic == 1


@pytest.mark.integration
def test_live_retrieval_spans_disciplines(tmp_path):
    result = retrieve(CTX, source_discipline="neuroimaging", workdir=tmp_path)
    assert 3 <= len(result.doc_ids) <= MAX_DOCS
    assert len(result.sources) >= 2, f"single-source result: {result.sources}"
    assert all(len(doc_id) > 6 for doc_id in result.doc_ids)


@pytest.mark.integration
def test_live_search_ids_are_usable_by_map_from(tmp_path):
    result = retrieve(CTX, workdir=tmp_path)
    assert result.search_ids
    assert all(search_id.startswith("s_") for search_id in result.search_ids)
