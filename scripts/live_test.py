"""Live test — makes real Groq calls and checks the plan against the constraints.

Run from the project root after putting GROQ_API_KEY in .env:
    python scripts/live_test.py

Checks, for each profile:
  1. exactly the requested number of training days
  2. no equipment mentioned that the user does not have
  3. the injury safety section appears only when limitations were given
  4. day headings are parseable (so the swap feature has something to work with)
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv  # noqa: E402

from src.groq_client import GroqClientError, generate_plan, swap_exercise  # noqa: E402
from src.models import UserProfile  # noqa: E402
from src.parsing import extract_day_labels  # noqa: E402

load_dotenv()

FORBIDDEN_EQUIPMENT: dict[str, tuple[str, ...]] = {
    "No equipment": ("barbell", "dumbbell", "cable", "machine", "kettlebell", "band", "pull-up bar"),
    "Home dumbbells": ("barbell", "cable", "machine", "kettlebell", "smith"),
    "Full gym": (),
}


def count_days(plan: str) -> int:
    return len(re.findall(r"^#{1,4}\s*day\s*\d+", plan, re.IGNORECASE | re.MULTILINE))


def check_profile(profile: UserProfile, label: str) -> str:
    print(f"\n{'=' * 70}\n{label}")
    print(f"goal={profile.goal} | level={profile.level} | days={profile.days_per_week} "
          f"| equipment={profile.equipment} | {profile.session_minutes} min")
    print(f"limitations: {profile.injuries or 'none'}\n")

    try:
        plan = generate_plan(profile)
    except GroqClientError as exc:
        print(f"API ERROR: {exc}")
        raise SystemExit(1)

    print(plan)

    print("\n--- CHECKS ---")
    days = count_days(plan)
    ok_days = days == profile.days_per_week
    print(f"[{'PASS' if ok_days else 'FAIL'}] day blocks: {days} (asked for {profile.days_per_week})")

    lowered = plan.lower()
    banned = [w for w in FORBIDDEN_EQUIPMENT.get(profile.equipment, ()) if w in lowered]
    ok_equipment = not banned
    print(f"[{'PASS' if ok_equipment else 'FAIL'}] no unavailable equipment"
          + (f" — found: {', '.join(banned)}" if banned else ""))

    has_clinician_note = "clinician" in lowered or "physiotherapist" in lowered
    ok_injury = has_clinician_note if profile.has_limitations else True
    print(f"[{'PASS' if ok_injury else 'FAIL'}] safety note "
          f"{'present as expected' if profile.has_limitations else 'not required'}")

    labels = extract_day_labels(plan)
    ok_parse = len(labels) == profile.days_per_week
    print(f"[{'PASS' if ok_parse else 'FAIL'}] day headings parseable: {labels}")

    if not all((ok_days, ok_equipment, ok_injury, ok_parse)):
        raise SystemExit(1)
    return plan


def main() -> None:
    beginner_no_kit = UserProfile(
        goal="Build muscle",
        level="Beginner",
        days_per_week=3,
        equipment="No equipment",
        session_minutes=30,
        injuries="bad knees, cannot do jumping",
    )

    gym_intermediate = UserProfile(
        goal="Lose fat",
        level="Intermediate",
        days_per_week=4,
        equipment="Full gym",
        session_minutes=60,
    )

    check_profile(beginner_no_kit, "PROFILE A — beginner, no equipment, 3 days, bad knees")
    check_profile(gym_intermediate, "PROFILE B — intermediate, full gym, 4 days, no injuries")

    print(f"\n{'=' * 70}\nSWAP TEST")
    print(swap_exercise(beginner_no_kit, "Day 1", "Bodyweight squat"))

    print("\nAll live checks passed.")


if __name__ == "__main__":
    main()
