"""Council deliberation participant selection.

Regression tests for the single-participant collapse: select_participants
used to consider only modules with a predefined deliberation role, and
on_load could snapshot the sibling registry before other modules finished
registering — both paths stranded deliberations at one participant.
"""
import pytest

from nexus.modules.council import CouncilModule


class _StubModule:
    def __init__(self, name):
        self.name = name

    async def handle(self, message, context):
        return f"{self.name} perspective on: {message[:40]}"


class _StubCortex:
    def __init__(self, names):
        self._modules = {n: _StubModule(n) for n in names}


def _council_with_siblings(names):
    council = CouncilModule()
    council._modules = {n: _StubModule(n) for n in names}
    return council


def test_select_participants_includes_loaded_sibling_with_matching_trigger():
    council = _council_with_siblings(["oracle", "echo", "sentry"])
    selected = council.select_participants("analyze the best approach and compare options")
    assert "oracle" in selected


def test_select_participants_considers_roleless_loaded_modules():
    # A loaded module without a predefined deliberation role is still a
    # candidate (it fills up to min_modules with the default role).
    council = _council_with_siblings(["custommod"])
    selected = council.select_participants("plain question with no trigger words")
    assert "custommod" in selected


@pytest.mark.asyncio
async def test_deliberate_resnapshots_sibling_registry_from_cortex():
    # on_load raced module registration: council._modules is empty, but the
    # live cortex registry has siblings. deliberate() must re-snapshot.
    council = CouncilModule()
    council._modules = {}
    cortex = _StubCortex(["council", "oracle", "specter", "sentry"])

    result = await council.deliberate(
        "should i adopt this plan — what are the risks?",
        {"cortex": cortex},
    )
    # Council itself is excluded from its own sibling set.
    assert "council" not in council._modules
    assert len(result.participants) >= 2
    assert result.rounds >= 1


@pytest.mark.asyncio
async def test_deliberate_without_cortex_still_degrades_gracefully():
    council = CouncilModule()
    council._modules = {}
    result = await council.deliberate("should i do this?", {})
    assert result.participants == []
    assert result.confidence == 0.0
