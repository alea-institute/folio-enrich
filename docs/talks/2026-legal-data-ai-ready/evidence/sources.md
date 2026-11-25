# Sources and live facts

All facts below were collected on 2026-11-25. Quotes come verbatim from the page fetched that day, extracted with `curl` and then stripped of HTML.

## FOLIO counts

**Method:** I used `folio-python` 0.4.2 with `FOLIO()` (default source: GitHub `alea-institute/FOLIO`, branch `2.0.0`), plus a cold load with `FOLIO(use_cache=False)` that returned the same count. Each figure comes from:
- **Concepts:** `len(folio.classes)`
- **Branches:** `len(folio.get_folio_branches())`
- **Translations:** a concept counts as having Spanish or Portuguese if its `translations` dict holds a key whose base language is `es` or `pt`.

Note: `FOLIO.list_branches()` returns the *git* branches of the repo, not taxonomy branches. Use `get_folio_branches()` for taxonomy branches.

| Measure | Live value |
|---|---|
| OWL classes (concepts) | **18,323** |
| OWL object properties | **175** |
| Top-level taxonomy branches | **24** |
| Concepts with any translation | **5,730 (31.27%)** |
| Concepts with a Spanish label (es-es / es-mx) | **4,961 (27.08%)** |
| Concepts with a Portuguese label (pt-br) | **5,450 (29.74%)** |

**Locales present, with concept counts:** fr-fr 5,450; pt-br 5,450; de-de 5,450; ja-jp 5,450; zh-cn 5,450; en-gb 4,981; es-es 4,961; es-mx 4,961; he-il 4,961; hi-in 4,961. A few stray keys also appear: en-us 28, en-ca 12, fr 3, en-au 2, and es/he/hi/zh/ja 1 each.

That makes **10 main locales**. They cover **9 base languages**: English (en-gb), French, German, Spanish (in two variants, es-es and es-mx), Portuguese (pt-br), Japanese, Chinese, Hebrew, and Hindi. Of those, **8 are non-English**.

**Concepts per branch:**

| Branch | Concepts |
|---|---|
| Objectives | 5,409 |
| Location | 3,782 |
| Document Artifact | 2,796 |
| Forums/Venues | 2,180 |
| Industry | 2,137 |
| Governmental Body | 1,585 |
| Standards Compatibility | 868 |
| Actor/Player | 563 |
| Legal Entity | 517 |
| Language | 489 |
| Service | 434 |
| Event | 401 |
| Asset Type | 345 |
| Engagement Terms | 343 |
| Currency | 178 |
| Area of Law | 174 |
| Legal Authorities | 82 |
| Status | 23 |
| Data Format | 17 |
| Matter Narrative | 13 |
| System Identifiers | 13 |
| Communication Modality | 11 |
| Folio Type | 3 |
| Matter Narrative Format | 2 |


### README claims compared with live values

| Claim (source) | Live value | Holds? |
|---|---|---|
| "~18,300 concepts" / "Over 18,000 standardized concepts" (FOLIO GitHub README) | 18,323 | **Yes** |
| "24 branches" (folio-mcp README: "List all 24 taxonomy branches") | 24 | **Yes** |
| "translations (31% of concepts, 10+ languages)" (folio-mcp README) | 31.27% of concepts; 10 locales across 9 languages | **31% holds.** "10+ languages" is generous: the data holds exactly 10 locales (9 distinct languages, since Spanish appears twice). Safer wording: "10 language locales". |
| "Translations for the ten most common languages" (FOLIO GitHub README) | 10 locales | Holds if "languages" means locales |
| "10+ Supported Languages", "18,000+ Standardized Tags" (openlegalstandard.org home page) | as above | 18,000+ holds; for "10+", see the row above |

## Standards

### SALI (Standards Advancement for the Legal Industry)

- **Acronym, published by SALI:** "The SALI (Standards Advancement for the Legal Industry) Alliance, the leading global non-profit dedicated to creating and promoting legal data standards, has released to the draft standard (subject to review and comment) the definitions of 12,000+ standardized legal tags, as well as translations into 11 languages." (press release dated September 12, 2023)
  - https://members.sali.org/SALI-Alliance-Defines-and-Translates-12000-Legal-Data-Tags-in-11-Languages
- **What it publishes:** "The Legal Matter Specification Standard (LMSS), published by the SALI Alliance, is the legal industry's shared language for describing legal work." https://www.sali.org/
- **Who stewards it:** "The SALI Alliance is a not-for-profit organization directed by a board comprised of leaders of legal industry professional associations and driven forward by volunteers building the taxonomy and supporting technologies." https://www.sali.org/about
  - **Founding board:** "...Association of Legal Administrators (ALA), the International Legal Technology Association (ILTA), and the Legal Marketing Association (LMA) quickly recognized the promise of a standard taxonomy, and a representative of each created the organization's first board of directors." https://www.sali.org/about
  - **Current board, named in SALI's rebrand post:** Eryn Carter, "Executive Director of the Association of Legal Administrators (ALA) and SALI Alliance board member"; Joy Heath Rush, "Executive Director of the International Legal Technology Association (ILTA) and SALI Alliance board member." https://sali.org/sali-rebrand/
  - **Founded:** "...in 2017, a formally organized not-for-profit corporation." Also: "The first version of the LMSS was released on February 4, 2020." And: "Version two of the LMSS was published on March 9, 2022, and the API standard was released on May 10, 2024." https://www.sali.org/about
- **Tag count as published by SALI:**
  - **Latest SALI-published number:** "12,000+" (the September 12, 2023 press release above).
  - **Current pages:** the live sali.org home, about, explore, community, and membership pages, fetched 2026-11-25, state no number. sali.org/about says only "these thousands of tags".
  - **FOLIO's figure:** FOLIO's own blog says "LMSS's 18,000+ tags". That is FOLIO's claim, not SALI's.
- **Translation lineage:** "Michael Bommarito of 273 Ventures provided the translations of the extensive set of legal tags into the world's most commonly spoken languages: German, French, Chinese, Brazilian Portuguese, Japanese, Peninsular Spanish, Mexican Spanish, Hindi, Hebrew, and UK English." (same 2023 press release)
  - These ten locales match FOLIO's 10 live locales exactly.
- **Current license (SALI):** "The choice of the CC BY ND license is intended to facilitate widespread adoption and use of SALI standards while preserving canonical reference versions. This means that SALI-licensed materials cannot be used to create competing standards or distributed derivatives." https://sali.org/explore-the-standard/
- **Vendors supporting SALI:**
  - **No named list found.** None of the official SALI pages fetched today names specific vendors.
  - **General claims:** sali.org/about says "Law firms, in-house counsel, and legal tech companies are quickly and broadly moving towards standardizing with SALI tags". sali.org/community says "Learn how firms and vendors are adopting the LMSS in practice".
  - **Third-party headline:** "SALI's 10,000-Plus Tags Adopted By Providers, Vendors, And Clients" (Above the Law, January 2023, https://abovethelaw.com/2023/01/standardizing-legal-data-salis-10000-plus-tags-adopted-by-providers-vendors-and-clients/). I did not fetch it, and it is not an official SALI page.
  - **For the deck:** do not name any vendor as a SALI supporter.

### noslegal (UK)

- **What it is:** "Open source knowledge community for law 180+ people from 60+ organisations We're a voluntary community." https://www.noslegal.org/
- **Scope:** "We started in 2021 with a taxonomy of legal work types, areas of law and more. Its fourth major version was released recently (May 2026)." https://www.noslegal.org/
  - **Taxonomy modules (site navigation):** Work types, Areas of law, Participants, Roles, Sectors, Places, Process elements, Information types.
  - **Audiences:** "Created for Law firms / legal services Legal departments Legal tech providers".
- **Legal entity (UK):** "For this purpose, we established a UK company limited by guarantee, noslegal Ltd, company number 1339502." And: "The directors of noslegal Ltd are Graeme Johnston, Jacob Capleton and Paul McCormack." https://www.noslegal.org/about/who-we-are/
- **License:** "We use the well-known Apache 2.0 permissive open source licence for this purpose." https://www.noslegal.org/about/open-source/
- **Adoption, quoted on noslegal's home page:** Financial Times, 17 October 2024: "Adoption… by five sizeable law firms, including A&O Shearman." A testimonial also names a product: "By embedding noslegal's taxonomy into Tiger Eye Blueprint, ..." https://www.noslegal.org/

### FOLIO's relationship to SALI

- **Fork:** "In September 2024, we established SOLI (Standard for Open Legal Information) as a permitted, lawful fork of the MIT-licensed LMSS specification." https://openlegalstandard.org/whats-happening-with-sali-soli-folio
- **Rename:** "On March 14, 2025, we rebranded as FOLIO." (same page)
- **Who "we" is:** the same post names ALEA, and its contact is hello@aleainstitute.ai.
  - **Repo:** the ontology lives at https://github.com/alea-institute/FOLIO.
  - **Institute:** the ALEA site footer reads: "© 2024-2026 Institute for the Advancement of Legal and Ethical AI ("ALEA Institute")." https://aleainstitute.ai/
- **README lineage line:** "[Prior versions of a related project](https://github.com/sali-legal/LMSS) were available under an MIT license. The list of all original contributors can be reviewed there." https://raw.githubusercontent.com/alea-institute/FOLIO/main/README.md
- **FOLIO license:** "The data in this repository is licensed under a Creative Commons Attribution 4.0 International License. Any source is licensed under the MIT license." (same README)
- **FOLIO's own description:** "FOLIO (Federated Open Legal Information Ontology) is an open, CC-BY licensed standard designed to represent universal elements of legal data." (same README)
- **MCP announcement:** the ALEA blog lists "Free API and MCP Tools for FOLIO Legal Ontology", dated Thu Mar 19 2026. https://aleainstitute.ai/
- **Caution for the deck:**
  - **Contested history:** the SALI/SOLI/FOLIO post describes a governance dispute and SALI's January 13, 2025 cease-and-desist letters. Treat it as one side's account.
  - **Neutral facts:** state only that FOLIO began as SOLI (a fork of the MIT-licensed LMSS, September 2024), took the FOLIO name on March 14, 2025, and is maintained by the ALEA Institute under CC BY 4.0.
  - **License contrast:** SALI's current license is CC BY-ND, which forbids distributed derivatives. FOLIO is CC BY 4.0, which permits them.
