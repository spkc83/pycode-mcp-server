# Agent Evaluation Guide

## Overview

This directory contains **10 standardized coding tasks** for evaluating
coding agents (Claude Code, Antigravity, OpenCode) with and without the
Python Code Assistant Skill installed.

## Quick Start

### 1. Prepare Two Project Copies

```bash
# Copy with skill (unchanged)
cp -r python-code-assistant-skill /tmp/eval_with_skill

# Copy without skill (remove skill files)
cp -r python-code-assistant-skill /tmp/eval_without_skill
rm /tmp/eval_without_skill/SKILL.md
rm -r /tmp/eval_without_skill/scripts/
```

### 2. Run Each Task

For each task (01–10), in each condition (with/without skill):

```bash
cd /tmp/eval_with_skill   # or /tmp/eval_without_skill

# Start your agent
claude                    # for Claude Code
# or open in Antigravity/OpenCode

# Give the agent the EXACT prompt from the task file
# (see the docstring at top of each task_XX_*.py file)

# IMPORTANT: Don't help the agent! Let it work autonomously.
# Note the wall-clock time and session ID.

# After completion, run the verification tests:
pytest tests/eval_tasks/task_01_doc_lookup.py -v
```

### 3. Record Results

```bash
# Record each run
python scripts/agent_eval.py record \
    --task task_01_doc_lookup \
    --agent claude_code \
    --skill-enabled \
    --session-id <from agent> \
    --wall-clock <seconds> \
    --tests-passed <N> \
    --tests-total <N> \
    --input-tokens <N> \
    --output-tokens <N> \
    --tool-calls <N> \
    --turns <N>
```

### 4. Generate Report

```bash
python scripts/agent_eval.py compare --results-dir references/eval_results/
python scripts/agent_eval.py report --results-dir references/eval_results/ \
    --output references/eval_report.md
```

## Task List

| # | Task | Category | Difficulty | Key Skill |
|---|------|----------|------------|-----------|
| 01 | Doc Lookup | Documentation | Easy | doc_lookup.py |
| 02 | Error Handling | Documentation | Medium | doc_lookup.py |
| 03 | Class Usage | Documentation | Medium | doc_lookup.py |
| 04 | File Analysis | Understanding | Easy | code_analyzer.py |
| 05 | Project Deps | Understanding | Hard | project_analyzer.py |
| 06 | Refactor | Code Generation | Medium | code_analyzer.py |
| 07 | Debug Fix | Code Generation | Easy | diagnostics.py |
| 08 | Test Generation | Code Generation | Hard | code_analyzer.py |
| 09 | API Integration | Cross-Module | Hard | jedi_engine.py |
| 10 | Cross-Module | Cross-Module | Medium | health_check.py |

## Metrics Collected

| Metric | Source | Description |
|--------|--------|-------------|
| **Accuracy** | pytest results | % of verification tests passing |
| **Tokens** | Agent logs | Total input + output tokens used |
| **Speed** | Manual timing | Wall-clock seconds to complete |
| **Tool Calls** | Agent logs | Number of tool invocations |
| **Turns** | Agent logs | Number of human↔agent exchanges |

## Getting Token Counts

### Claude Code
```bash
# After a session, parse the JSONL log:
python scripts/agent_eval.py parse-logs \
    --agent claude_code \
    --session ~/.claude/projects/<hash>/<session>.jsonl

# Or use /cost command during session
```

### Antigravity
```bash
# Parse conversation logs:
python scripts/agent_eval.py parse-logs \
    --agent antigravity \
    --session <conversation-id>
```

## Tips for Valid Evaluations

1. **Use identical prompts** — copy verbatim from each task file's docstring
2. **Don't help the agent** — let it work autonomously
3. **Run 3+ times** per condition if possible (agents are non-deterministic)
4. **Same model** — use the same LLM model for with/without comparisons
5. **Same environment** — same machine, same Python version, same packages
6. **Create `task_outputs/`** dir — tasks expect agents to write here
