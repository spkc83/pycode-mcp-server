# Python Code Assistant Skill

This repository contains a self‑contained **Agent Skill** designed to help
agents generate, analyze, test and debug Python code without resorting
to external web searches.  It follows the open [Agent Skills
specification](https://agentskills.io/specification?utm_source=chatgpt.com)
and is ready to drop into frameworks such as Claude Code, OpenCode and
VS Code Copilot.  The skill introspects the local Python environment,
uses **Jedi** for intelligent code analysis and documentation,
examines existing source files, and provides project-level analysis
capabilities.  When a requested library is missing, it also suggests
commands for installing it.

## Contents

```
python-code-assistant-skill/
├── SKILL.md                  # Skill definition with description and usage
├── scripts/                  # Helper scripts for code intelligence
│   ├── jedi_engine.py        # Jedi-powered completions, search, refactoring, diagnostics
│   ├── project_analyzer.py   # Project-level analysis, import graphs, cross-references
│   ├── diagnostics.py        # Unified diagnostics (Jedi + Pyflakes + mypy/pyright)
│   ├── doc_lookup.py         # Documentation lookup (Jedi primary, inspect fallback)
│   ├── code_analyzer.py      # AST-based Python source analysis
│   ├── inspect_env.py        # Environment and package inspection
│   ├── cache.py              # JSON-based caching with LFU eviction and TTL
│   ├── benchmark.py          # Performance benchmark runner for timing and memory
│   ├── agent_eval.py         # Agent evaluation harness for skill benchmarking
│   ├── token_estimator.py    # Token cost estimation and savings calculation
│   ├── health_check.py       # Quick health check for all skill components
│   └── debug_wrapper.py      # Debug wrapper to log skill usage
├── references/
│   └── local_docs_index.json # Cache file for documentation and package tracking
├── .vscode/
│   ├── tasks.json            # Predefined VS Code tasks for easy execution
│   └── extensions.json       # Recommended extensions for VS Code
├── .github/workflows/
│   └── ci.yml                # GitHub Actions workflow for CI
├── tests/
│   ├── __init__.py
│   ├── test_basic.py         # Core test suite
│   ├── test_jedi_engine.py   # Jedi engine tests
│   ├── test_project_analyzer.py # Project analyzer tests
│   └── test_diagnostics.py   # Diagnostics tests
├── pyproject.toml            # Modern Python packaging (PEP 517/518)
├── CHANGELOG.md              # Version history
├── VERSION                   # Current version number (3.0.0)
├── requirements.txt          # Python dependencies
├── LICENSE                   # MIT license
├── .gitignore
└── README.md                 # This file
```

## Quick Start

1. **Install dependencies**: install Python ≥3.9 and then run
   `pip install -r requirements.txt` to install Jedi, pytest, and ruff.

2. **Inspect your environment**:

   ```bash
   python scripts/inspect_env.py
   ```
   This prints JSON with installed packages, versions, and metadata.

3. **Look up documentation** (Jedi-powered):

   ```bash
   python scripts/doc_lookup.py pandas.DataFrame.merge
   ```
   Returns structured JSON with signatures, parameters, examples, and
   related functions — powered by Jedi for accurate type inference.

4. **Analyze existing source**:

   ```bash
   python scripts/code_analyzer.py path/to/your_module.py
   ```
   Returns structured analysis of functions, classes, imports, and
   dependencies.

5. **Analyze an entire project**:

   ```bash
   python scripts/project_analyzer.py /path/to/project
   ```
   Builds import graphs, detects circular dependencies, classifies
   third-party vs stdlib dependencies, and generates project summaries.

6. **Code intelligence** (Jedi engine):

   ```bash
   # Semantic search across a project
   python scripts/jedi_engine.py search --query "DataFrame" --project /path

   # Find all references
   python scripts/jedi_engine.py references --file path.py --line 10 --col 5

   # Rename a symbol safely
   python scripts/jedi_engine.py rename --file path.py --line 10 --col 5 --new-name "better_name"

   # Get diagnostics
   python scripts/jedi_engine.py diagnostics --file path.py
   ```

7. **Run diagnostics**:

   ```bash
   python scripts/diagnostics.py path/to/file.py
   python scripts/diagnostics.py path/to/file.py --type-check  # include mypy/pyright
   python scripts/diagnostics.py path/to/project/ --summary     # project-wide
   ```

8. **Run the tests**:

   ```bash
   pytest -q
   ```

9. **Run a health check**:

   ```bash
   python scripts/health_check.py
   ```
   Verifies that all scripts are working correctly.

10. **Debug usage** (optional):

    ```bash
    python scripts/debug_wrapper.py doc_lookup json.dumps
    python scripts/debug_wrapper.py jedi_engine --search DataFrame .
    python scripts/debug_wrapper.py project_analyzer /path/to/project
    python scripts/debug_wrapper.py diagnostics path/to/file.py
    ```
    Logs all skill invocations to `references/skill_usage.log`.

## Continuous Integration

The repository includes a GitHub Actions workflow (`.github/workflows/ci.yml`)
that runs on every push and pull request.  It sets up Python 3.9–3.13,
installs dependencies, runs linting with ruff, formatting checks, the
test suite, and verifies all scripts work correctly.

## Versioning

The current version of the skill is stored in the `VERSION` file.  See
`CHANGELOG.md` for a history of changes.  Update the version number and
changelog whenever you make a backwards‑incompatible change or add new
features.  Because this repository is intended to be used as a
stand‑alone skill package, semantic versioning is recommended.

## License

This project is licensed under the MIT License.  See the `LICENSE`
file for full text.