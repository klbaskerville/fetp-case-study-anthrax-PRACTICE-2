import json
import re
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st

from instructor_gate import instructor_gate_ui, instructor_mode_enabled

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


def inject_css() -> None:
    st.markdown(
        """
        <style>
          .stApp {
            background: radial-gradient(circle at 20% 0%, #eaf2ff 0%, #f7fbff 35%, #f8fafc 100%);
          }
          .view-banner {
            padding: 0.8rem 1rem;
            border-radius: 0.8rem;
            border: 1px solid rgba(30, 58, 138, 0.2);
            background: #eff6ff;
            font-weight: 700;
            margin-bottom: 1rem;
          }
          .participant-banner {
            border-color: rgba(100, 116, 139, 0.35);
            background: #f8fafc;
          }
          .main-shell {
            border-radius: 1rem;
            border: 1px solid #dbe4ee;
            background: #ffffffd8;
            padding: 0.6rem;
            box-shadow: 0 10px 30px rgba(15, 23, 42, 0.06);
          }
          .section-chip {
            border-radius: 0.6rem;
            border: 1px solid #d7dee8;
            padding: 0.35rem 0.55rem;
            margin-bottom: 0.35rem;
            background: #ffffff;
            font-size: 0.9rem;
          }
          .section-active {
            background: #eff6ff;
            border-color: #93c5fd;
            font-weight: 700;
          }
          .section-complete {
            background: #ecfdf3;
            border-color: #86efac;
          }
          .question-callout {
            background: #fffbeb;
            border-left: 6px solid #f59e0b;
            border-radius: 0.65rem;
            padding: 0.65rem 0.8rem;
            margin-bottom: 0.6rem;
          }
          .question-callout.active {
            box-shadow: 0 0 0 2px #fde68a inset;
          }
          .placeholder-hint {
            color: #92400e;
            background: #fef3c7;
            border: 1px dashed #f59e0b;
            border-radius: 0.5rem;
            padding: 0.5rem 0.6rem;
            margin: 0.35rem 0;
            font-size: 0.9rem;
          }
          .guide-panel {
            border-left: 4px solid #64748b;
            background: #f8fafc;
            border-radius: 0.65rem;
            padding: 0.65rem 0.8rem;
            height: 100%;
          }
          .toc-box {
            background: #f8fafc;
            border: 1px solid #e2e8f0;
            border-radius: 0.7rem;
            padding: 0.7rem 0.8rem;
            margin-bottom: 0.8rem;
          }
        </style>
        """,
        unsafe_allow_html=True,
    )


def normalize_placeholder_id(raw_id: str) -> str:
    token = re.sub(r"\s+", "_", raw_id.strip())
    if re.fullmatch(r"[Qq](\d+[A-Za-z]?)", token):
        return f"Question_{re.sub(r'[Qq]', '', token, count=1)}"
    question_match = re.fullmatch(r"[Qq]uestion[_ ]?(\d+[A-Za-z]?)", raw_id.strip())
    if question_match:
        return f"Question_{question_match.group(1)}"
    if re.fullmatch(r"Question_\d+[A-Za-z]?", token):
        return token
    return token


def slugify(text: str) -> str:
    s = re.sub(r"[^a-zA-Z0-9\s-]", "", text).strip().lower()
    return re.sub(r"[\s_-]+", "-", s)


@st.cache_data
def load_items_json(path: str) -> dict[str, Any]:
    with Path(path).open("r", encoding="utf-8") as f:
        return json.load(f)


@st.cache_data
def load_markdown(path: str) -> str:
    return Path(path).read_text(encoding="utf-8")


def init_state() -> None:
    defaults = {
        "nav_mode": "Guided (Next/Back)",
        "guided_idx": 0,
        "jump_section": "Part 0",
        "appendix_selection": "Appendix 1",
        "include_appendices_guided": False,
        "show_all_questions": False,
        "active_qid": None,
    }
    for key, val in defaults.items():
        st.session_state.setdefault(key, val)


def extract_placeholders(md_text: str) -> list[str]:
    return [normalize_placeholder_id(m.group(1)) for m in PLACEHOLDER_PATTERN.finditer(md_text)]


def question_number(qid: str) -> str:
    m = re.match(r"Question_(.+)", qid)
    return m.group(1) if m else qid


def is_answered(qid: str) -> bool:
    resp = st.session_state.get(f"resp_{qid}")
    done = bool(st.session_state.get(f"done_{qid}", False))
    computed = st.session_state.get(f"computed_{qid}") is not None
    if isinstance(resp, str):
        has_resp = bool(resp.strip())
    elif isinstance(resp, (list, dict)):
        has_resp = len(resp) > 0
    else:
        has_resp = resp is not None
    return done or has_resp or computed


def response_preview(qid: str) -> str:
    resp = st.session_state.get(f"resp_{qid}")
    if resp is None:
        return ""
    if isinstance(resp, str):
        txt = resp.strip()
        return txt[:120] + ("…" if len(txt) > 120 else "")
    if isinstance(resp, list):
        return f"{len(resp)} row(s)"
    if isinstance(resp, dict):
        return f"{len(resp)} key(s)"
    return str(resp)


def validate_items(payload: dict[str, Any]) -> list[str]:
    errors = []
    for key in ["module_id", "title", "items"]:
        if key not in payload:
            errors.append(f"Missing top-level key: {key}")
    items = payload.get("items")
    if not isinstance(items, list):
        errors.append("items must be a list")
        return errors
    for i, item in enumerate(items, start=1):
        if not isinstance(item, dict):
            errors.append(f"Item #{i} is not an object")
            continue
        for req in ["id", "type", "prompt"]:
            if req not in item:
                errors.append(f"Item #{i} missing {req}")
    return errors


def build_part_items(all_items: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    mapping = {letter: [] for letter in PART_LETTERS}
    for item in all_items:
        part = str(item.get("part", "")).upper()
        if part in mapping:
            mapping[part].append(item)
    return mapping


def build_guided_steps(part_placeholders: dict[str, list[str]], include_appendices: bool) -> list[dict[str, str | None]]:
    steps: list[dict[str, str | None]] = [{"section": "Part 0", "question_id": None}]
    for part in ["Part A", "Part B", "Part C", "Part D"]:
        ids = part_placeholders.get(part, [])
        if ids:
            for qid in ids:
                steps.append({"section": part, "question_id": qid})
        else:
            steps.append({"section": part, "question_id": None})
    if include_appendices:
        for appendix in APPENDIX_FILES:
            steps.append({"section": appendix, "question_id": None})
    return steps


def render_facilitator_panel(instr: dict[str, Any]) -> None:
    st.markdown("<div class='guide-panel'>", unsafe_allow_html=True)
    st.markdown("#### 📌 Facilitator Guide")
    if not instr:
        st.caption("No facilitator guidance for this question.")
        st.markdown("</div>", unsafe_allow_html=True)
        return

    consumed: set[str] = set()

    before = instr.get("facilitator_pre_prompts")
    if before:
        consumed.add("facilitator_pre_prompts")
        st.markdown("**🧠 Before you ask**")
        values = before if isinstance(before, list) else [before]
        for v in values:
            st.markdown(f"- {v}")

    defs = instr.get("reference_definitions")
    if defs:
        consumed.add("reference_definitions")
        st.markdown("**🗝️ Key definitions**")
        if isinstance(defs, dict):
            for k, v in defs.items():
                st.markdown(f"- **{k}**: {v}")
        elif isinstance(defs, list):
            for entry in defs:
                st.markdown(f"- {entry}")
        else:
            st.markdown(str(defs))

    model = instr.get("model_answer")
    if model:
        consumed.add("model_answer")
        st.markdown("**✅ Suggested response**")
        st.success(model if isinstance(model, str) else json.dumps(model, ensure_ascii=False, indent=2))

    rubric = instr.get("rubric_keywords")
    if rubric:
        consumed.add("rubric_keywords")
        tags = rubric if isinstance(rubric, list) else [rubric]
        st.markdown("**🏷️ Rubric keywords**")
        st.markdown(" ".join(f"`{t}`" for t in tags))

    notes = instr.get("notes")
    if notes:
        consumed.add("notes")
        st.markdown("**📝 Facilitation notes**")
        if isinstance(notes, list):
            for n in notes:
                st.markdown(str(n))
        else:
            st.markdown(str(notes).replace("\n", "  \n"))

    extra = {k: v for k, v in instr.items() if k not in consumed}
    if extra:
        with st.expander("More instructor content", expanded=False):
            for k, v in extra.items():
                st.markdown(f"**{k.replace('_', ' ').title()}**")
                if isinstance(v, (dict, list)):
                    st.write(v)
                else:
                    st.markdown(str(v))
    st.markdown("</div>", unsafe_allow_html=True)


def render_input_widget(item: dict[str, Any]) -> None:
    qid = item["id"]
    qtype = item.get("type", "short_text")
    resp_key = f"resp_{qid}"
    done_key = f"done_{qid}"
    comp_key = f"computed_{qid}"

    if qtype in {"short_text", "discussion", "reflection", "annotation"}:
        st.session_state[resp_key] = st.text_area(
            "Your response",
            value=st.session_state.get(resp_key, ""),
            key=f"text_{qid}",
            height=130,
        )
    elif qtype == "timeline_entry":
        st.session_state[resp_key] = st.text_input(
            "Timeline entry",
            value=st.session_state.get(resp_key, ""),
            key=f"timeline_{qid}",
        )
    elif qtype == "table_calc":
        df_key = f"editor_{qid}"
        if df_key not in st.session_state:
            st.session_state[df_key] = pd.DataFrame(
                {"Metric": ["", "", ""], "Value": [0.0, 0.0, 0.0], "Notes": ["", "", ""]}
            )
        edited = st.data_editor(st.session_state[df_key], key=f"table_{qid}", num_rows="dynamic", use_container_width=True)
        st.session_state[df_key] = edited
        st.session_state[resp_key] = edited.to_dict(orient="records")
        if st.button("Compute", key=f"compute_{qid}"):
            numeric = edited.select_dtypes(include="number")
            st.session_state[comp_key] = {
                "rows": int(len(edited)),
                "numeric_column_totals": {c: float(numeric[c].fillna(0).sum()) for c in numeric.columns},
            }
        if st.session_state.get(comp_key) is not None:
            st.info(f"Computed: {st.session_state[comp_key]}")
    else:
        st.session_state[resp_key] = st.text_area(
            "Your response",
            value=st.session_state.get(resp_key, ""),
            key=f"fallback_{qid}",
            height=130,
        )

    st.session_state[done_key] = st.checkbox("Mark as complete", key=f"donebox_{qid}", value=bool(st.session_state.get(done_key, False)))


def render_question(item: dict[str, Any], instructor_on: bool, active: bool = False) -> None:
    qid = item["id"]
    state_icon = "✅" if is_answered(qid) else "⏳"
    active_cls = " active" if active else ""
    with st.container(border=True):
        st.markdown(
            f"<div class='question-callout{active_cls}'><strong>⚠️ Question {question_number(qid)}</strong> "
            f"<span style='opacity:0.8'>({state_icon})</span></div>",
            unsafe_allow_html=True,
        )
        if instructor_on:
            left, right = st.columns([1.35, 1], vertical_alignment="top")
            with left:
                st.markdown(item.get("prompt", ""))
                render_input_widget(item)
            with right:
                render_facilitator_panel(item.get("instructor_mode", {}))
        else:
            st.markdown(item.get("prompt", ""))
            render_input_widget(item)


def render_embedded_markdown(
    md_text: str,
    items_by_id: dict[str, dict[str, Any]],
    instructor_on: bool,
    visible_qids: set[str] | None,
    active_qid: str | None,
) -> None:
    last = 0
    for match in PLACEHOLDER_PATTERN.finditer(md_text):
        narrative = md_text[last:match.start()]
        if narrative.strip():
            st.markdown(narrative)

        raw_id = match.group(1)
        qid = normalize_placeholder_id(raw_id)
        item = items_by_id.get(qid)

        if item is None:
            st.warning(f"Placeholder '{qid}' found in markdown but missing in items.json.")
        elif visible_qids is not None and qid not in visible_qids:
            st.markdown("<div class='placeholder-hint'>Continue with Next…</div>", unsafe_allow_html=True)
        else:
            render_question(item, instructor_on=instructor_on, active=(qid == active_qid))

        last = match.end()

    tail = md_text[last:]
    if tail.strip():
        st.markdown(tail)


def render_front_matter_toc(items_payload: dict[str, Any]) -> None:
    st.markdown("<div class='toc-box'>", unsafe_allow_html=True)
    st.markdown("**Front Matter Navigation**")
    listed_parts = items_payload.get("parts")
    if isinstance(listed_parts, list) and listed_parts:
        for part in listed_parts:
            label = f"Part {part.get('part_id', '').strip()} — {part.get('title', '').strip()}"
            st.markdown(f"- [{label}](#{slugify(label)})")
    else:
        for p in PART_ORDER:
            st.markdown(f"- [{p}](#{slugify(p)})")
    for appendix in APPENDIX_FILES:
        st.markdown(f"- [{appendix}](#{slugify(appendix)})")
    st.markdown("</div>", unsafe_allow_html=True)


def section_complete(section: str, part_items: dict[str, list[dict[str, Any]]]) -> bool:
    if not section.startswith("Part ") or section == "Part 0":
        return False
    letter = section.split(" ")[-1]
    items = part_items.get(letter, [])
    return bool(items) and all(is_answered(it["id"]) for it in items)


def jump_to_question(qid: str, nav_mode: str, guided_steps: list[dict[str, str | None]], items_by_id: dict[str, dict[str, Any]]) -> None:
    st.session_state["active_qid"] = qid
    if nav_mode == "Guided (Next/Back)":
        for idx, step in enumerate(guided_steps):
            if step.get("question_id") == qid:
                st.session_state["guided_idx"] = idx
                break
    else:
        part = str(items_by_id.get(qid, {}).get("part", "")).upper()
        st.session_state["jump_section"] = f"Part {part}" if part in PART_LETTERS else "Part 0"


def main() -> None:
    st.set_page_config(page_title="Anthrax Case Study", layout="wide")
    inject_css()
    init_state()

    try:
        items_payload = load_items_json(str(ITEMS_JSON_PATH))
    except FileNotFoundError:
        st.error("Missing required file: content/items.json")
        st.stop()
    except json.JSONDecodeError as exc:
        st.error(f"Invalid JSON in content/items.json: {exc}")
        st.stop()

    issues = validate_items(items_payload)
    if issues:
        st.error("items.json failed validation")
        for issue in issues:
            st.write(f"- {issue}")
        st.stop()

    all_items: list[dict[str, Any]] = items_payload["items"]
    items_by_id = {item["id"]: item for item in all_items}
    part_items = build_part_items(all_items)

    part_markdown: dict[str, str | None] = {}
    part_placeholders: dict[str, list[str]] = {}
    for section, path in PART_FILES.items():
        try:
            text = load_markdown(str(path))
            part_markdown[section] = text
            part_placeholders[section] = extract_placeholders(text)
        except FileNotFoundError:
            part_markdown[section] = None
            part_placeholders[section] = []

    appendix_markdown: dict[str, str | None] = {}
    for appendix, path in APPENDIX_FILES.items():
        try:
            appendix_markdown[appendix] = load_markdown(str(path))
        except FileNotFoundError:
            appendix_markdown[appendix] = None

    guided_steps = build_guided_steps(part_placeholders, st.session_state["include_appendices_guided"])
    st.session_state["guided_idx"] = min(st.session_state["guided_idx"], max(0, len(guided_steps) - 1))

    total = sum(len(part_items[l]) for l in PART_LETTERS)
    answered = sum(1 for l in PART_LETTERS for item in part_items[l] if is_answered(item["id"]))
    pct = answered / total if total else 0.0

    st.markdown("<div class='main-shell'>", unsafe_allow_html=True)
    st.title(items_payload.get("title", "Anthrax Case Study"))
    if instructor_mode_enabled():
        st.markdown("<div class='view-banner'>🔓 Instructor View</div>", unsafe_allow_html=True)
    else:
        st.markdown("<div class='view-banner participant-banner'>🔒 Participant View</div>", unsafe_allow_html=True)

    with st.sidebar:
        instructor_gate_ui(help_text="Unlock instructor mode to view facilitator guidance.")
        st.session_state["nav_mode"] = st.radio(
            "Navigation",
            ["Guided (Next/Back)", "Jump to Section"],
            index=0 if st.session_state["nav_mode"] == "Guided (Next/Back)" else 1,
        )
        if st.session_state["nav_mode"] == "Guided (Next/Back)":
            st.session_state["include_appendices_guided"] = st.checkbox(
                "Include appendices in guided flow",
                value=bool(st.session_state["include_appendices_guided"]),
            )
            st.session_state["show_all_questions"] = st.checkbox(
                "Show all questions in this part",
                value=bool(st.session_state["show_all_questions"]),
            )

        st.markdown("### Sections")
        active_section = (
            guided_steps[st.session_state["guided_idx"]]["section"]
            if st.session_state["nav_mode"] == "Guided (Next/Back)"
            else st.session_state["jump_section"]
        )
        for section in PART_ORDER:
            classes = ["section-chip"]
            icon = "✅" if section_complete(section, part_items) else "⏳"
            if section == "Part 0":
                icon = "📖"
            if section == active_section:
                classes.append("section-active")
            if section_complete(section, part_items):
                classes.append("section-complete")
            st.markdown(f"<div class='{' '.join(classes)}'>{icon} {section}</div>", unsafe_allow_html=True)

        if st.button("Reload content (clear cache)", use_container_width=True):
            st.cache_data.clear()
            st.rerun()

    learn_tab, review_tab, appendices_tab = st.tabs(["Learn & Respond", "Review Answers", "Appendices"])

    with learn_tab:
        st.progress(pct, text=f"Progress (Parts A–D): {answered}/{total}")

        if st.session_state["nav_mode"] == "Jump to Section":
            section = st.selectbox("Jump to section", PART_ORDER, key="jump_section")
            md = part_markdown.get(section)
            if section == "Part 0":
                render_front_matter_toc(items_payload)

            if md is None:
                st.error(f"Missing markdown for {section}: {PART_FILES[section].relative_to(BASE_DIR)}")
                letter = section.split(" ")[-1]
                for item in part_items.get(letter, []):
                    render_question(item, instructor_mode_enabled(), active=(item["id"] == st.session_state.get("active_qid")))
            else:
                render_embedded_markdown(md, items_by_id, instructor_mode_enabled(), None, st.session_state.get("active_qid"))

        else:
            guided_steps = build_guided_steps(part_placeholders, st.session_state["include_appendices_guided"])
            max_idx = max(0, len(guided_steps) - 1)
            st.session_state["guided_idx"] = min(st.session_state["guided_idx"], max_idx)
            step = guided_steps[st.session_state["guided_idx"]]
            section = str(step["section"])
            current_qid = step.get("question_id")
            st.session_state["active_qid"] = current_qid

            if section == "Part 0":
                render_front_matter_toc(items_payload)

            md = part_markdown.get(section) if section in PART_FILES else appendix_markdown.get(section)
            missing_path = PART_FILES.get(section, APPENDIX_FILES.get(section))

            if md is None:
                st.error(f"Missing markdown for {section}: {missing_path.relative_to(BASE_DIR)}")
                if section.startswith("Part ") and section != "Part 0":
                    letter = section.split(" ")[-1]
                    for item in part_items.get(letter, []):
                        if st.session_state["show_all_questions"] or item["id"] == current_qid:
                            render_question(item, instructor_mode_enabled(), active=(item["id"] == current_qid))
            else:
                visible_qids = None
                if section.startswith("Part ") and section != "Part 0" and current_qid and not st.session_state["show_all_questions"]:
                    visible_qids = {current_qid}
                render_embedded_markdown(md, items_by_id, instructor_mode_enabled(), visible_qids, current_qid)

            c1, c2, c3 = st.columns([1, 1, 1])
            with c1:
                if st.button("⬅️ Previous", disabled=st.session_state["guided_idx"] <= 0, use_container_width=True):
                    st.session_state["guided_idx"] = max(0, st.session_state["guided_idx"] - 1)
                    st.rerun()
            with c2:
                st.markdown(
                    f"<div style='text-align:center;padding-top:0.45rem;font-weight:600;'>Step {st.session_state['guided_idx'] + 1} / {len(guided_steps)}</div>",
                    unsafe_allow_html=True,
                )
            with c3:
                if st.button("Next ➡️", disabled=st.session_state["guided_idx"] >= max_idx, use_container_width=True):
                    st.session_state["guided_idx"] = min(max_idx, st.session_state["guided_idx"] + 1)
                    st.rerun()

    with review_tab:
        st.subheader("Review Answers")
        for item in all_items:
            qid = item["id"]
            with st.container(border=True):
                c1, c2, c3, c4 = st.columns([1.6, 4, 1, 1.4])
                c1.markdown(f"**{qid}**")
                c1.caption("✅ answered" if is_answered(qid) else "⏳ pending")
                c2.caption(response_preview(qid) or "No response yet")
                if c3.button("Go", key=f"go_{qid}"):
                    jump_to_question(qid, st.session_state["nav_mode"], guided_steps, items_by_id)
                    st.rerun()
                if instructor_mode_enabled():
                    if c4.button("Show model answer", key=f"model_{qid}"):
                        model = item.get("instructor_mode", {}).get("model_answer")
                        if model:
                            st.info("Suggested response")
                            st.success(model if isinstance(model, str) else json.dumps(model, ensure_ascii=False, indent=2))
                        else:
                            st.caption("No model answer provided.")

    with appendices_tab:
        appendix = st.selectbox("Select appendix", list(APPENDIX_FILES.keys()), key="appendix_selection")
        text = appendix_markdown.get(appendix)
        if text is None:
            st.error(f"Missing markdown for {appendix}: {APPENDIX_FILES[appendix].relative_to(BASE_DIR)}")
        else:
            render_embedded_markdown(text, items_by_id, instructor_mode_enabled(), None, st.session_state.get("active_qid"))

    st.markdown("</div>", unsafe_allow_html=True)


if __name__ == "__main__":
    main()
