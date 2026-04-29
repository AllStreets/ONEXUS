"""
Code agent benchmark suite.
Tests Arbiter, Carve, Rune, and Remedy accuracy.
"""
from __future__ import annotations

from nexus.benchmarks.models import BenchmarkCase, BenchmarkSuite

# Build a long function body for Carve testing
_LONG_FUNCTION = "def process():\n" + "\n".join(f"    x = {i}" for i in range(50))

_DEEP_NESTING = (
    "if a:\n"
    "    if b:\n"
    "        if c:\n"
    "            if d:\n"
    "                if e:\n"
    "                    pass"
)

_CODE_WITH_ISSUES = (
    "import os\n"
    "import sys\n"
    "def do_stuff(items):\n"
    "    # TODO: fix this later\n"
    "    x = 123456789\n"
    "    for item in items:\n"
    "        print(item)\n"
    "    except:\n"
    "        pass\n"
)

_TRACEBACK_IMPORT = (
    'Traceback (most recent call last):\n'
    '  File "app.py", line 12, in <module>\n'
    '    import pandas\n'
    "ModuleNotFoundError: No module named 'pandas'"
)

_TRACEBACK_KEY = (
    'Traceback (most recent call last):\n'
    '  File "handler.py", line 45, in process\n'
    '    value = data["missing_key"]\n'
    "KeyError: 'missing_key'"
)

_TRACEBACK_TYPE = (
    'Traceback (most recent call last):\n'
    '  File "calc.py", line 8, in compute\n'
    '    result = x + None\n'
    "TypeError: unsupported operand type(s) for +: 'int' and 'NoneType'"
)

_TRACEBACK_INDEX = (
    'Traceback (most recent call last):\n'
    '  File "data.py", line 22, in fetch\n'
    '    item = items[99]\n'
    "IndexError: list index out of range"
)

_TRACEBACK_FILE = (
    'Traceback (most recent call last):\n'
    '  File "loader.py", line 5, in load\n'
    '    f = open("/missing/path.txt")\n'
    "FileNotFoundError: [Errno 2] No such file or directory: '/missing/path.txt'"
)

CODE_SUITE = BenchmarkSuite(
    name="Code Agents",
    description="Benchmark Arbiter, Carve, Rune, and Remedy accuracy",
    cases=[
        # ----------------------------------------------------------------
        # Carve -- complexity analysis
        # ----------------------------------------------------------------
        BenchmarkCase(
            name="carve_long_function",
            module_name="carve",
            input_message=f"analyze:\n{_LONG_FUNCTION}",
            expected_patterns=[r"(?i)long|lines|length|complex|extract"],
        ),
        BenchmarkCase(
            name="carve_deep_nesting",
            module_name="carve",
            input_message=f"analyze:\n{_DEEP_NESTING}",
            expected_patterns=[r"(?i)nest"],
        ),
        BenchmarkCase(
            name="carve_high_complexity",
            module_name="carve",
            input_message=(
                "analyze:\n"
                "def route(x):\n"
                + "".join(f"    if x == {i}:\n        pass\n    elif x == {i+100}:\n        pass\n" for i in range(10))
            ),
            expected_patterns=[r"(?i)complex|branch"],
        ),
        BenchmarkCase(
            name="carve_simple_code",
            module_name="carve",
            input_message="analyze:\nx = 1\ny = 2\nz = x + y",
            expected_patterns=[r"(?i)carve|analysis|code"],
        ),

        # ----------------------------------------------------------------
        # Arbiter -- code review
        # ----------------------------------------------------------------
        BenchmarkCase(
            name="arbiter_bare_except",
            module_name="arbiter",
            input_message="review:\ntry:\n    x = 1\nexcept:\n    pass",
            expected_patterns=[r"(?i)except|error.?handling"],
        ),
        BenchmarkCase(
            name="arbiter_todo",
            module_name="arbiter",
            input_message="review:\ndef process():\n    x = 1  # TODO: fix this critical bug\n    return x",
            expected_patterns=[r"(?i)todo|annotation|code.?quality"],
        ),
        BenchmarkCase(
            name="arbiter_print_statement",
            module_name="arbiter",
            input_message="review:\ndef handler(req):\n    print(req.body)\n    return 200",
            expected_patterns=[r"(?i)print|log"],
        ),
        BenchmarkCase(
            name="arbiter_clean_code",
            module_name="arbiter",
            input_message="review:\ndef add(a: int, b: int) -> int:\n    return a + b",
            expected_patterns=[r"(?i)no.*(issue|finding)|review|arbiter"],
        ),

        # ----------------------------------------------------------------
        # Rune -- regex building
        # ----------------------------------------------------------------
        BenchmarkCase(
            name="rune_email",
            module_name="rune",
            input_message="build a regex to match email addresses",
            expected_patterns=[r"@", r"\\w|\\S|\[|\w"],
        ),
        BenchmarkCase(
            name="rune_url",
            module_name="rune",
            input_message="build a regex to match URLs",
            expected_patterns=[r"http|url", r"://|\\S"],
        ),
        BenchmarkCase(
            name="rune_ip_address",
            module_name="rune",
            input_message="build a regex to match ip addresses",
            expected_patterns=[r"\\d|\d|ip", r"\\.|\["],
        ),
        BenchmarkCase(
            name="rune_phone",
            module_name="rune",
            input_message="build a regex to match phone numbers",
            expected_patterns=[r"\\d|\d|phone", r"rune"],
        ),

        # ----------------------------------------------------------------
        # Remedy -- error diagnosis
        # ----------------------------------------------------------------
        BenchmarkCase(
            name="remedy_import_error",
            module_name="remedy",
            input_message=f"diagnose: {_TRACEBACK_IMPORT}",
            expected_patterns=[r"(?i)install|pip|module", r"(?i)ModuleNotFoundError|import"],
        ),
        BenchmarkCase(
            name="remedy_key_error",
            module_name="remedy",
            input_message=f"diagnose: {_TRACEBACK_KEY}",
            expected_patterns=[r"(?i)key|dict", r"(?i)KeyError|exist"],
        ),
        BenchmarkCase(
            name="remedy_type_error",
            module_name="remedy",
            input_message=f"diagnose: {_TRACEBACK_TYPE}",
            expected_patterns=[r"(?i)type|TypeError", r"(?i)None|operand|argument"],
        ),
        BenchmarkCase(
            name="remedy_index_error",
            module_name="remedy",
            input_message=f"diagnose: {_TRACEBACK_INDEX}",
            expected_patterns=[r"(?i)index|IndexError", r"(?i)range|bound|length"],
        ),
        BenchmarkCase(
            name="remedy_file_not_found",
            module_name="remedy",
            input_message=f"diagnose: {_TRACEBACK_FILE}",
            expected_patterns=[r"(?i)file|FileNotFoundError|path", r"(?i)exist|verify"],
        ),
    ],
)
