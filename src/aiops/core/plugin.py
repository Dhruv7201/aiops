"""Simple plugin registry for extensibility."""

from __future__ import annotations

from typing import Any, TypeVar, Callable

T = TypeVar("T")


class PluginRegistry:
    """Registry that maps string keys to factory callables."""

    def __init__(self, name: str) -> None:
        self.name = name
        self._plugins: dict[str, Callable[..., Any]] = {}

    def register(self, key: str, factory: Callable[..., Any]) -> None:
        self._plugins[key] = factory

    def get(self, key: str) -> Callable[..., Any]:
        if key not in self._plugins:
            available = ", ".join(sorted(self._plugins))
            raise KeyError(
                f"Unknown {self.name} plugin '{key}'. Available: {available}"
            )
        return self._plugins[key]

    def create(self, key: str, *args: Any, **kwargs: Any) -> Any:
        return self.get(key)(*args, **kwargs)

    def keys(self) -> list[str]:
        return list(self._plugins.keys())

    def __contains__(self, key: str) -> bool:
        return key in self._plugins
