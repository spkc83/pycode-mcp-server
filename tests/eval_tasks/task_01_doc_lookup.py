"""Task 01: Documentation Lookup — serialize a set using json.dumps.

Prompt to give the agent:
---
Write a function called `serialize_set` that uses `json.dumps` with the
`default` parameter to serialize a Python set into a JSON array string.
The function should have proper type hints and a docstring that includes
the correct signature of `json.dumps`. Save it to `task_outputs/task_01_output.py`.
---

Expected skill usage: doc_lookup.py (json.dumps)
Difficulty: Easy
"""

import json
import sys
from pathlib import Path

import pytest

# Allow importing from task_outputs/
OUTPUTS_DIR = Path(__file__).resolve().parent.parent.parent / "task_outputs"
if str(OUTPUTS_DIR) not in sys.path:
    sys.path.insert(0, str(OUTPUTS_DIR))


@pytest.fixture(autouse=True)
def _skip_if_no_output():
    output = OUTPUTS_DIR / "task_01_output.py"
    if not output.exists():
        pytest.skip("task_01_output.py not yet created by agent")


class TestTask01DocLookup:
    """Verification tests for Task 01."""

    def test_function_exists(self):
        from task_01_output import serialize_set

        assert callable(serialize_set)

    def test_serializes_set_of_ints(self):
        from task_01_output import serialize_set

        result = json.loads(serialize_set({1, 2, 3}))
        assert sorted(result) == [1, 2, 3]

    def test_serializes_set_of_strings(self):
        from task_01_output import serialize_set

        result = json.loads(serialize_set({"a", "b"}))
        assert sorted(result) == ["a", "b"]

    def test_handles_empty_set(self):
        from task_01_output import serialize_set

        result = json.loads(serialize_set(set()))
        assert result == []

    def test_returns_string(self):
        from task_01_output import serialize_set

        result = serialize_set({1})
        assert isinstance(result, str)

    def test_has_docstring(self):
        from task_01_output import serialize_set

        assert serialize_set.__doc__ is not None
        assert len(serialize_set.__doc__) > 10
