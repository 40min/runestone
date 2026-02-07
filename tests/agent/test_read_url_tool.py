import pytest

import runestone.agent.tools as tools


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
