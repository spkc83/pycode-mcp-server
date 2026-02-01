"""List installed Python packages with comprehensive metadata.

This script introspects the current Python environment and returns detailed
information about installed packages including import names, dependencies,
and main exports.

Usage:
    python inspect_env.py [--no-cache] [--simple] [--package NAME]
"""

from __future__ import annotations

import importlib
import inspect
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from importlib.metadata import distributions, PackageNotFoundError


def get_import_names(dist) -> List[str]:
    """Get the actual import names for a package from top_level.txt."""
    try:
        top_level = dist.read_text('top_level.txt')
        if top_level:
            return [name.strip() for name in top_level.strip().split('\n') if name.strip()]
    except FileNotFoundError:
        pass
    
    try:
        files = dist.files
        if files:
            import_names = set()
            for f in files:
                parts = str(f).split('/')
                if parts and not parts[0].endswith('.dist-info') and not parts[0].endswith('.egg-info'):
                    name = parts[0].replace('.py', '')
                    if name and not name.startswith('_') and name not in ('tests', 'test', 'docs'):
                        import_names.add(name)
            if import_names:
                return sorted(import_names)[:5]
    except Exception:
        pass
    
    pkg_name = dist.metadata.get("Name", "")
    return [pkg_name.lower().replace('-', '_')] if pkg_name else []


def get_dependencies(dist) -> List[str]:
    """Get package dependencies."""
    try:
        requires = dist.requires
        if requires:
            deps = []
            for req in requires:
                name = req.split(';')[0].split('[')[0].split('<')[0].split('>')[0].split('=')[0].split('!')[0].strip()
                if name:
                    deps.append(name)
            return deps[:20]
    except Exception:
        pass
    return []


def get_package_location(dist) -> Optional[str]:
    """Get the installation location of a package."""
    try:
        files = dist.files
        if files and len(files) > 0:
            first_file = files[0]
            if hasattr(first_file, 'locate'):
                loc = first_file.locate()
                if loc:
                    return str(loc.parent)
    except Exception:
        pass
    return None


def get_main_exports(import_name: str, limit: int = 10) -> List[str]:
    """Get the main public exports from a module."""
    exports = []
    try:
        module = importlib.import_module(import_name)
        
        if hasattr(module, '__all__'):
            return list(module.__all__)[:limit]
        
        for name in dir(module):
            if name.startswith('_'):
                continue
            try:
                obj = getattr(module, name)
                if inspect.isclass(obj) or inspect.isfunction(obj):
                    exports.append(name)
                if len(exports) >= limit:
                    break
            except Exception:
                continue
    except Exception:
        pass
    
    return exports


def list_installed_packages() -> List[Tuple[str, str]]:
    """Return a sorted list of (package_name, version) tuples.
    
    This is the simple/legacy output format for backwards compatibility.
    """
    return sorted(
        (d.metadata["Name"], d.version)
        for d in distributions()
        if d.metadata["Name"] is not None
    )


def get_package_details(package_name: str) -> Optional[Dict[str, Any]]:
    """Get detailed information about a specific package."""
    for dist in distributions():
        if dist.metadata["Name"] and dist.metadata["Name"].lower() == package_name.lower():
            import_names = get_import_names(dist)
            
            info: Dict[str, Any] = {
                "name": dist.metadata["Name"],
                "version": dist.version,
                "import_names": import_names,
                "summary": dist.metadata.get("Summary", ""),
            }
            
            deps = get_dependencies(dist)
            if deps:
                info["dependencies"] = deps
            
            location = get_package_location(dist)
            if location:
                info["location"] = location
            
            if import_names:
                exports = get_main_exports(import_names[0])
                if exports:
                    info["main_exports"] = exports
            
            return info
    
    return None


def get_environment_info() -> Dict[str, Any]:
    """Get information about the Python environment."""
    info: Dict[str, Any] = {
        "python_version": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
        "python_executable": sys.executable,
        "platform": sys.platform,
    }
    
    if sys.prefix != sys.base_prefix:
        info["in_virtualenv"] = True
        info["virtualenv_path"] = sys.prefix
    else:
        info["in_virtualenv"] = False
    
    try:
        import site
        info["site_packages"] = site.getsitepackages()
    except Exception:
        pass
    
    return info


def get_full_environment() -> Dict[str, Any]:
    """Get comprehensive environment information with all packages."""
    result = {
        "environment": get_environment_info(),
        "packages": {},
        "package_count": 0,
    }
    
    for dist in distributions():
        name = dist.metadata.get("Name")
        if not name:
            continue
        
        import_names = get_import_names(dist)
        
        result["packages"][name] = {
            "version": dist.version,
            "import_names": import_names,
        }
        
        deps = get_dependencies(dist)
        if deps:
            result["packages"][name]["dependencies"] = deps
    
    result["package_count"] = len(result["packages"])
    
    return result


def is_package_installed(package_name: str) -> bool:
    """Check if a package is installed."""
    for dist in distributions():
        if dist.metadata["Name"] and dist.metadata["Name"].lower() == package_name.lower():
            return True
    return False


def find_package_by_import(import_name: str) -> Optional[str]:
    """Find which package provides a given import name."""
    for dist in distributions():
        import_names = get_import_names(dist)
        if import_name in import_names or import_name.lower() in [n.lower() for n in import_names]:
            return dist.metadata.get("Name")
    return None


def main() -> None:
    import argparse
    from cache import CacheManager
    
    parser = argparse.ArgumentParser(description="List installed Python packages with metadata")
    parser.add_argument("--simple", action="store_true", help="Simple output: just name and version")
    parser.add_argument("--package", "-p", type=str, help="Get details for a specific package")
    parser.add_argument("--find-import", type=str, help="Find which package provides an import name")
    parser.add_argument("--env", action="store_true", help="Show environment information only")
    parser.add_argument("--update-cache", action="store_true", help="Update the package cache")
    parser.add_argument("--no-cache", action="store_true", help="Don't update the cache")
    
    args = parser.parse_args()
    
    if args.env:
        print(json.dumps(get_environment_info(), indent=2))
        return
    
    if args.package:
        details = get_package_details(args.package)
        if details:
            print(json.dumps(details, indent=2))
        else:
            print(json.dumps({"error": f"Package '{args.package}' not found"}, indent=2))
        return
    
    if args.find_import:
        pkg = find_package_by_import(args.find_import)
        if pkg:
            print(json.dumps({"import_name": args.find_import, "package": pkg}, indent=2))
        else:
            print(json.dumps({"error": f"No package found for import '{args.find_import}'"}, indent=2))
        return
    
    packages = list_installed_packages()
    
    if args.update_cache or not args.no_cache:
        cache = CacheManager()
        cache.update_packages(packages)
        cache.save()
    
    if args.simple:
        print(json.dumps(packages, indent=2))
    else:
        result = get_full_environment()
        print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
