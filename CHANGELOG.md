# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [5.0.0] - 2026-03-17

### Added

* **Ripgrep text search engine** (`scripts/ripgrep_engine.py`):
  - `search_text` — Fast regex search across all file types using ripgrep subprocess
  - `find_config_references` — Trace config keys across .py, .yaml, .toml, .env, Dockerfile with categorized results
  - Graceful degradation when ripgrep is not installed
  - CLI with `search`, `config-refs`, and `status` subcommands

* **AST-grep structural search engine** (`scripts/ast_grep_engine.py`):
  - `search_code_pattern` — Structural AST pattern matching with metavariable syntax ($NAME, $$$ARGS)
  - `check_anti_patterns` — YAML-defined lint rules for detecting code smells (bare except, broad catches, print statements, star imports)
  - `transform_code` — Pattern-based code rewriting with dry-run support and diff preview
  - Graceful degradation when ast-grep-py is not installed
  - CLI with `search`, `anti-patterns`, `transform`, and `status` subcommands

* **Default anti-pattern rules** (`scripts/default_rules.yml`):
  - 5 built-in rules: `bare-except`, `assert-without-message`, `broad-exception-catch`, `print-statement`, `star-import`

* **5 new MCP tools** in `mcp_server.py`:
  - `search_text` — Ripgrep-powered regex search across all file types
  - `find_config_references` — Config key tracing across Python, YAML, TOML, ENV, Docker
  - `search_code_pattern` — AST structural pattern matching
  - `check_anti_patterns` — Structural anti-pattern detection
  - `transform_code` — AST-based code transformation with dry-run

* Added `ast-grep-py` to `[project.optional-dependencies.enhanced]`
* Added `tests/test_ripgrep_engine.py` — Tests for ripgrep engine functions
* Added `tests/test_ast_grep_engine.py` — Tests for ast-grep engine functions
* Added test classes for 5 new MCP tools in `tests/test_mcp_server.py`

### Changed

* Version bumped from 4.0.0 to 5.0.0
* Total MCP tools: 9 → 14

## [4.0.0] - 2026-03-16

### Changed

* **Architecture: Agent Skill → MCP Server** — The application is now a Model Context Protocol (MCP) server using the FastMCP framework. AI agents with MCP support (Claude Code, Cursor, etc.) can discover and use tools natively without shell execution.
* **Repository renamed** from `python-code-assistant-skill` to `pycode-mcp-server`.
* **`pyproject.toml`** — Renamed package, added `mcp[cli]` dependency, added `pycode-mcp-server` console entry point, bumped minimum Python to 3.10.
* **`SKILL.md`** — Rewritten as a general-purpose skill definition for non-coding AI agents, with both MCP and CLI fallback instructions.
* **`README.md`** — Completely rewritten for MCP server installation, agent configuration, and tool reference.

### Added

* **`mcp_server.py`** — FastMCP server entrypoint exposing 8 tools:
  - `get_local_docs` — Documentation lookup (signatures, params, examples)
  - `inspect_environment` — Python runtime & package listing
  - `get_package_details` — Detailed package info
  - `find_package_for_import` — Reverse import-to-package lookup
  - `analyze_file` — Single-file code structure analysis
  - `analyze_project` — Project-wide analysis with import graphs
  - `get_diagnostics` — Jedi/Pyflakes/mypy diagnostics
  - `get_install_instructions` — Package manager detection & install commands
* **`scripts/__init__.py`** — Proper package init replacing `sys.path` hacks.
* **`tests/test_mcp_server.py`** — Integration tests for all 8 MCP tools.

### Removed

* **`scripts/debug_wrapper.py`** — Replaced by MCP tool dispatch.
* **`scripts/health_check.py`** — Replaced by MCP server startup and `inspect_environment` tool.
* **`references/local_docs_index.json`** — Stale snapshot; MCP queries live data.
* **`TestHealthCheck` and `TestDebugWrapper`** test classes removed from `test_basic.py`.


## [3.1.0] - 2026-03-14

### Added

* **New `scripts/benchmark.py`** — Performance benchmark runner:
  - 5 benchmark suites: doc lookup, code analysis, project analysis,
    environment inspection, diagnostics
  - Measures execution time (via `timeit`), memory usage (via `tracemalloc`),
    and cache speedup ratios
  - CLI with `--suite`, `--iterations`, `--format` (markdown/json/table),
    and `--output` options

* **New `scripts/token_estimator.py`** — Token cost comparison tool:
  - Estimates LLM tokens for structured skill output vs raw approaches
    (pydoc, help(), ast.dump, pip list)
  - 5 comparison scenarios: doc lookup, class lookup, code analysis,
    project analysis, environment inspection
  - Configurable model pricing (GPT-4o, Claude 3.5, Gemini, etc.)
  - Optional `tiktoken` support for exact token counts
  - CLI with `--compare`, `--estimate`, `--model`, `--format` options

* **New `scripts/agent_eval.py`** — Agent evaluation harness:
  - Benchmarks coding agents (Claude Code, Antigravity, OpenCode) on
    standardized tasks with and without the skill installed
  - Parses Claude Code JSONL session logs for token/tool/turn counts
  - Parses Antigravity brain logs for conversation metrics
  - Comparison engine with per-task and aggregate reporting
  - CLI subcommands: `list-tasks`, `record`, `parse-logs`, `compare`, `report`

* **New `tests/eval_tasks/`** — 10 standardized evaluation tasks:
  - Tasks 01–03: Documentation lookup (Easy–Medium)
  - Tasks 04–05: Codebase understanding (Easy–Hard)
  - Tasks 06–08: Code generation (Easy–Hard)
  - Tasks 09–10: Cross-module integration (Medium–Hard)
  - Each task has exact prompts and automated pytest verification tests
  - Step-by-step evaluation guide in `README.md`

* **New `tests/test_benchmarks.py`** — 25+ benchmark assertions:
  - Performance guard rails with CI thresholds
  - Token savings verification (>30% doc lookup, >50% project analysis)
  - Information density comparison tests
  - Unit tests for benchmark and token_estimator modules

* Added `tiktoken` to `[project.optional-dependencies.benchmark]`
* Added benchmark and eval output paths to `.gitignore`
* Added non-blocking benchmark smoke tests to CI pipeline

## [3.0.0] - 2026-03-14

### ⚠️ Breaking Changes

* **Minimum Python version bumped from 3.8 to 3.9.** Removed all Python 3.8
  compatibility workarounds (`ast.unparse` fallback, `ast.Num`/`ast.Str`/
  `ast.NameConstant`/`ast.Index` handling).
* `jedi>=0.19.0` is now a **required dependency** (was not previously used).
  Jedi is the primary engine for documentation lookup, replacing the simpler
  `inspect`/`pydoc` approach which is now a fallback.
* Cache version bumped from `2` to `3`. Existing cache files will be migrated
  automatically.
* Removed `_evict_lru()` alias from `cache.py` (the actual algorithm was always
  LFU, the alias name was misleading).

### Added

* **New `scripts/jedi_engine.py`** — Jedi-powered code intelligence engine:
  - Autocompletions (`completions`)
  - Go-to-definition and type inference (`definitions`, `infer`)
  - Find all references (`references`)
  - Go-to without following imports (`goto`)
  - Hover information (`hover`)
  - Function signature help (`signatures`)
  - Semantic search across projects (`search`)
  - Safe symbol renaming (`rename`)
  - Variable extraction (`extract_variable`)
  - Function extraction (`extract_function`)
  - Variable inlining (`inline`)
  - Syntax error diagnostics (`diagnostics`)
  - Status check (`status`)

* **New `scripts/project_analyzer.py`** — Project-level analysis:
  - Recursive Python file discovery with exclusion patterns
  - Import dependency graph construction
  - Circular dependency detection
  - Dependency classification (stdlib vs third-party)
  - Cross-reference index (via Jedi, optional)
  - Project summary statistics

* **New `scripts/diagnostics.py`** — Unified diagnostics engine:
  - Jedi syntax error detection
  - Pyflakes integration (undefined names, unused imports)
  - mypy/pyright subprocess integration (optional type checking)
  - Project-wide diagnostic summaries

* **Dynamic stdlib detection** in `code_analyzer.py`: now uses
  `sys.stdlib_module_names` (Python 3.10+) with a comprehensive ~200-module
  fallback for Python 3.9. Previous version had only ~38 hardcoded modules,
  causing many stdlib modules (e.g., `textwrap`, `struct`, `decimal`,
  `traceback`, `warnings`, `signal`) to be falsely reported as third-party.

* **Cache TTL**: Documentation cache entries now expire after 7 days
  (configurable via `DEFAULT_TTL_HOURS`).

* `health_check.py` expanded to verify all new scripts (Jedi engine,
  project analyzer, diagnostics).

* `debug_wrapper.py` updated to support all new scripts.

* Added `ruff` for linting and formatting in CI.

* Added tests: `test_jedi_engine.py`, `test_project_analyzer.py`,
  `test_diagnostics.py`, plus new test classes in `test_basic.py`
  (`TestHealthCheck`, `TestDebugWrapper`, `TestStdlibDetection`,
  `TestExtractRaises`).

### Fixed

* **CRITICAL**: Fixed `code_analyzer.py` using `X | Y` type union syntax
  (`ast.FunctionDef | ast.AsyncFunctionDef`) which causes `SyntaxError`
  on Python 3.8 and 3.9 despite claiming 3.8+ support. Now uses `Union[]`.

* **CRITICAL**: Fixed fragile `from cache import CacheManager` imports in
  `doc_lookup.py` and `inspect_env.py` that only worked when CWD was
  `scripts/`. All scripts now add their directory to `sys.path` automatically.

* Fixed `inspect_env.py` calling `distributions()` up to 6 times per
  invocation. Results are now cached in a module-level variable.

* Fixed `get_import_names()` in `inspect_env.py` only catching
  `FileNotFoundError` when `dist.read_text()` can also raise `TypeError`
  or `KeyError` depending on Python version.

* Fixed `extract_raises()` in `doc_lookup.py` — now correctly parses
  Google-style, NumPy-style, and Sphinx-style docstrings using regex.

* Removed duplicated directory tree in `README.md`.

* Fixed CHANGELOG v1.1.0 referring to "LRU eviction" when the actual
  algorithm is LFU (Least Frequently Used).

### Changed

* `doc_lookup.py` restructured to use Jedi as primary engine with
  `inspect`/`pydoc` as fallback.
* CI matrix updated: removed Python 3.8, added Python 3.13, added ruff
  lint/format checks and health check step.
* Comprehensive documentation rewrite: README.md, SKILL.md, CHANGELOG.md.

## [2.0.0] - 2025-02-01

### ⚠️ Breaking Changes

* `doc_lookup.py` now returns structured JSON by default instead of raw pydoc
  text. Use `--raw` flag to get the legacy pydoc output.
* `code_analyzer.py` now returns structured JSON by default instead of raw AST
  dump. Use `--raw` flag to get the legacy AST output.
* `inspect_env.py` now returns comprehensive environment info by default. Use
  `--simple` flag for legacy `[(name, version), ...]` format.

### Added

* **Structured documentation output** in `doc_lookup.py`:
  - Function signatures with full type information
  - Structured parameter lists with types, defaults, and requirements
  - Return type information
  - Import statements (how to import the object)
  - Code examples extracted from docstrings via doctest parser
  - Exception information (what can be raised)
  - Related functions discovery
  - Source file locations
  - Class methods and attributes for class objects

* **Package name to import name mapping** in `inspect_env.py`:
  - Maps packages like `Pillow` → `PIL`, `PyYAML` → `yaml`
  - New `--find-import` flag to find which package provides an import
  - Package dependencies list
  - Main exports (classes/functions)
  - Installation locations
  - Virtual environment detection

* **Structured code analysis** in `code_analyzer.py`:
  - Functions with signatures, parameters, decorators, descriptions
  - Classes with methods, attributes, base classes
  - Import dependency analysis (stdlib vs third-party)
  - Decorator usage tracking
  - Summary statistics

* Expanded test suite from 30 to 48 tests covering all new functionality.

### Fixed

* **CRITICAL**: Fixed `doc_lookup.py` to work with ALL packages, not just
  builtins. The previous version used `eval()` which failed for any module
  that wasn't imported. Now uses `importlib` for proper module resolution.
  - Before: `json.dumps` → "name 'json' is not defined" ❌
  - After: `json.dumps` → Full structured documentation ✅

### Changed

* Completely rewrote `doc_lookup.py` with proper import resolution.
* Completely rewrote `code_analyzer.py` with structured output.
* Enhanced `inspect_env.py` with comprehensive package metadata.
* Updated SKILL.md with full documentation of all features and output formats.

## [1.1.1] - 2025-02-01

### Fixed

* Fixed critical bug in `cache.py` where eviction count was always 0 when
  packages changed. The code was clearing docstrings before counting them.
* Fixed `hit_count` for new cache entries starting at 1 instead of 0, which
  caused incorrect LFU eviction ordering.
* Removed unnecessary disk write on every cache hit in `doc_lookup.py`. Cache
  is now only saved when new entries are added, improving performance.

### Added

* Added 9 new tests covering LFU eviction, package change eviction counting,
  corrupted JSON recovery, version migration, and cache hit paths. Test count
  increased from 21 to 30.
* Enhanced SKILL.md with comprehensive CLI flag documentation for all scripts
  and cache location details.

## [1.1.0] - 2025-02-01

### Added

* New `scripts/cache.py` module providing JSON-based caching for docstring
  lookups and package tracking. Features include:
  - Automatic cache invalidation when packages are updated
  - LFU eviction when cache reaches maximum size (500 entries)
  - CLI interface with `--stats` and `--clear` options
  - Hit/miss statistics tracking
* `pyproject.toml` for modern Python packaging (PEP 517/518 compliant).
  The skill can now be installed with `pip install .`
* Comprehensive test suite with 21 tests covering all scripts and cache
  functionality.
* GitHub Actions CI now tests against Python 3.8, 3.9, 3.10, 3.11, and 3.12.

### Changed

* Migrated `scripts/inspect_env.py` from deprecated `pkg_resources` to
  `importlib.metadata` (Python 3.8+ stdlib). This eliminates deprecation
  warnings and ensures forward compatibility.
* Enhanced `scripts/doc_lookup.py` with caching support. Results are now
  cached to `references/local_docs_index.json` for faster subsequent lookups.
  Use `--no-cache` to bypass caching.
* `scripts/inspect_env.py` now updates the package cache by default. Use
  `--no-cache` to skip cache updates.
* Updated author metadata to "spkc83 & Opencode".

### Fixed

* Fixed future date in v1.0.0 changelog entry (was 2026-01-20).

## [1.0.0] - 2025-01-01

### Added

* Initial release of the **Python Code Assistant** skill, including
  `SKILL.md` definition, helper scripts for environment inspection
  (`inspect_env.py`), local documentation lookup (`doc_lookup.py`) and
  AST analysis (`code_analyzer.py`).
* Basic VS Code tasks configuration and recommended extensions.
* Example test suite and GitHub Actions workflow for continuous
  integration.
* MIT license and project metadata.
