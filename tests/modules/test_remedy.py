# tests/modules/test_remedy.py
import pytest
from unittest.mock import AsyncMock
from nexus.modules.remedy import RemedyModule


@pytest.fixture
def remedy():
    return RemedyModule()


def test_remedy_attrs(remedy):
    assert remedy.name == "remedy"
    assert remedy.version == "0.1.0"


def test_parse_traceback(remedy):
    tb = '''Traceback (most recent call last):
  File "/app/main.py", line 42, in process
    result = data["key"]
KeyError: 'key'
'''
    parsed = remedy.parse_traceback(tb)
    assert parsed["error_type"] == "KeyError"
    assert parsed["error_message"] == "'key'"
    assert parsed["file_path"] == "/app/main.py"
    assert parsed["line_number"] == 42


def test_parse_traceback_module_not_found(remedy):
    tb = '''Traceback (most recent call last):
  File "script.py", line 1, in <module>
    import pandas
ModuleNotFoundError: No module named 'pandas'
'''
    parsed = remedy.parse_traceback(tb)
    assert parsed["error_type"] == "ModuleNotFoundError"
    assert "pandas" in parsed["error_message"]


def test_parse_traceback_no_error(remedy):
    parsed = remedy.parse_traceback("just some random text")
    assert parsed["error_type"] == ""


def test_diagnose_key_error(remedy):
    parsed = {
        "error_type": "KeyError",
        "error_message": "'missing_key'",
        "file_path": "app.py",
        "line_number": 10,
        "frames": [],
    }
    diagnosis = remedy.diagnose(parsed)
    assert diagnosis.error_type == "KeyError"
    assert "dict" in diagnosis.root_cause.lower() or "key" in diagnosis.root_cause.lower()
    assert "get" in diagnosis.suggestion.lower()


def test_diagnose_module_not_found(remedy):
    parsed = {
        "error_type": "ModuleNotFoundError",
        "error_message": "No module named 'requests'",
        "file_path": "app.py",
        "line_number": 1,
        "frames": [],
    }
    diagnosis = remedy.diagnose(parsed)
    assert "requests" in diagnosis.suggestion


def test_diagnose_unknown_error(remedy):
    parsed = {
        "error_type": "CustomError",
        "error_message": "something broke",
        "file_path": "",
        "line_number": 0,
        "frames": [],
    }
    diagnosis = remedy.diagnose(parsed)
    assert diagnosis.error_type == "CustomError"


@pytest.mark.asyncio
async def test_handle_with_traceback(remedy):
    tb = '''Traceback (most recent call last):
  File "app.py", line 5, in main
    x = 1 / 0
ZeroDivisionError: division by zero
'''
    context = {"llm": None, "engram": None}
    result = await remedy.handle(tb, context)
    assert "[Remedy]" in result
    assert "ZeroDivisionError" in result
    assert "zero" in result.lower()


@pytest.mark.asyncio
async def test_handle_no_traceback(remedy):
    context = {"llm": None, "engram": None}
    result = await remedy.handle("something broke", context)
    assert "[Remedy]" in result
    assert "could not parse" in result.lower() or "paste" in result.lower()


@pytest.mark.asyncio
async def test_handle_stores_diagnosis(remedy):
    tb = "Traceback:\n  File \"x.py\", line 1\nValueError: bad value"
    context = {"llm": None, "engram": None}
    await remedy.handle(tb, context)
    assert len(remedy._diagnoses) == 1
