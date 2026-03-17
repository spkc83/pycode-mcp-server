"""Jedi-powered code intelligence engine for the Python Code Assistant skill.

Provides completions, go-to-definition, references, semantic search,
refactoring operations, and diagnostics using Jedi as the primary engine.

Usage:
    python jedi_engine.py completions --file path.py --line 10 --col 5
    python jedi_engine.py definitions --file path.py --line 10 --col 5
    python jedi_engine.py references --file path.py --line 10 --col 5
    python jedi_engine.py search --query "DataFrame" --project /path
    python jedi_engine.py rename --file path.py --line 10 --col 5 --new-name "x"
    python jedi_engine.py diagnostics --file path.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

_SCRIPTS_DIR = Path(__file__).resolve().parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

try:
    import jedi
    JEDI_AVAILABLE = True
    JEDI_VERSION = jedi.__version__
except ImportError:
    JEDI_AVAILABLE = False
    JEDI_VERSION = None


def jedi_available() -> bool:
    """Check if Jedi is installed and available."""
    return JEDI_AVAILABLE


def _make_script(source: Optional[str] = None, path: Optional[str] = None,
                 project_path: Optional[str] = None) -> "jedi.Script":
    """Create a Jedi Script object from source or file path."""
    if not JEDI_AVAILABLE:
        raise RuntimeError("Jedi is not installed. Install with: pip install jedi>=0.19.0")

    kwargs: Dict[str, Any] = {}
    if source is not None:
        kwargs["code"] = source
    if path is not None:
        kwargs["path"] = path
    if project_path is not None:
        kwargs["project"] = jedi.Project(path=project_path)

    return jedi.Script(**kwargs)


def _name_to_dict(name: Any) -> Dict[str, Any]:
    """Convert a Jedi Name object to a serializable dictionary."""
    result: Dict[str, Any] = {
        "name": name.name,
        "type": name.type,
        "module_name": name.module_name,
    }

    if name.module_path:
        result["module_path"] = str(name.module_path)
    if name.line is not None:
        result["line"] = name.line
    if name.column is not None:
        result["column"] = name.column

    try:
        desc = name.description
        if desc:
            result["description"] = desc
    except Exception:
        pass

    try:
        docstring = name.docstring(raw=False)
        if docstring:
            result["docstring"] = docstring[:500]
    except Exception:
        pass

    try:
        full_name = name.full_name
        if full_name:
            result["full_name"] = full_name
    except Exception:
        pass

    return result


def get_completions(source: Optional[str] = None, line: int = 1, col: int = 0,
                    path: Optional[str] = None,
                    project_path: Optional[str] = None) -> List[Dict[str, Any]]:
    """Get autocompletion suggestions at a given position.

    Args:
        source: Python source code string.
        line: 1-indexed line number.
        col: 0-indexed column number.
        path: Path to the Python file (used for project context).
        project_path: Root path of the project.

    Returns:
        List of completion dictionaries with name, type, and description.
    """
    if not JEDI_AVAILABLE:
        return [{"error": "Jedi not available"}]

    try:
        script = _make_script(source=source, path=path, project_path=project_path)
        completions = script.complete(line, col)
        return [_name_to_dict(c) for c in completions]
    except Exception as e:
        return [{"error": str(e)}]


def get_definitions(source: Optional[str] = None, line: int = 1, col: int = 0,
                    path: Optional[str] = None,
                    project_path: Optional[str] = None) -> List[Dict[str, Any]]:
    """Get definitions / type inference for the object at a given position.

    Uses Script.infer() to follow imports and resolve the ultimate definition.

    Args:
        source: Python source code string.
        line: 1-indexed line number.
        col: 0-indexed column number.
        path: Path to the Python file.
        project_path: Root path of the project.

    Returns:
        List of definition dictionaries.
    """
    if not JEDI_AVAILABLE:
        return [{"error": "Jedi not available"}]

    try:
        script = _make_script(source=source, path=path, project_path=project_path)
        definitions = script.infer(line, col)
        return [_name_to_dict(d) for d in definitions]
    except Exception as e:
        return [{"error": str(e)}]


def get_references(source: Optional[str] = None, line: int = 1, col: int = 0,
                   path: Optional[str] = None,
                   project_path: Optional[str] = None) -> List[Dict[str, Any]]:
    """Find all references to the object at a given position.

    Args:
        source: Python source code string.
        line: 1-indexed line number.
        col: 0-indexed column number.
        path: Path to the Python file.
        project_path: Root path of the project.

    Returns:
        List of reference location dictionaries.
    """
    if not JEDI_AVAILABLE:
        return [{"error": "Jedi not available"}]

    try:
        script = _make_script(source=source, path=path, project_path=project_path)
        refs = script.get_references(line, col)
        return [_name_to_dict(r) for r in refs]
    except Exception as e:
        return [{"error": str(e)}]


def get_signatures(source: Optional[str] = None, line: int = 1, col: int = 0,
                   path: Optional[str] = None,
                   project_path: Optional[str] = None) -> List[Dict[str, Any]]:
    """Get function signature help at a given position.

    Args:
        source: Python source code string.
        line: 1-indexed line number.
        col: 0-indexed column number.
        path: Path to the Python file.
        project_path: Root path of the project.

    Returns:
        List of signature dictionaries with name, params, and index.
    """
    if not JEDI_AVAILABLE:
        return [{"error": "Jedi not available"}]

    try:
        script = _make_script(source=source, path=path, project_path=project_path)
        sigs = script.get_signatures(line, col)
        results = []
        for sig in sigs:
            sig_info: Dict[str, Any] = {
                "name": sig.name,
                "index": sig.index,
                "params": [],
            }
            for param in sig.params:
                param_info: Dict[str, Any] = {"name": param.name}
                desc = param.description
                if desc:
                    param_info["description"] = desc
                sig_info["params"].append(param_info)

            try:
                docstring = sig.docstring(raw=False)
                if docstring:
                    sig_info["docstring"] = docstring[:500]
            except Exception:
                pass

            results.append(sig_info)
        return results
    except Exception as e:
        return [{"error": str(e)}]


def search_project(query: str, project_path: str) -> List[Dict[str, Any]]:
    """Semantic search across a project.

    Args:
        query: Search query (name, dotted path, or 'type name' like 'class Foo').
        project_path: Root path of the project to search.

    Returns:
        List of matching name dictionaries.
    """
    if not JEDI_AVAILABLE:
        return [{"error": "Jedi not available"}]

    try:
        project = jedi.Project(path=project_path)
        results = project.search(query)
        return [_name_to_dict(r) for r in results]
    except Exception as e:
        return [{"error": str(e)}]


def rename_symbol(source: Optional[str] = None, line: int = 1, col: int = 0,
                  new_name: str = "", path: Optional[str] = None,
                  project_path: Optional[str] = None) -> Dict[str, Any]:
    """Rename a symbol and return the refactoring changes.

    Args:
        source: Python source code string.
        line: 1-indexed line number.
        col: 0-indexed column number.
        new_name: The new name for the symbol.
        path: Path to the Python file.
        project_path: Root path of the project.

    Returns:
        Dictionary with changed_files mapping file paths to new content.
    """
    if not JEDI_AVAILABLE:
        return {"error": "Jedi not available"}

    if not new_name:
        return {"error": "new_name is required"}

    try:
        script = _make_script(source=source, path=path, project_path=project_path)
        refactoring = script.rename(line, col, new_name=new_name)

        changed_files = {}
        for filepath, changed_file in refactoring.get_changed_files().items():
            changed_files[str(filepath)] = changed_file.get_new_code()

        return {
            "success": True,
            "new_name": new_name,
            "changed_files": changed_files,
            "diff": refactoring.get_diff(),
        }
    except Exception as e:
        return {"error": str(e)}


def extract_variable(source: str, line: int, col: int,
                     end_line: int, end_col: int,
                     new_name: str = "extracted_var",
                     path: Optional[str] = None) -> Dict[str, Any]:
    """Extract an expression into a variable.

    Args:
        source: Python source code string.
        line: Start line (1-indexed).
        col: Start column (0-indexed).
        end_line: End line (1-indexed).
        end_col: End column (0-indexed).
        new_name: Name for the extracted variable.
        path: Path to the Python file.

    Returns:
        Dictionary with the refactored code.
    """
    if not JEDI_AVAILABLE:
        return {"error": "Jedi not available"}

    try:
        script = _make_script(source=source, path=path)
        refactoring = script.extract_variable(
            line, col, end_line=end_line, end_col=end_col, new_name=new_name
        )
        return {
            "success": True,
            "new_name": new_name,
            "new_code": refactoring.get_changed_files().get(
                Path(path) if path else None, source
            ),
            "diff": refactoring.get_diff(),
        }
    except Exception as e:
        return {"error": str(e)}


def extract_function(source: str, line: int, col: int,
                     end_line: int, end_col: int,
                     new_name: str = "extracted_func",
                     path: Optional[str] = None) -> Dict[str, Any]:
    """Extract code into a new function.

    Args:
        source: Python source code string.
        line: Start line (1-indexed).
        col: Start column (0-indexed).
        end_line: End line (1-indexed).
        end_col: End column (0-indexed).
        new_name: Name for the extracted function.
        path: Path to the Python file.

    Returns:
        Dictionary with the refactored code.
    """
    if not JEDI_AVAILABLE:
        return {"error": "Jedi not available"}

    try:
        script = _make_script(source=source, path=path)
        refactoring = script.extract_function(
            line, col, end_line=end_line, end_col=end_col, new_name=new_name
        )
        return {
            "success": True,
            "new_name": new_name,
            "new_code": refactoring.get_changed_files().get(
                Path(path) if path else None, source
            ),
            "diff": refactoring.get_diff(),
        }
    except Exception as e:
        return {"error": str(e)}


def inline_variable(source: Optional[str] = None, line: int = 1, col: int = 0,
                    path: Optional[str] = None) -> Dict[str, Any]:
    """Inline a variable (replace all usages with its value).

    Args:
        source: Python source code string.
        line: 1-indexed line number.
        col: 0-indexed column number.
        path: Path to the Python file.

    Returns:
        Dictionary with the refactored code.
    """
    if not JEDI_AVAILABLE:
        return {"error": "Jedi not available"}

    try:
        script = _make_script(source=source, path=path)
        refactoring = script.inline(line, col)
        return {
            "success": True,
            "diff": refactoring.get_diff(),
        }
    except Exception as e:
        return {"error": str(e)}


def get_diagnostics(source: Optional[str] = None,
                    path: Optional[str] = None) -> List[Dict[str, Any]]:
    """Get syntax error diagnostics for a file.

    Args:
        source: Python source code string.
        path: Path to the Python file.

    Returns:
        List of diagnostic dictionaries with line, col, severity, message.
    """
    if not JEDI_AVAILABLE:
        return [{"error": "Jedi not available"}]

    try:
        script = _make_script(source=source, path=path)
        errors = script.get_syntax_errors()
        diagnostics = []
        for error in errors:
            diagnostics.append({
                "line": error.line,
                "column": error.column,
                "end_line": error.until_line,
                "end_column": error.until_column,
                "severity": "error",
                "source": "jedi",
                "message": error.get_message(),
            })
        return diagnostics
    except Exception as e:
        return [{"error": str(e)}]


def get_goto(source: Optional[str] = None, line: int = 1, col: int = 0,
             path: Optional[str] = None,
             project_path: Optional[str] = None) -> List[Dict[str, Any]]:
    """Go to the definition of the object at a given position.

    Unlike get_definitions (infer), this returns the initial definition
    without following imports.

    Args:
        source: Python source code string.
        line: 1-indexed line number.
        col: 0-indexed column number.
        path: Path to the Python file.
        project_path: Root path of the project.

    Returns:
        List of definition location dictionaries.
    """
    if not JEDI_AVAILABLE:
        return [{"error": "Jedi not available"}]

    try:
        script = _make_script(source=source, path=path, project_path=project_path)
        defs = script.goto(line, col)
        return [_name_to_dict(d) for d in defs]
    except Exception as e:
        return [{"error": str(e)}]


def get_hover_info(source: Optional[str] = None, line: int = 1, col: int = 0,
                   path: Optional[str] = None) -> Dict[str, Any]:
    """Get hover information (type + docstring) for an object at a position.

    Args:
        source: Python source code string.
        line: 1-indexed line number.
        col: 0-indexed column number.
        path: Path to the Python file.

    Returns:
        Dictionary with type info, docstring, and signature.
    """
    if not JEDI_AVAILABLE:
        return {"error": "Jedi not available"}

    try:
        script = _make_script(source=source, path=path)
        names = script.infer(line, col)
        if not names:
            return {"found": False}

        name = names[0]
        result: Dict[str, Any] = {
            "found": True,
            "name": name.name,
            "type": name.type,
            "full_name": name.full_name,
        }

        try:
            result["description"] = name.description
        except Exception:
            pass

        try:
            docstring = name.docstring(raw=False)
            if docstring:
                result["docstring"] = docstring
        except Exception:
            pass

        if name.module_path:
            result["module_path"] = str(name.module_path)

        return result
    except Exception as e:
        return {"error": str(e)}


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(
        description="Jedi-powered code intelligence engine"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Common args helper
    def add_file_args(sub):
        sub.add_argument("--file", "-f", type=str, help="Path to Python file")
        sub.add_argument("--line", "-l", type=int, default=1, help="Line number (1-indexed)")
        sub.add_argument("--col", "-c", type=int, default=0, help="Column number (0-indexed)")
        sub.add_argument("--project", type=str, help="Project root path")

    # completions
    p_comp = subparsers.add_parser("completions", help="Get autocompletions")
    add_file_args(p_comp)

    # definitions
    p_def = subparsers.add_parser("definitions", help="Get definitions (infer)")
    add_file_args(p_def)

    # references
    p_ref = subparsers.add_parser("references", help="Find all references")
    add_file_args(p_ref)

    # goto
    p_goto = subparsers.add_parser("goto", help="Go to definition")
    add_file_args(p_goto)

    # hover
    p_hover = subparsers.add_parser("hover", help="Get hover information")
    add_file_args(p_hover)

    # signatures
    p_sig = subparsers.add_parser("signatures", help="Get signature help")
    add_file_args(p_sig)

    # search
    p_search = subparsers.add_parser("search", help="Semantic search in project")
    p_search.add_argument("--query", "-q", type=str, required=True, help="Search query")
    p_search.add_argument("--project", type=str, required=True, help="Project root path")

    # rename
    p_rename = subparsers.add_parser("rename", help="Rename a symbol")
    add_file_args(p_rename)
    p_rename.add_argument("--new-name", type=str, required=True, help="New name for the symbol")

    # diagnostics
    p_diag = subparsers.add_parser("diagnostics", help="Get syntax diagnostics")
    p_diag.add_argument("--file", "-f", type=str, help="Path to Python file")

    # status
    subparsers.add_parser("status", help="Check Jedi availability")

    args = parser.parse_args()

    if args.command == "status":
        print(json.dumps({
            "jedi_available": JEDI_AVAILABLE,
            "jedi_version": JEDI_VERSION,
        }, indent=2))
        return

    if args.command == "search":
        result = search_project(args.query, args.project)
        print(json.dumps(result, indent=2, default=str))
        return

    if args.command == "diagnostics":
        source = None
        file_path = args.file
        if file_path:
            source = Path(file_path).read_text(encoding="utf-8")
        result = get_diagnostics(source=source, path=file_path)
        print(json.dumps(result, indent=2, default=str))
        return

    # Commands that need file + position
    source = None
    file_path = getattr(args, "file", None)
    if file_path:
        source = Path(file_path).read_text(encoding="utf-8")

    line = getattr(args, "line", 1)
    col = getattr(args, "col", 0)
    project = getattr(args, "project", None)

    if args.command == "completions":
        result = get_completions(source=source, line=line, col=col,
                                 path=file_path, project_path=project)
    elif args.command == "definitions":
        result = get_definitions(source=source, line=line, col=col,
                                 path=file_path, project_path=project)
    elif args.command == "references":
        result = get_references(source=source, line=line, col=col,
                                path=file_path, project_path=project)
    elif args.command == "goto":
        result = get_goto(source=source, line=line, col=col,
                          path=file_path, project_path=project)
    elif args.command == "hover":
        result = get_hover_info(source=source, line=line, col=col, path=file_path)
    elif args.command == "signatures":
        result = get_signatures(source=source, line=line, col=col,
                                path=file_path, project_path=project)
    elif args.command == "rename":
        result = rename_symbol(source=source, line=line, col=col,
                               new_name=args.new_name, path=file_path,
                               project_path=project)
    else:
        result = {"error": f"Unknown command: {args.command}"}

    print(json.dumps(result, indent=2, default=str))


if __name__ == "__main__":
    main()
