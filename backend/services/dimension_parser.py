"""
Dimension and physical measurement parser for spoken kiosk utterances.
Extracts structured measurement representations (feet, inches, meters, cm, dimensions)
and provides clear clarification when non-menu physical measurements are detected.
"""

import re
from typing import List, Dict, Any, Optional


DIMENSION_PATTERN = re.compile(
    r"""
    \b
    (?P<val1>\d+(?:\.\d+)?)\s*
    (?P<unit1>feet|foot|ft|meters|meter|m|inches|inch|in|cm|mm|['"])
    (?:\s*(?:by|x|\*)\s*(?P<val2>\d+(?:\.\d+)?)\s*(?P<unit2>feet|foot|ft|meters|meter|m|inches|inch|in|cm|mm|['"])?)?
    (?:\s*(?P<val_sub>\d+(?:\.\d+)?)\s*(?P<unit_sub>inches|inch|in|")?)?
    \b
    """,
    re.IGNORECASE | re.VERBOSE,
)

# Additional compound pattern for phrases like "8 feet 8", "11 feet 8" (colloquial feet + inches shorthand)
COMPOUND_FEET_INCHES_PATTERN = re.compile(
    r"\b(\d+(?:\.\d+)?)\s*(?:feet|foot|ft|')\s*(\d+(?:\.\d+)?)\s*(?:inches|inch|in|\")?\b",
    re.IGNORECASE,
)

STANDALONE_UNIT_PATTERN = re.compile(
    r"\b(\d+(?:\.\d+)?)\s*(feet|foot|ft|inches|inch|in|meters|meter|cm|mm)\b",
    re.IGNORECASE,
)


def parse_spoken_dimensions(text: str) -> List[Dict[str, Any]]:
    """
    Parses spoken utterances into structured measurement representations.
    Returns a list of structured measurement dictionaries if found, otherwise empty list.

    Example inputs:
    - "8 feet 8, 11 feet 8." -> [
        {"raw": "8 feet 8", "feet": 8.0, "inches": 8.0, "unit": "feet_inches"},
        {"raw": "11 feet 8", "feet": 11.0, "inches": 8.0, "unit": "feet_inches"}
      ]
    - "12 inches" -> [{"raw": "12 inches", "value": 12.0, "unit": "inches"}]
    - "8 by 10 feet" -> [{"raw": "8 by 10 feet", "dimension_1": 8.0, "dimension_2": 10.0, "unit": "feet"}]
    """
    if not text or not isinstance(text, str):
        return []

    results: List[Dict[str, Any]] = []
    seen_spans = set()

    # 1. Match compound feet + inches (e.g. "8 feet 8", "11 feet 8")
    for m in COMPOUND_FEET_INCHES_PATTERN.finditer(text):
        span = m.span()
        if any(s[0] <= span[0] and span[1] <= s[1] for s in seen_spans):
            continue
        feet_val = float(m.group(1))
        inches_val = float(m.group(2))
        results.append({
            "raw": m.group(0),
            "feet": feet_val,
            "inches": inches_val,
            "unit": "feet_inches",
            "span": span,
        })
        seen_spans.add(span)

    # 2. Match standard dimensions (e.g. "12 inches", "5 meters", "8 feet")
    for m in STANDALONE_UNIT_PATTERN.finditer(text):
        span = m.span()
        if any(s[0] <= span[0] and span[1] <= s[1] for s in seen_spans):
            continue
        val = float(m.group(1))
        unit = m.group(2).lower()
        if unit in ("feet", "foot", "ft"):
            canonical_unit = "feet"
        elif unit in ("inches", "inch", "in"):
            canonical_unit = "inches"
        elif unit in ("meters", "meter", "m"):
            canonical_unit = "meters"
        elif unit == "cm":
            canonical_unit = "centimeters"
        elif unit == "mm":
            canonical_unit = "millimeters"
        else:
            canonical_unit = unit

        results.append({
            "raw": m.group(0),
            "value": val,
            "unit": canonical_unit,
            "span": span,
        })
        seen_spans.add(span)

    return results


def is_dimension_query(text: str) -> bool:
    """Check if an utterance contains physical dimension or measurement specifications."""
    return len(parse_spoken_dimensions(text)) > 0


def build_dimension_clarification_response(dimensions: List[Dict[str, Any]], current_screen: Optional[str] = None) -> str:
    """
    Produces a concise, polite clarifying question when customer speaks measurements,
    grounding the answer in the restaurant menu reality without inventing products,
    prices, or quantities.
    """
    return (
        "We don't offer items by dimensions or physical measurements. "
        "Were you looking for a burger, beverage, side, or dessert from our menu?"
    )
