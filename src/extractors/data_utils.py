import json
import logging
import os
import re
from typing import Any, Dict, Iterable, List, Optional, Tuple

logger = logging.getLogger(__name__)

def read_urls_from_file(path: str) -> List[str]:
    """
    Read input URLs from a text file.

    Lines starting with '#' or empty lines are ignored.
    """
    if not os.path.exists(path):
        logger.warning("Input file %s does not exist.", path)
        return []

    urls: List[str] = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            raw = line.strip()
            if not raw or raw.startswith("#"):
                continue
            urls.append(raw)
    return urls

def ensure_directory(path: str) -> None:
    """
    Create directory if it does not exist.
    """
    try:
        os.makedirs(path, exist_ok=True)
    except OSError as exc:
        logger.error("Failed to create directory %s: %s", path, exc)
        raise

_whitespace_re = re.compile(r"\s+", re.UNICODE)

def clean_text(value: Optional[str]) -> Optional[str]:
    """
    Strip whitespace and collapse internal whitespace.
    """
    if value is None:
        return None
    value = value.strip()
    if not value:
        return None
    value = _whitespace_re.sub(" ", value)
    return value

_currency_re = re.compile(
    r"(?P<currency>[A-Z]{3}|[$€£])?\s*(?P<amount>[0-9,]+(?:\.[0-9]+)?)",
    re.UNICODE,
)

def extract_currency_amount(raw: Optional[str]) -> Tuple[Optional[float], Optional[str]]:
    """
    Extract numeric amount and currency from a string such as '5,000,000 USD' or '$5,000,000'.
    """
    if not raw:
        return None, None
    match = _currency_re.search(raw)
    if not match:
        return None, None
    amount_str = match.group("amount").replace(",", "")
    try:
        amount = float(amount_str)
    except ValueError:
        amount = None

    currency = match.group("currency")
    if currency in ("$", "€", "£"):
        # Map common symbols to ISO-ish codes
        symbol_map = {"$": "USD", "€": "EUR", "£": "GBP"}
        currency = symbol_map.get(currency, currency)
    return amount, currency

def parse_int_safe(raw: Any) -> Optional[int]:
    """
    Safely parse an integer from raw input.
    """
    if raw is None:
        return None
    if isinstance(raw, int):
        return raw
    try:
        return int(str(raw).replace(",", "").strip())
    except (ValueError, TypeError):
        logger.debug("Failed to parse int from %r", raw)
        return None

def parse_float_safe(raw: Any) -> Optional[float]:
    """
    Safely parse a float from raw input.
    """
    if raw is None:
        return None
    if isinstance(raw, (int, float)):
        return float(raw)
    try:
        return float(str(raw).replace(",", "").strip())
    except (ValueError, TypeError):
        logger.debug("Failed to parse float from %r", raw)
        return None

def safe_get(d: Dict[str, Any], *keys: str) -> Any:
    """
    Nested dictionary get: safe_get(obj, 'a', 'b') == obj.get('a', {}).get('b').
    """
    cur: Any = d
    for key in keys:
        if not isinstance(cur, dict):
            return None
        cur = cur.get(key)
    return cur

def merge_dicts(primary: Dict[str, Any], secondary: Dict[str, Any]) -> Dict[str, Any]:
    """
    Merge two dictionaries, preferring non-null values from primary.
    Secondary provides only fields that are missing or null in primary.
    """
    result: Dict[str, Any] = dict(primary)
    for key, value in secondary.items():
        if key not in result or result[key] is None:
            result[key] = value
    return result

def to_serializable(obj: Any) -> Any:
    """
    Convert non-serializable objects to JSON-serializable forms.
    """
    try:
        json.dumps(obj)
        return obj
    except TypeError:
        if isinstance(obj, set):
            return list(obj)
        if hasattr(obj, "__dict__"):
            return obj.__dict__
        return str(obj)

def normalize_list(value: Any) -> List[Any]:
    """
    Ensure the returned value is a list; wrap scalars, return [] for None.
    """
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, (tuple, set)):
        return list(value)
    return [value]

def flatten(iterables: Iterable[Iterable[Any]]) -> List[Any]:
    """
    Flatten a list of iterables into a single list.
    """
    return [item for sub in iterables for item in sub]