"""Tests for project_analyzer.py — project-level analysis."""

import json
import sys
import tempfile
from pathlib import Path

# Add scripts directory to path
from project_analyzer import (
    STDLIB_MODULES,
    analyze_project,
    build_import_graph,
    classify_dependencies,
    detect_circular_dependencies,
    discover_python_files,
)

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))


class TestFileDiscovery:
    """Test recursive Python file discovery."""

    def test_discover_in_scripts_dir(self):
        files = discover_python_files(SCRIPTS_DIR)
        assert len(files) > 0
        # Should include our scripts
        names = [f.name for f in files]
        assert "jedi_engine.py" in names
        assert "code_analyzer.py" in names
        assert "doc_lookup.py" in names

    def test_discover_with_exclusions(self):
        files = discover_python_files(SCRIPTS_DIR, exclude_patterns=["debug*"])
        names = [f.name for f in files]
        assert "debug_wrapper.py" not in names
        assert "code_analyzer.py" in names

    def test_discover_with_depth(self):
        root = SCRIPTS_DIR.parent
        files_d0 = discover_python_files(root, max_depth=0)
        files_d1 = discover_python_files(root, max_depth=1)
        # Depth 1 should find more files than depth 0
        assert len(files_d1) >= len(files_d0)

    def test_discover_empty_dir(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            files = discover_python_files(Path(tmpdir))
            assert len(files) == 0

    def test_discover_creates_sorted_list(self):
        files = discover_python_files(SCRIPTS_DIR)
        names = [f.name for f in files]
        assert names == sorted(names)

    def test_discover_finds_py_files_only(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            (tmpdir_path / "script.py").write_text("x = 1\n")
            (tmpdir_path / "data.json").write_text("{}\n")
            (tmpdir_path / "readme.md").write_text("# Hi\n")

            files = discover_python_files(tmpdir_path)
            assert len(files) == 1
            assert files[0].name == "script.py"


class TestImportGraph:
    """Test import graph construction."""

    def test_build_graph_from_scripts(self):
        files = discover_python_files(SCRIPTS_DIR)
        graph = build_import_graph(SCRIPTS_DIR, files)
        assert isinstance(graph, dict)
        assert len(graph) > 0

    def test_graph_detects_local_imports(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            (tmpdir_path / "a.py").write_text("from b import helper\n")
            (tmpdir_path / "b.py").write_text("def helper(): pass\n")

            files = discover_python_files(tmpdir_path)
            graph = build_import_graph(tmpdir_path, files)
            assert "a" in graph
            assert "b" in graph["a"]

    def test_graph_ignores_stdlib(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            (tmpdir_path / "app.py").write_text("import os\nimport json\n")

            files = discover_python_files(tmpdir_path)
            graph = build_import_graph(tmpdir_path, files)
            # os and json are stdlib, not local, so should not be in deps
            assert graph.get("app", []) == []


class TestCircularDependencies:
    """Test circular dependency detection."""

    def test_no_cycles(self):
        graph = {"a": ["b"], "b": ["c"], "c": []}
        cycles = detect_circular_dependencies(graph)
        assert len(cycles) == 0

    def test_simple_cycle(self):
        graph = {"a": ["b"], "b": ["a"]}
        cycles = detect_circular_dependencies(graph)
        assert len(cycles) > 0

    def test_self_cycle(self):
        graph = {"a": ["a"]}
        cycles = detect_circular_dependencies(graph)
        assert len(cycles) > 0

    def test_complex_cycle(self):
        graph = {"a": ["b"], "b": ["c"], "c": ["a"], "d": []}
        cycles = detect_circular_dependencies(graph)
        assert len(cycles) > 0
        # The cycle should involve a, b, c
        cycle_modules = set()
        for cycle in cycles:
            cycle_modules.update(cycle)
        assert "a" in cycle_modules
        assert "b" in cycle_modules
        assert "c" in cycle_modules


class TestDependencyClassification:
    """Test dependency classification."""

    def test_classifies_stdlib(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            (tmpdir_path / "app.py").write_text("import os\nimport json\nimport sys\n")

            files = discover_python_files(tmpdir_path)
            result = classify_dependencies(files)
            assert "os" in result["stdlib"]
            assert "json" in result["stdlib"]
            assert "sys" in result["stdlib"]

    def test_classifies_third_party(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            (tmpdir_path / "app.py").write_text("import pandas\nimport numpy\n")

            files = discover_python_files(tmpdir_path)
            result = classify_dependencies(files)
            assert "pandas" in result["third_party"]
            assert "numpy" in result["third_party"]


class TestStdlibModulesComprehensive:
    """Test that the stdlib modules set is comprehensive."""

    def test_common_stdlib_modules(self):
        common = [
            "os",
            "sys",
            "json",
            "re",
            "typing",
            "pathlib",
            "collections",
            "functools",
            "itertools",
            "datetime",
            "time",
            "math",
            "random",
            "hashlib",
            "base64",
            "urllib",
            "http",
            "email",
            "html",
            "xml",
            "logging",
            "unittest",
            "ast",
            "inspect",
            "importlib",
            "contextlib",
            "dataclasses",
            "enum",
            "abc",
            "copy",
            "pickle",
            "io",
            "tempfile",
            "shutil",
            "glob",
            "fnmatch",
            "argparse",
            "configparser",
            "csv",
            "sqlite3",
            "threading",
            "multiprocessing",
            "subprocess",
            "socket",
            "ssl",
            "asyncio",
            "concurrent",
            "queue",
        ]
        for mod in common:
            assert mod in STDLIB_MODULES, f"{mod} should be in stdlib set"

    def test_previously_missing_stdlib_modules(self):
        """These were missing from the old hardcoded list."""
        previously_missing = [
            "struct",
            "array",
            "textwrap",
            "pdb",
            "traceback",
            "warnings",
            "signal",
            "zipfile",
            "tarfile",
            "gzip",
            "bz2",
            "lzma",
            "decimal",
            "fractions",
            "statistics",
            "string",
            "difflib",
            "pprint",
            "dis",
            "token",
            "tokenize",
            "builtins",
            "__future__",
        ]
        for mod in previously_missing:
            assert mod in STDLIB_MODULES, f"{mod} should be in stdlib set"


class TestProjectAnalysis:
    """Test full project analysis."""

    def test_analyze_scripts_dir(self):
        result = analyze_project(str(SCRIPTS_DIR), include_cross_refs=False)
        assert "files" in result
        assert "summary" in result
        assert result["summary"]["total_files"] > 0
        assert result["summary"]["total_functions"] > 0

    def test_analyze_with_exclusions(self):
        result = analyze_project(
            str(SCRIPTS_DIR),
            exclude_patterns=["debug*", "health*"],
            include_cross_refs=False,
        )
        file_names = [f["path"] for f in result["files"]]
        assert not any("debug" in n for n in file_names)
        assert not any("health" in n for n in file_names)

    def test_analyze_nonexistent_dir(self):
        result = analyze_project("/nonexistent/path")
        assert "error" in result

    def test_analyze_empty_dir(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            result = analyze_project(tmpdir)
            assert "error" in result

    def test_analyze_includes_import_graph(self):
        result = analyze_project(str(SCRIPTS_DIR), include_cross_refs=False)
        assert "import_graph" in result
        assert isinstance(result["import_graph"], dict)

    def test_analyze_includes_dependencies(self):
        result = analyze_project(str(SCRIPTS_DIR), include_cross_refs=False)
        assert "stdlib_dependencies" in result
        assert "third_party_dependencies" in result
        assert isinstance(result["stdlib_dependencies"], list)

    def test_analyze_temp_project(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            (tmpdir_path / "main.py").write_text(
                "import json\nfrom utils import helper\n\ndef main():\n    return helper()\n"
            )
            (tmpdir_path / "utils.py").write_text("def helper():\n    return 42\n")

            result = analyze_project(tmpdir, include_cross_refs=False)
            assert result["summary"]["total_files"] == 2
            assert result["summary"]["total_functions"] == 2

            # Import graph should show main depends on utils
            graph = result["import_graph"]
            assert "utils" in graph.get("main", [])


class TestCLI:
    """Test CLI entry point."""

    def test_cli_full_analysis(self):
        import subprocess

        result = subprocess.run(
            [sys.executable, str(SCRIPTS_DIR / "project_analyzer.py"), str(SCRIPTS_DIR)],
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert "summary" in data
        assert data["summary"]["total_files"] > 0

    def test_cli_graph_only(self):
        import subprocess

        result = subprocess.run(
            [sys.executable, str(SCRIPTS_DIR / "project_analyzer.py"), str(SCRIPTS_DIR), "--graph"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert isinstance(data, dict)

    def test_cli_cycles_only(self):
        import subprocess

        result = subprocess.run(
            [
                sys.executable,
                str(SCRIPTS_DIR / "project_analyzer.py"),
                str(SCRIPTS_DIR),
                "--cycles",
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert isinstance(data, list)
