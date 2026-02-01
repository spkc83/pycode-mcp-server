"""Lookup local documentation for Python objects with structured output.

This script provides comprehensive documentation lookup for Python objects
using only local sources (installed packages, no web searches). It returns
structured JSON with signatures, type hints, examples, and related functions.

Usage:
    python doc_lookup.py <object_name> [--no-cache] [--raw]
    
Examples:
    python doc_lookup.py json.dumps
    python doc_lookup.py pandas.DataFrame.merge --no-cache
    python doc_lookup.py os.path.join --raw
"""

from __future__ import annotations

import builtins
import doctest
import importlib
import inspect
import json
import sys
from typing import Any, Dict, List, Optional, Tuple, Union

try:
    from typing import get_type_hints
except ImportError:
    get_type_hints = None

import pydoc

from cache import CacheManager


def resolve_object(name: str) -> Tuple[Optional[Any], Optional[str]]:
    """Resolve a fully-qualified name to a Python object.
    
    Handles module imports properly instead of using eval().
    
    Args:
        name: Fully qualified name like 'json.dumps' or 'pandas.DataFrame.merge'
    
    Returns:
        Tuple of (object, error_message). If successful, error_message is None.
    """
    if not name:
        return None, "Empty name provided"
    
    parts = name.split('.')
    
    if hasattr(builtins, parts[0]):
        try:
            obj = getattr(builtins, parts[0])
            for attr in parts[1:]:
                obj = getattr(obj, attr)
            return obj, None
        except AttributeError as e:
            return None, str(e)
    
    for i in range(len(parts), 0, -1):
        module_path = '.'.join(parts[:i])
        try:
            module = importlib.import_module(module_path)
            obj = module
            for attr in parts[i:]:
                obj = getattr(obj, attr)
            return obj, None
        except ImportError:
            continue
        except AttributeError as e:
            return None, f"Attribute error: {e}"
    
    return None, f"Could not resolve '{name}': module not found"


def extract_signature(obj: Any) -> Optional[str]:
    """Extract the signature of a callable object."""
    try:
        sig = inspect.signature(obj)
        return str(sig)
    except (ValueError, TypeError):
        pass
    
    if hasattr(obj, '__doc__') and obj.__doc__:
        lines = obj.__doc__.split('\n')
        for line in lines[:3]:
            line = line.strip()
            if '(' in line and ')' in line:
                return line
    
    return None


def extract_type_hints_safe(obj: Any) -> Dict[str, str]:
    """Safely extract type hints from an object."""
    hints = {}
    
    if get_type_hints is not None:
        try:
            raw_hints = get_type_hints(obj)
            for key, val in raw_hints.items():
                try:
                    if hasattr(val, '__name__'):
                        hints[key] = val.__name__
                    elif hasattr(val, '__origin__'):
                        hints[key] = str(val)
                    else:
                        hints[key] = str(val)
                except Exception:
                    hints[key] = str(val)
        except Exception:
            pass
    
    if not hints and hasattr(obj, '__annotations__'):
        try:
            for key, val in obj.__annotations__.items():
                hints[key] = str(val) if not isinstance(val, str) else val
        except Exception:
            pass
    
    return hints


def extract_parameters(obj: Any) -> List[Dict[str, Any]]:
    """Extract parameter information from a callable."""
    params = []
    
    try:
        sig = inspect.signature(obj)
        type_hints = extract_type_hints_safe(obj)
        
        for name, param in sig.parameters.items():
            param_info: Dict[str, Any] = {"name": name}
            
            if name in type_hints:
                param_info["type"] = type_hints[name]
            elif param.annotation != inspect.Parameter.empty:
                param_info["type"] = str(param.annotation)
            
            if param.default != inspect.Parameter.empty:
                try:
                    param_info["default"] = repr(param.default)
                except Exception:
                    param_info["default"] = "..."
                param_info["required"] = False
            else:
                param_info["required"] = param.kind not in (
                    inspect.Parameter.VAR_POSITIONAL,
                    inspect.Parameter.VAR_KEYWORD
                )
            
            kind_map = {
                inspect.Parameter.POSITIONAL_ONLY: "positional_only",
                inspect.Parameter.POSITIONAL_OR_KEYWORD: "positional_or_keyword",
                inspect.Parameter.VAR_POSITIONAL: "var_positional",
                inspect.Parameter.KEYWORD_ONLY: "keyword_only",
                inspect.Parameter.VAR_KEYWORD: "var_keyword",
            }
            param_info["kind"] = kind_map.get(param.kind, "unknown")
            
            params.append(param_info)
    except (ValueError, TypeError):
        pass
    
    return params


def extract_return_type(obj: Any) -> Optional[str]:
    """Extract the return type annotation."""
    try:
        sig = inspect.signature(obj)
        if sig.return_annotation != inspect.Signature.empty:
            ann = sig.return_annotation
            if hasattr(ann, '__name__'):
                return ann.__name__
            return str(ann)
    except (ValueError, TypeError):
        pass
    
    type_hints = extract_type_hints_safe(obj)
    return type_hints.get('return')


def extract_examples(docstring: Optional[str]) -> List[Dict[str, str]]:
    """Extract code examples from docstring using doctest parser."""
    if not docstring:
        return []
    
    examples = []
    try:
        parser = doctest.DocTestParser()
        parsed = parser.parse(docstring, "docstring")
        
        for item in parsed:
            if isinstance(item, doctest.Example):
                examples.append({
                    "code": item.source.strip(),
                    "expected": item.want.strip() if item.want else None
                })
    except Exception:
        pass
    
    return examples


def extract_raises(docstring: Optional[str]) -> List[Dict[str, str]]:
    """Extract exception information from docstring."""
    if not docstring:
        return []
    
    raises = []
    in_raises_section = False
    current_exception = None
    
    for line in docstring.split('\n'):
        line_stripped = line.strip()
        line_lower = line_stripped.lower()
        
        if line_lower in ('raises', 'raises:', 'exceptions', 'exceptions:'):
            in_raises_section = True
            continue
        elif line_lower.startswith(('raises', 'raise ')) and ':' in line_stripped:
            match = line_stripped.split(':', 1)
            if len(match) == 2:
                exc_part = match[0].replace('Raises', '').replace('Raise', '').strip()
                raises.append({
                    "exception": exc_part,
                    "description": match[1].strip()
                })
        elif in_raises_section:
            if line_stripped and not line.startswith(' ') and line.startswith(line_stripped):
                if ':' not in line_stripped:
                    in_raises_section = False
                    continue
            
            if line_stripped.startswith('-'):
                continue
            
            if ':' in line_stripped and not line_stripped.startswith(' '):
                parts = line_stripped.split(':', 1)
                if len(parts) == 2:
                    raises.append({
                        "exception": parts[0].strip(),
                        "description": parts[1].strip()
                    })
    
    return raises


def find_related(obj: Any, name: str) -> List[str]:
    """Find related functions/classes in the same module."""
    related = []
    
    try:
        module = inspect.getmodule(obj)
        if module is None:
            parts = name.split('.')
            if len(parts) > 1:
                try:
                    module = importlib.import_module(parts[0])
                except ImportError:
                    return related
        
        if module is None:
            return related
        
        obj_name = name.split('.')[-1]
        
        if hasattr(obj, '__doc__') and obj.__doc__:
            doc = obj.__doc__
            for marker in ('See Also', 'See also', 'Related', 'SEE ALSO'):
                if marker in doc:
                    idx = doc.index(marker)
                    section = doc[idx:idx+500]
                    lines = section.split('\n')[1:10]
                    for line in lines:
                        line = line.strip().strip('-').strip()
                        if line and not line.startswith(marker):
                            if '(' in line:
                                line = line.split('(')[0]
                            if ':' in line:
                                line = line.split(':')[0]
                            line = line.strip()
                            if line and len(line) < 50 and line != obj_name:
                                related.append(line)
        
        if len(related) < 5:
            for member_name, member in inspect.getmembers(module):
                if member_name.startswith('_'):
                    continue
                if member_name == obj_name:
                    continue
                if callable(member) and callable(obj):
                    if obj_name.lower() in member_name.lower() or member_name.lower() in obj_name.lower():
                        if member_name not in related:
                            related.append(member_name)
                if len(related) >= 5:
                    break
    except Exception:
        pass
    
    return related[:5]


def get_import_statement(name: str, obj: Any) -> str:
    """Generate the import statement for an object."""
    parts = name.split('.')
    
    if hasattr(builtins, parts[0]):
        return f"# Built-in: {parts[0]}"
    
    try:
        module = inspect.getmodule(obj)
        if module:
            module_name = module.__name__
            obj_name = parts[-1]
            
            if len(parts) == 1:
                return f"import {parts[0]}"
            elif module_name == parts[0]:
                return f"from {module_name} import {obj_name}"
            else:
                return f"from {module_name} import {obj_name}"
    except Exception:
        pass
    
    if len(parts) == 1:
        return f"import {parts[0]}"
    elif len(parts) == 2:
        return f"from {parts[0]} import {parts[1]}"
    else:
        return f"from {'.'.join(parts[:-1])} import {parts[-1]}"


def get_source_location(obj: Any) -> Optional[str]:
    """Get the source file location of an object."""
    try:
        return inspect.getfile(obj)
    except (TypeError, OSError):
        return None


def get_structured_docs(name: str) -> Dict[str, Any]:
    """Get comprehensive structured documentation for a Python object.
    
    Args:
        name: Fully qualified name of the object.
    
    Returns:
        Dictionary with structured documentation including signature,
        parameters, types, examples, and related functions.
    """
    result: Dict[str, Any] = {
        "name": name,
        "found": False,
        "error": None,
    }
    
    obj, error = resolve_object(name)
    
    if error:
        result["error"] = error
        return result
    
    result["found"] = True
    result["type"] = type(obj).__name__
    
    if inspect.ismodule(obj):
        result["object_type"] = "module"
    elif inspect.isclass(obj):
        result["object_type"] = "class"
    elif inspect.isfunction(obj) or inspect.ismethod(obj):
        result["object_type"] = "function"
    elif inspect.isbuiltin(obj):
        result["object_type"] = "builtin"
    elif callable(obj):
        result["object_type"] = "callable"
    else:
        result["object_type"] = "object"
    
    result["import_statement"] = get_import_statement(name, obj)
    
    sig = extract_signature(obj)
    if sig:
        result["signature"] = f"{name.split('.')[-1]}{sig}"
    
    docstring = inspect.getdoc(obj)
    if docstring:
        lines = docstring.split('\n')
        result["short_description"] = lines[0].strip() if lines else None
        result["full_docstring"] = docstring
    
    if callable(obj):
        params = extract_parameters(obj)
        if params:
            result["parameters"] = params
        
        return_type = extract_return_type(obj)
        if return_type:
            result["returns"] = {"type": return_type}
    
    if docstring:
        examples = extract_examples(docstring)
        if examples:
            result["examples"] = examples
        
        raises = extract_raises(docstring)
        if raises:
            result["raises"] = raises
    
    related = find_related(obj, name)
    if related:
        result["related"] = related
    
    source_file = get_source_location(obj)
    if source_file:
        result["source_file"] = source_file
    
    if inspect.isclass(obj):
        result["methods"] = []
        result["attributes"] = []
        
        for member_name, member in inspect.getmembers(obj):
            if member_name.startswith('_') and not member_name.startswith('__'):
                continue
            if member_name.startswith('__') and member_name not in ('__init__', '__call__', '__enter__', '__exit__'):
                continue
            
            if inspect.isfunction(member) or inspect.ismethod(member):
                method_sig = extract_signature(member)
                method_info = {"name": member_name}
                if method_sig:
                    method_info["signature"] = method_sig
                method_doc = inspect.getdoc(member)
                if method_doc:
                    method_info["description"] = method_doc.split('\n')[0]
                result["methods"].append(method_info)
        
        if hasattr(obj, '__annotations__'):
            for attr_name, attr_type in obj.__annotations__.items():
                if not attr_name.startswith('_'):
                    result["attributes"].append({
                        "name": attr_name,
                        "type": str(attr_type)
                    })
    
    if inspect.ismodule(obj):
        result["exports"] = []
        for member_name, member in inspect.getmembers(obj):
            if member_name.startswith('_'):
                continue
            if inspect.isfunction(member) or inspect.isclass(member):
                result["exports"].append(member_name)
            if len(result["exports"]) >= 20:
                break
    
    return result


def get_local_docs(name: str, use_cache: bool = True, structured: bool = True) -> Union[str, Dict[str, Any]]:
    """Return documentation for a given object name.

    Args:
        name: Fully qualified name of the object to document.
        use_cache: Whether to use the cache (default True).
        structured: Return structured dict (True) or raw pydoc text (False).

    Returns:
        Structured dictionary or string with documentation.
    """
    cache = CacheManager() if use_cache else None
    
    if cache:
        cached = cache.get_doc(name)
        if cached is not None:
            if structured and isinstance(cached, dict):
                return cached
            elif not structured and isinstance(cached, str):
                return cached
    
    pkg_name = name.split('.')[0] if '.' in name else name
    pkg_version = None
    try:
        mod = importlib.import_module(pkg_name)
        pkg_version = getattr(mod, "__version__", None)
    except ImportError:
        pass
    
    if structured:
        result = get_structured_docs(name)
        if cache and result.get("found", False):
            cache.set_doc(name, result, pkg_name, pkg_version)
            cache.save()
        return result
    
    obj, error = resolve_object(name)
    if error:
        return f"No documentation found locally: {error}"
    
    try:
        content = pydoc.render_doc(obj)
        
        if cache:
            cache.set_doc(name, content, pkg_name, pkg_version)
            cache.save()
        
        return content
    except Exception as e:
        return f"No documentation found locally: {e}"


def main() -> None:
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Lookup local Python documentation with structured output"
    )
    parser.add_argument("name", help="Fully qualified object name (e.g., json.dumps)")
    parser.add_argument("--no-cache", action="store_true", help="Bypass the cache")
    parser.add_argument("--raw", action="store_true", help="Return raw pydoc text instead of structured JSON")
    
    args = parser.parse_args()
    
    result = get_local_docs(args.name, use_cache=not args.no_cache, structured=not args.raw)
    
    if isinstance(result, dict):
        print(json.dumps(result, indent=2, default=str))
    else:
        print(result)


if __name__ == "__main__":
    main()
