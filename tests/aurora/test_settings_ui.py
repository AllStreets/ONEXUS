"""Tests for the Settings + permission UI surfaces."""


def test_settings_route_in_app_js(client):
    r = client.get("/aurora/static/app.js")
    assert "renderSettings" in r.text
    assert "#/settings" in r.text


def test_permission_handling_in_app_js(client):
    """v2 uses /api/permissions/ws (preferred) with a /pending+/decide REST
    fallback; the inline permission prompt renders both pending tickets and
    their action pills."""
    r = client.get("/aurora/static/app.js")
    body = r.text
    assert "/api/permissions/pending" in body
    assert "/api/permissions/decide" in body
    # WebSocket subscription path
    assert "/api/permissions/ws" in body
    # Inline prompt component
    assert "renderPendingPermissionHTML" in body


def test_settings_btn_present(client):
    r = client.get("/aurora")
    assert "nx-open-settings" in r.text
