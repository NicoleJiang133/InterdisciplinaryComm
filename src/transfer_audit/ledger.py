"""T4 — source documents -> LedgerEntry[].

One `paperclip map` per search leg, one entry per paper, no retry loop: Paperclip
already gives each paper a single correction attempt against the output schema, and
BUILD.md puts self-correction out of scope.

Three CLI facts from NOTES.md section 4 are load-bearing here:
  * `--output-schema` takes the schema file's CONTENTS inline, never a path.
  * `--json` must never be passed to map — it gets swallowed into the query string.
  * doc ids on stdout are truncated, so results are read from `results <m_id> --save`.

And one model fact: the map worker fills `source_doc_id` with the paper TITLE. Every
entry's id is overwritten with the id the search step already knows, because a ledger
whose provenance points at a title is a ledger nobody can check.
"""

from __future__ import annotations

import json
import re
import sys
import tempfile
from pathlib import Path

from pydantic import BaseModel, ValidationError

from transfer_audit.models import SCHEMA_PATH, LedgerEntry, TransferContext, emit_schema
from transfer_audit.pc import pc

MAP_TIMEOUT = 600
# The only worker this account may use: every other value is gated server-side with
# "Parallel map workers are currently limited to GXL testers" (NOTES.md section 13).
WORKER = "quick-reader"

_MAP_ID = re.compile(r"\bm_[0-9a-f]{6,}\b")
_BLOCK = re.compile(r"^---\s*\[\d+\]\s*\[(?P<state>\w+)\]\s*(?P<title>.*?)\s*---\s*$")
_DOC_ID = re.compile(r"^doc_id:\s*(?P<doc_id>\S+)\s*$")

_QUERY = """\
Read this paper's METHODS and audit ONE condition that ITS OWN result rests on — a \
requirement its design quietly needs in order for its headline finding to mean what it \
says. Then state what the ANALOGOUS condition would demand of the target setting below.

TARGET CLAIM: {target_claim}
TARGET SYSTEM: {target_system}
STATE VARIABLE: {state_variable}
READOUT: {readout}
PERTURBATION: {perturbation}
CONSTRAINTS: {constraints}

DO NOT report that this paper studies a different subject, population, or data modality \
than the target. That is already known and is not an audit finding. "This paper is about \
brain images and the target is about vital signs" is a failed answer. The useful finding \
is the methodological condition the paper depended on, which the target will also have \
to satisfy in its own terms.

Work down this list and stop at the FIRST axis for which this paper's methods give you \
concrete evidence. C is last on purpose: it is the easy answer and it is usually the \
least informative one, so reach for it only when A, B, D and E genuinely have nothing.
  A_isolation — what was held out, and did anything cross that boundary? How were train, \
validation and test split; was scaling, imputation or feature selection fitted before \
the split; can one subject, admission or site appear on both sides? A1 no independent \
test set, A2 preprocessing crossed the boundary, A3 feature selection crossed it, A4 \
duplicate entities across groups.
  B_legitimacy — is any input recorded because of, or after, the outcome it predicts \
(treatments started, orders placed, labels derived from a downstream action), or simply \
not available at the moment the prediction has to be made?
  D_metric_alignment — what did it optimise and report, and is that the same thing the \
target needs? Discrimination on a balanced sample versus early warning at a tolerable \
false alarm rate is a mismatch.
  E_evidence_quality — missingness and how it was handled, sample size against number of \
predictors, or an outcome definition that is a proxy for the thing of interest.
  C_domain_of_validity — LAST RESORT. Use only for a distribution restriction the paper \
itself documents: its stated inclusion criteria, its single site, its recruitment \
window, its repeated measures. C1 temporal direction, C2 dependence structure, C3 \
representativeness.

STATUS IS ABOUT THE TARGET, NOT ABOUT THIS PAPER. You are not grading this paper. You \
are judging whether the TARGET described above can satisfy the analogous condition, \
using only what the target description actually says. The target description is the \
handful of lines above and nothing else.

  SATISFIED — only when the target description positively states the condition is met. \
Say in the rationale which part of the target description states it.
  VIOLATED — only when the target description positively shows the condition fails. \
That this paper studies a different subject, population or data modality is NOT \
evidence of failure. Do not infer failure from distance between the two domains.
  UNKNOWN — the expected answer, and a SUCCESS state when it carries a real question. \
The target is a short claim that is usually silent about method, so most conditions \
cannot be judged from it. Prefer UNKNOWN to a guess in either direction.
  NA — the axis genuinely cannot apply to this transfer.

A ledger in which every entry is SATISFIED, or every entry is VIOLATED, is a FAILED \
audit: it means status was decided by framing rather than by evidence.

what_would_resolve_it is REQUIRED when status is UNKNOWN, at least 20 characters. Write \
the single question a reviewer would actually put to the team — answerable by pointing \
at a protocol, a split definition, a table, or a number. "More information is needed" \
and "further validation is required" are failed answers. A good one reads like: "Are \
the train and test splits made by patient admission, so that no ICU stay contributes \
windows to both sides?"

source_assumption: what THIS paper assumes, in its own terms. A sentence that would be \
true of any paper in the field is a failed answer — cite its cohort, its split, its \
preprocessing, its instrument, or its metric.
target_restatement: what the analogous condition would demand of {target_system}.
evidence_lines: line numbers or the section of THIS paper you read the assumption from.
source_doc_id: this paper's document id.\
"""


class LedgerError(RuntimeError):
    """The map step produced nothing usable."""


class Drop(BaseModel):
    doc_id: str
    reason: str


class LedgerRun(BaseModel):
    entries: list[LedgerEntry]
    drops: list[Drop]
    map_ids: list[str]

    @property
    def axes(self) -> set[str]:
        return {entry.axis for entry in self.entries}


def _slot(value: str | None) -> str:
    return value if value else "not stated"


def build_query(ctx: TransferContext) -> str:
    return _QUERY.format(
        target_claim=ctx.target_claim,
        target_system=ctx.target_system,
        state_variable=_slot(ctx.state_variable),
        readout=_slot(ctx.readout),
        perturbation=_slot(ctx.perturbation),
        constraints="; ".join(ctx.constraints) if ctx.constraints else "none stated",
    )


def load_schema_text(path: Path = SCHEMA_PATH) -> str:
    """The CONTENTS of the generated schema. Passing the path makes map fail."""
    path = Path(path)
    if not path.exists():
        emit_schema(path)
    return path.read_text(encoding="utf-8")


def _parse_map_id(stdout: str) -> str | None:
    found = _MAP_ID.search(stdout)
    return found.group(0) if found else None


def _parse_blocks(text: str) -> list[tuple[str, str]]:
    """(doc_id, payload) per paper from a `results --save` export."""
    blocks: list[tuple[str, list[str]]] = []
    doc_id = ""
    for line in text.splitlines():
        header = _BLOCK.match(line)
        if header:
            doc_id = ""
            blocks.append(("", []))
            continue
        if not blocks:
            continue
        found = _DOC_ID.match(line)
        if found:
            doc_id = found.group("doc_id")
            blocks[-1] = (doc_id, blocks[-1][1])
            continue
        blocks[-1][1].append(line)
    return [(doc, "\n".join(lines).strip()) for doc, lines in blocks]


def _payload_json(payload: str) -> dict | None:
    start, end = payload.find("{"), payload.rfind("}")
    if start == -1 or end <= start:
        return None
    try:
        parsed = json.loads(payload[start : end + 1])
    except ValueError:
        return None
    return parsed if isinstance(parsed, dict) else None


def run_map(
    ctx: TransferContext,
    doc_ids: list[str],
    search_ids: list[str],
    *,
    worker: str = WORKER,
    workdir: Path | None = None,
) -> LedgerRun:
    """Map every search leg, validate each paper's answer, drop what does not parse."""
    if not search_ids:
        raise LedgerError("no search ids; run retrieve() first — map needs --from <s_id>")

    workdir = Path(workdir) if workdir else Path(tempfile.mkdtemp(prefix="transfer-audit-"))
    workdir.mkdir(parents=True, exist_ok=True)
    schema_text = load_schema_text()
    query = build_query(ctx)
    allowed = set(doc_ids)

    entries: list[LedgerEntry] = []
    drops: list[Drop] = []
    map_ids: list[str] = []
    seen: set[str] = set()

    for search_id in search_ids:
        stdout = pc(
            "map",
            "--worker",
            worker,
            "--from",
            search_id,
            "--output-schema",
            schema_text,
            query,
            timeout=MAP_TIMEOUT,
        )
        map_id = _parse_map_id(stdout)
        if not map_id:
            drops.append(Drop(doc_id=search_id, reason="map returned no results id"))
            continue
        map_ids.append(map_id)

        export = workdir / f"{map_id}.txt"
        pc("results", map_id, "--save", str(export))
        if not export.exists():
            drops.append(Drop(doc_id=map_id, reason="results --save wrote nothing"))
            continue

        for doc_id, payload in _parse_blocks(export.read_text(encoding="utf-8")):
            if not doc_id or doc_id in seen:
                continue
            if allowed and doc_id not in allowed:
                continue  # trimmed by the T3 dedupe or cap; not an error
            seen.add(doc_id)

            parsed = _payload_json(payload)
            if parsed is None:
                drops.append(Drop(doc_id=doc_id, reason="no JSON object in map output"))
                continue
            # The worker writes the paper's title here. Provenance is demo-critical.
            parsed["source_doc_id"] = doc_id
            try:
                entries.append(LedgerEntry.model_validate(parsed))
            except ValidationError as exc:
                drops.append(Drop(doc_id=doc_id, reason=_first_error(exc)))

    print(f"ledger: {len(entries)} valid entries, {len(drops)} dropped", file=sys.stderr)
    for drop in drops:
        print(f"  dropped {drop.doc_id}: {drop.reason}", file=sys.stderr)
    return LedgerRun(entries=entries, drops=drops, map_ids=map_ids)


def _first_error(exc: ValidationError) -> str:
    error = exc.errors()[0]
    location = ".".join(str(part) for part in error["loc"]) or "entry"
    return f"{location}: {error['msg']}"


def build_ledger(
    ctx: TransferContext,
    doc_ids: list[str],
    search_ids: list[str],
) -> list[LedgerEntry]:
    """BUILD.md T4 entry point. Use run_map() when you also need drops and map ids."""
    return run_map(ctx, doc_ids, search_ids).entries


def write_ledger(entries: list[LedgerEntry], path: Path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = [json.loads(entry.model_dump_json()) for entry in entries]
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return path


if __name__ == "__main__":
    from transfer_audit.ingest import build_context_from_file
    from transfer_audit.retrieve import retrieve

    claim_file = Path(sys.argv[1] if len(sys.argv) > 1 else "tests/fixtures/target_claim.txt")
    context = build_context_from_file(claim_file)
    found = retrieve(context)
    run = run_map(context, found.doc_ids, found.search_ids)
    print(json.dumps([json.loads(e.model_dump_json()) for e in run.entries], indent=2))
