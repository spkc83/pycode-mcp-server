# Python Code Assistant Skill

This repository contains a self‑contained **Agent Skill** designed to help
agents generate, analyze, test and debug Python code without resorting
to external web searches.  It follows the open [Agent Skills
specification](https://agentskills.io/specification?utm_source=chatgpt.com)
and is ready to drop into frameworks such as Claude Code, OpenCode and
VS Code Copilot.  The skill introspects the local Python environment,
consults docstrings of installed packages and examines existing source
files to provide contextual code generation.  When a requested library
is missing, it also suggests commands for installing it.

## Contents

```
python-code-assistant-skill/
├── SKILL.md                # Skill definition with description and usage
├── scripts/                # Helper scripts for environment inspection and docs
│   ├── inspect_env.py      # Lists installed packages with metadata
│   ├── doc_lookup.py       # Retrieves structured documentation for Python objects
│   ├── code_analyzer.py    # Parses Python source and returns structured analysis
│   ├── cache.py            # JSON-based caching for documentation lookups
│   ├── health_check.py     # Quick health check to verify skill functionality
│   └── debug_wrapper.py    # Debug wrapper to log skill usage
├── references/
│   └── local_docs_index.json # Cache file for documentation and package tracking
├── .vscode/
│   ├── tasks.json          # Predefined VS Code tasks for easy execution
│   └── extensions.json     # Recommended extensions for VS Code
├── .github/workflows/
│   └── ci.yml              # GitHub Actions workflow for CI
├── tests/
│   ├── __init__.py
│   └── test_basic.py       # Comprehensive test suite (48 tests)
├── pyproject.toml          # Modern Python packaging (PEP 517/518)
├── CHANGELOG.md            # Version history
├── VERSION                 # Current version number (2.0.0)
├── requirements.txt        # Python dependencies for development/CI
├── LICENSE                 # MIT license
├── .gitignore
└── README.md               # This file
```
python-code-assistant-skill/
├── SKILL.md                # Skill definition with description and usage
├── scripts/                # Helper scripts for environment inspection and docs
│   ├── inspect_env.py
│   ├── doc_lookup.py
│   └── code_analyzer.py
├── references/
│   └── local_docs_index.json (placeholder for offline docs index)
├── .vscode/
│   ├── tasks.json          # Predefined VS Code tasks for easy execution
│   └── extensions.json     # Recommended extensions for VS Code
├── .github/workflows/
│   └── ci.yml              # GitHub Actions workflow for CI
├── tests/
│   ├── __init__.py
│   └── test_basic.py       # Minimal unit test for CI
├── CHANGELOG.md            # Version history
├── VERSION                 # Current version number
├── requirements.txt        # Python dependencies for development/CI
├── LICENSE                 # MIT license
├── .gitignore
└── README.md               # This file
```

## Quick Start

1. **Install dependencies**: install Python ≥3.8 and then run
   `pip install -r requirements.txt` to install development tools (only
   `pytest` is required for the provided tests).

2. **Inspect your environment**:

   ```bash
   python scripts/inspect_env.py
   ```
   This prints a JSON list of installed packages and versions.

3. **Look up documentation**:

   ```bash
   python scripts/doc_lookup.py pandas.DataFrame.merge
   ```
   Replace the argument with any fully‑qualified Python object name to
   see its docstring.

4. **Analyze existing source**:

   ```bash
   python scripts/code_analyzer.py path/to/your_module.py
   ```
   This prints the abstract syntax tree of the given file, which can
   help when refactoring or generating compatible code.

5. **Run the tests**:

   ```bash
   pytest -q
   ```
   A comprehensive test suite with 48 tests validates all scripts and
   caching functionality.

6. **Run a health check**:

   ```bash
   python scripts/health_check.py
   ```
   This verifies that all scripts are working correctly and the skill
   is healthy.

7. **Debug usage** (optional):

   ```bash
   python scripts/debug_wrapper.py doc_lookup json.dumps
   python scripts/debug_wrapper.py inspect_env --find-import PIL
   python scripts/debug_wrapper.py code_analyzer path/to/file.py
   ```
   The debug wrapper logs all skill invocations to
   `references/skill_usage.log` for troubleshooting.

## Continuous Integration

The repository includes a GitHub Actions workflow (`.github/workflows/ci.yml`)
that runs on every push and pull request.  It sets up Python, installs
dependencies from `requirements.txt` and runs the test suite via
`pytest`.  You can customise this workflow to add linting, type
checking or additional test commands as your project evolves.

## Versioning

The current version of the skill is stored in the `VERSION` file.  See
`CHANGELOG.md` for a history of changes.  Update the version number and
changelog whenever you make a backwards‑incompatible change or add new
features.  Because this repository is intended to be used as a
stand‑alone skill package, semantic versioning is recommended.

## License

This project is licensed under the MIT License.  See the `LICENSE`
file for full text.