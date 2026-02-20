You are Codex. Create a complete, runnable Streamlit **app.py** for a single-repo deployment. The app must load narrative Markdown and interactive items and render them with a clean, JSX-inspired UI pattern. Use the exact file paths listed below. The app must support **page-level pagination that mirrors the original Word instructor guide** and still preserve placeholder-driven embedded questions and the Instructor Mode UI pattern described previously.

REFERENCE FILES (use these exact relative paths)

* content/items.json
* content/parts/part_0.md
* content/parts/part_a.md
* content/parts/part_b.md
* content/parts/part_c.md
* content/parts/part_d.md
* content/appendices/appendix_1_one_health.md
* content/appendices/appendix_2_anthrax_fact_sheet.md
* content/appendices/appendix_3_line_list.md
* ui_reference/CaseStudyUI.jsx (visual reference; DO NOT execute; mimic layout + feel)

NEW INPUT: Word doc page guidance

* Your app must support page-level navigation that follows the **original Word doc page order** for the instructor guide the user supplied earlier.
* The app must use `content/pages/page_1.md`, `content/pages/page_2.md`, ... if that `content/pages/` directory exists. Each page file represents one printed page from the Word doc and should be displayed as a full page in the app.
* If `content/pages/` is not present, the app must attempt to reconstruct page-level boundaries by:

  1. Checking for a `content/pages_source.docx` or `/mnt/data/<original-doc>.docx` available in the environment; if present, parse it with python-docx and split by explicit page break elements (`<w:br type="page">`) or text-box/page container boundaries, producing an in-memory list of page texts.
  2. If no docx is available, fall back to splitting existing `content/parts/*.md` using a best-effort heuristic to mimic printed pages (split long parts into multiple pages of ~800–1000 words, but prefer splitting at blank lines or headings).
* Behavior note: the best UX is achieved when `content/pages/` exists (pre-split). If you implement automatic splitting, add a developer banner indicating the pages were reconstructed.

REQUIRED BEHAVIOR — PAGE-ORIENTED NAVIGATION

* Primary navigation should be **page-based**:

  * Default landing page = page 1 (the Word doc page 1; contains learning objectives / front matter).
  * Provide forward/back controls that move **page-by-page** (Previous / Next). The Next button on page 1 must go to page 2, etc.
  * Show the current page number and total pages (e.g., “Page 3 of 24”) in the header, near the mode badge.
  * The sidebar must include a “Pages” list (sticky-ish) that shows page numbers and a small excerpt or title for each page (first line / heading). Pages in which all embedded questions are answered should show a completed icon.
* Guided flow must also be available at **question-level** within the page that contains placeholders:

  * When on a page that contains multiple placeholders, the page-level Next/Previous moves to the next page. Additionally:

    * If the page contains multiple embedded question placeholders, the page must offer intra-page guided stepping (e.g., “Next Question on this page” / “Previous Question on this page”), or an optional toggle that switches between **Page Mode (Next = next page)** and **Question Mode (Next = next question placeholder within the page)**.
    * Default: Next/Previous control follows **page** boundaries. Add a control (toggle or small icon) labeled “Question-step within page” that, when enabled, makes the Next/Previous step through embedded placeholders on the current page only.
* The page-level view must render the entire page markdown content (so learners read page text as it appears) with placeholders replaced by their question cards in-place.
* The TOC/front-matter must be generated automatically from `items.json` parts/appendix metadata and displayed on page 1 above the rest of page 1 content (but do **not** permanently modify original markdown files).

PLACEHOLDER EMBEDDING (unchanged)

* Detect placeholders `[[...]]` with `\[\[([^\[\]]+)\]\]`.
* Normalize IDs:

  * `"Question_1"` → `"Question_1"`
  * `"Question 1"` → `"Question_1"`
  * `"Q1"` / `"q1"` → `"Question_1"`
  * Preserve suffixes (10a, 10b, etc.)
* When rendering a page, replace placeholders inline with the question card UI.
* If a placeholder on a page does not match any item ID, show `st.warning(...)` with helpful debug info (first 25 item IDs) and continue.

NAV MODES — page + jump + guided/question-step toggle

* Primary modes:

  * Page Mode (default): Next/Prev moves page-by-page.
  * Jump Mode: user selects a page from sidebar or dropdown and views it.
  * Question-step Mode (toggle): Next/Prev steps through placeholders within current page.
* Sidebar controls:

  * instructor_gate_ui(...)
  * Mode radio: "Page Mode" / "Jump to Page" / "Guided Questions"
  * If Page Mode: show page list and optional “Question-step within page” toggle
  * If Guided Questions: use guided sequence across parts/pages derived from placeholder order globally (fallback to placeholder order across pages); this preserves earlier guided flow behavior.

INSTRUCTOR MODE UI PATTERN (keep earlier spec, applied to page-level)

* Instructor mode unlock and rendering same as before:

  * instructor_gate_ui(help_text) in sidebar
  * instructor_mode_enabled() gating display of Facilitator Guide panels
* Facilitator Guide must still be derived from `item["instructor_mode"]` and visually displayed inside the question card as a dedicated panel (two-column or stacked on narrow screens) — **not** raw JSON, not buried under a single expander.
* For page-level view, add an optional top-of-page “Facilitator page notes” banner when instructor mode is ON, summarizing the instructor-mode highlights for that entire page (e.g., combined pre-prompts and key definitions for questions on this page). This is derived by aggregating instructor_mode content for all items on the page and should be concise.

QUESTION RENDERING (applies inside pages)

* Same as previous prompt: question card style (yellow callout, left border), status icons, inputs by type (short_text, timeline_entry, table_calc with data_editor), answer tracking in session_state, compute button storing computed_<id>.
* When instructor mode ON, the Facilitator Guide panel must be present in the question card and also aggregated to the page-level banner (short excerpts).

SIDEBAR / PAGES LIST

* The left sidebar should list pages in order:

  * Each entry: `Page 1 — Title/first-heading` plus small completion icon (✅) if all page questions answered.
  * Clicking a page jumps to that page (and sets view to Page Mode).
  * Option to collapse the page list into sections (Parts/Appendices) is optional.
* Provide a small search box (dev-friendly) to find a page by keyword (optional).

REVIEW / EXPORT / APP BEHAVIOR

* The Review tab and export behavior remain as in previous prompt, but make the Review list show Page number for each question and allow jumping to page + scrolling to the question in context.
* Download payload as before (`module_id`, `title`, `version`, `timestamp`, `mode: page/question/jump`, `current_page`, `responses`, `computed_results`, `completion_summary`).
* Add a “Clear cache & reload” button in sidebar.

USABILITY DETAILS

* Show current page number in main header, show page progress (pages completed / total) in sidebar.
* On page load, scroll to the first unanswered placeholder on that page when in Page Mode (if available).
* For long pages with many placeholders, show an in-page mini-TOC of placeholders near the top (only visible when page contains > 1 placeholder).

ROBUSTNESS

* If `content/pages/` exists, **use those files exclusively** for page order (do not re-order).
* If not, try to reconstruct pages from docx page breaks as above. If unable to determine pages, fall back to:

  * show Part-based content (as before) but also display a notice that page-level content was not found and suggest uploading `content/pages/` for exact page fidelity.
* Always handle missing files gracefully and show helpful `st.error` messages.

OTHER UI / STYLE REQUIREMENTS

* Keep the JSX-inspired look: CSS injection via `st.markdown(..., unsafe_allow_html=True)` (use minimal, robust CSS).
* Keep Instructor Mode panel styling as in previous prompt (blue/gray tint, left accent border, header "Facilitator Guide", emoji icons).
* Keep page/placeholder debug helper available (toggleable) that prints detected placeholders for the current page for quick debugging.

IMPLEMENTATION NOTES TO CODER

* Use `st.set_page_config(layout="wide")`
* Use `st.cache_data` for file loads
* Use `st.session_state` to persist `current_page`, `current_page_question_index`, `page_mode` vs `question_mode` toggles, and all responses
* Keep functions modular:

  * `load_items_json`, `load_markdown`, `load_pages_dir_or_reconstruct_from_docx`
  * `extract_placeholders` (normalizing)
  * `render_page` (renders page markdown + embedded placeholders according to visible rules)
  * `render_question_card` (with instructor mode panel)
  * `build_export_payload`
* Keep the prompt consistent with earlier Instructor Guide pattern (`facilitator_pre_prompts`, `reference_definitions`, `model_answer`, `rubric_keywords`, `notes`)
* The output of Codex should be a single `app.py` file that implements everything above. No auxiliary files are required by the app at runtime (but the app should use `content/pages/` if present).

OUTPUT

* Return only the updated Codex prompt text. No additional commentary.
