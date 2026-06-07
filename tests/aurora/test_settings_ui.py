"""Tests for the Settings + permission UI surfaces."""


def test_settings_route_in_app_js(client):
    r = client.get("/aurora/static/app.js")
    assert "renderSettings" in r.text
    assert "#/settings" in r.text


def test_permission_polling_in_app_js(client):
    r = client.get("/aurora/static/app.js")
    assert "pollPermissions" in r.text
    assert "/api/permissions/pending" in r.text
    assert "/api/permissions/decide" in r.text


def test_install_review_in_app_js(client):
    r = client.get("/aurora/static/app.js")
    assert "/api/agents/install" in r.text


def test_settings_btn_present(client):
    r = client.get("/aurora")
    assert "nx-settings-btn" in r.text
