# Evidence: FOLIO Mapper clip

- **URL:** https://mapper.openlegalstandard.org
- **Date:** 2026-11-25
- **Sign-in:** none. No LLM configured, no key entered; the app ran local fuzzy matching.
- **Script:** `capture/mapper.mjs` (re-shoot steps in `capture/README.md`).
- **Input:** 16 invented practice-area labels (no real firm data): Cross-border Arbitration,
  Employment Claims, Product Liability, Disputes > Distribution, Trademark Enforcement,
  Customs & Trade, Data Protection, M&A, Real Estate Leasing, Banking & Finance,
  Tax Controversy, Regulatory Investigations, Insolvency, Antitrust,
  Wine & Spirits Regulatory, Franchise Disputes.

## What the clip shows

1. **Input.** Taxonomy typed into "Enter text directly"; Parse Text; "16 items detected".
2. **Warning.** Continue, then "Continue Anyway" on the No LLM Connected dialog.
3. **Candidates.** Branch-grouped FOLIO candidates with confidence badges.
4. **Accepts.** The top candidate for three labels, with Candidate Details open:
   - Cross-border Arbitration -> Arbitration Practice (Service), **85**
   - Employment Claims -> Employment Claims (Objectives), **99**
   - Product Liability -> Product Liability Law (Area of Law), **98**

## Best candidate per label (same run, top badge score)

| Label | Top FOLIO candidate | Score |
|---|---|---|
| Disputes > Distribution | Dispute Service | 79 |
| Cross-border Arbitration | Arbitration Practice | 85 |
| Trademark Enforcement | Regulatory Enforcement | 47 |
| Customs & Trade | Trade Law | 51 |
| Data Protection | Data Protection Agreement | 86 |
| Employment Claims | Employment Claims | 99 |
| M&A | M&A Practice Components | 60 |
| Real Estate Leasing | Real Property Law | 99 |
| Banking & Finance | Banking Law Documents | 50 |
| Tax Controversy | Tax Law | 99 |
| Product Liability | Product Liability Law | 98 |
| Regulatory Investigations | Regulatory Compliance | 99 |
| Insolvency | Corporate Insolvency Law | 79 |
| Antitrust | Compliance | 91 |
| Wine & Spirits Regulatory | Regulatory Compliance | 99 |
| Franchise Disputes | Dispute Service | 79 |

Weak keyword matches (Trademark Enforcement 47, Banking & Finance 50) show the no-LLM
path's limits; the clip does not feature them.

## Outputs and screening

- `media/mapper.mp4`: 23.44 s, 585,613 bytes, 1920x1080 H.264.
- `media/mapper-still.jpg`: 3840x2160 (deviceScaleFactor 2), JPEG q85, item 3 of 16 accepted.
- **Screening:** 12 frames at one every 2 s, each inspected. No keys, tokens, emails,
  names or personal data. Frames deleted.
