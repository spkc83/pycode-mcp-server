"""PyCode MCP Server — Python code intelligence for AI agents.

Exposes local Python environment introspection, documentation lookup,
code analysis, and diagnostics as MCP tools via the FastMCP framework.

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
        kwargs["version"] = "4.0.0"
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


def _detect_package_manager(project_root: Path) -> str:
    """Detect which package manager a project uses."""
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
