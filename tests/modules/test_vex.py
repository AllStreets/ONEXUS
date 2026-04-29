# tests/modules/test_vex.py
import pytest
from unittest.mock import AsyncMock
from nexus.modules.vex import VexModule


@pytest.fixture
def vex():
    return VexModule()


def test_vex_attrs(vex):
    assert vex.name == "vex"
    assert vex.version == "0.1.0"
    assert vex.description


def test_scan_finds_eval(vex):
    code = "result = eval(user_input)"
    findings = vex.scan(code)
    assert len(findings) >= 1
    assert findings[0].severity == "HIGH"
    assert findings[0].category == "Injection"


def test_scan_finds_hardcoded_secret(vex):
    code = 'password = "super_secret_123"'
    findings = vex.scan(code)
    assert len(findings) >= 1
    assert any(f.category == "Credentials" for f in findings)


def test_scan_finds_sql_injection(vex):
    code = 'cursor.execute("SELECT * FROM users WHERE id = %s" % user_id)'
    findings = vex.scan(code)
    assert len(findings) >= 1
    assert any(f.category == "SQL Injection" for f in findings)


def test_scan_finds_ssl_disabled(vex):
    code = "requests.get(url, verify=False)"
    findings = vex.scan(code)
    assert len(findings) >= 1
    assert any(f.category == "TLS" for f in findings)


def test_scan_clean_code(vex):
    code = "def add(a, b):\n    return a + b"
    findings = vex.scan(code)
    assert len(findings) == 0


def test_scan_skips_comments(vex):
    code = "# eval(user_input)  -- this is a comment"
    findings = vex.scan(code)
    assert len(findings) == 0


def test_scan_summary(vex):
    code = (
        'eval(x)\n'
        'password = "secret"\n'
        'import random\nrandom.choice(items)\n'
    )
    findings = vex.scan(code)
    summary = vex.scan_summary(findings)
    assert summary["HIGH"] >= 2
    assert isinstance(summary["LOW"], int)


def test_scan_sorts_by_severity(vex):
    code = (
        'random.choice(items)\n'
        'eval(user_input)\n'
    )
    findings = vex.scan(code)
    if len(findings) >= 2:
        assert findings[0].severity == "HIGH"


@pytest.mark.asyncio
async def test_handle_returns_string(vex):
    context = {"llm": None, "engram": None}
    result = await vex.handle("def safe():\n    return 42", context)
    assert isinstance(result, str)
    assert "[Vex]" in result


@pytest.mark.asyncio
async def test_handle_with_vulnerabilities(vex):
    context = {"llm": None, "engram": None}
    result = await vex.handle("result = eval(user_input)", context)
    assert "HIGH" in result
    assert "Injection" in result
