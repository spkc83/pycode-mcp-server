"""Caching layer for Python Code Assistant skill.

Provides JSON-based caching for documentation lookups and environment inspection.
Supports both structured (dict) and raw (string) documentation formats.
Uses only stdlib modules (json, hashlib, pathlib).
"""

from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

CACHE_FILE = Path(__file__).parent.parent / "references" / "local_docs_index.json"
CACHE_VERSION = "2"
MAX_DOCSTRING_ENTRIES = 500


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _compute_packages_hash(packages: List[Tuple[str, str]]) -> str:
    sorted_pkgs = sorted(packages)
    content = json.dumps(sorted_pkgs, sort_keys=True)
    return hashlib.sha256(content.encode()).hexdigest()[:16]


class CacheManager:
    def __init__(self, cache_path: Optional[Path] = None):
        self.cache_path = cache_path or CACHE_FILE
        self._data: Optional[Dict[str, Any]] = None

    def load(self) -> Dict[str, Any]:
        if self._data is not None:
            return self._data
        
        data: Dict[str, Any]
        if self.cache_path.exists():
            try:
                with open(self.cache_path, "r", encoding="utf-8") as f:
                    loaded = json.load(f)
                    if loaded.get("version") != CACHE_VERSION:
                        data = self._empty_cache()
                    else:
                        data = loaded
            except (json.JSONDecodeError, KeyError):
                data = self._empty_cache()
        else:
            data = self._empty_cache()
        
        self._data = data
        return data

    def _empty_cache(self) -> Dict[str, Any]:
        return {
            "version": CACHE_VERSION,
            "created_at": _now_iso(),
            "updated_at": _now_iso(),
            "environment": {
                "python_version": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
                "packages_hash": None,
                "packages_count": 0,
                "cached_at": None,
            },
            "packages": {},
            "docs": {},
            "stats": {
                "cache_hits": 0,
                "cache_misses": 0,
                "evictions": 0,
            },
        }

    def save(self) -> None:
        if self._data is None:
            return
        
        self._data["updated_at"] = _now_iso()
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        
        tmp_path = self.cache_path.with_suffix(".tmp")
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(self._data, f, indent=2)
        tmp_path.replace(self.cache_path)

    def get_packages_hash(self) -> Optional[str]:
        cache = self.load()
        return cache.get("environment", {}).get("packages_hash")

    def update_packages(self, packages: List[Tuple[str, str]]) -> str:
        cache = self.load()
        new_hash = _compute_packages_hash(packages)
        old_hash = cache["environment"].get("packages_hash")
        
        if old_hash != new_hash:
            evicted_count = len(cache.get("docs", {}))
            cache["docs"] = {}
            cache["stats"]["evictions"] += evicted_count
        
        cache["environment"]["packages_hash"] = new_hash
        cache["environment"]["packages_count"] = len(packages)
        cache["environment"]["cached_at"] = _now_iso()
        
        cache["packages"] = {name: {"version": ver, "cached_at": _now_iso()} for name, ver in packages}
        
        return new_hash

    def is_packages_stale(self, current_packages: List[Tuple[str, str]]) -> bool:
        current_hash = _compute_packages_hash(current_packages)
        stored_hash = self.get_packages_hash()
        return stored_hash != current_hash

    def get_doc(self, name: str) -> Optional[Union[str, Dict[str, Any]]]:
        """Get cached documentation (structured dict or raw string)."""
        cache = self.load()
        entry = cache.get("docs", {}).get(name)
        
        if entry is None:
            cache["stats"]["cache_misses"] += 1
            return None
        
        pkg = entry.get("package")
        cached_ver = entry.get("package_version")
        current_ver = cache.get("packages", {}).get(pkg, {}).get("version")
        
        if pkg and current_ver is not None and cached_ver != current_ver:
            del cache["docs"][name]
            cache["stats"]["cache_misses"] += 1
            return None
        
        entry["hit_count"] = entry.get("hit_count", 0) + 1
        cache["stats"]["cache_hits"] += 1
        return entry.get("content")

    def set_doc(
        self, 
        name: str, 
        content: Union[str, Dict[str, Any]], 
        package: Optional[str] = None, 
        version: Optional[str] = None
    ) -> None:
        """Cache documentation (structured dict or raw string)."""
        cache = self.load()
        
        if len(cache.get("docs", {})) >= MAX_DOCSTRING_ENTRIES:
            self._evict_lfu()
        
        cache.setdefault("docs", {})[name] = {
            "package": package,
            "package_version": version,
            "content": content,
            "is_structured": isinstance(content, dict),
            "cached_at": _now_iso(),
            "hit_count": 0,
        }

    def get_docstring(self, name: str) -> Optional[str]:
        """Legacy method for backwards compatibility - returns raw string only."""
        result = self.get_doc(name)
        if isinstance(result, str):
            return result
        return None

    def set_docstring(
        self, 
        name: str, 
        content: str, 
        package: Optional[str] = None, 
        version: Optional[str] = None
    ) -> None:
        """Legacy method for backwards compatibility - stores raw string."""
        self.set_doc(name, content, package, version)

    def _evict_lfu(self, count: int = 50) -> int:
        """Evict least frequently used entries."""
        cache = self.load()
        docs = cache.get("docs", {})
        
        if not docs:
            return 0
        
        sorted_entries = sorted(docs.items(), key=lambda x: x[1].get("hit_count", 0))
        to_remove = [k for k, _ in sorted_entries[:count]]
        
        for key in to_remove:
            del docs[key]
        
        cache["stats"]["evictions"] += len(to_remove)
        return len(to_remove)

    def _evict_lru(self, count: int = 50) -> int:
        """Alias for _evict_lfu for backwards compatibility."""
        return self._evict_lfu(count)

    def clear(self) -> None:
        self._data = self._empty_cache()
        self.save()

    def get_stats(self) -> Dict[str, Any]:
        cache = self.load()
        stats = cache.get("stats", {}).copy()
        stats["docstring_count"] = len(cache.get("docs", {}))
        stats["packages_count"] = cache.get("environment", {}).get("packages_count", 0)
        return stats


def main() -> None:
    import argparse
    
    parser = argparse.ArgumentParser(description="Cache management for Python Code Assistant")
    parser.add_argument("--clear", action="store_true", help="Clear the entire cache")
    parser.add_argument("--stats", action="store_true", help="Show cache statistics")
    parser.add_argument("--path", type=Path, default=CACHE_FILE, help="Path to cache file")
    
    args = parser.parse_args()
    cache = CacheManager(args.path)
    
    if args.clear:
        cache.clear()
        print("Cache cleared.")
    elif args.stats:
        stats = cache.get_stats()
        print(json.dumps(stats, indent=2))
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
