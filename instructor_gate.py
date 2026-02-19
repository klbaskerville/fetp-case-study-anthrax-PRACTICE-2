import hmac
import os
from typing import Optional

import streamlit as st
from streamlit.errors import StreamlitSecretNotFoundError

UNLOCKED_KEY = "instructor_unlocked"
ENABLED_KEY = "instructor_enabled"
ERROR_KEY = "instructor_unlock_error"
INPUT_KEY = "instructor_unlock_input"


def _init_state() -> None:
    if UNLOCKED_KEY not in st.session_state:
        st.session_state[UNLOCKED_KEY] = False
    if ENABLED_KEY not in st.session_state:
        st.session_state[ENABLED_KEY] = False
    if ERROR_KEY not in st.session_state:
        st.session_state[ERROR_KEY] = None
    if INPUT_KEY not in st.session_state:
        st.session_state[INPUT_KEY] = ""


def _get_unlock_code() -> Optional[str]:
    code = None
    try:
        code = st.secrets.get("INSTRUCTOR_UNLOCK_CODE")
    except StreamlitSecretNotFoundError:
        code = None

    if code:
        return str(code)

    env_code = os.environ.get("INSTRUCTOR_UNLOCK_CODE")
    if env_code:
        return str(env_code)

    return None


def is_instructor_unlocked() -> bool:
    _init_state()
    return bool(st.session_state.get(UNLOCKED_KEY, False))


def instructor_mode_enabled() -> bool:
    _init_state()
    return is_instructor_unlocked() and bool(st.session_state.get(ENABLED_KEY, False))


def lock_instructor() -> None:
    _init_state()
    st.session_state[UNLOCKED_KEY] = False
    st.session_state[ENABLED_KEY] = False
    st.session_state[ERROR_KEY] = None
    st.session_state[INPUT_KEY] = ""


def set_instructor_enabled(enabled: bool) -> None:
    _init_state()
    if is_instructor_unlocked():
        st.session_state[ENABLED_KEY] = bool(enabled)
    else:
        st.session_state[ENABLED_KEY] = False


def _unlock_attempt(configured_code: Optional[str]) -> None:
    entered_code = str(st.session_state.get(INPUT_KEY, ""))
    if not configured_code:
        st.session_state[ERROR_KEY] = "Unlock code not configured."
        return

    if hmac.compare_digest(entered_code, configured_code):
        st.session_state[UNLOCKED_KEY] = True
        st.session_state[ERROR_KEY] = None
        st.session_state[INPUT_KEY] = ""
    else:
        st.session_state[UNLOCKED_KEY] = False
        st.session_state[ENABLED_KEY] = False
        st.session_state[ERROR_KEY] = "Incorrect unlock code."


def instructor_gate_ui(
    *,
    location: str = "sidebar",
    label: str = "Instructor Mode",
    help_text: str | None = None,
) -> None:
    _init_state()
    configured_code = _get_unlock_code()

    container = st.sidebar if location == "sidebar" else st
    container.subheader(label)
    if help_text:
        container.caption(help_text)

    if not is_instructor_unlocked():
        container.caption("🔒 Locked · Instructor notes are hidden")
        container.text_input(
            "Unlock code",
            type="password",
            key=INPUT_KEY,
            placeholder="Enter instructor unlock code",
        )
        if container.button("Unlock", key=f"unlock_btn_{location}_{label}", use_container_width=True):
            _unlock_attempt(configured_code)

        if st.session_state.get(ERROR_KEY):
            container.warning(st.session_state[ERROR_KEY])
        elif not configured_code:
            container.warning("Unlock code not configured.")
        return

    mode_on = container.toggle(
        "Instructor Mode",
        value=bool(st.session_state.get(ENABLED_KEY, False)),
        key=f"{ENABLED_KEY}_toggle_{location}_{label}",
    )
    set_instructor_enabled(mode_on)

    if instructor_mode_enabled():
        container.caption("✅ Instructor Mode ON")
    else:
        container.caption("✅ Unlocked · Instructor notes are hidden")

    if container.button("Lock", key=f"lock_btn_{location}_{label}", use_container_width=True):
        lock_instructor()
        st.rerun()
