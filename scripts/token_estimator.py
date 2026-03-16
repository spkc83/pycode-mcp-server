"""Token cost estimator for comparing skill output vs naive approaches.

Estimates LLM token counts for different output formats and computes
cost savings from using structured skill output vs raw pydoc/help/source.

Usage:
    python token_estimator.py                      # Run all comparisons
    python token_estimator.py --compare doc_lookup json.dumps
    python token_estimator.py --estimate "text"
    python token_estimator.py --estimate-file path.py
    python token_estimator.py --model claude-3.5-sonnet --format json
"""

from __future__ import annotations

import ast
import json
import pydoc
import subprocess
import sys
from dataclasses import asdict, dataclass, field
from io import StringIO
from pathlib import Path
from typing import Any, Dict, List, Optional

_SCRIPTS_DIR = Path(__file__).resolve().parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))


# ---------------------------------------------------------------------------
# Token estimation
# ---------------------------------------------------------------------------

# Try tiktoken for exact counts; fall back to approximation
try:
    import tiktoken

    _ENCODER = tiktoken.get_encoding("cl100k_base")
    TIKTOKEN_AVAILABLE = True
except Exception:
    _ENCODER = None
    TIKTOKEN_AVAILABLE = False


def estimate_tokens(text: str, method: str = "auto") -> int:
    """Estimate the number of LLM tokens in *text*.

    Methods:
        'auto'        – use tiktoken if available, else 'approximate'
        'approximate' – ~4 chars per token (fast, no deps)
        'word'        – ~0.75 words per token
        'tiktoken'    – exact count via cl100k_base (requires tiktoken)
    """
    if not text:
        return 0

    if method == "auto":
        method = "tiktoken" if TIKTOKEN_AVAILABLE else "approximate"

    if method == "tiktoken":
        if _ENCODER is None:
            raise RuntimeError("tiktoken is not installed")
        return len(_ENCODER.encode(text))

    if method == "word":
        words = len(text.split())
        return max(1, int(words / 0.75))

    # Default: approximate (~4 chars per token)
    return max(1, len(text) // 4)


# ---------------------------------------------------------------------------
# Cost estimation
# ---------------------------------------------------------------------------

# Pricing per 1 M tokens (USD).  Easy to update in one place.
MODEL_PRICING: Dict[str, Dict[str, float]] = {
    "gpt-4o": {"input": 2.50, "output": 10.00},
    "gpt-4o-mini": {"input": 0.15, "output": 0.60},
    "gpt-4.1": {"input": 2.00, "output": 8.00},
    "claude-3.5-sonnet": {"input": 3.00, "output": 15.00},
    "claude-3.7-sonnet": {"input": 3.00, "output": 15.00},
    "claude-4-sonnet": {"input": 3.00, "output": 15.00},
    "gemini-2.5-pro": {"input": 1.25, "output": 10.00},
    "gemini-2.5-flash": {"input": 0.15, "output": 0.60},
}

DEFAULT_MODEL = "claude-3.5-sonnet"


def estimate_cost_usd(
    tokens: int,
    model: str = DEFAULT_MODEL,
    direction: str = "input",
) -> float:
    """Estimate cost in USD for a token count."""
    pricing = MODEL_PRICING.get(model, MODEL_PRICING[DEFAULT_MODEL])
    rate = pricing.get(direction, pricing["input"])
    return tokens * rate / 1_000_000


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class TokenEstimate:
    """Token count + cost for one approach."""

    label: str
    text_length: int
    tokens: int
    cost_usd: float
    info_quality: int  # 1-5 stars
    method: str = ""


@dataclass
class TokenComparison:
    """Side-by-side comparison of with-skill vs without-skill."""

    scenario: str
    without_skill: List[TokenEstimate]
    with_skill: List[TokenEstimate]
    best_without_tokens: int = 0
    best_with_tokens: int = 0
    savings_pct: float = 0.0
    tokens_saved: int = 0
    cost_saved_per_1k: float = 0.0

    def compute(self, model: str = DEFAULT_MODEL) -> None:
        self.best_without_tokens = min(e.tokens for e in self.without_skill)
        self.best_with_tokens = min(e.tokens for e in self.with_skill)
        self.tokens_saved = self.best_without_tokens - self.best_with_tokens
        if self.best_without_tokens > 0:
            self.savings_pct = self.tokens_saved / self.best_without_tokens * 100
        self.cost_saved_per_1k = estimate_cost_usd(
            self.tokens_saved * 1000, model=model
        )


# ---------------------------------------------------------------------------
# Helpers: generate "without skill" outputs
# ---------------------------------------------------------------------------


def _raw_pydoc(name: str) -> str:
    """Render raw pydoc output for *name* (what an agent would run)."""
    old_stdout = sys.stdout
    sys.stdout = buf = StringIO()
    try:
        pydoc.doc(eval(name, {}), output=buf)  # noqa: S307
    except Exception:
        try:
            # Try importing the module first
            parts = name.rsplit(".", 1)
            if len(parts) == 2:
                mod = __import__(parts[0], fromlist=[parts[1]])
                obj = getattr(mod, parts[1])
                pydoc.doc(obj, output=buf)
            else:
                __import__(name)
                mod = sys.modules[name]
                pydoc.doc(mod, output=buf)
        except Exception:
            buf.write(f"Could not look up {name}")
    finally:
        sys.stdout = old_stdout
    return buf.getvalue()


def _raw_help(name: str) -> str:
    """Capture help() output (subprocess, like an agent would)."""
    try:
        result = subprocess.run(
            [sys.executable, "-c", f"help({name})"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        return result.stdout
    except Exception:
        return f"Could not run help({name})"


def _raw_ast_dump(source: str) -> str:
    """Raw ast.dump() of source (what an agent would get without the skill)."""
    try:
        tree = ast.parse(source)
        return ast.dump(tree, indent=2)
    except SyntaxError:
        return "SyntaxError"


def _raw_pip_list() -> str:
    """Raw `pip list --format=json` output."""
    try:
        result = subprocess.run(
            [sys.executable, "-m", "pip", "list", "--format=columns"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        return result.stdout
    except Exception:
        return "pip list failed"


# ---------------------------------------------------------------------------
# Helpers: generate "with skill" outputs
# ---------------------------------------------------------------------------


def _skill_doc_lookup(name: str) -> str:
    """Structured doc lookup via the skill."""
    try:
        from doc_lookup import get_local_docs

        result = get_local_docs(name, use_cache=False, structured=True)
        if isinstance(result, dict):
            return json.dumps(result, indent=2, default=str)
        return str(result)
    except Exception as e:
        return json.dumps({"error": str(e)})


def _skill_code_analysis(source: str) -> str:
    """Structured code analysis via the skill."""
    try:
        from code_analyzer import analyze_source

        result = analyze_source(source)
        return json.dumps(result, indent=2, default=str)
    except Exception as e:
        return json.dumps({"error": str(e)})


def _skill_project_analysis(root: str) -> str:
    """Project analysis via the skill."""
    try:
        from project_analyzer import analyze_project

        result = analyze_project(root, include_cross_refs=False)
        return json.dumps(result, indent=2, default=str)
    except Exception as e:
        return json.dumps({"error": str(e)})


def _skill_env_inspection() -> str:
    """Environment inspection via the skill."""
    try:
        from inspect_env import get_environment_info

        result = get_environment_info()
        return json.dumps(result, indent=2, default=str)
    except Exception as e:
        return json.dumps({"error": str(e)})


# ---------------------------------------------------------------------------
# Comparison scenarios
# ---------------------------------------------------------------------------


def _make_estimate(
    label: str, text: str, quality: int, model: str = DEFAULT_MODEL
) -> TokenEstimate:
    tokens = estimate_tokens(text)
    return TokenEstimate(
        label=label,
        text_length=len(text),
        tokens=tokens,
        cost_usd=estimate_cost_usd(tokens, model),
        info_quality=quality,
        method="tiktoken" if TIKTOKEN_AVAILABLE else "approximate",
    )


def compare_doc_lookup(
    name: str = "json.dumps", model: str = DEFAULT_MODEL
) -> TokenComparison:
    """Compare doc lookup approaches for a given object."""
    raw_pydoc = _raw_pydoc(name)
    raw_help = _raw_help(name)
    skill_out = _skill_doc_lookup(name)

    comp = TokenComparison(
        scenario=f"Doc Lookup: {name}",
        without_skill=[
            _make_estimate("pydoc.render_doc()", raw_pydoc, 2, model),
            _make_estimate("help() subprocess", raw_help, 2, model),
        ],
        with_skill=[
            _make_estimate("Skill: structured JSON", skill_out, 5, model),
        ],
    )
    comp.compute(model)
    return comp


def compare_code_analysis(
    filepath: Optional[str] = None, model: str = DEFAULT_MODEL
) -> TokenComparison:
    """Compare code analysis approaches."""
    if filepath:
        source = Path(filepath).read_text(encoding="utf-8")
        label = Path(filepath).name
    else:
        # Use a representative file from the skill itself
        source = (_SCRIPTS_DIR / "cache.py").read_text(encoding="utf-8")
        label = "cache.py"

    raw_source = source
    raw_ast = _raw_ast_dump(source)
    skill_out = _skill_code_analysis(source)

    comp = TokenComparison(
        scenario=f"Code Analysis: {label} ({source.count(chr(10))+1} lines)",
        without_skill=[
            _make_estimate("Read entire file", raw_source, 3, model),
            _make_estimate("ast.dump()", raw_ast, 1, model),
        ],
        with_skill=[
            _make_estimate("Skill: analyze_source()", skill_out, 5, model),
        ],
    )
    comp.compute(model)
    return comp


def compare_project_analysis(
    root: Optional[str] = None, model: str = DEFAULT_MODEL
) -> TokenComparison:
    """Compare project analysis approaches."""
    if root is None:
        root = str(_SCRIPTS_DIR)
    root_path = Path(root)

    # "Without skill": read all .py files
    all_source = []
    for f in sorted(root_path.rglob("*.py")):
        try:
            all_source.append(f.read_text(encoding="utf-8"))
        except Exception:
            pass
    combined_source = "\n".join(all_source)
    file_count = len(all_source)

    skill_out = _skill_project_analysis(root)

    comp = TokenComparison(
        scenario=f"Project Analysis: {root_path.name}/ ({file_count} files)",
        without_skill=[
            _make_estimate(
                f"Read all {file_count} files", combined_source, 2, model
            ),
        ],
        with_skill=[
            _make_estimate("Skill: analyze_project()", skill_out, 5, model),
        ],
    )
    comp.compute(model)
    return comp


def compare_env_inspection(model: str = DEFAULT_MODEL) -> TokenComparison:
    """Compare environment inspection approaches."""
    raw_pip = _raw_pip_list()
    skill_out = _skill_env_inspection()

    comp = TokenComparison(
        scenario="Environment Inspection",
        without_skill=[
            _make_estimate("pip list --format=columns", raw_pip, 2, model),
        ],
        with_skill=[
            _make_estimate("Skill: inspect_env.py", skill_out, 5, model),
        ],
    )
    comp.compute(model)
    return comp


def compare_class_lookup(
    name: str = "pathlib.Path", model: str = DEFAULT_MODEL
) -> TokenComparison:
    """Compare class documentation lookup."""
    raw_pydoc = _raw_pydoc(name)
    raw_help = _raw_help(name)
    skill_out = _skill_doc_lookup(name)

    comp = TokenComparison(
        scenario=f"Class Lookup: {name}",
        without_skill=[
            _make_estimate("pydoc.render_doc()", raw_pydoc, 1, model),
            _make_estimate("help() subprocess", raw_help, 1, model),
        ],
        with_skill=[
            _make_estimate("Skill: structured JSON", skill_out, 5, model),
        ],
    )
    comp.compute(model)
    return comp


# ---------------------------------------------------------------------------
# Run all comparisons
# ---------------------------------------------------------------------------


def run_all_comparisons(model: str = DEFAULT_MODEL) -> List[TokenComparison]:
    """Run all comparison scenarios."""
    return [
        compare_doc_lookup("json.dumps", model),
        compare_class_lookup("pathlib.Path", model),
        compare_code_analysis(None, model),
        compare_project_analysis(None, model),
        compare_env_inspection(model),
    ]


# ---------------------------------------------------------------------------
# Report generation
# ---------------------------------------------------------------------------


def _stars(n: int) -> str:
    return "★" * n + "☆" * (5 - n)


def format_markdown(comparisons: List[TokenComparison]) -> str:
    """Generate a markdown report."""
    lines = [
        "# Token Cost Analysis: Python Code Assistant Skill\n",
        f"_Estimation method: {'tiktoken (exact)' if TIKTOKEN_AVAILABLE else 'approximate (~4 chars/token)'}_\n",
    ]

    for comp in comparisons:
        lines.append(f"\n## {comp.scenario}\n")
        lines.append("| Approach | Tokens | Cost (USD) | Quality |")
        lines.append("|----------|--------|------------|---------|")
        for est in comp.without_skill:
            lines.append(
                f"| Without: {est.label} | {est.tokens:,} | "
                f"${est.cost_usd:.6f} | {_stars(est.info_quality)} |"
            )
        for est in comp.with_skill:
            lines.append(
                f"| **With: {est.label}** | **{est.tokens:,}** | "
                f"**${est.cost_usd:.6f}** | **{_stars(est.info_quality)}** |"
            )
        lines.append("")
        lines.append(f"→ **Token savings: {comp.savings_pct:.1f}%** ({comp.tokens_saved:,} tokens saved)")
        lines.append(f"→ Cost savings at 1,000 calls: ${comp.cost_saved_per_1k:.4f}")

    # Aggregate summary
    lines.append("\n## Aggregate Summary\n")
    lines.append("| Scenario | Tokens Saved | Savings % | $/1K ops |")
    lines.append("|----------|-------------|-----------|----------|")
    total_saved = 0
    total_without = 0
    for comp in comparisons:
        lines.append(
            f"| {comp.scenario.split(':')[0]} | {comp.tokens_saved:,} | "
            f"{comp.savings_pct:.1f}% | ${comp.cost_saved_per_1k:.4f} |"
        )
        total_saved += comp.tokens_saved
        total_without += comp.best_without_tokens

    if total_without > 0:
        overall_pct = total_saved / total_without * 100
    else:
        overall_pct = 0
    lines.append(
        f"| **TOTAL** | **{total_saved:,}** | "
        f"**{overall_pct:.1f}%** | — |"
    )

    return "\n".join(lines)


def format_json(comparisons: List[TokenComparison]) -> str:
    """Generate JSON report."""
    data = []
    for comp in comparisons:
        data.append({
            "scenario": comp.scenario,
            "without_skill": [asdict(e) for e in comp.without_skill],
            "with_skill": [asdict(e) for e in comp.with_skill],
            "savings_pct": round(comp.savings_pct, 1),
            "tokens_saved": comp.tokens_saved,
            "cost_saved_per_1k": round(comp.cost_saved_per_1k, 6),
        })
    return json.dumps(data, indent=2)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(
        description="Token cost estimator — compare skill output vs naive approaches"
    )
    parser.add_argument(
        "--compare",
        nargs=2,
        metavar=("TYPE", "ARG"),
        help="Compare a specific scenario (doc_lookup NAME | code_analysis FILE | project_analysis DIR)",
    )
    parser.add_argument("--estimate", type=str, help="Estimate tokens for text")
    parser.add_argument(
        "--estimate-file", type=str, help="Estimate tokens for a file"
    )
    parser.add_argument(
        "--model", type=str, default=DEFAULT_MODEL, help=f"LLM model for cost (default: {DEFAULT_MODEL})"
    )
    parser.add_argument(
        "--format",
        choices=["markdown", "json"],
        default="markdown",
        help="Output format (default: markdown)",
    )
    parser.add_argument("--output", type=str, help="Save report to file")

    args = parser.parse_args()

    # Simple token estimation
    if args.estimate:
        tokens = estimate_tokens(args.estimate)
        cost = estimate_cost_usd(tokens, args.model)
        print(json.dumps({"text_length": len(args.estimate), "tokens": tokens, "cost_usd": cost}))
        return

    if args.estimate_file:
        text = Path(args.estimate_file).read_text(encoding="utf-8")
        tokens = estimate_tokens(text)
        cost = estimate_cost_usd(tokens, args.model)
        print(json.dumps({"file": args.estimate_file, "text_length": len(text), "tokens": tokens, "cost_usd": cost}))
        return

    # Specific comparison
    if args.compare:
        ctype, carg = args.compare
        if ctype == "doc_lookup":
            comps = [compare_doc_lookup(carg, args.model)]
        elif ctype == "class_lookup":
            comps = [compare_class_lookup(carg, args.model)]
        elif ctype == "code_analysis":
            comps = [compare_code_analysis(carg, args.model)]
        elif ctype == "project_analysis":
            comps = [compare_project_analysis(carg, args.model)]
        else:
            print(f"Unknown comparison type: {ctype}", file=sys.stderr)
            sys.exit(1)
    else:
        comps = run_all_comparisons(args.model)

    # Format output
    if args.format == "json":
        report = format_json(comps)
    else:
        report = format_markdown(comps)

    if args.output:
        Path(args.output).write_text(report, encoding="utf-8")
        print(f"Report saved to {args.output}")
    else:
        print(report)


if __name__ == "__main__":
    main()
