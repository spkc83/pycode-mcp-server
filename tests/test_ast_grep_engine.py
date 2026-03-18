import sys
from pathlib import Path
from unittest.mock import patch

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))
sys.path.insert(0, str(ROOT))

from ast_grep_engine import (  # noqa: E402
    AST_GREP_AVAILABLE,
    _get_default_rules,
    ast_grep_available,
    check_anti_patterns,
    search_code_pattern,
    transform_code,
)

requires_ast_grep = pytest.mark.skipif(
    not AST_GREP_AVAILABLE,
    reason="ast-grep-py is not installed",
)


class TestAstGrepAvailability:
    def test_returns_bool(self):
        result = ast_grep_available()
        assert isinstance(result, bool)

    def test_matches_import_flag(self):
        assert ast_grep_available() == AST_GREP_AVAILABLE


class TestGracefulDegradation:
    def test_search_code_pattern_error(self, tmp_path):
        with patch("ast_grep_engine.AST_GREP_AVAILABLE", False):
            result = search_code_pattern("def $F($$$P): $$$B", str(tmp_path))
            assert "error" in result
            assert "not installed" in result["error"]

    def test_check_anti_patterns_error(self, tmp_path):
        with patch("ast_grep_engine.AST_GREP_AVAILABLE", False):
            result = check_anti_patterns(project_path=str(tmp_path))
            assert "error" in result
            assert "not installed" in result["error"]

    def test_transform_code_error(self, tmp_path):
        f = tmp_path / "test.py"
        f.write_text("x = 1\n")
        with patch("ast_grep_engine.AST_GREP_AVAILABLE", False):
            result = transform_code(str(f), "print($A)", "log($A)")
            assert "error" in result
            assert "not installed" in result["error"]


class TestDefaultRules:
    def test_returns_list(self):
        rules = _get_default_rules()
        assert isinstance(rules, list)
        assert len(rules) > 0

    def test_rules_have_required_fields(self):
        rules = _get_default_rules()
        for rule in rules:
            assert "id" in rule
            assert "pattern" in rule
            assert "message" in rule
            assert "severity" in rule

    def test_known_rule_ids(self):
        rules = _get_default_rules()
        rule_ids = {r["id"] for r in rules}
        assert "bare-except" in rule_ids
        assert "print-statement" in rule_ids
        assert "star-import" in rule_ids

    def test_at_least_five_rules(self):
        rules = _get_default_rules()
        assert len(rules) >= 5


class TestSearchCodePattern:
    def test_error_for_invalid_directory(self):
        if not AST_GREP_AVAILABLE:
            pytest.skip("ast-grep-py not installed")
        result = search_code_pattern("def $F(): $$$B", "/nonexistent/xyz")
        assert "error" in result

    def test_empty_project(self, tmp_path):
        if not AST_GREP_AVAILABLE:
            pytest.skip("ast-grep-py not installed")
        result = search_code_pattern("def $F(): $$$B", str(tmp_path))
        assert result["match_count"] == 0
        assert result["files_searched"] == 0

    @requires_ast_grep
    def test_finds_function_definitions(self, tmp_path):
        src = tmp_path / "example.py"
        src.write_text("def hello():\n    return 'world'\n\ndef greet(name):\n    print(name)\n")

        result = search_code_pattern("def $FUNC($$$PARAMS):\n    $$$BODY", str(tmp_path))
        assert result["match_count"] >= 1
        assert result["files_searched"] >= 1
        assert len(result["files_with_matches"]) >= 1

    @requires_ast_grep
    def test_finds_import_statements(self, tmp_path):
        src = tmp_path / "imports.py"
        src.write_text("import os\nimport sys\nimport json\n")

        result = search_code_pattern("import $MODULE", str(tmp_path))
        assert result["match_count"] >= 1

    @requires_ast_grep
    def test_skips_pycache_dirs(self, tmp_path):
        cache_dir = tmp_path / "__pycache__"
        cache_dir.mkdir()
        (cache_dir / "cached.py").write_text("def cached(): pass\n")

        src = tmp_path / "real.py"
        src.write_text("def real(): pass\n")

        result = search_code_pattern("def $F(): $$$B", str(tmp_path))
        for m in result.get("matches", []):
            assert "__pycache__" not in m.get("file", "")

    @requires_ast_grep
    def test_result_structure(self, tmp_path):
        (tmp_path / "a.py").write_text("x = 1\n")
        result = search_code_pattern("$X = 1", str(tmp_path))
        assert "pattern" in result
        assert "language" in result
        assert "project_path" in result
        assert "files_searched" in result
        assert "match_count" in result
        assert "truncated" in result
        assert "matches" in result


class TestCheckAntiPatterns:
    def test_requires_file_or_project(self):
        if not AST_GREP_AVAILABLE:
            pytest.skip("ast-grep-py not installed")
        result = check_anti_patterns()
        assert "error" in result
        assert "required" in result["error"]

    def test_error_for_missing_file(self):
        if not AST_GREP_AVAILABLE:
            pytest.skip("ast-grep-py not installed")
        result = check_anti_patterns(file_path="/nonexistent/file.py")
        assert "error" in result

    def test_error_for_missing_directory(self):
        if not AST_GREP_AVAILABLE:
            pytest.skip("ast-grep-py not installed")
        result = check_anti_patterns(project_path="/nonexistent/dir")
        assert "error" in result

    @requires_ast_grep
    def test_detects_bare_except(self, tmp_path):
        f = tmp_path / "bad.py"
        f.write_text("try:\n    x = 1\nexcept:\n    pass\n")

        result = check_anti_patterns(file_path=str(f))
        assert result["files_checked"] == 1
        assert result["rules_applied"] >= 1
        assert "findings" in result
        assert "severity_counts" in result

    @requires_ast_grep
    def test_detects_print_statement(self, tmp_path):
        f = tmp_path / "prints.py"
        f.write_text("print('hello')\nprint('world')\n")

        result = check_anti_patterns(file_path=str(f))
        if "print-statement" in result.get("findings", {}):
            assert len(result["findings"]["print-statement"]) >= 1

    @requires_ast_grep
    def test_detects_star_import(self, tmp_path):
        f = tmp_path / "star.py"
        f.write_text("from os import *\n")

        result = check_anti_patterns(file_path=str(f))
        if "star-import" in result.get("findings", {}):
            assert len(result["findings"]["star-import"]) >= 1

    @requires_ast_grep
    def test_scans_project_directory(self, tmp_path):
        (tmp_path / "a.py").write_text("print('a')\n")
        (tmp_path / "b.py").write_text("print('b')\n")

        result = check_anti_patterns(project_path=str(tmp_path))
        assert result["files_checked"] == 2

    @requires_ast_grep
    def test_clean_file_zero_findings(self, tmp_path):
        f = tmp_path / "clean.py"
        f.write_text("import os\n\nx = os.getcwd()\n")

        result = check_anti_patterns(file_path=str(f))
        assert result["total_findings"] == 0

    @requires_ast_grep
    def test_result_structure(self, tmp_path):
        f = tmp_path / "any.py"
        f.write_text("x = 1\n")

        result = check_anti_patterns(file_path=str(f))
        assert "files_checked" in result
        assert "rules_applied" in result
        assert "total_findings" in result
        assert "severity_counts" in result
        assert "findings" in result


class TestTransformCode:
    def test_error_for_missing_file(self):
        if not AST_GREP_AVAILABLE:
            pytest.skip("ast-grep-py not installed")
        result = transform_code("/nonexistent/file.py", "print($A)", "log($A)")
        assert "error" in result

    @requires_ast_grep
    def test_no_matches_returns_zero_count(self, tmp_path):
        f = tmp_path / "clean.py"
        f.write_text("x = 1\ny = 2\n")

        result = transform_code(str(f), "print($A)", "log($A)")
        assert result["match_count"] == 0
        assert "No matches" in result["message"]

    @requires_ast_grep
    def test_dry_run_does_not_modify_file(self, tmp_path):
        f = tmp_path / "code.py"
        original = "print('hello')\n"
        f.write_text(original)

        result = transform_code(str(f), "print($$$ARGS)", "logging.info($$$ARGS)", dry_run=True)
        assert result["dry_run"] is True
        assert f.read_text() == original
        if result["match_count"] > 0:
            assert "transformed_preview" in result

    @requires_ast_grep
    def test_apply_modifies_file(self, tmp_path):
        f = tmp_path / "code.py"
        f.write_text("print('hello')\n")

        result = transform_code(str(f), "print($$$ARGS)", "logging.info($$$ARGS)", dry_run=False)
        if result["match_count"] > 0:
            assert result.get("written") is True
            new_content = f.read_text()
            assert "logging.info" in new_content

    @requires_ast_grep
    def test_result_structure(self, tmp_path):
        f = tmp_path / "s.py"
        f.write_text("x = 1\n")

        result = transform_code(str(f), "print($A)", "log($A)")
        assert "file" in result
        assert "pattern" in result
        assert "replacement" in result
        assert "match_count" in result
        assert "dry_run" in result

    @requires_ast_grep
    def test_diff_output(self, tmp_path):
        f = tmp_path / "d.py"
        f.write_text("print('diff test')\n")

        result = transform_code(str(f), "print($$$ARGS)", "logging.info($$$ARGS)", dry_run=True)
        if result["match_count"] > 0:
            assert "diff" in result
            assert "replacements" in result
