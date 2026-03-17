---
name: Python Code Intelligence
description: Provides Python environment information (signatures, docs, package details) to reduce token usage and increase code generation accuracy
---

# Python Code Intelligence Skill

This skill enables AI agents to access local Python environment intelligence for generating accurate, version-compatible code. It is designed for **general-purpose AI agents** that need code generation capabilities but may not be dedicated coding assistants.

> **For dedicated coding agents with MCP support** (Claude Code, Cursor, etc.), use the MCP server directly. See [README.md](README.md) for setup instructions.

## When to Use This Skill

Use this skill when you need to:
- **Look up function signatures** before generating code that calls Python libraries
- **Check installed package versions** to ensure generated code is compatible
- **Get install instructions** for packages the user needs
- **Analyze existing code** to understand its structure before modifying it
- **Run diagnostics** to validate generated code

## Available Capabilities

### 1. Documentation Lookup
Get accurate signatures, parameters, and docstrings for any importable Python object.

```bash
# Via MCP (preferred)
# Tool: get_local_docs
# Args: {"object_name": "json.dumps"}

# Via CLI fallback
python scripts/doc_lookup.py json.dumps
python scripts/doc_lookup.py pandas.DataFrame.merge --no-cache
```

### 2. Environment Inspection
Check the Python runtime and installed packages.

```bash
# Via MCP: inspect_environment (no args)
# Via MCP: get_package_details {"package_name": "requests"}

# Via CLI fallback
python scripts/inspect_env.py --env
python scripts/inspect_env.py --package requests
```

### 3. Import Resolution
Find which PyPI package provides a given import name.

```bash
# Via MCP: find_package_for_import {"import_name": "cv2"}

# Via CLI fallback
python scripts/inspect_env.py --find-import cv2
```

### 4. Install Instructions
Get package manager-specific install commands.

```bash
# Via MCP: get_install_instructions {"package_name": "requests"}
# Returns: {"install_command": "poetry add requests", "detected_package_manager": "poetry"}
```

### 5. Code Analysis
Analyze Python source files or entire projects.

```bash
# Via MCP: analyze_file {"file_path": "/path/to/file.py"}
# Via MCP: analyze_project {"project_path": "/path/to/project"}

# Via CLI fallback
python scripts/code_analyzer.py /path/to/file.py
python scripts/project_analyzer.py /path/to/project
```

### 6. Diagnostics
Run code quality checks combining Jedi, Pyflakes, and optionally mypy/pyright.

```bash
# Via MCP: get_diagnostics {"file_path": "/path/to/file.py", "type_check": true}

# Via CLI fallback
python scripts/diagnostics.py /path/to/file.py --type-check
```

### 7. Budgeted Version-Aware Codegen Context
Build a single context contract for coding agents that includes local API details,
compatibility checks, and install guidance.

```bash
# Via MCP: prepare_codegen_context
# Args example:
# {
#   "object_name": "json.dumps",
#   "package_name": "json",
#   "min_python": "3.10",
#   "package_version_spec": ">=3.0",
#   "budget": "short",
#   "task_goal": "implementation"
# }

# Via CLI fallback
python scripts/codegen_context.py --object json.dumps --budget short --task-goal implementation
python scripts/codegen_context.py --package requests --package-version-spec ">=2.30,<3"
```

Supported `task_goal` values:
- `implementation`
- `debugging`
- `refactor`
- `testing`
- `research`

## Connecting via MCP

If your AI agent supports the Model Context Protocol:

```json
{
  "mcpServers": {
    "pycode-mcp-server": {
      "command": "python",
      "args": ["/path/to/pycode-mcp-server/mcp_server.py"]
    }
  }
}
```

## Best Practices for AI Agents

1. **Always check signatures before generating function calls** — use `get_local_docs` to avoid hallucinated parameters.
2. **Check the environment first** — use `inspect_environment` to know what packages are available and their versions.
3. **Use install instructions** — when a package is needed, use `get_install_instructions` to give the user the correct command for their package manager.
4. **Analyze before modifying** — use `analyze_file` on existing code before suggesting changes to understand its structure.
5. **Use budgeted context generation** — call `prepare_codegen_context` first for token-efficient, compatibility-aware coding output.
6. **Choose a task goal explicitly** — set `task_goal` so returned fields match the coding intent and reduce unnecessary tokens.
