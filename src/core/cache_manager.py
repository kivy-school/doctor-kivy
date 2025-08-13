# filepath: /kivy-discord-bot/kivy-discord-bot/src/core/cache_manager.py

import os
import json
from pathlib import Path
from typing import Any, Dict

class CacheManager:
    def __init__(self, cache_dir: str = './cache'):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _get_cache_file_path(self, key: str) -> Path:
        return self.cache_dir / f"{key}.json"

    def get(self, key: str) -> Any:
        cache_file = self._get_cache_file_path(key)
        if cache_file.exists():
            with open(cache_file, 'r') as f:
                return json.load(f)
        return None

    def set(self, key: str, value: Any) -> None:
        cache_file = self._get_cache_file_path(key)
        with open(cache_file, 'w') as f:
            json.dump(value, f)

    def clear(self, key: str) -> None:
        cache_file = self._get_cache_file_path(key)
        if cache_file.exists():
            os.remove(cache_file)

    def clear_all(self) -> None:
        for cache_file in self.cache_dir.iterdir():
            if cache_file.is_file():
                os.remove(cache_file)