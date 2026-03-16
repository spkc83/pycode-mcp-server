"""Task 04: File Analysis — understand cache.py internals.

Prompt to give the agent:
---
Read `scripts/cache.py` and answer: What type of eviction does it use?
What is the max entry count? What is the default TTL?
Save your answers as a JSON file `task_outputs/task_04_output.json` with
keys: eviction_type, max_entries, ttl_hours.
---

Expected skill usage: code_analyzer.py
Difficulty: Easy
"""

import json
import sys
from pathlib import Path

import pytest

OUTPUTS_DIR = Path(__file__).resolve().parent.parent.parent / "task_outputs"


@pytest.fixture(autouse=True)
def _skip_if_no_output():
    if not (OUTPUTS_DIR / "task_04_output.json").exists():
        pytest.skip("task_04_output.json not yet created by agent")


class TestTask04FileAnalysis:

    @pytest.fixture
    def answers(self):
        return json.loads((OUTPUTS_DIR / "task_04_output.json").read_text())

    def test_has_required_keys(self, answers):
        assert "eviction_type" in answers
        assert "max_entries" in answers
        assert "ttl_hours" in answers

    def test_eviction_type(self, answers):
        eviction = str(answers["eviction_type"]).upper()
        assert "LFU" in eviction, f"Expected LFU, got: {answers['eviction_type']}"

    def test_max_entries(self, answers):
        assert int(answers["max_entries"]) == 500

    def test_ttl_hours(self, answers):
        ttl = answers["ttl_hours"]
        # Accept 168 (hours) or 7 (days) variants
        assert ttl in (168, 7, "168", "7", "168 hours", "7 days"), (
            f"Expected 168 hours / 7 days, got: {ttl}"
        )
