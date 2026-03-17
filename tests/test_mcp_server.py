"""Integration tests for the MCP server tool functions.

These tests verify the MCP tool functions work correctly by calling
the underlying Python functions directly (not over MCP transport).
For full MCP protocol testing, use the MCP Inspector.
"""

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))
sys.path.insert(0, str(ROOT))


class TestGetLocalDocs:
    """Test the get_local_docs MCP tool."""

    def test_builtin_type(self):
        from mcp_server import get_local_docs

        result = json.loads(get_local_docs("str"))
        assert result["found"] is True
        assert result["name"] == "str"

    def test_stdlib_function(self):
        from mcp_server import get_local_docs

        result = json.loads(get_local_docs("json.dumps"))
        assert result["found"] is True
        assert "signature" in result

    def test_not_found(self):
        from mcp_server import get_local_docs

        result = json.loads(get_local_docs("nonexistent_xyz_123"))
        assert result["found"] is False

    def test_raw_mode(self):
        from mcp_server import get_local_docs

        result = get_local_docs("str", structured=False)
        assert isinstance(result, str)
        assert len(result) > 0


class TestInspectEnvironment:
    """Test the inspect_environment MCP tool."""

    def test_returns_valid_json(self):
        from mcp_server import inspect_environment

        result = json.loads(inspect_environment())
        assert "environment" in result
        assert "packages" in result
        assert "package_count" in result

    def test_has_python_version(self):
        from mcp_server import inspect_environment

        result = json.loads(inspect_environment())
        assert "python_version" in result["environment"]


class TestGetPackageDetails:
    """Test the get_package_details MCP tool."""

    def test_installed_package(self):
        from mcp_server import get_package_details

        result = json.loads(get_package_details("pytest"))
        assert result["name"].lower() == "pytest"
        assert "version" in result

    def test_not_installed_package(self):
        from mcp_server import get_package_details

        result = json.loads(get_package_details("nonexistent_xyz_123"))
        assert "error" in result


class TestFindPackageForImport:
    """Test the find_package_for_import MCP tool."""

    def test_known_import(self):
        from mcp_server import find_package_for_import

        result = json.loads(find_package_for_import("pytest"))
        assert "matched_import" in result
        assert result["matched_import"] == "pytest"

    def test_unknown_import(self):
        from mcp_server import find_package_for_import

        result = json.loads(find_package_for_import("nonexistent_xyz_123"))
        assert "error" in result


class TestAnalyzeFile:
    """Test the analyze_file MCP tool."""

    def test_analyze_python_file(self, tmp_path):
        from mcp_server import analyze_file

        test_file = tmp_path / "sample.py"
        test_file.write_text("def hello():\n    return 'world'\n")

        result = json.loads(analyze_file(str(test_file)))
        assert "functions" in result
        assert result["functions"][0]["name"] == "hello"


class TestGetDiagnostics:
    """Test the get_diagnostics MCP tool."""

    def test_clean_file(self, tmp_path):
        from mcp_server import get_diagnostics

        test_file = tmp_path / "clean.py"
        test_file.write_text("x = 1\n")

        result = json.loads(get_diagnostics(str(test_file)))
        assert "diagnostics" in result
        assert "summary" in result

    def test_nonexistent_file(self):
        from mcp_server import get_diagnostics

        result = json.loads(get_diagnostics("/tmp/does_not_exist_xyz.py"))
        assert "error" in result


class TestGetInstallInstructions:
    """Test the get_install_instructions MCP tool."""

    def test_installed_package(self):
        from mcp_server import get_install_instructions

        result = json.loads(get_install_instructions("pytest"))
        assert result["already_installed"] is True
        assert "install_command" in result

    def test_not_installed_package(self):
        from mcp_server import get_install_instructions

        result = json.loads(get_install_instructions("some_unlikely_package_xyz"))
        assert result["already_installed"] is False
        assert "install_command" in result

    def test_detects_package_manager(self, tmp_path):
        from mcp_server import get_install_instructions

        # Create a poetry-style project
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text("[tool.poetry]\nname = 'test'\n")

        result = json.loads(
            get_install_instructions("requests", project_path=str(tmp_path))
        )
        assert result["detected_package_manager"] == "poetry"
        assert "poetry add" in result["install_command"]
