"""Task 06: Refactor — add get_or_set method to CacheManager.

Prompt to give the agent:
---
Add a `get_or_set(self, name, factory_fn, package=None)` method to the
CacheManager class in `scripts/cache.py`. It should return the cached value
if present, otherwise call factory_fn(), cache the result, and return it.
---

Expected skill usage: code_analyzer.py, jedi_engine.py
Difficulty: Medium
"""

import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent.parent.parent / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))


class TestTask06Refactor:
    def test_method_exists(self):
        from cache import CacheManager

        mgr = CacheManager.__new__(CacheManager)
        assert hasattr(mgr, "get_or_set"), "CacheManager should have get_or_set method"

    def test_get_or_set_callable(self):
        from cache import CacheManager

        mgr = CacheManager.__new__(CacheManager)
        assert callable(getattr(mgr, "get_or_set", None))

    def test_get_or_set_calls_factory(self, tmp_path):
        from cache import CacheManager

        mgr = CacheManager(cache_dir=str(tmp_path / ".cache"))

        call_count = {"n": 0}

        def factory():
            call_count["n"] += 1
            return {"data": "from_factory"}

        result = mgr.get_or_set("test_key", factory)
        assert result is not None
        assert call_count["n"] == 1

    def test_get_or_set_returns_cached(self, tmp_path):
        from cache import CacheManager

        mgr = CacheManager(cache_dir=str(tmp_path / ".cache"))

        call_count = {"n": 0}

        def factory():
            call_count["n"] += 1
            return {"data": "from_factory"}

        result1 = mgr.get_or_set("test_key2", factory)
        result2 = mgr.get_or_set("test_key2", factory)
        # Factory should only be called once
        assert call_count["n"] == 1
        assert result1 == result2

    def test_existing_tests_still_pass(self):
        """Importing cache module should not raise."""
        import cache  # noqa: F401
