"""Unified diagnostics engine combining Jedi, Pyflakes, and mypy/pyright.

Provides a single interface for code quality diagnostics from multiple
analysis sources, with graceful degradation when tools are unavailable.

Usage:
    python diagnostics.py file.py
    python diagnostics.py file.py --syntax-only
    python diagnostics.py file.py --type-check
    python diagnostics.py /path/to/project/ --summary
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

_SCRIPTS_DIR = Path(__file__).resolve().parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))


def _check_tool_available(tool: str) -> bool:
    """Check if a CLI tool is available on PATH."""
    try:
        result = subprocess.run(
            [tool, "--version"],
            capture_output=True, text=True, timeout=10
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def get_jedi_diagnostics(source: str, path: Optional[str] = None) -> List[Dict[str, Any]]:
    """Get syntax error diagnostics from Jedi.

    Args:
        source: Python source code string.
        path: Optional file path for context.

    Returns:
        List of diagnostic dictionaries.
    """
    try:
        from jedi_engine import get_diagnostics, jedi_available
        if not jedi_available():
            return []
        return get_diagnostics(source=source, path=path)
    except ImportError:
        return []


def get_pyflakes_diagnostics(source: str, filepath: Optional[str] = None) -> List[Dict[str, Any]]:
    """Get diagnostics from Pyflakes (undefined names, unused imports, etc).

    Runs Pyflakes as a subprocess for isolation.

    Args:
        source: Python source code string.
        filepath: File path to pass to Pyflakes.

    Returns:
        List of diagnostic dictionaries.
    """
    diagnostics: List[Dict[str, Any]] = []

    # Try programmatic API first
    try:
        from pyflakes.api import check as pyflakes_check
        from io import StringIO

        warnings_io = StringIO()
        filename = filepath or "<stdin>"
        pyflakes_check(source, filename, reporter=type(
            'Reporter', (), {
                'unexpectedError': lambda self, fn, msg: warnings_io.write(f"{fn}:0:0: E {msg}\n"),
                'syntaxError': lambda self, fn, msg, lineno, offset, text: warnings_io.write(
                    f"{fn}:{lineno}:{offset}: E {msg}\n"
                ),
                'flake': lambda self, msg: warnings_io.write(f"{msg}\n"),
            }
        )())

        output = warnings_io.getvalue()
        for line in output.strip().split('\n'):
            if not line:
                continue
            diag = _parse_pyflakes_line(line)
            if diag:
                diagnostics.append(diag)
        return diagnostics

    except ImportError:
        pass

    # Fallback: subprocess
    if not _check_tool_available("pyflakes"):
        return []

    try:
        result = subprocess.run(
            ["pyflakes"],
            input=source,
            capture_output=True, text=True, timeout=30,
        )
        for line in result.stdout.strip().split('\n'):
            if not line:
                continue
            diag = _parse_pyflakes_line(line)
            if diag:
                diagnostics.append(diag)
    except (subprocess.TimeoutExpired, OSError):
        pass

    return diagnostics


def _parse_pyflakes_line(line: str) -> Optional[Dict[str, Any]]:
    """Parse a single pyflakes output line into a diagnostic dict."""
    # Format: filename:line:col: message  or  filename:line: message
    parts = line.split(':', 3)
    if len(parts) < 3:
        return None

    try:
        line_num = int(parts[1])
    except ValueError:
        return None

    col = 0
    message = ""
    if len(parts) >= 4:
        try:
            col = int(parts[2])
            message = parts[3].strip()
        except ValueError:
            message = ':'.join(parts[2:]).strip()
    else:
        message = parts[2].strip()

    # Determine severity
    severity = "warning"
    if "undefined" in message.lower() or "syntax" in message.lower():
        severity = "error"

    return {
        "line": line_num,
        "column": col,
        "severity": severity,
        "source": "pyflakes",
        "message": message,
    }


def get_mypy_diagnostics(filepath: str) -> List[Dict[str, Any]]:
    """Get type-checking diagnostics from mypy.

    Args:
        filepath: Path to the Python file.

    Returns:
        List of diagnostic dictionaries.
    """
    if not _check_tool_available("mypy"):
        return []

    diagnostics: List[Dict[str, Any]] = []

    try:
        result = subprocess.run(
            ["mypy", "--no-color-output", "--no-error-summary",
             "--show-column-numbers", filepath],
            capture_output=True, text=True, timeout=60,
        )

        for line in result.stdout.strip().split('\n'):
            if not line:
                continue
            diag = _parse_mypy_line(line)
            if diag:
                diagnostics.append(diag)
    except (subprocess.TimeoutExpired, OSError):
        pass

    return diagnostics


def _parse_mypy_line(line: str) -> Optional[Dict[str, Any]]:
    """Parse a single mypy output line into a diagnostic dict."""
    # Format: filename:line:col: severity: message
    parts = line.split(':', 4)
    if len(parts) < 4:
        return None

    try:
        line_num = int(parts[1])
    except ValueError:
        return None

    col = 0
    severity_str = ""
    message = ""

    if len(parts) >= 5:
        try:
            col = int(parts[2])
            severity_str = parts[3].strip()
            message = parts[4].strip()
        except ValueError:
            severity_str = parts[2].strip()
            message = ':'.join(parts[3:]).strip()
    else:
        severity_str = parts[2].strip()
        message = parts[3].strip() if len(parts) > 3 else ""

    severity = "error" if "error" in severity_str else "warning"
    if "note" in severity_str:
        severity = "info"

    return {
        "line": line_num,
        "column": col,
        "severity": severity,
        "source": "mypy",
        "message": message,
    }


def get_pyright_diagnostics(filepath: str) -> List[Dict[str, Any]]:
    """Get type-checking diagnostics from pyright.

    Falls back to pyright if mypy is not available.

    Args:
        filepath: Path to the Python file.

    Returns:
        List of diagnostic dictionaries.
    """
    if not _check_tool_available("pyright"):
        return []

    diagnostics: List[Dict[str, Any]] = []

    try:
        result = subprocess.run(
            ["pyright", "--outputjson", filepath],
            capture_output=True, text=True, timeout=60,
        )

        try:
            data = json.loads(result.stdout)
            for diag_data in data.get("generalDiagnostics", []):
                rng = diag_data.get("range", {}).get("start", {})
                diagnostics.append({
                    "line": rng.get("line", 0) + 1,  # pyright uses 0-indexed
                    "column": rng.get("character", 0),
                    "severity": diag_data.get("severity", "error"),
                    "source": "pyright",
                    "message": diag_data.get("message", ""),
                    "rule": diag_data.get("rule", ""),
                })
        except json.JSONDecodeError:
            pass
    except (subprocess.TimeoutExpired, OSError):
        pass

    return diagnostics


def run_diagnostics(
    filepath: str,
    syntax_only: bool = False,
    type_check: bool = False,
) -> Dict[str, Any]:
    """Run all available diagnostics on a file.

    Args:
        filepath: Path to the Python file.
        syntax_only: Only run Jedi syntax checks.
        type_check: Include type-checking (mypy/pyright).

    Returns:
        Dictionary with file path, diagnostics list, and summary.
    """
    file_path = Path(filepath)

    if not file_path.exists():
        return {"error": f"File not found: {filepath}"}

    if not file_path.suffix == '.py':
        return {"error": f"Not a Python file: {filepath}"}

    try:
        source = file_path.read_text(encoding='utf-8')
    except (OSError, UnicodeDecodeError) as e:
        return {"error": f"Cannot read file: {e}"}

    all_diagnostics: List[Dict[str, Any]] = []
    sources_used: List[str] = []

    # 1. Jedi syntax errors (always)
    jedi_diags = get_jedi_diagnostics(source, filepath)
    if jedi_diags:
        all_diagnostics.extend([d for d in jedi_diags if "error" not in d])
        sources_used.append("jedi")

    if syntax_only:
        return _build_result(filepath, all_diagnostics, sources_used)

    # 2. Pyflakes (undefined names, unused imports)
    pyflakes_diags = get_pyflakes_diagnostics(source, filepath)
    if pyflakes_diags:
        all_diagnostics.extend(pyflakes_diags)
        sources_used.append("pyflakes")

    # 3. Type checking (optional)
    if type_check:
        mypy_diags = get_mypy_diagnostics(filepath)
        if mypy_diags:
            all_diagnostics.extend(mypy_diags)
            sources_used.append("mypy")
        else:
            # Try pyright as fallback
            pyright_diags = get_pyright_diagnostics(filepath)
            if pyright_diags:
                all_diagnostics.extend(pyright_diags)
                sources_used.append("pyright")

    return _build_result(filepath, all_diagnostics, sources_used)


def _build_result(filepath: str, diagnostics: List[Dict[str, Any]],
                  sources: List[str]) -> Dict[str, Any]:
    """Build the final diagnostics result dictionary."""
    # Sort by line number
    diagnostics.sort(key=lambda d: (d.get("line", 0), d.get("column", 0)))

    errors = sum(1 for d in diagnostics if d.get("severity") == "error")
    warnings = sum(1 for d in diagnostics if d.get("severity") == "warning")
    info = sum(1 for d in diagnostics if d.get("severity") == "info")

    return {
        "file": filepath,
        "diagnostics": diagnostics,
        "sources_used": sources,
        "summary": {
            "total": len(diagnostics),
            "errors": errors,
            "warnings": warnings,
            "info": info,
        },
    }


def run_project_diagnostics(
    project_path: str,
    exclude_patterns: Optional[List[str]] = None,
    type_check: bool = False,
) -> Dict[str, Any]:
    """Run diagnostics across an entire project.

    Args:
        project_path: Root directory of the project.
        exclude_patterns: Glob patterns to exclude.
        type_check: Include type-checking.

    Returns:
        Dictionary with per-file diagnostics and project summary.
    """
    from project_analyzer import discover_python_files

    root = Path(project_path).resolve()
    if not root.is_dir():
        return {"error": f"Not a directory: {project_path}"}

    files = discover_python_files(root, exclude_patterns)
    if not files:
        return {"error": f"No Python files found in: {project_path}"}

    file_results: List[Dict[str, Any]] = []
    total_errors = 0
    total_warnings = 0

    for f in files:
        result = run_diagnostics(str(f), type_check=type_check)
        summary = result.get("summary", {})
        error_count = summary.get("errors", 0)
        warning_count = summary.get("warnings", 0)

        if error_count > 0 or warning_count > 0:
            file_results.append({
                "file": str(f.relative_to(root)),
                "errors": error_count,
                "warnings": warning_count,
                "diagnostics": result.get("diagnostics", []),
            })

        total_errors += error_count
        total_warnings += warning_count

    return {
        "project_root": str(root),
        "files_checked": len(files),
        "files_with_issues": len(file_results),
        "file_results": file_results,
        "summary": {
            "total_errors": total_errors,
            "total_warnings": total_warnings,
        },
        "tools_available": {
            "jedi": _is_jedi_available(),
            "pyflakes": _check_tool_available("pyflakes"),
            "mypy": _check_tool_available("mypy"),
            "pyright": _check_tool_available("pyright"),
        },
    }


def _is_jedi_available() -> bool:
    """Check if Jedi is available."""
    try:
        from jedi_engine import jedi_available
        return jedi_available()
    except ImportError:
        return False


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(
        description="Unified Python diagnostics engine"
    )
    parser.add_argument("path", help="Path to Python file or project directory")
    parser.add_argument("--syntax-only", action="store_true",
                        help="Only check for syntax errors")
    parser.add_argument("--type-check", action="store_true",
                        help="Include type checking (mypy/pyright)")
    parser.add_argument("--summary", action="store_true",
                        help="Project-wide diagnostic summary")

    args = parser.parse_args()

    target = Path(args.path)

    if target.is_dir() or args.summary:
        exclude = ["__pycache__", "*.egg-info", ".git"]
        result = run_project_diagnostics(
            str(target),
            exclude_patterns=exclude,
            type_check=args.type_check,
        )
    else:
        result = run_diagnostics(
            str(target),
            syntax_only=args.syntax_only,
            type_check=args.type_check,
        )

    print(json.dumps(result, indent=2, default=str))


if __name__ == "__main__":
    main()
