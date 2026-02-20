import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st

from instructor_gate import instructor_gate_ui, instructor_mode_enabled

try:
    from instructor_gate import is_instructor_unlocked
except ImportError:  # optional helper
    is_instructor_unlocked = None

BASE_DIR = Path(__file__).resolve().parent
CONTENT_DIR = BASE_DIR / "content"
ITEMS_JSON_PATH = CONTENT_DIR / "items.json"

PART_FILES = {
    "Part 0": CONTENT_DIR / "parts" / "part_0.md",
    "Part A": CONTENT_DIR / "parts" / "part_a.md",
    "Part B": CONTENT_DIR / "parts" / "part_b.md",
    "Part C": CONTENT_DIR / "parts" / "part_c.md",
    "Part D": CONTENT_DIR / "parts" / "part_d.md",
}

APPENDIX_FILES = {
    "Appendix 1": CONTENT_DIR / "appendices" / "appendix_1_one_health.md",
    "Appendix 2": CONTENT_DIR / "appendices" / "appendix_2_anthrax_fact_sheet.md",
    "Appendix 3": CONTENT_DIR / "appendices" / "appendix_3_line_list.md",
}

PART_ORDER = ["Part 0", "Part A", "Part B", "Part C", "Part D"]
PART_LETTERS = ["A", "B", "C", "D"]
PLACEHOLDER_PATTERN = re.compile(r"\[\[([^\[\]]+)\]\]")


def load_theme() -> None:
    css_path = BASE_DIR / ".streamlit" / "style.css"
    if css_path.exists():
        st.markdown(f"<style>{css_path.read_text(encoding='utf-8')}</style>", unsafe_allow_html=True)


def normalize_placeholder_id(raw_id: str) -> str:
    token = raw_id.strip()
    token = re.sub(r"\s+", "_", token)

    q_match = re.fullmatch(r"[Qq](\d+[A-Za-z]?)", token)
    if q_match:
        return f"Question_{q_match.group(1)}"

    question_match = re.fullmatch(r"[Qq]uestion_(.+)", token)
    if question_match:
        return f"Question_{question_match.group(1)}"

    return token


@st.cache_data
def load_items_json(path: str) -> dict[str, Any]:
    with Path(path).open("r", encoding="utf-8") as handle:
        return json.load(handle)


@st.cache_data
def load_markdown(path: str) -> str:
    return Path(path).read_text(encoding="utf-8")


def validate_items_payload(payload: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    for key in ["module_id", "title", "items"]:
        if key not in payload:
            errors.append(f"Missing key in items.json: '{key}'")

    items = payload.get("items")
    if not isinstance(items, list):
        errors.append("'items' must be a list.")
        return errors

    for idx, item in enumerate(items, start=1):
        if not isinstance(item, dict):
            errors.append(f"Item #{idx} must be an object.")
            continue
        for key in ["id", "part", "type", "prompt"]:
            if key not in item:
                errors.append(f"Item #{idx} missing required field '{key}'.")
    return errors


def extract_placeholders(markdown_text: str) -> list[str]:
    return [normalize_placeholder_id(match.group(1)) for match in PLACEHOLDER_PATTERN.finditer(markdown_text)]


def is_answered(item_id: str) -> bool:
    response = st.session_state.get(f"resp_{item_id}")
    done = bool(st.session_state.get(f"done_{item_id}", False))
    computed = st.session_state.get(f"computed_{item_id}") is not None

    if isinstance(response, str):
        has_response = bool(response.strip())
    elif isinstance(response, (list, dict)):
        has_response = len(response) > 0
    else:
        has_response = response is not None

    return done or has_response or computed


def response_preview(item_id: str) -> str:
    response = st.session_state.get(f"resp_{item_id}")
    if response is None:
        return ""
    if isinstance(response, str):
        trimmed = response.strip()
        return (trimmed[:90] + "…") if len(trimmed) > 90 else trimmed
    if isinstance(response, list):
        return f"{len(response)} rows"
    if isinstance(response, dict):
        return f"{len(response)} keys"
    return str(response)


def render_facilitator_guide(instr: dict[str, Any]) -> None:
    st.markdown("#### Facilitator Guide")
    if not instr:
        st.caption("No instructor guidance provided for this item.")
        return

    consumed: set[str] = set()

    pre_prompts = instr.get("facilitator_pre_prompts")
    if pre_prompts:
        consumed.add("facilitator_pre_prompts")
        st.markdown("**Before you ask**")
        for prompt in pre_prompts if isinstance(pre_prompts, list) else [pre_prompts]:
            st.markdown(f"- {prompt}")

    definitions = instr.get("reference_definitions")
    if definitions:
        consumed.add("reference_definitions")
        st.markdown("**Key definitions**")
        if isinstance(definitions, dict):
            for key, value in definitions.items():
                st.markdown(f"- **{key}**: {value}")
        elif isinstance(definitions, list):
            for line in definitions:
                st.markdown(f"- {line}")
        else:
            st.markdown(f"- {definitions}")

    model_answer = instr.get("model_answer")
    if model_answer:
        consumed.add("model_answer")
        if isinstance(model_answer, str):
            st.success(model_answer)
        else:
            st.info(json.dumps(model_answer, ensure_ascii=False, indent=2))

    rubric = instr.get("rubric_keywords")
    if rubric:
        consumed.add("rubric_keywords")
        tags = rubric if isinstance(rubric, list) else [rubric]
        st.markdown("**Rubric keywords**")
        st.markdown(" ".join(f"`{tag}`" for tag in tags))

    notes = instr.get("notes")
    if notes:
        consumed.add("notes")
        st.markdown("**Facilitation notes**")
        if isinstance(notes, list):
            st.markdown("\n\n".join(str(n) for n in notes))
        else:
            st.markdown(str(notes))

    extras = {k: v for k, v in instr.items() if k not in consumed}
    if extras:
        with st.expander("More instructor content", expanded=False):
            for key, value in extras.items():
                st.markdown(f"**{key.replace('_', ' ').title()}**")
                if isinstance(value, dict):
                    st.json(value)
                elif isinstance(value, list):
                    for row in value:
                        st.markdown(f"- {row}")
                else:
                    st.markdown(str(value))


def render_response_widget(item: dict[str, Any]) -> None:
    item_id = item["id"]
    item_type = item.get("type", "short_text")

    response_key = f"resp_{item_id}"
    done_key = f"done_{item_id}"
    computed_key = f"computed_{item_id}"

    if item_type in {"short_text", "discussion", "reflection", "annotation"}:
        st.session_state[response_key] = st.text_area(
            "Your response",
            key=f"input_{item_id}",
            value=st.session_state.get(response_key, ""),
            height=130,
        )
        st.session_state[done_key] = st.checkbox(
            "Mark as complete",
            key=f"check_{item_id}",
            value=bool(st.session_state.get(done_key, False)),
        )
    elif item_type == "timeline_entry":
        st.session_state[response_key] = st.text_input(
            "Timeline entry",
            key=f"input_{item_id}",
            value=st.session_state.get(response_key, ""),
        )
        st.session_state[done_key] = st.checkbox(
            "Mark as complete",
            key=f"check_{item_id}",
            value=bool(st.session_state.get(done_key, False)),
        )
    elif item_type == "table_calc":
        starter = pd.DataFrame({"Metric": ["", "", ""], "Value": [0.0, 0.0, 0.0], "Notes": ["", "", ""]})
        table_key = f"editor_{item_id}"
        if table_key not in st.session_state:
            st.session_state[table_key] = starter

        edited = st.data_editor(
            st.session_state[table_key],
            key=f"table_{item_id}",
            num_rows="dynamic",
            use_container_width=True,
        )
        st.session_state[table_key] = edited
        st.session_state[response_key] = edited.to_dict(orient="records")

        if st.button("Compute", key=f"compute_btn_{item_id}"):
            numeric = edited.select_dtypes(include="number")
            st.session_state[computed_key] = {
                "rows": int(len(edited)),
                "numeric_column_totals": {col: float(numeric[col].fillna(0).sum()) for col in numeric.columns},
            }
        if st.session_state.get(computed_key) is not None:
            st.info(f"Computed result: {st.session_state[computed_key]}")
    else:
        st.session_state[response_key] = st.text_area(
            "Your response",
            key=f"input_{item_id}",
            value=st.session_state.get(response_key, ""),
            height=130,
        )


def render_question_card(item: dict[str, Any], instructor_on: bool, active: bool = False) -> None:
    item_id = item["id"]
    status_icon = "✅" if is_answered(item_id) else "⏳"
    subtitle = " (current step)" if active else ""

    with st.container(border=True):
        st.markdown(f"### {status_icon} {item_id}{subtitle}")
        if instructor_on:
            left, right = st.columns([1.35, 1])
            with left:
                st.markdown(item.get("prompt", ""))
                render_response_widget(item)
            with right:
                with st.container(border=True):
                    render_facilitator_guide(item.get("instructor_mode", {}))
        else:
            st.markdown(item.get("prompt", ""))
            render_response_widget(item)


def render_markdown_with_embedded_questions(
    markdown_text: str,
    items_by_id: dict[str, dict[str, Any]],
    instructor_on: bool,
    visible_question_ids: set[str] | None,
    active_question_id: str | None,
) -> None:
    last_end = 0
    for match in PLACEHOLDER_PATTERN.finditer(markdown_text):
        narrative = markdown_text[last_end:match.start()]
        if narrative.strip():
            st.markdown(narrative)

        qid = normalize_placeholder_id(match.group(1))
        item = items_by_id.get(qid)
        if item is None:
            st.warning(f"Placeholder '{qid}' was found in markdown but not in items.json.")
        elif visible_question_ids is not None and qid not in visible_question_ids:
            pass
        else:
            render_question_card(item, instructor_on=instructor_on, active=(qid == active_question_id))
        last_end = match.end()

    tail = markdown_text[last_end:]
    if tail.strip():
        st.markdown(tail)


def build_guided_steps(part_placeholder_order: dict[str, list[str]], include_appendices: bool) -> list[dict[str, str | None]]:
    steps: list[dict[str, str | None]] = [{"section": "Part 0", "question_id": None}]
    for section in ["Part A", "Part B", "Part C", "Part D"]:
        placeholders = part_placeholder_order.get(section, [])
        if placeholders:
            for qid in placeholders:
                steps.append({"section": section, "question_id": qid})
        else:
            steps.append({"section": section, "question_id": None})

    if include_appendices:
        for appendix in APPENDIX_FILES:
            steps.append({"section": appendix, "question_id": None})

    return steps


def build_export_payload(
    items_payload: dict[str, Any],
    item_ids: list[str],
    mode: str,
    current_section: str,
    answered_count: int,
    total_count: int,
) -> dict[str, Any]:
    responses = {item_id: st.session_state.get(f"resp_{item_id}") for item_id in item_ids}
    computed_results = {
        item_id: st.session_state.get(f"computed_{item_id}")
        for item_id in item_ids
        if st.session_state.get(f"computed_{item_id}") is not None
    }
    percent = (answered_count / total_count * 100) if total_count else 0.0
    return {
        "module_id": items_payload.get("module_id"),
        "title": items_payload.get("title"),
        "version": items_payload.get("version"),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "mode": mode,
        "current_section": current_section,
        "responses": responses,
        "computed_results": computed_results,
        "completion_summary": {
            "answered_count": answered_count,
            "total_count": total_count,
            "percent_complete": round(percent, 1),
        },
    }


def reset_responses(item_ids: list[str]) -> None:
    for item_id in item_ids:
        for key in [
            f"resp_{item_id}",
            f"done_{item_id}",
            f"computed_{item_id}",
            f"editor_{item_id}",
            f"input_{item_id}",
            f"check_{item_id}",
            f"table_{item_id}",
            f"compute_btn_{item_id}",
        ]:
            st.session_state.pop(key, None)


def init_state() -> None:
    defaults: dict[str, Any] = {
        "nav_mode": "Guided (Next/Back)",
        "guided_index": 0,
        "jump_section": "Part 0",
        "appendix_selection": "Appendix 1",
        "include_appendices_guided": False,
        "show_full_part": False,
        "active_question_id": None,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def main() -> None:
    st.set_page_config(page_title="Anthrax Case Study", layout="wide")
    load_theme()
    init_state()

    try:
        items_payload = load_items_json(str(ITEMS_JSON_PATH))
    except FileNotFoundError:
        st.error("Required file missing: content/items.json")
        st.stop()
    except json.JSONDecodeError as err:
        st.error(f"Invalid JSON in content/items.json: {err}")
        st.stop()

    errors = validate_items_payload(items_payload)
    if errors:
        st.error("items.json is invalid.")
        for err in errors:
            st.markdown(f"- {err}")
        st.stop()

    all_items: list[dict[str, Any]] = items_payload["items"]
    items_by_id = {item["id"]: item for item in all_items}
    item_ids = [item["id"] for item in all_items]

    part_items: dict[str, list[dict[str, Any]]] = {letter: [] for letter in PART_LETTERS}
    for item in all_items:
        part = str(item.get("part", "")).upper()
        if part in part_items:
            part_items[part].append(item)

    part_markdown: dict[str, str | None] = {}
    part_placeholder_order: dict[str, list[str]] = {}
    for part_name, path in PART_FILES.items():
        try:
            content = load_markdown(str(path))
            part_markdown[part_name] = content
            part_placeholder_order[part_name] = extract_placeholders(content)
        except FileNotFoundError:
            part_markdown[part_name] = None
            part_placeholder_order[part_name] = []

    appendix_markdown: dict[str, str | None] = {}
    for appendix_name, path in APPENDIX_FILES.items():
        try:
            appendix_markdown[appendix_name] = load_markdown(str(path))
        except FileNotFoundError:
            appendix_markdown[appendix_name] = None

    guided_steps = build_guided_steps(part_placeholder_order, st.session_state["include_appendices_guided"])
    max_index = max(len(guided_steps) - 1, 0)
    st.session_state["guided_index"] = min(st.session_state["guided_index"], max_index)

    answered_count = sum(1 for letter in PART_LETTERS for item in part_items[letter] if is_answered(item["id"]))
    total_count = sum(len(part_items[letter]) for letter in PART_LETTERS)
    percent = (answered_count / total_count * 100) if total_count else 0.0

    st.title(items_payload.get("title", "Case Study"))
    if instructor_mode_enabled():
        st.info("🔓 Instructor View")
    else:
        st.caption("🔒 Participant View")

    with st.sidebar:
        instructor_gate_ui(help_text="Unlock instructor mode to reveal facilitator guide content.")
        if is_instructor_unlocked is not None:
            st.caption("Instructor gate: unlocked" if is_instructor_unlocked() else "Instructor gate: locked")

        st.session_state["nav_mode"] = st.radio(
            "Navigation mode",
            options=["Guided (Next/Back)", "Jump to Section"],
            index=0 if st.session_state["nav_mode"] == "Guided (Next/Back)" else 1,
        )

        if st.session_state["nav_mode"] == "Guided (Next/Back)":
            st.session_state["include_appendices_guided"] = st.checkbox(
                "Include appendices in guided flow",
                value=bool(st.session_state["include_appendices_guided"]),
            )
            st.session_state["show_full_part"] = st.checkbox(
                "Show full part (all questions)",
                value=bool(st.session_state["show_full_part"]),
            )

        current_section = guided_steps[st.session_state["guided_index"]]["section"] if st.session_state["nav_mode"] == "Guided (Next/Back)" else st.session_state["jump_section"]
        current_part_placeholders = part_placeholder_order.get(current_section, []) if current_section in PART_FILES else []

        if instructor_mode_enabled() and current_part_placeholders:
            jump_qid = st.selectbox(
                "Facilitator Quick Jump",
                options=["--"] + current_part_placeholders,
                index=0,
                key="facilitator_quick_jump",
            )
            if jump_qid != "--":
                st.session_state["active_question_id"] = jump_qid
                if st.session_state["nav_mode"] == "Guided (Next/Back)":
                    for idx, step in enumerate(guided_steps):
                        if step["question_id"] == jump_qid:
                            st.session_state["guided_index"] = idx
                            break
                else:
                    part = items_by_id.get(jump_qid, {}).get("part", "").upper()
                    if part in PART_LETTERS:
                        st.session_state["jump_section"] = f"Part {part}"
                st.rerun()

        if st.button("Reset responses", use_container_width=True):
            reset_responses(item_ids)
            st.rerun()

        export_payload = build_export_payload(
            items_payload,
            item_ids,
            "guided" if st.session_state["nav_mode"] == "Guided (Next/Back)" else "jump",
            current_section,
            answered_count,
            total_count,
        )
        st.download_button(
            "Download responses (JSON)",
            data=json.dumps(export_payload, ensure_ascii=False, indent=2),
            file_name="anthrax_case_study_responses.json",
            mime="application/json",
            use_container_width=True,
        )

        if st.button("Reload content (clear cache)", use_container_width=True):
            st.cache_data.clear()
            st.rerun()

    learn_tab, review_tab, appendices_tab = st.tabs(["Learn & Respond", "Review Answers", "Appendices"])

    with learn_tab:
        st.progress(percent / 100 if total_count else 0.0, text=f"Progress (Parts A–D): {percent:.1f}%")

        if st.session_state["nav_mode"] == "Jump to Section":
            section = st.selectbox("Choose section", PART_ORDER, key="jump_section")
            markdown_text = part_markdown.get(section)

            if markdown_text is None:
                st.error(f"Missing markdown file for {section}: {PART_FILES[section].relative_to(BASE_DIR)}")
                part_letter = section.split(" ")[-1] if section != "Part 0" else ""
                if part_letter in PART_LETTERS:
                    for item in part_items[part_letter]:
                        render_question_card(item, instructor_on=instructor_mode_enabled(), active=item["id"] == st.session_state.get("active_question_id"))
            else:
                render_markdown_with_embedded_questions(
                    markdown_text=markdown_text,
                    items_by_id=items_by_id,
                    instructor_on=instructor_mode_enabled(),
                    visible_question_ids=None,
                    active_question_id=st.session_state.get("active_question_id"),
                )
        else:
            guided_steps = build_guided_steps(part_placeholder_order, st.session_state["include_appendices_guided"])
            max_index = max(len(guided_steps) - 1, 0)
            st.session_state["guided_index"] = min(st.session_state["guided_index"], max_index)
            step = guided_steps[st.session_state["guided_index"]]
            section = step["section"]
            current_qid = step["question_id"]
            st.session_state["active_question_id"] = current_qid

            md_text = part_markdown.get(section) if section in PART_FILES else appendix_markdown.get(section)
            missing_ref = PART_FILES.get(section, APPENDIX_FILES.get(section))

            if md_text is None:
                st.error(f"Missing markdown file for {section}: {missing_ref.relative_to(BASE_DIR)}")
                if section.startswith("Part ") and section != "Part 0":
                    part_letter = section.split(" ")[-1]
                    for item in part_items.get(part_letter, []):
                        if st.session_state["show_full_part"] or item["id"] == current_qid:
                            render_question_card(item, instructor_on=instructor_mode_enabled(), active=item["id"] == current_qid)
            else:
                visible_ids = None
                if current_qid and not st.session_state["show_full_part"]:
                    visible_ids = {current_qid}
                render_markdown_with_embedded_questions(
                    markdown_text=md_text,
                    items_by_id=items_by_id,
                    instructor_on=instructor_mode_enabled(),
                    visible_question_ids=visible_ids,
                    active_question_id=current_qid,
                )

            col1, col2, col3 = st.columns(3)
            with col1:
                if st.button("⬅️ Back", use_container_width=True, disabled=st.session_state["guided_index"] <= 0):
                    st.session_state["guided_index"] = max(0, st.session_state["guided_index"] - 1)
                    st.rerun()
            with col3:
                if st.button("Next ➡️", use_container_width=True, disabled=st.session_state["guided_index"] >= max_index):
                    st.session_state["guided_index"] = min(max_index, st.session_state["guided_index"] + 1)
                    st.rerun()

    with review_tab:
        rows = []
        for item in all_items:
            qid = item["id"]
            rows.append(
                {
                    "item_id": qid,
                    "status": "✅" if is_answered(qid) else "⏳",
                    "preview": response_preview(qid) or "No response yet",
                }
            )

        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

        for item in all_items:
            qid = item["id"]
            with st.container(border=True):
                c1, c2, c3 = st.columns([1.3, 4, 1])
                c1.markdown(f"**{qid}**")
                c1.caption("Answered" if is_answered(qid) else "Pending")
                c2.caption(response_preview(qid) or "No response yet")
                if c3.button("Go", key=f"review_go_{qid}"):
                    part = str(item.get("part", "")).upper()
                    target = f"Part {part}" if part in PART_LETTERS else "Part 0"
                    st.session_state["active_question_id"] = qid
                    if st.session_state["nav_mode"] == "Guided (Next/Back)":
                        guided_steps = build_guided_steps(part_placeholder_order, st.session_state["include_appendices_guided"])
                        for idx, gstep in enumerate(guided_steps):
                            if gstep["question_id"] == qid:
                                st.session_state["guided_index"] = idx
                                break
                    else:
                        st.session_state["jump_section"] = target
                    st.rerun()

                if instructor_mode_enabled():
                    model = item.get("instructor_mode", {}).get("model_answer")
                    if st.button("Show model answer", key=f"model_{qid}"):
                        if model:
                            with st.expander(f"Model answer: {qid}", expanded=True):
                                if isinstance(model, str):
                                    st.success(model)
                                else:
                                    st.info(json.dumps(model, ensure_ascii=False, indent=2))
                        else:
                            st.caption("No model answer provided.")

    with appendices_tab:
        appendix_choice = st.selectbox("Select appendix", list(APPENDIX_FILES.keys()), key="appendix_selection")
        appendix_text = appendix_markdown.get(appendix_choice)
        if appendix_text is None:
            st.error(f"Missing markdown file for {appendix_choice}: {APPENDIX_FILES[appendix_choice].relative_to(BASE_DIR)}")
        else:
            render_markdown_with_embedded_questions(
                markdown_text=appendix_text,
                items_by_id=items_by_id,
                instructor_on=instructor_mode_enabled(),
                visible_question_ids=None,
                active_question_id=st.session_state.get("active_question_id"),
            )


if __name__ == "__main__":
    main()
