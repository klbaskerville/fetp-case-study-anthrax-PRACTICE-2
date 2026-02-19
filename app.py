import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st

def load_theme():
    css_path = Path(".streamlit/style.css")
    if css_path.exists():
        st.markdown(
            f"<style>{css_path.read_text(encoding='utf-8')}</style>",
            unsafe_allow_html=True
        )

load_theme()

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
GUIDED_QUESTION_PARTS = ["A", "B", "C", "D"]
PLACEHOLDER_PATTERN = re.compile(r"\[\[([^\[\]]+)\]\]")


def normalize_placeholder_id(raw_id: str) -> str:
    token = raw_id.strip()
    if token.lower().startswith("question_"):
        suffix = token.split("_", 1)[1]
        return f"Question_{suffix}"
    if re.fullmatch(r"q\d+[a-zA-Z]?", token, flags=re.IGNORECASE):
        return f"Question_{token[1:]}"
    return token


@st.cache_data
def load_items_json(path: str) -> dict[str, Any]:
    file_path = Path(path)
    with file_path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    return payload


@st.cache_data
def load_markdown(path: str) -> str:
    file_path = Path(path)
    return file_path.read_text(encoding="utf-8")


def validate_items_payload(payload: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    required_root = ["module_id", "title", "items"]
    for key in required_root:
        if key not in payload:
            errors.append(f"Missing key in items.json: '{key}'")

    items = payload.get("items")
    if not isinstance(items, list):
        errors.append("'items' must be a list.")
        return errors

    for index, item in enumerate(items, start=1):
        if not isinstance(item, dict):
            errors.append(f"Item #{index} must be an object.")
            continue
        for key in ["id", "part", "type", "prompt"]:
            if key not in item:
                errors.append(f"Item #{index} missing required field '{key}'.")
    return errors


def extract_placeholders(markdown_text: str) -> list[str]:
    return [normalize_placeholder_id(match.group(1)) for match in PLACEHOLDER_PATTERN.finditer(markdown_text)]


def is_answered(item_id: str) -> bool:
    response = st.session_state.get(f"resp_{item_id}")
    done_checked = bool(st.session_state.get(f"done_{item_id}", False))
    computed_exists = st.session_state.get(f"computed_{item_id}") is not None

    if isinstance(response, str):
        has_response = bool(response.strip())
    elif isinstance(response, list):
        has_response = len(response) > 0
    elif isinstance(response, dict):
        has_response = len(response) > 0
    else:
        has_response = response is not None

    return done_checked or has_response or computed_exists


def get_preview(item_id: str) -> str:
    response = st.session_state.get(f"resp_{item_id}")
    if response is None:
        return ""
    if isinstance(response, str):
        return (response[:80] + "…") if len(response) > 80 else response
    if isinstance(response, list):
        return f"{len(response)} rows"
    if isinstance(response, dict):
        return f"{len(response)} keys"
    return str(response)


def render_instructor_mode(instr: dict[str, Any]) -> None:
    if not instr:
        st.caption("No instructor notes provided for this item.")
        return

    consumed: set[str] = set()

    prompts = instr.get("facilitator_pre_prompts")
    if prompts:
        consumed.add("facilitator_pre_prompts")
        st.markdown("**Facilitator prompts**")
        for prompt in prompts:
            st.markdown(f"- {prompt}")

    definitions = instr.get("reference_definitions")
    if definitions:
        consumed.add("reference_definitions")
        st.markdown("**Key definitions**")
        if isinstance(definitions, dict):
            for term, definition in definitions.items():
                st.markdown(f"- **{term}:** {definition}")
        elif isinstance(definitions, list):
            for line in definitions:
                st.markdown(f"- {line}")
        else:
            st.markdown(str(definitions))

    model_answer = instr.get("model_answer")
    if model_answer:
        consumed.add("model_answer")
        st.markdown("**Model answer**")
        if isinstance(model_answer, str):
            st.success(model_answer)
        elif isinstance(model_answer, list):
            for bullet in model_answer:
                st.markdown(f"- {bullet}")
        elif isinstance(model_answer, dict):
            for section, value in model_answer.items():
                st.markdown(f"###### {section}")
                if isinstance(value, str):
                    st.markdown(value)
                elif isinstance(value, list):
                    for bullet in value:
                        st.markdown(f"- {bullet}")
                else:
                    st.markdown(str(value))
        else:
            st.markdown(str(model_answer))

    rubric_keywords = instr.get("rubric_keywords")
    if rubric_keywords:
        consumed.add("rubric_keywords")
        if isinstance(rubric_keywords, list):
            tags = " ".join(f"`{keyword}`" for keyword in rubric_keywords)
        else:
            tags = f"`{rubric_keywords}`"
        st.markdown(f"**Rubric keywords:** {tags}")

    remaining = {k: v for k, v in instr.items() if k not in consumed}
    if remaining:
        with st.expander("More instructor notes", expanded=False):
            for key, value in remaining.items():
                st.markdown(f"**{key.replace('_', ' ').title()}**")
                if isinstance(value, list):
                    for entry in value:
                        st.markdown(f"- {entry}")
                elif isinstance(value, dict):
                    for sub_key, sub_value in value.items():
                        st.markdown(f"- **{sub_key}:** {sub_value}")
                else:
                    st.markdown(str(value))


def render_question_card(item: dict[str, Any], instructor_on: bool, active: bool = False) -> None:
    item_id = item["id"]
    item_type = item.get("type", "short_text")
    prompt = item.get("prompt", "")

    with st.container(border=True):
        status_icon = "✅" if is_answered(item_id) else "⏳"
        focus_text = " (current step)" if active else ""
        st.subheader(f"{status_icon} {item_id}{focus_text}")
        st.markdown(prompt)
        st.caption(f"Response type: {item_type.replace('_', ' ').title()}")

        response_key = f"resp_{item_id}"
        done_key = f"done_{item_id}"
        computed_key = f"computed_{item_id}"

        if item_type in {"short_text", "discussion", "reflection", "annotation"}:
            st.session_state[response_key] = st.text_area(
                "Your response",
                key=f"input_{item_id}",
                value=st.session_state.get(response_key, ""),
                placeholder="Type your thoughts here. Consider key evidence and your rationale.",
                height=130,
            )
            st.session_state[done_key] = st.checkbox(
                "Mark as complete",
                value=bool(st.session_state.get(done_key, False)),
                key=f"check_{item_id}",
            )

        elif item_type == "timeline_entry":
            st.session_state[response_key] = st.text_input(
                "Timeline entry",
                key=f"input_{item_id}",
                value=st.session_state.get(response_key, ""),
                placeholder="Add a concise date/event entry.",
            )
            st.session_state[done_key] = st.checkbox(
                "Mark as complete",
                value=bool(st.session_state.get(done_key, False)),
                key=f"check_{item_id}",
            )

        elif item_type == "table_calc":
            default_df = pd.DataFrame(
                {
                    "Metric": ["", "", ""],
                    "Value": [0.0, 0.0, 0.0],
                    "Notes": ["", "", ""],
                }
            )
            editor_state_key = f"editor_{item_id}"
            if editor_state_key not in st.session_state:
                st.session_state[editor_state_key] = default_df

            edited_df = st.data_editor(
                st.session_state[editor_state_key],
                key=f"table_{item_id}",
                use_container_width=True,
                num_rows="dynamic",
            )
            st.session_state[editor_state_key] = edited_df
            st.session_state[response_key] = edited_df.to_dict(orient="records")

            if st.button("Compute", key=f"compute_btn_{item_id}"):
                numeric_only = edited_df.select_dtypes(include="number")
                result = {
                    "rows": int(len(edited_df)),
                    "numeric_column_totals": {
                        col: float(numeric_only[col].fillna(0).sum()) for col in numeric_only.columns
                    },
                }
                st.session_state[computed_key] = result

            if st.session_state.get(computed_key):
                st.info(f"Computed result: {st.session_state[computed_key]}")

        else:
            st.session_state[response_key] = st.text_area(
                "Your response",
                key=f"input_{item_id}",
                value=st.session_state.get(response_key, ""),
                placeholder="Type your response.",
                height=130,
            )

        if instructor_on:
            with st.expander("Instructor Notes", expanded=False):
                render_instructor_mode(item.get("instructor_mode", {}))


def render_markdown_with_embedded_questions(
    markdown_text: str,
    items_by_id: dict[str, dict[str, Any]],
    instructor_on: bool,
    visible_question_ids: set[str] | None = None,
    active_question_id: str | None = None,
) -> None:
    chunks: list[str] = []
    last_end = 0

    for match in PLACEHOLDER_PATTERN.finditer(markdown_text):
        chunks.append(markdown_text[last_end:match.start()])
        token = normalize_placeholder_id(match.group(1))
        chunks.append(f"__PLACEHOLDER__::{token}")
        last_end = match.end()
    chunks.append(markdown_text[last_end:])

    for chunk in chunks:
        if chunk.startswith("__PLACEHOLDER__::"):
            qid = chunk.split("::", 1)[1]
            item = items_by_id.get(qid)

            if not item:
                st.warning(f"Placeholder '{qid}' was found in markdown but not in items.json.")
                continue

            if visible_question_ids is not None and qid not in visible_question_ids:
                st.caption("Continue with Next to reach this question.")
                continue

            render_question_card(item, instructor_on=instructor_on, active=(qid == active_question_id))
            st.divider()
        else:
            if chunk.strip():
                st.markdown(chunk)


def build_export_payload(
    items_payload: dict[str, Any],
    item_ids: list[str],
    mode: str,
    current_section: str,
    answered_count: int,
    total_count: int,
) -> dict[str, Any]:
    responses: dict[str, Any] = {}
    computed_results: dict[str, Any] = {}

    for item_id in item_ids:
        responses[item_id] = st.session_state.get(f"resp_{item_id}")
        computed = st.session_state.get(f"computed_{item_id}")
        if computed is not None:
            computed_results[item_id] = computed

    percent_complete = (answered_count / total_count * 100) if total_count else 0.0
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
            "percent_complete": round(percent_complete, 1),
        },
    }


def reset_all_responses(item_ids: list[str]) -> None:
    for item_id in item_ids:
        keys_to_clear = [
            f"resp_{item_id}",
            f"done_{item_id}",
            f"computed_{item_id}",
            f"editor_{item_id}",
            f"input_{item_id}",
            f"check_{item_id}",
            f"table_{item_id}",
            f"compute_btn_{item_id}",
        ]
        for key in keys_to_clear:
            st.session_state.pop(key, None)


def init_state() -> None:
    defaults = {
        "nav_mode": "Guided (Next/Back)",
        "guided_index": 0,
        "jump_section": "Part 0",
        "appendix_selection": "Appendix 1",
        "include_appendices_guided": False,
        "active_question_id": None,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def main() -> None:
    st.set_page_config(page_title="Anthrax Guided Case Study", layout="wide")
    init_state()

    try:
        items_payload = load_items_json(str(ITEMS_JSON_PATH))
    except FileNotFoundError:
        st.error("Required file is missing: content/items.json")
        st.stop()
    except json.JSONDecodeError as err:
        st.error(f"Invalid JSON in content/items.json: {err}")
        st.stop()

    validation_errors = validate_items_payload(items_payload)
    if validation_errors:
        st.error("items.json is invalid. Please fix the following:")
        for err in validation_errors:
            st.markdown(f"- {err}")
        st.stop()

    all_items: list[dict[str, Any]] = items_payload["items"]
    items_by_id = {item["id"]: item for item in all_items}
    item_ids = [item["id"] for item in all_items]

    part_items: dict[str, list[dict[str, Any]]] = {p: [] for p in GUIDED_QUESTION_PARTS}
    for item in all_items:
        part_key = str(item.get("part", "")).upper()
        if part_key in part_items:
            part_items[part_key].append(item)

    part_markdown: dict[str, str | None] = {}
    part_placeholder_order: dict[str, list[str]] = {}

    for part_name, path in PART_FILES.items():
        try:
            part_markdown[part_name] = load_markdown(str(path))
            part_placeholder_order[part_name] = extract_placeholders(part_markdown[part_name] or "")
        except FileNotFoundError:
            part_markdown[part_name] = None
            part_placeholder_order[part_name] = []

    appendix_markdown: dict[str, str | None] = {}
    appendix_placeholder_order: dict[str, list[str]] = {}
    for app_name, path in APPENDIX_FILES.items():
        try:
            appendix_markdown[app_name] = load_markdown(str(path))
            appendix_placeholder_order[app_name] = extract_placeholders(appendix_markdown[app_name] or "")
        except FileNotFoundError:
            appendix_markdown[app_name] = None
            appendix_placeholder_order[app_name] = []

    guided_steps: list[dict[str, Any]] = [{"section": "Part 0", "question_id": None}]
    for section in ["Part A", "Part B", "Part C", "Part D"]:
        placeholders = part_placeholder_order.get(section, [])
        if placeholders:
            for qid in placeholders:
                guided_steps.append({"section": section, "question_id": qid})
        else:
            guided_steps.append({"section": section, "question_id": None})

    if st.session_state["include_appendices_guided"]:
        for app_name in APPENDIX_FILES:
            guided_steps.append({"section": app_name, "question_id": None})

    max_index = max(len(guided_steps) - 1, 0)
    st.session_state["guided_index"] = min(st.session_state["guided_index"], max_index)

    total_ad_questions = sum(len(part_items[p]) for p in GUIDED_QUESTION_PARTS)
    answered_ad_questions = sum(1 for p in GUIDED_QUESTION_PARTS for item in part_items[p] if is_answered(item["id"]))
    overall_percent = (answered_ad_questions / total_ad_questions * 100) if total_ad_questions else 0.0

    st.title(items_payload.get("title", "Guided Case Study"))
    st.caption("A learner-friendly case study flow with embedded questions, progress tracking, and exports.")

    with st.sidebar:
        st.header("Learning Controls")
        instructor_mode_on = st.toggle("Instructor Mode", value=False)

        nav_mode = st.radio(
            "Navigation mode",
            options=["Guided (Next/Back)", "Jump to Section"],
            index=0 if st.session_state["nav_mode"] == "Guided (Next/Back)" else 1,
        )
        st.session_state["nav_mode"] = nav_mode

        if nav_mode == "Guided (Next/Back)":
            st.session_state["include_appendices_guided"] = st.checkbox(
                "Include appendices in guided flow",
                value=bool(st.session_state["include_appendices_guided"]),
            )

        if st.button("Reset responses", use_container_width=True):
            reset_all_responses(item_ids)
            st.success("All saved responses were reset.")

        if nav_mode == "Guided (Next/Back)":
            current_section_name = guided_steps[st.session_state["guided_index"]]["section"]
        else:
            current_section_name = st.session_state.get("jump_section", "Part 0")

        export_payload = build_export_payload(
            items_payload=items_payload,
            item_ids=item_ids,
            mode="guided" if nav_mode == "Guided (Next/Back)" else "jump",
            current_section=current_section_name,
            answered_count=answered_ad_questions,
            total_count=total_ad_questions,
        )
        st.download_button(
            "Download responses (JSON)",
            data=json.dumps(export_payload, indent=2, ensure_ascii=False),
            file_name="anthrax_case_study_responses.json",
            mime="application/json",
            use_container_width=True,
        )

    tab_learn, tab_review, tab_appendix = st.tabs(["Learn & Respond", "Review Answers", "Appendices"])

    with tab_learn:
        st.progress(overall_percent / 100 if total_ad_questions else 0.0, text=f"Overall progress (Parts A–D): {overall_percent:.1f}%")

        if nav_mode == "Jump to Section":
            selected_section = st.selectbox("Choose section", options=PART_ORDER, key="jump_section")
            selected_part_letter = selected_section.split(" ")[-1] if selected_section != "Part 0" else None

            if selected_part_letter in GUIDED_QUESTION_PARTS:
                part_total = len(part_items[selected_part_letter])
                part_answered = sum(1 for item in part_items[selected_part_letter] if is_answered(item["id"]))
                st.caption(f"Part progress: {part_answered}/{part_total} answered")
            else:
                st.caption("Part progress: Introductory section (no scored questions).")

            markdown_text = part_markdown.get(selected_section)
            if markdown_text is None:
                st.error(f"Missing markdown file for {selected_section}: {PART_FILES[selected_section].relative_to(BASE_DIR)}")
                if selected_part_letter in GUIDED_QUESTION_PARTS:
                    for item in part_items[selected_part_letter]:
                        render_question_card(item, instructor_mode_on)
                        st.divider()
            else:
                st.header(selected_section)
                render_markdown_with_embedded_questions(
                    markdown_text,
                    items_by_id,
                    instructor_on=instructor_mode_on,
                    visible_question_ids=None,
                    active_question_id=st.session_state.get("active_question_id"),
                )

        else:
            current_step = guided_steps[st.session_state["guided_index"]]
            current_section = current_step["section"]
            current_qid = current_step["question_id"]
            st.session_state["active_question_id"] = current_qid

            selected_part_letter = current_section.split(" ")[-1] if current_section.startswith("Part ") and current_section != "Part 0" else None
            if selected_part_letter in GUIDED_QUESTION_PARTS:
                part_total = len(part_items[selected_part_letter])
                part_answered = sum(1 for item in part_items[selected_part_letter] if is_answered(item["id"]))
                st.caption(f"Part progress: {part_answered}/{part_total} answered")
            else:
                st.caption("Part progress: Introductory/appendix step.")

            if current_section in PART_FILES:
                md_text = part_markdown.get(current_section)
                missing_path = PART_FILES[current_section].relative_to(BASE_DIR)
            else:
                md_text = appendix_markdown.get(current_section)
                missing_path = APPENDIX_FILES[current_section].relative_to(BASE_DIR)

            if md_text is None:
                st.error(f"Missing markdown file for {current_section}: {missing_path}")
                if selected_part_letter in GUIDED_QUESTION_PARTS and current_qid:
                    item = items_by_id.get(current_qid)
                    if item:
                        render_question_card(item, instructor_mode_on, active=True)
            else:
                st.header(current_section)
                visible: set[str] | None = None
                if current_qid:
                    visible = {current_qid}
                render_markdown_with_embedded_questions(
                    md_text,
                    items_by_id,
                    instructor_on=instructor_mode_on,
                    visible_question_ids=visible,
                    active_question_id=current_qid,
                )

            col_back, col_top, col_next = st.columns([1, 1, 1])
            with col_back:
                if st.button("⬅️ Back", use_container_width=True, disabled=st.session_state["guided_index"] <= 0):
                    st.session_state["guided_index"] = max(st.session_state["guided_index"] - 1, 0)
                    st.rerun()
            with col_top:
                if st.button("🔝 Back to top", use_container_width=True):
                    st.rerun()
            with col_next:
                if st.button("Next ➡️", use_container_width=True, disabled=st.session_state["guided_index"] >= max_index):
                    st.session_state["guided_index"] = min(st.session_state["guided_index"] + 1, max_index)
                    st.rerun()

    with tab_review:
        st.header("Review your responses")
        st.caption("Jump to any question to continue editing in context.")

        for item in all_items:
            qid = item["id"]
            status = "✅ Answered" if is_answered(qid) else "⏳ Pending"
            preview = get_preview(qid)
            with st.container(border=True):
                c1, c2, c3 = st.columns([1.2, 4, 1])
                c1.markdown(f"**{qid}**")
                c1.caption(status)
                c2.markdown(item.get("prompt", ""))
                c2.caption(f"Preview: {preview if preview else 'No response yet'}")
                if c3.button("Go", key=f"go_{qid}"):
                    item_part = str(item.get("part", "")).upper()
                    target_section = f"Part {item_part}" if item_part in GUIDED_QUESTION_PARTS else "Part 0"
                    st.session_state["active_question_id"] = qid

                    if st.session_state["nav_mode"] == "Guided (Next/Back)":
                        target_index = None
                        for idx, step in enumerate(guided_steps):
                            if step["question_id"] == qid:
                                target_index = idx
                                break
                        if target_index is not None:
                            st.session_state["guided_index"] = target_index
                    else:
                        st.session_state["jump_section"] = target_section
                    st.rerun()

    with tab_appendix:
        st.header("Appendices")
        appendix_choice = st.selectbox("Select appendix", list(APPENDIX_FILES.keys()), key="appendix_selection")

        appendix_text = appendix_markdown.get(appendix_choice)
        if appendix_text is None:
            st.error(f"Missing markdown file for {appendix_choice}: {APPENDIX_FILES[appendix_choice].relative_to(BASE_DIR)}")
        else:
            st.subheader(appendix_choice)
            render_markdown_with_embedded_questions(
                appendix_text,
                items_by_id,
                instructor_on=instructor_mode_on,
                visible_question_ids=None,
                active_question_id=st.session_state.get("active_question_id"),
            )


if __name__ == "__main__":
    main()
