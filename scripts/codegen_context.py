from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from doc_lookup import get_local_docs
from inspect_env import (
    find_package_by_import,
    get_environment_info,
    get_package_details,
    is_package_installed,
)


def _parse_version(value: str) -> Optional[Tuple[int, ...]]:
    match = re.search(r"\d+(?:\.\d+){0,3}", value)
    if not match:
        return None
    return tuple(int(part) for part in match.group(0).split("."))


def _compare_versions(left: Tuple[int, ...], right: Tuple[int, ...]) -> int:
    max_len = max(len(left), len(right))
    lvals = left + (0,) * (max_len - len(left))
    rvals = right + (0,) * (max_len - len(right))
    if lvals < rvals:
        return -1
    if lvals > rvals:
        return 1
    return 0


def _check_version_spec(current: Optional[str], spec: Optional[str]) -> Dict[str, Any]:
    result: Dict[str, Any] = {
        "checked": bool(spec),
        "compatible": True,
        "spec": spec,
        "current": current,
        "details": [],
    }

    if not spec:
        return result
    if not current:
        result["compatible"] = False
        result["details"].append("Current package version unavailable for compatibility check")
        return result

    current_parsed = _parse_version(current)
    if current_parsed is None:
        result["compatible"] = False
        result["details"].append(f"Unable to parse current version '{current}'")
        return result

    clauses = [clause.strip() for clause in spec.split(",") if clause.strip()]
    op_re = re.compile(r"^(>=|<=|==|!=|>|<)\s*(.+)$")
    for clause in clauses:
        match = op_re.match(clause)
        if not match:
            result["compatible"] = False
            result["details"].append(f"Unsupported version clause '{clause}'")
            continue

        operator, rhs = match.groups()
        rhs_parsed = _parse_version(rhs)
        if rhs_parsed is None:
            result["compatible"] = False
            result["details"].append(f"Unable to parse version in clause '{clause}'")
            continue

        cmp_value = _compare_versions(current_parsed, rhs_parsed)
        is_ok = {
            ">": cmp_value > 0,
            ">=": cmp_value >= 0,
            "<": cmp_value < 0,
            "<=": cmp_value <= 0,
            "==": cmp_value == 0,
            "!=": cmp_value != 0,
        }[operator]

        if not is_ok:
            result["compatible"] = False
            result["details"].append(f"Installed version {current} does not satisfy '{clause}'")

    return result


def _detect_package_manager(project_root: Path) -> str:
    current = project_root.resolve()
    for _ in range(10):
        if (current / "uv.lock").exists():
            return "uv"
        if (current / "poetry.lock").exists():
            return "poetry"
        if (current / "Pipfile").exists():
            return "pipenv"
        if (current / "pyproject.toml").exists():
            try:
                content = (current / "pyproject.toml").read_text(encoding="utf-8")
            except OSError:
                content = ""
            if "[tool.poetry]" in content:
                return "poetry"
            if "[tool.uv]" in content:
                return "uv"
        parent = current.parent
        if parent == current:
            break
        current = parent
    return "pip"


def _install_command(package_name: str, project_path: Optional[str]) -> Dict[str, str]:
    root = Path(project_path) if project_path else Path.cwd()
    manager = _detect_package_manager(root)
    command_map = {
        "uv": f"uv add {package_name}",
        "poetry": f"poetry add {package_name}",
        "pipenv": f"pipenv install {package_name}",
        "pip": f"pip install {package_name}",
    }
    return {
        "detected_package_manager": manager,
        "install_command": command_map.get(manager, f"pip install {package_name}"),
    }


def _derive_package_name(object_name: Optional[str]) -> Optional[str]:
    if not object_name or "." not in object_name:
        return None
    root = object_name.split(".")[0]
    if root in {"str", "int", "float", "bool", "list", "dict", "set", "tuple"}:
        return None
    return root


def _apply_budget(doc_data: Dict[str, Any], budget: str) -> Dict[str, Any]:
    if budget == "full":
        return doc_data

    keep_common = {
        "name",
        "found",
        "error",
        "object_type",
        "import_statement",
        "signature",
        "short_description",
        "source_file",
    }
    base = {key: value for key, value in doc_data.items() if key in keep_common}

    if budget == "short":
        if "parameters" in doc_data:
            base["parameters"] = [
                {"name": p.get("name"), "required": p.get("required", True)}
                for p in doc_data.get("parameters", [])[:5]
            ]
        if "examples" in doc_data:
            base["examples"] = doc_data.get("examples", [])[:1]
        if "related" in doc_data:
            base["related"] = doc_data.get("related", [])[:3]
        return base

    if "parameters" in doc_data:
        base["parameters"] = doc_data.get("parameters", [])[:15]
    if "returns" in doc_data:
        base["returns"] = doc_data.get("returns")
    if "examples" in doc_data:
        base["examples"] = doc_data.get("examples", [])[:2]
    if "raises" in doc_data:
        base["raises"] = doc_data.get("raises", [])[:5]
    if "related" in doc_data:
        base["related"] = doc_data.get("related", [])[:5]
    if "methods" in doc_data:
        base["methods"] = doc_data.get("methods", [])[:15]
    if "attributes" in doc_data:
        base["attributes"] = doc_data.get("attributes", [])[:10]
    return base


def prepare_codegen_context(
    object_name: Optional[str] = None,
    package_name: Optional[str] = None,
    import_name: Optional[str] = None,
    project_path: Optional[str] = None,
    min_python: Optional[str] = None,
    package_version_spec: Optional[str] = None,
    budget: str = "medium",
) -> Dict[str, Any]:
    budget_mode = budget.lower().strip()
    if budget_mode not in {"short", "medium", "full"}:
        raise ValueError("budget must be one of: short, medium, full")

    derived_package = _derive_package_name(object_name)
    target_package = package_name or derived_package
    env = get_environment_info()

    compatibility_warnings: List[str] = []
    recommendations: List[str] = []

    docs: Optional[Dict[str, Any]] = None
    if object_name:
        docs_raw = get_local_docs(object_name, use_cache=True, structured=True)
        docs = docs_raw if isinstance(docs_raw, dict) else {"found": False, "error": str(docs_raw)}
        docs = _apply_budget(docs, budget_mode)
        if not docs.get("found", False):
            compatibility_warnings.append(
                f"Object '{object_name}' is not importable in the local environment"
            )

    package_details = None
    install = None
    version_check = {"checked": False, "compatible": True, "details": []}
    if target_package:
        installed = is_package_installed(target_package)
        if installed:
            package_details = get_package_details(target_package)
            current_version = package_details.get("version") if package_details else None
            version_check = _check_version_spec(current_version, package_version_spec)
            if not version_check.get("compatible", True):
                compatibility_warnings.extend(version_check.get("details", []))
        else:
            install = _install_command(target_package, project_path)
            compatibility_warnings.append(
                f"Package '{target_package}' is not installed in the local runtime"
            )

    import_resolution = None
    if import_name:
        resolved = find_package_by_import(import_name)
        import_resolution = {
            "import_name": import_name,
            "resolved_package": resolved,
        }
        if resolved is None:
            compatibility_warnings.append(
                f"Import '{import_name}' does not map to any installed package"
            )
        elif target_package and resolved.lower() != target_package.lower():
            compatibility_warnings.append(
                f"Import '{import_name}' resolves to '{resolved}', not '{target_package}'"
            )

    python_check = {"checked": bool(min_python), "compatible": True, "details": []}
    if min_python:
        current_python = _parse_version(env.get("python_version", ""))
        required_python = _parse_version(min_python)
        if current_python is None or required_python is None:
            python_check["compatible"] = False
            python_check["details"].append(
                "Unable to parse Python version check "
                f"current={env.get('python_version')} required={min_python}"
            )
        elif _compare_versions(current_python, required_python) < 0:
            python_check["compatible"] = False
            python_check["details"].append(
                f"Current Python {env.get('python_version')} is below required minimum {min_python}"
            )

    if not python_check.get("compatible", True):
        compatibility_warnings.extend(python_check.get("details", []))

    if docs and docs.get("found"):
        recommendations.append(
            "Use the returned signature and parameters exactly when generating code"
        )
    if install:
        recommendations.append(
            f"Ask the user to run '{install['install_command']}' before using {target_package}"
        )
    if package_details:
        recommendations.append(
            "Target installed package version "
            f"{package_details.get('version')} for API compatibility"
        )
    if not compatibility_warnings:
        recommendations.append("No compatibility blockers detected for the current request")

    return {
        "request": {
            "object_name": object_name,
            "package_name": package_name,
            "import_name": import_name,
            "project_path": project_path,
            "min_python": min_python,
            "package_version_spec": package_version_spec,
            "budget": budget_mode,
        },
        "environment": {
            "python_version": env.get("python_version"),
            "python_executable": env.get("python_executable"),
            "platform": env.get("platform"),
            "in_virtualenv": env.get("in_virtualenv"),
        },
        "docs": docs,
        "package": package_details,
        "install": install,
        "import_resolution": import_resolution,
        "compatibility": {
            "python": python_check,
            "package_version": version_check,
            "warnings": compatibility_warnings,
            "is_compatible": len(compatibility_warnings) == 0,
        },
        "agent_contract": {
            "coding_focus": "version-compatible local runtime code generation",
            "must_follow": [
                "Prefer local signatures over assumed API shapes",
                "Respect compatibility warnings before emitting final code",
                "Use provided install command when package is missing",
            ],
            "budget_mode": budget_mode,
        },
        "recommendations": recommendations,
    }


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(
        description="Build version-aware context for AI code generation"
    )
    parser.add_argument("--object", dest="object_name", help="Fully qualified object name")
    parser.add_argument("--package", dest="package_name", help="Target package name")
    parser.add_argument("--import-name", dest="import_name", help="Import name to resolve")
    parser.add_argument(
        "--project-path", dest="project_path", help="Project root for package manager detection"
    )
    parser.add_argument(
        "--min-python", dest="min_python", help="Required minimum Python version (e.g. 3.10)"
    )
    parser.add_argument(
        "--package-version-spec",
        dest="package_version_spec",
        help="Version constraint (e.g. '>=2.1,<3')",
    )
    parser.add_argument(
        "--budget",
        default="medium",
        choices=["short", "medium", "full"],
        help="Context size mode",
    )
    args = parser.parse_args()

    result = prepare_codegen_context(
        object_name=args.object_name,
        package_name=args.package_name,
        import_name=args.import_name,
        project_path=args.project_path,
        min_python=args.min_python,
        package_version_spec=args.package_version_spec,
        budget=args.budget,
    )
    print(json.dumps(result, indent=2, default=str))


if __name__ == "__main__":
    main()
