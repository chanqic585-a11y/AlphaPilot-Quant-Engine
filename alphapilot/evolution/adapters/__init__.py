"""Adapters for importing existing AlphaPilot research artifacts."""

from .legacy_report_adapter import classify_legacy_payload, load_json_object

__all__ = ["classify_legacy_payload", "load_json_object"]
