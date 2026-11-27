"""Bilan hebdomadaire MASI / MASI 20 : données de la semaine et export Word.

Plan (validé le 27/11/2026) :
  page 1  L'essentiel, face à face MASI | MASI 20 | Hors MASI 20, MASI et MASI 20 en base 100
  1       Le marché (MASI) : secteurs, actions de la semaine, volumes, grosses transactions
  2       Le MASI 20 : qui a fait bouger l'indice, volumes des 20 valeurs, technique
  3       Le marché à terme
  4       Avis DRF (et points à surveiller)
  annexes A. les 20 valeurs  B. les grosses transactions  C. définitions
"""
from __future__ import annotations

import io

import numpy as np
import pandas as pd

from . import composants as K
from . import config as C
from . import grosses as GT
from . import hebdo as H
from . import marche as M
from .fmt import date_courte, mad, nombre, pct


# ======================================================================= données
def _bloc(x: pd.DataFrame) -> dict:
    w = x["capi_debut"].fillna(0)
    return {"var": float((x["rendement"] * w).sum() / w.sum()) if w.sum() else np.nan,
            "hausses": int((x["rendement"] > 0).sum()), "baisses": int((x["rendement"] < 0).sum()),
            "actions": int(len(x)), "volume": float(x["volume"].sum()), "volume_gros": float(x["volume_gros"].sum())}


def donnees(db: dict, fin) -> dict:
    """Toutes les données du bilan de la semaine qui se termine le vendredi `fin`."""
    o = H.bilan(db, fin)
    if not o:
        return {}
    debut, fin = o["debut"], o["fin"]
    d = {"o": o, "debut": debut, "fin": fin, "seances": len(o["seances"])}
    act, flux, compo = db["actions"], db["flux"], db["composition"]
    mv = o.get("masi_vision") or M.vision_masi(db, debut, fin)
    d["mv"] = mv
    isins20 = set(K.composition_au(compo, fin)["isin"])

    # ---- toutes les actions de la semaine
    a = act[(act["date"] >= debut) & (act["date"] <= fin)].copy().sort_values("date")
    d["cote_dispo"] = not a.empty
    if not a.empty:
        a["r"] = a["cours_ref_suivant"] / a["cours_ref"] - 1
        premier = a.groupby("isin").first()
        g = a.groupby(["isin", "nom", "secteur_code"], as_index=False).agg(
            rendement=("r", lambda s: float((1 + s.fillna(0)).prod() - 1)), cloture=("cours_ref_suivant", "last"))
        g["capi_debut"] = g["isin"].map(premier["nb_titres"] * premier["cours_ref"])
        g["secteur"] = g["secteur_code"].map(C.SECTEURS).fillna(g["secteur_code"])
        cen = flux[(flux["date"] >= debut) & (flux["date"] <= fin) & (flux["marche"] == "central")]
        v = cen.groupby("isin").agg(volume=("volume", "sum"), volume_gros=("volume_gros", "sum"), nb=("nb", "sum"))
        g = g.merge(v, on="isin", how="left").fillna({"volume": 0, "volume_gros": 0, "nb": 0})
        g["m20"] = g["isin"].isin(isins20)
        d["actions"] = g
        d["hors"], d["vingt"] = _bloc(g[~g["m20"]]), _bloc(g[g["m20"]])

        # volume par séance comparé à l'habituel (20 séances précédentes)
        jours = sorted(flux.loc[flux["marche"] == "central", "date"].unique())
        avant = [x for x in jours if x < debut][-20:]
        n = max(cen["date"].nunique(), 1)
        hist = flux[(flux["marche"] == "central") & flux["date"].isin(avant)]

        def vs(isins=None):
            f, c = (hist, cen) if isins is None else (hist[hist["isin"].isin(isins)], cen[cen["isin"].isin(isins)])
            hab = f.groupby("date")["volume"].sum().mean() if not f.empty else np.nan
            return float(c["volume"].sum() / n / hab) if hab and not np.isnan(hab) else np.nan
        d["vs"] = {"marche": vs(), "m20": vs(isins20), "hors": vs(set(g.loc[~g["m20"], "isin"]))}
        prec = hist.groupby("isin")["volume"].sum() / max(len(avant), 1)

        # MASI 20 : contributions, concentration, volumes des 20 valeurs
        b = o.get("composants")
        if b is not None and not b.empty:
            x, conc = M.concentration(b)
            b = b.copy()
            b["vs"] = (b["volume"] / n) / b["isin"].map(prec)
            b["part_gt"] = b["volume_gros"] / b["volume"].where(b["volume"] > 0)
            b["portee"] = b["isin"].map(x.set_index("isin")["portee"])
            d["b"], d["conc"] = b, conc
        gt = db.get("grosses")
        d["gt"] = (gt[(gt["date"] >= debut) & (gt["date"] <= fin)].sort_values("volume", ascending=False)
                   if gt is not None and not gt.empty else pd.DataFrame())

    # ---- MASI 20 depuis le 31/12
    m20 = db["masi20"].sort_values("date")
    an = m20[m20["date"].dt.year < pd.Timestamp(fin).year]
    d["ytd20"] = o["masi20"] / an["cloture"].iloc[-1] - 1 if not an.empty else np.nan
    if pd.isna(d["ytd20"]):
        i20 = db["indices"][(db["indices"]["indice"] == "MASI 20") & (db["indices"]["date"] <= fin)]
        d["ytd20"] = float(i20.sort_values("date")["var_ytd"].iloc[-1]) / 100 if not i20.empty else np.nan

    # ---- base 100 : MASI 20 (table masi20) et MASI (table indices), séances communes
    d["base100"] = base100(db, fin)
    d["essentiel"] = essentiel(d)
    return d


def base100(db: dict, fin=None, depuis=None) -> pd.DataFrame:
    """MASI et MASI 20 en base 100, sur les séances où les deux sont connus (historique complet si importé)."""
    m20 = db["masi20"][["date", "cloture"]].rename(columns={"cloture": "MASI 20"})
    ind = db["indices"]
    masi = ind[ind["indice"] == "MASI"][["date", "valeur"]].rename(columns={"valeur": "MASI"}) if not ind.empty else pd.DataFrame(columns=["date", "MASI"])
    p = m20.merge(masi, on="date").sort_values("date").dropna()
    if fin is not None:
        p = p[p["date"] <= pd.Timestamp(fin)]
    if depuis is not None:
        p = p[p["date"] >= pd.Timestamp(depuis)]
    else:
        # on part de la dernière séance d'un bloc continu (pas de trou de plus de 10 jours)
        if len(p) > 1:
            trou = p["date"].diff().dt.days > 10
            if trou.any():
                p = p.loc[trou[trou].index[-1]:]
        p = p.tail(130)
    if p.empty:
        return p
    for c in ("MASI", "MASI 20"):
        p[c] = p[c] / p[c].iloc[0] * 100
    return p.reset_index(drop=True)


def essentiel(d: dict) -> list[str]:
    o, mv = d["o"], d["mv"]
    s = []
    if mv.get("var") is not None and not pd.isna(mv.get("var")):
        s.append(f"Le MASI {'recule' if mv['var'] < 0 else 'progresse'} de {pct(abs(mv['var']), signe=False)} sur la semaine, "
                 f"à {nombre(mv['valeur'])} pts ({pct(mv['var_ytd'])} depuis le 31/12) ; le MASI 20 "
                 f"{'recule' if o['masi20_var'] < 0 else 'progresse'} de {pct(abs(o['masi20_var']), signe=False)}.")
        ecart = o["masi20_var"] - mv["var"]
        d["ecart"] = ecart
        t = f"Les grandes valeurs font {'mieux' if ecart > 0 else 'moins bien'} que le marché ({pct(ecart)} d'écart)"
        if "hors" in d and not pd.isna(d["hors"]["var"]):
            t += f" ; hors MASI 20, les {d['hors']['actions']} autres actions font {pct(d['hors']['var'])}"
        s.append(t + ".")
    else:
        s.append(f"Le MASI 20 {'recule' if o['masi20_var'] < 0 else 'progresse'} de {pct(abs(o['masi20_var']), signe=False)} "
                 f"sur la semaine, à {nombre(o['masi20'])} pts.")
    if mv.get("actions"):
        t = f"Sur les {mv['actions']} actions, {mv['hausses']} montent et {mv['baisses']} baissent"
        sect = mv.get("secteurs")
        if sect is not None and len(sect) >= 2:
            t += (f". Côté secteurs, {sect.iloc[0]['secteur'].lower()} mène ({pct(sect.iloc[0]['var'])}) et "
                  f"{sect.iloc[-1]['secteur'].lower()} ferme la marche ({pct(sect.iloc[-1]['var'])})")
        s.append(t + ".")
    if mv.get("volume"):
        t = f"Le marché échange {mad(mv['volume'])}"
        if "vs" in d and not pd.isna(d["vs"]["marche"]):
            t += f", soit {nombre(d['vs']['marche'], 1)} fois son volume habituel par séance"
        t += f", dont {pct(mv['part_gros'], 0, False)} en grosses transactions"
        if "conc" in d and not pd.isna(d["conc"].get("part_mouvement_gt", np.nan)):
            t += (f" ; {pct(d['conc']['part_mouvement_gt'], 0, False)} du mouvement du MASI 20 vient de valeurs "
                  "dominées par des grosses transactions")
        s.append(t + ".")
    return s


def face_a_face(d: dict) -> list[list]:
    """Lignes du tableau MASI | MASI 20 | Hors MASI 20 : (texte, valeur signée ou None)."""
    o, mv = d["o"], d["mv"]
    vg, hs, vs = d.get("vingt", {}), d.get("hors", {}), d.get("vs", {})

    def p(v, dd=2, signe=True):
        return (pct(v, dd, signe), v if signe else None)

    def hb(x):
        return f"{x['hausses']} / {x['baisses']} sur {x['actions']}" if x else "–"

    def fois(v):
        return f"{nombre(v, 1)} ×" if v is not None and not pd.isna(v) else "–"

    def part(x):
        return pct(x["volume_gros"] / x["volume"], 0, False) if x and x.get("volume") else "–"
    return [
        ["Clôture de la semaine", f"{nombre(mv.get('valeur'))} pts" if mv.get("valeur") else "–", f"{nombre(o['masi20'])} pts", "–"],
        ["Variation de la semaine", p(mv.get("var")), p(o["masi20_var"]), p(hs.get("var"))],
        ["Depuis le 31/12", p(mv.get("var_ytd")), p(d.get("ytd20")), "–"],
        ["Hausses / baisses", f"{mv['hausses']} / {mv['baisses']} sur {mv['actions']}" if mv.get("actions") else "–", hb(vg), hb(hs)],
        ["Volume de la semaine", mad(mv.get("volume")), mad(vg.get("volume")), mad(hs.get("volume"))],
        ["Volume par séance vs habituel", fois(vs.get("marche")), fois(vs.get("m20")), fois(vs.get("hors"))],
        ["Part des grosses transactions", pct(mv.get("part_gros"), 0, False), part(vg), part(hs)],
    ]


# ======================================================================= graphiques (Word)
def _plt():
    from . import report_word as RW  # applique le style matplotlib commun
    import matplotlib.pyplot as plt
    return RW, plt


def fig_base100(d: dict):
    RW, plt = _plt()
    b = d["base100"]
    fig, ax = plt.subplots(figsize=(8.5, 3.0))
    xs = list(range(len(b)))
    ax.plot(xs, b["MASI 20"], color=C.NAVY, lw=2.2, marker="o", ms=2.5, label="MASI 20")
    ax.plot(xs, b["MASI"], color=C.GOLD, lw=2.0, marker="o", ms=2.5, label="MASI")
    ax.axhline(100, color="#8A94A6", lw=0.8, ls=":")
    pas = max(1, len(b) // 12)
    ax.set_xticks(xs[::pas])
    ax.set_xticklabels([x.strftime("%d/%m") for x in b["date"]][::pas], fontsize=7.5)
    sem = b.index[b["date"] >= d["debut"]]
    if len(sem):
        ax.axvspan(sem[0] - 0.5, len(b) - 0.5, color=C.GOLD, alpha=0.10, lw=0)
    ax.legend(frameon=False, ncol=2, loc="best")
    ax.set_ylabel(f"Base 100 au {b['date'].iloc[0]:%d/%m/%Y}", fontsize=8)
    fig.tight_layout()
    return fig


def fig_contributions(d: dict):
    RW, plt = _plt()
    b = d["b"].sort_values("contribution_pb")
    fig, ax = plt.subplots(figsize=(8.5, 5.0))
    cols = [{"Grosses transactions": "#C8A24A", "Mixte": "#E9D7A5"}.get(p, C.UP if c >= 0 else C.DOWN)
            for p, c in zip(b["portee"], b["contribution_pb"])]
    ax.barh(b["nom"].str.title(), b["contribution_pb"], color=cols, height=0.65)
    for i, v in enumerate(b["contribution_pb"]):
        ax.text(v + (0.6 if v >= 0 else -0.6), i, nombre(v, 1, True).replace("-", "−"), va="center",
                ha="left" if v >= 0 else "right", fontsize=7)
    ax.axvline(0, color="#8A94A6", lw=0.8)
    m = max(b["contribution_pb"].abs().max(), 1) * 1.3
    ax.set_xlim(-m, m)
    ax.grid(axis="y", visible=False)
    ax.set_xlabel("Contribution à la variation du MASI 20 (pb) · or = valeur portée par des grosses transactions", fontsize=8)
    ax.tick_params(axis="y", labelsize=7.5)
    fig.tight_layout()
    return fig


# ======================================================================= Word
def docx(d: dict, avis: str, points: str = "", auteur: str = "") -> bytes:
    from docx import Document
    from docx.enum.section import WD_SECTION
    from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK
    from docx.shared import Cm, Pt, RGBColor
    from . import brand
    from . import futures as F
    RW, plt = _plt()
    o, mv = d["o"], d["mv"]
    DARK, GOLDT, GREY = RW._rgb(C.NAVY), RW._rgb("#8A6D1F"), RW._rgb("#5F6A63")

    doc = Document()
    sec = doc.sections[0]
    sec.page_width, sec.page_height = Cm(21), Cm(29.7)
    sec.left_margin = sec.right_margin = Cm(1.8)
    sec.top_margin = sec.bottom_margin = Cm(1.6)
    st_ = doc.styles["Normal"]
    st_.font.name, st_.font.size = RW.FONT, Pt(9.5)
    semaine = f"du {date_courte(d['debut'])} au {date_courte(d['fin'])}"

    # en-tête et pied de page
    hp = sec.header.paragraphs[0]
    hp.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    RW._run(hp, f"MASI20TRACKER · Bilan hebdomadaire · semaine {semaine}", couleur=GREY, taille=7.5)
    fp = sec.footer.paragraphs[0]
    fp.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    RW._run(fp, f"{C.NOM_ENTREPRISE} – {C.SERVICE} · usage interne · source : bulletins de la Bourse de Casablanca",
            couleur=GREY, taille=7.5)

    def para(after=4):
        p = doc.add_paragraph()
        p.paragraph_format.space_after = Pt(after)
        return p

    def h1(t, num=None):
        p = para(6)
        p.paragraph_format.space_before = Pt(14)
        p.paragraph_format.keep_with_next = True
        if num:
            RW._run(p, f"{num} · ", gras=True, couleur=GOLDT, taille=15)
        RW._run(p, t, gras=True, couleur=DARK, taille=15)

    def h2(t):
        p = para(4)
        p.paragraph_format.space_before = Pt(9)
        p.paragraph_format.keep_with_next = True
        RW._run(p, t, gras=True, couleur=DARK, taille=11)

    def note(t):
        p = para(8)
        RW._run(p, t, couleur=GREY, taille=8, italique=True)

    def texte(morceaux):
        p = para(5)
        for m in morceaux:
            if isinstance(m, tuple):
                RW._run(p, m[0], gras=True, couleur=RW._couleur(m[1]) if len(m) > 1 else None)
            else:
                RW._run(p, m)
        return p

    def encadre(lignes, fill="F4F1E8", titre=None):
        t = doc.add_table(rows=1, cols=1)
        c = t.rows[0].cells[0]
        RW._shade(c, fill)
        c.width = Cm(17.4)
        c.paragraphs[0].text = ""
        first = True
        if titre:
            RW._run(c.paragraphs[0], titre, gras=True, couleur=DARK, taille=10)
            first = False
        for ln in lignes:
            p = c.paragraphs[0] if first else c.add_paragraph()
            first = False
            p.paragraph_format.space_after = Pt(4)
            RW._run(p, ln, taille=9.5)
        para(4)

    def image(fig, cm=16.5):
        RW._image(doc, fig, cm)
        plt.close("all")

    def saut():
        doc.add_paragraph().add_run().add_break(WD_BREAK.PAGE)

    # ---------------- page 1
    logo = brand.logo_png_bytes()
    if logo:
        doc.add_picture(io.BytesIO(logo), height=Cm(1.3))
    p = para(0)
    RW._run(p, "BILAN HEBDOMADAIRE · MARCHÉ ACTIONS ET MARCHÉ À TERME", gras=True, couleur=GOLDT, taille=8.5)
    p = para(2)
    RW._run(p, f"Semaine {semaine}", gras=True, couleur=DARK, taille=20)
    p = para(10)
    RW._run(p, f"{d['seances']} séance(s) · MASI et MASI 20 · {C.NOM_ENTREPRISE} – {C.SERVICE}"
               + (f" · {auteur}" if auteur else ""), couleur=GREY, taille=9)
    RW._bordure_bas(p, C.GOLD, 12)

    h1("L’essentiel")
    encadre([f"•  {s}" for s in d["essentiel"]])
    h2("MASI, MASI 20 et reste du marché")
    RW._table(doc, ["", "MASI (tout le marché)", "MASI 20", "Hors MASI 20"], face_a_face(d), [5.0, 4.1, 4.1, 4.1],
              aligner_droite=(1, 2, 3))
    note("Hors MASI 20 : les autres actions de la cote, variation pondérée par la capitalisation. Volumes : marché central, blocs exclus.")
    if len(d["base100"]) > 1:
        h2("MASI et MASI 20 en base 100")
        image(fig_base100(d), 16.5)
        if "ecart" in d:
            texte([("Lecture : ",), f"écart MASI 20 − MASI sur la semaine = {pct(d['ecart'])}. "
                   + ("Les grandes valeurs ont mieux résisté que le reste du marché."
                      if d["ecart"] > 0 else "Les grandes valeurs ont fait moins bien que le reste du marché.")])

    # ---------------- partie 1
    saut()
    h1("Le marché (MASI)", "1")
    sect = mv.get("secteurs")
    if sect is not None and not sect.empty:
        h2("1.1 · Les secteurs")
        image(RW._g_secteurs(sect), 14.5)
        note("Indices sectoriels publiés par la Bourse de Casablanca, variation de la semaine.")
    if "actions" in d:
        g = d["actions"].sort_values("rendement", ascending=False)
        h2("1.2 · Les actions de la semaine")
        top, flop = g.head(5), g.tail(5).iloc[::-1]
        RW._table(doc, ["Meilleures", "Var.", "Moins bonnes", "Var."],
                  [[a.nom.title(), (pct(a.rendement), a.rendement), z.nom.title(), (pct(z.rendement), z.rendement)]
                   for a, z in zip(top.itertuples(), flop.itertuples())], [5.6, 3.1, 5.6, 3.1], aligner_droite=(1, 3))
        h2("1.3 · Les volumes")
        texte(["Le marché a échangé ", (mad(mv.get("volume")),)]
              + ([" sur la semaine, soit ", (f"{nombre(d['vs']['marche'], 1)} ×",), " son volume habituel par séance"]
                 if not pd.isna(d["vs"]["marche"]) else [" sur la semaine"])
              + [". Les 20 valeurs du MASI 20 en représentent ", (pct(mv.get("part_masi20"), 0, False),), "."])
        gv = g.sort_values("volume", ascending=False)
        tv = gv["volume"].sum()
        RW._table(doc, ["Actions les plus échangées", "Volume", "Part du marché", "Part GT", "Indice"],
                  [[r.nom.title(), mad(r.volume), pct(r.volume / tv, 1, False) if tv else "–",
                    pct(r.volume_gros / r.volume, 0, False) if r.volume else "–", "MASI 20" if r.m20 else ""]
                   for r in gv.head(5).itertuples()], [6.2, 3.1, 3.0, 2.4, 2.7], aligner_droite=(1, 2, 3))
        para(3)
        sv = g.groupby("secteur", as_index=False)["volume"].sum().sort_values("volume", ascending=False).head(6)
        RW._table(doc, ["Secteurs les plus échangés", "Volume", "Part du marché"],
                  [[r.secteur, mad(r.volume), pct(r.volume / tv, 1, False) if tv else "–"] for r in sv.itertuples()],
                  [9.0, 4.2, 4.2], aligner_droite=(1, 2))
        h2("1.4 · Les grosses transactions")
        gt = d["gt"]
        texte([f"{len(gt)} grosse(s) transaction(s) repérée(s) sur la semaine ; elles font ",
               (pct(mv.get("part_gros"), 0, False),), " du volume du marché."])
        if not gt.empty:
            RW._table(doc, ["Séance", "Valeur", "Prix", "Montant", "Contrats", "Par contrat", "Test"], _gt_lignes(gt.head(6)),
                      [1.5, 4.6, 2.0, 2.6, 1.7, 2.6, 1.6], aligner_droite=(2, 3, 4, 5))
            note("Liste complète en annexe B. Test 1 : ≥ 5 M MAD et ≥ 1 M MAD par contrat ; "
                 "test 2 : ≥ 1 M MAD et ≥ 10 × le contrat habituel de la valeur.")

    # ---------------- partie 2
    h1("Le MASI 20", "2")
    texte(["Le MASI 20 termine la semaine à ", (f"{nombre(o['masi20'])} pts",), " (", (pct(o["masi20_var"]), o["masi20_var"]), ")."])
    if "b" in d:
        b = d["b"].sort_values("contribution_pb", ascending=False)
        h2("2.1 · Qui a fait bouger l’indice")
        t3, f3 = b.head(3), b.tail(3).iloc[::-1]
        RW._table(doc, ["Tirent l’indice", "pb", "Freinent l’indice", "pb"],
                  [[a.nom.title(), (nombre(a.contribution_pb, 1, True), a.contribution_pb), z.nom.title(),
                    (nombre(z.contribution_pb, 1, True), z.contribution_pb)] for a, z in zip(t3.itertuples(), f3.itertuples())],
                  [5.6, 3.1, 5.6, 3.1], aligner_droite=(1, 3))
        image(fig_contributions(d), 15.5)
        note("Contribution = poids × variation, en points de base (1 pb = 0,01 %). "
             "Poids approchés : capitalisation totale, sans flottant ni plafonnement.")
        h2("2.2 · Les volumes des 20 valeurs")
        cc = d["conc"]
        texte(["Les grosses transactions font ", (pct(cc.get("part_gros"), 0, False),), " du volume des 20 valeurs, et ",
               (f"{pct(cc.get('part_mouvement_gt'), 0, False)} du mouvement du MASI 20",),
               f" vient de {cc.get('valeurs_gt', 0)} valeur(s) dont le volume est dominé par des grosses transactions."])
        bv = d["b"].sort_values("volume", ascending=False).head(8)
        RW._table(doc, ["Valeur", "Volume", "Part des 20", "Vol./poids", "vs habituel", "Part GT"],
                  [[r.nom.title(), mad(r.volume), pct(r.part_volume, 1, False), f"{nombre(r.volume_sur_poids, 1)} ×",
                    f"{nombre(r.vs, 1)} ×" if pd.notna(r.vs) else "–", pct(r.part_gt, 0, False) if pd.notna(r.part_gt) else "–"]
                   for r in bv.itertuples()], [5.0, 2.8, 2.4, 2.4, 2.4, 2.4], aligner_droite=(1, 2, 3, 4, 5))
        note("Vol./poids : 1 × = la valeur s’échange en proportion de son poids. "
             "vs habituel : volume par séance ÷ moyenne des séances précédentes.")
    h2("2.3 · La technique")
    RW._table(doc, ["Méthode", "Lecture", "Verdict"], [[s["Famille"], s["Lecture"], s["Verdict"]] for s in o.get("signaux", [])],
              [3.4, 10.6, 3.4])
    image(RW._g_technique(o["technique"]), 13.5)

    # ---------------- partie 3
    h1("Le marché à terme", "3")
    fu = o.get("futures") or {}
    tab = fu.get("tableau", pd.DataFrame())
    if tab is None or tab.empty:
        texte(["Aucun bulletin du marché à terme sur la semaine."])
    else:
        RW._table(doc, ["Échéance", "Clôture", "Var. sem.", "Base", "Positions", "Δ pos.", "Volume", "Lecture"],
                  [[r.contrat, f"{nombre(r.cloture)} pts", (pct(r.var_semaine), r.var_semaine), pct(r.base_pct),
                    nombre(r.open_interest, 0), nombre(r.delta_oi, 0, True) if pd.notna(r.delta_oi) else "–",
                    mad(r.volume) if r.volume else "Aucun échange",
                    r.signal if r.signal != "Indéterminé" else "Pas de signal"] for r in tab.itertuples()],
                  [1.7, 2.3, 1.7, 1.6, 1.8, 1.5, 2.4, 4.4], aligner_droite=(1, 2, 3, 4, 5))
        note("Base = (future − MASI 20) ÷ MASI 20 ; négative = déport. 1 point d’indice = 10 MAD par contrat.")
        if not fu.get("volume_semaine"):
            texte([("Lecture : ",), "aucune transaction sur la semaine, positions ouvertes inchangées : "
                   "les futures suivent le MASI 20 sans engagement nouveau des intervenants."])

    # ---------------- partie 4
    h1("Avis DRF", "4")
    lignes = [l for l in (avis or "").split("\n") if l.strip()]
    pts = [f"•  {l.strip().lstrip('-•').strip()}" for l in (points or "").split("\n") if l.strip()]
    encadre(lignes + ([""] if pts else []), fill="FBF6E9")
    if pts:
        encadre(pts, fill="FBF6E9", titre="Points à surveiller la semaine prochaine")

    # ---------------- annexes
    saut()
    h1("Annexes")
    if "b" in d:
        h2("A · Les 20 valeurs du MASI 20")
        b = d["b"].sort_values("contribution_pb", ascending=False)
        RW._table(doc, ["Valeur", "Var. sem.", "Poids", "Contrib. (pb)", "Volume", "Part GT"],
                  [[r.nom.title(), (pct(r.rendement), r.rendement), pct(r.poids, 1, False),
                    (nombre(r.contribution_pb, 1, True), r.contribution_pb), mad(r.volume),
                    pct(r.part_gt, 0, False) if pd.notna(r.part_gt) else "–"] for r in b.itertuples()],
                  [5.4, 2.3, 2.0, 2.5, 3.2, 2.0], aligner_droite=(1, 2, 3, 4, 5))
    if "gt" in d and not d["gt"].empty:
        h2("B · Les grosses transactions de la semaine")
        RW._table(doc, ["Séance", "Valeur", "Prix", "Montant", "Contrats", "Par contrat", "Test"], _gt_lignes(d["gt"]),
                  [1.5, 4.6, 2.0, 2.6, 1.7, 2.6, 1.6], aligner_droite=(2, 3, 4, 5))
    h2("C · Définitions")
    for t, x in (("Poids", "capitalisation de la valeur (nombre de titres × cours) ÷ capitalisation des 20 valeurs. Poids approché : "
                  "le poids officiel applique en plus le facteur de flottant et le plafonnement."),
                 ("Contribution", "poids × variation ; la somme des 20 contributions donne la variation du MASI 20."),
                 ("Grosse transaction", "un prix où la taille par contrat est anormalement grande (test 1 : ≥ 5 M MAD et ≥ 1 M MAD "
                  "par contrat ; test 2 : ≥ 1 M MAD et ≥ 10 × le contrat habituel, médiane des 20 dernières séances). "
                  "Part GT = grosses transactions ÷ volume."),
                 ("Mouvement porté par des grosses transactions", "part de la variation du MASI 20 (contributions sans le signe) qui "
                  "vient de valeurs dont au moins 50 % du volume est en grosses transactions."),
                 ("Technique", "moyennes mobiles 5 · 10 · 20 · 40 séances ; RSI 5 et 14 (surachat > 70, survente < 30) ; ATR 5 et 14 "
                  "(amplitude moyenne d’une séance) ; variation 5 séances (BOOM ≥ +3 %, SLUMP ≤ −3 %).")):
        p = para(3)
        RW._run(p, f"•  {t} : ", gras=True)
        RW._run(p, x)
    out = io.BytesIO()
    doc.save(out)
    return out.getvalue()


def _gt_lignes(gt: pd.DataFrame) -> list[list]:
    return [[x.strftime("%d/%m"), n.title(), nombre(c), mad(v), nombre(k, 0), mad(pc), p]
            for x, n, c, v, k, pc, p in zip(gt["date"], gt["nom"], gt["cours"], gt["volume"], gt["nb"], gt["par_contrat"], gt["porte"])]
