# PyCode MCP Server

A **Model Context Protocol (MCP) server** that provides Python code intelligence to AI coding agents. It exposes documentation lookup, environment introspection, code analysis, and diagnostics as structured MCP tools — enabling agents like Claude Code, Cursor, and others to generate more accurate, version-compatible Python code with fewer tokens.

## Features

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

## Quick Start

### Installation

```bash
# Clone the repository
git clone https://github.com/spkc83/pycode-mcp-server.git
cd pycode-mcp-server

# Install dependencies
pip install -e .
```

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

## Directory Structure

```
pycode-mcp-server/
├── mcp_server.py              # MCP server entrypoint (FastMCP)
├── pyproject.toml             # Package configuration
├── requirements.txt           # Dependencies
├── VERSION                    # Version file (4.0.0)
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
│   ├── benchmark.py           # Performance benchmarking suite
│   ├── agent_eval.py          # Agent evaluation framework
│   └── token_estimator.py     # Token cost estimation
└── tests/
    ├── test_basic.py          # Core module tests
    ├── test_benchmarks.py     # Benchmark tests
    ├── test_diagnostics.py    # Diagnostics tests
    ├── test_jedi_engine.py    # Jedi engine tests
    ├── test_mcp_server.py     # MCP server integration tests
    └── test_project_analyzer.py  # Project analyzer tests
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
  "budget": "short"
}
```

### Budget Modes

- `short`: minimal high-signal fields for token efficiency
- `medium`: balanced details for coding workflows (default)
- `full`: complete payload including expanded docs/metadata

The response includes:

- `docs`: local signatures/parameters/examples from runtime-installed libraries
- `compatibility`: Python/package constraint checks and warnings
- `install`: package-manager-aware install command when package is missing
- `agent_contract`: guardrails for version-compatible code generation

## License

MIT
