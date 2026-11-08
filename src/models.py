"""Typed input model for the workout plan generator.

Keeping the inputs in one dataclass means the UI, the validation and the
prompt builder all speak the same language, and the prompt can never receive
a field that was never validated.
"""
from __future__ import annotations

from dataclasses import dataclass

Goal = str
Level = str
Equipment = str

GOAL_OPTIONS: tuple[str, ...] = (
    "Build muscle",
    "Lose fat",
    "General fitness",
    "Improve endurance",
)

LEVEL_OPTIONS: tuple[str, ...] = ("Beginner", "Intermediate", "Advanced")

EQUIPMENT_OPTIONS: tuple[str, ...] = (
    "No equipment",
    "Home dumbbells",
    "Full gym",
)

SESSION_LENGTHS: tuple[int, ...] = (30, 45, 60, 90)

MIN_DAYS = 1
MAX_DAYS = 7


@dataclass(frozen=True)
class UserProfile:
    """Everything the model needs to know about the person asking."""

    goal: Goal
    level: Level
    days_per_week: int
    equipment: Equipment
    session_minutes: int
    injuries: str = ""
    extra_notes: str = ""

    def validate(self) -> list[str]:
        """Return a list of human-readable problems. Empty list means valid.

        This is deliberately forgiving about the free-text fields: someone
        writing "bad knees" is fine, silence is fine, we only reject things
        that would actually produce a nonsense plan.
        """
        errors: list[str] = []

        if self.goal not in GOAL_OPTIONS:
            errors.append("Please choose one of the listed fitness goals.")

        if self.level not in LEVEL_OPTIONS:
            errors.append("Please choose one of the listed experience levels.")

        if self.equipment not in EQUIPMENT_OPTIONS:
            errors.append("Please choose one of the listed equipment options.")

        if not isinstance(self.days_per_week, int):
            errors.append("Days per week must be a whole number.")
        elif self.days_per_week < MIN_DAYS:
            errors.append(
                "You need at least 1 day per week for a plan to be useful. "
                "Pick a number between 1 and 7."
            )
        elif self.days_per_week > MAX_DAYS:
            errors.append("A week only has 7 days — please choose 7 or fewer.")

        if self.session_minutes < 15:
            errors.append("Sessions under 15 minutes are too short to build a plan around.")

        if len(self.injuries) > 500 or len(self.extra_notes) > 500:
            errors.append("Please keep the notes fields under 500 characters.")

        return errors

    def as_prompt_lines(self) -> list[str]:
        """Render the profile as a clean key/value brief for the model."""
        lines = [
            f"- Fitness goal: {self.goal}",
            f"- Experience level: {self.level}",
            f"- Training days available per week: {self.days_per_week}",
            f"- Equipment access: {self.equipment}",
            f"- Time available per session: {self.session_minutes} minutes",
        ]

        injuries = self.injuries.strip()
        lines.append(
            f"- Injuries or limitations: {injuries}" if injuries else "- Injuries or limitations: none reported"
        )

        notes = self.extra_notes.strip()
        if notes:
            lines.append(f"- Other context: {notes}")

        return lines

    @property
    def has_limitations(self) -> bool:
        return bool(self.injuries.strip())
