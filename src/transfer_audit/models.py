"""T1 — the data contract.

Everything else in the pipeline is built against these two models. `LedgerEntry`
doubles as the JSON Schema handed to `paperclip map --output-schema`, so its
shape has to stay strict: extra keys are rejected rather than silently absorbed.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, model_validator

REPO_ROOT = Path(__file__).resolve().parents[2]
SCHEMA_PATH = REPO_ROOT / "data" / "schema" / "ledger_entry.json"

MIN_RESOLUTION_CHARS = 20

Axis = Literal[
    "A_isolation",
    "B_legitimacy",
    "C_domain_of_validity",
    "D_metric_alignment",
    "E_evidence_quality",
]
Subtype = Literal["A1", "A2", "A3", "A4", "C1", "C2", "C3"]
Status = Literal["SATISFIED", "VIOLATED", "UNKNOWN", "NA"]


class TransferContext(BaseModel):
    """The target-side description a claim is being transferred into."""

    model_config = ConfigDict(extra="forbid")

    target_claim: str
    target_system: str
    state_variable: str | None = None
    perturbation: str | None = None
    readout: str | None = None
    constraints: list[str] = []
    source_discipline_hint: str | None = None


class LedgerEntry(BaseModel):
    """One audited validity condition of the source result."""

    model_config = ConfigDict(extra="forbid")

    axis: Axis
    subtype: Subtype | None = None
    status: Status
    source_assumption: str
    target_restatement: str | None = None
    rationale: str
    evidence_lines: str | None = None
    what_would_resolve_it: str | None = None
    source_doc_id: str

    @model_validator(mode="after")
    def _unknown_requires_resolution(self) -> LedgerEntry:
        """The anti-gaming rule: UNKNOWN is only a success state if it says what would settle it."""
        if self.status != "UNKNOWN":
            return self
        resolution = (self.what_would_resolve_it or "").strip()
        if len(resolution) < MIN_RESOLUTION_CHARS:
            raise ValueError(
                "status='UNKNOWN' requires what_would_resolve_it of at least "
                f"{MIN_RESOLUTION_CHARS} characters describing the specific check, "
                "measurement, or record that would settle it"
            )
        return self


def emit_schema(path: Path = SCHEMA_PATH) -> Path:
    """Write the generated JSON Schema for LedgerEntry to disk. Never hand-edit the output."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(LedgerEntry.model_json_schema(), indent=2) + "\n",
        encoding="utf-8",
    )
    return path


if __name__ == "__main__":
    print(emit_schema())
