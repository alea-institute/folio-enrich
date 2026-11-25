# ontology-dynamic on the demo memo (2026-11-25)

**What ran.** `ontdyn` 0.1.0 (ontology-dynamic `main` at `4f45473`) against the synthetic demo
memo (`demo-document.md`, first HTML-comment line stripped). All state lived in a scratch
directory: its own store, source cache and model archive. The repo's live data and tracked
files were not touched.

**Provider and cost.** Decider Claude Haiku, generator Claude Sonnet, both through the
`claude` CLI on the existing Claude subscription (sandboxed by bubblewrap; the subscription
login file passed by path only). No API key, no metered spend: **US$0.00**. Usage gate
reading at start: 55% of the weekly window.

## Commands

Scratch layout: `config.json` (store `runtime/corpora.sqlite`, master `FOLIO.owl` from the
earlier bake-off, OpenGloss sidecar and crosswalk, `candidate_budget` 60), `runtime/models.json`
(Claude haiku decider, Claude sonnet generator, `call_budget` 200, Jev cap 0), and a
one-document corpus manifest `corpora/distmemo/manifest.json`
(`format: {"kind":"plain","citation":"Synthetic Memorandum (demo)"}`, `public_law: false`).

```sh
ontdyn --config config.json ingest distmemo distribution-memo     # Ingested 1 document(s) in distmemo.
ontdyn --config config.json tag distmemo distribution-memo        # 212 tags for distribution-memo in distmemo
box-run --max 8G -- ontdyn --config config.json propose distmemo distribution-memo --budget 60
ONTDYN_VIEWER_PORT=8811 ontdyn-viewer runtime/corpora.sqlite FOLIO.owl
```

Pass 1 (07:30-07:42, 11 min 53 s, the pass the clip shows), verbatim:

```
Proposing distribution-memo: 6 admitted, 1 held, 76 cut by budget, 0 request too large; 101 decider / 82 generator live calls.
```

136 candidates; 41 confirmed as legal concepts and drafted; 34 unsupported at the support check;
6 admitted; 1 held as duplicate; 76 cut by budget.

Pass 2 (07:51-08:05) resumed with `--budget 140` on a fresh build of the CLI (see "Viewer
build" below) and stopped with `per-run live call budget exhausted` after 200 live calls.
Its admissions stay in the store: the queue grew to 20 items (13 proposals, 7 held drafts).
It did **not** propose an International Chamber of Commerce institution concept.

**Viewer build.** The prebuilt `target/release/ontdyn-viewer` (Nov 14 08:18) predates the
human QA mode merged in #36, so `ontdyn-viewer` and `ontdyn` were rebuilt from the same
commit into a scratch `--target-dir` (`cargo build --release --offline -p ontdyn-viewer`,
1 min 55 s; `-p ontdyn-cli`, 2 min 53 s). The QA build migrates the store, so the old CLI
can no longer open a store the new viewer has opened.

## Headline proposal: a concept FOLIO lacks

FOLIO's tagger matches the memo's "wrongful termination" only to **Wrongful Discharge or
Termination** (ancestry: Employment Claims → Civil Claims → Litigation Claims → Litigation
Objectives → Objectives), defined as "the illegal firing or dismissal of an employee by an
employer". The memo's claim concerns a terminated distribution agreement, so the pipeline
proposed:

- **Label:** Wrongful Termination of Commercial Contract
- **Parent:** is a kind of **Breach of Contract** (`https://folio.openlegalstandard.org/RC2fjcpsEbrVvVymvt4oASx`)
- **Definition:** "A claim that a party improperly terminated a commercial contract, such as an international sale or distribution agreement, in breach of the contract or the governing law. It is distinct from employment-related wrongful discharge."
- **Evidence (verbatim, bytes 540-652):** "Claims: breach of contract; breach of warranty; wrongful termination; trademark infringement; unfair competition"

## All pass-1 proposals (what the clip's queue shows)

| Label | Parent (FOLIO) | Verbatim evidence |
|---|---|---|
| Wrongful Termination of Commercial Contract | Breach of Contract | "Claims: breach of contract; breach of warranty; wrongful termination; trademark infringement; unfair competition" |
| Prejudgment Interest | Damages | "Remedies Sought: direct damages; consequential damages; lost profits; prejudgment interest; preliminary injunction; accounting of profits" |
| Lost Profits | Economic Damages | same Remedies Sought line |
| Prejudgment Interest (held draft, duplicate of the proposal above) | Damages | same Remedies Sought line |
| Accounting of Profits | Damages | same Remedies Sought line |
| Product Recall Order | Administrative Order | "Ministry of Agriculture administrative order: product recall; customs duties; regulatory fine; storage costs." |
| Exclusive Distribution Agreement | Distributor Agreement | "Exclusive Distribution Agreement, five-year contract term." |

Pass 2 added, among others: "Arbitral Award" (parent Arbitration Clause; "arbitration clause,
New York Convention; arbitral award enforcement, Brazil, Chile, Peru."), "Unfair Competition"
(parent Litigation Claims), two near-identical limitation-of-liability carve-outs, two
near-identical force-majeure items, and "Cordillera is a Corporation" (a fact, not a
concept). These show the curator load the CFAA walkthrough describes: duplicates and
clause slicing that a reviewer rejects. Full pass-2 list with definitions: see
"Full proposal list" below.

## Clip and still

- **`media/ontdyn.mp4`:** 24.8 s, 1920×1080, H.264 CRF 28, 0.68 MB. Script `capture/ontdyn.mjs`;
  trimmed `-ss 0.6`. Sequence: QA annotated text of the memo (FOLIO tags underlined) → click
  "wrongful termination": FOLIO's only match is employment-flavoured "Wrongful Discharge or
  Termination" → QA Review queue, filter "Proposals awaiting review" → 1/7 "Wrongful
  Termination of Commercial Contract" with its definition and source line → proposal page:
  "is a kind of — Breach of Contract" and "Evidence in context" with the quoted Claims line
  highlighted (bytes 540–652). Read-only: no review action submitted.
- **`media/ontdyn-still.jpg`:** proposal page at 2× scale, downscaled to 1920 wide.
- **Screening:** 12 frames (1 per 2 s) plus the still inspected; only synthetic party names
  and FOLIO labels; no keys, tokens, emails or personal data.

## Full proposal list (after pass 2)

### Wrongful Termination of Commercial Contract
- parent: Breach of Contract (https://folio.openlegalstandard.org/RC2fjcpsEbrVvVymvt4oASx)
- definition: A claim that a party improperly terminated a commercial contract, such as an international sale or distribution agreement, in breach of the contract or the governing law. It is distinct from employment-related wrongful discharge.
- evidence (bytes 540-652): "Claims: breach of contract; breach of warranty; wrongful termination; trademark infringement; unfair competition"

### Prejudgment Interest
- parent: Damages (https://folio.openlegalstandard.org/RCCv5YLoHUOm5AlqcCBzqGf)
- definition: A remedy sought in a dispute: interest on a monetary award, calculated for the period before a final decision or award is issued. In this matter it is sought together with direct damages, consequential damages and lost profits.
- evidence (bytes 653-790): "Remedies Sought: direct damages; consequential damages; lost profits; prejudgment interest; preliminary injunction; accounting of profits"

### Lost Profits
- parent: Economic Damages (https://folio.openlegalstandard.org/RouKBMqFNMZxi21EPh6JJ6)
- definition: A remedy sought as a form of monetary damages for the profits a party would have earned but for the opposing party's alleged wrongdoing. In this matter it is listed among the remedies sought, alongside direct damages, consequential damages, prejudgment interest, a preliminary injunction and an accounting of profits.
- evidence (bytes 653-790): "Remedies Sought: direct damages; consequential damages; lost profits; prejudgment interest; preliminary injunction; accounting of profits"

### Accounting of Profits
- parent: Damages (https://folio.openlegalstandard.org/RCCv5YLoHUOm5AlqcCBzqGf)
- definition: A remedy sought in the matter, alongside damages and injunctive relief, whereby the claimant seeks an accounting of the profits the opposing party earned, here in connection with trademark infringement and unfair competition claims.
- evidence (bytes 653-790): "Remedies Sought: direct damages; consequential damages; lost profits; prejudgment interest; preliminary injunction; accounting of profits"

### Product Recall Order
- parent: Administrative Order (https://folio.openlegalstandard.org/RqR6mIq4quTMy3JrdpVViL)
- definition: An administrative order, as issued here by the Brazilian Ministry of Agriculture after customs detention of a wine shipment and laboratory reports showing a regulatory violation, that requires a product recall. In the source it appears with customs duties, a regulatory fine and storage costs.
- evidence (bytes 1208-1317): "Ministry of Agriculture administrative order: product recall; customs duties; regulatory fine; storage costs."

### Exclusive Distribution Agreement
- parent: Distributor Agreement (https://folio.openlegalstandard.org/RxvDJ1zl0ikIMMjfefcuyp)
- definition: A distributor agreement under which a supplier grants a distributor exclusive rights to distribute its products. In the source, it has a five-year contract term, supplier warranties (product specifications, certificate of origin, Brazilian import regulations, food safety regulations, labeling requirements), and payment mechanics (invoice, letter of credit, commercial bank, payment term, bill of lading).
- evidence (bytes 803-861): "Exclusive Distribution Agreement, five-year contract term."

### Limitation of Liability Exclusion for Gross Negligence and Willful Misconduct
- parent: Limitation of Liability Clause (https://folio.openlegalstandard.org/RBukB9MGGdY4Kwx3b6itiwi)
- definition: A limitation of liability clause whose cap or limit does not apply to (excludes) liability arising from gross negligence and willful misconduct.
- evidence (bytes 2484-2564): "Limitation of liability clause excludes gross negligence and willful misconduct."

### Limitation of Liability Carve-Out for Gross Negligence and Willful Misconduct
- parent: Limitation of Liability Clause (https://folio.openlegalstandard.org/RBukB9MGGdY4Kwx3b6itiwi)
- definition: A limitation of liability clause whose cap or exclusion of liability does not apply to, i.e., excludes from its scope, losses arising from gross negligence and willful misconduct.
- evidence (bytes 2484-2564): "Limitation of liability clause excludes gross negligence and willful misconduct."

### Force Majeure Clause Not a Defense
- parent: Force Majeure Clause (https://folio.openlegalstandard.org/R7mT3oM7UJnGCUIq15FYip5)
- definition: A position in the matter's analysis that the force majeure clause in the contract provides no defense to the claims asserted.
- evidence (bytes 2565-2598): "Force majeure clause: no defense."

### Arbitral Award
- parent: Arbitration Clause (https://folio.openlegalstandard.org/RWQW185M6gqosVVQA1GE0A)
- definition: The decision issued in an arbitration, here arising under an arbitration clause governed by the New York Convention, for which enforcement is contemplated in Brazil, Chile and Peru.
- evidence (bytes 2772-2861): "arbitration clause, New York Convention; arbitral award enforcement, Brazil, Chile, Peru."

### Force Majeure Defense Unavailable
- parent: Force Majeure Clause (https://folio.openlegalstandard.org/R7mT3oM7UJnGCUIq15FYip5)
- definition: In the matter analyzed, the force majeure clause is assessed as providing no defense to the breach claims.
- evidence (bytes 2565-2598): "Force majeure clause: no defense."

### Cordillera is a Corporation
- parent: Corporation (https://folio.openlegalstandard.org/RDdgYa5ZbqVnS9aGrOwQu5h)
- definition: Viña Cordillera S.A., the opposing party in the matter, is identified in the source as a corporation based in Santiago, Chile.
- evidence (bytes 148-215): "Opposing Party: Viña Cordillera S.A., corporation, Santiago, Chile"

### Unfair Competition
- parent: Litigation Claims (https://folio.openlegalstandard.org/R9q7GJc1zsYT0P4Xdp6l9Oz)
- definition: A claim asserted in the matter, alongside trademark infringement, breach of contract, breach of warranty and wrongful termination, by Distribuidora Atlântica Ltda. against Viña Cordillera S.A. in ICC arbitration seated in Lima, Peru.
- evidence (bytes 540-652): "Claims: breach of contract; breach of warranty; wrongful termination; trademark infringement; unfair competition"

