"""AST-grep powered structural code search and transformation engine.

Provides AST-aware pattern matching using the ast-grep-py library.
Supports structural search, anti-pattern detection via YAML rules,
and safe code transformations with dry-run support.

Requires: ast-grep-py (pip install ast-grep-py)

Usage:
    python ast_grep_engine.py search "def $FUNC($$$PARAMS): $$$BODY" /path
    python ast_grep_engine.py anti-patterns /path/to/file.py
    python ast_grep_engine.py anti-patterns /path/to/project/
    python ast_grep_engine.py transform file.py "print($$$A)" "logging.info($$$A)" --dry-run
    python ast_grep_engine.py status
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    from ast_grep_py import SgRoot

    AST_GREP_AVAILABLE = True
except ImportError:
    AST_GREP_AVAILABLE = False


def ast_grep_available() -> bool:
    """Check if ast-grep-py is installed and available."""
    return AST_GREP_AVAILABLE


def _node_to_dict(node: Any, source_file: Optional[str] = None) -> Dict[str, Any]:
    """Convert an SgNode match to a serializable dictionary.

    Args:
        node: An SgNode object from ast-grep-py.
        source_file: Optional file path for context.

    Returns:
        Dictionary with text, kind, range, and matched metavariables.
    """
    rng = node.range()
    result: Dict[str, Any] = {
        "text": node.text(),
        "kind": node.kind(),
        "start_line": rng.start.line + 1,  # Convert to 1-indexed
        "start_col": rng.start.column,
        "end_line": rng.end.line + 1,
        "end_col": rng.end.column,
    }
    if source_file:
        result["file"] = source_file
    return result


def _extract_metavars(node: Any, pattern: str) -> Dict[str, str]:
    """Extract metavariable bindings from a match.

    Scans the pattern for $NAME and $$$NAME tokens and attempts
    to retrieve their matched text from the node.

    Args:
        node: An SgNode match object.
        pattern: The original search pattern.

    Returns:
        Dictionary mapping metavariable names to matched text.
    """
    import re

    metavars: Dict[str, str] = {}
    # Find metavariable names: $$$NAME or $NAME (but not $$)
    for token in re.findall(r"\$\$\$([A-Z_][A-Z0-9_]*)", pattern):
        try:
            mv = node.get_match(token)
            if mv:
                metavars[f"$$${token}"] = mv.text()
        except Exception:
            pass

    for token in re.findall(r"(?<!\$)\$([A-Z_][A-Z0-9_]*)(?!\$)", pattern):
        try:
            mv = node.get_match(token)
            if mv:
                metavars[f"${token}"] = mv.text()
        except Exception:
            pass

    return metavars


def search_code_pattern(
    pattern: str,
    project_path: str,
    language: str = "python",
    max_results: int = 100,
) -> Dict[str, Any]:
    """Search for an AST pattern across Python files in a project.

    Uses ast-grep metavariable syntax:
      - $NAME matches any single AST node
      - $$$ARGS matches multiple nodes (variadic)

    Examples:
      - "def $FUNC($$$PARAMS): $$$BODY" — find all function definitions
      - "try: $$$B except: $$$H" — find bare except blocks
      - "import $MODULE" — find all import statements

    Args:
        pattern: AST pattern with metavariables.
        project_path: Root directory to search.
        language: Language for parsing (default "python").
        max_results: Maximum matches to return (default 100).

    Returns:
        Dictionary with matches list, match_count, and file list.
    """
    if not AST_GREP_AVAILABLE:
        return {
            "error": "ast-grep-py is not installed. Install with: pip install ast-grep-py",
        }

    root = Path(project_path).resolve()
    if not root.is_dir():
        return {"error": f"Not a directory: {project_path}"}

    # Map language to file extension
    ext_map = {
        "python": "*.py",
        "javascript": "*.js",
        "typescript": "*.ts",
        "tsx": "*.tsx",
        "rust": "*.rs",
        "go": "*.go",
    }
    glob = ext_map.get(language, f"*.{language}")

    all_matches: List[Dict[str, Any]] = []
    files_searched = 0
    files_with_matches: List[str] = []

    for filepath in sorted(root.rglob(glob)):
        # Skip common non-source directories
        parts = filepath.parts
        if any(
            p in (".git", "__pycache__", "node_modules", ".venv", "venv", ".tox") for p in parts
        ):
            continue

        files_searched += 1
        try:
            source = filepath.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue

        try:
            sg_root = SgRoot(source, language)
            tree_root = sg_root.root()
            nodes = tree_root.find_all(pattern=pattern)
        except Exception:
            continue

        file_had_match = False
        rel_path = str(filepath.relative_to(root))

        for node in nodes:
            if len(all_matches) >= max_results:
                break

            match_dict = _node_to_dict(node, source_file=rel_path)
            metavars = _extract_metavars(node, pattern)
            if metavars:
                match_dict["metavariables"] = metavars
            all_matches.append(match_dict)
            file_had_match = True

        if file_had_match:
            files_with_matches.append(rel_path)

        if len(all_matches) >= max_results:
            break

    return {
        "pattern": pattern,
        "language": language,
        "project_path": str(root),
        "files_searched": files_searched,
        "files_with_matches": files_with_matches,
        "match_count": len(all_matches),
        "truncated": len(all_matches) >= max_results,
        "matches": all_matches,
    }


def _get_default_rules() -> List[Dict[str, Any]]:
    """Load built-in anti-pattern rules from default_rules.yml.

    Falls back to hardcoded rules if the YAML file is missing or
    PyYAML is not installed.
    """
    rules_path = Path(__file__).resolve().parent / "default_rules.yml"

    if rules_path.exists():
        try:
            import yaml

            with open(rules_path, encoding="utf-8") as f:
                data = yaml.safe_load(f)
            return data.get("rules", [])
        except ImportError:
            pass
        except Exception:
            pass

    # Hardcoded fallback — same rules as default_rules.yml
    return [
        {
            "id": "bare-except",
            "pattern": "try:\n    $$$BODY\nexcept:\n    $$$HANDLER",
            "message": "Bare 'except:' catches all exceptions including KeyboardInterrupt "
            "and SystemExit. Use 'except Exception:' instead.",
            "severity": "warning",
        },
        {
            "id": "assert-without-message",
            "pattern": "assert $COND",
            "message": "Assert without a message makes debugging harder. "
            "Add a descriptive message: assert condition, 'description'.",
            "severity": "info",
        },
        {
            "id": "broad-exception-catch",
            "pattern": "except Exception:\n    $$$HANDLER",
            "message": "Catching bare 'Exception' is too broad. "
            "Catch specific exception types when possible.",
            "severity": "info",
        },
        {
            "id": "print-statement",
            "pattern": "print($$$ARGS)",
            "message": "Consider using the logging module instead of print() for production code.",
            "severity": "info",
        },
        {
            "id": "star-import",
            "pattern": "from $MODULE import *",
            "message": "Wildcard imports pollute the namespace and make it unclear "
            "which names are present. Import specific names instead.",
            "severity": "warning",
        },
    ]


def check_anti_patterns(
    file_path: Optional[str] = None,
    project_path: Optional[str] = None,
    rule_file: Optional[str] = None,
    language: str = "python",
) -> Dict[str, Any]:
    """Check Python files against anti-pattern rules.

    Can check a single file or scan an entire project directory.
    Rules can be loaded from a YAML file or use built-in defaults.

    Args:
        file_path: Path to a single file to check.
        project_path: Path to a project directory to scan.
        rule_file: Path to a custom YAML rules file.
        language: Language for parsing (default "python").

    Returns:
        Dictionary with findings grouped by rule, and summary counts.
    """
    if not AST_GREP_AVAILABLE:
        return {
            "error": "ast-grep-py is not installed. Install with: pip install ast-grep-py",
        }

    if not file_path and not project_path:
        return {"error": "Either file_path or project_path is required"}

    # Load rules
    if rule_file:
        try:
            import yaml

            with open(rule_file, encoding="utf-8") as f:
                data = yaml.safe_load(f)
            rules = data.get("rules", [])
        except ImportError:
            return {"error": "PyYAML is required to load custom rule files: pip install pyyaml"}
        except Exception as e:
            return {"error": f"Failed to load rules file: {e}"}
    else:
        rules = _get_default_rules()

    # Collect files to scan
    files_to_scan: List[Path] = []
    base_path: Path

    if file_path:
        fp = Path(file_path).resolve()
        if not fp.exists():
            return {"error": f"File not found: {file_path}"}
        files_to_scan = [fp]
        base_path = fp.parent
    else:
        base_path = Path(project_path).resolve()  # type: ignore[arg-type]
        if not base_path.is_dir():
            return {"error": f"Not a directory: {project_path}"}

        ext_map = {"python": "*.py"}
        glob = ext_map.get(language, f"*.{language}")

        for p in sorted(base_path.rglob(glob)):
            parts = p.parts
            if any(
                d in (".git", "__pycache__", "node_modules", ".venv", "venv", ".tox") for d in parts
            ):
                continue
            files_to_scan.append(p)

    # Run rules against all files
    all_findings: Dict[str, List[Dict[str, Any]]] = {}
    severity_counts = {"error": 0, "warning": 0, "info": 0}
    files_checked = 0

    for fp in files_to_scan:
        try:
            source = fp.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue

        files_checked += 1

        try:
            sg_root = SgRoot(source, language)
            tree_root = sg_root.root()
        except Exception:
            continue

        try:
            rel_path = str(fp.relative_to(base_path))
        except ValueError:
            rel_path = str(fp)

        for rule in rules:
            rule_id = rule.get("id", "unknown")
            rule_pattern = rule.get("pattern", "")
            rule_message = rule.get("message", "")
            rule_severity = rule.get("severity", "warning")

            if not rule_pattern:
                continue

            try:
                nodes = tree_root.find_all(pattern=rule_pattern)
            except Exception:
                continue

            for node in nodes:
                rng = node.range()
                finding = {
                    "file": rel_path,
                    "line": rng.start.line + 1,
                    "column": rng.start.column,
                    "end_line": rng.end.line + 1,
                    "text": node.text()[:200],  # Truncate long matches
                    "message": rule_message,
                    "severity": rule_severity,
                }
                all_findings.setdefault(rule_id, []).append(finding)
                severity_counts[rule_severity] = severity_counts.get(rule_severity, 0) + 1

    total_findings = sum(len(v) for v in all_findings.values())

    return {
        "files_checked": files_checked,
        "rules_applied": len(rules),
        "total_findings": total_findings,
        "severity_counts": severity_counts,
        "findings": all_findings,
    }


def transform_code(
    file_path: str,
    pattern: str,
    replacement: str,
    language: str = "python",
    dry_run: bool = True,
) -> Dict[str, Any]:
    """Transform code by replacing AST patterns.

    Uses ast-grep to find structural patterns and replace them,
    preserving matched metavariables.

    Example:
        pattern: "print($$$ARGS)"
        replacement: "logging.info($$$ARGS)"

    Args:
        file_path: Path to the file to transform.
        pattern: AST pattern to find (with metavariables).
        replacement: Replacement pattern (can reference metavariables).
        language: Language for parsing (default "python").
        dry_run: If True (default), return preview without modifying file.

    Returns:
        Dictionary with original/transformed code, diff, and match count.
    """
    if not AST_GREP_AVAILABLE:
        return {
            "error": "ast-grep-py is not installed. Install with: pip install ast-grep-py",
        }

    fp = Path(file_path).resolve()
    if not fp.exists():
        return {"error": f"File not found: {file_path}"}

    try:
        original = fp.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as e:
        return {"error": f"Cannot read file: {e}"}

    try:
        sg_root = SgRoot(original, language)
        tree_root = sg_root.root()
        nodes = list(tree_root.find_all(pattern=pattern))
    except Exception as e:
        return {"error": f"Pattern matching failed: {e}"}

    if not nodes:
        return {
            "file": str(fp),
            "pattern": pattern,
            "replacement": replacement,
            "match_count": 0,
            "dry_run": dry_run,
            "message": "No matches found",
        }

    # Apply replacements in reverse order (bottom-up) to preserve positions
    transformed = original
    replacements_made: List[Dict[str, Any]] = []

    # Sort nodes by position in reverse order
    sorted_nodes = sorted(
        nodes, key=lambda n: (n.range().start.line, n.range().start.column), reverse=True
    )

    for node in sorted_nodes:
        rng = node.range()

        # Build the actual replacement text by substituting metavariables
        actual_replacement = replacement
        metavars = _extract_metavars(node, pattern)
        for var_name, var_text in metavars.items():
            actual_replacement = actual_replacement.replace(var_name, var_text)

        # Get character offsets from line/col
        lines = transformed.split("\n")
        start_offset = sum(len(lines[i]) + 1 for i in range(rng.start.line)) + rng.start.column
        end_offset = sum(len(lines[i]) + 1 for i in range(rng.end.line)) + rng.end.column

        replacements_made.append(
            {
                "line": rng.start.line + 1,
                "column": rng.start.column,
                "original_text": node.text()[:200],
                "replacement_text": actual_replacement[:200],
            }
        )

        transformed = transformed[:start_offset] + actual_replacement + transformed[end_offset:]

    # Generate a simple diff
    diff_lines: List[str] = []
    orig_lines = original.split("\n")
    trans_lines = transformed.split("\n")

    for i, (ol, tl) in enumerate(zip(orig_lines, trans_lines)):
        if ol != tl:
            diff_lines.append(f"L{i + 1}:")
            diff_lines.append(f"  - {ol}")
            diff_lines.append(f"  + {tl}")

    result: Dict[str, Any] = {
        "file": str(fp),
        "pattern": pattern,
        "replacement": replacement,
        "match_count": len(nodes),
        "dry_run": dry_run,
        "replacements": list(reversed(replacements_made)),
        "diff": "\n".join(diff_lines) if diff_lines else "No changes",
    }

    if dry_run:
        result["transformed_preview"] = transformed
    else:
        # Write the transformed content
        try:
            fp.write_text(transformed, encoding="utf-8")
            result["written"] = True
        except OSError as e:
            result["error"] = f"Failed to write file: {e}"
            result["written"] = False

    return result


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="AST-grep structural code search engine")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # search
    p_search = subparsers.add_parser("search", help="Search for AST patterns")
    p_search.add_argument("pattern", help="AST pattern with metavariables")
    p_search.add_argument("project_path", help="Project root directory")
    p_search.add_argument("--language", default="python", help="Language (default: python)")
    p_search.add_argument("--max-results", type=int, default=100, help="Max results")

    # anti-patterns
    p_anti = subparsers.add_parser("anti-patterns", help="Check for anti-patterns")
    p_anti.add_argument("path", help="File or project directory to check")
    p_anti.add_argument("--rules", help="Custom YAML rules file")
    p_anti.add_argument("--language", default="python", help="Language (default: python)")

    # transform
    p_trans = subparsers.add_parser("transform", help="Transform code patterns")
    p_trans.add_argument("file_path", help="File to transform")
    p_trans.add_argument("pattern", help="AST pattern to find")
    p_trans.add_argument("replacement", help="Replacement pattern")
    p_trans.add_argument("--language", default="python", help="Language (default: python)")
    p_trans.add_argument(
        "--dry-run", action="store_true", default=True, help="Preview only (default)"
    )
    p_trans.add_argument("--apply", action="store_true", help="Apply changes to file")

    # status
    subparsers.add_parser("status", help="Check ast-grep-py availability")

    args = parser.parse_args()

    if args.command == "status":
        print(
            json.dumps(
                {
                    "ast_grep_available": AST_GREP_AVAILABLE,
                },
                indent=2,
            )
        )
        return

    if args.command == "search":
        result = search_code_pattern(
            pattern=args.pattern,
            project_path=args.project_path,
            language=args.language,
            max_results=args.max_results,
        )
    elif args.command == "anti-patterns":
        target = Path(args.path)
        if target.is_file():
            result = check_anti_patterns(
                file_path=str(target),
                rule_file=args.rules,
                language=args.language,
            )
        else:
            result = check_anti_patterns(
                project_path=str(target),
                rule_file=args.rules,
                language=args.language,
            )
    elif args.command == "transform":
        result = transform_code(
            file_path=args.file_path,
            pattern=args.pattern,
            replacement=args.replacement,
            language=args.language,
            dry_run=not args.apply,
        )
    else:
        result = {"error": f"Unknown command: {args.command}"}

    print(json.dumps(result, indent=2, default=str))


if __name__ == "__main__":
    main()
