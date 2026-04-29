# tests/modules/test_bastion.py
import pytest
from unittest.mock import AsyncMock
from nexus.modules.bastion import BastionModule, APIFinding


@pytest.fixture
def bastion():
    return BastionModule()


def test_bastion_attrs(bastion):
    assert bastion.name == "bastion"
    assert bastion.version == "0.1.0"


def test_parse_endpoints_http_methods(bastion):
    text = "GET /api/users\nPOST /api/users\nDELETE /api/users/{id}"
    endpoints = bastion.parse_endpoints(text)
    assert len(endpoints) == 3
    assert endpoints[0]["method"] == "GET"
    assert endpoints[0]["path"] == "/api/users"


def test_parse_endpoints_empty(bastion):
    assert bastion.parse_endpoints("no endpoints here") == []


def test_check_sensitive_path(bastion):
    ep = {"method": "GET", "path": "/api/admin/users"}
    findings = bastion.check_endpoint_security(ep)
    assert any(f.category == "Exposure" for f in findings)


def test_check_bola_risk(bastion):
    ep = {"method": "GET", "path": "/api/users/{id}"}
    findings = bastion.check_endpoint_security(ep)
    assert any(f.category == "BOLA" for f in findings)


def test_check_mass_assignment(bastion):
    ep = {"method": "POST", "path": "/api/users"}
    findings = bastion.check_endpoint_security(ep)
    assert any(f.category == "Mass Assignment" for f in findings)


def test_check_sensitive_param_in_path(bastion):
    ep = {"method": "GET", "path": "/api/users/password/reset"}
    findings = bastion.check_endpoint_security(ep)
    assert any(f.category == "Data Exposure" for f in findings)


def test_check_spec_no_auth(bastion):
    text = "GET /api/users\nPOST /api/orders"
    findings = bastion.check_spec_security(text)
    assert any(f.category == "Authentication" for f in findings)


def test_check_spec_http_not_https(bastion):
    text = "Base URL: http://api.example.com with bearer token auth"
    findings = bastion.check_spec_security(text)
    assert any(f.category == "Transport" for f in findings)


def test_check_spec_with_auth(bastion):
    text = "All endpoints require bearer token authentication"
    findings = bastion.check_spec_security(text)
    assert not any(f.category == "Authentication" for f in findings)


def test_severity_score(bastion):
    findings = [
        APIFinding("*", "*", "Auth", "critical", "No auth", "Add auth"),
        APIFinding("/a", "GET", "BOLA", "medium", "BOLA risk", "Fix"),
    ]
    score = bastion.severity_score(findings)
    assert score == 25  # 20 + 5


def test_severity_score_empty(bastion):
    assert bastion.severity_score([]) == 0


@pytest.mark.asyncio
async def test_handle_returns_scan(bastion):
    context = {"llm": None, "engram": None}
    result = await bastion.handle("GET /api/admin/users\nPOST /api/orders", context)
    assert "[Bastion]" in result
    assert "Risk Score" in result


@pytest.mark.asyncio
async def test_handle_stores_scan(bastion):
    context = {"llm": None, "engram": None}
    await bastion.handle("GET /api/users", context)
    assert len(bastion._scans) == 1
