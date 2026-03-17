"""Analyze Python source files and return structured summaries.

This script parses Python source code and returns structured information
about functions, classes, imports, and dependencies - much more useful
for coding agents than raw AST dumps.

Usage:
    python code_analyzer.py <file.py> [--raw] [--json]
"""

from __future__ import annotations

import ast
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Union

_SCRIPTS_DIR = Path(__file__).resolve().parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))



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


def _ast_unparse(node: ast.AST) -> str:
    """Convert an AST node back to source code string."""
    return ast.unparse(node)


def _ast_dump(node: ast.AST, indent: int = 2) -> str:
    """Dump an AST node with indentation."""
    return ast.dump(node, indent=indent)


class CodeVisitor(ast.NodeVisitor):
    """AST visitor that extracts structured information from Python code."""
    
    def __init__(self):
        self.imports: List[Dict[str, Any]] = []
        self.from_imports: List[Dict[str, Any]] = []
        self.functions: List[Dict[str, Any]] = []
        self.classes: List[Dict[str, Any]] = []
        self.global_variables: List[Dict[str, Any]] = []
        self.decorators_used: List[str] = []
        self._current_class: Optional[str] = None
    
    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            self.imports.append({
                "module": alias.name,
                "alias": alias.asname,
            })
        self.generic_visit(node)
    
    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        names = [{"name": a.name, "alias": a.asname} for a in node.names]
        self.from_imports.append({
            "module": node.module or "",
            "names": names,
            "level": node.level,
        })
        self.generic_visit(node)
    
    def _extract_decorator_names(self, decorator_list: List[ast.expr]) -> List[str]:
        names = []
        for dec in decorator_list:
            if isinstance(dec, ast.Name):
                names.append(dec.id)
            elif isinstance(dec, ast.Attribute):
                names.append(_ast_unparse(dec))
            elif isinstance(dec, ast.Call):
                if isinstance(dec.func, ast.Name):
                    names.append(dec.func.id)
                elif isinstance(dec.func, ast.Attribute):
                    names.append(_ast_unparse(dec.func))
        return names
    
    def _extract_arguments(self, args: ast.arguments) -> List[Dict[str, Any]]:
        params = []
        
        defaults_offset = len(args.args) - len(args.defaults)
        
        for i, arg in enumerate(args.args):
            param: Dict[str, Any] = {"name": arg.arg}
            if arg.annotation:
                param["type"] = _ast_unparse(arg.annotation)
            
            default_idx = i - defaults_offset
            if default_idx >= 0 and default_idx < len(args.defaults):
                try:
                    param["default"] = _ast_unparse(args.defaults[default_idx])
                except Exception:
                    param["default"] = "..."
            
            params.append(param)
        
        for i, arg in enumerate(args.kwonlyargs):
            param = {"name": arg.arg, "keyword_only": True}
            if arg.annotation:
                param["type"] = _ast_unparse(arg.annotation)
            if i < len(args.kw_defaults) and args.kw_defaults[i] is not None:
                kw_default = args.kw_defaults[i]
                if kw_default is not None:
                    try:
                        param["default"] = _ast_unparse(kw_default)
                    except Exception:
                        param["default"] = "..."
            params.append(param)
        
        if args.vararg:
            param = {"name": f"*{args.vararg.arg}", "variadic": True}
            if args.vararg.annotation:
                param["type"] = _ast_unparse(args.vararg.annotation)
            params.append(param)
        
        if args.kwarg:
            param = {"name": f"**{args.kwarg.arg}", "variadic": True}
            if args.kwarg.annotation:
                param["type"] = _ast_unparse(args.kwarg.annotation)
            params.append(param)
        
        return params
    
    def _extract_docstring(self, node: Union[ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Module]) -> Optional[str]:
        return ast.get_docstring(node)
    
    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._process_function(node, is_async=False)
        self.generic_visit(node)
    
    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._process_function(node, is_async=True)
        self.generic_visit(node)
    
    def _process_function(self, node: Union[ast.FunctionDef, ast.AsyncFunctionDef], is_async: bool) -> None:
        if self._current_class:
            return
        
        decorators = self._extract_decorator_names(node.decorator_list)
        for dec in decorators:
            if dec not in self.decorators_used:
                self.decorators_used.append(dec)
        
        func_info: Dict[str, Any] = {
            "name": node.name,
            "line": node.lineno,
            "parameters": self._extract_arguments(node.args),
        }
        
        if is_async:
            func_info["async"] = True
        
        if node.returns:
            func_info["returns"] = _ast_unparse(node.returns)
        
        if decorators:
            func_info["decorators"] = decorators
        
        docstring = self._extract_docstring(node)
        if docstring:
            lines = docstring.split('\n')
            func_info["description"] = lines[0].strip()
        
        sig_parts = [f"{p['name']}: {p.get('type', 'Any')}" if 'type' in p else p['name'] 
                     for p in func_info["parameters"] if not p['name'].startswith('self')]
        returns = func_info.get('returns', 'None')
        func_info["signature"] = f"{node.name}({', '.join(sig_parts)}) -> {returns}"
        
        self.functions.append(func_info)
    
    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        decorators = self._extract_decorator_names(node.decorator_list)
        for dec in decorators:
            if dec not in self.decorators_used:
                self.decorators_used.append(dec)
        
        bases = [_ast_unparse(b) for b in node.bases]
        
        class_info: Dict[str, Any] = {
            "name": node.name,
            "line": node.lineno,
            "bases": bases,
            "methods": [],
            "attributes": [],
        }
        
        if decorators:
            class_info["decorators"] = decorators
        
        docstring = self._extract_docstring(node)
        if docstring:
            lines = docstring.split('\n')
            class_info["description"] = lines[0].strip()
        
        self._current_class = node.name
        
        for item in node.body:
            if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                method_decorators = self._extract_decorator_names(item.decorator_list)
                
                method_info: Dict[str, Any] = {
                    "name": item.name,
                    "parameters": self._extract_arguments(item.args),
                }
                
                if isinstance(item, ast.AsyncFunctionDef):
                    method_info["async"] = True
                
                if item.returns:
                    method_info["returns"] = _ast_unparse(item.returns)
                
                if method_decorators:
                    method_info["decorators"] = method_decorators
                
                method_doc = self._extract_docstring(item)
                if method_doc:
                    method_info["description"] = method_doc.split('\n')[0].strip()
                
                params = [p for p in method_info["parameters"] if p['name'] != 'self' and p['name'] != 'cls']
                sig_parts = [f"{p['name']}: {p.get('type', 'Any')}" if 'type' in p else p['name'] for p in params]
                returns = method_info.get('returns', 'None')
                method_info["signature"] = f"{item.name}({', '.join(sig_parts)}) -> {returns}"
                
                class_info["methods"].append(method_info)
            
            elif isinstance(item, ast.AnnAssign) and isinstance(item.target, ast.Name):
                attr_info: Dict[str, Any] = {"name": item.target.id}
                if item.annotation:
                    attr_info["type"] = _ast_unparse(item.annotation)
                if item.value:
                    try:
                        attr_info["default"] = _ast_unparse(item.value)
                    except Exception:
                        pass
                class_info["attributes"].append(attr_info)
        
        self._current_class = None
        self.classes.append(class_info)
    
    def visit_Assign(self, node: ast.Assign) -> None:
        if self._current_class is None:
            for target in node.targets:
                if isinstance(target, ast.Name) and not target.id.startswith('_'):
                    var_info: Dict[str, Any] = {"name": target.id, "line": node.lineno}
                    try:
                        var_info["value"] = _ast_unparse(node.value)[:50]
                    except Exception:
                        pass
                    self.global_variables.append(var_info)
        self.generic_visit(node)
    
    def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
        if self._current_class is None and isinstance(node.target, ast.Name):
            if not node.target.id.startswith('_'):
                var_info: Dict[str, Any] = {
                    "name": node.target.id,
                    "line": node.lineno,
                    "type": _ast_unparse(node.annotation),
                }
                if node.value:
                    try:
                        var_info["value"] = _ast_unparse(node.value)[:50]
                    except Exception:
                        pass
                self.global_variables.append(var_info)
        self.generic_visit(node)


def analyze_source(source: str) -> Dict[str, Any]:
    """Analyze Python source code and return structured information."""
    tree = ast.parse(source)
    visitor = CodeVisitor()
    visitor.visit(tree)
    
    result: Dict[str, Any] = {}
    
    module_docstring = ast.get_docstring(tree)
    if module_docstring:
        result["module_description"] = module_docstring.split('\n')[0].strip()
    
    if visitor.imports:
        result["imports"] = visitor.imports
    
    if visitor.from_imports:
        result["from_imports"] = visitor.from_imports
    
    all_deps = set()
    for imp in visitor.imports:
        all_deps.add(imp["module"].split('.')[0])
    for imp in visitor.from_imports:
        if imp["module"]:
            all_deps.add(imp["module"].split('.')[0])
    
    third_party = sorted([d for d in all_deps if d not in STDLIB_MODULES and d])
    if third_party:
        result["third_party_dependencies"] = third_party
    
    if visitor.functions:
        result["functions"] = visitor.functions
    
    if visitor.classes:
        result["classes"] = visitor.classes
    
    if visitor.global_variables:
        result["global_variables"] = visitor.global_variables[:10]
    
    if visitor.decorators_used:
        result["decorators_used"] = visitor.decorators_used
    
    result["summary"] = {
        "total_functions": len(visitor.functions),
        "total_classes": len(visitor.classes),
        "total_imports": len(visitor.imports) + len(visitor.from_imports),
    }
    
    return result


def analyze_source_raw(source: str) -> str:
    """Return raw AST dump for backwards compatibility."""
    tree = ast.parse(source)
    return _ast_dump(tree, indent=2)


def analyze_file(path: str, raw: bool = False) -> Union[Dict[str, Any], str]:
    """Analyze a Python file."""
    file_path = Path(path)
    
    if not file_path.exists():
        return {"error": f"File not found: {path}"}
    
    if not file_path.suffix == '.py':
        return {"error": f"Not a Python file: {path}"}
    
    source = file_path.read_text(encoding='utf-8')
    
    if raw:
        return analyze_source_raw(source)
    
    try:
        result = analyze_source(source)
        result["file"] = str(file_path.absolute())
        result["file_name"] = file_path.name
        return result
    except SyntaxError as e:
        return {"error": f"Syntax error in {path}: {e}"}


def main() -> None:
    import argparse
    
    parser = argparse.ArgumentParser(description="Analyze Python source files")
    parser.add_argument("path", help="Path to Python file to analyze")
    parser.add_argument("--raw", action="store_true", help="Output raw AST dump")
    parser.add_argument("--json", action="store_true", help="Force JSON output (default for structured)")
    
    args = parser.parse_args()
    
    result = analyze_file(args.path, raw=args.raw)
    
    if isinstance(result, str):
        print(result)
    else:
        print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
