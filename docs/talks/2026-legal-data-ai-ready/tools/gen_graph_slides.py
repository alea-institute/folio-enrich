"""Generate FOLIO concept-graph and 'show me all' query slides from live FOLIO data.
Scratch tooling for the talk deck; layout follows the Lawful Good c2/c2-id slides."""
import html, json, sys
from folio import FOLIO

OUT = sys.argv[1]
f = FOLIO()
B = "https://folio.openlegalstandard.org/"
E = html.escape

FLAGS = {
 "es-es": '<rect width="44" height="30" fill="#AA151B"/><rect y="7.5" width="44" height="15" fill="#F1BF00"/>',
 "es-mx": '<rect width="14.67" height="30" fill="#006847"/><rect x="14.67" width="14.67" height="30" fill="#FFFFFF"/><rect x="29.33" width="14.67" height="30" fill="#CE1126"/><circle cx="22" cy="15" r="3.2" fill="#8C6A2F"/>',
 "pt-br": '<rect width="44" height="30" fill="#009C3B"/><polygon points="22,3 40,15 22,27 4,15" fill="#FFDF00"/><circle cx="22" cy="15" r="6.5" fill="#002776"/>',
 "fr-fr": '<rect width="14.67" height="30" fill="#002654"/><rect x="14.67" width="14.67" height="30" fill="#FFFFFF"/><rect x="29.33" width="14.67" height="30" fill="#CE1126"/>',
 "de-de": '<rect width="44" height="10" fill="#000000"/><rect y="10" width="44" height="10" fill="#DD0000"/><rect y="20" width="44" height="10" fill="#FFCE00"/>',
 "ja-jp": '<rect width="44" height="30" fill="#FFFFFF"/><circle cx="22" cy="15" r="9" fill="#BC002D"/>',
 "zh-cn": '<rect width="44" height="30" fill="#EE1C25"/><polygon points="8,4 9.8,9.2 15,9.2 10.8,12.4 12.4,17.6 8,14.4 3.6,17.6 5.2,12.4 1,9.2 6.2,9.2" fill="#FFDE00"/>',
}
FLAGNAME = {"ja-jp": "Japanese flag", "zh-cn": "Chinese flag", "es-es": "Spanish (Spain) flag", "es-mx": "Mexican flag", "pt-br": "Brazilian flag", "fr-fr": "French flag", "de-de": "German flag"}

def w(text, px=26, pad=44):
    return int(len(text) * px * 0.52 + pad)

def chip(x_center, top, text, i, cls="anim-rise", width=None):
    wd = width or w(text)
    return (f'<p class="{cls}" style="--i:{i};position:absolute;left:{x_center - wd // 2}px;top:{top}px;width:{wd}px;height:52px;'
            'box-sizing:border-box;margin:0;padding:9px 20px;font-size:26px;line-height:30px;text-align:center;white-space:nowrap;'
            f'color:#F1E9DA;background:#1E2129;border:2px solid #8A8273;border-radius:26px">{E(text)}</p>')

def arrow(x1, y1, x2, y2, color="#8A8273"):
    if x1 == x2:
        d = f"M{x1} {y1}L{x2} {y2 - 10}"
    else:
        d = f"M{x1} {y1}C{x1} {y1 + 40} {x2} {y2 - 50} {x2} {y2 - 10}"
    return (f'<path d="{d}" stroke="{color}" stroke-width="3" fill="none"/>'
            f'<path d="M{x2 - 8} {y2 - 11}L{x2 + 8} {y2 - 11}L{x2} {y2}Z" fill="{color}"/>')

def svg(i, label, body):
    return (f'<svg class="anim-fade" aria-label="{E(label)}" style="--i:{i};position:absolute;left:0;top:0;width:1920px;height:1080px" '
            f'width="1920" height="1080" viewBox="0 0 1920 1080">{body}</svg>')

def graph_slide(sid, title, iri_id, crumb, root, columns, target_label, panel_alts, notes, lead=None):
    """columns: list of chains (each a list of labels from below root down to just above target)."""
    c = f[B + iri_id]
    tr = c.translations or {}
    parts = [f'<section id="{sid}" style="gap:48px">', f'<h2 class="hl anim-rise">{E(title)}</h2>']
    xs = [410, 940] if len(columns) == 2 else [700]
    rootx = 940 if len(columns) == 2 else 700
    rows = [366, 470, 574, 678]
    i = 2
    lines = []
    ends = []
    for ci, chain in enumerate(columns):
        x = xs[ci]
        offs = 0 if ci == 0 else 52
        prev = (rootx, 314)
        for k, lbl in enumerate(chain):
            top = rows[k] + offs
            lines.append((i + k * 2, arrow(prev[0], prev[1], x, top), f"{E(lbl)}"))
            parts.append(chip(x, top, lbl, i + k * 2 + 1))
            prev = (x, top + 52)
        ends.append(prev)
    tgt_w = max(480, w(target_label, 40, 80))
    tx = rootx if len(columns) == 1 else 850
    tgt_top = 790
    lands = [tx] if len(columns) == 1 else [760, 940]
    gold = "".join(arrow(ex, ey, lands[k], tgt_top, "#C9A24A") for k, (ex, ey) in enumerate(ends))
    for (ii, body, lbl) in lines:
        parts.insert(2, svg(ii, f"Arrow to {lbl}", body))
    parts.insert(2, svg(11, "Paths merge into " + target_label, gold))
    # breadcrumb + root
    rw = w(root)
    parts.append(f'<p class="anim-fade" style="--i:0;position:absolute;left:128px;top:273px;width:{rootx - rw // 2 - 20 - 128}px;margin:0;font-size:24px;line-height:30px;color:#A79F90;text-align:right;white-space:nowrap">{E(crumb)}</p>')
    parts.append(chip(rootx, 262, root, 1, cls="anim-fade"))
    # target
    parts.append(f'<p class="anim-pop" style="--i:12;position:absolute;left:{tx - tgt_w // 2}px;top:{tgt_top}px;width:{tgt_w}px;height:88px;box-sizing:border-box;margin:0;padding:20px 24px;font-family:\'Fraunces\',Georgia,serif;font-size:40px;font-weight:600;line-height:48px;text-align:center;white-space:nowrap;color:#1B1D24;background:#C9A24A;border-radius:44px">{E(target_label)}</p>')
    parts.append(f'<p class="anim-fade" style="--i:13;position:absolute;left:{tx - 230}px;top:894px;width:460px;height:44px;box-sizing:border-box;margin:0;padding:7px 16px;font-family:\'JetBrains Mono\',\'Courier New\',monospace;font-size:24px;line-height:30px;text-align:center;white-space:nowrap;color:#E6DBC6;background:#2A2E38;border-radius:8px">ID {iri_id}</p>')
    # panel
    parts.append('<div class="anim-fade" aria-label="Labels panel" style="--i:14;position:absolute;left:1208px;top:242px;width:604px;height:638px;box-sizing:border-box;background:#181A20;border:2px solid #C9A24A;border-radius:20px"></div>')
    parts.append(svg(14, target_label + " has these labels", f'<path d="M{1160} 834 L1170 826 L1180 834 L1170 842 Z" fill="#C9A24A"/><path d="M1180 834 H1208" stroke="#C9A24A" stroke-width="3"/>'))
    parts.append('<p class="anim-fade" style="--i:14;position:absolute;left:1228px;top:262px;width:564px;margin:0;font-size:24px;line-height:30px;color:#A79F90;letter-spacing:2px"><span style="color:#C9A24A;font-weight:700">SAME ID</span> · every name, every language</p>')
    y = 306
    n = 15
    for a in panel_alts:
        parts.append(f'<p class="anim-rise" style="--i:{n};position:absolute;left:1228px;top:{y}px;width:564px;height:62px;box-sizing:border-box;margin:0;padding:10px 28px;font-family:\'Fraunces\',Georgia,serif;font-size:32px;line-height:38px;white-space:nowrap;color:#F1E9DA;background:#1E2129;border:2px solid #C9A24A;border-radius:31px">{E(a)}</p>')
        y += 74; n += 1
    for loc in ["es-es", "es-mx", "pt-br", "fr-fr", "de-de", "ja-jp", "zh-cn"]:
        t = tr.get(loc)
        if not t or y > 800 or (loc == "es-mx" and t == tr.get("es-es")):
            continue
        fs = 24 if len(t) <= 34 else 21
        parts.append(f'<p class="anim-rise" style="--i:{n};position:absolute;left:1228px;top:{y}px;width:564px;height:52px;box-sizing:border-box;margin:0;padding:9px 16px 9px 74px;font-size:{fs}px;line-height:30px;white-space:nowrap;color:#E6DBC6;background:#1E2129;border:2px solid #3A3E48;border-radius:26px">{E(t)}</p>')
        parts.append(f'<svg class="anim-rise" aria-label="{FLAGNAME[loc]}" style="--i:{n};position:absolute;left:1250px;top:{y + 11}px;width:44px;height:30px" width="44" height="30" viewBox="0 0 44 30">{FLAGS[loc]}<rect x="0.5" y="0.5" width="43" height="29" fill="none" stroke="#8A8273" stroke-width="1"/></svg>')
        y += 62; n += 1
    if lead:
        parts.append(f'<p class="stmt anim-fade" style="--i:{n + 1};position:absolute;left:128px;top:952px;width:1664px;font-size:34px;color:#E6DBC6">{E(lead)}</p>')
    parts.append(f"<aside>{E(notes)}</aside>")
    parts.append("</section>")
    open(f"{OUT}/{sid}.html", "w").write("\n".join(parts) + "\n")


def query_slide(sid, query, root_label, root_id, highlight, snippet, snippet_lang, notes, extra_sub=None):
    root = f[B + root_id]
    kids = [f[k] for k in (root.parent_class_of or []) if k]
    labels = sorted({k.label for k in kids})
    # put highlight first-row middle for visibility
    labels = [l for l in labels if l != highlight]
    labels = labels[:11]
    labels.insert(4, highlight)
    tr = root.translations or {}
    p = [f'<section id="{sid}" style="gap:40px">']
    p.append('<div class="anim-rise" style="display:flex;align-items:center;gap:24px;background:#F1E9DA;border-radius:48px;padding:22px 40px;box-sizing:border-box">'
             '<x-icon name="Search" style="width:44px;height:44px;color:#1B1D24"></x-icon>'
             f'<p style="margin:0;font-family:\'Fraunces\',Georgia,serif;font-size:48px;line-height:1.15;color:#1B1D24">{E(query)}</p></div>')
    p.append('<div style="display:flex;gap:48px;flex:1">')
    p.append('<div style="flex:1;display:flex;flex-direction:column;gap:24px">')
    p.append(f'<p class="anim-pop" style="--i:2;align-self:flex-start;margin:0;padding:12px 28px;font-size:30px;font-weight:700;color:#1B1D24;background:#E6DBC6;border-radius:30px">{E(root_label)} · {len(kids)} kinds</p>')
    p.append('<div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:14px">')
    for k, l in enumerate(labels):
        if l == highlight:
            p.append(f'<p class="anim-pop" style="--i:{8};margin:0;padding:12px 18px;font-size:26px;line-height:1.2;font-weight:700;text-align:center;color:#1B1D24;background:#C9A24A;border-radius:26px">{E(l)}</p>')
        else:
            p.append(f'<p class="anim-fade" style="--i:{3 + k // 3};margin:0;padding:12px 18px;font-size:24px;line-height:1.2;text-align:center;color:#E6DBC6;background:#1E2129;border:2px solid #3A3E48;border-radius:26px">{E(l)}</p>')
    p.append('</div>')
    if extra_sub:
        p.append(f'<p class="sm anim-fade" style="--i:9">{E(extra_sub)}</p>')
    p.append('</div>')
    p.append('<div class="fragment" style="width:560px;display:flex;flex-direction:column;gap:20px">')
    p.append(f'<p class="lbl">Found, though the document never said “{E(root_label)}”</p>')
    p.append(f'<div class="card" style="border-color:#C9A24A"><p class="lbl">{E(snippet_lang)}</p><p class="stmt" style="font-size:36px">{snippet}</p></div>')
    p.append(f'<p class="txt"><span class="brass">→</span> tagged <b>{E(highlight)}</b> → counts as <b>{E(root_label)}</b></p>')
    p.append('</div>')
    p.append('</div>')
    p.append('<p class="stmt anim-fade" style="--i:10;position:absolute;left:128px;top:880px;width:1664px"><span class="brass">Ask for the parent.</span> Get every child, in every language.</p>')
    p.append(f"<aside>{E(notes)}</aside>")
    p.append("</section>")
    open(f"{OUT}/{sid}.html", "w").write("\n".join(p) + "\n")
    return len(kids), tr.get("es-es"), tr.get("pt-br")


S = "Source: live FOLIO ontology via folio-python, Nov. 25, 2026."
graph_slide("g-breach", "One concept, one ID, every language", "RC2fjcpsEbrVvVymvt4oASx",
            "Objectives › Litigation Objectives ›", "Litigation Claims",
            [["Civil Claims", "Contract & Quasi-Contract Claims", "Breach of Contract Claims"]],
            "Breach of Contract", ["Breach of Contract"],
            "Disputes. Breach of Contract sits in FOLIO’s tree under Litigation Claims, Civil Claims, Contract and Quasi-Contract Claims. It has one permanent ID, and the same ID carries Incumplimiento de contrato in Spanish and Quebra de contrato in Portuguese. A Chilean pleading and a Brazilian one point to the same concept. " + S)
graph_slide("g-distrib", "Documents get tags too", "RxvDJ1zl0ikIMMjfefcuyp",
            "Document / Artifact ›", "Document Types",
            [["Transactional Document", "Agreements"]],
            "Distributor Agreement", ["Distributor Agreement"],
            "Transactional work. Documents have their own branch: Document Types, Transactional Document, Agreements, Distributor Agreement. Contrato de Distribución, Contrato de distribuição: same ID. Tag your contracts once and you can find every distribution agreement, in any language. " + S)
graph_slide("g-trademark", "One claim, two families", "RBQCFqSF0Q0sCqCcEwv2pgz",
            "Objectives › Litigation Objectives › Litigation Claims ›", "Civil Claims",
            [["Intellectual Property Claims"], ["Business Torts and Actions", "Unfair Competition Claims"]],
            "Trademark Infringement", ["Trademark Infringement", "Service Mark Infringement"],
            "Real law overlaps, and so does FOLIO. Trademark Infringement belongs to two families at once: Intellectual Property Claims, and Unfair Competition Claims under Business Torts. Ask for either family and this claim comes back. Infracción de marca registrada; Violação de marca registrada. " + S)
graph_slide("g-identity", "Two parents, one ID", "RFjY2mO804t9gJNy5Dn4P1",
            "Objectives › Litigation Objectives ›", "Litigation Claims",
            [["Criminal Claims", "Crimes Against Property", "Criminal Theft", "Criminal Fraud"], ["Civil Claims", "Privacy Claims"]],
            "Identity Theft", ["Impersonation", "Theft of Personal Identifying Info"],
            "Identity Theft is both a crime (Criminal Claims, Crimes Against Property, Criminal Theft, Criminal Fraud) and a civil privacy claim (Civil Claims, Privacy Claims). One ID, two parents. FOLIO’s label is Impersonation / Identity Theft; Spanish Suplantación de identidad / Robo de identidad; Portuguese Impersonação / Roubo de identidade. " + S)
graph_slide("g-force", "Two parents, one ID", "RBMu52Fw2HtrbeGoI6XKoJV",
            "Objectives › Litigation Objectives › Litigation Claims ›", "Civil Claims",
            [["Constitutional Claims", "U.S. Constitutional Claims", "4th Amendment Claim", "Unreasonable Search and Seizure Claim"], ["Governmental Tort Liability"]],
            "Excessive Force Claim", ["Police Brutality", "Police Brutality Claim"],
            "Excessive Force Claim has two parents: Unreasonable Search and Seizure Claim, through the U.S. Constitutional Claims line, and Governmental Tort Liability. Synonyms on the same ID include Police Brutality. Spanish Reclamación por uso excesivo de la fuerza; Portuguese Reivindicação de uso excessivo da força. " + S)
n1, es1, pt1 = query_slide("q-privacy", "“Show me all the Privacy Claims.”", "Privacy Claims", "Rd7uelGFqCTWSgf9lWki5N",
            "Impersonation / Identity Theft",
            "“…la demandante sufrió <b>robo de identidad</b> tras la filtración…”", "Example document · Spanish",
            "Ask for the parent and you get every child. Privacy Claims has these kinds underneath it in FOLIO, including Impersonation / Identity Theft. Click: a Spanish document that only says robo de identidad was tagged Identity Theft, so it comes back when you ask for Privacy Claims, even though it never uses those words, and even though it isn’t in English. The example sentence is illustrative. " + S,
            extra_sub="Plus their children: Forgery, Credit Theft, Deepfake Claim…")
n2, es2, pt2 = query_slide("q-govtort", "“Show me all the Governmental Tort Liability claims.”", "Governmental Tort Liability", "RBREngQZS9QIgeWCOMPBLIo",
            "Excessive Force Claim",
            "“…the complaint alleges <b>police brutality</b> during the arrest…”", "Example document · English",
            "Same move for claims against the state. Governmental Tort Liability (Spanish: Responsabilidad civil extracontractual del Estado; Portuguese: Responsabilidade civil do Estado) has these kinds underneath, including Excessive Force Claim. Click: a complaint that only says police brutality is tagged Excessive Force Claim, because Police Brutality is one of its FOLIO names, so it answers the question. Note: FOLIO files Government Immunity as a defense, not a claim, so the claim-side parent is Governmental Tort Liability. The example sentence is illustrative. " + S,
            extra_sub="Plus their children: Discrimination Claims, Voting Rights Claims…")
print(json.dumps({"privacy_kids": n1, "govtort_kids": n2}))
