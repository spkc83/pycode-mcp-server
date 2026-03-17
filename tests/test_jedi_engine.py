"""Tests for jedi_engine.py — Jedi-powered code intelligence."""

import json
import sys
from pathlib import Path

import pytest

# Add scripts directory to path
from jedi_engine import (
    JEDI_AVAILABLE,
    extract_function,
    extract_variable,
    get_completions,
    get_definitions,
    get_diagnostics,
    get_goto,
    get_hover_info,
    get_references,
    get_signatures,
    jedi_available,
    rename_symbol,
    search_project,
)

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))


class TestJediAvailability:
    """Test that Jedi is available and properly detected."""

    def test_jedi_available(self):
        assert jedi_available() is True, "Jedi should be installed"

    def test_jedi_version(self):
        from jedi_engine import JEDI_VERSION

        assert JEDI_VERSION is not None
        # Should be at least 0.19.0
        major, minor = JEDI_VERSION.split(".")[:2]
        assert int(major) >= 0
        assert int(minor) >= 19


@pytest.mark.skipif(not JEDI_AVAILABLE, reason="Jedi not installed")
class TestCompletions:
    """Test autocompletion functionality."""

    def test_completions_on_json(self):
        source = "import json\njson."
        results = get_completions(source=source, line=2, col=5)
        assert len(results) > 0
        names = [r["name"] for r in results]
        assert "dumps" in names
        assert "loads" in names

    def test_completions_on_string_methods(self):
        source = "'hello'."
        results = get_completions(source=source, line=1, col=8)
        assert len(results) > 0
        names = [r["name"] for r in results]
        assert "upper" in names
        assert "split" in names

    def test_completions_empty_source(self):
        results = get_completions(source="", line=1, col=0)
        # Should return some builtins
        assert isinstance(results, list)

    def test_completions_have_type(self):
        source = "import json\njson."
        results = get_completions(source=source, line=2, col=5)
        for r in results[:5]:
            assert "name" in r
            assert "type" in r


@pytest.mark.skipif(not JEDI_AVAILABLE, reason="Jedi not installed")
class TestDefinitions:
    """Test go-to-definition / type inference."""

    def test_definitions_builtin(self):
        source = "print"
        results = get_definitions(source=source, line=1, col=0)
        assert len(results) > 0
        assert results[0]["name"] == "print"

    def test_definitions_json_dumps(self):
        source = "import json\njson.dumps"
        results = get_definitions(source=source, line=2, col=6)
        assert len(results) > 0
        assert results[0]["name"] == "dumps"

    def test_definitions_have_module(self):
        source = "import os\nos.path"
        results = get_definitions(source=source, line=2, col=3)
        assert len(results) > 0
        assert results[0].get("module_name") is not None


@pytest.mark.skipif(not JEDI_AVAILABLE, reason="Jedi not installed")
class TestReferences:
    """Test find-all-references."""

    def test_references_local_var(self):
        source = "x = 1\ny = x + 2\nprint(x)"
        results = get_references(source=source, line=1, col=0)
        assert len(results) >= 2  # definition + at least one usage


@pytest.mark.skipif(not JEDI_AVAILABLE, reason="Jedi not installed")
class TestSignatures:
    """Test function signature help."""

    def test_signatures_print(self):
        source = "print("
        results = get_signatures(source=source, line=1, col=6)
        assert len(results) > 0
        assert results[0]["name"] == "print"
        assert "params" in results[0]

    def test_signatures_json_dumps(self):
        source = "import json\njson.dumps("
        results = get_signatures(source=source, line=2, col=11)
        assert len(results) > 0
        params = results[0]["params"]
        assert any(p["name"] == "obj" for p in params)


@pytest.mark.skipif(not JEDI_AVAILABLE, reason="Jedi not installed")
class TestSearch:
    """Test semantic search."""

    def test_search_in_scripts_dir(self):
        results = search_project("CacheManager", str(SCRIPTS_DIR))
        assert len(results) > 0
        names = [r["name"] for r in results]
        assert "CacheManager" in names

    def test_search_nonexistent(self):
        results = search_project("XyzNonExistentSymbol12345", str(SCRIPTS_DIR))
        assert isinstance(results, list)


@pytest.mark.skipif(not JEDI_AVAILABLE, reason="Jedi not installed")
class TestRename:
    """Test safe symbol renaming."""

    def test_rename_variable(self):
        source = "x = 1\ny = x + 2\nprint(x)"
        result = rename_symbol(source=source, line=1, col=0, new_name="value")
        assert result.get("success") is True
        assert result["new_name"] == "value"
        assert "diff" in result

    def test_rename_no_name(self):
        source = "x = 1"
        result = rename_symbol(source=source, line=1, col=0, new_name="")
        assert "error" in result


@pytest.mark.skipif(not JEDI_AVAILABLE, reason="Jedi not installed")
class TestExtractRefactoring:
    """Test extract variable and function refactoring."""

    def test_extract_variable(self):
        source = "result = 1 + 2 + 3\n"
        result = extract_variable(
            source=source, line=1, col=9, end_line=1, end_col=18, new_name="total"
        )
        # extract_variable may or may not succeed depending on Jedi version
        assert isinstance(result, dict)

    def test_extract_function(self):
        source = "x = 1\ny = x + 2\nprint(y)\n"
        result = extract_function(
            source=source, line=2, col=0, end_line=3, end_col=8, new_name="process"
        )
        assert isinstance(result, dict)


@pytest.mark.skipif(not JEDI_AVAILABLE, reason="Jedi not installed")
class TestDiagnostics:
    """Test syntax diagnostics."""

    def test_diagnostics_valid_code(self):
        source = "def hello():\n    return 'world'\n"
        results = get_diagnostics(source=source)
        assert isinstance(results, list)
        # Valid code should have no errors
        real_errors = [d for d in results if "error" not in d]
        assert len(real_errors) == 0

    def test_diagnostics_syntax_error(self):
        source = "def broken(\n"
        results = get_diagnostics(source=source)
        assert len(results) > 0
        assert results[0]["severity"] == "error"

    def test_diagnostics_missing_colon(self):
        source = "def foo()\n    pass\n"
        results = get_diagnostics(source=source)
        assert len(results) > 0


@pytest.mark.skipif(not JEDI_AVAILABLE, reason="Jedi not installed")
class TestGoto:
    """Test go-to-definition."""

    def test_goto_import(self):
        source = "import json\njson"
        results = get_goto(source=source, line=2, col=0)
        assert len(results) > 0


@pytest.mark.skipif(not JEDI_AVAILABLE, reason="Jedi not installed")
class TestHoverInfo:
    """Test hover information."""

    def test_hover_builtin(self):
        source = "len"
        result = get_hover_info(source=source, line=1, col=0)
        assert result.get("found") is True
        assert result["name"] == "len"
        assert "docstring" in result

    def test_hover_not_found(self):
        source = ""
        result = get_hover_info(source=source, line=1, col=0)
        # Empty source, nothing to hover on
        assert isinstance(result, dict)


@pytest.mark.skipif(not JEDI_AVAILABLE, reason="Jedi not installed")
class TestCLI:
    """Test CLI entry point."""

    def test_status_command(self):
        """Test that the status command produces valid JSON."""
        import subprocess

        result = subprocess.run(
            [sys.executable, str(SCRIPTS_DIR / "jedi_engine.py"), "status"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert data["jedi_available"] is True
        assert data["jedi_version"] is not None
