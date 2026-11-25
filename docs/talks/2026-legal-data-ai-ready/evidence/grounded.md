# Evidence: grounded vs. ungrounded FOLIO tagging

Captured 2026-11-25. Model: `claude-opus-5-5` (Claude Code 2.1.332, `claude -p --model opus`, subscription auth; `modelUsage` in every JSON result names only `claude-opus-5-5`). Comparison run: Codex CLI, model `gpt-6.1-sol`. FOLIO MCP server: `https://folio.openlegalstandard.org/mcp` (serverInfo "FOLIO Legal Ontology" 1.27.0). Raw JSON results stay in the session scratchpad; this file carries every answer verbatim.

## Question (identical in every run)

> Tag this matter with standard legal-ontology concepts and give each concept's identifier and its Portuguese (Brazil) label: A Brazilian wine distributor is bringing an ICC arbitration against its Chilean supplier for breach of an exclusive distribution agreement, wrongful termination, and trademark infringement.

## Commands

```bash
# Run A: ungrounded, no tools, no MCP servers (3 runs, in parallel)
claude -p --model opus --tools "" --strict-mcp-config --no-session-persistence --output-format json "$PROMPT_A"
# PROMPT_A = "Answer from your own knowledge only. Use the FOLIO legal ontology (Federated Open Legal Information Ontology) as the standard ontology; give each concept's FOLIO IRI and its pt-BR label.\n\n<question>"

# Run A-forced: same flags, prompt insists on an IRI for every concept (3 runs)
# PROMPT_F = "Answer from your own knowledge only (no lookups are possible). Use the FOLIO legal ontology (...). You must give a FOLIO IRI and a pt-BR label for every concept; give your best recollection even if unsure.\n\n<question>"

# Run B: grounded, FOLIO MCP is the only tool source (3 runs)
# folio-mcp.json = {"mcpServers":{"folio":{"type":"http","url":"https://folio.openlegalstandard.org/mcp"}}}
claude -p --model opus --tools "" --strict-mcp-config --mcp-config folio-mcp.json --allowedTools "mcp__folio" --no-session-persistence --output-format json "$PROMPT_B"
# PROMPT_B = "Use the FOLIO MCP tools (search_concepts, get_concept, etc.) to answer. Use only FOLIO concepts you actually retrieved with those tools; for each, give the IRI and the pt-BR label exactly as the tool returned them. Do not add any concept you did not retrieve.\n\n<question>"

# Cross-model check: Codex, forced prompt, read-only sandbox
codex exec --skip-git-repo-check -s read-only "$PROMPT_F"

# Verification: every IRI in Run B fetched with the MCP server's get_concept (JSON-RPC over HTTP, scratchpad script mcpcheck.py),
# then the claimed pt-BR label compared byte-for-byte with the record's translations["pt-br"].
```

Caveat: `claude -p` still loads the user's global CLAUDE.md, which stresses honesty and evidence; that context may make the ungrounded model more cautious than a bare API call would be.

## Summary table

| Run | Concepts tagged | Valid FOLIO IRIs | pt-BR labels given | pt-BR labels matching FOLIO exactly | Turns (tool calls) |
|---|---|---|---|---|---|
| A1 ungrounded | 18 | 0 (none given) | 18 | 1 exact ("Requerente"), 1 partial ("Contrato de Distribuição (com Exclusividade)") | 1 |
| A2 ungrounded | 21 | 0 (none given) | 21 | 1 ("Requerente") | 1 |
| A3 ungrounded | 14 | 0 (none given) | 14 | 0 exact; 2 only as parenthetical alternatives ("Distribuidor (Requerente)", "Inadimplemento Contratual (Quebra de Contrato)") | 1 |
| A-forced F1 | 20 | 0 ("lookup needed") | 20 | 2 (case-insensitive) | 1 |
| A-forced F2 | 16 | 0 ("UNVERIFIED" placeholders) | 16 | 2 (case-insensitive) | 1 |
| A-forced F3 | 18 | 0 ("needs lookup") | 18 | 2 (case-insensitive) | 1 |
| Codex forced | 6 + 3 metadata | 0 ("Not reliably recalled") | 6 | 1 ("Contrato de distribuição") | n/a |
| **B1 grounded** | **20** | **20 / 20** | **12** | **12 / 12** (other 8 correctly reported as having no pt-BR label) | 40 |
| **B2 grounded** | **18** | **18 / 18** | **11** | **11 / 11** (other 7 correctly reported) | 39 |
| **B3 grounded** | **17** | **17 / 17** | **10** | **10 / 10** (other 7 correctly reported) | 37 |

Ungrounded label matching was checked against the pt-BR labels of the 23 FOLIO concepts the grounded runs retrieved (the comparable set), case-insensitive, splitting "A / B (C)" alternatives. Most ungrounded labels are sound Brazilian legal Portuguese ("Inadimplemento Contratual", "Violação de Marca", "Direito Marcário") but do not match FOLIO's strings ("Quebra de contrato", "Violação de marca registrada", "Direito de Marcas e Designações Comerciais").

### Consistency across the 3 runs

- **Grounded (machine-checkable by IRI):** union 23 IRIs, 14 in all three runs (Jaccard 0.61); pairwise 0.73, 0.61, 0.84. Of the pt-BR-labelled tags, 8 IRIs appear in all three runs. Every shared IRI carries the identical pt-BR label in every run. The drift is at the edges: which industry code (Wholesale Trade vs. NAICS 424820 vs. Wineries), whether Seller/Claimant/Trademark Assets get tagged.
- **Ungrounded (not machine-checkable):** no identifiers, so overlap can only be judged by reading English names. The core claims (breach, termination, trademark infringement, distribution agreement, ICC, Brazil, Chile) recur, but the tag count swings 14 to 21 and the pt-BR strings drift for the same concept:
  - Trademark law: "Direito de Marcas" (A1) / "Direito Marcário" (A2) / "Direito da Propriedade Intelectual (Direito Marcário)" (A3)
  - Wrongful termination: "Rescisão Indevida (Resilição Imotivada)" / "Rescisão Indevida (Resilição Abusiva)" / "Rescisão Contratual Indevida"
  - ICC: "Corte Internacional de Arbitragem da CCI" (A1, A2) / "Corte Internacional de Arbitragem da Câmara de Comércio Internacional (CCI)" (A3)

### Grounded concept set (verified against live FOLIO)

| IRI suffix | FOLIO label | FOLIO pt-BR | B1 B2 B3 |
|---|---|---|---|
| `RC2LcVXjOZOiT3wqNc2SU5n` | Arbitration Event | Evento de arbitragem | X X . |
| `R8LtU1k4pyiSD639zaq4vrM` | Arbitration Forum | (none in FOLIO) | X X X |
| `RXO2u2WBkUUcEG1jczLIcA` | Arbitration Practice | Prática de arbitragem | X X X |
| `RBB829d2E27c3F9D3df5A1e5` | Brazil | (none in FOLIO) | X X X |
| `RC2fjcpsEbrVvVymvt4oASx` | Breach of Contract | Quebra de contrato | X X X |
| `RbkhZxcSyqaKNyUivxRRpu` | Breach of Contract Claims | Reivindicações por quebra de contrato | X X X |
| `R6062f0A6352c79Ae5c7E86b` | Chile | (none in FOLIO) | X X X |
| `R9UnetFhUZWHNEZJYjGQuXN` | Claimant | Requerente | . . X |
| `RCIPwpgRpMs1eVz4vPid0pV` | Contract Law | (none in FOLIO) | X X X |
| `RB3TXlxV89oDiy7HtSN9cF0` | Contract Termination | (none in FOLIO) | X X X |
| `RBsiX2FSnOKhxvLGKoU9x1` | Cross-Border Objective | (none in FOLIO) | X X X |
| `RxvDJ1zl0ikIMMjfefcuyp` | Distributor Agreement | Contrato de distribuição | X X X |
| `RDgEiiX23zftUP0Mggfc68n` | Exclusivity Clause | Cláusula de exclusividade | X X X |
| `R7gdCxuo1pOeQuksIZwB5qC` | ICC Arbitration Clause | Cláusula de arbitragem da ICC | X X X |
| `R8x520MB0xME0o4Wrg2o1so` | International Trade Practice | (none in FOLIO) | X . . |
| `R7kkf8NvitG8hubZUnTwevG` | Seller | Vendedor | . X X |
| `R8uW7tSElnScC1uC2CnZTIL` | Termination of Contract Clause | Cláusula de rescisão de contrato | X X . |
| `RBaL7gtiLlgraIRVwa44vg2` | Trademark Assets | Ativos de marca | X . . |
| `RBQCFqSF0Q0sCqCcEwv2pgz` | Trademark Infringement | Violação de marca registrada | X X X |
| `R8phitqyUIXJ4ZdLaJjabna` | Trademark and Trade Dress Law | Direito de Marcas e Designações Comerciais | X X X |
| `R97XG1bV4Mx6t2B4cpMlF0U` | Wholesale Trade Industry | Indústria de comércio atacadista | X . . |
| `N0gwCr2vTyKkBHTZi8MHbQ` | Wine and Distilled Alcoholic Beverage Merchant Wholesalers | (none in FOLIO) | . X X |
| `cbaI5ZloRfmVi2OXwB4cfA` | Wineries | (none in FOLIO) | X . . |

All 23 resolve with `get_concept` (0 errors, 0 invented IRIs).

## Honest reading

- **The ungrounded model did not hallucinate IRIs.** Opus 5.5 refused to invent identifiers in all six runs, even when told it must give one; Codex (gpt-6.1-sol) did the same. The "before" failure is therefore not fake IRIs: it is **no identifiers at all**, plus pt-BR labels that are plausible but do not match the ontology's and drift between runs. Do not put a fabricated-IRI claim on the slide.
- **Grounding made the output verifiable:** 55/55 IRIs real, 33/33 pt-BR labels exact, and the model correctly flagged the 22 tag slots where FOLIO has no pt-BR label (for example, Contract Law, Brazil, Chile).
- **Grounding surfaced ontology gaps an ungrounded model glossed over:** all three grounded runs rejected FOLIO's "Wrongful Discharge or Termination" as an employment concept, and found no concept for the ICC as an institution.
- **Cost:** grounded runs took 37 to 40 turns (tool round-trips) vs. 1.

## Slide excerpts (verbatim)

Ungrounded (A2):
> | 6 | Legal Matter / Claim | Breach of Contract | Inadimplemento Contratual | not recalled |
> | 8 | Legal Matter / Claim | Trademark Infringement | Violação de Marca | not recalled |

Grounded (B2):
> | 7 | Breach of Contract | https://folio.openlegalstandard.org/RC2fjcpsEbrVvVymvt4oASx | Quebra de contrato |
> | 9 | Trademark Infringement | https://folio.openlegalstandard.org/RBQCFqSF0Q0sCqCcEwv2pgz | Violação de marca registrada |

## Verbatim answers

### Run A1, ungrounded

````markdown
# FOLIO tags for this matter (IRIs unverified)

**I can't give you real FOLIO IRIs from memory.** FOLIO identifiers are opaque hashes, such as `https://folio.openlegalstandard.org/R…` followed by about 22 random characters. Any IRI I typed would be invented, and a fabricated IRI would quietly corrupt your tagging. I've left the IRI column blank. The concept selection and pt-BR labels below come from my knowledge of FOLIO's branch structure and standard Brazilian legal terminology. They are not verified against FOLIO's `rdfs:label@pt-BR` / `skos:altLabel@pt-BR` values.

| Branch | Concept (en) | Proposed pt-BR label | FOLIO IRI |
|---|---|---|---|
| **Area of Law** | Arbitration / Alternative Dispute Resolution | Arbitragem / Resolução Alternativa de Disputas | *needs lookup* |
| **Area of Law** | Contract Law | Direito Contratual | *needs lookup* |
| **Area of Law** | Intellectual Property Law | Direito de Propriedade Intelectual | *needs lookup* |
| **Area of Law** | Trademark Law | Direito de Marcas | *needs lookup* |
| **Area of Law** | International Trade / Commercial Law | Direito do Comércio Internacional | *needs lookup* |
| **Legal Matter / Claim** | Breach of Contract | Inadimplemento Contratual (Violação de Contrato) | *needs lookup* |
| **Legal Matter / Claim** | Wrongful Termination (of contract) | Rescisão Indevida (Resilição Imotivada) | *needs lookup* |
| **Legal Matter / Claim** | Trademark Infringement | Violação de Marca | *needs lookup* |
| **Document / Artifact** | Distribution Agreement (exclusive) | Contrato de Distribuição (com Exclusividade) | *needs lookup* |
| **Forum / Venue** | International Chamber of Commerce (ICC) Court of Arbitration | Corte Internacional de Arbitragem da CCI | *needs lookup* |
| **Engagement / Service** | Arbitration (proceeding) | Procedimento Arbitral | *needs lookup* |
| **Actor / Player** | Claimant | Requerente | *needs lookup* |
| **Actor / Player** | Respondent | Requerida | *needs lookup* |
| **Actor / Player** | Distributor | Distribuidor | *needs lookup* |
| **Actor / Player** | Supplier | Fornecedor | *needs lookup* |
| **Industry** | Wine / Beverage Wholesale | Comércio Atacadista de Vinhos / Bebidas | *needs lookup* |
| **Location** | Brazil | Brasil | *needs lookup* |
| **Location** | Chile | Chile | *needs lookup* |

## Label notes

- **Wrongful termination:** in Brazil this phrase usually means employment dismissal (*dispensa sem justa causa*). For a commercial contract, *rescisão indevida* or *resilição unilateral imotivada* fits better. Check that FOLIO tags the contract-termination concept, not the employment one.
- **Arbitration roles:** ICC Portuguese practice uses *Requerente* and *Requerida*, not *Autor* and *Réu*.
- **"Exclusive":** FOLIO may lack a separate "exclusive distribution" class. If so, tag *Distribution Agreement* and record exclusivity as a property or note.

## Getting the real IRIs

To fill the blank column, I can look each concept up against the live FOLIO ontology with `folio-python` or the published OWL file. I'd match on English labels, then pull the actual pt-BR labels. That breaks your "own knowledge only" constraint, so I'll wait for your go-ahead.
````

### Run A2, ungrounded

````markdown
# FOLIO Tagging: Brazilian Distributor v. Chilean Supplier (ICC Arbitration)

I can't give you the FOLIO IRIs from memory. FOLIO IRIs are opaque random identifiers (for example `https://folio.openlegalstandard.org/R…`), not readable slugs. Any IRI I wrote down without a lookup would likely be made up and would look real, which is worse than leaving it out. The same caution applies to the pt-BR labels. FOLIO ships translated labels, but I can't confirm its exact pt-BR strings without checking. The labels below are my standard Brazilian legal terms, so compare them against FOLIO's own before you use them.

| # | FOLIO branch | Concept (en) | pt-BR label (unverified) | IRI |
|---|---|---|---|---|
| 1 | Area of Law | International Arbitration | Arbitragem Internacional | not recalled |
| 2 | Area of Law | Contract Law | Direito Contratual | not recalled |
| 3 | Area of Law | Commercial Law | Direito Comercial / Direito Empresarial | not recalled |
| 4 | Area of Law | Intellectual Property Law | Direito da Propriedade Intelectual | not recalled |
| 5 | Area of Law | Trademark Law | Direito Marcário | not recalled |
| 6 | Legal Matter / Claim | Breach of Contract | Inadimplemento Contratual | not recalled |
| 7 | Legal Matter / Claim | Wrongful Termination (of contract) | Rescisão Indevida (Resilição Abusiva) | not recalled |
| 8 | Legal Matter / Claim | Trademark Infringement | Violação de Marca | not recalled |
| 9 | Document / Agreement | Exclusive Distribution Agreement | Contrato de Distribuição Exclusiva | not recalled |
| 10 | Forum / Venue | ICC International Court of Arbitration | Corte Internacional de Arbitragem da CCI | not recalled |
| 11 | Service / Objective | Dispute Resolution | Resolução de Disputas | not recalled |
| 12 | Actor / Player | Claimant | Requerente | not recalled |
| 13 | Actor / Player | Respondent | Requerida | not recalled |
| 14 | Actor / Player | Distributor | Distribuidor | not recalled |
| 15 | Actor / Player | Supplier | Fornecedor | not recalled |
| 16 | Location | Brazil | Brasil | not recalled |
| 17 | Location | Chile | Chile | not recalled |
| 18 | Industry (NAICS-derived) | Beer, Wine, and Distilled Alcoholic Beverage Merchant Wholesalers | Atacadistas de Cervejas, Vinhos e Bebidas Destiladas | not recalled |
| 19 | Industry (NAICS-derived) | Wineries | Vinícolas | not recalled |
| 20 | Remedy (optional) | Damages | Perdas e Danos | not recalled |
| 21 | Remedy (optional) | Injunction | Tutela Inibitória | not recalled |

## Tagging notes

- **Wrongful termination:** in Brazilian usage, "rescisão" covers termination generally. "Resilição abusiva/imotivada" fits a unilateral termination without cause, which matches this claim. If FOLIO offers "Wrongful Termination" only under employment, use the contract-termination concept instead.
- **Party roles:** claimant (the Brazilian distributor) and respondent (the Chilean supplier) belong at the matter level. Distributor and supplier describe the parties' commercial roles.
- **Arbitration vs. litigation:** tag the proceeding type as arbitration, not litigation or court, so the forum and procedure facets stay accurate.

You asked for an answer from my own knowledge only, so I didn't run a lookup. If you lift that limit, I can resolve each row against FOLIO, for example with `folio-python` label search in this worktree. That would fill in the real IRIs and FOLIO's actual pt-BR labels and flag any concepts that don't exist as named.
````

### Run A3, ungrounded

````markdown
I can't give you accurate FOLIO IRIs from memory. FOLIO identifiers are opaque generated strings (`https://folio.openlegalstandard.org/R…`), not readable slugs, and I don't reliably recall which string belongs to which class. Any IRI I wrote here would be fabricated, so I've left that column for lookup.

The pt-BR labels below are my own translations of the standard Brazilian legal terms. They may not match FOLIO's official `skos:prefLabel@pt-BR` strings exactly.

## Proposed tags

| FOLIO branch | Concept (en) | Proposed pt-BR label | FOLIO IRI |
|---|---|---|---|
| **Dispute resolution / Forum** | International Commercial Arbitration | Arbitragem Comercial Internacional | *lookup needed* |
| **Forum / Venue** | International Chamber of Commerce (ICC) International Court of Arbitration | Corte Internacional de Arbitragem da Câmara de Comércio Internacional (CCI) | *lookup needed* |
| **Legal matter / Claim** | Breach of Contract | Inadimplemento Contratual (Quebra de Contrato) | *lookup needed* |
| **Legal matter / Claim** | Wrongful Termination of Contract | Rescisão Contratual Indevida | *lookup needed* |
| **Legal matter / Claim** | Trademark Infringement | Violação de Marca | *lookup needed* |
| **Document / Artifact** | Exclusive Distribution Agreement | Contrato de Distribuição Exclusiva | *lookup needed* |
| **Area of law** | Contract Law | Direito Contratual | *lookup needed* |
| **Area of law** | Intellectual Property Law (Trademark Law) | Direito da Propriedade Intelectual (Direito Marcário) | *lookup needed* |
| **Area of law** | International Trade / Commercial Law | Direito Comercial Internacional | *lookup needed* |
| **Jurisdiction** | Brazil | Brasil | *lookup needed* |
| **Jurisdiction** | Chile | Chile | *lookup needed* |
| **Industry** | Wine / Beverage Manufacturing and Distribution | Indústria Vinícola / Distribuição de Bebidas | *lookup needed* |
| **Actor / Player** | Distributor (Claimant) | Distribuidor (Requerente) | *lookup needed* |
| **Actor / Player** | Supplier (Respondent) | Fornecedor (Requerido) | *lookup needed* |

## Tagging notes

- **Termination concept:** tag the contract termination class, not "Wrongful Termination" under employment law. FOLIO can file the bare phrase under employment, and this dispute involves no employment relationship.
- **Party roles:** ICC practice uses Claimant and Respondent (*Requerente* and *Requerido*), not Plaintiff and Defendant.
- **Granularity:** if FOLIO has no "Exclusive Distribution Agreement" class, tag the parent "Distribution Agreement" and record exclusivity as a matter attribute.

## Getting real IRIs

To get verified IRIs and official pt-BR labels, I can query the FOLIO OWL file or the FOLIO API (`folio-python`) and resolve each concept to its exact class. You asked for my own knowledge only, so I haven't done that here. Say the word and I'll run the lookup.
````

### Run A-forced F1

````markdown
# FOLIO Tags: Brazilian Distributor v. Chilean Supplier (ICC Arbitration)

**About the IRIs:** FOLIO IRIs use the namespace `https://folio.openlegalstandard.org/` followed by an opaque, randomly generated ID (for example, `R8pNPutX0TN6DlEqkyZuxSw`). I can't recall those suffixes reliably. Any ID I wrote would be invented, so the IRI column marks each one **"lookup needed."** The concepts, FOLIO branches, and pt-BR labels below are my best recollection. The pt-BR labels are standard Brazilian legal terms and may differ from FOLIO's official `pt-BR` prefLabels.

| # | FOLIO branch | Concept (en) | IRI | pt-BR label |
|---|---|---|---|---|
| 1 | Area of Law | Contract Law | `folio:` lookup needed | Direito Contratual |
| 2 | Area of Law | Commercial Law | `folio:` lookup needed | Direito Comercial / Direito Empresarial |
| 3 | Area of Law | Intellectual Property Law | `folio:` lookup needed | Direito da Propriedade Intelectual |
| 4 | Area of Law | Trademark Law | `folio:` lookup needed | Direito Marcário |
| 5 | Area of Law | International Arbitration | `folio:` lookup needed | Arbitragem Internacional |
| 6 | Service / Engagement | Arbitration | `folio:` lookup needed | Arbitragem |
| 7 | Forum / Venue | International Chamber of Commerce (ICC) Court of Arbitration | `folio:` lookup needed | Corte Internacional de Arbitragem da Câmara de Comércio Internacional (CCI) |
| 8 | Legal Cause / Claim | Breach of Contract | `folio:` lookup needed | Inadimplemento Contratual / Violação de Contrato |
| 9 | Legal Cause / Claim | Wrongful Termination (of contract) | `folio:` lookup needed | Rescisão Contratual Indevida / Resilição Imotivada |
| 10 | Legal Cause / Claim | Trademark Infringement | `folio:` lookup needed | Violação de Marca / Contrafação de Marca |
| 11 | Document / Artifact | Distribution Agreement (exclusive) | `folio:` lookup needed | Contrato de Distribuição (com Exclusividade) |
| 12 | Actor / Player | Distributor | `folio:` lookup needed | Distribuidor |
| 13 | Actor / Player | Supplier | `folio:` lookup needed | Fornecedor |
| 14 | Actor / Player | Claimant | `folio:` lookup needed | Requerente |
| 15 | Actor / Player | Respondent | `folio:` lookup needed | Requerido |
| 16 | Industry | Wineries / Wine Manufacturing (NAICS 312130) | `folio:` lookup needed | Vinícolas / Fabricação de Vinhos |
| 17 | Industry | Beverage Wholesale / Distribution (NAICS 4248) | `folio:` lookup needed | Comércio Atacadista de Bebidas |
| 18 | Location | Brazil | `folio:` lookup needed | Brasil |
| 19 | Location | Chile | `folio:` lookup needed | Chile |
| 20 | Governing instrument (likely) | CISG / New York Convention (enforcement) | `folio:` lookup needed | Convenção de Viena (CISG) / Convenção de Nova York |

**Notes on the tags:**
- **Wrongful termination:** in Brazilian practice, this is usually framed as *resilição unilateral imotivada*, which can trigger indemnity under Civil Code art. 473 and analogous rules for distribution contracts (art. 710 ff.). The label is not the employment-law sense.
- **CISG relevance:** CISG governs the underlying sales, not the distribution framework itself. Tag 20 only applies if the case raises enforcement or sales issues.

**How to get real IRIs:** with network access, I can resolve each concept against the live FOLIO ontology, either through the FOLIO API's label search or through `folio-python`'s `search_by_label`. That search would also pull the official `pt-BR` labels, so this table would carry real IRIs instead of placeholders.
````

### Run A-forced F2

````markdown
# FOLIO tagging: Brazil–Chile wine distribution ICC arbitration

**I can't give you real FOLIO IRIs from memory.** FOLIO IRIs are opaque, random-looking identifiers (for example, `https://folio.openlegalstandard.org/R…` followed by about 22 base-62 characters). They encode nothing about the concept, so I can't reconstruct them. Any specific IRI I wrote here would be invented, and it would look just as valid as a real one, which makes it worse than a blank. Each IRI below is therefore a clearly marked placeholder. The concepts and pt-BR labels are my best answer.

## Concept tags

| # | FOLIO branch | Concept (en) | pt-BR label | IRI |
|---|---|---|---|---|
| 1 | Forums & Venues / Dispute Resolution | Arbitration | Arbitragem | `folio:⟨UNVERIFIED⟩` |
| 2 | Area of Law | International Commercial Arbitration | Arbitragem Comercial Internacional | `folio:⟨UNVERIFIED⟩` |
| 3 | Actor/Player – Organization | International Chamber of Commerce (ICC) | Câmara de Comércio Internacional (CCI) | `folio:⟨UNVERIFIED⟩` |
| 4 | Area of Law | Contract Law | Direito Contratual | `folio:⟨UNVERIFIED⟩` |
| 5 | Legal Document / Agreement | Distribution Agreement | Contrato de Distribuição | `folio:⟨UNVERIFIED⟩` |
| 6 | Agreement attribute | Exclusive Distribution / Exclusivity | Distribuição Exclusiva / Exclusividade | `folio:⟨UNVERIFIED⟩` |
| 7 | Objectives / Claims | Breach of Contract | Inadimplemento Contratual (Violação de Contrato) | `folio:⟨UNVERIFIED⟩` |
| 8 | Objectives / Claims | Wrongful Termination (of contract) | Resilição Unilateral Indevida (Rescisão Indevida) | `folio:⟨UNVERIFIED⟩` |
| 9 | Area of Law | Intellectual Property Law | Direito de Propriedade Intelectual | `folio:⟨UNVERIFIED⟩` |
| 10 | Area of Law / Claim | Trademark Infringement | Violação de Marca (Contrafação de Marca) | `folio:⟨UNVERIFIED⟩` |
| 11 | Area of Law | International Trade Law | Direito do Comércio Internacional | `folio:⟨UNVERIFIED⟩` |
| 12 | Actor/Player – Role | Distributor (Claimant) | Distribuidor (Requerente) | `folio:⟨UNVERIFIED⟩` |
| 13 | Actor/Player – Role | Supplier (Respondent) | Fornecedor (Requerido) | `folio:⟨UNVERIFIED⟩` |
| 14 | Jurisdiction / Location | Brazil | Brasil | `folio:⟨UNVERIFIED⟩` |
| 15 | Jurisdiction / Location | Chile | Chile | `folio:⟨UNVERIFIED⟩` |
| 16 | Industry | Wine / Beverage Manufacturing & Distribution | Indústria Vinícola / Bebidas | `folio:⟨UNVERIFIED⟩` |

## Notes on the pt-BR labels

- **"Resilição" vs. "rescisão":** Brazilian doctrine uses *resilição unilateral* for one party ending a contract (Código Civil art. 473), and *rescisão* loosely for termination after breach. "Wrongful termination" of a distribution deal is usually argued as *resilição unilateral indevida*. The reasonable-notice and investment-recoupment rule in the paragraph after art. 473 is likely central to the distributor's claim.
- **Distribution regime:** Código Civil arts. 710–721 (agência e distribuição) may govern if Brazilian law applies. Lei 6.729/79 (Lei Ferrari) covers only vehicles, so it does not apply here.
- **Trademark:** Lei 9.279/96 (LPI) governs Brazilian marks. Arbitrability covers contractual and damages aspects, but registration validity stays with INPI and the courts.
- **CISG:** Brazil and Chile both ratified it, but it governs the individual sale contracts, not the distribution framework agreement itself. Consider tagging "Sale of Goods" if supply orders are in dispute.

## Getting the real IRIs

The scratchpad sits in a `folio-enrich` worktree. If you lift the no-lookup constraint, I can resolve each label to its actual IRI and official `pt-BR` `skos:prefLabel`/`altLabel` through `folio-python` (`FOLIO().search_by_label(...)`) or the FOLIO API. I can then replace every placeholder with verified values. FOLIO's own pt-BR translations may differ from my labels above. When they do, FOLIO's labels should win.
````

### Run A-forced F3

````markdown
# FOLIO Tags for the Brazil–Chile Wine Distribution Arbitration

**I can't give you real FOLIO IRIs from memory.** FOLIO IRIs are opaque random identifiers (for example, `https://folio.openlegalstandard.org/R` followed by about 22 random characters). They don't follow from the label, so any IRI I wrote would be invented, not recalled. Fake IRIs that look plausible would quietly corrupt your tagging, so I've left them blank. The concepts and pt-BR labels below are reliable. Resolve the IRIs with one lookup pass (see the end).

## Concept Tags

| # | FOLIO branch | Concept (en) | pt-BR label | FOLIO IRI |
|---|---|---|---|---|
| 1 | Area of Law | Arbitration / Alternative Dispute Resolution | Arbitragem / Resolução Alternativa de Disputas | *needs lookup* |
| 2 | Area of Law | International Commercial Arbitration | Arbitragem Comercial Internacional | *needs lookup* |
| 3 | Forum / Venue | International Chamber of Commerce (ICC) Court of Arbitration | Corte Internacional de Arbitragem da Câmara de Comércio Internacional (CCI) | *needs lookup* |
| 4 | Area of Law | Contract Law | Direito Contratual | *needs lookup* |
| 5 | Legal Matter / Cause of Action | Breach of Contract | Inadimplemento Contratual (Violação de Contrato) | *needs lookup* |
| 6 | Document / Artifact | Distribution Agreement | Contrato de Distribuição | *needs lookup* |
| 7 | Document / Artifact | Exclusive Distribution Agreement | Contrato de Distribuição Exclusiva | *needs lookup* |
| 8 | Cause of Action | Wrongful Termination of Contract | Rescisão Contratual Indevida (Resilição Unilateral Abusiva) | *needs lookup* |
| 9 | Area of Law | Intellectual Property Law | Direito da Propriedade Intelectual | *needs lookup* |
| 10 | Cause of Action | Trademark Infringement | Violação de Marca (Contrafação de Marca) | *needs lookup* |
| 11 | Area of Law | International Trade Law | Direito do Comércio Internacional | *needs lookup* |
| 12 | Jurisdiction | Brazil | Brasil | *needs lookup* |
| 13 | Jurisdiction | Chile | Chile | *needs lookup* |
| 14 | Industry | Beverage Manufacturing / Wineries | Fabricação de Bebidas / Vinícolas | *needs lookup* |
| 15 | Industry | Wholesale Trade (Beer, Wine, and Distilled Beverages) | Comércio Atacadista de Bebidas (Cerveja, Vinho e Destilados) | *needs lookup* |
| 16 | Actor / Player | Claimant | Requerente (Demandante) | *needs lookup* |
| 17 | Actor / Player | Respondent | Requerido(a) | *needs lookup* |
| 18 | Legal Remedy | Damages | Perdas e Danos (Indenização) | *needs lookup* |

## Tagging Notes

- **Wrongful termination:** FOLIO's "Wrongful Termination" concept leans toward employment law. This matter concerns termination of a commercial contract, so prefer a contract-termination concept. Brazilian practice also invokes indemnity for abrupt unilateral termination of a long-term distribution relationship (Civil Code art. 473, sole paragraph).
- **CISG:** CISG (Convention on Contracts for the International Sale of Goods) may also apply. Brazil and Chile are both parties, so if FOLIO has a CISG concept, add it.
- **Industry tags:** FOLIO imports NAICS-style industries. Tags 14–15 should map to those nodes.
- **pt-BR labels:** these give standard Brazilian legal terminology. FOLIO's own translated labels may word things differently; when they differ, its `prefLabel@pt-BR` wins.

## How to Resolve the IRIs

Run a label search with `folio-python` (`FOLIO().search_by_label("Trademark Infringement")`, then read the `iri` and `translations["pt-BR"]` fields). Or search the FOLIO browser at `folio.openlegalstandard.org`. Each search pulls the real IRI and FOLIO's own pt-BR label at once. When you're working in the folio-enrich worktree with lookups enabled, I can run that pass and fill in the table.
````

### Run B1, grounded

````markdown
I tagged the matter with 12 FOLIO concepts that have a pt-BR label. All 12 come from `get_concept` records, and the Portuguese text is copied exactly as the tool returned it.

### Concepts with a pt-BR label

| Facet | Concept (English label) | IRI | pt-BR label |
|---|---|---|---|
| **Area of law** | Arbitration Practice | https://folio.openlegalstandard.org/RXO2u2WBkUUcEG1jczLIcA | Prática de arbitragem |
| **Event** | Arbitration Event | https://folio.openlegalstandard.org/RC2LcVXjOZOiT3wqNc2SU5n | Evento de arbitragem |
| **Clause (ICC)** | ICC Arbitration Clause | https://folio.openlegalstandard.org/R7gdCxuo1pOeQuksIZwB5qC | Cláusula de arbitragem da ICC |
| **Contract type** | Distributor Agreement (preferred label: Distribution Agreement) | https://folio.openlegalstandard.org/RxvDJ1zl0ikIMMjfefcuyp | Contrato de distribuição |
| **Clause (exclusivity)** | Exclusivity Clause | https://folio.openlegalstandard.org/RDgEiiX23zftUP0Mggfc68n | Cláusula de exclusividade |
| **Claim category** | Breach of Contract Claims | https://folio.openlegalstandard.org/RbkhZxcSyqaKNyUivxRRpu | Reivindicações por quebra de contrato |
| **Claim** | Breach of Contract | https://folio.openlegalstandard.org/RC2fjcpsEbrVvVymvt4oASx | Quebra de contrato |
| **Clause (termination)** | Termination of Contract Clause | https://folio.openlegalstandard.org/R8uW7tSElnScC1uC2CnZTIL | Cláusula de rescisão de contrato |
| **Claim (IP)** | Trademark Infringement | https://folio.openlegalstandard.org/RBQCFqSF0Q0sCqCcEwv2pgz | Violação de marca registrada |
| **Area of law (IP)** | Trademark and Trade Dress Law | https://folio.openlegalstandard.org/R8phitqyUIXJ4ZdLaJjabna | Direito de Marcas e Designações Comerciais |
| **Asset** | Trademark Assets | https://folio.openlegalstandard.org/RBaL7gtiLlgraIRVwa44vg2 | Ativos de marca |
| **Industry** | Wholesale Trade Industry | https://folio.openlegalstandard.org/R97XG1bV4Mx6t2B4cpMlF0U | Indústria de comércio atacadista |

### Relevant concepts with no pt-BR label
FOLIO has no pt-BR translation for these, so I can't give you a Portuguese label for them:

| Facet | Concept | IRI |
|---|---|---|
| **Location (distributor)** | Brazil | https://folio.openlegalstandard.org/RBB829d2E27c3F9D3df5A1e5 |
| **Location (supplier)** | Chile | https://folio.openlegalstandard.org/R6062f0A6352c79Ae5c7E86b |
| **Forum** | Arbitration Forum | https://folio.openlegalstandard.org/R8LtU1k4pyiSD639zaq4vrM |
| **Event (termination)** | Contract Termination (preferred label: Agreement Termination) | https://folio.openlegalstandard.org/RB3TXlxV89oDiy7HtSN9cF0 |
| **Objective** | Cross-Border Objective (preferred label: International Objective) | https://folio.openlegalstandard.org/RBsiX2FSnOKhxvLGKoU9x1 |
| **Area of law** | International Trade Practice | https://folio.openlegalstandard.org/R8x520MB0xME0o4Wrg2o1so |
| **Area of law** | Contract Law | https://folio.openlegalstandard.org/RCIPwpgRpMs1eVz4vPid0pV |
| **Industry (supplier)** | Wineries (NAICS 312130) | https://folio.openlegalstandard.org/cbaI5ZloRfmVi2OXwB4cfA |

### What FOLIO doesn't cover
- **Wrongful termination:** FOLIO's only match, "Wrongful Discharge or Termination" (RDJYLQ3woaBs6FkT7wMbB4U), means firing an employee, so I left it out. The termination claim is covered by Breach of Contract plus the termination concepts above.
- **ICC as a forum:** FOLIO has no entry for the International Chamber of Commerce as an arbitral institution. The ICC appears only in the clause concept, so the forum tag is the generic Arbitration Forum.
- **Wine distribution:** FOLIO has no wine-wholesaler industry code. Its only wine wholesaler is "Beer and Ale Merchant Wholesalers", which is the wrong product, so I tagged the distributor with the broader Wholesale Trade Industry.
````

### Run B2, grounded

````markdown
I tagged the matter with 12 FOLIO concepts that have a Portuguese (Brazil) label. Each identifier and label below is exactly as `get_concept` returned it.

## Concepts with pt-BR labels

| # | Concept (en) | IRI | pt-BR label |
|---|---|---|---|
| 1 | Arbitration Practice | https://folio.openlegalstandard.org/RXO2u2WBkUUcEG1jczLIcA | Prática de arbitragem |
| 2 | Arbitration Event | https://folio.openlegalstandard.org/RC2LcVXjOZOiT3wqNc2SU5n | Evento de arbitragem |
| 3 | ICC Arbitration Clause | https://folio.openlegalstandard.org/R7gdCxuo1pOeQuksIZwB5qC | Cláusula de arbitragem da ICC |
| 4 | Distributor Agreement (preferred label: Distribution Agreement) | https://folio.openlegalstandard.org/RxvDJ1zl0ikIMMjfefcuyp | Contrato de distribuição |
| 5 | Exclusivity Clause | https://folio.openlegalstandard.org/RDgEiiX23zftUP0Mggfc68n | Cláusula de exclusividade |
| 6 | Breach of Contract Claims | https://folio.openlegalstandard.org/RbkhZxcSyqaKNyUivxRRpu | Reivindicações por quebra de contrato |
| 7 | Breach of Contract | https://folio.openlegalstandard.org/RC2fjcpsEbrVvVymvt4oASx | Quebra de contrato |
| 8 | Termination of Contract Clause | https://folio.openlegalstandard.org/R8uW7tSElnScC1uC2CnZTIL | Cláusula de rescisão de contrato |
| 9 | Trademark Infringement | https://folio.openlegalstandard.org/RBQCFqSF0Q0sCqCcEwv2pgz | Violação de marca registrada |
| 10 | Trademark and Trade Dress Law | https://folio.openlegalstandard.org/R8phitqyUIXJ4ZdLaJjabna | Direito de Marcas e Designações Comerciais |
| 11 | Seller (synonyms include "Supplier"), for the Chilean supplier | https://folio.openlegalstandard.org/R7kkf8NvitG8hubZUnTwevG | Vendedor |

FOLIO has no separate "exclusive distribution agreement" concept. The Distribution Agreement's direct children are Reseller, Financial Services Distribution, Publishing, and Wholesale Agreements. Tags 4 and 5 together cover the exclusive distribution agreement.

## Relevant concepts with no pt-BR label in FOLIO
These fit the matter, but their records have no pt-BR translation, so I give no Portuguese label:

- **Contract Termination** (preferred label: Agreement Termination): https://folio.openlegalstandard.org/RB3TXlxV89oDiy7HtSN9cF0. This is the event behind the wrongful-termination claim.
- **Arbitration Forum**: https://folio.openlegalstandard.org/R8LtU1k4pyiSD639zaq4vrM
- **Contract Law**: https://folio.openlegalstandard.org/RCIPwpgRpMs1eVz4vPid0pV
- **Cross-Border Objective** (preferred label: International Objective): https://folio.openlegalstandard.org/RBsiX2FSnOKhxvLGKoU9x1
- **Brazil**: https://folio.openlegalstandard.org/RBB829d2E27c3F9D3df5A1e5 (identifier SAM-BR)
- **Chile**: https://folio.openlegalstandard.org/R6062f0A6352c79Ae5c7E86b (identifier SAM-CL)
- **Wine and Distilled Alcoholic Beverage Merchant Wholesalers** (industry code NAICS 424820): https://folio.openlegalstandard.org/N0gwCr2vTyKkBHTZi8MHbQ

## Concepts I left out
- **Wrongful Discharge or Termination** (RDJYLQ3woaBs6FkT7wMbB4U): FOLIO defines it as firing an employee, not ending a commercial contract.
- **ICC as an institution**: FOLIO has no concept for the International Chamber of Commerce itself. The ICC Arbitration Clause is the closest match.
````

### Run B3, grounded

````markdown
I tagged the matter with 10 FOLIO concepts that have a Portuguese (Brazil) label. Each label is the `pt-br` value the tool returned. Seven other relevant concepts have no pt-BR label in FOLIO, and I list them separately. FOLIO has no concept for wrongful termination of a commercial contract.

## Concepts with a pt-BR label

| Facet | FOLIO concept (English) | IRI | pt-BR label |
|---|---|---|---|
| **Forum / ADR** | Arbitration Practice (identifier `D-ADR-ARB`) | https://folio.openlegalstandard.org/RXO2u2WBkUUcEG1jczLIcA | **Prática de arbitragem** |
| **ICC arbitration** | ICC Arbitration Clause | https://folio.openlegalstandard.org/R7gdCxuo1pOeQuksIZwB5qC | **Cláusula de arbitragem da ICC** |
| **Contract** | Distributor Agreement (preferred: Distribution Agreement) | https://folio.openlegalstandard.org/RxvDJ1zl0ikIMMjfefcuyp | **Contrato de distribuição** |
| **Exclusivity** | Exclusivity Clause | https://folio.openlegalstandard.org/RDgEiiX23zftUP0Mggfc68n | **Cláusula de exclusividade** |
| **Claim: breach** | Breach of Contract | https://folio.openlegalstandard.org/RC2fjcpsEbrVvVymvt4oASx | **Quebra de contrato** |
| **Claim category** | Breach of Contract Claims | https://folio.openlegalstandard.org/RbkhZxcSyqaKNyUivxRRpu | **Reivindicações por quebra de contrato** |
| **Claim: trademark** | Trademark Infringement | https://folio.openlegalstandard.org/RBQCFqSF0Q0sCqCcEwv2pgz | **Violação de marca registrada** |
| **Area of law** | Trademark and Trade Dress Law (identifier `INTP-TMRK`) | https://folio.openlegalstandard.org/R8phitqyUIXJ4ZdLaJjabna | **Direito de Marcas e Designações Comerciais** |
| **Claimant** | Claimant (the Brazilian distributor) | https://folio.openlegalstandard.org/R9UnetFhUZWHNEZJYjGQuXN | **Requerente** |
| **Respondent** | Seller (synonym "Supplier"; identifier `SELR`) | https://folio.openlegalstandard.org/R7kkf8NvitG8hubZUnTwevG | **Vendedor** |

## Relevant concepts without a pt-BR label

| Facet | FOLIO concept | IRI | Identifier |
|---|---|---|---|
| **Location** | Brazil | https://folio.openlegalstandard.org/RBB829d2E27c3F9D3df5A1e5 | `SAM-BR` |
| **Location** | Chile | https://folio.openlegalstandard.org/R6062f0A6352c79Ae5c7E86b | `SAM-CL` |
| **Forum** | Arbitration Forum | https://folio.openlegalstandard.org/R8LtU1k4pyiSD639zaq4vrM | — |
| **Termination** | Contract Termination (preferred: Agreement Termination) | https://folio.openlegalstandard.org/RB3TXlxV89oDiy7HtSN9cF0 | — |
| **Area of law** | Contract Law | https://folio.openlegalstandard.org/RCIPwpgRpMs1eVz4vPid0pV | — |
| **Cross-border** | Cross-Border Objective (preferred: International Objective) | https://folio.openlegalstandard.org/RBsiX2FSnOKhxvLGKoU9x1 | — |
| **Industry** | Wine and Distilled Alcoholic Beverage Merchant Wholesalers (NAICS 424820) | https://folio.openlegalstandard.org/N0gwCr2vTyKkBHTZi8MHbQ | — |

## Gaps
- **Wrongful termination:** I used Contract Termination for this claim. The only "wrongful termination" concept FOLIO has is "Wrongful Discharge or Termination," which covers firing an employee. It doesn't fit a distribution contract, so I left it out.
- **ICC as institution:** I found no concept for the ICC itself or for the ICC Arbitration Rules. The closest are ICC Arbitration Clause (above) and the general "Rules of Arbitration" (`R8xVj14htMg08Ph5XqOUdbf`). I didn't fetch the full record for Rules of Arbitration, so I don't know whether it has a pt-BR label.
- **"Supplier":** FOLIO has no separate concept for it. "Supplier" is a synonym under Seller, which is why that concept's pt-BR label reads "Vendedor".
````

### Codex (gpt-6.1-sol), forced prompt

````text
I can identify relevant concepts, but I do not reliably recall their **FOLIO IRIs**. Providing exact identifiers from memory would risk inventing them. The pt-BR labels below are proposed translations, not verified FOLIO preferred labels.

| Concept to tag | pt-BR label | FOLIO IRI |
|---|---|---|
| International commercial arbitration | Arbitragem comercial internacional | Not reliably recalled |
| Distribution agreement | Contrato de distribuição | Not reliably recalled |
| Exclusivity | Exclusividade | Not reliably recalled |
| Breach of contract | Inadimplemento contratual | Not reliably recalled |
| Wrongful termination of contract | Rescisão contratual indevida | Not reliably recalled |
| Trademark infringement | Violação de marca | Not reliably recalled |

Additional matter metadata: **ICC / Câmara de Comércio Internacional** as the administering institution; **Brazil / Brasil** and **Chile / Chile** as the parties’ countries. Those facts do not establish the governing law or arbitration seat.

This is a provisional concept mapping, **not a verified FOLIO tagging result**.

````
