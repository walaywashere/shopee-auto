"""Utility helpers for configuration, logging, and async helpers."""

from __future__ import annotations

import asyncio
import json
import os
from typing import Any, Dict

from colorama import Fore, Style, init


init(autoreset=True)

# Global verbose flag
_VERBOSE = False


def set_verbose(enabled: bool) -> None:
    """Enable or disable verbose INFO logging."""
    global _VERBOSE
    _VERBOSE = enabled


def load_config(filepath: str) -> Dict[str, Any]:
    """Load JSON configuration from disk."""
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"Config file not found: {filepath}")
    with open(filepath, "r", encoding="utf-8") as file:
        return json.load(file)


def _format_prefix(prefix: str, color: str) -> str:
    """Format a colorized prefix for log messages."""
    return f"{color}[{prefix}]{Style.RESET_ALL}"


def log_info(message: str) -> None:
    """Print a green informational log message."""
    if _VERBOSE:
        print(f"{_format_prefix('INFO', Fore.GREEN)} {message}")


def log_error(message: str) -> None:
    """Print a red error log message."""
    print(f"{_format_prefix('ERROR', Fore.RED)} {message}")


def log_card_result(index: int, total: int, status: str, card_data: str, reason: str = "") -> None:
    """Print standardized per-card result output."""
    color = Fore.CYAN if status == "[3DS]" else Fore.GREEN if status == "[SUCCESS]" else Fore.RED
    result_line = f"{_format_prefix(f'{index}/{total}', color)} {status} {card_data}"
    if reason:
        result_line += f" - {reason}"
    print(result_line)


def log_summary(summary: Dict[str, Any]) -> None:
    """Print the final run summary using configured formatting."""
    lines = [
        "==================== SUMMARY ====================",
        f"Total Processed: {summary.get('total', 0)}",
        f"Success: {summary.get('success', 0)}",
        f"Failed: {summary.get('failed', 0)}",
        f"3DS: {summary.get('three_ds', 0)}",
        "================================================="
    ]
    print(Fore.MAGENTA + "\n".join(lines) + Style.RESET_ALL)


async def async_sleep(seconds: float) -> None:
    """Asyncio sleep wrapper with cancellation resilience."""
    try:
        await asyncio.sleep(seconds)
    except asyncio.CancelledError:
        log_error("Sleep cancelled; continuing execution.")
