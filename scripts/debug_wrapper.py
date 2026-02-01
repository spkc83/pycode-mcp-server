#!/usr/bin/env python
"""Debug wrapper to log skill usage. Run instead of direct script calls."""

import sys
import json
from datetime import datetime
from pathlib import Path

LOG_FILE = Path(__file__).parent.parent / "references" / "skill_usage.log"

def log(script: str, args: list, result_preview: str):
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(LOG_FILE, "a") as f:
        entry = {
            "timestamp": datetime.now().isoformat(),
            "script": script,
            "args": args,
            "result_preview": result_preview[:500]
        }
        f.write(json.dumps(entry) + "\n")

def main():
    if len(sys.argv) < 2:
        print("Usage: debug_wrapper.py <script> [args...]")
        print("Scripts: doc_lookup, inspect_env, code_analyzer")
        sys.exit(1)
    
    script = sys.argv[1]
    args = sys.argv[2:]
    
    if script == "doc_lookup":
        from doc_lookup import get_local_docs
        name = args[0] if args else ""
        use_cache = "--no-cache" not in args
        structured = "--raw" not in args
        result = get_local_docs(name, use_cache=use_cache, structured=structured)
        if isinstance(result, dict):
            output = json.dumps(result, indent=2, default=str)
        else:
            output = result
        log("doc_lookup", args, output)
        print(output)
        
    elif script == "inspect_env":
        from inspect_env import list_installed_packages, find_package_by_import, get_full_environment
        if "--find-import" in args:
            idx = args.index("--find-import")
            import_name = args[idx + 1] if idx + 1 < len(args) else ""
            pkg = find_package_by_import(import_name)
            output = json.dumps({"import_name": import_name, "package": pkg}, indent=2)
        elif "--full" in args:
            output = json.dumps(get_full_environment(), indent=2, default=str)
        else:
            packages = list_installed_packages()
            output = json.dumps(packages, indent=2)
        log("inspect_env", args, output)
        print(output)
        
    elif script == "code_analyzer":
        from code_analyzer import analyze_file
        filepath = args[0] if args else ""
        result = analyze_file(filepath)
        output = json.dumps(result, indent=2, default=str)
        log("code_analyzer", args, output)
        print(output)
    else:
        print(f"Unknown script: {script}")
        sys.exit(1)

if __name__ == "__main__":
    main()
