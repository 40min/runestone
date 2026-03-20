import pytest

from runestone.agents.tools import read_url as tools


def test_normalize_url_prepends_https():
    assert tools._normalize_url("example.com/path") == "https://example.com/path"


@pytest.mark.anyio
async def test_validate_fetch_url_rejects_unsafe_schemes(monkeypatch):
    async def _safe_host(_hostname: str, _port: int) -> bool:
        return True

    monkeypatch.setattr(tools, "_is_safe_public_host", _safe_host)

    ok, reason = await tools._validate_fetch_url("javascript:alert(1)")
    assert ok is False
    assert "http/https" in reason

    ok, reason = await tools._validate_fetch_url("file:///etc/passwd")
    assert ok is False
    assert "http/https" in reason


@pytest.mark.anyio
async def test_validate_fetch_url_blocks_credentials_and_ports(monkeypatch):
    async def _safe_host(_hostname: str, _port: int) -> bool:
        return True

    monkeypatch.setattr(tools, "_is_safe_public_host", _safe_host)

    ok, reason = await tools._validate_fetch_url("https://user:pass@example.com/")
    assert ok is False
    assert "Credentials" in reason

    ok, reason = await tools._validate_fetch_url("https://example.com:8080/")
    assert ok is False
    assert "ports" in reason


def test_simplify_markdown_filters_cookie_lines():
    md = "Line A\nLine A\n\nAccept cookies\nLine B\n"
    simplified = tools._simplify_markdown(md)
    assert simplified.count("Line A") == 1
    assert "Accept cookies" not in simplified


@pytest.mark.anyio
async def test_read_url_logs_when_output_is_truncated(monkeypatch, caplog):
    long_text = "x" * (tools.MAX_OUTPUT_CHARS + 64)

    async def _fake_fetch_url_bytes(_url: str):
        return long_text.encode("utf-8"), "https://example.com", "text/plain", False

    monkeypatch.setattr(tools, "_fetch_url_bytes", _fake_fetch_url_bytes)

    with caplog.at_level("WARNING"):
        result = await tools.read_url.ainvoke({"url": "https://example.com"})

    assert "read_url output truncated" in caplog.text
    assert "[Truncated output.]" in result
    assert "Note: Content was truncated due to size limits." in result
