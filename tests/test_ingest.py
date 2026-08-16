import json
from pathlib import Path

import pytest

from transfer_audit.ingest import (
    DEFAULT_MODEL,
    IngestError,
    build_context,
    build_context_from_file,
    build_context_offline,
    write_context,
)
from transfer_audit.models import TransferContext

FIXTURE = Path(__file__).parent / "fixtures" / "target_claim.txt"


class _Block:
    def __init__(self, text: str):
        self.text = text


class _Response:
    def __init__(self, text: str):
        self.content = [_Block(text)]


class FakeClient:
    """Stands in for anthropic.Anthropic so unit tests need no network or credits."""

    def __init__(self, reply: str):
        self.reply = reply
        self.calls: list[dict] = []
        self.messages = self

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return _Response(self.reply)


VALID_REPLY = json.dumps(
    {
        "target_claim": "the same connectivity-based approach should predict sepsis",
        "target_system": "ICU patients",
        "state_variable": "sepsis onset",
        "perturbation": None,
        "readout": "continuous vital-sign monitoring streams",
        "constraints": [],
        "source_discipline_hint": "neuroimaging",
    }
)


# --- build_context(), the live seam, exercised with a stub client -------------------


def test_parses_model_json_into_context():
    ctx = build_context("some claim", client=FakeClient(VALID_REPLY))
    assert ctx.target_system == "ICU patients"
    assert ctx.state_variable == "sepsis onset"
    assert ctx.perturbation is None


def test_sends_the_generated_schema_and_the_claim():
    client = FakeClient(VALID_REPLY)
    build_context("A claim about ICU patients.", client=client)
    sent = client.calls[0]
    assert sent["model"] == DEFAULT_MODEL
    assert sent["messages"][0]["content"] == "A claim about ICU patients."
    assert "target_system" in sent["system"]
    assert "Inventing a slot is WORSE" in sent["system"]


def test_makes_exactly_one_call_no_retry_loop():
    client = FakeClient(VALID_REPLY)
    build_context("some claim", client=client)
    assert len(client.calls) == 1


def test_accepts_json_wrapped_in_markdown_fences():
    ctx = build_context("some claim", client=FakeClient(f"```json\n{VALID_REPLY}\n```"))
    assert ctx.target_system == "ICU patients"


def test_null_constraints_become_empty_list():
    reply = json.dumps(
        {"target_claim": "c", "target_system": "s", "constraints": None}
    )
    assert build_context("some claim", client=FakeClient(reply)).constraints == []


def test_non_json_reply_is_rejected():
    with pytest.raises(IngestError, match="did not return JSON"):
        build_context("some claim", client=FakeClient("Here are the slots you asked for!"))


def test_extra_field_from_model_is_rejected():
    """TransferContext forbids extras, so a hallucinated key fails loudly."""
    reply = json.dumps({"target_claim": "c", "target_system": "s", "confidence": 0.9})
    with pytest.raises(IngestError, match="not a TransferContext"):
        build_context("some claim", client=FakeClient(reply))


def test_missing_target_system_fails_loudly():
    reply = json.dumps({"target_claim": "c", "target_system": None})
    with pytest.raises(IngestError, match="does not name a target system"):
        build_context("some claim", client=FakeClient(reply))


def test_operator_target_system_overrides_the_model():
    ctx = build_context(
        "some claim",
        target_system="community pharmacy dispensing records",
        client=FakeClient(VALID_REPLY),
    )
    assert ctx.target_system == "community pharmacy dispensing records"


def test_empty_text_rejected_before_any_call():
    client = FakeClient(VALID_REPLY)
    with pytest.raises(IngestError, match="empty"):
        build_context("   \n  ", client=client)
    assert client.calls == []


def test_missing_api_key_explains_itself(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    with pytest.raises(IngestError, match="ANTHROPIC_API_KEY"):
        build_context("some claim")


# --- build_context_offline(), the deterministic fallback ---------------------------


def test_offline_fixture_extracts_expected_slots():
    ctx = build_context_from_file(FIXTURE, offline=True)
    assert ctx.target_system == "ICU patients"
    assert ctx.state_variable == "sepsis"
    assert ctx.readout == "continuous vital-sign monitoring streams"


def test_offline_target_claim_is_the_text_verbatim():
    ctx = build_context_from_file(FIXTURE, offline=True)
    assert ctx.target_claim == " ".join(FIXTURE.read_text().split())


def test_offline_source_result_is_the_source_half():
    ctx = build_context_from_file(FIXTURE, offline=True)
    assert ctx.source_result is not None
    assert "resting-state fMRI" in ctx.source_result
    assert "sepsis" not in ctx.source_result


def test_live_stub_fills_source_result_from_the_original_text():
    ctx = build_context(
        "Kuramoto coupling of oscillators predicts synchrony, so the same "
        "coupling should predict flowering in a meadow from temperature.",
        client=FakeClient(VALID_REPLY),
    )
    assert "Kuramoto" in (ctx.source_result or "")
    assert ctx.target_system == "ICU patients"


def test_offline_unstated_slots_are_none_not_guesses():
    ctx = build_context_from_file(FIXTURE, offline=True)
    assert ctx.perturbation is None
    assert ctx.source_discipline_hint is None
    assert ctx.constraints == []


def test_offline_missing_target_system_fails_loudly():
    with pytest.raises(IngestError, match="no target system"):
        build_context_offline("Gradient boosting beats logistic regression here.")


def test_offline_slots_come_from_the_target_half_of_the_claim():
    ctx = build_context_offline(
        "Mice will develop tumours in this assay, so the model should predict "
        "which hospital patients will develop delirium from their nursing notes."
    )
    assert ctx.target_system == "hospital patients"
    assert ctx.state_variable == "delirium"
    assert ctx.readout == "nursing notes"


def test_offline_stated_perturbation_and_discipline_are_captured():
    ctx = build_context_offline(
        "Response rates rose after treatment with metformin in the endocrinology "
        "literature, so the same effect should appear in dialysis patients, "
        "limited to adults over 65."
    )
    assert ctx.perturbation == "metformin"
    assert ctx.source_discipline_hint == "endocrinology"
    assert ctx.constraints == ["limited to adults over 65"]


# --- shared plumbing ---------------------------------------------------------------


def test_writes_valid_context_json(tmp_path):
    ctx = build_context_from_file(FIXTURE, offline=True)
    out = write_context(ctx, tmp_path / "run" / "context.json")
    assert TransferContext.model_validate_json(out.read_text()) == ctx


@pytest.mark.integration
def test_live_extraction_on_the_fixture():
    ctx = build_context_from_file(FIXTURE)
    assert ctx.target_system
    assert ctx.target_claim
