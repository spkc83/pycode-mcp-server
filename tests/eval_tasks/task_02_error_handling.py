"""Task 02: Error Handling — parse JSON with proper exception handling.

Prompt to give the agent:
---
Write a function called `safe_json_parse` that parses user JSON input
and handles ALL exceptions that `json.loads` can raise. The function
should return a tuple of (parsed_data, error_message). If parsing succeeds,
error_message should be None. List each exception type in the docstring.
Save it to `task_outputs/task_02_output.py`.
---

Expected skill usage: doc_lookup.py (json.loads exceptions)
Difficulty: Medium
"""

import sys
from pathlib import Path

import pytest

OUTPUTS_DIR = Path(__file__).resolve().parent.parent.parent / "task_outputs"
if str(OUTPUTS_DIR) not in sys.path:
    sys.path.insert(0, str(OUTPUTS_DIR))


@pytest.fixture(autouse=True)
def _skip_if_no_output():
    if not (OUTPUTS_DIR / "task_02_output.py").exists():
        pytest.skip("task_02_output.py not yet created by agent")


class TestTask02ErrorHandling:
    def test_function_exists(self):
        from task_02_output import safe_json_parse

        assert callable(safe_json_parse)

    def test_valid_json(self):
        from task_02_output import safe_json_parse

        data, err = safe_json_parse('{"key": "value"}')
        assert data == {"key": "value"}
        assert err is None

    def test_invalid_json(self):
        from task_02_output import safe_json_parse

        data, err = safe_json_parse("not json")
        assert data is None
        assert err is not None

    def test_wrong_type(self):
        from task_02_output import safe_json_parse

        data, err = safe_json_parse(12345)  # type: ignore
        assert data is None
        assert err is not None

    def test_empty_string(self):
        from task_02_output import safe_json_parse

        data, err = safe_json_parse("")
        assert data is None
        assert err is not None

    def test_returns_tuple(self):
        from task_02_output import safe_json_parse

        result = safe_json_parse('{"a": 1}')
        assert isinstance(result, tuple)
        assert len(result) == 2

    def test_has_docstring(self):
        from task_02_output import safe_json_parse

        assert safe_json_parse.__doc__ is not None
