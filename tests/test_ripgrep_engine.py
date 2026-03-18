import json
import sys
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))
sys.path.insert(0, str(ROOT))

from ripgrep_engine import (  # noqa: E402
    _classify_config_file,
    _parse_rg_json_output,
    find_config_references,
    ripgrep_available,
    search_text,
)


class TestRipgrepAvailability:
    def test_returns_bool(self):
        result = ripgrep_available()
        assert isinstance(result, bool)

    def test_unavailable_when_not_on_path(self):
        with patch("ripgrep_engine.subprocess.run", side_effect=FileNotFoundError):
            assert ripgrep_available() is False


class TestParseRgJsonOutput:
    def test_empty_output(self):
        assert _parse_rg_json_output("") == []

    def test_parses_match_messages(self):
        rg_output = json.dumps(
            {
                "type": "match",
                "data": {
                    "path": {"text": "/project/src/main.py"},
                    "line_number": 42,
                    "lines": {"text": "x = DATABASE_URL\n"},
                    "submatches": [{"match": {"text": "DATABASE_URL"}, "start": 4, "end": 16}],
                },
            }
        )
        matches = _parse_rg_json_output(rg_output)
        assert len(matches) == 1
        assert matches[0]["file"] == "/project/src/main.py"
        assert matches[0]["line"] == 42
        assert matches[0]["text"] == "x = DATABASE_URL"
        assert matches[0]["submatches"][0]["match"] == "DATABASE_URL"

    def test_skips_non_match_messages(self):
        lines = "\n".join(
            [
                json.dumps({"type": "begin", "data": {"path": {"text": "a.py"}}}),
                json.dumps(
                    {
                        "type": "match",
                        "data": {
                            "path": {"text": "a.py"},
                            "line_number": 1,
                            "lines": {"text": "match\n"},
                            "submatches": [],
                        },
                    }
                ),
                json.dumps({"type": "end", "data": {}}),
                json.dumps({"type": "summary", "data": {}}),
            ]
        )
        matches = _parse_rg_json_output(lines)
        assert len(matches) == 1

    def test_handles_malformed_json_lines(self):
        lines = "not json\n" + json.dumps(
            {
                "type": "match",
                "data": {
                    "path": {"text": "a.py"},
                    "line_number": 1,
                    "lines": {"text": "ok\n"},
                    "submatches": [],
                },
            }
        )
        matches = _parse_rg_json_output(lines)
        assert len(matches) == 1


class TestClassifyConfigFile:
    def test_python(self):
        assert _classify_config_file("py", "settings.py") == "python"

    def test_yaml(self):
        assert _classify_config_file("yaml", "config.yaml") == "yaml"
        assert _classify_config_file("yml", "config.yml") == "yaml"

    def test_docker_compose(self):
        assert _classify_config_file("yml", "docker-compose.yml") == "docker-compose"
        assert _classify_config_file("yaml", "docker-compose.prod.yaml") == "docker-compose"

    def test_toml(self):
        assert _classify_config_file("toml", "pyproject.toml") == "toml"

    def test_env(self):
        assert _classify_config_file("env", ".env") == "env"
        assert _classify_config_file("", ".env.production") == "env"

    def test_config_extensions(self):
        assert _classify_config_file("cfg", "setup.cfg") == "config"
        assert _classify_config_file("ini", "tox.ini") == "config"
        assert _classify_config_file("conf", "app.conf") == "config"

    def test_json(self):
        assert _classify_config_file("json", "package.json") == "json"

    def test_dockerfile(self):
        assert _classify_config_file("", "Dockerfile") == "docker"
        assert _classify_config_file("", "Dockerfile.prod") == "docker"

    def test_unknown(self):
        assert _classify_config_file("rs", "main.rs") == "other"


class TestSearchText:
    def test_returns_error_when_rg_unavailable(self, tmp_path):
        with patch("ripgrep_engine.ripgrep_available", return_value=False):
            result = search_text("pattern", str(tmp_path))
            assert "error" in result
            assert "not installed" in result["error"]

    def test_returns_error_for_invalid_directory(self):
        with patch("ripgrep_engine.ripgrep_available", return_value=True):
            result = search_text("pattern", "/nonexistent/path/xyz")
            assert "error" in result
            assert "Not a directory" in result["error"]

    def test_returns_structured_result_on_no_matches(self, tmp_path):
        (tmp_path / "test.py").write_text("x = 1\n")

        mock_result = type("Result", (), {"returncode": 1, "stdout": "", "stderr": ""})()
        with (
            patch("ripgrep_engine.ripgrep_available", return_value=True),
            patch("ripgrep_engine.subprocess.run", return_value=mock_result),
        ):
            result = search_text("nonexistent_pattern", str(tmp_path))
            assert result["match_count"] == 0
            assert result["truncated"] is False
            assert result["matches"] == []

    def test_returns_matches_on_success(self, tmp_path):
        rg_output = json.dumps(
            {
                "type": "match",
                "data": {
                    "path": {"text": str(tmp_path / "app.py")},
                    "line_number": 10,
                    "lines": {"text": "TODO: fix this\n"},
                    "submatches": [{"match": {"text": "TODO"}, "start": 0, "end": 4}],
                },
            }
        )
        mock_result = type("Result", (), {"returncode": 0, "stdout": rg_output, "stderr": ""})()
        with (
            patch("ripgrep_engine.ripgrep_available", return_value=True),
            patch("ripgrep_engine.subprocess.run", return_value=mock_result),
        ):
            result = search_text("TODO", str(tmp_path))
            assert result["match_count"] == 1
            assert result["pattern"] == "TODO"

    def test_truncation_flag(self, tmp_path):
        lines = []
        for i in range(3):
            lines.append(
                json.dumps(
                    {
                        "type": "match",
                        "data": {
                            "path": {"text": str(tmp_path / "a.py")},
                            "line_number": i + 1,
                            "lines": {"text": f"line {i}\n"},
                            "submatches": [],
                        },
                    }
                )
            )
        mock_result = type(
            "Result", (), {"returncode": 0, "stdout": "\n".join(lines), "stderr": ""}
        )()
        with (
            patch("ripgrep_engine.ripgrep_available", return_value=True),
            patch("ripgrep_engine.subprocess.run", return_value=mock_result),
        ):
            result = search_text("line", str(tmp_path), max_results=2)
            assert result["truncated"] is True
            assert result["match_count"] == 2

    def test_timeout_returns_error(self, tmp_path):
        import subprocess

        with (
            patch("ripgrep_engine.ripgrep_available", return_value=True),
            patch(
                "ripgrep_engine.subprocess.run",
                side_effect=subprocess.TimeoutExpired(cmd="rg", timeout=60),
            ),
        ):
            result = search_text("pattern", str(tmp_path))
            assert "error" in result
            assert "timed out" in result["error"]


class TestFindConfigReferences:
    def test_returns_error_when_rg_unavailable(self, tmp_path):
        with patch("ripgrep_engine.ripgrep_available", return_value=False):
            result = find_config_references("KEY", str(tmp_path))
            assert "error" in result

    def test_returns_error_for_invalid_directory(self):
        with patch("ripgrep_engine.ripgrep_available", return_value=True):
            result = find_config_references("KEY", "/nonexistent/xyz")
            assert "error" in result

    def test_categorizes_results(self, tmp_path):
        matches = []
        for fname, line_text in [
            ("settings.py", "DATABASE_URL = 'postgres://...'"),
            ("config.yaml", "DATABASE_URL: postgres://..."),
            (".env", "DATABASE_URL=postgres://..."),
        ]:
            matches.append(
                json.dumps(
                    {
                        "type": "match",
                        "data": {
                            "path": {"text": str(tmp_path / fname)},
                            "line_number": 1,
                            "lines": {"text": f"{line_text}\n"},
                            "submatches": [
                                {"match": {"text": "DATABASE_URL"}, "start": 0, "end": 12}
                            ],
                        },
                    }
                )
            )
        mock_result = type(
            "Result", (), {"returncode": 0, "stdout": "\n".join(matches), "stderr": ""}
        )()
        with (
            patch("ripgrep_engine.ripgrep_available", return_value=True),
            patch("ripgrep_engine.subprocess.run", return_value=mock_result),
        ):
            result = find_config_references("DATABASE_URL", str(tmp_path))
            assert result["total_references"] == 3
            assert "python" in result["categories"]
            assert "yaml" in result["categories"]
            assert "env" in result["categories"]
            assert result["category_counts"]["python"] == 1
