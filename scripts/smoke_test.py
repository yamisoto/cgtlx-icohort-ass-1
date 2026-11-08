"""Offline smoke test — checks validation and prompt construction without any API call.

Run from the project root:
    python scripts/smoke_test.py

This is what I used to iterate on the prompt: it prints the exact user prompt
for several profiles so you can read what the model will actually see.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.models import UserProfile  # noqa: E402
from src.parsing import extract_day_labels  # noqa: E402
from src.prompts import build_system_prompt, build_user_prompt  # noqa: E402


def check(condition: bool, message: str) -> None:
    status = "PASS" if condition else "FAIL"
    print(f"[{status}] {message}")
    if not condition:
        raise SystemExit(1)


def main() -> None:
    print("=== Validation ===")
    bad = UserProfile(
        goal="Build muscle",
        level="Beginner",
        days_per_week=0,
        equipment="No equipment",
        session_minutes=45,
    )
    check(bool(bad.validate()), "zero training days is rejected with a message")

    good = UserProfile(
        goal="Build muscle",
        level="Beginner",
        days_per_week=3,
        equipment="No equipment",
        session_minutes=45,
        injuries="bad knees",
    )
    check(not good.validate(), "a valid profile passes validation")

    print("\n=== Constraints appear in the prompt ===")
    prompt = build_user_prompt(good)
    check("exactly 3" in prompt, "days per week is stated as an explicit number")
    check("bad knees" in prompt, "the injury is carried into the prompt")
    check("Bodyweight only" in prompt, "equipment guidance matches 'No equipment'")
    check("45 minutes" in prompt, "session length is stated")

    print("\n=== Injury addendum is conditional ===")
    no_injury = UserProfile(
        goal="Lose fat",
        level="Intermediate",
        days_per_week=4,
        equipment="Full gym",
        session_minutes=60,
    )
    check("Injuries or limitations: none reported" in build_user_prompt(no_injury),
          "a profile without injuries says so explicitly")

    print("\n=== System prompt has the hard rules ===")
    system = build_system_prompt()
    for phrase in ("HARD CONSTRAINTS", "OUTPUT FORMAT", "Weekly overview", "not medical advice"):
        check(phrase in system, f"system prompt contains '{phrase}'")

    print("\n=== Day parsing ===")
    sample = "### Day 1 — Lower body\n| a | b |\n### Day 2 — Upper body\n"
    check(extract_day_labels(sample) == ["Day 1", "Day 2"], "day headings are extracted in order")
    check(extract_day_labels("no headings here") == [], "a plan without headings returns nothing")

    print("\n=== Sample user prompt (what the model receives) ===")
    print(prompt)

    print("\nAll offline checks passed.")


if __name__ == "__main__":
    main()
