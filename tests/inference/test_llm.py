import pytest
from nexus.inference.llm import LLMClient


@pytest.fixture
def llm():
    return LLMClient(base_url="http://localhost:8384")


def test_format_prompt(llm):
    result = llm.format_prompt(system="You are a helpful assistant.", user="What is 2+2?")
    assert "helpful assistant" in result
    assert "2+2" in result


def test_format_prompt_with_history(llm):
    result = llm.format_prompt(
        system="Assistant.",
        user="Follow up question.",
        history=[
            {"role": "user", "content": "First question"},
            {"role": "assistant", "content": "First answer"},
        ],
    )
    assert "First question" in result
    assert "First answer" in result
    assert "Follow up" in result


def test_parse_response():
    raw = "Here is my response to your question."
    assert LLMClient.parse_response(raw) == raw.strip()


def test_parse_response_strips_tags():
    raw = "<|assistant|>Here is the answer.<|end|>"
    cleaned = LLMClient.parse_response(raw)
    assert "<|" not in cleaned
    assert "Here is the answer." in cleaned
