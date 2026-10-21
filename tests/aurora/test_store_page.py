"""The agent store page in Aurora: its sidebar entry, routes and the API it calls.

The full flow (browse, open, install with live steps, launch, remove) was walked in a
headless browser against a real server and real recipes; these pin its contracts."""


def test_store_link_in_sidebar(client):
    assert 'id="nx-open-store"' in client.get("/aurora").text


def test_store_routes_and_api_in_app_js(client):
    body = client.get("/aurora/static/app.js").text
    for needle in ("renderStore", "renderStoreAgent", "openStoreInstall", "#/store",
                   "/api/store/agents", "/api/store/jobs/"):
        assert needle in body, needle


def test_store_never_shows_an_unbacked_launch(client):
    # Catalog cards only offer Launch where launching works.
    body = client.get("/aurora/static/app.js").text
    assert 'const launchable = a.is_builtin || (st && st.installed) || (a.adapter_ref || "").startsWith("adapters/")' in body
    assert "graded and runnable" not in body


def test_store_layout_css_present(client):
    css = client.get("/aurora/static/app.css").text
    for cls in (".nx-store-grid", ".nx-store-card", ".nx-store-sections", ".nx-store-overlay"):
        assert cls in css, cls
