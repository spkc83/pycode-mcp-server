"""Performance benchmark runner for the PyCode MCP Server.

Measures execution time, memory usage, and throughput across all MCP tool
backend modules with comparisons between approaches (Jedi vs fallback,
cached vs uncached, structured vs raw).

Usage:
    python benchmark.py                          # Run all suites
    python benchmark.py --suite doc_lookup       # Run one suite
    python benchmark.py --format json            # JSON output
    python benchmark.py --iterations 50          # Custom iterations
    python benchmark.py --output results.json    # Save to file
"""

from __future__ import annotations

import ast
import gc
import json
import statistics
import subprocess
import sys
import tempfile
import time
import tracemalloc
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

_SCRIPTS_DIR = Path(__file__).resolve().parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))


# ---------------------------------------------------------------------------
# Benchmark result
# ---------------------------------------------------------------------------


@dataclass
class BenchmarkResult:
    """Result of a single benchmark."""

    name: str
    iterations: int
    mean_ms: float
    median_ms: float
    min_ms: float
    max_ms: float
    std_dev_ms: float
    memory_peak_kb: float


@dataclass
class SuiteResult:
    """Result of a benchmark suite."""

    suite_name: str
    benchmarks: List[BenchmarkResult]
    comparisons: List[Dict[str, Any]] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Core benchmark runner
# ---------------------------------------------------------------------------


def run_benchmark(
    name: str,
    func: Callable,
    args: tuple = (),
    kwargs: Optional[dict] = None,
    iterations: int = 20,
    warmup: int = 3,
) -> BenchmarkResult:
    """Run a benchmark with warmup, timing, and memory measurement."""
    kwargs = kwargs or {}

    # Warmup
    for _ in range(warmup):
        func(*args, **kwargs)

    # Collect timings
    timings: List[float] = []
    gc.disable()
    try:
        tracemalloc.start()
        for _ in range(iterations):
            start = time.perf_counter()
            func(*args, **kwargs)
            elapsed = (time.perf_counter() - start) * 1000  # ms
            timings.append(elapsed)
        _, peak_bytes = tracemalloc.get_traced_memory()
        tracemalloc.stop()
    finally:
        gc.enable()

    return BenchmarkResult(
        name=name,
        iterations=iterations,
        mean_ms=round(statistics.mean(timings), 3),
        median_ms=round(statistics.median(timings), 3),
        min_ms=round(min(timings), 3),
        max_ms=round(max(timings), 3),
        std_dev_ms=round(statistics.stdev(timings), 3) if len(timings) > 1 else 0.0,
        memory_peak_kb=round(peak_bytes / 1024, 1),
    )


# ---------------------------------------------------------------------------
# Synthetic test data generators
# ---------------------------------------------------------------------------


def _generate_source(lines: int) -> str:
    """Generate a synthetic Python source file of approximately *lines* lines."""
    parts = [
        '"""Synthetic module for benchmarking."""\n',
        "import os\nimport json\nimport sys\nfrom pathlib import Path\n",
        "from typing import Any, Dict, List, Optional\n\n",
    ]
    func_count = max(1, lines // 10)
    for i in range(func_count):
        parts.append(
            f"def function_{i}(arg1: str, arg2: int = 0) -> Dict[str, Any]:\n"
            f'    """Function {i} docstring."""\n'
            f"    result = {{'name': arg1, 'value': arg2 + {i}}}\n"
            f"    return result\n\n"
        )
    # Pad with comments if needed
    current = sum(p.count("\n") for p in parts)
    while current < lines:
        parts.append(f"# padding line {current}\n")
        current += 1
    return "".join(parts)


def _generate_project(num_files: int, lines_per_file: int = 50) -> Path:
    """Generate a synthetic project in a temp directory."""
    tmpdir = Path(tempfile.mkdtemp(prefix="bench_project_"))
    for i in range(num_files):
        source = _generate_source(lines_per_file)
        if i > 0:
            # Add imports between files
            source = f"from file_0 import function_0\n{source}"
        (tmpdir / f"file_{i}.py").write_text(source, encoding="utf-8")
    return tmpdir


# ---------------------------------------------------------------------------
# Suite 1: Doc Lookup
# ---------------------------------------------------------------------------


def _suite_doc_lookup(iterations: int) -> SuiteResult:
    """Benchmark doc lookup approaches."""
    import pydoc
    from io import StringIO

    results: List[BenchmarkResult] = []
    test_names = ["json.dumps", "os.path.join", "str.split"]

    # --- Jedi structured lookup ---
    try:
        from doc_lookup import get_local_docs

        def jedi_lookup():
            get_local_docs("json.dumps", use_cache=False, structured=True)

        results.append(run_benchmark("Jedi structured (json.dumps)", jedi_lookup, iterations=iterations))
    except Exception as e:
        results.append(BenchmarkResult(f"Jedi structured (FAILED: {e})", 0, 0, 0, 0, 0, 0, 0))

    # --- Inspect/pydoc fallback ---
    try:
        from doc_lookup import _get_inspect_structured_docs

        def inspect_lookup():
            _get_inspect_structured_docs("json.dumps")

        results.append(run_benchmark("Inspect fallback (json.dumps)", inspect_lookup, iterations=iterations))
    except Exception as e:
        results.append(BenchmarkResult(f"Inspect fallback (FAILED: {e})", 0, 0, 0, 0, 0, 0, 0))

    # --- Raw pydoc (no skill) ---
    def raw_pydoc():
        buf = StringIO()
        try:
            obj = eval("json.dumps", {"json": __import__("json")})  # noqa: S307
            pydoc.doc(obj, output=buf)
        except Exception:
            pass

    results.append(run_benchmark("Raw pydoc (no skill)", raw_pydoc, iterations=iterations))

    # --- Cached lookup ---
    try:
        from doc_lookup import get_local_docs

        # Prime the cache
        get_local_docs("json.dumps", use_cache=True, structured=True)

        def cached_lookup():
            get_local_docs("json.dumps", use_cache=True, structured=True)

        results.append(run_benchmark("Cache hit (json.dumps)", cached_lookup, iterations=iterations))
    except Exception as e:
        results.append(BenchmarkResult(f"Cache hit (FAILED: {e})", 0, 0, 0, 0, 0, 0, 0))

    # Comparisons
    comparisons = []
    cache_result = next((r for r in results if "Cache hit" in r.name), None)
    jedi_result = next((r for r in results if "Jedi structured" in r.name), None)
    raw_result = next((r for r in results if "Raw pydoc" in r.name), None)

    if cache_result and jedi_result and cache_result.median_ms > 0:
        speedup = jedi_result.median_ms / cache_result.median_ms
        comparisons.append({
            "comparison": "Cache vs Jedi",
            "speedup": f"{speedup:.1f}x faster",
        })
    if cache_result and raw_result and cache_result.median_ms > 0:
        speedup = raw_result.median_ms / cache_result.median_ms
        comparisons.append({
            "comparison": "Cache vs Raw pydoc",
            "speedup": f"{speedup:.1f}x faster",
        })

    return SuiteResult("Doc Lookup", results, comparisons)


# ---------------------------------------------------------------------------
# Suite 2: Code Analysis
# ---------------------------------------------------------------------------


def _suite_code_analysis(iterations: int) -> SuiteResult:
    """Benchmark code analysis approaches."""
    results: List[BenchmarkResult] = []

    small_src = _generate_source(50)
    medium_src = _generate_source(200)
    large_src = _generate_source(500)

    # --- Structured analysis ---
    try:
        from code_analyzer import analyze_source

        results.append(run_benchmark(
            "analyze_source (50 lines)", analyze_source, args=(small_src,), iterations=iterations
        ))
        results.append(run_benchmark(
            "analyze_source (200 lines)", analyze_source, args=(medium_src,), iterations=iterations
        ))
        results.append(run_benchmark(
            "analyze_source (500 lines)", analyze_source, args=(large_src,), iterations=iterations
        ))
    except Exception as e:
        results.append(BenchmarkResult(f"analyze_source (FAILED: {e})", 0, 0, 0, 0, 0, 0, 0))

    # --- Raw ast.dump (no skill) ---
    def raw_ast_small():
        ast.dump(ast.parse(small_src), indent=2)

    def raw_ast_medium():
        ast.dump(ast.parse(medium_src), indent=2)

    results.append(run_benchmark("ast.dump (50 lines)", raw_ast_small, iterations=iterations))
    results.append(run_benchmark("ast.dump (200 lines)", raw_ast_medium, iterations=iterations))

    # --- Jedi completions ---
    try:
        from jedi_engine import get_completions

        def jedi_comp():
            get_completions(source=small_src, line=5, col=0)

        results.append(run_benchmark("Jedi completions (50 lines)", jedi_comp, iterations=iterations))
    except Exception as e:
        results.append(BenchmarkResult(f"Jedi completions (FAILED: {e})", 0, 0, 0, 0, 0, 0, 0))

    return SuiteResult("Code Analysis", results)


# ---------------------------------------------------------------------------
# Suite 3: Project Analysis
# ---------------------------------------------------------------------------


def _suite_project_analysis(iterations: int) -> SuiteResult:
    """Benchmark project analysis."""
    results: List[BenchmarkResult] = []

    try:
        from project_analyzer import (
            analyze_project,
            build_import_graph,
            detect_circular_dependencies,
            discover_python_files,
        )

        # --- File discovery ---
        results.append(run_benchmark(
            "discover_files (scripts/)",
            discover_python_files,
            args=(Path(_SCRIPTS_DIR),),
            iterations=iterations,
        ))

        # --- Import graph ---
        files = discover_python_files(Path(_SCRIPTS_DIR))
        results.append(run_benchmark(
            "build_import_graph (scripts/)",
            build_import_graph,
            args=(Path(_SCRIPTS_DIR), files),
            iterations=iterations,
        ))

        # --- Cycle detection ---
        graph = build_import_graph(Path(_SCRIPTS_DIR), files)
        results.append(run_benchmark(
            "detect_cycles (scripts/)",
            detect_circular_dependencies,
            args=(graph,),
            iterations=iterations,
        ))

        # --- Full analysis ---
        def full_analysis():
            analyze_project(str(_SCRIPTS_DIR), include_cross_refs=False)

        results.append(run_benchmark(
            "full analysis (scripts/)", full_analysis, iterations=max(5, iterations // 4)
        ))

        # --- Synthetic project (50 files) ---
        syn_project = _generate_project(50)
        try:
            def syn_analysis():
                analyze_project(str(syn_project), include_cross_refs=False)

            results.append(run_benchmark(
                "full analysis (50 synthetic files)", syn_analysis, iterations=max(3, iterations // 5)
            ))
        finally:
            import shutil
            shutil.rmtree(syn_project, ignore_errors=True)

    except Exception as e:
        results.append(BenchmarkResult(f"Project analysis (FAILED: {e})", 0, 0, 0, 0, 0, 0, 0))

    return SuiteResult("Project Analysis", results)


# ---------------------------------------------------------------------------
# Suite 4: Environment Inspection
# ---------------------------------------------------------------------------


def _suite_environment(iterations: int) -> SuiteResult:
    """Benchmark environment inspection."""
    results: List[BenchmarkResult] = []

    try:
        from inspect_env import get_environment_info

        results.append(run_benchmark(
            "get_environment_info()", get_environment_info, iterations=max(3, iterations // 5)
        ))
    except Exception as e:
        results.append(BenchmarkResult(f"get_environment_info (FAILED: {e})", 0, 0, 0, 0, 0, 0, 0))

    # Raw pip list (no skill)
    def raw_pip():
        subprocess.run(
            [sys.executable, "-m", "pip", "list", "--format=json"],
            capture_output=True, text=True, timeout=30,
        )

    results.append(run_benchmark(
        "pip list --format=json (no skill)", raw_pip, iterations=max(3, iterations // 5)
    ))

    return SuiteResult("Environment Inspection", results)


# ---------------------------------------------------------------------------
# Suite 5: Diagnostics
# ---------------------------------------------------------------------------


def _suite_diagnostics(iterations: int) -> SuiteResult:
    """Benchmark diagnostics."""
    results: List[BenchmarkResult] = []
    source = _generate_source(100)

    try:
        from diagnostics import get_jedi_diagnostics, get_pyflakes_diagnostics

        results.append(run_benchmark(
            "Jedi diagnostics (100 lines)",
            get_jedi_diagnostics,
            args=(source,),
            iterations=iterations,
        ))

        results.append(run_benchmark(
            "Pyflakes diagnostics (100 lines)",
            get_pyflakes_diagnostics,
            args=(source, "bench.py"),
            iterations=iterations,
        ))
    except Exception as e:
        results.append(BenchmarkResult(f"Diagnostics (FAILED: {e})", 0, 0, 0, 0, 0, 0, 0))

    return SuiteResult("Diagnostics", results)


# ---------------------------------------------------------------------------
# Report formatters
# ---------------------------------------------------------------------------

SUITE_RUNNERS = {
    "doc_lookup": _suite_doc_lookup,
    "code_analysis": _suite_code_analysis,
    "project_analysis": _suite_project_analysis,
    "environment": _suite_environment,
    "diagnostics": _suite_diagnostics,
}


def format_markdown(suites: List[SuiteResult]) -> str:
    """Format results as markdown."""
    lines = ["# Performance Benchmark Report\n"]
    for suite in suites:
        lines.append(f"\n## {suite.suite_name}\n")
        lines.append("| Benchmark | Mean (ms) | Median (ms) | Min (ms) | Std Dev | Memory (KB) |")
        lines.append("|-----------|-----------|-------------|----------|---------|-------------|")
        for b in suite.benchmarks:
            lines.append(
                f"| {b.name} | {b.mean_ms:.1f} | {b.median_ms:.1f} | "
                f"{b.min_ms:.1f} | {b.std_dev_ms:.1f} | {b.memory_peak_kb:.0f} |"
            )
        if suite.comparisons:
            lines.append("")
            for c in suite.comparisons:
                lines.append(f"→ **{c['comparison']}**: {c['speedup']}")
    return "\n".join(lines)


def format_json(suites: List[SuiteResult]) -> str:
    """Format results as JSON."""
    data = []
    for suite in suites:
        data.append({
            "suite": suite.suite_name,
            "benchmarks": [asdict(b) for b in suite.benchmarks],
            "comparisons": suite.comparisons,
        })
    return json.dumps(data, indent=2)


def format_table(suites: List[SuiteResult]) -> str:
    """Compact table format."""
    lines = []
    for suite in suites:
        lines.append(f"\n{'='*60}")
        lines.append(f"  {suite.suite_name}")
        lines.append(f"{'='*60}")
        for b in suite.benchmarks:
            lines.append(f"  {b.name:<40} {b.median_ms:>8.1f} ms  ({b.memory_peak_kb:.0f} KB)")
        for c in suite.comparisons:
            lines.append(f"  → {c['comparison']}: {c['speedup']}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Performance benchmark runner")
    parser.add_argument(
        "--suite",
        choices=list(SUITE_RUNNERS.keys()),
        help="Run a specific suite only",
    )
    parser.add_argument("--iterations", type=int, default=20, help="Iterations per benchmark (default: 20)")
    parser.add_argument(
        "--format",
        choices=["markdown", "json", "table"],
        default="markdown",
        help="Output format (default: markdown)",
    )
    parser.add_argument("--output", type=str, help="Save report to file")

    args = parser.parse_args()

    # Run selected or all suites
    if args.suite:
        suites = [SUITE_RUNNERS[args.suite](args.iterations)]
    else:
        suites = [runner(args.iterations) for runner in SUITE_RUNNERS.values()]

    # Format
    if args.format == "json":
        report = format_json(suites)
    elif args.format == "table":
        report = format_table(suites)
    else:
        report = format_markdown(suites)

    if args.output:
        Path(args.output).write_text(report, encoding="utf-8")
        print(f"Report saved to {args.output}")
    else:
        print(report)


if __name__ == "__main__":
    main()
