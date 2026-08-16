from __future__ import annotations

import json
from pathlib import Path

from transfer_audit.align import (
    MIN_EXTRACTION_QUALITY,
    PaperSlots,
    format_break_points,
    judge_slot,
    score_alignment,
    score_paper,
    summarise_break_points,
    target_slots,
    write_alignment,
)
from transfer_audit.models import TransferContext
from transfer_audit.retrieve import Retrieval, SourceDoc

CTX = TransferContext(
    target_claim="connectivity should predict sepsis in ICU patients from vital signs",
    target_system="ICU patients",
    state_variable="development of sepsis",
    readout="continuous vital-sign monitoring streams",
    source_discipline_hint="neuroimaging",
)


def _doc(doc_id: str, title: str = "A paper") -> SourceDoc:
    return SourceDoc(doc_id=doc_id, source="arXiv", title=title, search_id="s_test")


def _retrieval(*docs: SourceDoc) -> Retrieval:
    return Retrieval(
        doc_ids=[doc.doc_id for doc in docs],
        search_ids=["s_test"],
        documents=list(docs),
        queries={"arxiv": "q"},
    )


def test_target_slots_treat_empty_constraints_as_no_counterpart():
    slots = target_slots(CTX)
    assert slots["system"] == "ICU patients"
    assert slots["constraints"] is None
    assert slots["isolation_unit"] is None


def test_paper_slot_without_target_counterpart_is_unmapped():
    slot = judge_slot("isolation_unit", "subject", None)
    assert slot.judgement == "unmapped"


def test_both_sides_instantiating_a_slot_is_mapped_even_when_values_differ():
    slot = judge_slot("system", "ADNI memory-clinic cohort", "ICU patients")
    assert slot.judgement == "mapped"


def test_paper_not_instantiating_a_slot_is_absent():
    assert judge_slot("perturbation", None, None).judgement == "absent"


def test_extraction_quality_is_instantiated_slots_and_gates():
    paper = PaperSlots(
        system="ADNI",
        state_variable="AD conversion",
        readout="fMRI",
        isolation_unit="subject",
        constraints="excluded borderline cases",
    )
    scored = score_paper(_doc("arx_good"), paper, CTX)
    assert scored.extraction_quality == 5  # 3 mapped + 2 unmapped
    assert scored.break_richness == 2
    assert scored.admitted is True


def test_empty_extraction_is_held_out():
    scored = score_paper(_doc("arx_empty"), PaperSlots(), CTX)
    assert scored.extraction_quality == 0
    assert scored.break_richness == 0
    assert scored.admitted is False


def test_partial_extraction_still_passes_the_gate():
    # Two mapped slots is structure, not an extraction failure.
    scored = score_paper(
        _doc("arx_2204.07005"),
        PaperSlots(system="neuroimaging cohorts", readout="T1-weighted MRI"),
        CTX,
    )
    assert scored.extraction_quality == 2
    assert scored.break_richness == 0
    assert scored.admitted is True


def test_break_richness_does_not_gate():
    rich = PaperSlots(
        system="one site",
        state_variable="an outcome",
        readout="a signal",
        isolation_unit="subject",
        constraints="one inclusion rule",
        failure_mode="a miss",
    )
    thin = PaperSlots(system="one site", state_variable="an outcome", readout="a signal")
    rich_scored = score_paper(_doc("rich"), rich, CTX)
    thin_scored = score_paper(_doc("thin"), thin, CTX)
    assert rich_scored.break_richness > thin_scored.break_richness
    assert rich_scored.admitted is True
    assert thin_scored.admitted is True


def test_break_points_are_aggregated_not_repeated_per_paper():
    docs = (
        _doc("a", "A"),
        _doc("b", "B"),
        _doc("empty", "Guide"),
    )
    extracted = {
        "a": PaperSlots(
            system="ADNI",
            state_variable="AD",
            readout="fMRI",
            isolation_unit="subject",
            constraints="age > 50",
        ),
        "b": PaperSlots(
            system="ICU",
            state_variable="sepsis",
            readout="vitals",
            isolation_unit="admission",
        ),
        "empty": PaperSlots(),
    }
    report = score_alignment(CTX, _retrieval(*docs), extracted=extracted)
    assert report.admitted_ids == ["a", "b"]
    assert report.held_out_ids == ["empty"]
    by_slot = {row.slot: row for row in report.break_points}
    assert list(by_slot)[0] == "isolation_unit"  # 2/2, ranked first
    assert by_slot["isolation_unit"].papers_stating == 2
    assert by_slot["isolation_unit"].extracted == 2
    assert by_slot["isolation_unit"].target_states_it is False
    assert by_slot["constraints"].papers_stating == 1
    assert "failure_mode" not in by_slot
    table = format_break_points(report.break_points)
    assert table.count("isolation_unit") == 1


def test_write_alignment_includes_break_points(tmp_path):
    extracted = {
        "arx_good": PaperSlots(
            system="ADNI", state_variable="AD", readout="fMRI", isolation_unit="subject"
        ),
    }
    report = score_alignment(CTX, _retrieval(_doc("arx_good")), extracted=extracted)
    written = json.loads(write_alignment(report, tmp_path / "alignment.json").read_text())
    assert written["break_points"][0]["slot"] == "isolation_unit"
    assert written["min_extraction_quality"] == MIN_EXTRACTION_QUALITY


def test_target_protocol_clears_break_points():
    ctx = CTX.model_copy(
        update={
            "isolation_unit": "admission",
            "failure_mode": "missed sepsis onset",
            "constraints": ["LOS >= 12 hours"],
        }
    )
    scored = score_paper(
        _doc("arx_good"),
        PaperSlots(
            system="ADNI",
            state_variable="AD",
            readout="fMRI",
            isolation_unit="subject",
            failure_mode="missed converter",
            constraints="excluded borderline cases",
        ),
        ctx,
    )
    assert scored.break_richness == 0
    assert summarise_break_points([scored], ctx) == []


def test_extract_prompt_defines_slots_by_role_not_ml_ontology():
    from transfer_audit.align import _EXTRACT_QUERY

    query = _EXTRACT_QUERY.lower()
    assert "each slot is a role" in query
    assert "unit across which independence is assumed" in query
    assert "control parameter" in query
    # ML remains an example, not the definition
    assert "train/test" in query
    assert "ensemble of oscillators" in query
    assert "forager" in query
