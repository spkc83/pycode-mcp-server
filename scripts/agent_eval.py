"""Agent evaluation harness for benchmarking coding agents with/without MCP tools.

Parses conversation logs from Claude Code, Antigravity, and OpenCode to
extract metrics (tokens, tool calls, turns), then compares performance
on standardized tasks with and without the MCP server tools available.

Usage:
    python agent_eval.py list-tasks
    python agent_eval.py record --task task_01 --agent claude_code ...
    python agent_eval.py parse-logs --agent claude_code --session <path>
    python agent_eval.py compare --results-dir references/eval_results/
    python agent_eval.py report --results-dir references/eval_results/
"""

from __future__ import annotations

import json
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

_SCRIPTS_DIR = Path(__file__).resolve().parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from token_estimator import MODEL_PRICING, estimate_tokens

# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

SUPPORTED_AGENTS = ["claude_code", "antigravity", "opencode"]


@dataclass
class AgentRunMetrics:
    """Metrics from a single agent run on a single task."""

    task_id: str
    agent: str
    skill_enabled: bool

    # Accuracy
    tests_total: int = 0
    tests_passed: int = 0
    accuracy_pct: float = 0.0

    # Token efficiency
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0

    # Speed
    wall_clock_seconds: float = 0.0

    # Efficiency
    turn_count: int = 0
    tool_calls: int = 0
    retry_count: int = 0

    # Cost
    estimated_cost_usd: float = 0.0
    model: str = ""

    # Metadata
    session_id: str = ""
    timestamp: str = ""
    notes: str = ""


@dataclass
class TaskComparison:
    """Comparison of with-skill vs without-skill for one task."""

    task_id: str
    with_skill: AgentRunMetrics
    without_skill: AgentRunMetrics
    accuracy_improvement: float = 0.0
    token_savings_pct: float = 0.0
    speed_improvement_pct: float = 0.0
    tool_call_reduction: int = 0
    turn_reduction: int = 0


# ---------------------------------------------------------------------------
# Task registry
# ---------------------------------------------------------------------------

EVAL_TASKS = {
    "task_01_doc_lookup": {
        "name": "Documentation Lookup",
        "category": "Documentation",
        "difficulty": "Easy",
        "prompt": (
            'Write a function called `serialize_set` that uses `json.dumps` '
            'with the `default` parameter to serialize a Python set into a '
            'JSON array string. The function should have proper type hints '
            'and a docstring that includes the correct signature of `json.dumps`.'
        ),
        "expected_skill_usage": ["doc_lookup.py"],
        "tests_file": "tests/eval_tasks/task_01_doc_lookup.py",
    },
    "task_02_error_handling": {
        "name": "Error Handling",
        "category": "Documentation",
        "difficulty": "Medium",
        "prompt": (
            'Write a function called `safe_json_parse` that parses user JSON '
            'input and handles ALL exceptions that `json.loads` can raise. '
            'The function should return a tuple of (parsed_data, error_message). '
            'List each exception type in the docstring.'
        ),
        "expected_skill_usage": ["doc_lookup.py"],
        "tests_file": "tests/eval_tasks/task_02_error_handling.py",
    },
    "task_03_class_usage": {
        "name": "Class Usage",
        "category": "Documentation",
        "difficulty": "Medium",
        "prompt": (
            'Create a function called `find_python_files` that uses `pathlib.Path` '
            'to recursively find all `.py` files in a directory, get their sizes, '
            'and return a dict sorted by size (largest first). Use correct method names.'
        ),
        "expected_skill_usage": ["doc_lookup.py"],
        "tests_file": "tests/eval_tasks/task_03_class_usage.py",
    },
    "task_04_file_analysis": {
        "name": "File Analysis",
        "category": "Understanding",
        "difficulty": "Easy",
        "prompt": (
            'Read `scripts/cache.py` and answer: What type of eviction does it use? '
            'What is the max entry count? What is the default TTL? '
            'Save your answers as a JSON object with keys: eviction_type, max_entries, ttl_hours.'
        ),
        "expected_skill_usage": ["code_analyzer.py"],
        "tests_file": "tests/eval_tasks/task_04_file_analysis.py",
    },
    "task_05_project_deps": {
        "name": "Project Dependencies",
        "category": "Understanding",
        "difficulty": "Hard",
        "prompt": (
            'Analyze this project and answer: What are the third-party dependencies? '
            'Which scripts import from other scripts? Are there any circular dependencies? '
            'Save your answers as JSON with keys: third_party, import_graph, circular_deps.'
        ),
        "expected_skill_usage": ["project_analyzer.py"],
        "tests_file": "tests/eval_tasks/task_05_project_deps.py",
    },
    "task_06_refactor": {
        "name": "Refactor",
        "category": "Code Generation",
        "difficulty": "Medium",
        "prompt": (
            'Add a `get_or_set(self, name, factory_fn, package=None)` method to the '
            'CacheManager class in `scripts/cache.py`. It should return the cached '
            'value if present, otherwise call factory_fn(), cache the result, and return it.'
        ),
        "expected_skill_usage": ["code_analyzer.py", "jedi_engine.py"],
        "tests_file": "tests/eval_tasks/task_06_refactor.py",
    },
    "task_07_debug_fix": {
        "name": "Debug Fix",
        "category": "Code Generation",
        "difficulty": "Easy",
        "prompt": (
            'Find and fix any import ordering bugs in the scripts/ directory where '
            'a name is used before it is imported. Report which files had issues.'
        ),
        "expected_skill_usage": ["diagnostics.py", "code_analyzer.py"],
        "tests_file": "tests/eval_tasks/task_07_debug_fix.py",
    },
    "task_08_test_generation": {
        "name": "Test Generation",
        "category": "Code Generation",
        "difficulty": "Hard",
        "prompt": (
            'Write comprehensive tests for `detect_circular_dependencies()` in '
            '`scripts/project_analyzer.py`. Cover: no cycles, simple A→B→A cycle, '
            'self-cycle, diamond graph with cycle, and disconnected components.'
        ),
        "expected_skill_usage": ["code_analyzer.py", "doc_lookup.py"],
        "tests_file": "tests/eval_tasks/task_08_test_generation.py",
    },
    "task_09_api_integration": {
        "name": "API Integration",
        "category": "Cross-Module",
        "difficulty": "Hard",
        "prompt": (
            'Create `scripts/code_search.py` that combines `jedi_engine.search_project()` '
            'and `project_analyzer.analyze_project()` to search for a symbol across the '
            'project and show where it is defined, used, and what modules depend on it.'
        ),
        "expected_skill_usage": ["jedi_engine.py", "project_analyzer.py"],
        "tests_file": "tests/eval_tasks/task_09_api_integration.py",
    },
    "task_10_cross_module": {
        "name": "Cross-Module Enhancement",
        "category": "Cross-Module",
        "difficulty": "Medium",
        "prompt": (
            'Add a `--health-detail` flag to `scripts/health_check.py` that also runs '
            '`diagnostics.py` on each script in `scripts/` and includes diagnostic '
            'results in the health check output.'
        ),
        "expected_skill_usage": ["health_check.py", "diagnostics.py"],
        "tests_file": "tests/eval_tasks/task_10_cross_module.py",
    },
}


# ---------------------------------------------------------------------------
# Log parsers
# ---------------------------------------------------------------------------


def parse_claude_code_logs(session_path: str) -> AgentRunMetrics:
    """Parse Claude Code JSONL session logs.

    Claude Code stores sessions at:
        ~/.claude/projects/<project-hash>/<session-id>.jsonl

    Each line is a JSON object with various event types.
    """
    path = Path(session_path)
    if not path.exists():
        return AgentRunMetrics(
            task_id="unknown", agent="claude_code", skill_enabled=False,
            notes=f"File not found: {session_path}",
        )

    total_input = 0
    total_output = 0
    tool_calls = 0
    turns = 0
    first_ts = None
    last_ts = None

    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue

        event_type = event.get("type", "")

        # Track timestamps
        ts = event.get("timestamp") or event.get("ts")
        if ts:
            if first_ts is None:
                first_ts = ts
            last_ts = ts

        # Token counting from various event formats
        if "usage" in event:
            usage = event["usage"]
            total_input += usage.get("input_tokens", 0)
            total_output += usage.get("output_tokens", 0)

        if event_type in ("assistant", "turn.completed"):
            turns += 1
            total_input += event.get("input_tokens", 0)
            total_output += event.get("output_tokens", 0)

        if event_type == "tool_use" or event.get("role") == "tool":
            tool_calls += 1

        # Look through content blocks for tool_use
        for block in event.get("content", []):
            if isinstance(block, dict) and block.get("type") == "tool_use":
                tool_calls += 1

    # Estimate wall clock time
    wall_clock = 0.0
    if first_ts and last_ts:
        try:
            t1 = datetime.fromisoformat(str(first_ts).replace("Z", "+00:00"))
            t2 = datetime.fromisoformat(str(last_ts).replace("Z", "+00:00"))
            wall_clock = (t2 - t1).total_seconds()
        except (ValueError, TypeError):
            pass

    return AgentRunMetrics(
        task_id="unknown",
        agent="claude_code",
        skill_enabled=False,
        input_tokens=total_input,
        output_tokens=total_output,
        total_tokens=total_input + total_output,
        turn_count=turns,
        tool_calls=tool_calls,
        wall_clock_seconds=wall_clock,
        session_id=path.stem,
    )


def parse_antigravity_logs(conv_id: str) -> AgentRunMetrics:
    """Parse Antigravity conversation logs.

    Logs are at:
        ~/.gemini/antigravity/brain/<conv-id>/.system_generated/logs/
    """
    brain_dir = Path.home() / ".gemini" / "antigravity" / "brain" / conv_id
    logs_dir = brain_dir / ".system_generated" / "logs"

    if not logs_dir.exists():
        return AgentRunMetrics(
            task_id="unknown", agent="antigravity", skill_enabled=False,
            notes=f"Logs not found: {logs_dir}",
        )

    total_text = ""
    turn_count = 0

    for log_file in sorted(logs_dir.iterdir()):
        if log_file.is_file():
            try:
                content = log_file.read_text(encoding="utf-8")
                total_text += content
                # Count turns by looking for user/assistant markers
                turn_count += content.count("ASSISTANT:") + content.count("assistant")
            except (OSError, UnicodeDecodeError):
                continue

    # Estimate tokens from text length
    total_tokens = estimate_tokens(total_text)

    return AgentRunMetrics(
        task_id="unknown",
        agent="antigravity",
        skill_enabled=False,
        total_tokens=total_tokens,
        input_tokens=total_tokens // 2,  # rough estimate
        output_tokens=total_tokens // 2,
        turn_count=turn_count,
        session_id=conv_id,
    )


def parse_generic_logs(log_path: str) -> AgentRunMetrics:
    """Parse generic JSON/JSONL agent logs."""
    path = Path(log_path)
    if not path.exists():
        return AgentRunMetrics(
            task_id="unknown", agent="opencode", skill_enabled=False,
            notes=f"File not found: {log_path}",
        )

    text = path.read_text(encoding="utf-8")
    total_tokens = estimate_tokens(text)

    return AgentRunMetrics(
        task_id="unknown",
        agent="opencode",
        skill_enabled=False,
        total_tokens=total_tokens,
        session_id=path.stem,
    )


LOG_PARSERS = {
    "claude_code": parse_claude_code_logs,
    "antigravity": parse_antigravity_logs,
    "opencode": parse_generic_logs,
}


# ---------------------------------------------------------------------------
# Comparison engine
# ---------------------------------------------------------------------------


def compare_runs(
    with_skill: AgentRunMetrics,
    without_skill: AgentRunMetrics,
) -> TaskComparison:
    """Compare two runs and compute improvement percentages."""
    accuracy_imp = with_skill.accuracy_pct - without_skill.accuracy_pct

    token_savings = 0.0
    if without_skill.total_tokens > 0:
        token_savings = (
            (without_skill.total_tokens - with_skill.total_tokens)
            / without_skill.total_tokens
            * 100
        )

    speed_imp = 0.0
    if without_skill.wall_clock_seconds > 0:
        speed_imp = (
            (without_skill.wall_clock_seconds - with_skill.wall_clock_seconds)
            / without_skill.wall_clock_seconds
            * 100
        )

    return TaskComparison(
        task_id=with_skill.task_id,
        with_skill=with_skill,
        without_skill=without_skill,
        accuracy_improvement=round(accuracy_imp, 1),
        token_savings_pct=round(token_savings, 1),
        speed_improvement_pct=round(speed_imp, 1),
        tool_call_reduction=without_skill.tool_calls - with_skill.tool_calls,
        turn_reduction=without_skill.turn_count - with_skill.turn_count,
    )


# ---------------------------------------------------------------------------
# Results persistence
# ---------------------------------------------------------------------------


def save_run(metrics: AgentRunMetrics, results_dir: str) -> str:
    """Save run metrics to a JSON file."""
    rd = Path(results_dir)
    rd.mkdir(parents=True, exist_ok=True)

    skill_label = "with_skill" if metrics.skill_enabled else "without_skill"
    filename = f"{metrics.task_id}_{metrics.agent}_{skill_label}.json"
    filepath = rd / filename

    metrics.timestamp = datetime.now(timezone.utc).isoformat()
    filepath.write_text(json.dumps(asdict(metrics), indent=2), encoding="utf-8")
    return str(filepath)


def load_results(results_dir: str) -> List[AgentRunMetrics]:
    """Load all saved run metrics from a directory."""
    rd = Path(results_dir)
    if not rd.exists():
        return []

    results = []
    for f in sorted(rd.glob("*.json")):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            results.append(AgentRunMetrics(**data))
        except (json.JSONDecodeError, TypeError):
            continue
    return results


def build_comparisons(results: List[AgentRunMetrics]) -> List[TaskComparison]:
    """Group results by task+agent and build comparisons."""
    # Group by (task_id, agent)
    groups: Dict[tuple, Dict[str, AgentRunMetrics]] = {}
    for r in results:
        key = (r.task_id, r.agent)
        if key not in groups:
            groups[key] = {}
        label = "with" if r.skill_enabled else "without"
        groups[key][label] = r

    comparisons = []
    for (task_id, agent), runs in sorted(groups.items()):
        if "with" in runs and "without" in runs:
            comparisons.append(compare_runs(runs["with"], runs["without"]))

    return comparisons


# ---------------------------------------------------------------------------
# Report generation
# ---------------------------------------------------------------------------


def format_report_markdown(comparisons: List[TaskComparison]) -> str:
    """Generate a markdown comparison report."""
    if not comparisons:
        return "# Agent Evaluation Report\n\nNo comparison data available.\n"

    lines = [
        "# Agent Evaluation Report: Python Code Assistant Skill\n",
        f"_Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}_\n",
    ]

    # Group by agent
    agents: Dict[str, List[TaskComparison]] = {}
    for comp in comparisons:
        agent = comp.with_skill.agent
        agents.setdefault(agent, []).append(comp)

    for agent, comps in agents.items():
        lines.append(f"\n## {agent.replace('_', ' ').title()}\n")
        lines.append("| Task | Accuracy | Tokens | Speed | Tools | Turns |")
        lines.append("|------|----------|--------|-------|-------|-------|")

        total_acc = 0
        total_tok = 0
        total_speed = 0
        total_tools = 0
        total_turns = 0

        for c in comps:
            task_name = EVAL_TASKS.get(c.task_id, {}).get("name", c.task_id)
            acc_str = (
                f"{c.without_skill.accuracy_pct:.0f}%→{c.with_skill.accuracy_pct:.0f}%"
            )
            tok_str = f"{c.token_savings_pct:+.0f}%"
            speed_str = f"{c.speed_improvement_pct:+.0f}%"
            tools_str = f"{-c.tool_call_reduction:+d}" if c.tool_call_reduction else "0"
            turns_str = f"{-c.turn_reduction:+d}" if c.turn_reduction else "0"

            lines.append(
                f"| {task_name} | {acc_str} | {tok_str} | {speed_str} | {tools_str} | {turns_str} |"
            )

            total_acc += c.accuracy_improvement
            total_tok += c.token_savings_pct
            total_speed += c.speed_improvement_pct
            total_tools += c.tool_call_reduction
            total_turns += c.turn_reduction

        n = len(comps)
        if n > 0:
            lines.append(
                f"| **AVERAGE** | **{total_acc/n:+.1f}%** | "
                f"**{total_tok/n:+.1f}%** | **{total_speed/n:+.1f}%** | "
                f"**{-total_tools/n:+.1f}** | **{-total_turns/n:+.1f}** |"
            )

        lines.append("")
        lines.append("### Key Findings")
        lines.append(f"- Accuracy: {total_acc/n:+.1f}% improvement on average")
        lines.append(f"- Token efficiency: {total_tok/n:+.1f}% tokens consumed per task")
        lines.append(f"- Tool calls: {total_tools/n:.1f} fewer tool invocations per task")

    return "\n".join(lines)


def format_report_json(comparisons: List[TaskComparison]) -> str:
    """Generate a JSON comparison report."""
    data = []
    for c in comparisons:
        data.append({
            "task_id": c.task_id,
            "task_name": EVAL_TASKS.get(c.task_id, {}).get("name", c.task_id),
            "agent": c.with_skill.agent,
            "accuracy_improvement": c.accuracy_improvement,
            "token_savings_pct": c.token_savings_pct,
            "speed_improvement_pct": c.speed_improvement_pct,
            "tool_call_reduction": c.tool_call_reduction,
            "turn_reduction": c.turn_reduction,
            "with_skill": asdict(c.with_skill),
            "without_skill": asdict(c.without_skill),
        })
    return json.dumps(data, indent=2)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(
        description="Agent evaluation harness for the Python Code Assistant Skill"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # list-tasks
    subparsers.add_parser("list-tasks", help="List all evaluation tasks")

    # record
    p_record = subparsers.add_parser("record", help="Record an evaluation run")
    p_record.add_argument("--task", required=True, help="Task ID")
    p_record.add_argument("--agent", required=True, choices=SUPPORTED_AGENTS)
    p_record.add_argument("--skill-enabled", action="store_true")
    p_record.add_argument("--session-id", default="")
    p_record.add_argument("--wall-clock", type=float, default=0)
    p_record.add_argument("--tests-passed", type=int, default=0)
    p_record.add_argument("--tests-total", type=int, default=0)
    p_record.add_argument("--input-tokens", type=int, default=0)
    p_record.add_argument("--output-tokens", type=int, default=0)
    p_record.add_argument("--tool-calls", type=int, default=0)
    p_record.add_argument("--turns", type=int, default=0)
    p_record.add_argument("--model", default="")
    p_record.add_argument("--notes", default="")
    p_record.add_argument(
        "--results-dir",
        default="references/eval_results",
        help="Directory to save results",
    )

    # parse-logs
    p_parse = subparsers.add_parser("parse-logs", help="Parse agent conversation logs")
    p_parse.add_argument("--agent", required=True, choices=SUPPORTED_AGENTS)
    p_parse.add_argument("--session", required=True, help="Path to session log or conversation ID")
    p_parse.add_argument("--task", default="unknown", help="Task ID to associate")
    p_parse.add_argument("--skill-enabled", action="store_true")

    # compare
    p_compare = subparsers.add_parser("compare", help="Compare evaluation results")
    p_compare.add_argument(
        "--results-dir",
        default="references/eval_results",
        help="Directory with saved results",
    )
    p_compare.add_argument("--format", choices=["markdown", "json"], default="markdown")

    # report
    p_report = subparsers.add_parser("report", help="Generate full evaluation report")
    p_report.add_argument(
        "--results-dir",
        default="references/eval_results",
        help="Directory with saved results",
    )
    p_report.add_argument("--format", choices=["markdown", "json"], default="markdown")
    p_report.add_argument("--output", help="Save report to file")

    args = parser.parse_args()

    if args.command == "list-tasks":
        for task_id, info in EVAL_TASKS.items():
            print(f"\n{'='*60}")
            print(f"  {task_id}: {info['name']}")
            print(f"  Category: {info['category']} | Difficulty: {info['difficulty']}")
            print(f"  Expected skill usage: {', '.join(info['expected_skill_usage'])}")
            print(f"\n  Prompt:\n  {info['prompt']}")
        return

    if args.command == "record":
        accuracy = (
            args.tests_passed / args.tests_total * 100
            if args.tests_total > 0
            else 0
        )
        metrics = AgentRunMetrics(
            task_id=args.task,
            agent=args.agent,
            skill_enabled=args.skill_enabled,
            tests_total=args.tests_total,
            tests_passed=args.tests_passed,
            accuracy_pct=accuracy,
            input_tokens=args.input_tokens,
            output_tokens=args.output_tokens,
            total_tokens=args.input_tokens + args.output_tokens,
            wall_clock_seconds=args.wall_clock,
            turn_count=args.turns,
            tool_calls=args.tool_calls,
            model=args.model,
            session_id=args.session_id,
            notes=args.notes,
        )
        filepath = save_run(metrics, args.results_dir)
        print(f"Run saved to: {filepath}")
        return

    if args.command == "parse-logs":
        parser_fn = LOG_PARSERS.get(args.agent)
        if not parser_fn:
            print(f"No parser for agent: {args.agent}", file=sys.stderr)
            sys.exit(1)

        metrics = parser_fn(args.session)
        metrics.task_id = args.task
        metrics.skill_enabled = args.skill_enabled

        print(json.dumps(asdict(metrics), indent=2))
        return

    if args.command in ("compare", "report"):
        results = load_results(args.results_dir)
        if not results:
            print(f"No results found in: {args.results_dir}", file=sys.stderr)
            sys.exit(1)

        comparisons = build_comparisons(results)

        if args.format == "json":
            report = format_report_json(comparisons)
        else:
            report = format_report_markdown(comparisons)

        if args.command == "report" and hasattr(args, "output") and args.output:
            Path(args.output).write_text(report, encoding="utf-8")
            print(f"Report saved to: {args.output}")
        else:
            print(report)
        return


if __name__ == "__main__":
    main()
