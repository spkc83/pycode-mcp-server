---
name: python-code-assistant
description: |
  Generates, analyzes, debugs and tests Python code using only local context.  This
  skill inspects the local Python environment, reads docstrings and offline
  documentation from installed packages, and synthesizes example patterns found
  in the workspace to produce high‑quality solutions.  It never performs
  external web searches to gather information, instead relying on what is
  available locally.  When a requested library is missing, the skill returns
  the appropriate command to install it via pip or conda.
license: MIT
compatibility: |
  Works with any agent runtime that supports the open Agent Skills
  specification and can execute shell and Python commands (e.g. Claude Code,
  OpenCode, VS Code Copilot agents).  The skill assumes access to the local
  filesystem and a Python interpreter.
allowed-tools: Bash Python Read Write
metadata:
  author: spkc83 & Opencode
  version: "2.0.0"
---

# Python Code Assistant Skill

This skill equips an agent to build and refine Python programs without
reaching out to the internet for help.  It introspects the local
environment, examines code and documentation on disk, and proposes
installation steps for missing dependencies.  Typical use cases include
generating new scripts, debugging existing code, refactoring functions,
inspecting package APIs and versions, and writing tests.

## Purpose

* Detect which packages and versions are already installed.
* Map package names to import names (e.g., `Pillow` → `PIL`).
* Retrieve structured documentation for Python objects including signatures,
  parameters, types, examples, and related functions.
* Parse existing Python files to understand their structure and dependencies.
* Generate new code using idiomatic patterns found locally.
* Suggest pip or conda commands to install missing packages when needed.
* Produce simple unit tests and run them to validate generated code.

## How to Use

### 1. Check Package Availability

Before writing code that uses external libraries, check if they're installed:

```bash
# Check if a specific package is installed
python scripts/inspect_env.py --package pandas

# Find which package provides an import name
python scripts/inspect_env.py --find-import PIL
# Returns: {"import_name": "PIL", "package": "pillow"}

# Get full environment with all packages
python scripts/inspect_env.py
```

If a required library is absent, suggest installation:
```bash
pip install <package>
# or
conda install <package> -y
```

### 2. Lookup Documentation

Get structured documentation for any Python object:

```bash
# Get structured JSON documentation
python scripts/doc_lookup.py json.dumps

# Get raw pydoc text (legacy mode)
python scripts/doc_lookup.py pandas.DataFrame.merge --raw
```

The structured output includes:
- **signature**: Full function signature with types
- **import_statement**: How to import the object
- **parameters**: List of parameters with types, defaults, and requirements
- **returns**: Return type information
- **examples**: Code examples extracted from docstrings
- **related**: Related functions in the same module

### 3. Analyze Existing Code

Understand the structure of Python files:

```bash
# Get structured analysis
python scripts/code_analyzer.py path/to/file.py

# Get raw AST dump (legacy mode)
python scripts/code_analyzer.py path/to/file.py --raw
```

The structured output includes:
- **imports** and **from_imports**: All import statements
- **third_party_dependencies**: Non-stdlib dependencies
- **functions**: Function names, signatures, parameters, decorators
- **classes**: Class names, bases, methods, attributes
- **decorators_used**: All decorators found in the code

### 4. Generate Tests and Validate Code

When producing new code or refactoring existing functions, also write
unit tests. Run tests locally (e.g., via `pytest`) and report failures
back to the user alongside suggested fixes.

### 5. Manage the Cache

Documentation lookups are cached for performance:

```bash
# View cache statistics
python scripts/cache.py --stats

# Clear the cache
python scripts/cache.py --clear
```

## Scripts Reference

### `scripts/inspect_env.py`

Lists installed packages with comprehensive metadata.

| Flag | Description |
|------|-------------|
| `--simple` | Output just `[(name, version), ...]` format |
| `--package NAME` | Get detailed info for a specific package |
| `--find-import NAME` | Find which package provides an import name |
| `--env` | Show Python environment info only |
| `--no-cache` | Skip cache update |

**Output fields** (for `--package`):
- `name`: Package name
- `version`: Installed version
- `import_names`: Actual import names (e.g., `["PIL"]` for Pillow)
- `summary`: Package description
- `dependencies`: List of dependencies
- `location`: Installation path
- `main_exports`: Main classes/functions exported

### `scripts/doc_lookup.py`

Fetches structured documentation for Python objects.

| Flag | Description |
|------|-------------|
| `--no-cache` | Bypass the documentation cache |
| `--raw` | Return raw pydoc text instead of structured JSON |

**Output fields** (structured mode):
- `name`: Object name
- `found`: Whether the object was found
- `object_type`: `function`, `class`, `module`, `builtin`
- `import_statement`: How to import the object
- `signature`: Full signature with types
- `short_description`: First line of docstring
- `full_docstring`: Complete documentation
- `parameters`: List of parameters with types and defaults
- `returns`: Return type info
- `examples`: Code examples from docstrings
- `raises`: Exceptions that may be raised
- `related`: Related functions/classes
- `methods`: (for classes) List of methods
- `source_file`: Path to source code

### `scripts/code_analyzer.py`

Parses Python source code and returns structured information.

| Flag | Description |
|------|-------------|
| `--raw` | Output raw AST dump (legacy mode) |
| `--json` | Force JSON output |

**Output fields**:
- `file_name`: Name of analyzed file
- `module_description`: Module docstring summary
- `imports` / `from_imports`: Import statements
- `third_party_dependencies`: Non-stdlib imports
- `functions`: Functions with signatures, parameters, decorators
- `classes`: Classes with methods, attributes, bases
- `global_variables`: Module-level variables
- `decorators_used`: All decorators found
- `summary`: Counts of functions, classes, imports

### `scripts/cache.py`

Manages the JSON-based documentation cache.

| Flag | Description |
|------|-------------|
| `--stats` | Display cache statistics |
| `--clear` | Reset the entire cache |
| `--path FILE` | Use a custom cache file path |

### `scripts/health_check.py`

Quick health check to verify all skill components are working correctly.

```bash
python scripts/health_check.py
```

**Output**: Verifies that `doc_lookup.py`, `inspect_env.py`, `code_analyzer.py`,
and `cache.py` are all functioning correctly. Returns exit code 0 on success.

### `scripts/debug_wrapper.py`

Debug wrapper that logs all skill invocations for troubleshooting.

```bash
# Look up documentation with logging
python scripts/debug_wrapper.py doc_lookup json.dumps

# Inspect environment with logging
python scripts/debug_wrapper.py inspect_env --find-import PIL

# Analyze code with logging
python scripts/debug_wrapper.py code_analyzer path/to/file.py
```

**Log location**: `references/skill_usage.log`

Each log entry contains:
- `timestamp`: When the script was called
- `script`: Which script was invoked
- `args`: Arguments passed
- `result_preview`: First 500 characters of the output

## Cache Details

The cache is stored at `references/local_docs_index.json` and contains:
- **Package tracking**: Hash of installed packages to detect environment changes
- **Docstring cache**: Up to 500 entries with LFU eviction
- **Statistics**: Cache hits, misses, and eviction counts

When packages change (detected via hash), all cached docstrings are invalidated
to ensure documentation accuracy.

## Example Workflow

```python
# Agent receives: "Help me parse JSON with error handling"

# 1. Check if json is available (it's stdlib, always available)
$ python scripts/doc_lookup.py json.loads
{
  "name": "json.loads",
  "found": true,
  "signature": "loads(s, *, cls=None, ...)",
  "import_statement": "from json import loads",
  "parameters": [...],
  "raises": [{"exception": "JSONDecodeError", "description": "..."}]
}

# 2. Agent can now generate code with proper error handling:
from json import loads, JSONDecodeError

def safe_parse(data: str) -> dict | None:
    try:
        return loads(data)
    except JSONDecodeError as e:
        print(f"Invalid JSON: {e}")
        return None
```

See the top‑level `README.md` for more examples.
