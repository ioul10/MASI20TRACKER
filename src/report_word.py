"""Export du bilan hebdomadaire au format Word (.docx), modifiable.

Graphiques en images (matplotlib) : aucune dépendance à un navigateur,
fonctionne tel quel sur Streamlit Cloud.
"""
from __future__ import annotations

import io

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import matplotlib.ticker as mtick  # noqa: E402
import pandas as pd  # noqa: E402
from docx import Document  # noqa: E402
from docx.enum.section import WD_ORIENT  # noqa: E402
from docx.enum.table import WD_TABLE_ALIGNMENT  # noqa: E402
from docx.enum.text import WD_ALIGN_PARAGRAPH  # noqa: E402
from docx.oxml import OxmlElement  # noqa: E402
from docx.oxml.ns import qn  # noqa: E402
from docx.shared import Cm, Pt, RGBColor  # noqa: E402

from . import config as C  # noqa: E402
from . import futures as F  # noqa: E402
from .fmt import date_courte, date_longue, jour, mad, nombre, pct  # noqa: E402


def _rgb(h: str) -> RGBColor:
    h = h.lstrip("#")
    return RGBColor(int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))


NAVY, GOLD, UP, DOWN, MUTED = (_rgb(C.NAVY), _rgb(C.GOLD), _rgb(C.UP), _rgb(C.DOWN), _rgb(C.MUTED))
FONT = "Calibri"

plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 9, "axes.spines.top": False,
                     "axes.spines.right": False, "axes.edgecolor": "#C9D0DC", "axes.labelcolor": C.MUTED,
                     "xtick.color": C.MUTED, "ytick.color": C.MUTED, "axes.grid": True, "grid.color": C.GRID,
                     "grid.linewidth": 0.6, "axes.axisbelow": True})


# ------------------------------------------------------------- petits outils
def _shade(cell, hexa: str) -> None:
    tc = cell._tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), hexa.lstrip("#"))
    tc.append(shd)


def _bordure_bas(par, couleur: str, taille: int = 12) -> None:
    ppr = par._p.get_or_add_pPr()
    bdr = OxmlElement("w:pBdr")
    b = OxmlElement("w:bottom")
    for k, v in (("w:val", "single"), ("w:sz", str(taille)), ("w:space", "4"), ("w:color", couleur.lstrip("#"))):
        b.set(qn(k), v)
    bdr.append(b)
    ppr.append(bdr)


def _run(par, texte, gras=False, couleur=None, taille=None, italique=False):
    r = par.add_run(texte)
    r.bold, r.italic = gras, italique
    r.font.name = FONT
    if couleur is not None:
        r.font.color.rgb = couleur
    if taille:
        r.font.size = Pt(taille)
    return r


def _titre(doc, texte: str) -> None:
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(14)
    p.paragraph_format.space_after = Pt(6)
    p.paragraph_format.keep_with_next = True
    _run(p, texte.upper(), gras=True, couleur=NAVY, taille=11.5)
    _bordure_bas(p, C.GOLD, 12)


def _couleur(v):
    if v is None or pd.isna(v) or v == 0:
        return None
    return UP if v > 0 else DOWN


def _table(doc, entetes, lignes, largeurs_cm, aligner_droite=()):
    """lignes : listes de cellules ; une cellule peut être (texte, valeur signée) pour colorer."""
    t = doc.add_table(rows=1, cols=len(entetes))
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    t.style = "Table Grid"
    for i, h in enumerate(entetes):
        c = t.rows[0].cells[i]
        _shade(c, C.NAVY)
        c.paragraphs[0].text = ""
        _run(c.paragraphs[0], h, gras=True, couleur=RGBColor(255, 255, 255), taille=8.5)
        if i in aligner_droite:
            c.paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.RIGHT
    for k, ligne in enumerate(lignes):
        cells = t.add_row().cells
        for i, v in enumerate(ligne):
            texte, signe = v if isinstance(v, tuple) else (v, None)
            p = cells[i].paragraphs[0]
            _run(p, str(texte), gras=signe is not None and _couleur(signe) is not None, couleur=_couleur(signe), taille=8.5)
            if i in aligner_droite:
                p.alignment = WD_ALIGN_PARAGRAPH.RIGHT
            if k % 2 == 1:
                _shade(cells[i], "F3F5F9")
    for row in t.rows:
        for i, w in enumerate(largeurs_cm):
            row.cells[i].width = Cm(w)
    # bordures discrètes
    tbl = t._tbl.tblPr
    bd = OxmlElement("w:tblBorders")
    for side in ("top", "left", "bottom", "right", "insideH", "insideV"):
        e = OxmlElement(f"w:{side}")
        e.set(qn("w:val"), "single")
        e.set(qn("w:sz"), "4")
        e.set(qn("w:color"), "D5DBE6")
        bd.append(e)
    tbl.append(bd)
    return t


def _image(doc, fig, largeur_cm=17.0) -> None:
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=200, bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    doc.add_picture(buf, width=Cm(largeur_cm))
    doc.paragraphs[-1].alignment = WD_ALIGN_PARAGRAPH.CENTER


def _fmt_axe_fr(ax, axe="y", dec=0, suffixe=""):
    f = mtick.FuncFormatter(lambda v, _: nombre(v, dec) + suffixe)
    (ax.yaxis if axe == "y" else ax.xaxis).set_major_formatter(f)


# ------------------------------------------------------------------ graphiques
def _g_indice_volume(o):
    j = o["jours"]
    v = o.get("volumes_jour")
    x = [jour(d) for d in j["date"]]
    deux = v is not None and len(v)
    fig, axes = plt.subplots(2 if deux else 1, 1, figsize=(8.5, 4.6 if deux else 2.6), sharex=True,
                             gridspec_kw={"height_ratios": [1.1, 1]} if deux else None)
    ax = axes[0] if deux else axes
    ax.plot(x, j["cloture"], color=C.GOLD, lw=2.5, marker="o", ms=6)
    for xi, y, var in zip(x, j["cloture"], j["var"]):
        if pd.notna(var):
            ax.annotate(pct(var), (xi, y), textcoords="offset points", xytext=(0, 8), ha="center", fontsize=8,
                        color=C.UP if var > 0 else C.DOWN)
    ax.set_title("MASI 20 (pts)", loc="left", fontsize=9, color=C.MUTED)
    lo, hi = j["cloture"].min(), j["cloture"].max()
    ax.set_ylim(lo - (hi - lo) * 0.3 - 2, hi + (hi - lo) * 0.45 + 2)
    _fmt_axe_fr(ax)
    if deux:
        vv = v.set_index("date").reindex(j["date"]).fillna(0)
        a2 = axes[1]
        a2.bar(x, vv["marche"] / 1e6, color="#D8DEEA", width=0.6, label="Marché total")
        a2.bar(x, vv["masi20"] / 1e6, color=C.NAVY, width=0.35, label="Valeurs du MASI 20")
        a2.set_title("Volume du marché central (M MAD)", loc="left", fontsize=9, color=C.MUTED)
        a2.legend(frameon=False, fontsize=8, loc="upper left", ncol=2)
        _fmt_axe_fr(a2)
    fig.tight_layout()
    return fig


def _g_contributions(b):
    d = b.sort_values("contribution_pb")
    plein = d["tendance_volume"].fillna(1) >= 1 if "tendance_volume" in d else pd.Series(True, index=d.index)
    col = [(C.UP if c >= 0 else C.DOWN) if p else ("#9BD3B4" if c >= 0 else "#EBA9A9")
           for c, p in zip(d["contribution_pb"], plein)]
    fig, ax = plt.subplots(figsize=(8.5, 0.27 * len(d) + 0.8))
    ax.barh(d["nom"].str.title(), d["contribution_pb"], color=col, height=0.65)
    ax.axvline(0, color=C.MUTED, lw=0.8)
    ax.grid(axis="y", visible=False)
    ax.set_xlabel("Contribution à la variation de l'indice (points de base) · couleur pâle = volume en baisse")
    _fmt_axe_fr(ax, "x")
    ax.tick_params(axis="y", labelsize=8)
    fig.tight_layout()
    return fig


def _g_volume_poids(b):
    fig, ax = plt.subplots(figsize=(8.5, 4.2))
    x, y = b["poids"] * 100, b["part_volume"] * 100
    m = max(x.max(), y.max()) * 1.12
    ax.plot([0, m], [0, m], ls="--", color="#C9D0DC", lw=1)
    ax.scatter(x, y, s=55, c=[C.UP if r >= 0 else C.DOWN for r in b["rendement"]], edgecolor="white", lw=1.5, zorder=3)
    for n, xi, yi, pv, pw in zip(b["nom"], x, y, b["part_volume"], b["poids"]):
        if pv >= 0.05 or pw >= 0.08:
            ax.annotate(n.title(), (xi, yi), textcoords="offset points", xytext=(0, 6), ha="center", fontsize=7.5)
    ax.set_xlim(0, m), ax.set_ylim(0, m)
    ax.set_xlabel("Poids dans l'indice (%)")
    ax.set_ylabel("Part du volume (%)")
    ax.text(m * 0.02, m * 0.95, "Plus de volume que de poids", color=C.MUTED, fontsize=8, va="top")
    ax.text(m * 0.98, m * 0.03, "Moins de volume que de poids", color=C.MUTED, fontsize=8, ha="right")
    _fmt_axe_fr(ax)
    _fmt_axe_fr(ax, "x")
    fig.tight_layout()
    return fig


def _g_futures(fj):
    fig, ax = plt.subplots(figsize=(8.5, 2.9))
    jours = sorted(fj["date"].unique())
    tick = sorted(fj["ticker"].unique(), key=lambda t: F.echeance(t)[1])
    w = 0.8 / max(len(tick), 1)
    for k, t in enumerate(tick):
        g = fj[fj["ticker"] == t].set_index("date").reindex(jours)
        xs = [i + (k - (len(tick) - 1) / 2) * w for i in range(len(jours))]
        ax.bar(xs, g["cloture"], width=w * 0.92, color=F.couleur(t), label=F.libelle(t))
    ax.set_xticks(range(len(jours)), [jour(pd.Timestamp(d)) for d in jours])
    lo, hi = fj["cloture"].min(), fj["cloture"].max()
    ax.set_ylim(lo - (hi - lo) * 0.6 - 5, hi + (hi - lo) * 0.3 + 5)
    ax.legend(frameon=False, fontsize=8, ncol=len(tick), loc="upper left")
    ax.set_title("Clôture des futures (pts)", loc="left", fontsize=9, color=C.MUTED)
    _fmt_axe_fr(ax)
    fig.tight_layout()
    return fig


def _g_technique(t):
    t = t.tail(90)
    fig, (a1, a2) = plt.subplots(2, 1, figsize=(8.5, 4.2), sharex=True, gridspec_kw={"height_ratios": [3, 1]})
    a1.fill_between(t["date"], t["bb_bas"], t["bb_haut"], color="#9AA7BD", alpha=0.15, lw=0, label="Bollinger")
    a1.plot(t["date"], t["cloture"], color=C.NAVY, lw=1.8, label="MASI 20")
    a1.plot(t["date"], t["ema20"], color=C.GOLD, lw=1.3, label="EMA 20")
    a1.plot(t["date"], t["ema40"], color=C.SERIES[3], lw=1.3, label="EMA 40")
    a1.legend(frameon=False, fontsize=8, ncol=4, loc="upper left")
    _fmt_axe_fr(a1)
    a2.plot(t["date"], t["rsi14"], color=C.NAVY_2, lw=1.3)
    for y, c in ((70, C.DOWN), (30, C.UP)):
        a2.axhline(y, color=c, ls="--", lw=0.8)
    a2.set_ylim(0, 100)
    a2.set_yticks([30, 50, 70])
    a2.set_ylabel("RSI 14")
    a2.xaxis.set_major_formatter(matplotlib.dates.DateFormatter("%d/%m"))
    fig.tight_layout()
    return fig


# ------------------------------------------------------------------ document
def docx_bilan(o: dict, avis: str, auteur: str = "") -> bytes:
    doc = Document()
    sec = doc.sections[0]
    sec.page_width, sec.page_height = Cm(21), Cm(29.7)
    sec.orientation = WD_ORIENT.PORTRAIT
    for m in ("left_margin", "right_margin"):
        setattr(sec, m, Cm(2))
    sec.top_margin, sec.bottom_margin = Cm(1.6), Cm(1.6)
    st = doc.styles["Normal"]
    st.font.name, st.font.size = FONT, Pt(10)
    st.element.rPr.rFonts.set(qn("w:eastAsia"), FONT)

    fin = o["seances"][-1]
    # Pied de page
    pf = sec.footer.paragraphs[0]
    _run(pf, f"MASI20TRACKER · Bilan hebdomadaire au {date_courte(fin)} · Source : bulletins de la Bourse de Casablanca",
         couleur=MUTED, taille=7.5)

    # En-tête
    p = doc.add_paragraph()
    _run(p, "MASI", gras=True, couleur=NAVY, taille=20)
    _run(p, "20", gras=True, couleur=GOLD, taille=20)
    _run(p, "TRACKER", gras=True, couleur=NAVY, taille=20)
    _run(p, "   Bilan hebdomadaire", couleur=MUTED, taille=13)
    p = doc.add_paragraph()
    _run(p, f"Semaine du {date_courte(o['debut'])} au {date_courte(fin)} · {len(o['seances'])} séances",
         couleur=MUTED, taille=10)
    _bordure_bas(p, C.NAVY, 18)

    # Chiffres clés
    fu = o.get("futures") or {}
    tab = fu.get("tableau", pd.DataFrame())
    cles = [("MASI 20", o["masi20"], o["masi20_var"], None)]
    cles += [(r["contrat"], r["cloture"], r["var_semaine"], r["base_pct"]) for _, r in tab.iterrows()]
    t = doc.add_table(rows=2, cols=len(cles))
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    for i, (nom, val, var, base) in enumerate(cles):
        c1, c2 = t.rows[0].cells[i], t.rows[1].cells[i]
        _shade(c1, C.NAVY if i == 0 else "EEF2F9")
        _shade(c2, C.NAVY if i == 0 else "EEF2F9")
        blanc = RGBColor(255, 255, 255)
        p1 = c1.paragraphs[0]
        _run(p1, nom, gras=True, couleur=GOLD if i == 0 else NAVY, taille=8.5)
        _run(c1.add_paragraph(), nombre(val), gras=True, couleur=blanc if i == 0 else NAVY, taille=14)
        p2 = c2.paragraphs[0]
        _run(p2, pct(var), gras=True, couleur=(blanc if i == 0 else _couleur(var)), taille=10)
        if base is not None and pd.notna(base):
            _run(p2, f"  base {pct(base, 1)}", couleur=MUTED, taille=8)
        for c in (c1, c2):
            for par in c.paragraphs:
                par.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p = doc.add_paragraph()
    _run(p, f"Variations depuis la clôture du {date_courte(o['masi20_ref_date'])} (dernière séance de la semaine précédente). "
            "Base = future − MASI 20.", couleur=MUTED, taille=8, italique=True)

    # Avis DRF en premier : c'est ce qu'on lit d'abord
    _titre(doc, "Avis DRF")
    for ligne in [x for x in avis.split("\n") if x.strip()]:
        p = doc.add_paragraph()
        p.paragraph_format.space_after = Pt(4)
        _run(p, ligne.strip(), taille=10.5)

    # Vision générale
    _titre(doc, "Vision générale")
    gen = [["État de marché", o.get("etat_marche", "–")]]
    if "masi_var" in o:
        gen.append(["MASI (indice large)", (pct(o["masi_var"]), o["masi_var"])])
    if fu:
        gen += [["Positions ouvertes (fin de semaine)", (f"{nombre(fu['oi_total'], 0)} ({nombre(fu['delta_oi_total'], 0, True)} sur la semaine)",
                                                          fu["delta_oi_total"])],
                ["Volume des futures sur la semaine", mad(fu["volume_semaine"])],
                ["Séances sans transaction", str(fu["seances_sans_transaction"])],
                ["Depuis le lancement", f"{fu['seances_depuis_lancement']} séances · {mad(fu['volume_depuis_lancement'])}"]]
    if o.get("composants_dispo"):
        gen += [["Hausses / baisses (20 valeurs)", f"{o['hausses']} / {o['baisses']}"],
                ["Volume des 20 valeurs (marché central)", f"{mad(o['volume_masi20'])} · {pct(o['part_marche'], 0, False)} du marché"],
                ["Note de liquidité MASI 20", f"{nombre(o['liquidite_fin'], 0)} / 100" if o.get("liquidite_ok")
                 else f"en constitution ({o['liquidite_historique']} / 20 séances)"]]
    _table(doc, ["Indicateur", "Valeur"], gen, [8.5, 8.5], aligner_droite=(1,))

    # Futures
    if fu and not tab.empty:
        _titre(doc, "Marché à terme")
        _table(doc, ["Contrat", "Clôture", "Var. sem.", "OI", "Δ OI", "Volume", "Base", "Lecture prix × OI"],
               [[r["contrat"], nombre(r["cloture"]), (pct(r["var_semaine"]), r["var_semaine"]), nombre(r["open_interest"], 0),
                 (nombre(r["delta_oi"], 0, True), r["delta_oi"]), mad(r["volume"]), (pct(r["base_pct"]), r["base_pct"]),
                 r["signal"]] for _, r in tab.iterrows()],
               [1.6, 1.7, 1.7, 1.2, 1.3, 2.2, 1.6, 5.7], aligner_droite=(1, 2, 3, 4, 5, 6))
        if o.get("futures_jours") is not None and not o["futures_jours"].empty:
            _image(doc, _g_futures(o["futures_jours"]))

    # Composants
    if o.get("composants_dispo"):
        b = o["composants"]
        _titre(doc, "Indice et volume, séance par séance")
        if o.get("bulletins_manquants"):
            p = doc.add_paragraph()
            _run(p, "Bulletins de la cote manquants : " + ", ".join(o["bulletins_manquants"]) +
                 ". Contributions et volumes calculés sur les séances disponibles.", couleur=MUTED, taille=8.5, italique=True)
        _image(doc, _g_indice_volume(o))
        _titre(doc, "Qui a fait bouger l'indice")
        _image(doc, _g_contributions(b))
        _titre(doc, "Où va l'argent")
        _image(doc, _g_volume_poids(b), 15)
        _titre(doc, "Détail des 20 valeurs")
        _table(doc, ["Valeur", "Poids", "Var. sem.", "Contrib. (pb)", "Volume", "Vol./poids", "Liquidité", "Signal"],
               [[r["nom"].title(), pct(r["poids"], 1, False), (pct(r["rendement"], 1), r["rendement"]),
                 (nombre(r["contribution_pb"], 1, True), r["contribution_pb"]), mad(r.get("volume")),
                 nombre(r.get("volume_sur_poids"), 1) + "×", str(r.get("niveau", "–")), r.get("qualite", "")]
                for _, r in b.iterrows()],
               [3.6, 1.4, 1.6, 1.8, 2.0, 1.6, 2.0, 3.0], aligner_droite=(1, 2, 3, 4, 5))
        _titre(doc, "Par secteur")
        s = o["secteurs"]
        _table(doc, ["Secteur", "Poids", "Contribution (pb)", "Part du volume"],
               [[r["secteur"], pct(r["poids"], 1, False), (nombre(r["contribution_pb"], 1, True), r["contribution_pb"]),
                 pct(r.get("part_volume"), 1, False)] for _, r in s.iterrows()],
               [6.5, 3.0, 4.0, 3.5], aligner_droite=(1, 2, 3))
        _titre(doc, "À surveiller la semaine prochaine")
        for x in o.get("a_surveiller") or ["Rien de particulier."]:
            doc.add_paragraph(x, style="List Bullet")

    # Technique
    _titre(doc, "Analyse technique du MASI 20")
    _table(doc, ["Famille", "Lecture", "Verdict"], [[s["Famille"], s["Lecture"], s["Verdict"]] for s in o.get("signaux", [])],
           [2.6, 11.4, 3.0])
    if o.get("fib"):
        fb = o["fib"]
        p = doc.add_paragraph()
        _run(p, f"Fibonacci sur 120 séances : plus haut {nombre(fb['haut'])} · plus bas {nombre(fb['bas'])} · "
                f"tendance {fb['tendance']}.", couleur=MUTED, taille=8.5)
    _image(doc, _g_technique(o["technique"]))

    # Signature
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(12)
    _run(p, f"Généré par MASI20TRACKER{(' · ' + auteur) if auteur else ''} · {date_longue(pd.Timestamp.today())}. "
            "Poids approchés (nombre de titres × cours × facteur de flottant). Outil indépendant, non affilié à la "
            "Bourse de Casablanca. Ce document ne constitue pas un conseil en investissement.", couleur=MUTED, taille=7.5)

    out = io.BytesIO()
    doc.save(out)
    return out.getvalue()
