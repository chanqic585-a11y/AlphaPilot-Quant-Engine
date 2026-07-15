"""Static guard for generated formula snippets."""

from __future__ import annotations

import ast


_DYNAMIC_EXECUTION = frozenset({"eval", "exec", "compile"})
_IO_NAMES = frozenset({"open", "input"})


def inspect_generated_source(source: str) -> list[str]:
    try:
        tree = ast.parse(source, mode="exec")
    except SyntaxError:
        return ["invalid_syntax"]
    errors: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            errors.add("dynamic_import_or_import_statement")
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            if node.func.id in _DYNAMIC_EXECUTION:
                errors.add("dynamic_execution")
            if node.func.id == "__import__":
                errors.add("dynamic_import_or_import_statement")
            if node.func.id in _IO_NAMES:
                errors.add("file_or_console_io")
        elif isinstance(node, (ast.Attribute, ast.Subscript, ast.ClassDef, ast.Lambda)):
            errors.add("unsafe_language_feature")
    return sorted(errors)
