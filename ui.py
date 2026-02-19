"""Reusable Streamlit UI helper functions for FETP training modules."""

from __future__ import annotations

from pathlib import Path

import streamlit as st


CSS_PATH = Path(".streamlit/style.css")


def load_theme_css() -> None:
    """Inject custom CSS into the Streamlit app if the CSS file exists."""
    if CSS_PATH.exists():
        st.markdown(
            f"<style>{CSS_PATH.read_text(encoding='utf-8')}</style>",
            unsafe_allow_html=True,
        )


def section_header(title: str, subtitle: str | None = None, *, icon: str = "📘") -> None:
    """Render a consistent section header used across learning modules."""
    st.markdown(f"## {icon} {title}")
    if subtitle:
        st.caption(subtitle)


def status_badge(text: str, *, tone: str = "info") -> None:
    """Render a compact status callout."""
    tone_map = {
        "info": st.info,
        "success": st.success,
        "warning": st.warning,
        "error": st.error,
    }
    renderer = tone_map.get(tone, st.info)
    renderer(text)


def card(title: str, body: str) -> None:
    """Render card-like content with a title and markdown body."""
    with st.container(border=True):
        st.markdown(f"**{title}**")
        st.markdown(body)
