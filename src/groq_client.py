"""Groq API wrapper.

Every failure mode is translated into a GroqClientError with a message that is
safe to show a non-technical user. The UI never sees a raw traceback.
"""
from __future__ import annotations

import os
from typing import Final

from groq import (
    APIConnectionError,
    APIError,
    APIStatusError,
    AuthenticationError,
    Groq,
    RateLimitError,
)

from src.models import UserProfile
from src.prompts import build_swap_prompt, build_system_prompt, build_user_prompt

DEFAULT_MODEL: Final[str] = "openai/gpt-oss-120b"
MAX_TOKENS: Final[int] = 2500


class GroqClientError(RuntimeError):
    """A Groq failure we can explain to the user in one friendly sentence."""


def _model_name() -> str:
    return os.getenv("GROQ_MODEL", DEFAULT_MODEL).strip() or DEFAULT_MODEL


def _get_client() -> Groq:
    api_key = os.getenv("GROQ_API_KEY", "").strip()
    if not api_key:
        raise GroqClientError(
            "No Groq API key found. Create a file called .env next to app.py with "
            "GROQ_API_KEY=your_key_here and restart the app."
        )
    return Groq(api_key=api_key)


def _complete(system_prompt: str, user_prompt: str, temperature: float) -> str:
    """One chat completion, with every failure mapped to a friendly error."""
    client = _get_client()

    try:
        response = client.chat.completions.create(
            model=_model_name(),
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=temperature,
            max_tokens=MAX_TOKENS,
        )
    except AuthenticationError as exc:
        raise GroqClientError(
            "Groq rejected the API key. Check that GROQ_API_KEY in your .env file is "
            "correct and has not been revoked."
        ) from exc
    except RateLimitError as exc:
        raise GroqClientError(
            "Groq is rate limiting this key right now. Wait about a minute and try again."
        ) from exc
    except APIConnectionError as exc:
        raise GroqClientError(
            "Could not reach Groq. Check your internet connection and try again."
        ) from exc
    except APIStatusError as exc:
        raise GroqClientError(
            f"Groq returned an error (status {exc.status_code}). Try again, or switch "
            "GROQ_MODEL to a different model in your .env file."
        ) from exc
    except APIError as exc:
        raise GroqClientError(
            "Groq reported a problem with the request. Try again in a moment."
        ) from exc
    except Exception as exc:  # last resort: never crash the app
        raise GroqClientError(f"Something unexpected went wrong talking to Groq: {exc}") from exc

    if not response.choices:
        raise GroqClientError(
            "The model returned nothing at all. Try generating again, or switch the model."
        )

    content = (response.choices[0].message.content or "").strip()
    if not content:
        raise GroqClientError(
            "The model returned an empty response. Try again — this is usually a "
            "one-off glitch."
        )

    return content


def _looks_like_a_plan(text: str, expected_days: int) -> bool:
    """Loose structural check: we want day headings, not a chatty paragraph."""
    lowered = text.lower()
    if "day 1" not in lowered:
        return False
    if len(text) < 200:
        return False
    # If we asked for 3+ days, at least a couple of day headings should exist.
    if expected_days >= 2 and lowered.count("day ") < 2:
        return False
    return True


def generate_plan(profile: UserProfile, *, variation: int = 0) -> str:
    """Build a weekly plan for a validated profile.

    Args:
        profile: validated user inputs.
        variation: increments on each regenerate so repeat requests differ
            slightly instead of returning the identical plan.

    Raises:
        GroqClientError: for any API or response-shape failure.
    """
    errors = profile.validate()
    if errors:
        raise GroqClientError(" ".join(errors))

    # Small, deliberate temperature variation per regenerate: enough for a
    # different exercise selection, not enough to ignore constraints.
    temperature = min(0.5 + (0.1 * variation), 0.9)

    text = _complete(
        system_prompt=build_system_prompt(),
        user_prompt=build_user_prompt(profile),
        temperature=temperature,
    )

    if not _looks_like_a_plan(text, profile.days_per_week):
        raise GroqClientError(
            "The model replied but not in the plan format we asked for. "
            "Try generating again — if it keeps happening, switch GROQ_MODEL."
        )

    return text


def swap_exercise(profile: UserProfile, day_label: str, exercise: str) -> str:
    """Suggest a single substitute exercise under the same constraints."""
    if not exercise.strip():
        raise GroqClientError("Type the name of the exercise you want to swap out first.")

    return _complete(
        system_prompt=build_system_prompt(),
        user_prompt=build_swap_prompt(profile, day_label, exercise.strip()),
        temperature=0.4,
    )
