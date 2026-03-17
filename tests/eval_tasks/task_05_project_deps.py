"""Task 05: Project Dependencies — understand project structure.

Prompt to give the agent:
---
Analyze this project and answer: What are the third-party dependencies?
Which scripts import from other scripts? Are there any circular dependencies?
Save your answers as JSON `task_outputs/task_05_output.json` with keys:
third_party (list), import_graph (dict of lists), circular_deps (list of lists).
---

Expected skill usage: project_analyzer.py
Difficulty: Hard
"""

import json
from pathlib import Path

import pytest

OUTPUTS_DIR = Path(__file__).resolve().parent.parent.parent / "task_outputs"


@pytest.fixture(autouse=True)
def _skip_if_no_output():
    if not (OUTPUTS_DIR / "task_05_output.json").exists():
        pytest.skip("task_05_output.json not yet created by agent")


class TestTask05ProjectDeps:
    @pytest.fixture
    def answers(self):
        return json.loads((OUTPUTS_DIR / "task_05_output.json").read_text())

    def test_has_required_keys(self, answers):
        assert "third_party" in answers
        assert "import_graph" in answers
        assert "circular_deps" in answers

    def test_jedi_is_third_party(self, answers):
        third_party = [d.lower() for d in answers["third_party"]]
        assert "jedi" in third_party, f"jedi missing from third_party: {answers['third_party']}"

    def test_import_graph_is_dict(self, answers):
        assert isinstance(answers["import_graph"], dict)

    def test_import_graph_not_empty(self, answers):
        assert len(answers["import_graph"]) > 0, "Import graph should not be empty"

    def test_circular_deps_is_list(self, answers):
        assert isinstance(answers["circular_deps"], list)
