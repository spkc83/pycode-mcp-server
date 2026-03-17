"""Project-level code analysis with import graphs and cross-references.

Recursively analyzes Python projects to build import dependency graphs,
detect circular dependencies, create cross-reference indexes, and
generate project-wide summaries.

Usage:
    python project_analyzer.py /path/to/project
    python project_analyzer.py /path/to/project --exclude "test*,docs"
    python project_analyzer.py /path/to/project --graph
    python project_analyzer.py /path/to/project --cycles
"""

from __future__ import annotations

import ast
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

_SCRIPTS_DIR = Path(__file__).resolve().parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from code_analyzer import analyze_source


def _get_stdlib_modules() -> Set[str]:
    """Get a comprehensive set of standard library module names."""
    if hasattr(sys, 'stdlib_module_names'):
        return set(sys.stdlib_module_names)

    # Comprehensive fallback for Python 3.9
    return {
        '__future__', '_thread', 'abc', 'aifc', 'argparse', 'array', 'ast',
        'asynchat', 'asyncio', 'asyncore', 'atexit', 'audioop', 'base64',
        'bdb', 'binascii', 'binhex', 'bisect', 'builtins', 'bz2',
        'calendar', 'cgi', 'cgitb', 'chunk', 'cmath', 'cmd', 'code',
        'codecs', 'codeop', 'collections', 'colorsys', 'compileall',
        'concurrent', 'configparser', 'contextlib', 'contextvars', 'copy',
        'copyreg', 'cProfile', 'crypt', 'csv', 'ctypes', 'curses',
        'dataclasses', 'datetime', 'dbm', 'decimal', 'difflib', 'dis',
        'distutils', 'doctest', 'email', 'encodings', 'enum', 'errno',
        'faulthandler', 'fcntl', 'filecmp', 'fileinput', 'fnmatch',
        'fractions', 'ftplib', 'functools', 'gc', 'getopt', 'getpass',
        'gettext', 'glob', 'graphlib', 'grp', 'gzip', 'hashlib', 'heapq',
        'hmac', 'html', 'http', 'idlelib', 'imaplib', 'imghdr', 'imp',
        'importlib', 'inspect', 'io', 'ipaddress', 'itertools', 'json',
        'keyword', 'lib2to3', 'linecache', 'locale', 'logging', 'lzma',
        'mailbox', 'mailcap', 'marshal', 'math', 'mimetypes', 'mmap',
        'modulefinder', 'multiprocessing', 'netrc', 'nis', 'nntplib',
        'numbers', 'operator', 'optparse', 'os', 'ossaudiodev',
        'pathlib', 'pdb', 'pickle', 'pickletools', 'pipes', 'pkgutil',
        'platform', 'plistlib', 'poplib', 'posix', 'posixpath', 'pprint',
        'profile', 'pstats', 'pty', 'pwd', 'py_compile', 'pyclbr',
        'pydoc', 'queue', 'quopri', 'random', 're', 'readline', 'reprlib',
        'resource', 'rlcompleter', 'runpy', 'sched', 'secrets', 'select',
        'selectors', 'shelve', 'shlex', 'shutil', 'signal', 'site',
        'smtpd', 'smtplib', 'sndhdr', 'socket', 'socketserver', 'sqlite3',
        'ssl', 'stat', 'statistics', 'string', 'stringprep', 'struct',
        'subprocess', 'sunau', 'symtable', 'sys', 'sysconfig', 'syslog',
        'tabnanny', 'tarfile', 'telnetlib', 'tempfile', 'termios', 'test',
        'textwrap', 'threading', 'time', 'timeit', 'tkinter', 'token',
        'tokenize', 'trace', 'traceback', 'tracemalloc', 'tty', 'turtle',
        'turtledemo', 'types', 'typing', 'unicodedata', 'unittest',
        'urllib', 'uu', 'uuid', 'venv', 'warnings', 'wave', 'weakref',
        'webbrowser', 'winreg', 'winsound', 'wsgiref', 'xdrlib', 'xml',
        'xmlrpc', 'zipapp', 'zipfile', 'zipimport', 'zlib',
        '_io', '_collections_abc', 'typing_extensions',
    }


STDLIB_MODULES = _get_stdlib_modules()


def discover_python_files(
    root: Path,
    exclude_patterns: Optional[List[str]] = None,
    max_depth: Optional[int] = None,
) -> List[Path]:
    """Recursively discover Python files in a directory.

    Args:
        root: Root directory to scan.
        exclude_patterns: Glob patterns to exclude (e.g., ["test*", "docs"]).
        max_depth: Maximum directory depth to traverse.

    Returns:
        Sorted list of .py file paths.
    """
    exclude_patterns = exclude_patterns or []
    files: List[Path] = []

    def _should_exclude(p: Path) -> bool:
        for pattern in exclude_patterns:
            if p.match(pattern) or p.name.startswith('.'):
                return True
        return False

    def _scan(directory: Path, depth: int) -> None:
        if max_depth is not None and depth > max_depth:
            return
        try:
            for entry in sorted(directory.iterdir()):
                if _should_exclude(entry):
                    continue
                if entry.is_file() and entry.suffix in ('.py', '.pyi'):
                    files.append(entry)
                elif entry.is_dir() and not entry.name.startswith('__'):
                    _scan(entry, depth + 1)
        except PermissionError:
            pass

    _scan(root, 0)
    return files


def _extract_imports_from_source(source: str) -> Tuple[List[str], List[Dict[str, Any]]]:
    """Extract import information from source code using AST.

    Returns:
        Tuple of (module_imports, from_imports).
    """
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return [], []

    module_imports = []
    from_imports = []

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                module_imports.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                from_imports.append({
                    "module": node.module,
                    "names": [a.name for a in node.names],
                    "level": node.level,
                })

    return module_imports, from_imports


def _path_to_module_name(file_path: Path, root: Path) -> str:
    """Convert a file path to a Python module name relative to root."""
    try:
        rel = file_path.relative_to(root)
    except ValueError:
        return file_path.stem

    parts = list(rel.parts)
    if parts[-1] == '__init__.py':
        parts = parts[:-1]
    else:
        parts[-1] = parts[-1].replace('.py', '').replace('.pyi', '')

    return '.'.join(parts)


def build_import_graph(
    root: Path,
    files: List[Path],
) -> Dict[str, List[str]]:
    """Build a directed import dependency graph.

    Args:
        root: Project root directory.
        files: List of Python files to analyze.

    Returns:
        Dictionary mapping module name -> list of imported module names.
    """
    # Build a set of known local modules
    local_modules: Set[str] = set()
    for f in files:
        mod_name = _path_to_module_name(f, root)
        local_modules.add(mod_name)
        parts = mod_name.split('.')
        for i in range(1, len(parts)):
            local_modules.add('.'.join(parts[:i]))

    graph: Dict[str, List[str]] = {}

    for f in files:
        mod_name = _path_to_module_name(f, root)
        try:
            source = f.read_text(encoding='utf-8')
        except (OSError, UnicodeDecodeError):
            continue

        module_imports, from_imports = _extract_imports_from_source(source)
        deps: List[str] = []

        for imp in module_imports:
            top_level = imp.split('.')[0]
            if top_level in local_modules or imp in local_modules:
                deps.append(imp)

        for fi in from_imports:
            if fi["level"] > 0:
                # Relative import — part of this project
                deps.append(fi["module"])
            else:
                top_level = fi["module"].split('.')[0]
                if top_level in local_modules or fi["module"] in local_modules:
                    deps.append(fi["module"])

        graph[mod_name] = sorted(set(deps))

    return graph


def detect_circular_dependencies(graph: Dict[str, List[str]]) -> List[List[str]]:
    """Detect circular dependency chains in an import graph.

    Args:
        graph: Import graph (module -> [dependencies]).

    Returns:
        List of cycles, each cycle is a list of module names.
    """
    cycles: List[List[str]] = []
    visited: Set[str] = set()
    rec_stack: Set[str] = set()

    def _dfs(node: str, path: List[str]) -> None:
        visited.add(node)
        rec_stack.add(node)
        path.append(node)

        for neighbor in graph.get(node, []):
            if neighbor not in visited:
                _dfs(neighbor, path)
            elif neighbor in rec_stack:
                # Found a cycle
                cycle_start = path.index(neighbor)
                cycle = path[cycle_start:] + [neighbor]
                # Normalize: start from the smallest element
                min_idx = cycle.index(min(cycle[:-1]))
                normalized = cycle[min_idx:-1] + cycle[:min_idx] + [cycle[min_idx]]
                if normalized not in cycles:
                    cycles.append(normalized)

        path.pop()
        rec_stack.discard(node)

    for node in graph:
        if node not in visited:
            _dfs(node, [])

    return cycles


def classify_dependencies(
    files: List[Path],
) -> Dict[str, List[str]]:
    """Classify all imports as stdlib, third-party, or local.

    Returns:
        Dictionary with keys: stdlib, third_party, local.
    """
    all_imports: Set[str] = set()

    for f in files:
        try:
            source = f.read_text(encoding='utf-8')
        except (OSError, UnicodeDecodeError):
            continue

        module_imports, from_imports = _extract_imports_from_source(source)

        for imp in module_imports:
            all_imports.add(imp.split('.')[0])

        for fi in from_imports:
            if fi["level"] == 0 and fi["module"]:
                all_imports.add(fi["module"].split('.')[0])

    stdlib = sorted([m for m in all_imports if m in STDLIB_MODULES])
    third_party = sorted([m for m in all_imports if m not in STDLIB_MODULES and m])

    return {
        "stdlib": stdlib,
        "third_party": third_party,
    }


def analyze_project(
    root: str,
    exclude_patterns: Optional[List[str]] = None,
    max_depth: Optional[int] = None,
    include_graph: bool = True,
    include_cycles: bool = True,
    include_cross_refs: bool = False,
) -> Dict[str, Any]:
    """Perform comprehensive project-level analysis.

    Args:
        root: Project root directory path.
        exclude_patterns: Glob patterns to exclude.
        max_depth: Maximum directory depth.
        include_graph: Whether to include the import graph.
        include_cycles: Whether to detect circular dependencies.
        include_cross_refs: Whether to include cross-references (slower, uses Jedi).

    Returns:
        Dictionary with files, import_graph, cycles, dependencies, and summary.
    """
    root_path = Path(root).resolve()
    if not root_path.is_dir():
        return {"error": f"Not a directory: {root}"}

    files = discover_python_files(root_path, exclude_patterns, max_depth)

    if not files:
        return {"error": f"No Python files found in: {root}"}

    result: Dict[str, Any] = {
        "project_root": str(root_path),
        "files": [],
    }

    # Per-file analysis
    total_functions = 0
    total_classes = 0
    total_lines = 0
    total_imports = 0

    for f in files:
        try:
            source = f.read_text(encoding='utf-8')
        except (OSError, UnicodeDecodeError):
            continue

        line_count = source.count('\n') + 1
        total_lines += line_count

        try:
            analysis = analyze_source(source)
        except SyntaxError:
            result["files"].append({
                "path": str(f.relative_to(root_path)),
                "error": "SyntaxError",
                "lines": line_count,
            })
            continue

        func_count = len(analysis.get("functions", []))
        class_count = len(analysis.get("classes", []))
        import_count = analysis.get("summary", {}).get("total_imports", 0)

        total_functions += func_count
        total_classes += class_count
        total_imports += import_count

        file_info: Dict[str, Any] = {
            "path": str(f.relative_to(root_path)),
            "lines": line_count,
            "functions": func_count,
            "classes": class_count,
        }

        if analysis.get("module_description"):
            file_info["description"] = analysis["module_description"]

        if analysis.get("third_party_dependencies"):
            file_info["third_party_dependencies"] = analysis["third_party_dependencies"]

        result["files"].append(file_info)

    # Import graph
    if include_graph:
        result["import_graph"] = build_import_graph(root_path, files)

    # Circular dependencies
    if include_cycles and include_graph:
        result["circular_dependencies"] = detect_circular_dependencies(result["import_graph"])

    # Dependency classification
    dep_class = classify_dependencies(files)
    result["stdlib_dependencies"] = dep_class["stdlib"]
    result["third_party_dependencies"] = dep_class["third_party"]

    # Cross-references using Jedi (if requested and available)
    if include_cross_refs:
        try:
            from jedi_engine import jedi_available, search_project
            if jedi_available():
                # Get top-level definitions and find references
                cross_refs: Dict[str, List[Dict[str, Any]]] = {}
                for f in files[:50]:  # Limit for performance
                    try:
                        source = f.read_text(encoding='utf-8')
                        tree = ast.parse(source)
                    except (OSError, SyntaxError):
                        continue

                    for node in ast.walk(tree):
                        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                            if not node.name.startswith('_'):
                                refs = search_project(node.name, str(root_path))
                                if refs and not any("error" in r for r in refs):
                                    cross_refs[node.name] = [
                                        {
                                            "module": r.get("module_name", ""),
                                            "line": r.get("line"),
                                            "type": r.get("type", ""),
                                        }
                                        for r in refs[:20]
                                    ]
                result["cross_references"] = cross_refs
        except ImportError:
            result["cross_references_note"] = "Jedi not available for cross-references"

    # Summary
    result["summary"] = {
        "total_files": len(files),
        "total_functions": total_functions,
        "total_classes": total_classes,
        "total_lines": total_lines,
        "total_imports": total_imports,
        "stdlib_dependency_count": len(dep_class["stdlib"]),
        "third_party_dependency_count": len(dep_class["third_party"]),
    }

    return result


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(
        description="Project-level Python code analysis"
    )
    parser.add_argument("path", help="Root directory of the Python project")
    parser.add_argument("--exclude", type=str, default="",
                        help="Comma-separated glob patterns to exclude (e.g., 'test*,docs')")
    parser.add_argument("--depth", type=int, default=None,
                        help="Maximum directory depth to traverse")
    parser.add_argument("--graph", action="store_true",
                        help="Show only the import graph")
    parser.add_argument("--cycles", action="store_true",
                        help="Show only circular dependencies")
    parser.add_argument("--cross-refs", action="store_true",
                        help="Include cross-references (uses Jedi, slower)")

    args = parser.parse_args()

    exclude = [p.strip() for p in args.exclude.split(',') if p.strip()] if args.exclude else None

    if args.graph:
        root_path = Path(args.path).resolve()
        files = discover_python_files(root_path, exclude, args.depth)
        graph = build_import_graph(root_path, files)
        print(json.dumps(graph, indent=2))
        return

    if args.cycles:
        root_path = Path(args.path).resolve()
        files = discover_python_files(root_path, exclude, args.depth)
        graph = build_import_graph(root_path, files)
        cycles = detect_circular_dependencies(graph)
        print(json.dumps(cycles, indent=2))
        return

    result = analyze_project(
        args.path,
        exclude_patterns=exclude,
        max_depth=args.depth,
        include_cross_refs=args.cross_refs,
    )
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
