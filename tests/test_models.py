import pytest
from pydantic import ValidationError

from transfer_audit.models import LedgerEntry, TransferContext

VALID_ENTRY = {
    "axis": "C_domain_of_validity",
    "subtype": "C2",
    "status": "VIOLATED",
    "source_assumption": "Samples are independent across the train/test split.",
    "target_restatement": "ICU stays from the same patient appear in both splits.",
    "rationale": "Repeated admissions share a patient identifier, so the split is not independent.",
    "evidence_lines": "L112-L119",
    "source_doc_id": "arx_2207.07048",
}


def test_valid_entry_parses():
    entry = LedgerEntry(**VALID_ENTRY)
    assert entry.axis == "C_domain_of_validity"
    assert entry.status == "VIOLATED"
    assert entry.source_doc_id == "arx_2207.07048"


def test_extra_field_is_rejected():
    with pytest.raises(ValidationError) as exc:
        LedgerEntry(**VALID_ENTRY, confidence=0.9)
    assert "confidence" in str(exc.value)


@pytest.mark.parametrize("resolution", [None, "", "   ", "too short"])
def test_unknown_without_resolution_is_rejected(resolution):
    payload = {
        **VALID_ENTRY,
        "status": "UNKNOWN",
        "what_would_resolve_it": resolution,
    }
    with pytest.raises(ValidationError) as exc:
        LedgerEntry(**payload)
    assert "what_would_resolve_it" in str(exc.value)


def test_unknown_with_specific_resolution_parses():
    entry = LedgerEntry(
        **{
            **VALID_ENTRY,
            "status": "UNKNOWN",
            "what_would_resolve_it": (
                "Check whether the cohort table lists one row per patient or per admission."
            ),
        }
    )
    assert entry.status == "UNKNOWN"


def test_transfer_context_rejects_extra_field():
    with pytest.raises(ValidationError) as exc:
        TransferContext(
            target_claim="Connectivity features predict sepsis onset.",
            target_system="ICU vital-sign monitoring",
            confidence=0.9,
        )
    assert "confidence" in str(exc.value)


def test_minimal_transfer_context_parses():
    ctx = TransferContext(
        target_claim="Connectivity features predict sepsis onset.",
        target_system="ICU vital-sign monitoring",
    )
    assert ctx.state_variable is None
    assert ctx.perturbation is None
    assert ctx.readout is None
    assert ctx.constraints == []
    assert ctx.source_discipline_hint is None
    assert ctx.source_result is None
    assert ctx.failure_mode is None
    assert ctx.isolation_unit is None
