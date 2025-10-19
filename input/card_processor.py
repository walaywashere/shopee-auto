"""Card input parsing and validation logic."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from datetime import datetime
from typing import Any, Dict, List, Tuple

from utils.helpers import log_error, log_info

CardData = Dict[str, Any]


def _passes_luhn(number: str) -> bool:
    """Return True when the card number satisfies the Luhn checksum."""
    if not number or not number.isdigit():
        return False

    total = 0
    double = False
    for digit_char in reversed(number):
        digit = ord(digit_char) - 48
        if double:
            digit *= 2
            if digit > 9:
                digit -= 9
        total += digit
        double = not double
    return total % 10 == 0


def _parse_card_line(line: str) -> Tuple[bool, CardData]:
    """Parse a single card line into its components."""
    parts = [segment.strip() for segment in line.split("|")]
    if len(parts) != 4:
        return False, {"error": "Invalid format", "raw": line}

    number, mm, yy, cvv = parts
    card: CardData = {
        "number": number,
        "mm": mm,
        "yy": yy,
        "cvv": cvv,
        "raw": line,
        "retry_count": 0,
        "status": None,
        "error": None,
    }
    return True, card


def read_cards_from_file(filepath: str) -> List[CardData]:
    """Read raw card entries from disk."""
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"Card file not found: {filepath}")

    log_info(f"Loading cards from {filepath}")
    cards: List[CardData] = []

    with open(filepath, "r", encoding="utf-8") as file:
        for line_number, raw_line in enumerate(file, start=1):
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            ok, card = _parse_card_line(line)
            if not ok:
                log_error(f"Line {line_number}: {card['error']}")
                continue
            card["line_number"] = line_number
            cards.append(card)

    return cards


def validate_card(card: CardData) -> bool:
    """Validate a parsed card entry."""
    number = card.get("number", "")
    if not number.isdigit() or len(number) != 16:
        card["error"] = "Card number must be 16 digits"
        return False
    if not _passes_luhn(number):
        card["error"] = "Card number failed Luhn check"
        return False

    mm = card.get("mm", "")
    if len(mm) != 2 or not mm.isdigit() or not 1 <= int(mm) <= 12:
        card["error"] = "Invalid month"
        return False

    yy = card.get("yy", "")
    if len(yy) != 2 or not yy.isdigit():
        card["error"] = "Invalid year"
        return False

    current_year = datetime.utcnow().year % 100
    if int(yy) < current_year:
        card["error"] = "Card year already expired"
        return False

    cvv = card.get("cvv", "")
    if not cvv.isdigit() or len(cvv) not in (3, 4):
        card["error"] = "Invalid CVV"
        return False

    card["error"] = None
    return True


def build_card_queue(filepath: str) -> List[CardData]:
    """Build a validated card queue from file input."""
    raw_cards = read_cards_from_file(filepath)
    queue: List[CardData] = []

    for card in raw_cards:
        if validate_card(card):
            queue.append(card)
        else:
            log_error(f"Skipping invalid card on line {card.get('line_number')}: {card.get('error')}")

    log_info(f"Validated {len(queue)} cards out of {len(raw_cards)}")
    return queue


def format_card_string(card: CardData) -> str:
    """Return canonical string representation for logging/output."""
    return f"{card['number']}|{card['mm']}|{card['yy']}|{card['cvv']}"


def remove_card_from_file(filepath: str, raw_entry: str) -> None:
    """Remove the first occurrence of the raw card entry from the source file."""
    if not raw_entry:
        return

    source_path = Path(filepath)
    if not source_path.exists():
        return

    normalized = raw_entry.strip()
    if not normalized:
        return

    tmp_fd, tmp_path = tempfile.mkstemp(dir=str(source_path.parent))
    removed = False
    try:
        with os.fdopen(tmp_fd, "w", encoding="utf-8", newline="") as tmp_file, source_path.open(
            "r", encoding="utf-8", newline=""
        ) as src_file:
            for line in src_file:
                if not removed and line.strip() == normalized:
                    removed = True
                    continue
                tmp_file.write(line)

        if removed:
            os.replace(tmp_path, source_path)
        else:
            os.remove(tmp_path)
    except Exception:
        # Ensure temp file is removed on any unexpected error
        try:
            os.remove(tmp_path)
        except FileNotFoundError:
            pass
        raise
