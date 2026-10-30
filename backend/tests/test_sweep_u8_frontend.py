"""U8 sweep: source-level regression checks for frontend/index.html fixes.

Each test pins one verified browser defect. The behaviour itself was checked in a
real browser against a live backend; these guard the code shape that fixed it.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

INDEX = Path(__file__).resolve().parents[2] / "frontend" / "index.html"


@pytest.fixture(scope="module")
def html() -> str:
    return INDEX.read_text(encoding="utf-8")


def _function_body(html: str, name: str) -> str:
    start = html.index(f"function {name}(")
    nxt = re.search(r"\n(?:async )?function \w+\(", html[start + 10:])
    return html[start: start + 10 + nxt.start()] if nxt else html[start:]


def test_insights_rating_icons_are_interpolated_not_literal(html):
    # '${_thumbUpIcon}' inside quotes inside a template expression rendered literally.
    assert "'${_thumbUpIcon}'" not in html
    assert "'${_thumbDownIcon}'" not in html
    assert "fb.rating === 'up' ? _thumbUpIcon :" in html


def test_extracted_upload_is_submitted_as_plain_text(html):
    submit = _function_body(html, "submitEnrichment")
    assert "needsServerExtraction(uploadedFilename)" in submit
    assert "body.format = 'plain_text'" in submit
    assert "plain_text" in (INDEX.parents[1] / "backend" / "app" / "models" / "document.py").read_text()


def test_legacy_doc_upload_not_offered(html):
    accept = re.search(r'id="fileInput" accept="([^"]+)"', html).group(1).split(",")
    assert ".doc" not in accept and ".docx" in accept


def test_dropped_legacy_doc_goes_to_extraction(html):
    # A drag-and-dropped .doc is sent to /enrich/extract as base64 so the
    # backend's 400 ("save as .docx") reaches the editor, not file.text() garbage.
    binary = re.search(r"const EXTRACT_BINARY_EXTS = \[([^\]]+)\]", html).group(1)
    assert "'doc'" in binary and "'docx'" in binary
    process = _function_body(html, "processFile")
    assert "ta.placeholder = `Could not extract text from ${file.name}: ${e.message}`" in process
    assert "err.detail" in process


def test_leaving_demo_clears_results_and_header(html):
    assert "if (isDemoMode) exitDemoMode({ clearResults: true });" in _function_body(html, "submitEnrichment")
    assert "exitDemoMode({ clearResults: true })" in _function_body(html, "toggleDemoMode")
    clear = _function_body(html, "clearResultsOnly")
    assert "hideDocTypeBanner();" in clear
    assert "triTab.textContent = 'Triples'" in clear


def test_skipped_llm_stages_render_as_skipped(html):
    assert "const PPL_LLM_ONLY = new Set(['identifying', 'judging']);" in html
    assert ".ppl-step.skipped .ppl-node" in html
    # Keyless = the LLM station logged nothing (a silent judge on an LLM run isn't "skipped").
    assert "this.stageMessages('identifying').length === 0 && this.stageMessages(key).length === 0" in html
    assert "markSkipped()" in _function_body(html, "renderResults")
    assert "skipped — no AI provider for this run" in html


def test_lineage_skips_fetch_for_unknown_annotation(html):
    body = _function_body(html, "renderDetailLineage")
    guard = body.index("accumulatedAnnotations.some(a => a.id === annId)")
    assert guard < body.index("/lineage`")
    assert "No pipeline lineage recorded for this link." in body


def test_result_tabs_are_an_accessible_wrapping_tablist(html):
    assert '<div class="tabs" role="tablist"' in html
    tabs = re.findall(r'<div class="tab(?: active)?" data-tab="\w+"[^>]*>', html)
    assert len(tabs) == 9
    for tab in tabs:
        assert 'role="tab"' in tab and "tabindex=" in tab and "aria-selected=" in tab
    css = html[html.index("  .tabs {"): html.index("  .tab {")]
    assert "flex-wrap: wrap" in css
    assert "::-webkit-scrollbar { width: 5px; height: 5px; }" in html
    assert "setAttribute('aria-selected', 'true')" in _function_body(html, "switchTab")
    assert "e.key === 'Enter' || e.key === ' '" in html[html.index('.tabs[role="tablist"]\')'):]


def test_demo_title_persisted_across_reload(html):
    assert "_demoMeta: currentDemoMeta" in _function_body(html, "cacheState")
    assert "currentDemoMeta = meta || null;" in _function_body(html, "hydrateFromDemo")
    assert "currentDemoMeta.title" in _function_body(html, "syncOntologyUI")


def test_escape_closes_every_modal(html):
    handler = html[html.index("// Close modals on Escape"):]
    handler = handler[: handler.index("\n});") ]
    for modal, closer in [("settingsModal", "closeSettings"), ("syntheticModal", "closeSynthetic"),
                          ("ollamaWizardModal", "closeOllamaWizard"), ("folioModal", "closeFolioModal"),
                          ("graphModal", "closeGraphModal")]:
        assert f"['{modal}', {closer}]" in handler


def test_export_copy_count_and_distinct_filenames(html):
    assert "12 supported formats" not in html
    n_formats = len(re.findall(r"\{ name: '\w+', label: ", html[html.index("const EXPORT_FORMATS"):html.index("const SAMPLES")]))
    assert n_formats == 13
    assert f'id="exportFormatCount">{n_formats}<' in html
    body = _function_body(html, "exportFormat")
    assert "const suffix = ext === `.${format}` ? '' : `-${format}`;" in body
    assert "${suffix}${ext}" in body


def test_concepts_summary_ignores_individual_only_branches(html):
    body = _function_body(html, "renderConceptsTabTree")
    assert "filter(([, b]) => b.conceptCount > 0)" in body


def test_demo_badge_does_not_cover_short_labels(html):
    assert "#demoExemplarsCanon.demo-mode .sample-btn { border-color: var(--accent); padding-right: 30px; }" in html


def test_ollama_post_routes_not_opened_with_eventsource(html):
    assert not re.search(r"new EventSource\(`\$\{API\}/ollama", html)
    assert "fetch(`${API}/ollama/setup`, { method: 'POST' })" in html
    assert "async function readSSEStream(" in html


def test_admin_feedback_actions_gated_and_403_explained(html):
    assert "${_requireUserKey ? '' : `<button class=\"small secondary\" onclick=\"exportFeedback('json')\">" in html
    for name in ("exportFeedback", "clearAllFeedback"):
        body = _function_body(html, name)
        assert "resp.status === 403" in body and "Admin only on this server" in body
