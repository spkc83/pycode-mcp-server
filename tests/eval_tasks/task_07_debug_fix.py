"""Task 07: Debug Fix — find and fix import ordering bugs.

Prompt to give the agent:
---
Find and fix any import ordering bugs in the scripts/ directory where
a name is used before it is imported. Report which files had issues.
Save a list of fixed files to `task_outputs/task_07_output.json`.
---

Expected skill usage: diagnostics.py, code_analyzer.py
Difficulty: Easy
"""

import json
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parent.parent.parent / "scripts"
OUTPUTS_DIR = Path(__file__).resolve().parent.parent.parent / "task_outputs"


class TestTask07DebugFix:

    def test_all_scripts_import_cleanly(self):
        """Every script in scripts/ should import without NameError."""
        scripts = sorted(SCRIPTS_DIR.glob("*.py"))
        assert len(scripts) > 0, "No scripts found"

        errors = []
        for script in scripts:
            result = subprocess.run(
                [sys.executable, "-c", f"import importlib.util; "
                 f"spec = importlib.util.spec_from_file_location('mod', '{script}'); "
                 f"mod = importlib.util.module_from_spec(spec); "
                 f"spec.loader.exec_module(mod)"],
                capture_output=True, text=True, timeout=30,
            )
            if result.returncode != 0 and "NameError" in result.stderr:
                errors.append(f"{script.name}: {result.stderr.strip()}")

        assert not errors, f"Import errors found:\n" + "\n".join(errors)

    def test_output_file_exists(self):
        """Agent should have created an output file listing fixed files."""
        output = OUTPUTS_DIR / "task_07_output.json"
        if not output.exists():
            pytest.skip("task_07_output.json not yet created")
        data = json.loads(output.read_text())
        assert isinstance(data, list)
