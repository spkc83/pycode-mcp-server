"""PyCode MCP Server — Python code intelligence for AI agents.

Exposes local Python environment introspection, documentation lookup,
code analysis, diagnostics, structural code search, and text search
as MCP tools via the FastMCP framework.

Usage:
    python mcp_server.py                  # Run with stdio transport
    python mcp_server.py --transport sse  # Run with SSE transport
"""

from __future__ import annotations

import inspect
import json
import sys
from pathlib import Path
from typing import Optional

# Ensure scripts/ is importable
_SCRIPTS_DIR = Path(__file__).resolve().parent / "scripts"
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))


def _create_mcp_server():
    from mcp.server.fastmcp import FastMCP

    description = (
        "Python code intelligence server providing documentation lookup, "
        "environment introspection, code analysis, and diagnostics "
        "from the local Python runtime."
    )

    kwargs = {}
    try:
        params = inspect.signature(FastMCP).parameters
    except (TypeError, ValueError):
        params = {}

    if "version" in params:
        kwargs["version"] = "5.0.0"
    if "description" in params:
        kwargs["description"] = description

    try:
        return FastMCP("pycode-mcp-server", **kwargs)
    except TypeError:
        return FastMCP("pycode-mcp-server")


# Initialize the MCP server
mcp = _create_mcp_server()


# ---------------------------------------------------------------------------
# Tool: get_local_docs
# ---------------------------------------------------------------------------
@mcp.tool()
def get_local_docs(object_name: str, structured: bool = True) -> str:
    """Look up documentation for a Python object from the local environment.

    Returns signatures, parameters, docstrings, examples, and import
    statements for any importable Python object.

    Args:
        object_name: Fully qualified name, e.g. "json.dumps", "pathlib.Path".
        structured: If True (default), return structured JSON. If False, raw text.
    """
    from doc_lookup import get_local_docs as _get_local_docs

    result = _get_local_docs(object_name, use_cache=True, structured=structured)
    if isinstance(result, dict):
        return json.dumps(result, indent=2, default=str)
    return str(result)


# ---------------------------------------------------------------------------
# Tool: inspect_environment
# ---------------------------------------------------------------------------
@mcp.tool()
def inspect_environment() -> str:
    """Get comprehensive information about the current Python environment.

    Returns Python version, platform, virtualenv status, and a full list
    of installed packages with their versions and import names.
    """
    from inspect_env import get_full_environment

    result = get_full_environment()
    return json.dumps(result, indent=2, default=str)


# ---------------------------------------------------------------------------
# Tool: get_package_details
# ---------------------------------------------------------------------------
@mcp.tool()
def get_package_details(package_name: str) -> str:
    """Get detailed information about a specific installed Python package.

    Returns version, import names, dependencies, main exports, and
    installation location for the given package.

    Args:
        package_name: Package name as listed on PyPI, e.g. "requests", "numpy".
    """
    from inspect_env import get_package_details as _get_details

    result = _get_details(package_name)
    if result is None:
        return json.dumps(
            {"error": f"Package '{package_name}' is not installed"},
            indent=2,
        )
    return json.dumps(result, indent=2, default=str)


# ---------------------------------------------------------------------------
# Tool: find_package_for_import
# ---------------------------------------------------------------------------
@mcp.tool()
def find_package_for_import(import_name: str) -> str:
    """Find which installed PyPI package provides a given import name.

    Useful for resolving 'import X' to the installable package name.

    Args:
        import_name: The module name used in an import statement, e.g. "cv2", "PIL".
    """
    from inspect_env import find_package_by_import
    from inspect_env import get_package_details as _get_details

    pkg_name = find_package_by_import(import_name)
    if pkg_name is None:
        return json.dumps(
            {"error": f"No installed package found for import '{import_name}'"},
            indent=2,
        )
    # Return package details alongside the mapping
    details = _get_details(pkg_name) or {}
    details["matched_import"] = import_name
    return json.dumps(details, indent=2, default=str)


# ---------------------------------------------------------------------------
# Tool: analyze_file
# ---------------------------------------------------------------------------
@mcp.tool()
def analyze_file(file_path: str) -> str:
    """Analyze a Python source file to extract its structure.

    Returns functions, classes, imports, decorators, dependencies,
    and a summary of the file's contents.

    Args:
        file_path: Absolute path to a .py file.
    """
    from code_analyzer import analyze_file as _analyze_file

    result = _analyze_file(file_path)
    return json.dumps(result, indent=2, default=str)


# ---------------------------------------------------------------------------
# Tool: analyze_project
# ---------------------------------------------------------------------------
@mcp.tool()
def analyze_project(
    project_path: str,
    include_import_graph: bool = True,
    include_cycles: bool = True,
) -> str:
    """Perform comprehensive analysis of a Python project directory.

    Returns per-file summaries, import dependency graph, circular
    dependency detection, and stdlib vs third-party classification.

    Args:
        project_path: Absolute path to the project root directory.
        include_import_graph: Whether to include the import dependency graph.
        include_cycles: Whether to detect circular dependencies.
    """
    from project_analyzer import analyze_project as _analyze_project

    result = _analyze_project(
        project_path,
        include_graph=include_import_graph,
        include_cycles=include_cycles,
    )
    return json.dumps(result, indent=2, default=str)


# ---------------------------------------------------------------------------
# Tool: get_diagnostics
# ---------------------------------------------------------------------------
@mcp.tool()
def get_diagnostics(
    file_path: str,
    type_check: bool = False,
) -> str:
    """Run code quality diagnostics on a Python file.

    Combines Jedi syntax checks, Pyflakes analysis (unused imports,
    undefined names), and optionally mypy/pyright type checking.

    Args:
        file_path: Absolute path to a .py file.
        type_check: If True, also run mypy/pyright type checking.
    """
    from diagnostics import run_diagnostics

    result = run_diagnostics(file_path, type_check=type_check)
    return json.dumps(result, indent=2, default=str)


# ---------------------------------------------------------------------------
# Tool: get_install_instructions
# ---------------------------------------------------------------------------
@mcp.tool()
def get_install_instructions(package_name: str, project_path: Optional[str] = None) -> str:
    """Get installation instructions for a Python package.

    Detects the project's package manager (pip, poetry, uv, pipenv)
    and returns the appropriate install command. Also checks if the
    package is already installed.

    Args:
        package_name: The PyPI package name to install, e.g. "requests".
        project_path: Optional project root to detect package manager. Defaults to cwd.
    """
    from inspect_env import get_package_details as _get_details
    from inspect_env import is_package_installed

    result: dict = {"package": package_name}

    # Check if already installed
    if is_package_installed(package_name):
        details = _get_details(package_name)
        result["already_installed"] = True
        result["installed_version"] = details["version"] if details else "unknown"
        result["note"] = f"'{package_name}' is already installed."
    else:
        result["already_installed"] = False

    # Detect package manager
    search_path = Path(project_path) if project_path else Path.cwd()
    pm = _detect_package_manager(search_path)
    result["detected_package_manager"] = pm

    # Generate install command
    commands = {
        "uv": f"uv add {package_name}",
        "poetry": f"poetry add {package_name}",
        "pipenv": f"pipenv install {package_name}",
        "pip": f"pip install {package_name}",
    }
    result["install_command"] = commands.get(pm, f"pip install {package_name}")

    return json.dumps(result, indent=2, default=str)


@mcp.tool()
def prepare_codegen_context(
    object_name: Optional[str] = None,
    package_name: Optional[str] = None,
    import_name: Optional[str] = None,
    project_path: Optional[str] = None,
    min_python: Optional[str] = None,
    package_version_spec: Optional[str] = None,
    budget: str = "medium",
    task_goal: str = "implementation",
) -> str:
    """Build version-aware local context for agent code generation."""
    from codegen_context import prepare_codegen_context as _prepare_codegen_context

    result = _prepare_codegen_context(
        object_name=object_name,
        package_name=package_name,
        import_name=import_name,
        project_path=project_path,
        min_python=min_python,
        package_version_spec=package_version_spec,
        budget=budget,
        task_goal=task_goal,
    )
    return json.dumps(result, indent=2, default=str)


# ---------------------------------------------------------------------------
# Tool: search_text (ripgrep)
# ---------------------------------------------------------------------------
@mcp.tool()
def search_text(
    pattern: str,
    project_path: str,
    file_types: Optional[str] = None,
    context_lines: int = 2,
    max_results: int = 100,
) -> str:
    """Search for a regex pattern across all files using ripgrep.

    Fast text search across all file types — Python, YAML, TOML, Markdown,
    Dockerfiles, etc. Ideal for finding string literals, config keys, TODO
    comments, error messages, and cross-language references that Jedi cannot see.

    Requires ripgrep (rg) installed on the system PATH.

    Args:
        pattern: Regex pattern to search for (e.g. "TODO|FIXME", "DATABASE_URL").
        project_path: Absolute path to the project root directory.
        file_types: Comma-separated ripgrep type filters (e.g. "py", "py,yaml,toml").
        context_lines: Number of context lines around each match (default 2).
        max_results: Maximum number of matches to return (default 100).
    """
    from ripgrep_engine import search_text as _search_text

    result = _search_text(
        pattern=pattern,
        project_path=project_path,
        file_types=file_types,
        context_lines=context_lines,
        max_results=max_results,
    )
    return json.dumps(result, indent=2, default=str)


# ---------------------------------------------------------------------------
# Tool: find_config_references (ripgrep)
# ---------------------------------------------------------------------------
@mcp.tool()
def find_config_references(
    key: str,
    project_path: str,
    file_types: Optional[str] = None,
) -> str:
    """Trace a configuration key across Python, YAML, TOML, ENV, and Docker files.

    Searches for a config key name across all common configuration and source
    file types, then categorizes results by file type. Useful for understanding
    where a setting is defined, read, and used throughout a project.

    Requires ripgrep (rg) installed on the system PATH.

    Args:
        key: Configuration key to search for (e.g. "DATABASE_URL", "SECRET_KEY").
        project_path: Absolute path to the project root directory.
        file_types: Override default file type filters (comma-separated).
    """
    from ripgrep_engine import find_config_references as _find_config_references

    result = _find_config_references(
        key=key,
        project_path=project_path,
        file_types=file_types,
    )
    return json.dumps(result, indent=2, default=str)


# ---------------------------------------------------------------------------
# Tool: search_code_pattern (ast-grep)
# ---------------------------------------------------------------------------
@mcp.tool()
def search_code_pattern(
    pattern: str,
    project_path: str,
    language: str = "python",
) -> str:
    """Search for structural code patterns using AST matching.

    Uses ast-grep metavariable syntax for structural (not textual) matching:
      - $NAME matches any single AST node (identifier, expression, etc.)
      - $$$ARGS matches multiple nodes (variadic — function args, body stmts)

    Examples:
      - "def $FUNC($$$PARAMS): $$$BODY" — all function definitions
      - "try: $$$B except: $$$H" — bare except blocks
      - "import $MODULE" — all import statements
      - "$OBJ.get($KEY)" — all .get() calls

    Requires ast-grep-py (pip install ast-grep-py).

    Args:
        pattern: AST pattern with metavariables.
        project_path: Absolute path to the project root directory.
        language: Target language for parsing (default "python").
    """
    from ast_grep_engine import search_code_pattern as _search_code_pattern

    result = _search_code_pattern(
        pattern=pattern,
        project_path=project_path,
        language=language,
    )
    return json.dumps(result, indent=2, default=str)


# ---------------------------------------------------------------------------
# Tool: check_anti_patterns (ast-grep)
# ---------------------------------------------------------------------------
@mcp.tool()
def check_anti_patterns(
    file_path: Optional[str] = None,
    project_path: Optional[str] = None,
    rule_file: Optional[str] = None,
) -> str:
    """Check Python code against structural anti-pattern rules.

    Runs YAML-defined lint rules using AST matching to detect code smells
    like bare except, assert without message, broad exception catches,
    print statements, and wildcard imports. Provide either a single file
    or a project directory.

    Built-in rules are used by default. Pass a custom YAML rules file
    to define your own patterns.

    Requires ast-grep-py (pip install ast-grep-py).

    Args:
        file_path: Absolute path to a single .py file to check.
        project_path: Absolute path to a project directory to scan.
        rule_file: Optional path to a custom YAML rules file.
    """
    from ast_grep_engine import check_anti_patterns as _check_anti_patterns

    result = _check_anti_patterns(
        file_path=file_path,
        project_path=project_path,
        rule_file=rule_file,
    )
    return json.dumps(result, indent=2, default=str)


# ---------------------------------------------------------------------------
# Tool: transform_code (ast-grep)
# ---------------------------------------------------------------------------
@mcp.tool()
def transform_code(
    file_path: str,
    pattern: str,
    replacement: str,
    dry_run: bool = True,
) -> str:
    """Transform code by replacing structural AST patterns.

    Find structural patterns and replace them, preserving matched
    metavariables. Defaults to dry-run mode (preview only).

    Example: replace print() with logging.info():
      pattern: "print($$$ARGS)"
      replacement: "logging.info($$$ARGS)"

    Requires ast-grep-py (pip install ast-grep-py).

    Args:
        file_path: Absolute path to the file to transform.
        pattern: AST pattern to find (with metavariables).
        replacement: Replacement pattern (can reference metavariables).
        dry_run: If True (default), return preview without modifying file.
    """
    from ast_grep_engine import transform_code as _transform_code

    result = _transform_code(
        file_path=file_path,
        pattern=pattern,
        replacement=replacement,
        dry_run=dry_run,
    )
    return json.dumps(result, indent=2, default=str)


def _detect_package_manager(project_root: Path) -> str:
    # Walk up to find project root markers
    current = project_root.resolve()
    for _ in range(10):  # max 10 levels up
        if (current / "uv.lock").exists():
            return "uv"
        if (current / "poetry.lock").exists():
            return "poetry"
        if (current / "Pipfile").exists():
            return "pipenv"
        if (current / "pyproject.toml").exists():
            # Check if it's a poetry or uv project
            try:
                content = (current / "pyproject.toml").read_text()
                if "[tool.poetry]" in content:
                    return "poetry"
                if "[tool.uv]" in content:
                    return "uv"
            except OSError:
                pass
        parent = current.parent
        if parent == current:
            break
        current = parent
    return "pip"


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------
def main():
    """Run the MCP server."""
    mcp.run()


if __name__ == "__main__":
    main()
