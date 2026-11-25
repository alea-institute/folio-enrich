# Legal Data That's AI-Ready: Slides Deck Plan

Created: 2026-11-25
Execution: knowledge-work (deepened into build units 2026-11-25)

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

## Build units

Execution: knowledge-work. The deliverable is a Slides artifact plus media. The repo keeps the plan, the demo document, measured evidence, and the capture tooling under `docs/talks/2026-legal-data-ai-ready/`, so the clips can be re-shot before the talk if a tool changes. Capture tooling is small and throwaway, but it is committed so a re-shoot is one command. Large media (clips, stills) stays out of git, in the deck's asset store and a local `media/` folder that git ignores.

Spend rule: prefer routes that cost nothing: the Codex CLI subscription for Enrich (`--provider codex-cli`), local Ollama or a subscription CLI where a tool supports one. If a tool runs only on a paid API key, cap the run at US$2 (`--max-spend-usd` where offered), record the actual cost in the evidence file, and stop to ask before any run that would exceed it.

### U1. FOLIO-rich demo document
- **Files:** `docs/talks/2026-legal-data-ai-ready/demo-document.md`, `docs/talks/2026-legal-data-ai-ready/evidence/enrich-density.md`, `evidence/enrich-result.json`.
- **Work:** write a 600–900-word synthetic cross-border document (Chilean supplier, Brazilian distributor, arbitration, governing law, remedies, payment, IP, data protection, a court filing) using FOLIO labels as its vocabulary. Run it through the Enrich pipeline locally from the main repo's venv (`~/Coding Projects/folio-enrich/backend/.venv`), with the Codex CLI provider. Measure the share of words (three letters or more) that fall inside an annotation span, as the baked-exemplar check does.
- **Done:** word coverage at or above 70% (beating `rich_advisory` at 65% and `rich_contract` at 51%, measured the same way), with no real parties named. Record concept, individual, property, and triple counts and the run time in `enrich-density.md`. Revise and rerun at most four times; if coverage stays under 70%, keep the best version and note the measured figure.

### U2. Tool runs and evidence
- **Files:** one `evidence/<tool>.md` per tool, holding the command or URL, its output (trimmed), date, and cost.
- **Enrich:** reuse U1's result; also load it into the local Enrich frontend (as a local exemplar or through a job import) so the capture shows the real UI without a key on screen.
- **Intake:** the DEV site sits behind a sign-in (HTTP 401). Use the gate credential by reference if one exists for it; else run Intake locally (`docker compose up -d` per its README) and capture there. Input: a first-person, plain-language version of the dispute.
- **Insights:** run `folio-insights extract` locally on the demo document (free provider first), then `serve` for the review viewer.
- **ontology-dynamic:** `ontdyn ingest` → `tag` → `propose`, then `ontdyn-viewer`. Seed one or two local concepts if needed (a Chilean court, a Brazilian procedure).
- **MCP Server:** call `folio.openlegalstandard.org/mcp` with a real client and record the tool calls and answers (search a concept, get its Spanish and Portuguese labels, walk its parents). The clip replays this real transcript in a chat-style page; it adds nothing the server didn't return.
- **FOLIO Python:** run a five-line script (load FOLIO, search "arbitration", print the IRI, labels, and parents) and keep the real output.
- **Grounded vs. ungrounded:** ask one LLM the same question twice, without and with FOLIO results in context; keep both answers verbatim. Use a subscription CLI (Claude or Codex), not a paid API.
- **Mapper:** map a 15–20-term synthetic taxonomy (invented practice-area labels, no firm data) on `mapper.openlegalstandard.org`.
- **OntoKit:** on `ontokit.openlegalstandard.org` (DEV fallback), show a suggestion, its review, and its merge. If that needs a sign-in, use the existing demo credential by reference; never record a sign-in screen.
- **Public facts:** SALI's and noslegal's stewardship and scope, plus the FOLIO counts rechecked against the live API, saved with URLs and dates in `evidence/sources.md`.
- **Done:** every lifecycle slide's claim and figure traces to an evidence file.

### U3. Capture clips and stills
- **Files:** `docs/talks/2026-legal-data-ai-ready/capture/*.mjs` (one Playwright script per clip), `capture/README.md` (how to re-shoot), `media/` (git-ignored output).
- **Work:** Playwright's `recordVideo` at 1920×1080, one scripted flow per clip slide (13), paced for 10–25 seconds; ffmpeg trims and encodes to H.264 MP4 (`-crf 28`, `-movflags +faststart`, no audio). Take a still at the key frame for each clip (deviceScaleFactor 2). The two terminal clips (FOLIO Python, MCP) render their real recorded output in a terminal-styled page and record that, since no terminal recorder is installed.
- **Screening:** before upload, extract one frame every 2 seconds and inspect it for keys, tokens, email addresses, or personal data; re-shoot any frame that shows one.
- **Done:** 13 MP4s, each 20 MB or less, each with a matching still, all screened. A manifest (`media/manifest.json`) maps each slide id to its clip, still, duration, and size.

### U4. Build the deck
- **Work:** create a Slides artifact titled "Legal Data That's AI-Ready" from the Slides type. Copy Lawful Good's `deck.css` and add classes for the clip frame, code card, persona card, and loop diagram. Faces: Fraunces and Lato. Write `deck.json` with the 39-slide `order` and five `sections`. Upload each still and clip as assets; write slides three per publish with `data-video` frames. Speaker notes carry the talk track, the target minute, and a source for each figure.
- **Done:** all 39 slides publish without a held or read-only slide; every clip slide plays its clip; no slide shows a figure without a source in its notes.

### U5. Preview, QA, and handoff
- **Work:** preview every slide in the Slides viewer. Check text overflow, the 824px content height, contrast, fragment order, and clip playback. Fix and republish once per issue batch.
- **Done:** a QA log in `evidence/qa.md` (slide, issue, fix). Then hand off with the deck link, the bracketed placeholders still open, and the spend, if any.

## Resources needed

- **LLM access:** Codex CLI and Claude CLI subscriptions first, then local Ollama; paid keys only under the spend rule above, used by reference only and never shown on screen.
- **Hosts:** the hosts in the capture table, checked on 2026-11-25: Enrich, Insights DEV, Mapper, OntoKit, and the FOLIO API docs return 200. Intake DEV returns 401 (gated). The MCP endpoint returns 406 to a plain GET, as expected for an MCP server.
- **Tooling:** Playwright and ffmpeg (both installed). No asciinema, agg, or vhs.

## Risks and contingencies

| Risk | Fallback |
|---|---|
| Intake DEV stays gated |  Run Intake locally with Docker Compose and capture there |
| A tool needs a paid API key | Cap at US$2 and record the cost; ask before going higher |
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
