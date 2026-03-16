"""Task 03: Class Usage — find Python files using pathlib.Path.

Prompt to give the agent:
---
Create a function called `find_python_files` that uses `pathlib.Path` to
recursively find all `.py` files in a directory, get their sizes, and
return a dict mapping file paths (str) to sizes (int), sorted by size
(largest first). Use the correct method names.
Save it to `task_outputs/task_03_output.py`.
---

Expected skill usage: doc_lookup.py (pathlib.Path)
Difficulty: Medium
"""

import sys
import tempfile
from pathlib import Path

import pytest

OUTPUTS_DIR = Path(__file__).resolve().parent.parent.parent / "task_outputs"
if str(OUTPUTS_DIR) not in sys.path:
    sys.path.insert(0, str(OUTPUTS_DIR))


@pytest.fixture(autouse=True)
def _skip_if_no_output():
    if not (OUTPUTS_DIR / "task_03_output.py").exists():
        pytest.skip("task_03_output.py not yet created by agent")


@pytest.fixture
def sample_dir(tmp_path):
    (tmp_path / "a.py").write_text("x = 1\n")
    (tmp_path / "b.py").write_text("y = 2\nz = 3\n")
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "c.py").write_text("import os\nimport sys\nimport json\n")
    (tmp_path / "not_python.txt").write_text("hello")
    return tmp_path


class TestTask03ClassUsage:

    def test_function_exists(self):
        from task_03_output import find_python_files
        assert callable(find_python_files)

    def test_finds_all_py_files(self, sample_dir):
        from task_03_output import find_python_files
        result = find_python_files(sample_dir)
        assert len(result) == 3

    def test_excludes_non_py(self, sample_dir):
        from task_03_output import find_python_files
        result = find_python_files(sample_dir)
        assert all(k.endswith(".py") for k in result)

    def test_values_are_ints(self, sample_dir):
        from task_03_output import find_python_files
        result = find_python_files(sample_dir)
        assert all(isinstance(v, int) for v in result.values())

    def test_sorted_largest_first(self, sample_dir):
        from task_03_output import find_python_files
        result = find_python_files(sample_dir)
        sizes = list(result.values())
        assert sizes == sorted(sizes, reverse=True)

    def test_returns_dict(self, sample_dir):
        from task_03_output import find_python_files
        result = find_python_files(sample_dir)
        assert isinstance(result, dict)

    def test_empty_dir(self, tmp_path):
        from task_03_output import find_python_files
        result = find_python_files(tmp_path)
        assert result == {} or len(result) == 0
