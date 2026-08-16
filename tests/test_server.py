"""Local UI server. Saved replay must never be labelled live."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

pytest.importorskip("fastapi")

from transfer_audit.ingest import IngestError
from transfer_audit.server import RunRequest, pipeline


def _events(chunks) -> list[tuple[str, dict]]:
    parsed: list[tuple[str, dict]] = []
    event = "message"
    for raw in "".join(chunks).split("\n\n"):
        if not raw.strip():
            continue
        event = "message"
        data = ""
        for line in raw.split("\n"):
            if line.startswith("event:"):
                event = line.split(":", 1)[1].strip()
            if line.startswith("data:"):
                data = line.split(":", 1)[1].strip()
        if data:
            parsed.append((event, json.loads(data)))
    return parsed


def test_saved_mode_is_labelled_saved_and_emits_five_stages(tmp_path, monkeypatch):
    out = tmp_path / "20260101T000000Z"
    monkeypatch.setattr("transfer_audit.server.default_out", lambda: out)
    events = _events(pipeline(RunRequest(claim="unused", live=False)))
    kinds = [name for name, _ in events]
    assert kinds[0] == "start"
    assert events[0][1]["mode"] == "saved"
    assert "not a live pipeline" in events[0][1]["reason"]
    assert "ingest" in kinds
    assert "doc" in kinds
    assert "retrieve" in kinds
    assert "align" in kinds
    assert "entry" in kinds
    assert "ledger" in kinds
    assert "report" in kinds
    assert all(payload.get("mode") != "live" for _, payload in events)
    assert (out / "report.html").is_file()
    assert "PMC6925691" in (out / "report.html").read_text(encoding="utf-8")
    assert any(row[1].get("entry", {}).get("source_doc_id") == "PMC6925691" for row in events if row[0] == "entry")


def test_live_failure_falls_back_to_saved_and_says_so(tmp_path, monkeypatch):
    out = tmp_path / "20260101T000001Z"
    monkeypatch.setattr("transfer_audit.server.default_out", lambda: out)

    def boom(_claim, **_kwargs):
        raise IngestError("ANTHROPIC_API_KEY is not set")

    monkeypatch.setattr("transfer_audit.server.build_context", boom)
    events = _events(pipeline(RunRequest(claim="a claim about ICU patients", live=True)))
    assert events[0][1]["mode"] == "live"
    fallback = next(payload for name, payload in events if name == "fallback")
    assert fallback["mode"] == "saved"
    assert "ANTHROPIC_API_KEY" in fallback["reason"]
    assert "saved fixture" in fallback["reason"]
    ingest = next(payload for name, payload in events if name == "ingest")
    assert ingest["mode"] == "saved"
    assert (out / "report.html").is_file()


def test_corrections_append(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    from transfer_audit import server as server_mod

    run = tmp_path / "20260101T000002Z"
    run.mkdir()
    monkeypatch.setattr(server_mod, "RUNS", tmp_path)
    client = TestClient(server_mod.app)
    response = client.post(
        "/api/runs/20260101T000002Z/corrections",
        json={
            "source_doc_id": "PMC6925691",
            "axis": "B_legitimacy",
            "target_restatement": "corrected restatement",
        },
    )
    assert response.status_code == 200, response.text
    saved = json.loads((run / "corrections.json").read_text(encoding="utf-8"))
    assert saved[0]["target_restatement"] == "corrected restatement"
    assert saved[0]["source"] == "web"
    assert saved[0]["timestamp"]
