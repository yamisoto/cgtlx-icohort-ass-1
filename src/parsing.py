"""Small helpers for reading the generated plan back."""
from __future__ import annotations

import re

_DAY_PATTERN = re.compile(r"^#{1,4}\s*(day\s*\d+)", re.IGNORECASE | re.MULTILINE)


def extract_day_labels(plan: str) -> list[str]:
    """Return day headings found in a plan, e.g. ['Day 1', 'Day 2'].

    Used to populate the exercise-swap dropdown. Falls back to an empty list
    when the plan has no recognisable day headings.
    """
    labels: list[str] = []
    for match in _DAY_PATTERN.finditer(plan):
        label = " ".join(match.group(1).split()).title()
        if label not in labels:
            labels.append(label)
    return labels
