from __future__ import annotations

import json
from pathlib import Path

import pytest

from transfer_audit.align import (
    MIN_MAPPED,
    PaperSlots,
    judge_slot,
    score_alignment,
    score_paper,
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
    assert slots["state_variable"] == "development of sepsis"
    assert slots["readout"] == "continuous vital-sign monitoring streams"
    assert slots["perturbation"] is None
    assert slots["constraints"] is None
    assert slots["failure_mode"] is None
    assert slots["isolation_unit"] is None


def test_paper_slot_without_target_counterpart_is_unmapped():
    slot = judge_slot("isolation_unit", "subject", None)
    assert slot.judgement == "unmapped"
    assert "no counterpart" in (slot.note or "")


def test_both_sides_instantiating_a_slot_is_mapped_even_when_values_differ():
    slot = judge_slot("system", "ADNI memory-clinic cohort", "ICU patients")
    assert slot.judgement == "mapped"
    assert slot.paper_value == "ADNI memory-clinic cohort"
    assert slot.target_value == "ICU patients"


def test_paper_not_instantiating_a_slot_is_absent():
    slot = judge_slot("perturbation", None, None)
    assert slot.judgement == "absent"


def test_prediction_paper_is_admitted_and_reports_unmapped_isolation():
    paper = PaperSlots(
        system="ADNI memory-clinic patients",
        state_variable="conversion to Alzheimer's disease",
        readout="resting-state fMRI connectivity",
        isolation_unit="subject",
        constraints="excluded borderline MCI cases",
    )
    scored = score_paper(_doc("arx_good"), paper, CTX)
    assert scored.mapped >= MIN_MAPPED
    assert scored.admitted is True
    names = {slot.slot: slot.judgement for slot in scored.slots}
    assert names["system"] == "mapped"
    assert names["state_variable"] == "mapped"
    assert names["readout"] == "mapped"
    assert names["isolation_unit"] == "unmapped"
    assert names["constraints"] == "unmapped"
    assert "isolation_unit" in [slot.slot for slot in scored.break_points]


def test_metaphor_paper_is_held_out():
    # Conceptual guide: a system and a readout, nothing else. The restatement
    # can only be a metaphor ("register the vital-sign streams").
    paper = PaperSlots(
        system="neuroimaging cohorts",
        readout="T1-weighted MRI",
    )
    scored = score_paper(_doc("arx_2204.07005"), paper, CTX)
    assert scored.mapped < MIN_MAPPED
    assert scored.admitted is False


def test_icu_paper_maps_the_shared_prediction_slots():
    paper = PaperSlots(
        system="adult ICU admissions",
        state_variable="sepsis onset",
        readout="bedside vital signs",
        isolation_unit="admission",
        failure_mode="missed sepsis onset",
    )
    scored = score_paper(_doc("PMC6925691"), paper, CTX)
    assert scored.admitted is True
    names = {slot.slot: slot.judgement for slot in scored.slots}
    assert names["system"] == "mapped"
    assert names["isolation_unit"] == "unmapped"
    assert names["failure_mode"] == "unmapped"


def test_weak_flag_when_unmapped_meets_mapped():
    paper = PaperSlots(
        system="one site",
        state_variable="an outcome",
        readout="a signal",
        isolation_unit="subject",
        constraints="one inclusion rule",
        failure_mode="a miss",
    )
    scored = score_paper(_doc("arx_weak"), paper, CTX)
    assert scored.mapped == 3
    assert scored.unmapped == 3
    assert scored.admitted is True
    assert scored.weak is True


def test_score_alignment_gates_without_calling_paperclip():
    docs = (
        _doc("arx_good", "External validation of an AD classifier"),
        _doc("arx_2204.07005", "Interpretability of ML in neuroimaging"),
    )
    extracted = {
        "arx_good": PaperSlots(
            system="ADNI",
            state_variable="AD conversion",
            readout="fMRI",
            isolation_unit="subject",
        ),
        "arx_2204.07005": PaperSlots(system="brains", readout="MRI"),
    }
    report = score_alignment(CTX, _retrieval(*docs), extracted=extracted)
    assert report.admitted_ids == ["arx_good"]
    assert report.held_out_ids == ["arx_2204.07005"]
    assert report.threshold_mapped == MIN_MAPPED


def test_write_alignment_round_trips(tmp_path):
    extracted = {
        "arx_good": PaperSlots(system="ADNI", state_variable="AD", readout="fMRI"),
    }
    report = score_alignment(CTX, _retrieval(_doc("arx_good")), extracted=extracted)
    path = write_alignment(report, tmp_path / "alignment.json")
    written = json.loads(path.read_text(encoding="utf-8"))
    assert written["admitted_ids"] == ["arx_good"]


def test_target_protocol_can_map_isolation_and_failure():
    ctx = CTX.model_copy(
        update={
            "isolation_unit": "admission",
            "failure_mode": "missed sepsis onset",
            "constraints": ["LOS >= 12 hours", "no Sepsis-3 at admission"],
        }
    )
    paper = PaperSlots(
        system="ADNI",
        state_variable="AD conversion",
        readout="fMRI",
        isolation_unit="subject",
        failure_mode="missed converter",
        constraints="excluded borderline cases",
    )
    scored = score_paper(_doc("arx_good"), paper, ctx)
    names = {slot.slot: slot.judgement for slot in scored.slots}
    assert names["isolation_unit"] == "mapped"
    assert names["failure_mode"] == "mapped"
    assert names["constraints"] == "mapped"
    assert scored.break_points == []
