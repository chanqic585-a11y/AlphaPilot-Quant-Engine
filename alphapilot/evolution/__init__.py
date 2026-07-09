"""Versioned, research-only strategy evolution kernel."""

from .registry.database import DEFAULT_REGISTRY_PATH, connect_registry

__all__ = ["DEFAULT_REGISTRY_PATH", "connect_registry"]
