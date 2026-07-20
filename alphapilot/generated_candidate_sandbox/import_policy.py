"""Import allowlist for generated research candidates."""

from __future__ import annotations


ALLOWED_IMPORT_ROOTS = frozenset({"math", "statistics"})
FORBIDDEN_IMPORT_ROOTS = frozenset(
    {
        "aiohttp",
        "ctypes",
        "ftplib",
        "httpx",
        "multiprocessing",
        "os",
        "pathlib",
        "requests",
        "shutil",
        "smtplib",
        "socket",
        "subprocess",
        "urllib",
    }
)


def validate_import(module_name: str) -> str | None:
    root = module_name.split(".", 1)[0]
    if root in FORBIDDEN_IMPORT_ROOTS:
        return f"forbidden_import:{root}"
    if root not in ALLOWED_IMPORT_ROOTS:
        return f"import_not_allowlisted:{root}"
    return None
