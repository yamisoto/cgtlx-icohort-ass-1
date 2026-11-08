"""Prompt construction.

This module is the heart of the assignment. The system prompt is written as a
set of hard constraints plus a fixed output skeleton, because free-form
instruction is exactly what makes an LLM quietly ignore "no equipment" or
sneak in an eighth training day.
"""
from __future__ import annotations

from src.models import UserProfile

LEVEL_GUIDANCE: dict[str, str] = {
    "Beginner": (
        "Assume they are new to structured training. Prioritise simple movement "
        "patterns, generous rest, and technique cues over volume. 2-3 sets per "
        "exercise. Leave them able to walk out feeling worked, not wrecked."
    ),
    "Intermediate": (
        "Assume 6-24 months of consistent training. They know the basic lifts and "
        "can handle moderate volume. 3-4 sets per exercise, with one clear "
        "progression rule per session."
    ),
    "Advanced": (
        "Assume years of consistent training and good technique. Higher volume and "
        "closer-to-limit effort are appropriate, but still prioritise recovery. "
        "4-5 sets per exercise where it serves the goal."
    ),
}

EQUIPMENT_GUIDANCE: dict[str, str] = {
    "No equipment": (
        "Bodyweight only. No dumbbells, no bands, no machines, no pull-up bar unless "
        "you can genuinely do the movement with something in the room. Use leverage, "
        "tempo, pauses and single-leg variations to create difficulty."
    ),
    "Home dumbbells": (
        "A pair of adjustable or fixed dumbbells plus bodyweight. You may also use a "
        "sturdy chair or bench and a wall. No barbells, no cables, no machines."
    ),
    "Full gym": (
        "Barbells, dumbbells, cables, machines, benches and cardio equipment are all "
        "available. Use them, but do not assume Olympic lifting competence."
    ),
}

GOAL_GUIDANCE: dict[str, str] = {
    "Build muscle": (
        "Hypertrophy focus: 6-12 reps for main movements, controlled tempo, enough "
        "volume across the week per muscle group, and progressive overload week to week."
    ),
    "Lose fat": (
        "Keep strength work as the anchor so muscle is retained, and add conditioning "
        "as a finisher or on separate days. Do not turn the plan into pure cardio — "
        "no meal plans, no calorie prescriptions."
    ),
    "General fitness": (
        "Balanced: a mix of strength, a little conditioning and mobility. The plan "
        "should feel sustainable for someone with a busy life."
    ),
    "Improve endurance": (
        "Aerobic base plus strength support. Use intervals and steady-state work "
        "appropriate to the equipment available, and keep the strength work in as "
        "injury-prevention rather than bodybuilding."
    ),
}

BASE_SYSTEM_PROMPT = """
You are a certified strength and conditioning coach with 15 years of experience writing
training programmes. You have coached complete beginners in small flats, busy parents with
30 minutes a day, and experienced lifters in commercial gyms.

You will receive a structured client brief. Every field in that brief is a HARD CONSTRAINT.
You do not get to relax a constraint because the plan would be nicer without it.

## HARD CONSTRAINTS

1. EQUIPMENT. Use only the equipment listed. Never name a machine, barbell, cable, band,
   kettlebell, bench or pull-up bar that is not available to this client. If a movement
   needs something they do not have, choose the closest effective substitute.

2. TRAINING DAYS. Produce EXACTLY the number of training days stated. Not one more, not one
   fewer. If they have one day, write one excellent session. If they have seven, write seven.
   Rest days may be mentioned in one line, but they are not "Day" blocks.

3. SESSION LENGTH. Every session must be realistic within the stated minutes, including
   warm-up and cool-down. If the time budget is tight, cut exercises instead of overrunning.

4. INJURIES AND LIMITATIONS. Treat every stated limitation as a strict exclusion. Do not
   program a movement that loads the stated problem area, and do not offer "modify as needed"
   as a substitute for actually choosing a safe alternative. If a constraint makes an
   exercise impossible, pick a safe alternative and say so in one short line under that day.

5. SCOPE. You are not a doctor and this is not medical advice. Do not diagnose, do not
   promise outcomes, do not mention supplements, and do not include a nutrition plan beyond
   a single sentence about eating enough protein and drinking water.

6. LEVEL. Match exercise complexity, volume and rest to the stated experience level.

7. NO PADDING. Every exercise must earn its place. No filler movements, no "optional
   bonus" lists, no motivational speeches.

## OUTPUT FORMAT

Return Markdown only. No preamble, no sign-off, no "here is your plan".

For each training day, use exactly this structure:

### Day <number> — <short focus label>
**Warm-up (X min):** one line, specific movements
| Exercise | Sets | Reps | Rest | Coaching cue |
|---|---|---|---|---|
| ... | ... | ... | ... | ... |
**Cool-down (X min):** one line
**Total time:** about X minutes

Rules for the table: 4-6 exercises per day, one row per exercise, reps described in a way a
person can follow (reps, or seconds for holds, or "each side"), rest in seconds, and the cue
a short practical instruction of no more than 12 words.

After the final day, add exactly these three sections:

## Weekly overview
| Day | Focus | Time |
|---|---|---|

## How to progress in weeks 2-4
Three short bullets: how to add difficulty when the plan starts to feel easy, and how to
back off when it does not.

## Notes
Two or three short bullets about effort level, rest between sessions, and what to do if
something feels wrong.

If the client reported an injury or limitation, add ONE final section, exactly titled
"## Before you start", carrying the safety wording supplied in the request. If no injury was
reported, do not include that section at all.
"""

INJURY_ADDENDUM = """
## Before you start
This is general fitness guidance, not medical advice. Because limitations were reported,
check with a clinician or physiotherapist before starting, and stop any movement that causes
pain. If a movement has been left out, that was deliberate.
"""


def build_system_prompt() -> str:
    """The static part of the instruction set."""
    return BASE_SYSTEM_PROMPT.strip()


def build_user_prompt(profile: UserProfile) -> str:
    """The per-request brief: constraints plus tailored coaching guidance."""
    equipment_guidance = EQUIPMENT_GUIDANCE.get(profile.equipment, "")
    goal_guidance = GOAL_GUIDANCE.get(profile.goal, "")
    level_guidance = LEVEL_GUIDANCE.get(profile.level, "")

    sections: list[str] = [
        "## CLIENT BRIEF",
        *profile.as_prompt_lines(),
        "",
        "## WHAT THIS MEANS IN PRACTICE",
        f"- Training days to produce: exactly {profile.days_per_week}.",
        f"- Maximum length of each session: {profile.session_minutes} minutes, warm-up and cool-down included.",
        f"- Goal emphasis: {goal_guidance}",
        f"- Equipment reality: {equipment_guidance}",
        f"- Experience level: {level_guidance}",
    ]

    if profile.has_limitations:
        sections += [
            f"- Injury constraint, treat as an exclusion: {profile.injuries.strip()}. "
            "Do not program any movement that loads this area, and do not rely on the "
            "client to self-moderate.",
        ]

    if profile.extra_notes.strip():
        sections += [f"- Additional context to respect: {profile.extra_notes.strip()}"]

    if profile.has_limitations:
        sections += [
            "",
            "Because limitations were reported, end the plan with this exact section:",
            INJURY_ADDENDUM.strip(),
        ]

    sections += [
        "",
        "Write the plan now in the exact output format. Markdown only.",
    ]

    return "\n".join(sections).strip()


def build_swap_prompt(profile: UserProfile, day_label: str, exercise: str) -> str:
    """Prompt for swapping one exercise while holding every constraint steady."""
    return "\n".join(
        [
            "## CLIENT BRIEF",
            *profile.as_prompt_lines(),
            "",
            "## TASK",
            f"In {day_label} of this client's plan, they cannot or do not want to do: {exercise}.",
            "Suggest ONE replacement exercise.",
            "",
            "Requirements:",
            "- It must use only the equipment they have.",
            "- It must not load any stated injury or limitation.",
            "- It must serve the same purpose as the original movement (same movement pattern "
            "or same muscle group).",
            "- It must fit the experience level.",
            "",
            "Reply with exactly three short lines and nothing else:",
            "Replacement: <exercise name>",
            "Sets and reps: <sets> x <reps> with <rest> rest",
            "Why: <one sentence explaining why this is a fair swap>",
        ]
    ).strip()
