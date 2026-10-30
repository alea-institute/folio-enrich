from __future__ import annotations

import html

from app.models.job import Job
from app.services.export.base import ExporterBase
from app.services.export.sanitize import strip_xml_illegal


def _esc(value: str) -> str:
    """HTML-escape text after dropping control characters HTML disallows."""
    return html.escape(strip_xml_illegal(value))


class HTMLExporter(ExporterBase):
    @property
    def format_name(self) -> str:
        return "html"

    @property
    def content_type(self) -> str:
        return "text/html"

    def export(self, job: Job) -> str:
        if job.result.canonical_text is None:
            return "<html><body><p>No content</p></body></html>"

        full_text = job.result.canonical_text.full_text

        # Escape and sanitize per character so list indices stay equal to the
        # document's character offsets (escaping the whole string first turns
        # "&" into five list items and shifts every later tag). Tags are
        # collected per offset and woven in once, so inserting one kind of span
        # never shifts the offsets of another.
        n = len(full_text)
        chars = [_esc(c) for c in full_text]
        # (start, end, seq, tag) per offset; ordered when woven in below.
        opens: list[list[tuple[int, int, int, str]]] = [[] for _ in range(n + 1)]
        closes: list[list[tuple[int, int, int, str]]] = [[] for _ in range(n + 1)]
        seq = 0

        def add_tag(start: int, end: int, open_tag: str, close_tag: str) -> None:
            nonlocal seq
            start = max(0, min(start, n))
            end = max(start, min(end, n))
            opens[start].append((start, end, seq, open_tag))
            closes[end].append((start, end, seq, close_tag))
            seq += 1

        for ann in job.result.annotations:
            if not ann.concepts:
                continue
            concept = ann.concepts[0]
            branch_str = concept.branches[0] if concept.branches else ""
            branch_part = f" ({branch_str})" if branch_str else ""
            tooltip = _esc(
                f"{concept.folio_label or concept.concept_text}"
                f"{branch_part}"
                f" - {concept.folio_definition or 'No definition'}"
            )
            iri = _esc(concept.folio_iri or "#")
            iri_link = f"{iri}/html" if iri != "#" else "#"

            # Confidence-based styling
            conf = concept.confidence
            if conf >= 0.90:
                border_color = "#228B22"  # green
            elif conf >= 0.60:
                border_color = "#FFD700"  # gold
            elif conf >= 0.45:
                border_color = "#FF8C00"  # orange
            else:
                border_color = "#D3D3D3"  # gray

            # Branch color for background tint
            branch_color = concept.branch_color or "#2196F3"

            close_tag = "</a></span>"
            open_tag = (
                f'<span class="folio-annotation" '
                f'style="border-bottom-color: {border_color}; background-color: {branch_color}18;" '
                f'data-iri="{iri}" '
                f'data-branch="{_esc(branch_str)}" '
                f'data-confidence="{concept.confidence:.2f}">'
                f'<a href="{iri_link}" title="{tooltip}" class="folio-link">'
            )

            add_tag(ann.span.start, ann.span.end, open_tag, close_tag)

        # Individual spans (top border style)
        for ind in job.result.individuals:
            class_label = ind.class_links[0].folio_label if ind.class_links else ind.individual_type
            tooltip = _esc(f"{ind.name} ({class_label})")
            conf = ind.confidence
            border_color = "#009688" if ind.individual_type == "legal_citation" else "#FF9800"

            close_tag = "</span>"
            open_tag = (
                f'<span class="folio-individual" '
                f'style="border-top: 2px solid {border_color}; background-color: {border_color}12;" '
                f'data-type="individual" '
                f'data-individual-type="{_esc(ind.individual_type)}" '
                f'title="{tooltip}">'
            )
            add_tag(ind.span.start, ind.span.end, open_tag, close_tag)

        # Property spans (purple wavy underline)
        for prop in job.result.properties:
            label = prop.folio_label or prop.property_text
            tooltip = _esc(f"{label} — {prop.folio_definition or 'OWL ObjectProperty'}")

            close_tag = "</span>"
            open_tag = (
                f'<span class="folio-property" '
                f'style="text-decoration: underline wavy #9C27B0; text-underline-offset: 3px;" '
                f'data-type="property" '
                f'data-iri="{_esc(prop.folio_iri or "#")}" '
                f'title="{tooltip}">'
            )
            add_tag(prop.span.start, prop.span.end, open_tag, close_tag)

        # Nest properly: at an offset the longest span opens first (outermost)
        # and the latest-starting span closes first (innermost). Identical spans
        # keep the old order: one added later wraps the earlier one.
        parts: list[str] = []
        for i in range(n + 1):
            parts.extend(t[3] for t in sorted(closes[i], key=lambda t: (-t[0], t[2])))
            parts.extend(t[3] for t in sorted(opens[i], key=lambda t: (-t[1], -t[2])))
            if i < n:
                parts.append(chars[i])
        body = "".join(parts)

        # Build triples table HTML
        triples_html = ""
        if job.result.triples:
            triples_rows = ""
            for t in job.result.triples:
                has_link = bool(t.subject_links or t.object_links or t.predicate_links)
                link_badge = '<span style="color:#009688;font-weight:bold;">&#x2713;</span>' if has_link else ""
                triples_rows += (
                    f"<tr><td>{_esc(t.subject)}</td>"
                    f"<td><em>{_esc(t.predicate)}</em></td>"
                    f"<td>{_esc(t.object)}</td>"
                    f"<td>{_esc(t.voice)}</td>"
                    f"<td>{t.confidence:.2f}</td>"
                    f"<td>{link_badge}</td></tr>\n"
                )
            triples_html = f"""
<hr>
<h2>Extracted Triples ({len(job.result.triples)})</h2>
<table border="1" cellpadding="4" cellspacing="0" style="border-collapse:collapse;width:100%;font-size:0.9em;">
<tr style="background:#f5f5f5;"><th>Subject</th><th>Predicate</th><th>Object</th><th>Voice</th><th>Confidence</th><th>FOLIO</th></tr>
{triples_rows}</table>"""

        return f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>FOLIO Enrich - Annotated Document</title>
<style>
.folio-annotation {{ background-color: #e8f4fd; border-bottom: 2px solid #2196F3; cursor: pointer; }}
.folio-annotation:hover {{ background-color: #bbdefb; }}
.folio-individual {{ border-top: 2px solid #009688; cursor: pointer; }}
.folio-individual:hover {{ background-color: rgba(0,150,136,0.15); }}
.folio-property {{ text-decoration: underline wavy #9C27B0; cursor: pointer; }}
.folio-property:hover {{ background-color: rgba(156,39,176,0.15); }}
.folio-link {{ color: inherit; text-decoration: none; }}
body {{ font-family: 'Georgia', serif; line-height: 1.6; max-width: 800px; margin: 40px auto; padding: 0 20px; }}
</style>
</head>
<body>
<pre style="white-space: pre-wrap; font-family: inherit;">{body}</pre>
{triples_html}
</body>
</html>"""
