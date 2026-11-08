"""Workout Plan Generator — single-page Streamlit app.

Run:
    streamlit run app.py

The UI only collects and validates inputs. All prompt construction and all
API calls live in src/, so the interesting logic is testable on its own.
"""
from __future__ import annotations

from datetime import date

import streamlit as st
from dotenv import load_dotenv

from src.groq_client import GroqClientError, generate_plan, swap_exercise
from src.models import (
    EQUIPMENT_OPTIONS,
    GOAL_OPTIONS,
    LEVEL_OPTIONS,
    SESSION_LENGTHS,
    UserProfile,
)
from src.parsing import extract_day_labels
from src.prompts import build_swap_prompt, build_system_prompt, build_user_prompt

load_dotenv()

st.set_page_config(
    page_title="Workout Plan Generator",
    page_icon=None,
    layout="centered",
)


def init_state() -> None:
    """Seed session state once so a generated plan survives widget reruns."""
    st.session_state.setdefault("plan", "")
    st.session_state.setdefault("profile", None)
    st.session_state.setdefault("variation", 0)
    st.session_state.setdefault("swap_result", "")


def collect_inputs() -> UserProfile:
    """Render the structured inputs and return them as a typed profile."""
    st.subheader("Tell me about yourself")

    col_left, col_right = st.columns(2)

    with col_left:
        goal = st.selectbox("Fitness goal", GOAL_OPTIONS, index=0)
        days_per_week = st.slider(
            "Days available per week",
            min_value=1,
            max_value=7,
            value=3,
            help="Training days, not calendar days. Rest days are woven around them.",
        )

    with col_right:
        level = st.selectbox("Experience level", LEVEL_OPTIONS, index=0)
        equipment = st.selectbox("Equipment access", EQUIPMENT_OPTIONS, index=0)

    session_minutes = st.selectbox(
        "Time per session",
        SESSION_LENGTHS,
        index=1,
        format_func=lambda minutes: f"{minutes} minutes",
    )

    with st.expander("Injuries, limitations or anything else I should know"):
        injuries = st.text_area(
            "Injuries or limitations",
            placeholder="e.g. bad knees, no overhead pressing, lower back pain when bending",
            max_chars=500,
            height=80,
        )
        extra_notes = st.text_area(
            "Anything else",
            placeholder="e.g. training at home in a small flat, hate running, prefer morning sessions",
            max_chars=500,
            height=80,
        )

    return UserProfile(
        goal=goal,
        level=level,
        days_per_week=days_per_week,
        equipment=equipment,
        session_minutes=session_minutes,
        injuries=injuries,
        extra_notes=extra_notes,
    )


def render_plan(plan: str) -> None:
    """Show the plan, plus download and swap controls."""
    st.divider()
    st.subheader("Your plan")
    st.markdown(plan)

    download_col, swap_col = st.columns([1, 1])
    with download_col:
        st.download_button(
            "Download as Markdown",
            data=plan,
            file_name=f"workout-plan-{date.today().isoformat()}.md",
            mime="text/markdown",
            use_container_width=True,
        )
    with swap_col:
        st.download_button(
            "Download as text",
            data=plan.replace("##", "").replace("|", " ").replace("**", ""),
            file_name=f"workout-plan-{date.today().isoformat()}.txt",
            mime="text/plain",
            use_container_width=True,
        )

    with st.expander("Swap one exercise"):
        day_labels = extract_day_labels(plan)
        if not day_labels:
            st.info("I couldn't find day headings in this plan, so swapping is unavailable.")
        else:
            swap_day = st.selectbox("Which day?", day_labels, key="swap_day")
            swap_target = st.text_input(
                "Which exercise do you want to replace?",
                placeholder="e.g. Bulgarian split squat",
            )
            if st.button("Suggest a replacement", use_container_width=True):
                profile = st.session_state.get("profile")
                if not isinstance(profile, UserProfile):
                    st.warning("Generate a plan first, then try swapping an exercise.")
                else:
                    try:
                        with st.spinner("Finding a fair swap..."):
                            st.session_state["swap_result"] = swap_exercise(
                                profile, swap_day, swap_target
                            )
                    except GroqClientError as exc:
                        st.session_state["swap_result"] = ""
                        st.error(str(exc))

            if st.session_state.get("swap_result"):
                st.success("Here's a swap that keeps your constraints intact:")
                st.markdown(st.session_state["swap_result"])

    with st.expander("See the exact prompt sent to the model"):
        profile = st.session_state.get("profile")
        if isinstance(profile, UserProfile):
            st.caption("System prompt")
            st.code(build_system_prompt(), language="markdown")
            st.caption("User prompt for this request")
            st.code(build_user_prompt(profile), language="markdown")
        else:
            st.caption("Generate a plan first to inspect its prompt.")


def main() -> None:
    init_state()

    st.title("Workout Plan Generator")
    st.caption(
        "A weekly plan built around your goal, your level, your equipment and the days you "
        "actually have — not a generic list of exercises."
    )

    profile = collect_inputs()

    st.divider()
    generate_col, regenerate_col = st.columns([2, 1])

    with generate_col:
        generate_clicked = st.button(
            "Generate Plan", type="primary", use_container_width=True
        )

    with regenerate_col:
        regenerate_clicked = st.button(
            "Regenerate",
            use_container_width=True,
            disabled=not st.session_state["plan"],
            help="Same constraints, different exercise selection.",
        )

    if regenerate_clicked:
        st.session_state["variation"] += 1
        generate_clicked = True

    if generate_clicked:
        errors = profile.validate()
        if errors:
            st.error("I need a couple of things before I can build your plan:")
            for error in errors:
                st.write(f"- {error}")
            st.stop()

        try:
            with st.spinner("Building your plan..."):
                plan = generate_plan(profile, variation=st.session_state["variation"])
        except GroqClientError as exc:
            st.error(str(exc))
            st.info(
                "Nothing you did caused this. Your inputs are saved, so once it's fixed "
                "you can press Generate Plan again."
            )
            st.stop()

        st.session_state["plan"] = plan
        st.session_state["profile"] = profile
        st.session_state["swap_result"] = ""

    if st.session_state["plan"]:
        render_plan(st.session_state["plan"])
    else:
        st.info(
            "Set your goal, level, days and equipment above, then press Generate Plan. "
            "If you have an injury, add it in the limitations box — the plan will be "
            "built around it rather than on top of it."
        )
        with st.expander("See the prompt this app will send"):
            st.caption(
                "This is what gets sent before you've generated anything. The system prompt "
                "is where the constraints live."
            )
            st.code(build_system_prompt(), language="markdown")

    st.divider()
    st.caption(
        "This app produces general fitness guidance, not medical advice. If you have an "
        "injury or a health condition, check with a clinician before starting."
    )


if __name__ == "__main__":
    main()
