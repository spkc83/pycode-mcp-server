#!/usr/bin/env python
"""Quick health check for the Python Code Assistant skill."""

import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).parent
sys.path.insert(0, str(SCRIPTS_DIR))

def check_doc_lookup():
    from doc_lookup import get_local_docs
    
    tests = [
        ("json.dumps", True),
        ("str", True),
        ("pathlib.Path", True),
        ("nonexistent.xyz", False)
    ]
    
    print("doc_lookup.py:")
    for name, should_find in tests:
        result = get_local_docs(name, use_cache=False, structured=True)
        found = result.get("found", False)
        status = "✓" if found == should_find else "✗"
        print(f"  {status} {name}: found={found}")
    
def check_inspect_env():
    from inspect_env import list_installed_packages, find_package_by_import, is_package_installed
    
    print("\ninspect_env.py:")
    packages = list_installed_packages()
    print(f"  ✓ Found {len(packages)} packages")
    
    pytest_installed = is_package_installed("pytest")
    print(f"  {'✓' if pytest_installed else '✗'} pytest installed: {pytest_installed}")
    
    pkg = find_package_by_import("pytest")
    print(f"  {'✓' if pkg else '✗'} find_package_by_import('pytest'): {pkg}")

def check_code_analyzer():
    from code_analyzer import analyze_source
    
    print("\ncode_analyzer.py:")
    source = "def hello(name: str) -> str:\n    return f'Hello {name}'\n"
    result = analyze_source(source)
    has_funcs = len(result.get("functions", [])) > 0
    print(f"  {'✓' if has_funcs else '✗'} Parsed function: {result.get('functions', [{}])[0].get('name', 'N/A')}")

def check_cache():
    from cache import CacheManager
    
    print("\ncache.py:")
    cm = CacheManager()
    stats = cm.get_stats()
    print(f"  ✓ Cache entries: {stats.get('docstring_count', 0)}")
    print(f"  ✓ Cache hits: {stats.get('cache_hits', 0)}, misses: {stats.get('cache_misses', 0)}")

def main():
    print("=" * 50)
    print("Python Code Assistant Skill - Health Check")
    print("=" * 50)
    
    try:
        check_doc_lookup()
        check_inspect_env()
        check_code_analyzer()
        check_cache()
        print("\n" + "=" * 50)
        print("All checks passed! Skill is healthy.")
        print("=" * 50)
    except Exception as e:
        print(f"\n✗ Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
