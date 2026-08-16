import pytest

from transfer_audit.pc import pc


@pytest.mark.integration
def test_pc_search_returns_non_empty_result():
    out = pc("search", "data leakage", "-s", "arxiv", "-n", "3")
    assert out, "pc() returned nothing for a live search"
    text = out if isinstance(out, str) else str(out)
    assert "arx_" in text, f"expected arXiv doc ids in search output, got: {text[:400]}"
