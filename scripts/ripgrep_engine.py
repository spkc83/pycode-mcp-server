"""Ripgrep-powered text search engine for cross-file pattern matching.

Provides fast regex-based text search across all file types using ripgrep
as a subprocess. Parses JSON output for structured results.

Requires: ripgrep (rg) installed and on PATH.
    Install: https://github.com/BurntSushi/ripgrep#installation

Usage:
    python ripgrep_engine.py search "pattern" /path/to/project
    python ripgrep_engine.py search "TODO|FIXME" /path --file-types py
    python ripgrep_engine.py config-refs "DATABASE_URL" /path
    python ripgrep_engine.py status
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional


def ripgrep_available() -> bool:
    """Check if ripgrep (rg) is installed and available on PATH."""
    try:
        result = subprocess.run(
            ["rg", "--version"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def get_ripgrep_version() -> Optional[str]:
    """Get the installed ripgrep version string."""
    try:
        result = subprocess.run(
            ["rg", "--version"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0:
            # Output format: "ripgrep X.Y.Z ..."
            return result.stdout.strip().split("\n")[0]
        return None
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None


def _parse_rg_json_output(stdout: str) -> List[Dict[str, Any]]:
    """Parse ripgrep --json output into structured match results.

    Ripgrep JSON output is newline-delimited JSON with message types:
    - "begin": start of a file
    - "match": a matching line
    - "end": end of a file
    - "summary": search summary

    Args:
        stdout: Raw stdout from ripgrep --json.

    Returns:
        List of match dictionaries with file, line, text, and submatches.
    """
    matches: List[Dict[str, Any]] = []

    for line in stdout.strip().split("\n"):
        if not line:
            continue
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            continue

        if msg.get("type") != "match":
            continue

        data = msg.get("data", {})
        path_info = data.get("path", {})
        file_path = path_info.get("text", "")
        line_number = data.get("line_number", 0)
        line_text = data.get("lines", {}).get("text", "").rstrip("\n")

        submatches = []
        for sm in data.get("submatches", []):
            submatches.append(
                {
                    "match": sm.get("match", {}).get("text", ""),
                    "start": sm.get("start", 0),
                    "end": sm.get("end", 0),
                }
            )

        matches.append(
            {
                "file": file_path,
                "line": line_number,
                "text": line_text,
                "submatches": submatches,
            }
        )

    return matches


def search_text(
    pattern: str,
    project_path: str,
    file_types: Optional[str] = None,
    context_lines: int = 2,
    max_results: int = 100,
    case_sensitive: bool = True,
    glob_pattern: Optional[str] = None,
) -> Dict[str, Any]:
    """Search for a regex pattern across files using ripgrep.

    Args:
        pattern: Regex pattern to search for.
        project_path: Root directory to search.
        file_types: Comma-separated ripgrep type filters (e.g. "py,yaml,toml").
        context_lines: Number of context lines around matches (default 2).
        max_results: Maximum number of matches to return (default 100).
        case_sensitive: Whether the search is case-sensitive (default True).
        glob_pattern: Glob pattern to filter files (e.g. "*.py").

    Returns:
        Dictionary with matches list, match_count, and truncated flag.
    """
    if not ripgrep_available():
        return {
            "error": "ripgrep (rg) is not installed. Install from: "
            "https://github.com/BurntSushi/ripgrep#installation",
        }

    root = Path(project_path).resolve()
    if not root.is_dir():
        return {"error": f"Not a directory: {project_path}"}

    cmd: List[str] = ["rg", "--json"]

    if not case_sensitive:
        cmd.append("--ignore-case")

    if context_lines > 0:
        cmd.extend(["--context", str(context_lines)])

    # File type filtering
    if file_types:
        for ft in file_types.split(","):
            ft = ft.strip()
            if ft:
                cmd.extend(["--type", ft])

    if glob_pattern:
        cmd.extend(["--glob", glob_pattern])

    # Max count — request slightly more to detect truncation
    cmd.extend(["--max-count", str(max_results + 1)])

    cmd.append(pattern)
    cmd.append(str(root))

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=60,
            cwd=str(root),
        )
    except subprocess.TimeoutExpired:
        return {"error": "Search timed out after 60 seconds"}
    except FileNotFoundError:
        return {"error": "ripgrep (rg) not found on PATH"}

    # rg returns exit code 1 for "no matches" — not an error
    if result.returncode not in (0, 1):
        stderr = result.stderr.strip()
        return {"error": f"ripgrep error (exit {result.returncode}): {stderr}"}

    all_matches = _parse_rg_json_output(result.stdout)

    truncated = len(all_matches) > max_results
    matches = all_matches[:max_results]

    # Make paths relative to project root
    for m in matches:
        try:
            m["file"] = str(Path(m["file"]).relative_to(root))
        except ValueError:
            pass

    return {
        "pattern": pattern,
        "project_path": str(root),
        "match_count": len(matches),
        "truncated": truncated,
        "matches": matches,
    }


def find_config_references(
    key: str,
    project_path: str,
    file_types: Optional[str] = None,
) -> Dict[str, Any]:
    """Trace a configuration key across Python, YAML, TOML, ENV, and Docker files.

    Searches for a config key name across all common configuration and source
    file types. Useful for understanding where a setting is defined, read,
    and used throughout a project.

    Args:
        key: Configuration key to search for (e.g. "DATABASE_URL", "debug").
        project_path: Root directory to search.
        file_types: Override file types (comma-separated). Default searches
                     py, yaml, yml, toml, env, cfg, ini, json, dockerfile.

    Returns:
        Dictionary with categorized results by file type.
    """
    if not ripgrep_available():
        return {
            "error": "ripgrep (rg) is not installed. Install from: "
            "https://github.com/BurntSushi/ripgrep#installation",
        }

    root = Path(project_path).resolve()
    if not root.is_dir():
        return {"error": f"Not a directory: {project_path}"}

    # Default config-relevant file patterns
    default_globs = [
        "*.py",
        "*.yaml",
        "*.yml",
        "*.toml",
        "*.env",
        "*.env.*",
        "*.cfg",
        "*.ini",
        "*.json",
        "Dockerfile",
        "Dockerfile.*",
        "docker-compose*.yml",
        "docker-compose*.yaml",
        "*.conf",
        "*.properties",
    ]

    cmd: List[str] = ["rg", "--json", "--ignore-case"]

    if file_types:
        for ft in file_types.split(","):
            ft = ft.strip()
            if ft:
                cmd.extend(["--type", ft])
    else:
        for g in default_globs:
            cmd.extend(["--glob", g])

    cmd.append(key)
    cmd.append(str(root))

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=60,
            cwd=str(root),
        )
    except subprocess.TimeoutExpired:
        return {"error": "Search timed out after 60 seconds"}
    except FileNotFoundError:
        return {"error": "ripgrep (rg) not found on PATH"}

    if result.returncode not in (0, 1):
        stderr = result.stderr.strip()
        return {"error": f"ripgrep error (exit {result.returncode}): {stderr}"}

    all_matches = _parse_rg_json_output(result.stdout)

    # Make paths relative and categorize by file extension
    categorized: Dict[str, List[Dict[str, Any]]] = {}
    for m in all_matches:
        try:
            rel = str(Path(m["file"]).relative_to(root))
            m["file"] = rel
        except ValueError:
            rel = m["file"]

        ext = Path(rel).suffix.lstrip(".") or Path(rel).name.lower()
        category = _classify_config_file(ext, rel)
        categorized.setdefault(category, []).append(m)

    return {
        "key": key,
        "project_path": str(root),
        "total_references": len(all_matches),
        "categories": categorized,
        "category_counts": {k: len(v) for k, v in categorized.items()},
    }


def _classify_config_file(ext: str, filename: str) -> str:
    """Classify a file into a config category based on extension/name."""
    lower_name = filename.lower()
    if ext == "py":
        return "python"
    if ext in ("yaml", "yml"):
        if "docker-compose" in lower_name:
            return "docker-compose"
        return "yaml"
    if ext == "toml":
        return "toml"
    if ext in ("env",) or ".env" in lower_name:
        return "env"
    if ext in ("cfg", "ini", "conf", "properties"):
        return "config"
    if ext == "json":
        return "json"
    if "dockerfile" in lower_name:
        return "docker"
    return "other"


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Ripgrep-powered text search engine")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # search
    p_search = subparsers.add_parser("search", help="Search for a regex pattern")
    p_search.add_argument("pattern", help="Regex pattern to search for")
    p_search.add_argument("project_path", help="Project root directory")
    p_search.add_argument("--file-types", help="Comma-separated rg type filters")
    p_search.add_argument("--context", type=int, default=2, help="Context lines")
    p_search.add_argument("--max-results", type=int, default=100, help="Max results")
    p_search.add_argument("--ignore-case", action="store_true", help="Case insensitive")
    p_search.add_argument("--glob", help="Glob pattern to filter files")

    # config-refs
    p_config = subparsers.add_parser("config-refs", help="Trace config key references")
    p_config.add_argument("key", help="Config key to search for")
    p_config.add_argument("project_path", help="Project root directory")
    p_config.add_argument("--file-types", help="Override file type filters")

    # status
    subparsers.add_parser("status", help="Check ripgrep availability")

    args = parser.parse_args()

    if args.command == "status":
        print(
            json.dumps(
                {
                    "ripgrep_available": ripgrep_available(),
                    "version": get_ripgrep_version(),
                },
                indent=2,
            )
        )
        return

    if args.command == "search":
        result = search_text(
            pattern=args.pattern,
            project_path=args.project_path,
            file_types=args.file_types,
            context_lines=args.context,
            max_results=args.max_results,
            case_sensitive=not args.ignore_case,
            glob_pattern=args.glob,
        )
    elif args.command == "config-refs":
        result = find_config_references(
            key=args.key,
            project_path=args.project_path,
            file_types=args.file_types,
        )
    else:
        result = {"error": f"Unknown command: {args.command}"}

    print(json.dumps(result, indent=2, default=str))


if __name__ == "__main__":
    main()
