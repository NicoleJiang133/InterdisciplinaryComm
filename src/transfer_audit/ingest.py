"""T2 — target description -> TransferContext.

Every value this module produces is a verbatim span of the input text. Nothing is
inferred, normalised into jargon, or filled from background knowledge: a slot whose
pattern does not match becomes None, which is the specified behaviour and the honest
one. A wrong slot silently mis-frames every downstream question in the ledger.

Why there is no LLM call here: BUILD.md asks for one Paperclip call that fills the
slots, and the CLI cannot do it. `generate-search-config` (the only command that reads
arbitrary text) is disabled server-side; `map`/`filter`/`reduce` only accept corpus
search-result sets; and text uploaded to /clipboard/ is searchable but map refuses it
with "has no loadable full text". All three probes are recorded in NOTES.md section 8.
If an extraction model becomes available, `build_context` is the single seam to change.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from transfer_audit.models import TransferContext


class IngestError(ValueError):
    """The text does not state something the ledger cannot be built without."""


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


def _first_match(patterns, text: str) -> str | None:
    for pattern in patterns:
        found = pattern.search(text)
        if found:
            return found.group(1).strip(" ,.;")
    return None


def _search(pattern: re.Pattern[str], text: str) -> str | None:
    found = pattern.search(text)
    return found.group(1).strip(" ,.;") if found else None


def build_context(text: str, *, target_system: str | None = None) -> TransferContext:
    """Fill the TransferContext slots from a free-text target description.

    Unmatched slots are None. `target_system` may be supplied by the operator when the
    text does not name one; without it, ingest fails loudly rather than inventing one.
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
    )


def build_context_from_file(path: Path, **kwargs) -> TransferContext:
    return build_context(Path(path).read_text(encoding="utf-8"), **kwargs)


def write_context(ctx: TransferContext, path: Path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(ctx.model_dump_json(indent=2) + "\n", encoding="utf-8")
    return path


if __name__ == "__main__":
    import sys

    source = Path(sys.argv[1] if len(sys.argv) > 1 else "tests/fixtures/target_claim.txt")
    print(build_context_from_file(source).model_dump_json(indent=2))
