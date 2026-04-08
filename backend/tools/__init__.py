"""Tool layer — executor, Kali tool catalog, stealth wrappers."""
from .executor import CommandResult, ShellExecutor, get_executor
from .kali_catalog import KaliToolCatalog, get_catalog

__all__ = [
    "CommandResult",
    "ShellExecutor",
    "get_executor",
    "KaliToolCatalog",
    "get_catalog",
]
