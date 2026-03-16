"""Task 09: API Integration — create code_search.py.

Prompt to give the agent:
---
Create a new script `scripts/code_search.py` that combines
`jedi_engine.search_project()` and `project_analyzer.analyze_project()`
to search for a symbol across the project and show where it is defined,
used, and what modules depend on it. It should accept a symbol name and
project root as CLI arguments.
---

Expected skill usage: jedi_engine.py, project_analyzer.py
Difficulty: Hard
"""

import subprocess
import sys
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parent.parent.parent / "scripts"


class TestTask09ApiIntegration:

    def test_script_exists(self):
        assert (SCRIPTS_DIR / "code_search.py").exists(), "code_search.py not created"

    def test_script_imports_cleanly(self):
        result = subprocess.run(
            [sys.executable, "-c", "import importlib.util; "
             f"spec = importlib.util.spec_from_file_location('cs', '{SCRIPTS_DIR / 'code_search.py'}'); "
             f"mod = importlib.util.module_from_spec(spec); "
             f"spec.loader.exec_module(mod)"],
            capture_output=True, text=True, timeout=30,
        )
        # Should not crash on import (may fail if jedi not available, that's OK)
        assert "SyntaxError" not in result.stderr, f"Syntax error: {result.stderr}"

    def test_has_cli_interface(self):
        source = (SCRIPTS_DIR / "code_search.py").read_text()
        assert "argparse" in source or "sys.argv" in source, "Should have CLI interface"

    def test_uses_jedi_engine(self):
        source = (SCRIPTS_DIR / "code_search.py").read_text()
        assert "jedi_engine" in source, "Should import from jedi_engine"

    def test_uses_project_analyzer(self):
        source = (SCRIPTS_DIR / "code_search.py").read_text()
        assert "project_analyzer" in source, "Should import from project_analyzer"
