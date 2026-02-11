import json
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st

BASE_DIR = Path(__file__).resolve().parent
CONTENT_DIR = BASE_DIR / "content"
ITEMS_PATH = CONTENT_DIR / "items.json"

SECTION_CONFIG = {
    "Part A": {"kind": "part", "id": "A", "path": CONTENT_DIR / "parts" / "part_a.md"},
    "Part B": {"kind": "part", "id": "B", "path": CONTENT_DIR / "parts" / "part_b.md"},
    "Part C": {"kind": "part", "id": "C", "path": CONTENT_DIR / "parts" / "part_c.md"},
    "Part D": {"kind": "part", "id": "D", "path": CONTENT_DIR / "parts" / "part_d.md"},
    "Appendix 1": {
        "kind": "appendix",
        "id": "1",
        "path": CONTENT_DIR / "appendices" / "appendix_1_one_health.md",
    },
    "Appendix 2": {
        "kind": "appendix",
        "id": "2",
        "path": CONTENT_DIR / "appendices" / "appendix_2_anthrax_fact_sheet.md",
    },
    "Appendix 3": {
        "kind": "appendix",
        "id": "3",
        "path": CONTENT_DIR / "appendices" / "appendix_3_line_list.md",
    },
}


@st.cache_data
def load_items(path: Path) -> dict[str, Any] | None:
    try:
        with path.open("r", encoding="utf-8") as file:
            return json.load(file)
    except FileNotFoundError:
        return None
    except json.JSONDecodeError as err:
        st.error(f"Could not parse JSON file: {path}. Error: {err}")
        return None


@st.cache_data
def load_markdown(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return None


def render_instructor_mode(details: Any) -> None:
    with st.expander("Instructor notes", expanded=False):
        if details is None:
            st.info("No instructor notes available for this question.")
        elif isinstance(details, (dict, list)):
            st.json(details)
        else:
            st.write(details)


def render_item(item: dict[str, Any], instructor_mode: bool) -> None:
    item_id = item.get("id", "unknown_id")
    item_type = item.get("type", "short_text")
    prompt = item.get("prompt", "")

    st.subheader(f"{item_id}")
    if prompt:
        st.markdown(prompt)

    if item_type in {"short_text", "discussion", "reflection", "annotation"}:
        st.session_state[item_id] = st.text_area(
            "Response",
            key=f"input__{item_id}",
            value=st.session_state.get(item_id, ""),
            height=120,
        )
    elif item_type == "timeline_entry":
        st.session_state[item_id] = st.text_input(
            "Response",
            key=f"input__{item_id}",
            value=st.session_state.get(item_id, ""),
        )
    elif item_type == "table_calc":
        default_df = pd.DataFrame({"Input": ["", ""], "Value": [0, 0]})
        editor_key = f"editor__{item_id}"
        if editor_key not in st.session_state:
            st.session_state[editor_key] = default_df

        edited_df = st.data_editor(
            st.session_state[editor_key],
            key=f"data_editor__{item_id}",
            use_container_width=True,
            num_rows="dynamic",
        )
        st.session_state[editor_key] = edited_df

        if st.button("Compute", key=f"compute__{item_id}"):
            st.session_state[f"{item_id}__computed_result"] = {
                "status": "computed",
                "rows": len(edited_df),
                "columns": list(edited_df.columns),
            }

        if f"{item_id}__computed_result" in st.session_state:
            st.success("Computed result saved in session state.")
            st.json(st.session_state[f"{item_id}__computed_result"])

        st.session_state[item_id] = edited_df.to_dict(orient="records")
    else:
        st.session_state[item_id] = st.text_area(
            "Response",
            key=f"input__{item_id}",
            value=st.session_state.get(item_id, ""),
            height=120,
        )

    if instructor_mode:
        render_instructor_mode(item.get("instructor_mode"))

    st.divider()


def collect_responses(items: list[dict[str, Any]]) -> dict[str, Any]:
    responses: dict[str, Any] = {}
    for item in items:
        item_id = item.get("id")
        if item_id:
            responses[item_id] = st.session_state.get(item_id, "")
            computed_key = f"{item_id}__computed_result"
            if computed_key in st.session_state:
                responses[computed_key] = st.session_state[computed_key]
    return responses


def main() -> None:
    st.set_page_config(page_title="Anthrax Case Study", layout="wide")

    items_payload = load_items(ITEMS_PATH)
    if items_payload is None:
        st.error(
            "Unable to load module metadata and items from content/items.json. "
            "Please verify that the file exists and is valid JSON."
        )
        return

    module_title = items_payload.get("title", "Case Study Module")
    module_id = items_payload.get("module_id", "")
    module_version = items_payload.get("version", "")
    all_items = items_payload.get("items", [])

    st.title(module_title)
    if module_id or module_version:
        st.caption(f"Module ID: {module_id} | Version: {module_version}")

    with st.sidebar:
        st.header("Navigation")
        section = st.radio("Select section", list(SECTION_CONFIG.keys()), index=0)
        instructor_mode = st.toggle("Instructor Mode", value=False)

        if st.button("Reset responses", use_container_width=True):
            for item in all_items:
                item_id = item.get("id")
                if not item_id:
                    continue
                st.session_state.pop(item_id, None)
                st.session_state.pop(f"input__{item_id}", None)
                st.session_state.pop(f"editor__{item_id}", None)
                st.session_state.pop(f"data_editor__{item_id}", None)
                st.session_state.pop(f"{item_id}__computed_result", None)
                st.session_state.pop(f"compute__{item_id}", None)
            st.success("Responses reset.")

        responses_json = json.dumps(collect_responses(all_items), indent=2, ensure_ascii=False)
        st.download_button(
            "Download responses",
            data=responses_json,
            file_name="anthrax_case_study_responses.json",
            mime="application/json",
            use_container_width=True,
        )

    section_cfg = SECTION_CONFIG[section]
    markdown_content = load_markdown(section_cfg["path"])

    if markdown_content is None:
        st.error(f"Section content file is missing: {section_cfg['path'].relative_to(BASE_DIR)}")
    elif not markdown_content.strip():
        st.info("This section has no markdown content yet.")
    else:
        st.markdown(markdown_content)

    if section_cfg["kind"] == "part":
        selected_part = section_cfg["id"]
        part_items = [item for item in all_items if str(item.get("part", "")).upper() == selected_part]

        if not part_items:
            st.warning(f"No questions found for Part {selected_part}.")
        else:
            st.header(f"Questions - Part {selected_part}")
            for item in part_items:
                render_item(item, instructor_mode=instructor_mode)


if __name__ == "__main__":
    main()
