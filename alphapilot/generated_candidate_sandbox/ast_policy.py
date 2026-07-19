"""Whole-module AST policy for generated candidate source."""

from __future__ import annotations

import ast

from .audit import SourceAudit
from .import_policy import validate_import


FORBIDDEN_CALLS = frozenset(
    {
        "__import__",
        "compile",
        "eval",
        "exec",
        "open",
        "os.getenv",
        "os.popen",
        "os.system",
        "subprocess.call",
        "subprocess.check_call",
        "subprocess.check_output",
        "subprocess.Popen",
        "subprocess.run",
    }
)
FORBIDDEN_METHODS = frozenset(
    {
        "connect",
        "execv",
        "execve",
        "popen",
        "read_bytes",
        "read_text",
        "replace",
        "send",
        "sendall",
        "spawnl",
        "spawnle",
        "spawnlp",
        "spawnlpe",
        "spawnv",
        "spawnve",
        "spawnvp",
        "spawnvpe",
        "unlink",
        "write_bytes",
        "write_text",
    }
)


def _call_name(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        prefix = _call_name(node.value)
        return f"{prefix}.{node.attr}" if prefix else node.attr
    return ""


def inspect_candidate_source(source: str) -> SourceAudit:
    try:
        tree = ast.parse(source, mode="exec")
    except SyntaxError as exc:
        return SourceAudit(
            passed=False,
            reasons=(f"syntax_error:{exc.lineno or 0}",),
            imports=(),
            calls=(),
        )

    reasons: set[str] = set()
    imports: set[str] = set()
    calls: set[str] = set()
    aliases: dict[str, str] = {}
    generate_found = False

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == "generate":
            generate_found = True
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.add(alias.name)
                aliases[alias.asname or alias.name.split(".", 1)[0]] = alias.name
                reason = validate_import(alias.name)
                if reason:
                    reasons.add(reason)
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            imports.add(module)
            reason = validate_import(module)
            if reason:
                reasons.add(reason)
            for alias in node.names:
                aliases[alias.asname or alias.name] = f"{module}.{alias.name}"
        elif isinstance(node, ast.Attribute) and node.attr.startswith("__"):
            reasons.add(f"forbidden_dunder_attribute:{node.attr}")
        elif isinstance(node, ast.Call):
            raw_name = _call_name(node.func)
            root, separator, remainder = raw_name.partition(".")
            resolved = aliases.get(root, root)
            name = f"{resolved}.{remainder}" if separator else resolved
            calls.add(name)
            if name in FORBIDDEN_CALLS:
                reasons.add(f"forbidden_call:{name}")
            elif name.split(".")[-1] in FORBIDDEN_METHODS:
                reasons.add(f"forbidden_call:{name}")

    if not generate_found:
        reasons.add("missing_generate_function")
    return SourceAudit(
        passed=not reasons,
        reasons=tuple(sorted(reasons)),
        imports=tuple(sorted(imports)),
        calls=tuple(sorted(calls)),
    )
