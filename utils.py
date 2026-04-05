import re

# Shared threshold for spaced-repetition review; used by Dashboard and Next Step.
REVIEW_DAYS = 7


def parse_weak_areas(blob: str) -> list:
    """Split, deduplicate (order-preserving), and return weak area strings.

    Splits on both newlines and commas so that entries stored in either
    format (legacy newline-separated or current comma-separated) are
    handled correctly on every subsequent save.
    """
    seen = set()
    parts = []
    for item in re.split(r"[\n,]+", blob or ""):
        item = item.strip()
        if item and item not in seen:
            seen.add(item)
            parts.append(item)
    return parts
