"""FIX 2 — Cortex launcher in-flight + error UX contracts.

The behaviour is pure frontend (vanilla JS state machine), so these are
asset-contract tests in the style of test_accessibility.py: they pin the
markup/CSS invariants the UX depends on, so a refactor that silently drops
the spinner, the running state, or the role="alert" banner fails CI.
"""
from __future__ import annotations


def _app_js(client) -> str:
    return client.get("/aurora/static/app.js").text


def _app_css(client) -> str:
    return client.get("/aurora/static/app.css").text


def test_dispatch_button_has_spinner(client):
    src = _app_js(client)
    # spinner markup ships inside the run button and is toggled while running
    assert 'class="nx-spinner"' in src
    assert "spinner.hidden = !_cortexState.running" in src


def test_pending_cards_render_as_running_not_error(client):
    src = _app_js(client)
    # pending run objects are flagged pending:true and never carry a fake
    # "pending" error string
    assert "pending: true" in src
    assert '"pending"' not in src.replace("error: null", "")  # old sentinel removed
    # the pending branch renders a running status + pending card class
    assert 'nx-cortex-run-card pending' in src
    assert 'nx-cortex-run-status running' in src


def test_dispatch_failure_surfaces_alert_banner(client):
    src = _app_js(client)
    assert 'role="alert"' in src
    assert "DISPATCH FAILED" in src
    # HTTP status + detail reach the banner text
    assert "HTTP ${err.status}" in src
    # every selected agent's card flips to an explicit error with elapsed time
    assert "failAll(" in src
    assert "Date.now() - startedAt" in src


def test_failed_card_states_elapsed_time(client):
    src = _app_js(client)
    assert "failed after ${secs}s" in src


def test_css_ships_spinner_and_pending_pulse(client):
    css = _app_css(client)
    assert ".nx-spinner" in css
    assert "@keyframes nx-spin" in css
    assert ".nx-cortex-run-card.pending" in css
    assert "@keyframes nx-pending-pulse" in css
    assert ".nx-cortex-error" in css


def test_animations_respect_reduced_motion(client):
    # The global reduced-motion collapse in tokens.css covers the new
    # spinner/pulse animations (they are plain CSS animations).
    tokens = client.get("/aurora/static/tokens.css").text
    assert "prefers-reduced-motion" in tokens
    assert "animation-duration: 0.001ms" in tokens
