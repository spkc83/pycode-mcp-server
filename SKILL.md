---
name: python-code-assistant
description: |
  Generates, analyzes, debugs, refactors and tests Python code using Jedi-powered
  local intelligence.  This skill uses Jedi for accurate type inference,
  semantic search, refactoring, and diagnostics.  It inspects the local Python
  environment, reads docstrings and documentation from installed packages, builds
  project-level import graphs, and synthesizes example patterns found in the
  workspace to produce high‑quality solutions.  It never performs external web
  searches to gather information, instead relying on what is available locally.
  When a requested library is missing, the skill returns the appropriate command
  to install it via pip or conda.
license: MIT
compatibility: |
  Works with any agent runtime that supports the open Agent Skills
  specification and can execute shell and Python commands (e.g. Claude Code,
  OpenCode, VS Code Copilot agents).  The skill assumes access to the local
  filesystem and a Python ≥3.9 interpreter with Jedi installed.
allowed-tools: Bash Python Read Write
metadata:
  author: spkc83 & Opencode
  version: "3.0.0"
---

# Python Code Assistant Skill

This skill equips an agent to build and refine Python programs without
reaching out to the internet for help.  It uses **Jedi** as the primary
code intelligence engine for accurate documentation lookup, type inference,
semantic search, and refactoring.  It also introspects the local environment,
examines code and documentation on disk, builds project-level import graphs,
and proposes installation steps for missing dependencies.

## Purpose

* Detect which packages and versions are already installed.
* Map package names to import names (e.g., `Pillow` → `PIL`).
* Retrieve structured documentation for Python objects including signatures,
  parameters, types, examples, and related functions — powered by Jedi.
* Parse existing Python files to understand their structure and dependencies.
* Analyze entire projects: import graphs, circular dependencies, cross-references.
* Perform semantic search across projects (find functions/classes by name).
* Refactor code safely: rename symbols, extract variables/functions, inline.
* Run diagnostics: syntax errors, undefined names, unused imports, type checking.
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

Get structured documentation for any Python object (Jedi-powered):

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
- **third_party_dependencies**: Non-stdlib dependencies (detected using ~200 stdlib modules)
- **functions**: Function names, signatures, parameters, decorators
- **classes**: Class names, bases, methods, attributes
- **decorators_used**: All decorators found in the code

### 4. Analyze an Entire Project

Get project-level insights:

```bash
# Full project analysis
python scripts/project_analyzer.py /path/to/project

# Import graph only
python scripts/project_analyzer.py /path/to/project --graph

# Detect circular dependencies
python scripts/project_analyzer.py /path/to/project --cycles

# Include cross-references (slower, uses Jedi)
python scripts/project_analyzer.py /path/to/project --cross-refs
```

The output includes:
- **files**: Per-file analysis (functions, classes, dependencies)
- **import_graph**: Module-to-module dependency graph
- **circular_dependencies**: Detected import cycles
- **third_party_dependencies**: All external packages used
- **summary**: Aggregate statistics

### 5. Code Intelligence (Jedi Engine)

Use Jedi for advanced code intelligence:

```bash
# Get autocompletions
python scripts/jedi_engine.py completions --file path.py --line 10 --col 5

# Go to definition / type inference
python scripts/jedi_engine.py definitions --file path.py --line 10 --col 5

# Find all references
python scripts/jedi_engine.py references --file path.py --line 10 --col 5

# Semantic search across a project
python scripts/jedi_engine.py search --query "DataFrame" --project /path

# Rename a symbol safely
python scripts/jedi_engine.py rename --file path.py --line 10 --col 5 --new-name "better_name"

# Get hover information
python scripts/jedi_engine.py hover --file path.py --line 10 --col 5

# Check Jedi status
python scripts/jedi_engine.py status
```

### 6. Run Diagnostics

Check code quality with unified diagnostics:

```bash
# All available checks
python scripts/diagnostics.py file.py

# Syntax errors only
python scripts/diagnostics.py file.py --syntax-only

# Include type checking (mypy/pyright)
python scripts/diagnostics.py file.py --type-check

# Project-wide diagnostics
python scripts/diagnostics.py /path/to/project/ --summary
```

Diagnostic sources:
- **Jedi**: Syntax errors and some semantic issues
- **Pyflakes**: Undefined names, unused imports, redefined variables
- **mypy/pyright**: Full type checking (when installed)

### 7. Generate Tests and Validate Code

When producing new code or refactoring existing functions, also write
unit tests. Run tests locally (e.g., via `pytest`) and report failures
back to the user alongside suggested fixes.

### 8. Manage the Cache

Documentation lookups are cached for performance (7-day TTL):

```bash
# View cache statistics
python scripts/cache.py --stats

# Clear the cache
python scripts/cache.py --clear
```

## Scripts Reference

### `scripts/jedi_engine.py`

Jedi-powered code intelligence engine.

| Command | Description |
|---------|-------------|
| `completions` | Get autocompletion suggestions |
| `definitions` | Go to definition / type inference |
| `references` | Find all references to a symbol |
| `goto` | Go to definition (without following imports) |
| `hover` | Get hover information (type + docstring) |
| `signatures` | Get function signature help |
| `search` | Semantic search across a project |
| `rename` | Rename a symbol safely across files |
| `diagnostics` | Get syntax error diagnostics |
| `status` | Check Jedi availability |

### `scripts/project_analyzer.py`

Project-level Python code analysis.

| Flag | Description |
|------|-------------|
| `--exclude PATTERNS` | Comma-separated glob patterns to exclude |
| `--depth N` | Maximum directory depth to traverse |
| `--graph` | Show only the import graph |
| `--cycles` | Show only circular dependencies |
| `--cross-refs` | Include Jedi-based cross-references |

### `scripts/diagnostics.py`

Unified diagnostics from multiple sources.

| Flag | Description |
|------|-------------|
| `--syntax-only` | Only check for syntax errors |
| `--type-check` | Include type checking (mypy/pyright) |
| `--summary` | Project-wide diagnostic summary |

### `scripts/doc_lookup.py`

Fetches structured documentation using Jedi (primary) with inspect/pydoc fallback.

| Flag | Description |
|------|-------------|
| `--no-cache` | Bypass the documentation cache |
| `--raw` | Return raw pydoc text instead of structured JSON |

### `scripts/code_analyzer.py`

Parses Python source code and returns structured information.

| Flag | Description |
|------|-------------|
| `--raw` | Output raw AST dump (legacy mode) |
| `--json` | Force JSON output |

### `scripts/inspect_env.py`

Lists installed packages with comprehensive metadata.

| Flag | Description |
|------|-------------|
| `--simple` | Output just `[(name, version), ...]` format |
| `--package NAME` | Get detailed info for a specific package |
| `--find-import NAME` | Find which package provides an import name |
| `--env` | Show Python environment info only |
| `--no-cache` | Skip cache update |

### `scripts/cache.py`

Manages the JSON-based documentation cache with LFU eviction and TTL.

| Flag | Description |
|------|-------------|
| `--stats` | Display cache statistics |
| `--clear` | Reset the entire cache |
| `--path FILE` | Use a custom cache file path |

### `scripts/benchmark.py`

Performance benchmark runner for the skill. Measures execution time, memory usage, and compares approaches.

| Command/Flag | Description |
|--------------|-------------|
| `--suite` | Run a specific benchmarking suite (e.g. `doc_lookup`) |
| `--iterations` | Number of iterations per benchmark (default: 20) |
| `--format` | Output format (`markdown`, `json`, `table`) |

### `scripts/agent_eval.py`

Agent evaluation harness for benchmarking coding agents with/without the skill.

| Command | Description |
|---------|-------------|
| `list-tasks` | List all evaluation tasks |
| `record` | Record an evaluation run manually |
| `parse-logs` | Parse agent conversation logs to extract metrics |
| `compare` | Compare results between with-skill and without-skill runs |
| `report` | Generate a full evaluation report |

### `scripts/token_estimator.py`

Token cost estimator to calculate token and cost savings from using the skill.

| Command/Flag | Description |
|--------------|-------------|
| `--compare` | Compare a specific scenario (e.g., `doc_lookup json.dumps`) |
| `--estimate` | Estimate tokens for a string of text |
| `--estimate-file` | Estimate tokens for a file |
| `--model` | LLM model to use for cost estimation (default: `claude-3.5-sonnet`) |

### `scripts/health_check.py`

Quick health check to verify all skill components are working correctly.

```bash
python scripts/health_check.py
```

### `scripts/debug_wrapper.py`

Debug wrapper that logs all skill invocations for troubleshooting.

```bash
python scripts/debug_wrapper.py doc_lookup json.dumps
python scripts/debug_wrapper.py jedi_engine --search DataFrame .
python scripts/debug_wrapper.py project_analyzer /path/to/project
python scripts/debug_wrapper.py diagnostics path/to/file.py
```

**Log location**: `references/skill_usage.log`

## Cache Details

The cache is stored at `references/local_docs_index.json` and contains:
- **Package tracking**: Hash of installed packages to detect environment changes
- **Docstring cache**: Up to 500 entries with LFU eviction and 7-day TTL
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
