# PyCode MCP Server

A **Model Context Protocol (MCP) server** that provides Python code intelligence to AI coding agents. It exposes documentation lookup, environment introspection, code analysis, and diagnostics as structured MCP tools — enabling agents like Claude Code, Cursor, and others to generate more accurate, version-compatible Python code with fewer tokens.

## Features

### Semantic Intelligence (Jedi)

| Tool | Description |
|------|-------------|
| `get_local_docs` | Look up signatures, parameters, docstrings, and examples for any Python object |
| `inspect_environment` | List installed packages, Python version, virtualenv info |
| `get_package_details` | Get version, imports, exports, and dependencies for a specific package |
| `find_package_for_import` | Reverse lookup: resolve `import X` to its PyPI package name |
| `analyze_file` | Extract functions, classes, imports, and structure from a Python file |
| `analyze_project` | Project-wide analysis with import graphs and circular dependency detection |
| `get_diagnostics` | Run Jedi, Pyflakes, and optionally mypy/pyright diagnostics on a file |
| `get_install_instructions` | Detect package manager (pip/poetry/uv) and suggest install commands |
| `prepare_codegen_context` | Build budgeted, version-aware coding context with compatibility warnings |

### Text Search (ripgrep)

| Tool | Description |
|------|-------------|
| `search_text` | Fast regex search across all file types (Python, YAML, TOML, Markdown, etc.) |
| `find_config_references` | Trace a config key across .py, .yaml, .toml, .env, Dockerfile with categorized results |

### Structural Code Analysis (ast-grep)

| Tool | Description |
|------|-------------|
| `search_code_pattern` | AST-aware pattern matching with metavariables ($NAME, $$$ARGS) |
| `check_anti_patterns` | Run YAML-defined lint rules to detect code smells structurally |
| `transform_code` | Pattern-based code rewriting with dry-run support and diff preview |

## Quick Start

### Installation

```bash
# Clone the repository
git clone https://github.com/spkc83/pycode-mcp-server.git
cd pycode-mcp-server

# Install dependencies
pip install -e .

# Install optional enhanced features (ast-grep structural analysis)
pip install -e ".[enhanced]"
```

#### System Requirements

- **Python** ≥ 3.10
- **ripgrep** (optional, for `search_text` and `find_config_references`):
  Install from https://github.com/BurntSushi/ripgrep#installation

### Running the Server

```bash
# Run with stdio transport (default for most agents)
python mcp_server.py

# Or use the installed entry point
pycode-mcp-server
```

### Connecting to AI Agents

#### Claude Code
```bash
claude mcp add pycode-mcp-server -- python /path/to/pycode-mcp-server/mcp_server.py
```

#### Cursor
Add to your `.cursor/mcp.json`:
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

#### MCP Inspector (for testing)
```bash
npx @modelcontextprotocol/inspector python mcp_server.py
```

#### OpenAI Codex CLI

Add to your `~/.codex/config.toml`:

```toml
[mcp_servers.pycode_mcp_server]
command = "/absolute/path/to/python"
args = ["/absolute/path/to/pycode-mcp-server/mcp_server.py"]
```

> **Important — Codex CLI compatibility notes:**
>
> - **Use underscores in the server name**, not hyphens. Codex sanitizes names internally
>   (`-` → `_`), but the `/mcp` UI matches against the raw config name. Using hyphens
>   causes `Tools: (none)` in the UI even though tools load correctly.
> - **Use an absolute path to the Python binary.** Codex calls `env_clear()` before
>   spawning MCP subprocesses, stripping `VIRTUAL_ENV`, `CONDA_PREFIX`, and `PYTHONPATH`.
>   A relative `python` may resolve to the wrong interpreter.

## Directory Structure

```
pycode-mcp-server/
├── mcp_server.py              # MCP server entrypoint (FastMCP, 14 tools)
├── pyproject.toml             # Package configuration
├── requirements.txt           # Dependencies
├── VERSION                    # Version file (5.0.1)
├── SKILL.md                   # General-purpose AI skill definition
├── CHANGELOG.md               # Version history
├── scripts/
│   ├── __init__.py            # Package init
│   ├── cache.py               # Caching layer (disk + in-memory)
│   ├── code_analyzer.py       # AST-based source code analysis
│   ├── diagnostics.py         # Unified diagnostics (Jedi/Pyflakes/mypy)
│   ├── doc_lookup.py          # Documentation lookup engine
│   ├── inspect_env.py         # Environment & package introspection
│   ├── jedi_engine.py         # Jedi-powered code intelligence
│   ├── project_analyzer.py    # Project-level analysis & import graphs
│   ├── ripgrep_engine.py      # Ripgrep-powered text search
│   ├── ast_grep_engine.py     # AST-grep structural search & transforms
│   ├── default_rules.yml      # Built-in anti-pattern rules
│   ├── benchmark.py           # Performance benchmarking suite
│   ├── agent_eval.py          # Agent evaluation framework
│   └── token_estimator.py     # Token cost estimation
└── tests/
    ├── test_basic.py          # Core module tests
    ├── test_benchmarks.py     # Benchmark tests
    ├── test_diagnostics.py    # Diagnostics tests
    ├── test_jedi_engine.py    # Jedi engine tests
    ├── test_mcp_server.py     # MCP server integration tests
    ├── test_project_analyzer.py  # Project analyzer tests
    ├── test_ripgrep_engine.py # Ripgrep engine tests
    └── test_ast_grep_engine.py # AST-grep engine tests
```

## Development

```bash
# Install dev dependencies
pip install -e ".[dev,enhanced]"

# Run tests
pytest tests/

# Run benchmarks
python scripts/benchmark.py
python scripts/token_estimator.py
```

## Version-Aware Codegen Context (New)

Use `prepare_codegen_context` when an agent needs a single payload with local signature/docs,
environment/package compatibility checks, and install guidance.

### MCP Example

Tool: `prepare_codegen_context`

Args example:

```json
{
  "object_name": "pandas.DataFrame.merge",
  "package_name": "pandas",
  "package_version_spec": ">=2.0,<3",
  "min_python": "3.10",
  "budget": "short",
  "task_goal": "implementation"
}
```

### Budget Modes

- `short`: minimal high-signal fields for token efficiency
- `medium`: balanced details for coding workflows (default)
- `full`: complete payload including expanded docs/metadata

### Task Goals

- `implementation`: prioritize signatures + parameters + examples
- `debugging`: prioritize raises/source/related metadata
- `refactor`: emphasize methods/attributes/related symbols
- `testing`: emphasize returns/raises/examples for assertions
- `research`: broad summary for exploration

The response includes:

- `docs`: local signatures/parameters/examples from runtime-installed libraries
- `compatibility`: Python/package constraint checks and warnings
- `install`: package-manager-aware install command when package is missing
- `agent_contract`: guardrails for version-compatible code generation

## Benchmarking & Validation Playbook

Use this workflow to validate token savings and compatibility quality before adoption.

### 1) Generate baseline token report

```bash
python scripts/token_estimator.py --format markdown --output references/benchmark_baseline.md
python scripts/token_estimator.py --format json --output references/benchmark_baseline.json
```

### 2) Compare budget/task_goal payload sizes

```bash
python scripts/codegen_context.py --object json.dumps --budget short --task-goal implementation > /tmp/ctx_short.json
python scripts/codegen_context.py --object json.dumps --budget medium --task-goal implementation > /tmp/ctx_medium.json
python scripts/codegen_context.py --object json.dumps --budget full --task-goal implementation > /tmp/ctx_full.json

python scripts/token_estimator.py --estimate-file /tmp/ctx_short.json
python scripts/token_estimator.py --estimate-file /tmp/ctx_medium.json
python scripts/token_estimator.py --estimate-file /tmp/ctx_full.json
```

Expected: `short < medium < full` token counts.

### 3) Validate compatibility warnings

```bash
# Missing package warning + install command
python scripts/codegen_context.py --package some_unlikely_package_xyz --budget medium

# Python version incompatibility warning
python scripts/codegen_context.py --object json.dumps --min-python 99.0 --budget medium

# Package version constraint check
python scripts/codegen_context.py --package pytest --package-version-spec ">=1.0,<999.0" --budget medium
```

Expected: `compatibility.is_compatible` flips to `false` on deliberate incompatibility inputs.

### 4) Validate goal-specific shaping

```bash
python scripts/codegen_context.py --object json.dumps --task-goal debugging --budget short
python scripts/codegen_context.py --object json.dumps --task-goal testing --budget short
python scripts/codegen_context.py --object json.dumps --task-goal refactor --budget short
```

Expected: returned `docs` fields differ by `task_goal` and stay minimal under `short` budget.

### 5) Regression safety checks

```bash
ruff check scripts/ tests/ mcp_server.py
ruff format --check scripts/ tests/ mcp_server.py
pytest -q
```

## License

MIT
