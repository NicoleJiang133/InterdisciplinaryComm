from pathlib import Path

import pytest

from transfer_audit.ingest import (
    IngestError,
    build_context,
    build_context_from_file,
    write_context,
)
from transfer_audit.models import TransferContext

FIXTURE = Path(__file__).parent / "fixtures" / "target_claim.txt"


def test_fixture_extracts_expected_slots():
    ctx = build_context_from_file(FIXTURE)
    assert ctx.target_system == "ICU patients"
    assert ctx.state_variable == "sepsis"
    assert ctx.readout == "continuous vital-sign monitoring streams"


def test_target_claim_is_the_text_verbatim():
    ctx = build_context_from_file(FIXTURE)
    assert ctx.target_claim == " ".join(FIXTURE.read_text().split())


def test_unstated_slots_are_none_not_guesses():
    """The fixture names no intervention and no source discipline. Neither may be invented."""
    ctx = build_context_from_file(FIXTURE)
    assert ctx.perturbation is None
    assert ctx.source_discipline_hint is None
    assert ctx.constraints == []


def test_writes_valid_context_json(tmp_path):
    ctx = build_context_from_file(FIXTURE)
    out = write_context(ctx, tmp_path / "run" / "context.json")
    assert out.exists()
    assert TransferContext.model_validate_json(out.read_text()) == ctx


def test_missing_target_system_fails_loudly():
    with pytest.raises(IngestError, match="no target system"):
        build_context("Gradient boosting beats logistic regression on this benchmark.")


def test_operator_can_supply_target_system():
    ctx = build_context(
        "Gradient boosting beats logistic regression on this benchmark.",
        target_system="community pharmacy dispensing records",
    )
    assert ctx.target_system == "community pharmacy dispensing records"
    assert ctx.state_variable is None


def test_empty_text_rejected():
    with pytest.raises(IngestError, match="empty"):
        build_context("   \n  ")


def test_stated_perturbation_and_discipline_are_captured():
    ctx = build_context(
        "Response rates rose after treatment with metformin in the endocrinology "
        "literature, so the same effect should appear in dialysis patients, "
        "limited to adults over 65."
    )
    assert ctx.target_system == "dialysis patients"
    assert ctx.perturbation == "metformin"
    assert ctx.source_discipline_hint == "endocrinology"
    assert ctx.constraints == ["limited to adults over 65"]


def test_slots_come_from_the_target_half_of_the_claim():
    """State variable must be read after the transfer marker, not from the source result."""
    ctx = build_context(
        "Mice will develop tumours in this assay, so the model should predict "
        "which hospital patients will develop delirium from their nursing notes."
    )
    assert ctx.target_system == "hospital patients"
    assert ctx.state_variable == "delirium"
    assert ctx.readout == "their nursing notes" or ctx.readout == "nursing notes"
