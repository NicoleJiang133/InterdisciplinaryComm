import pytest

from transfer_audit import pc as pc_module
from transfer_audit.pc import PaperclipError, pc


class _Completed:
    def __init__(self, stdout: str, returncode: int = 0):
        self.stdout = stdout
        self.stderr = "NotOpenSSLWarning: urllib3 v2 only supports OpenSSL 1.1.1+"
        self.returncode = returncode


def _fake_run(monkeypatch, stdout: str, returncode: int = 0):
    monkeypatch.setattr(
        pc_module.subprocess,
        "run",
        lambda *a, **kw: _Completed(stdout, returncode),
    )


def test_returns_stdout(monkeypatch):
    _fake_run(monkeypatch, "Found 3 papers  [s_7463c7b8]\n")
    assert pc("search", "x", "-s", "arxiv").startswith("Found 3 papers")


def test_raises_on_err_prefix_despite_exit_zero(monkeypatch):
    """The CLI reports real failures on stdout while exiting 0."""
    _fake_run(monkeypatch, "ERR: map: invalid output schema: Expecting value\n[exit 1]\n", 0)
    with pytest.raises(PaperclipError, match="invalid output schema"):
        pc("map", "--from", "s_x")


def test_raises_on_non_zero_returncode(monkeypatch):
    _fake_run(monkeypatch, "", 1)
    with pytest.raises(PaperclipError, match="exited 1"):
        pc("generate-search-config", "claim.txt")


def test_stderr_is_ignored(monkeypatch):
    _fake_run(monkeypatch, "ok\n")
    assert pc("config") == "ok\n"


def test_timeout_is_passed_through(monkeypatch):
    seen = {}

    def spy(cmd, **kwargs):
        seen.update(kwargs)
        seen["cmd"] = cmd
        return _Completed("ok\n")

    monkeypatch.setattr(pc_module.subprocess, "run", spy)
    pc("config", timeout=7)
    assert seen["timeout"] == 7
    assert seen["capture_output"] is True
    assert seen["text"] is True
    assert seen["cmd"] == ["paperclip", "config"]


@pytest.mark.integration
def test_pc_search_returns_non_empty_result():
    out = pc("search", "data leakage", "-s", "arxiv", "-n", "3")
    assert out, "pc() returned nothing for a live search"
    assert "arx_" in out, f"expected arXiv doc ids in search output, got: {out[:400]}"
