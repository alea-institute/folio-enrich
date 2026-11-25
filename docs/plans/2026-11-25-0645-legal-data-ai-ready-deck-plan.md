# Legal Data That's AI-Ready: Slides Deck Plan

Created: 2026-11-25

## Goal

Build a Claude Slides deck for Damien Riehl's 60-minute session, *Legal Data That's AI-Ready: Standardized data for structured intelligence*, for a South American legal audience: law firms, legal departments, courts, government lawyers, and legal-tech providers. The deck shows the FOLIO tools at work on one FOLIO-rich synthetic document and delivers the session description's five takeaways.

## Settled decisions (from the brainstorm)

| Decision | Choice |
|---|---|
| Format | New Claude Slides artifact, 16:9, English only |
| Length | 60-minute slot including Q&A, so 39 slides and about 44 minutes of talk |
| Look | Reuse the "Agents' Lawful Good" deck's `deck.css`: ink `#15171D`, parchment `#F1E9DA`, brass `#C9A24A`, teal, ox and violet secondaries; Fraunces headings with Lato body; `anim-*` arrival utilities and fragment steps; footer and page numbers off |
| Narrative | Bottom-up: start with FOLIO as it ships, tag, extract, fill the gaps, plug into AI, map legacy taxonomies, then collaborate. A brief persona tour follows |
| Tools with their own slides | FOLIO Enrich, ALEA Intake, FOLIO Insights, ontology-dynamic, FOLIO MCP Server, FOLIO Python, FOLIO Mapper, OntoKit |
| Folded in | FOLIO API and folio-propositions (on the Python/MCP slides); folio-resolve as a one-line "one engine" note at most |
| Excluded | Clio Skills (internal prototype) |
| Firm example | One placeholder slide; Damien switches to another screen. No real firm data, name, or mapping file in the deck |
| Demo material | One synthetic, English, cross-border commercial document with a South American setting, written so nearly every phrase is a FOLIO tag |
| Media | Real screenshots and prerecorded clips captured with Playwright from live or dev instances. No live demos except the firm switch |
| Numbers | Only figures sourced from repos or public pages; every figure carries a source note in the speaker notes |

## Research findings that shape the plan

- **Video works in Slides.** A slide plays an MP4 (H.264) or WebM clip of up to 20 MB, uploaded as an asset with a still frame: `<img src="/_blob/<still>" data-video="/_blob/<clip>">`. It loops while presented, up to four clips per slide, muted by default. Every download shows the still. Plan: one 10–25-second silent loop per tool, plus the still.
- **Images must be uploaded assets** (`/_blob/<id>`); no URLs and no `data:` URIs. Screenshots use `object-fit:contain` on a contrasting card.
- **SVG text never renders in the deck font.** Diagram labels go in `<p>` elements over the SVG.
- **Capture hosts:**

| Tool | Capture from | Note |
|---|---|---|
| FOLIO Enrich | `enrich.openlegalstandard.org` (PROD) | BYOK: needs Damien's own LLM key in the browser; key never captured on screen |
| ALEA Intake | `intake.dev.openlegalstandard.org` | DEV; verify it is up before capture |
| FOLIO Insights | `folio-insights.dev.openlegalstandard.org` | DEV; last commit 2026-10-27 |
| ontology-dynamic | Local `ontdyn` CLI and `ontdyn-viewer` (built in `target/release`) | No public host; a CFAA walkthrough with screenshots exists in `docs/demo/` to model the shots on |
| FOLIO MCP Server | `folio.openlegalstandard.org/mcp`, driven from a Claude session | Capture the conversation, not raw JSON |
| FOLIO Python | Terminal (`pip install folio-python`, short script) | Record a terminal session, rendered to video |
| FOLIO Mapper | `mapper.openlegalstandard.org` | Uses a synthetic demo taxonomy, never the firm's |
| OntoKit | `ontokit.openlegalstandard.org` (fallback `ontokit.dev.openlegalstandard.org`) | Show suggestion, review, and merge |

- **Sourced figures available now:** about 18,300 FOLIO concepts across 24 branches (folio-mapper README); translations on 31% of concepts in 10+ languages, including Spanish and Portuguese (folio-mcp README). Recheck both against the live ontology at build time and cite the date.

## Slide outline (39 slides)

Each act opens with a divider slide (eyebrow, title, pitch line), as in Lawful Good. Each line below is one slide. **Bold** marks a clip slide.

### Act 1: Problem (5 slides, about 5 minutes)
1. **Cover:** title, subtitle, Damien's name and roles: attorney, SALI co-architect, FOLIO tools developer, and Solutions Champion at Clio.
2. **Same matter, five labels:** one dispute as a firm, a court, an agency, a vendor, and a legal department each label it. The five labels pop in, then collapse into one FOLIO IRI on click.
3. **Fragmentation cost:** data can't be shared, compared, or counted across organizations and borders.
4. **AI inherits the mess:** inconsistent labels make retrieval miss and analytics wrong. A before/after card pair with an untagged query and a tagged query (illustrative, labeled as such).
5. **Thesis statement:** "AI-ready means consistently tagged."

### Act 2: Standards (5 slides, about 6 minutes)
6. Divider: *Open standards already exist.*
7. **SALI, FOLIO, noslegal:** who stewards each, how they relate, and that all are open source. A three-card row.
8. **18,000+ tags:** a big-number slide with the sourced count; the 24 branches cascade in as chips (substantive law, business of law, documents, workflows, industries, …).
9. **A graph, not a list:** one concept node with its IRI, parents, children, and Spanish and Portuguese labels. An animated SVG with HTML labels.
10. **Takeaway 1 line:** how the graphs structure and connect legal data.

### Act 3: Bottom-up lifecycle (18 slides, about 22 minutes)
11. Divider: *Start with FOLIO. Fill the gaps.* A loop diagram previews the seven stops.
12. **Demo document:** a still of the synthetic cross-border document, with tag density visible ("nearly every phrase is a tag").
13. **Enrich, tag a document:** clip of the document lighting up with concepts, individuals, properties, and triples.
14. **Enrich, LLMs do the tagging:** how the stages split the work, with numbers from the actual run (concept counts, time). Takeaway 3.
15. **Enrich, out to every system:** the export formats as a chip cascade (JSON-LD, RDF, Parquet, Elasticsearch, Neo4j, RAG chunks, …).
16. **Intake, tag the problem at the front door:** clip of a person describing a problem in plain words, with FOLIO tags appearing. Courts, government, legal aid.
17. **Insights, extract propositions:** clip of an opinion or treatise turning into atomic, FOLIO-tagged propositions.
18. **Insights, why propositions:** one statement plus an example proposition card.
19. **ontology-dynamic, find what FOLIO lacks:** clip of a proposal tied to its exact source quote (for example, a local court or procedure in the synthetic document).
20. **ontology-dynamic, review before canon:** proposed → reviewed → promoted, as a three-step diagram.
21. Divider: *Plug FOLIO into AI.*
22. **MCP Server:** clip of Claude answering a question by calling FOLIO's MCP tools and returning IRIs and Spanish labels.
23. **FOLIO Python and the API:** clip of a terminal running a five-line script, with a code card beside it. folio-propositions noted as the shared typed model.
24. **Grounded vs. ungrounded:** the same question with and without FOLIO grounding (captured, not invented). Takeaway 2.
25. **Mapper, bring your existing taxonomy:** clip of a synthetic taxonomy mapping to FOLIO with candidates and scores.
26. **Firm example (placeholder):** "A multinational firm's taxonomy, mapped." A plain slide with a speaker note to switch screens. No data.
27. **OntoKit, everyone improves the standard:** clip of a suggestion, review, and merge.
28. **OntoKit, collaboration at scale:** a statement on how jurisdictions add their own law through review, not forks.
29. **Loop recap:** the seven stops as a cycle diagram, the line drawing in with staged nodes. Takeaway 4.

### Act 4: Persona tour (6 slides, about 7 minutes)
30. Divider: *What this means for you.*
31. **Law firms:** matter intake, knowledge management, pricing analytics → Enrich, Mapper, MCP.
32. **Legal departments:** contracts, spend, outside-counsel reporting → Enrich, Insights, Python.
33. **Courts:** filings, dockets, access to justice → Intake, Enrich, Insights.
34. **Government:** regulation, cross-agency data, public services → Intake, ontology-dynamic, OntoKit.
35. **Legal tech, buy instead of build:** for attendees who would rather buy than build. What to ask a vendor: does it tag with SALI/FOLIO, export FOLIO IRIs, accept your mapped taxonomy, and connect through MCP? Names no vendors unless their support is publicly documented and cited.

### Act 5: First steps and close (4 slides, about 4 minutes)
36. **Five first steps:** an ordinal list (pick one dataset, tag it with Enrich, map one taxonomy, connect MCP to your AI, join OntoKit review). Takeaway 5.
37. **Every tool is open source:** names, repo links, and hosted URLs as a grid. No QR code or landing page (Damien, 2026-11-25).
38. **Ask:** an ask band for South American collaborators: translate labels, propose local concepts, pilot one dataset.
39. **Thanks and Q&A.**

## Work steps (in order)

1. **Write the FOLIO-rich synthetic document.** A cross-border supply dispute or contract (for example, a Chilean supplier, a Brazilian distributor, ICC arbitration seated in a third country) of about 600–900 words. Draft it with FOLIO's labels in view so nearly every noun phrase matches a FOLIO concept. Use Enrich's synthetic generator as a seed if it helps. No real parties.
2. **Verify tag density.** Run the document through Enrich and record the concept count, tag coverage (share of tokens inside a tag), individuals, properties, and triples. If coverage looks thin, revise the wording and rerun until nearly every phrase is tagged. These measured numbers become the figures on slides 12–14.
3. **Run the document through each tool** (Intake with a short first-person version, Insights, ontology-dynamic, MCP, Python, Mapper with a synthetic taxonomy, OntoKit) and keep every output as evidence.
4. **Capture media.** Playwright scripts per tool record 10–25-second clips (1920×1080, H.264, under 20 MB each; ffmpeg-trimmed) and one still each at deviceScaleFactor 2. Terminal clips are recorded and rendered to video. Inspect every frame set for keys, emails, or personal data before upload.
5. **Create the deck.** Create a new Slides artifact titled "Legal Data That's AI-Ready." Install the Lawful Good `deck.css` (copied, plus new classes for the clip frame, code card, and loop diagram), the Fraunces and Lato faces, and the full `order` and `sections`.
6. **Upload assets** (stills and clips) and write slides three per message, with speaker notes giving the talk track, timing, and a source for every figure.
7. **Preview** clip slides, diagram slides, and fragment-heavy slides in the viewer; fix overflow and timing.
8. **Hand off** the deck link, the list of bracketed placeholders, and any figures still to confirm.

## Resources needed

- **LLM keys:** Damien's existing keys for Enrich (BYOK), ontology-dynamic, and the MCP session, used by reference only and never shown on screen.
- **Live hosts:** the hosts in the capture table; DEV hosts checked before capture.
- **Tooling:** Playwright (installed), ffmpeg, and a terminal recorder.
- **Public facts:** SALI's and noslegal's stewardship and scope, from their public sites, cited in the notes.

## Risks and contingencies

| Risk | Fallback |
|---|---|
| A DEV host is down at capture time | Capture from a local run of that repo; else use a stepped-still sequence with fragments |
| ontology-dynamic output is thin on the synthetic document | Seed the document with one or two concepts FOLIO lacks (a local institution or procedure) so a proposal appears |
| Clip exceeds 20 MB | Shorten, cut the frame rate to 24 fps, or lower the bitrate |
| Venue projector or offline playback | Clips are deck assets; the PDF/PPTX export shows the stills |
| A figure can't be sourced | Drop it or mark it `[confirm]` in the handoff; never estimate |
| Real firm data leaks into the Mapper shots | Mapper is captured only with a synthetic taxonomy; the firm slide holds no data |

## Decisions after plan review (Damien, 2026-11-25)

- **Legal tech persona:** its own slide (35), framed as "buy instead of build."
- **QR code:** none; no landing page needed.
- **Cover roles:** attorney, SALI co-architect, FOLIO tools developer, plus his day-job title, Solutions Champion at Clio.
