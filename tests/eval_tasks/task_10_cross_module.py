"""Task 10: Cross-Module Enhancement — add --health-detail flag.

Prompt to give the agent:
---
Add a `--health-detail` flag to `scripts/health_check.py` that also runs
`diagnostics.py` on each script in `scripts/` and includes diagnostic
results in the health check output.
---

Expected skill usage: health_check.py, diagnostics.py
Difficulty: Medium
"""

import subprocess
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent.parent.parent / "scripts"


class TestTask10CrossModule:
    def test_health_check_accepts_flag(self):
        """health_check.py should accept --health-detail without crashing."""
        result = subprocess.run(
            [sys.executable, str(SCRIPTS_DIR / "health_check.py"), "--health-detail"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        # Should not crash with unrecognized argument error
        assert "unrecognized" not in result.stderr.lower(), f"Flag not recognized: {result.stderr}"

    def test_health_detail_includes_diagnostics(self):
        """Output with --health-detail should contain diagnostic info."""
        result = subprocess.run(
            [sys.executable, str(SCRIPTS_DIR / "health_check.py"), "--health-detail"],
            capture_output=True,
            text=True,
            timeout=60,
        )
        output = result.stdout.lower()
        # Should mention diagnostics in some form
        has_diag = "diagnostic" in output or "issue" in output or "check" in output
        assert has_diag, f"Expected diagnostic info in output:\n{result.stdout[:500]}"

    def test_health_check_still_works_without_flag(self):
        """health_check.py should still work without the new flag."""
        result = subprocess.run(
            [sys.executable, str(SCRIPTS_DIR / "health_check.py")],
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode == 0 or "error" not in result.stderr.lower()

    def test_source_imports_diagnostics(self):
        """Modified health_check.py should reference diagnostics module."""
        source = (SCRIPTS_DIR / "health_check.py").read_text()
        assert "diagnostics" in source, "health_check.py should import/use diagnostics"
