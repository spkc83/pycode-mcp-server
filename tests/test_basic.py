"""Comprehensive tests for the Python Code Assistant skill."""

import importlib.util
import json
import sys
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))


def load_module_from_path(name: str, path: Path) -> Any:
    spec = importlib.util.spec_from_file_location(name, str(path))
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load module from {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


class TestInspectEnv:
    @pytest.fixture
    def module(self):
        return load_module_from_path("inspect_env", SCRIPTS_DIR / "inspect_env.py")

    def test_returns_list_of_tuples(self, module):
        packages = module.list_installed_packages()
        assert isinstance(packages, list)
        assert all(isinstance(item, tuple) and len(item) == 2 for item in packages)

    def test_contains_pytest(self, module):
        packages = module.list_installed_packages()
        package_names = [name.lower() for name, _ in packages]
        assert "pytest" in package_names

    def test_packages_are_sorted(self, module):
        packages = module.list_installed_packages()
        names = [name for name, _ in packages]
        assert names == sorted(names)

    def test_versions_are_strings(self, module):
        packages = module.list_installed_packages()
        for name, version in packages[:10]:
            assert isinstance(name, str)
            assert isinstance(version, str)
            assert len(version) > 0

    def test_get_package_details(self, module):
        details = module.get_package_details("pytest")
        assert details is not None
        assert details["name"].lower() == "pytest"
        assert "version" in details
        assert "import_names" in details
        assert "pytest" in details["import_names"]

    def test_find_package_by_import(self, module):
        pkg = module.find_package_by_import("pytest")
        assert pkg is not None
        assert pkg.lower() == "pytest"

    def test_is_package_installed(self, module):
        assert module.is_package_installed("pytest") is True
        assert module.is_package_installed("nonexistent_package_xyz123") is False

    def test_get_environment_info(self, module):
        info = module.get_environment_info()
        assert "python_version" in info
        assert "python_executable" in info
        assert "in_virtualenv" in info

    def test_get_full_environment(self, module):
        env = module.get_full_environment()
        assert "environment" in env
        assert "packages" in env
        assert "package_count" in env
        assert env["package_count"] > 0


class TestCodeAnalyzer:
    @pytest.fixture
    def module(self):
        return load_module_from_path("code_analyzer", SCRIPTS_DIR / "code_analyzer.py")

    def test_parses_simple_function(self, module, tmp_path):
        content = "def hello():\n    return 'world'\n"
        test_file = tmp_path / "sample.py"
        test_file.write_text(content)
        result = module.analyze_source(test_file.read_text())
        assert isinstance(result, dict)
        assert "functions" in result
        assert len(result["functions"]) == 1
        assert result["functions"][0]["name"] == "hello"

    def test_parses_class(self, module):
        source = "class MyClass:\n    pass\n"
        result = module.analyze_source(source)
        assert isinstance(result, dict)
        assert "classes" in result
        assert len(result["classes"]) == 1
        assert result["classes"][0]["name"] == "MyClass"

    def test_parses_imports(self, module):
        source = "import os\nfrom pathlib import Path\n"
        result = module.analyze_source(source)
        assert isinstance(result, dict)
        assert "imports" in result
        assert "from_imports" in result

    def test_raises_on_syntax_error(self, module):
        source = "def broken(\n"
        with pytest.raises(SyntaxError):
            module.analyze_source(source)

    def test_extracts_function_signature(self, module):
        source = "def greet(name: str, times: int = 1) -> str:\n    return name * times\n"
        result = module.analyze_source(source)
        assert "functions" in result
        func = result["functions"][0]
        assert "signature" in func
        assert "name" in func["signature"]
        assert "parameters" in func
        assert len(func["parameters"]) == 2

    def test_extracts_class_methods(self, module):
        source = '''
class Calculator:
    def add(self, a: int, b: int) -> int:
        return a + b
    
    def subtract(self, a: int, b: int) -> int:
        return a - b
'''
        result = module.analyze_source(source)
        assert "classes" in result
        cls = result["classes"][0]
        assert cls["name"] == "Calculator"
        assert "methods" in cls
        method_names = [m["name"] for m in cls["methods"]]
        assert "add" in method_names
        assert "subtract" in method_names

    def test_extracts_decorators(self, module):
        source = '''
@dataclass
class Point:
    x: int
    y: int

@staticmethod
def helper():
    pass
'''
        result = module.analyze_source(source)
        assert "decorators_used" in result
        assert "dataclass" in result["decorators_used"]

    def test_raw_mode(self, module):
        source = "x = 1"
        result = module.analyze_source_raw(source)
        assert isinstance(result, str)
        assert "Module" in result

    def test_analyze_file(self, module, tmp_path):
        content = "def test_func():\n    pass\n"
        test_file = tmp_path / "test_module.py"
        test_file.write_text(content)
        result = module.analyze_file(str(test_file))
        assert isinstance(result, dict)
        assert "file_name" in result
        assert result["file_name"] == "test_module.py"


class TestDocLookup:
    @pytest.fixture
    def module(self):
        return load_module_from_path("doc_lookup", SCRIPTS_DIR / "doc_lookup.py")

    def test_resolve_object_builtin(self, module):
        obj, err = module.resolve_object("str")
        assert obj is str
        assert err is None

    def test_resolve_object_stdlib(self, module):
        obj, err = module.resolve_object("json.dumps")
        import json as json_mod
        assert obj is json_mod.dumps
        assert err is None

    def test_resolve_object_nested(self, module):
        obj, err = module.resolve_object("os.path.join")
        import os.path
        assert obj is os.path.join
        assert err is None

    def test_resolve_object_not_found(self, module):
        obj, err = module.resolve_object("nonexistent_module_xyz.func")
        assert obj is None
        assert err is not None

    def test_structured_docs_for_builtin(self, module):
        result = module.get_local_docs("str", use_cache=False, structured=True)
        assert isinstance(result, dict)
        assert result["found"] is True
        assert result["name"] == "str"
        assert "object_type" in result

    def test_structured_docs_for_function(self, module):
        result = module.get_local_docs("json.dumps", use_cache=False, structured=True)
        assert isinstance(result, dict)
        assert result["found"] is True
        assert "signature" in result
        assert "parameters" in result or "full_docstring" in result

    def test_structured_docs_for_class(self, module):
        result = module.get_local_docs("pathlib.Path", use_cache=False, structured=True)
        assert isinstance(result, dict)
        assert result["found"] is True
        assert result["object_type"] == "class"

    def test_raw_docs_mode(self, module):
        result = module.get_local_docs("str", use_cache=False, structured=False)
        assert isinstance(result, str)
        assert len(result) > 0

    def test_handles_nonexistent_name(self, module):
        result = module.get_local_docs("this_does_not_exist_xyz123", use_cache=False, structured=True)
        assert isinstance(result, dict)
        assert result["found"] is False
        assert "error" in result

    def test_import_statement_generation(self, module):
        result = module.get_local_docs("json.dumps", use_cache=False, structured=True)
        assert "import_statement" in result
        assert "json" in result["import_statement"]

    def test_example_extraction(self, module):
        result = module.get_structured_docs("json.dumps")
        assert result["found"] is True

    def test_extract_parameters(self, module):
        result = module.get_structured_docs("json.dumps")
        if "parameters" in result:
            params = result["parameters"]
            assert isinstance(params, list)
            param_names = [p["name"] for p in params]
            assert "obj" in param_names


class TestCache:
    @pytest.fixture
    def cache_module(self):
        return load_module_from_path("cache", SCRIPTS_DIR / "cache.py")

    @pytest.fixture
    def cache_manager(self, cache_module, tmp_path):
        cache_file = tmp_path / "test_cache.json"
        return cache_module.CacheManager(cache_file)

    def test_empty_cache_initialization(self, cache_manager):
        data = cache_manager.load()
        assert data["version"] == "2"
        assert "docs" in data
        assert "packages" in data
        assert "stats" in data

    def test_set_and_get_docstring(self, cache_manager):
        cache_manager.set_docstring("test.func", "Test documentation")
        cache_manager.save()
        
        result = cache_manager.get_docstring("test.func")
        assert result == "Test documentation"

    def test_set_and_get_docstring_with_package(self, cache_manager):
        cache_manager.update_packages([("test", "1.0.0")])
        cache_manager.set_docstring("test.func", "Test documentation", "test", "1.0.0")
        cache_manager.save()
        
        result = cache_manager.get_docstring("test.func")
        assert result == "Test documentation"

    def test_cache_miss_returns_none(self, cache_manager):
        result = cache_manager.get_docstring("nonexistent")
        assert result is None

    def test_update_packages(self, cache_manager):
        packages = [("pytest", "7.0.0"), ("numpy", "1.24.0")]
        hash_val = cache_manager.update_packages(packages)
        cache_manager.save()
        
        assert hash_val is not None
        assert len(hash_val) == 16

    def test_packages_stale_detection(self, cache_manager):
        packages_v1 = [("pytest", "7.0.0")]
        packages_v2 = [("pytest", "8.0.0")]
        
        cache_manager.update_packages(packages_v1)
        cache_manager.save()
        
        assert not cache_manager.is_packages_stale(packages_v1)
        assert cache_manager.is_packages_stale(packages_v2)

    def test_clear_cache(self, cache_manager):
        cache_manager.set_docstring("test", "data")
        cache_manager.save()
        
        cache_manager.clear()
        
        assert cache_manager.get_docstring("test") is None

    def test_stats_tracking(self, cache_manager):
        cache_manager.get_docstring("miss1")
        cache_manager.get_docstring("miss2")
        
        cache_manager.set_docstring("hit", "data")
        cache_manager.get_docstring("hit")
        cache_manager.save()
        
        stats = cache_manager.get_stats()
        assert stats["cache_misses"] >= 2
        assert stats["cache_hits"] >= 1

    def test_persistence(self, cache_module, tmp_path):
        cache_file = tmp_path / "persist_test.json"
        
        cm1 = cache_module.CacheManager(cache_file)
        cm1.set_docstring("persistent", "data")
        cm1.save()
        
        cm2 = cache_module.CacheManager(cache_file)
        result = cm2.get_docstring("persistent")
        assert result == "data"

    def test_lfu_eviction(self, cache_module, tmp_path):
        cache_file = tmp_path / "eviction_test.json"
        cm = cache_module.CacheManager(cache_file)
        
        cm.set_docstring("low_use", "rarely accessed")
        cm.set_docstring("high_use", "frequently accessed")
        
        for _ in range(5):
            cm.get_docstring("high_use")
        
        evicted = cm._evict_lru(count=1)
        
        assert evicted == 1
        assert cm.get_docstring("high_use") is not None
        data = cm.load()
        assert "low_use" not in data.get("docs", {})

    def test_eviction_count_on_package_change(self, cache_module, tmp_path):
        cache_file = tmp_path / "evict_count_test.json"
        cm = cache_module.CacheManager(cache_file)
        
        cm.update_packages([("pkg1", "1.0")])
        cm.set_docstring("func1", "doc1")
        cm.set_docstring("func2", "doc2")
        cm.set_docstring("func3", "doc3")
        cm.save()
        
        initial_evictions = cm.get_stats()["evictions"]
        
        cm.update_packages([("pkg1", "2.0")])
        cm.save()
        
        stats = cm.get_stats()
        assert stats["evictions"] == initial_evictions + 3
        assert stats["docstring_count"] == 0

    def test_corrupted_json_recovery(self, cache_module, tmp_path):
        cache_file = tmp_path / "corrupted.json"
        cache_file.write_text("{ invalid json }")
        
        cm = cache_module.CacheManager(cache_file)
        data = cm.load()
        
        assert data["version"] == "2"
        assert data["docs"] == {}

    def test_version_migration(self, cache_module, tmp_path):
        cache_file = tmp_path / "old_version.json"
        old_cache = {
            "version": "1",
            "docstrings": {"old": "data"},
        }
        cache_file.write_text(json.dumps(old_cache))
        
        cm = cache_module.CacheManager(cache_file)
        data = cm.load()
        
        assert data["version"] == "2"
        assert "old" not in data.get("docs", {})

    def test_docstring_invalidation_on_package_version_change(self, cache_module, tmp_path):
        cache_file = tmp_path / "version_change.json"
        cm = cache_module.CacheManager(cache_file)
        
        cm.update_packages([("mypackage", "1.0.0")])
        cm.set_docstring("mypackage.func", "old docs", "mypackage", "1.0.0")
        cm.save()
        
        assert cm.get_docstring("mypackage.func") == "old docs"
        
        cm.update_packages([("mypackage", "2.0.0")])
        cm.save()
        
        cm2 = cache_module.CacheManager(cache_file)
        cm2.update_packages([("mypackage", "2.0.0")])
        
        result = cm2.get_docstring("mypackage.func")
        assert result is None

    def test_hit_count_starts_at_zero(self, cache_manager):
        cache_manager.set_docstring("new_entry", "content")
        data = cache_manager.load()
        assert data["docs"]["new_entry"]["hit_count"] == 0

    def test_set_and_get_doc_structured(self, cache_manager):
        cache_manager.update_packages([("test", "1.0.0")])
        structured_doc = {"name": "test.func", "found": True, "signature": "test()"}
        cache_manager.set_doc("test.func", structured_doc, "test", "1.0.0")
        cache_manager.save()
        
        result = cache_manager.get_doc("test.func")
        assert isinstance(result, dict)
        assert result["name"] == "test.func"
        assert result["found"] is True

    def test_get_doc_returns_string_for_raw(self, cache_manager):
        cache_manager.update_packages([("test", "1.0.0")])
        cache_manager.set_doc("test.raw", "raw documentation string", "test", "1.0.0")
        cache_manager.save()
        
        result = cache_manager.get_doc("test.raw")
        assert isinstance(result, str)
        assert result == "raw documentation string"

    def test_is_structured_flag(self, cache_manager):
        cache_manager.set_doc("dict_entry", {"key": "value"})
        cache_manager.set_doc("str_entry", "string value")
        cache_manager.save()
        
        data = cache_manager.load()
        assert data["docs"]["dict_entry"]["is_structured"] is True
        assert data["docs"]["str_entry"]["is_structured"] is False


class TestDocLookupWithCache:
    @pytest.fixture
    def cache_module(self):
        return load_module_from_path("cache", SCRIPTS_DIR / "cache.py")
    
    @pytest.fixture
    def doc_module(self):
        return load_module_from_path("doc_lookup", SCRIPTS_DIR / "doc_lookup.py")
    
    def test_cache_hit_returns_cached_content(self, cache_module, doc_module, tmp_path, monkeypatch):
        cache_file = tmp_path / "doc_cache.json"
        
        monkeypatch.setattr(cache_module, "CACHE_FILE", cache_file)
        
        cm = cache_module.CacheManager(cache_file)
        cm.set_docstring("str", "CACHED: This is from cache")
        cm.save()
        
        cm2 = cache_module.CacheManager(cache_file)
        result = cm2.get_docstring("str")
        
        assert result == "CACHED: This is from cache"

    def test_structured_docs_are_cached(self, cache_module, doc_module, tmp_path, monkeypatch):
        cache_file = tmp_path / "structured_cache.json"
        
        original_cache_file = cache_module.CACHE_FILE
        cache_module.CACHE_FILE = cache_file
        
        try:
            result1 = doc_module.get_local_docs("json.dumps", use_cache=True, structured=True)
            assert isinstance(result1, dict)
            assert result1["found"] is True
            
            assert cache_file.exists(), f"Cache file should be created at {cache_file}"
            
            cm = cache_module.CacheManager(cache_file)
            cached = cm.get_doc("json.dumps")
            assert cached is not None, "json.dumps should be cached"
            assert isinstance(cached, dict)
            assert cached["found"] is True
        finally:
            cache_module.CACHE_FILE = original_cache_file

    def test_raw_docs_are_cached(self, cache_module, doc_module, tmp_path, monkeypatch):
        cache_file = tmp_path / "raw_cache.json"
        
        original_cache_file = cache_module.CACHE_FILE
        cache_module.CACHE_FILE = cache_file
        
        try:
            result1 = doc_module.get_local_docs("str", use_cache=True, structured=False)
            assert isinstance(result1, str)
            
            cm = cache_module.CacheManager(cache_file)
            cached = cm.get_doc("str")
            assert cached is not None
            assert isinstance(cached, str)
        finally:
            cache_module.CACHE_FILE = original_cache_file


class TestCodeAnalyzerEdgeCases:
    @pytest.fixture
    def module(self):
        return load_module_from_path("code_analyzer", SCRIPTS_DIR / "code_analyzer.py")
    
    def test_empty_source(self, module):
        result = module.analyze_source("")
        assert isinstance(result, dict)
        assert "summary" in result
    
    def test_complex_source(self, module):
        source = '''
from typing import List

@decorator
def func(x: int, y: str = "default") -> List[str]:
    """Docstring."""
    return [y] * x
'''
        result = module.analyze_source(source)
        assert isinstance(result, dict)
        assert "functions" in result
        assert result["functions"][0]["name"] == "func"
