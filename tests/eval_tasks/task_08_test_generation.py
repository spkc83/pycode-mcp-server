"""Task 08: Test Generation — tests for detect_circular_dependencies.

Prompt to give the agent:
---
Write comprehensive tests for `detect_circular_dependencies()` in
`scripts/project_analyzer.py`. Cover: no cycles, simple A→B→A cycle,
self-cycle, diamond graph with cycle, and disconnected components.
Save to `task_outputs/task_08_output.py`.
---

Expected skill usage: code_analyzer.py, doc_lookup.py
Difficulty: Hard
"""

import sys
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parent.parent.parent / "scripts"
OUTPUTS_DIR = Path(__file__).resolve().parent.parent.parent / "task_outputs"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))
if str(OUTPUTS_DIR) not in sys.path:
    sys.path.insert(0, str(OUTPUTS_DIR))


@pytest.fixture(autouse=True)
def _skip_if_no_output():
    if not (OUTPUTS_DIR / "task_08_output.py").exists():
        pytest.skip("task_08_output.py not yet created by agent")


class TestTask08TestGeneration:
    def test_output_is_valid_python(self):
        """Generated test file should be valid Python."""
        source = (OUTPUTS_DIR / "task_08_output.py").read_text()
        compile(source, "task_08_output.py", "exec")

    def test_output_imports_detect_circular(self):
        """Tests should import detect_circular_dependencies."""
        source = (OUTPUTS_DIR / "task_08_output.py").read_text()
        assert "detect_circular_dependencies" in source

    def test_covers_no_cycles(self):
        source = (OUTPUTS_DIR / "task_08_output.py").read_text()
        assert "no" in source.lower() and "cycle" in source.lower()

    def test_covers_simple_cycle(self):
        source = (OUTPUTS_DIR / "task_08_output.py").read_text()
        # Should test A→B→A or similar
        assert "cycle" in source.lower()

    def test_generated_tests_pass(self):
        """The agent's generated tests should all pass."""
        import subprocess

        result = subprocess.run(
            [sys.executable, "-m", "pytest", str(OUTPUTS_DIR / "task_08_output.py"), "-v"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode == 0, f"Generated tests failed:\n{result.stdout}\n{result.stderr}"
