"""Integration tests for the MCP server tool functions.

These tests verify the MCP tool functions work correctly by calling
the underlying Python functions directly (not over MCP transport).
For full MCP protocol testing, use the MCP Inspector.
"""

import json
import sys
from pathlib import Path

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

        result = json.loads(get_install_instructions("requests", project_path=str(tmp_path)))
        assert result["detected_package_manager"] == "poetry"
        assert "poetry add" in result["install_command"]


class TestPrepareCodegenContext:
    def test_includes_docs_and_environment(self):
        from mcp_server import prepare_codegen_context

        result = json.loads(
            prepare_codegen_context(
                object_name="json.dumps",
                package_name="json",
                budget="medium",
            )
        )
        assert "environment" in result
        assert "docs" in result
        assert result["docs"]["found"] is True
        assert "signature" in result["docs"]

    def test_short_budget_reduces_payload(self):
        from mcp_server import prepare_codegen_context

        result = json.loads(
            prepare_codegen_context(
                object_name="json.dumps",
                package_name="json",
                budget="short",
            )
        )
        docs = result["docs"]
        assert "full_docstring" not in docs
        assert "signature" in docs
        assert result["agent_contract"]["budget_mode"] == "short"

    def test_reports_missing_package_with_install_instruction(self):
        from mcp_server import prepare_codegen_context

        result = json.loads(
            prepare_codegen_context(
                package_name="some_unlikely_package_xyz",
                budget="medium",
            )
        )
        assert result["install"] is not None
        assert "install_command" in result["install"]
        assert result["compatibility"]["is_compatible"] is False

    def test_flags_python_version_incompatibility(self):
        from mcp_server import prepare_codegen_context

        result = json.loads(
            prepare_codegen_context(
                object_name="json.dumps",
                min_python="99.0",
                budget="medium",
            )
        )
        assert result["compatibility"]["python"]["checked"] is True
        assert result["compatibility"]["python"]["compatible"] is False

    def test_goal_shaping_for_debugging(self):
        from mcp_server import prepare_codegen_context

        result = json.loads(
            prepare_codegen_context(
                object_name="json.dumps",
                task_goal="debugging",
                budget="medium",
            )
        )
        assert result["task_goal"] == "debugging"
        assert "signature" in result["docs"]

    def test_invalid_task_goal_raises(self):
        from mcp_server import prepare_codegen_context

        try:
            prepare_codegen_context(object_name="json.dumps", task_goal="invalid_goal")
            raised = False
        except ValueError:
            raised = True
        assert raised is True


class TestSearchTextMCP:
    def test_returns_valid_json(self, tmp_path):
        from mcp_server import search_text

        result = json.loads(search_text(pattern="TODO", project_path=str(tmp_path)))
        assert isinstance(result, dict)

    def test_returns_error_without_ripgrep(self, tmp_path):
        from mcp_server import search_text

        result = json.loads(search_text(pattern="test", project_path=str(tmp_path)))
        if "error" in result:
            assert "ripgrep" in result["error"].lower() or "rg" in result["error"].lower()
        else:
            assert "matches" in result or "total_matches" in result

    def test_nonexistent_path(self):
        from mcp_server import search_text

        result = json.loads(search_text(pattern="x", project_path="/tmp/nonexistent_dir_xyz_12345"))
        assert "error" in result


class TestFindConfigReferencesMCP:
    def test_returns_valid_json(self, tmp_path):
        from mcp_server import find_config_references

        result = json.loads(find_config_references(key="DATABASE_URL", project_path=str(tmp_path)))
        assert isinstance(result, dict)

    def test_returns_error_without_ripgrep(self, tmp_path):
        from mcp_server import find_config_references

        result = json.loads(find_config_references(key="SECRET_KEY", project_path=str(tmp_path)))
        if "error" in result:
            assert "ripgrep" in result["error"].lower() or "rg" in result["error"].lower()
        else:
            assert "categories" in result or "total_matches" in result


class TestSearchCodePatternMCP:
    def test_returns_valid_json(self, tmp_path):
        from mcp_server import search_code_pattern

        test_file = tmp_path / "sample.py"
        test_file.write_text("def hello():\n    pass\n")

        result = json.loads(
            search_code_pattern(pattern="def $FUNC($$$PARAMS): $$$BODY", project_path=str(tmp_path))
        )
        assert isinstance(result, dict)

    def test_returns_error_without_ast_grep(self, tmp_path):
        from mcp_server import search_code_pattern

        test_file = tmp_path / "sample.py"
        test_file.write_text("x = 1\n")

        result = json.loads(search_code_pattern(pattern="$X = 1", project_path=str(tmp_path)))
        if "error" in result:
            assert "ast-grep" in result["error"].lower() or "ast_grep" in result["error"].lower()
        else:
            assert "matches" in result or "total_matches" in result


class TestCheckAntiPatternsMCP:
    def test_returns_valid_json_for_file(self, tmp_path):
        from mcp_server import check_anti_patterns

        test_file = tmp_path / "sample.py"
        test_file.write_text("try:\n    pass\nexcept:\n    pass\n")

        result = json.loads(check_anti_patterns(file_path=str(test_file)))
        assert isinstance(result, dict)

    def test_returns_valid_json_for_project(self, tmp_path):
        from mcp_server import check_anti_patterns

        test_file = tmp_path / "sample.py"
        test_file.write_text("import *\n")

        result = json.loads(check_anti_patterns(project_path=str(tmp_path)))
        assert isinstance(result, dict)

    def test_returns_error_without_ast_grep(self, tmp_path):
        from mcp_server import check_anti_patterns

        test_file = tmp_path / "sample.py"
        test_file.write_text("x = 1\n")

        result = json.loads(check_anti_patterns(file_path=str(test_file)))
        if "error" in result:
            assert "ast-grep" in result["error"].lower() or "ast_grep" in result["error"].lower()
        else:
            assert "findings" in result or "total_findings" in result


class TestTransformCodeMCP:
    def test_returns_valid_json(self, tmp_path):
        from mcp_server import transform_code

        test_file = tmp_path / "sample.py"
        test_file.write_text("print('hello')\n")

        result = json.loads(
            transform_code(
                file_path=str(test_file),
                pattern="print($$$ARGS)",
                replacement="logging.info($$$ARGS)",
                dry_run=True,
            )
        )
        assert isinstance(result, dict)

    def test_dry_run_does_not_modify_file(self, tmp_path):
        from mcp_server import transform_code

        test_file = tmp_path / "sample.py"
        original = "print('hello')\n"
        test_file.write_text(original)

        json.loads(
            transform_code(
                file_path=str(test_file),
                pattern="print($$$ARGS)",
                replacement="logging.info($$$ARGS)",
                dry_run=True,
            )
        )
        assert test_file.read_text() == original

    def test_returns_error_without_ast_grep(self, tmp_path):
        from mcp_server import transform_code

        test_file = tmp_path / "sample.py"
        test_file.write_text("x = 1\n")

        result = json.loads(
            transform_code(
                file_path=str(test_file),
                pattern="$X = 1",
                replacement="$X = 2",
                dry_run=True,
            )
        )
        if "error" in result:
            assert "ast-grep" in result["error"].lower() or "ast_grep" in result["error"].lower()
        else:
            assert "dry_run" in result or "diff" in result or "changes" in result
