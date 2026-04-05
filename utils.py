def parse_weak_areas(blob: str) -> list:
    """Split, deduplicate (order-preserving), and return weak area strings."""
    seen = set()
    parts = []
    for item in (blob or "").replace(",", "\n").split("\n"):
        item = item.strip()
        if item and item not in seen:
            seen.add(item)
            parts.append(item)
    return parts
