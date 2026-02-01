# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

* New `scripts/health_check.py` script for quick verification of skill functionality.
  Checks all core scripts (`doc_lookup.py`, `inspect_env.py`, `code_analyzer.py`,
  `cache.py`) and reports their status.
* New `scripts/debug_wrapper.py` for logging skill invocations. Writes usage logs
  to `references/skill_usage.log` for troubleshooting and debugging.
* Updated documentation in README.md and SKILL.md to reflect new scripts and
  accurate project structure.

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
  - LRU eviction when cache reaches maximum size (500 entries)
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
