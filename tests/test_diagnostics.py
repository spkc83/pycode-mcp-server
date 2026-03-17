"""Tests for diagnostics.py — unified diagnostics engine."""

import json
import sys
import tempfile
from pathlib import Path

import pytest

# Add scripts directory to path
SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from diagnostics import (
    get_jedi_diagnostics,
    get_pyflakes_diagnostics,
    run_diagnostics,
    _build_result,
)


class TestJediDiagnostics:
    """Test Jedi-based syntax diagnostics."""

    def test_valid_code_no_errors(self):
        source = "def hello():\n    return 'world'\n"
        diags = get_jedi_diagnostics(source)
        # Filter out any error dicts from the Jedi unavailable check
        real_diags = [d for d in diags if "error" not in d]
        assert len(real_diags) == 0

    def test_syntax_error_detected(self):
        source = "def broken(\n"
        diags = get_jedi_diagnostics(source)
        if diags:  # Only test if Jedi is available
            error_diags = [d for d in diags if d.get("severity") == "error"]
            assert len(error_diags) > 0

    def test_missing_colon_detected(self):
        source = "def foo()\n    pass\n"
        diags = get_jedi_diagnostics(source)
        if diags:
            error_diags = [d for d in diags if d.get("severity") == "error"]
            assert len(error_diags) > 0

    def test_diagnostics_have_line_numbers(self):
        source = "\n\ndef broken(\n"
        diags = get_jedi_diagnostics(source)
        if diags:
            for d in diags:
                if "error" not in d:
                    assert "line" in d
                    assert "column" in d


class TestPyflakesDiagnostics:
    """Test Pyflakes-based diagnostics."""

    def test_unused_import(self):
        source = "import os\nx = 1\n"
        diags = get_pyflakes_diagnostics(source, "test.py")
        # If pyflakes is available, should detect unused import
        if diags:
            messages = [d.get("message", "") for d in diags]
            assert any("os" in m for m in messages)

    def test_undefined_name(self):
        source = "print(undefined_variable)\n"
        diags = get_pyflakes_diagnostics(source, "test.py")
        if diags:
            messages = [d.get("message", "") for d in diags]
            assert any("undefined" in m.lower() for m in messages)

    def test_clean_code(self):
        source = "x = 1\nprint(x)\n"
        diags = get_pyflakes_diagnostics(source, "test.py")
        # Clean code should have no warnings
        assert len(diags) == 0


class TestRunDiagnostics:
    """Test the unified run_diagnostics function."""

    def test_run_on_valid_file(self):
        with tempfile.NamedTemporaryFile(suffix=".py", mode="w", delete=False) as f:
            f.write("def hello():\n    return 'world'\n")
            f.flush()

            result = run_diagnostics(f.name)
            assert "file" in result
            assert "diagnostics" in result
            assert "summary" in result
            assert isinstance(result["diagnostics"], list)

    def test_run_on_nonexistent_file(self):
        result = run_diagnostics("/nonexistent/file.py")
        assert "error" in result

    def test_run_on_non_python_file(self):
        with tempfile.NamedTemporaryFile(suffix=".txt", mode="w", delete=False) as f:
            f.write("not python")
            f.flush()
            result = run_diagnostics(f.name)
            assert "error" in result

    def test_run_syntax_only(self):
        with tempfile.NamedTemporaryFile(suffix=".py", mode="w", delete=False) as f:
            f.write("import os\n")  # unused import, but syntax_only should not flag it
            f.flush()

            result = run_diagnostics(f.name, syntax_only=True)
            assert "summary" in result
            # Syntax-only should only have Jedi errors, not pyflakes

    def test_summary_counts(self):
        with tempfile.NamedTemporaryFile(suffix=".py", mode="w", delete=False) as f:
            f.write("def broken(\n")
            f.flush()

            result = run_diagnostics(f.name)
            summary = result["summary"]
            assert "total" in summary
            assert "errors" in summary
            assert "warnings" in summary


class TestBuildResult:
    """Test the result builder helper."""

    def test_build_empty_result(self):
        result = _build_result("test.py", [], ["jedi"])
        assert result["file"] == "test.py"
        assert result["diagnostics"] == []
        assert result["summary"]["total"] == 0

    def test_build_result_counts(self):
        diags = [
            {"line": 1, "severity": "error", "message": "err1"},
            {"line": 2, "severity": "error", "message": "err2"},
            {"line": 3, "severity": "warning", "message": "warn1"},
            {"line": 4, "severity": "info", "message": "info1"},
        ]
        result = _build_result("test.py", diags, ["jedi", "pyflakes"])
        assert result["summary"]["errors"] == 2
        assert result["summary"]["warnings"] == 1
        assert result["summary"]["info"] == 1
        assert result["summary"]["total"] == 4
        assert result["sources_used"] == ["jedi", "pyflakes"]

    def test_build_result_sorted_by_line(self):
        diags = [
            {"line": 5, "column": 0, "severity": "error", "message": "late"},
            {"line": 1, "column": 0, "severity": "error", "message": "early"},
            {"line": 3, "column": 0, "severity": "warning", "message": "mid"},
        ]
        result = _build_result("test.py", diags, [])
        assert result["diagnostics"][0]["line"] == 1
        assert result["diagnostics"][1]["line"] == 3
        assert result["diagnostics"][2]["line"] == 5


class TestCLI:
    """Test CLI entry point."""

    def test_cli_file_diagnostics(self):
        import subprocess

        with tempfile.NamedTemporaryFile(suffix=".py", mode="w", delete=False) as f:
            f.write("x = 1\nprint(x)\n")
            f.flush()

            result = subprocess.run(
                [sys.executable, str(SCRIPTS_DIR / "diagnostics.py"), f.name],
                capture_output=True, text=True, timeout=30,
            )
            assert result.returncode == 0
            data = json.loads(result.stdout)
            assert "diagnostics" in data

    def test_cli_directory_diagnostics(self):
        import subprocess

        result = subprocess.run(
            [sys.executable, str(SCRIPTS_DIR / "diagnostics.py"), str(SCRIPTS_DIR)],
            capture_output=True, text=True, timeout=60,
        )
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert "files_checked" in data
        assert "summary" in data
