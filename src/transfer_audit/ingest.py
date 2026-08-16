"""T2 — target description -> TransferContext.

`build_context()` is the single seam every caller uses. It sends the claim to the
Anthropic API, because Paperclip's `map` reads PAPERS and cannot read our text at all
(NOTES.md section 0). This is the only module allowed to touch a non-Paperclip model.

The extraction rule that matters: a slot the text does not state must come back null.
An invented slot is worse than a missing one, because T3 queries the corpus by slot and
T4 audits assumptions against them — one hallucinated readout mis-frames every question
in the ledger, silently and plausibly.

`build_context_offline()` is a deterministic fallback that extracts only verbatim spans
by pattern. The unit tests run against it so the suite needs no network and no credits.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

from transfer_audit.models import TransferContext

DEFAULT_MODEL = "claude-sonnet-5"
MAX_TOKENS = 2000
# No temperature knob: claude-sonnet-5 rejects the parameter outright with
# "400 `temperature` is deprecated for this model" (NOTES.md section 12). Run-to-run
# stability has to come from the operator override, not from sampling settings.

_SYSTEM_PROMPT = """\
You extract structured slots from a scientific claim that someone is transferring from \
the discipline where it was established into a new target system.

Return ONLY a single JSON object matching this schema. No prose, no markdown fences.

{schema}

Field meanings:
- target_claim: the claim being made about the TARGET system, quoted from the input.
- target_system: the system, population, cohort or setting the claim is applied TO.
- state_variable: the variable whose state is predicted, classified or measured.
- perturbation: the intervention, treatment or manipulation applied, if any.
- readout: the measurement, signal or data source used to evaluate the claim.
- constraints: stated limits, thresholds, exclusions or eligibility conditions.
- source_discipline_hint: the NAME of the field or literature the claim is borrowed \
FROM, a few words at most, such as "neuroimaging" or "labour economics". A description \
of the source study, its method or its result is NOT a discipline name — if the input \
does not name a field, this is null.
- failure_mode: how the target system fails, if the input states it (a missed \
onset, a false alarm, a wrong conversion). Do not copy state_variable here.
- isolation_unit: the unit that must not cross a train/test boundary, if the \
input states it (patient, admission, site, scan). A short claim almost never does.

Rules:
- Use null for any slot the input does not state. Use [] for empty constraints.
- Inventing a slot is WORSE than leaving it null. Do not infer a value from background \
knowledge, do not guess from context, and do not restate one slot inside another to \
avoid a null. A null is a correct and expected answer.
- Prefer the input's own wording over your paraphrase.
- target_claim and target_system are the only required fields. If the input genuinely \
does not name a target system, return null for it and the caller will handle it.\
"""


class IngestError(ValueError):
    """The text could not be turned into a usable TransferContext."""


# A transfer claim has two halves joined by an inference marker: the source result,
# then the assertion about the new system. Only the second half describes the target.
_TRANSFER_MARKER = re.compile(
    r"\b(?:so|therefore|hence|thus|which suggests(?: that)?|it follows that|"
    r"the same (?:approach|method|model|technique) should)\b",
    re.IGNORECASE,
)

# Head nouns that denote a system, population, or setting rather than an outcome.
_SYSTEM_HEAD = (
    r"(?:patients|subjects|participants|individuals|people|users|customers|"
    r"population|populations|cohort|cohorts|cells|neurons|tissues|samples|"
    r"isolates|strains|sites|regions|hospitals|clinics|units|wards|schools|"
    r"firms|markets|images|datasets|genomes|sequences|trials|admissions)"
)

_TARGET_SYSTEM_PATTERNS = (
    re.compile(rf"\bwhich ((?:[A-Za-z0-9\-]+[ ]){{0,4}}?{_SYSTEM_HEAD})\b"),
    re.compile(rf"\bwhether ((?:[A-Za-z0-9\-]+[ ]){{0,4}}?{_SYSTEM_HEAD})\b"),
    re.compile(rf"\b(?:in|for|among|across|on) ((?:[A-Za-z0-9\-]+[ ]){{0,4}}?{_SYSTEM_HEAD})\b"),
)

# "...will develop sepsis", "...will experience relapse". Stops before the readout.
_STATE_VARIABLE_PATTERN = re.compile(
    r"\bwill (?:develop|experience|show|exhibit|have|reach|progress to|convert to) "
    r"(.+?)(?=\s+from\b|\s+using\b|\s+based on\b|\s+measured\b|\s+within\b|[,.;]|$)",
    re.IGNORECASE,
)

_READOUT_PATTERN = re.compile(
    r"\b(?:from|using|based on|measured by|measured with|scored by|read out (?:by|from)|via) "
    r"(?:their|its|his|her|the|a|an)?\s*"
    r"(.+?)(?=\s+(?:in|for|among|across|at|so|therefore|hence|thus|which|while|during|"
    r"when|because)\b|[,.;]|$)",
    re.IGNORECASE,
)

# A captured span ends at the next preposition or connective, otherwise the rest of the
# sentence gets swallowed into a slot that is supposed to hold one thing.
_PHRASE_END = (
    r"(?=\s+(?:in|for|among|across|on|at|from|so|therefore|hence|thus|which|while|"
    r"during|when|because)\b|[,.;]|$)"
)

# Deliberately narrow: an intervention has to be stated as one, not implied by a verb.
_PERTURBATION_PATTERN = re.compile(
    r"\b(?:after|following|under|upon|with) "
    r"(?:administering|administration of|treatment with|treating with|dosing with|"
    r"stimulation with|stimulating with|knockdown of|knockout of|ablation of|"
    r"perturbation with|exposure to|intervention of) "
    rf"(.+?){_PHRASE_END}",
    re.IGNORECASE,
)

_CONSTRAINT_PATTERN = re.compile(
    r"((?:only|excluding|limited to|restricted to|assuming|provided that|conditional on|"
    r"must be|must have|at least|at most|no more than|no fewer than|within)\b[^.;]*)",
    re.IGNORECASE,
)

_SOURCE_DISCIPLINE_PATTERN = re.compile(
    r"\b(?:borrowed from|imported from|adapted from|taken from|drawn from|"
    r"from the|in the) ([A-Za-z][A-Za-z \-]*?)\s*(?:literature|field|community|"
    r"discipline|research|studies)\b",
    re.IGNORECASE,
)


def _normalise(text: str) -> str:
    return " ".join(text.split())


def _target_clause(text: str) -> str:
    """The half of the claim that talks about the target. Falls back to the whole text."""
    markers = list(_TRANSFER_MARKER.finditer(text))
    if not markers:
        return text
    return text[markers[-1].end() :].strip()


def source_clause(text: str) -> str | None:
    """The half that states the borrowed result — the source's objects and mechanisms.

    Filled from the original text, not by the slot extractor. The extractor is
    target-sided; this clause is what the source-leg query needs to lead with.
    """
    markers = list(_TRANSFER_MARKER.finditer(text))
    if not markers:
        return None
    clause = text[: markers[-1].start()].strip(" ,.;")
    return clause or None


def _first_match(patterns, text: str) -> str | None:
    for pattern in patterns:
        found = pattern.search(text)
        if found:
            return found.group(1).strip(" ,.;")
    return None


def _search(pattern: re.Pattern[str], text: str) -> str | None:
    found = pattern.search(text)
    return found.group(1).strip(" ,.;") if found else None


def build_context(
    text: str,
    *,
    target_system: str | None = None,
    model: str = DEFAULT_MODEL,
    client: Any | None = None,
) -> TransferContext:
    """Fill the TransferContext slots from a free-text target description.

    One model call, no retry loop — Paperclip's correction pass has no equivalent here
    and BUILD.md puts self-correction loops out of scope. Slots the text does not state
    come back None. `target_system` overrides whatever the model returns, for the case
    where an operator knows the target and the text is vague.
    """
    claim = _normalise(text)
    if not claim:
        raise IngestError("empty target description")

    payload = _extract_slots(claim, model=model, client=client)

    if target_system:
        payload["target_system"] = target_system
    if not payload.get("target_claim"):
        payload["target_claim"] = claim
    if payload.get("constraints") is None:
        payload["constraints"] = []
    if not payload.get("target_system"):
        raise IngestError(
            "the text does not name a target system. State it explicitly (for example "
            "'in ICU patients') or pass target_system= to build_context()."
        )

    try:
        ctx = TransferContext.model_validate(payload)
    except Exception as exc:
        raise IngestError(f"model returned a payload that is not a TransferContext: {exc}") from exc
    # Deterministic: the source half of the original text, not a model paraphrase.
    return ctx.model_copy(update={"source_result": source_clause(claim)})


def _extract_slots(claim: str, *, model: str, client: Any | None) -> dict[str, Any]:
    """One Anthropic call. Returns the raw slot dict; validation is the caller's job."""
    if client is None:
        if not os.environ.get("ANTHROPIC_API_KEY"):
            raise IngestError(
                "ANTHROPIC_API_KEY is not set. Ingest needs it because Paperclip has no "
                "general LLM endpoint (NOTES.md section 0). Use build_context_offline() "
                "for a deterministic, lower-quality extraction without credentials."
            )
        from anthropic import Anthropic

        client = Anthropic()

    schema = json.dumps(TransferContext.model_json_schema(), indent=2)
    response = client.messages.create(
        model=model,
        max_tokens=MAX_TOKENS,
        system=_SYSTEM_PROMPT.format(schema=schema),
        messages=[{"role": "user", "content": claim}],
    )
    return _parse_json_object(_response_text(response))


def _response_text(response: Any) -> str:
    parts = [getattr(block, "text", "") for block in getattr(response, "content", [])]
    return "".join(parts).strip()


def _parse_json_object(raw: str) -> dict[str, Any]:
    text = raw.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.MULTILINE).strip()
    try:
        payload = json.loads(text)
    except ValueError as exc:
        raise IngestError(f"model did not return JSON: {raw[:300]!r}") from exc
    if not isinstance(payload, dict):
        raise IngestError(f"model returned {type(payload).__name__}, expected a JSON object")
    return payload


def build_context_offline(text: str, *, target_system: str | None = None) -> TransferContext:
    """Deterministic fallback: verbatim spans only, no model, no network.

    Lower quality than build_context() by design — it only recognises the phrasings
    encoded below and returns None for everything else. Used by the unit tests.
    """
    claim = _normalise(text)
    if not claim:
        raise IngestError("empty target description")

    clause = _target_clause(claim)

    system = target_system or _first_match(_TARGET_SYSTEM_PATTERNS, clause)
    if not system:
        raise IngestError(
            "no target system found in the text. State it explicitly (for example "
            "'in ICU patients') or pass target_system= to build_context()."
        )

    constraints = [
        _normalise(match.group(1)) for match in _CONSTRAINT_PATTERN.finditer(claim)
    ]

    return TransferContext(
        target_claim=claim,
        target_system=system,
        state_variable=_search(_STATE_VARIABLE_PATTERN, clause),
        perturbation=_search(_PERTURBATION_PATTERN, claim),
        readout=_search(_READOUT_PATTERN, clause),
        constraints=constraints,
        source_discipline_hint=_search(_SOURCE_DISCIPLINE_PATTERN, claim),
        source_result=source_clause(claim),
    )


def build_context_from_file(path: Path, *, offline: bool = False, **kwargs) -> TransferContext:
    builder = build_context_offline if offline else build_context
    return builder(Path(path).read_text(encoding="utf-8"), **kwargs)


def write_context(ctx: TransferContext, path: Path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(ctx.model_dump_json(indent=2) + "\n", encoding="utf-8")
    return path


if __name__ == "__main__":
    import sys

    args = [a for a in sys.argv[1:] if a != "--offline"]
    source = Path(args[0] if args else "tests/fixtures/target_claim.txt")
    ctx = build_context_from_file(source, offline="--offline" in sys.argv)
    print(ctx.model_dump_json(indent=2))
