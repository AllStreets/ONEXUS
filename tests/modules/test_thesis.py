# tests/modules/test_thesis.py
import pytest
from unittest.mock import AsyncMock
from nexus.agents.thesis import ThesisModule, PaperNote


@pytest.fixture
def thesis():
    return ThesisModule()


def test_thesis_attrs(thesis):
    assert thesis.name == "thesis"
    assert thesis.version == "0.1.0"
    assert thesis.description


def test_extract_title(thesis):
    text = "Attention Is All You Need\nby Vaswani et al.\nAbstract: We propose a new architecture..."
    title = thesis._extract_title(text)
    assert title == "Attention Is All You Need"


def test_extract_authors(thesis):
    text = "Attention Is All You Need\nby Vaswani, Shazeer, Parmar et al."
    authors = thesis._extract_authors(text)
    assert "Vaswani" in authors


def test_extract_tags_from_keywords(thesis):
    text = "Title\nKeywords: transformer, attention mechanism, neural machine translation"
    tags = thesis._extract_tags(text)
    assert "transformer" in tags
    assert "attention mechanism" in tags


def test_add_and_list_papers(thesis):
    note = PaperNote(
        title="Test Paper",
        authors="Author A",
        key_claims=["Claim 1"],
        methodology="Survey",
        limitations=["Small sample"],
        tags=["test"],
    )
    thesis.add_paper(note)
    assert len(thesis.list_papers()) == 1


def test_find_gaps_needs_multiple_papers(thesis):
    assert thesis.find_gaps() == []

    thesis.add_paper(PaperNote("P1", "A", ["c1"], "Survey", ["limited scope"], ["ai"]))
    assert thesis.find_gaps() == []

    thesis.add_paper(PaperNote("P2", "B", ["c2"], "Survey", ["limited scope, small sample"], ["ai"]))
    gaps = thesis.find_gaps()
    assert len(gaps) >= 1


def test_compare_papers(thesis):
    thesis.add_paper(PaperNote("Paper A", "Author X", ["Claim 1"], "RCT", ["Small N"], ["health"]))
    thesis.add_paper(PaperNote("Paper B", "Author Y", ["Claim 2"], "Survey", ["Bias"], ["health"]))
    comparison = thesis.compare_papers()
    assert "Paper A" in comparison
    assert "Paper B" in comparison


def test_compare_papers_empty(thesis):
    result = thesis.compare_papers()
    assert "no papers" in result.lower() or "No papers" in result


@pytest.mark.asyncio
async def test_handle_analyzes_paper(thesis):
    context = {"llm": None, "engram": None}
    result = await thesis.handle(
        "Attention Is All You Need\nby Vaswani et al.\n"
        "We propose a new architecture based on attention mechanisms.",
        context,
    )
    assert "[Thesis]" in result
    assert "Attention" in result


@pytest.mark.asyncio
async def test_handle_with_llm(thesis):
    llm = AsyncMock()
    llm.complete.return_value = (
        "KEY CLAIMS\n- Transformers outperform RNNs\n- Self-attention enables parallelization\n"
        "METHODOLOGY\nComparative study on WMT translation benchmarks\n"
        "LIMITATIONS\n- Only tested on English-German\n"
        "CONTRIBUTION\nIntroduces self-attention as primary mechanism\n"
    )
    context = {"llm": llm, "engram": None}
    result = await thesis.handle(
        "Attention Is All You Need\nby Vaswani et al.\nAbstract text here.",
        context,
    )
    assert "Transformers" in result or "Thesis" in result
    llm.complete.assert_called_once()


@pytest.mark.asyncio
async def test_handle_compare_command(thesis):
    thesis.add_paper(PaperNote("P1", "A", ["c"], "M", [], ["t"]))
    thesis.add_paper(PaperNote("P2", "B", ["c"], "M", [], ["t"]))
    context = {"llm": None, "engram": None}
    result = await thesis.handle("compare papers", context)
    assert "P1" in result and "P2" in result


@pytest.mark.asyncio
async def test_handle_stores_paper(thesis):
    context = {"llm": None, "engram": None}
    await thesis.handle("Test Paper Title\nSome content here.", context)
    assert len(thesis.list_papers()) == 1
