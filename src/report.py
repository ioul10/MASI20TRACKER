"""Export du bilan hebdomadaire en page HTML autonome, prête à imprimer en PDF
(Ctrl+P → Enregistrer au format PDF, format A4 paysage)."""
from __future__ import annotations

import html

import pandas as pd

from . import charts as G
from . import brand
from . import config as C
from .fmt import date_courte, date_longue, mad, nombre, pct


def _cls(v):
    return "" if v is None or pd.isna(v) or v == 0 else ("up" if v > 0 else "down")


def _fig(fig, h=None):
    if h:
        fig.update_layout(height=h)
    fig.update_layout(hovermode="closest")
    return "<div class='fig'>" + fig.to_html(include_plotlyjs=False, full_html=False,
                                            config={"displayModeBar": False, "responsive": True}) + "</div>"


def _table(rows: list[list], head: list[str], classes: list[str] | None = None) -> str:
    h = "".join(f"<th>{x}</th>" for x in head)
    body = ""
    for r in rows:
        tds = ""
        for i, x in enumerate(r):
            c = classes[i] if classes and i < len(classes) else ""
            if isinstance(x, tuple):  # (texte, valeur pour la couleur)
                tds += f"<td class='{c} {_cls(x[1])}'>{x[0]}</td>"
            else:
                tds += f"<td class='{c}'>{x}</td>"
        body += f"<tr>{tds}</tr>"
    return f"<table><thead><tr>{h}</tr></thead><tbody>{body}</tbody></table>"


CSS = f"""
@page {{ size: A4 landscape; margin: 10mm; }}
* {{ box-sizing: border-box; }}
body {{ font-family: Inter, 'Segoe UI', Arial, sans-serif; color: {C.INK}; margin: 0; background: #fff; font-size: 12px; }}
.wrap {{ max-width: 1180px; margin: 0 auto; padding: 18px; }}
.banner {{ background: linear-gradient(100deg, {C.NAVY}, {C.NAVY_2}); color: #fff; border-bottom: 4px solid {C.GOLD};
  border-radius: 10px; padding: 14px 20px; display: flex; justify-content: space-between; align-items: center; }}
.banner {{ gap: 18px; }}
.banner .logo {{ background: #fff; border-radius: 8px; padding: 6px 10px; }} .banner .logo img {{ height: 38px; display: block; }}
.banner h1 {{ margin: 0; font-size: 20px; letter-spacing: .4px; }} .banner h1 span {{ color: {C.GOLD}; }}
.banner p {{ margin: 3px 0 0; color: #C9D3E6; }}
.big {{ text-align: right; }} .big b {{ font-size: 24px; display: block; }}
h2 {{ background: {C.NAVY}; color: #fff; font-size: 13px; padding: 6px 12px; border-left: 4px solid {C.GOLD};
  border-radius: 5px; margin: 18px 0 8px; }}
.kpis {{ display: grid; grid-template-columns: repeat(5, 1fr); gap: 8px; margin-top: 10px; }}
.kpi {{ border: 1px solid {C.GRID}; border-top: 3px solid {C.NAVY}; border-radius: 8px; padding: 8px 10px; }}
.kpi .l {{ font-size: 9.5px; text-transform: uppercase; color: {C.MUTED}; font-weight: 600; letter-spacing: .5px; }}
.kpi .v {{ font-size: 18px; font-weight: 700; margin-top: 2px; }} .kpi .s {{ font-size: 10.5px; color: {C.MUTED}; }}
table {{ width: 100%; border-collapse: collapse; font-size: 11px; }}
th {{ background: #EEF2F9; color: {C.NAVY}; text-align: left; padding: 5px 7px; font-weight: 600; border-bottom: 2px solid {C.NAVY}; }}
td {{ padding: 4px 7px; border-bottom: 1px solid {C.GRID}; }} td.n {{ text-align: right; font-variant-numeric: tabular-nums; }}
.up {{ color: {C.UP}; font-weight: 600; }} .down {{ color: {C.DOWN}; font-weight: 600; }}
.grid2 {{ display: grid; grid-template-columns: 1fr 1fr; gap: 14px; align-items: start; }}
.avis {{ background: #EEF2F9; border-left: 4px solid {C.NAVY}; border-radius: 6px; padding: 10px 14px; font-size: 12.5px; line-height: 1.5; }}
ul {{ margin: 4px 0; padding-left: 18px; }} li {{ margin: 2px 0; }}
.note {{ color: {C.MUTED}; font-size: 10px; }}
.foot {{ color: {C.MUTED}; font-size: 9.5px; border-top: 1px solid {C.GRID}; margin-top: 18px; padding-top: 6px; }}
.pb {{ page-break-before: always; }}
.fig, .grid2, .kpis, table, h2 {{ break-inside: avoid; page-break-inside: avoid; }}
h2 {{ break-after: avoid; page-break-after: avoid; }}
@media print {{ .wrap {{ max-width: none; padding: 0; }} }}
"""


def _plotly_js() -> str:
    """plotly.js intégré dans le fichier : le bilan s'ouvre sans connexion internet."""
    from plotly.offline import get_plotlyjs
    return get_plotlyjs()


def html_bilan(o: dict, avis: str, auteur: str = "") -> str:
    deb, fin = o["debut"], o["seances"][-1]
    fu = o.get("futures") or {}
    tab = fu.get("tableau", pd.DataFrame())
    k = [("MASI 20", f"{nombre(o['masi20'])} pts", f"{pct(o['masi20_var'])} sur la semaine", o["masi20_var"])]
    for _, r in tab.iterrows():
        k.append((r["contrat"], f"{nombre(r['cloture'])} pts", f"{pct(r['var_semaine'])} · base {pct(r['base_pct'], 1)}", r["var_semaine"]))
    kp = "".join(f"<div class='kpi'><div class='l'>{a}</div><div class='v'>{b}</div><div class='s {_cls(v)}'>{c}</div></div>"
                 for a, b, c, v in k[:5])
    logo = brand.logo_data_uri()
    logo_html = f"<div class='logo'><img src='{logo}' alt='{C.NOM_ENTREPRISE}'></div>" if logo else ""
    p = [f"""<div class='banner'>{logo_html}<div style='flex:1'><h1>MASI<span>20</span>TRACKER · Bilan hebdomadaire</h1>
<p>Semaine du {date_courte(deb)} au {date_courte(fin)} · {len(o['seances'])} séances · Indice, composants et marché à terme</p></div>
<div class='big'><b>{nombre(o['masi20'])} pts</b><span class='{_cls(o['masi20_var'])}'>{pct(o['masi20_var'])}</span>
<span class='note'> depuis le {date_courte(o['masi20_ref_date'])}</span></div></div>
<div class='kpis'>{kp}</div>"""]

    # Vision générale
    p.append("<h2>Vision générale</h2>")
    gen = [["État de marché", o.get("etat_marche", "–")],
           ["MASI (indice large)", (pct(o.get("masi_var")), o.get("masi_var"))]]
    if fu:
        gen += [["Positions ouvertes (fin de semaine)", f"{nombre(fu['oi_total'], 0)} ({nombre(fu['delta_oi_total'], 0, True)} sur la semaine)"],
                ["Volume futures de la semaine", mad(fu["volume_semaine"])],
                ["Séances sans transaction", str(fu["seances_sans_transaction"])],
                ["Depuis le lancement", f"{fu['seances_depuis_lancement']} séances · {mad(fu['volume_depuis_lancement'])}"]]
    if o.get("composants_dispo"):
        gen += [["Hausses / baisses (20 valeurs)", f"{o['hausses']} / {o['baisses']}"],
                ["Volume des 20 valeurs (central)", f"{mad(o['volume_masi20'])} · {pct(o['part_marche'], 0, False)} du marché"],
                ["Note de liquidité MASI 20", f"{nombre(o['liquidite_fin'], 0)} / 100" if o.get("liquidite_ok")
                 else f"en constitution ({o['liquidite_historique']} / 20 séances)"]]
    p.append(_table(gen, ["Indicateur", "Valeur"], ["", "n"]))

    # Futures
    if fu:
        p.append("<h2>Marché à terme</h2><div class='grid2'><div>")
        p.append(_table([[r["contrat"], nombre(r["cloture"]), (pct(r["var_semaine"]), r["var_semaine"]),
                          nombre(r["open_interest"], 0), (nombre(r["delta_oi"], 0, True), r["delta_oi"]),
                          mad(r["volume"]), (pct(r["base_pct"]), r["base_pct"]), r["signal"]] for _, r in tab.iterrows()],
                        ["Contrat", "Clôture", "Var. sem.", "OI", "Δ OI", "Volume", "Base", "Lecture prix × OI"],
                        ["", "n", "n", "n", "n", "n", "n", ""]))
        p.append("<p class='note'>Variations depuis la clôture de la dernière séance de la semaine précédente. "
                 "Base = future − MASI 20.</p></div><div>")
        if o.get("futures_jours") is not None and not o["futures_jours"].empty:
            p.append(_fig(G.futures_semaine(o["futures_jours"]), 300))
        p.append("</div></div>")

    # Composants
    if o.get("composants_dispo"):
        b = o["composants"]
        p.append("<h2 class='pb'>Indice et volume, séance par séance</h2>")
        p.append(_fig(G.semaine_indice_volume(o), 380))
        if o.get("bulletins_manquants"):
            p.append(f"<p class='note'>Bulletins de la cote manquants : {', '.join(o['bulletins_manquants'])}. "
                     "Les contributions et volumes portent sur les séances disponibles.</p>")
        p.append("<h2>Qui a fait bouger l'indice, et où va l'argent</h2><div class='grid2'><div>")
        p.append(_fig(G.contributions(b), 26 * len(b) + 70))
        p.append("</div><div>")
        p.append(_fig(G.volume_poids(b), 420))
        p.append("</div></div>")
        p.append("<h2 class='pb'>Détail des 20 valeurs (triées par contribution)</h2>")
        p.append(_table([[r["nom"], pct(r["poids"], 1, False), (pct(r["rendement"], 1), r["rendement"]),
                          (nombre(r["contribution_pb"], 1, True), r["contribution_pb"]), mad(r.get("volume")),
                          nombre(r.get("volume_sur_poids"), 1) + "×",
                          (nombre(r.get("tendance_volume"), 2) + "×") if pd.notna(r.get("tendance_volume")) else "–",
                          r.get("niveau", "–"), r.get("qualite", "")] for _, r in b.iterrows()],
                        ["Valeur", "Poids", "Var. sem.", "Contrib. (pb)", "Volume", "Vol./poids", "Tend. vol.", "Liquidité", "Signal"],
                        ["", "n", "n", "n", "n", "n", "n", "n", ""]))
        s = o["secteurs"]
        p.append("<div class='grid2'><div><h2>Par secteur</h2>")
        p.append(_table([[r["secteur"], pct(r["poids"], 1, False), (nombre(r["contribution_pb"], 1, True), r["contribution_pb"]),
                          pct(r.get("part_volume"), 1, False)] for _, r in s.iterrows()],
                        ["Secteur", "Poids", "Contribution (pb)", "Part du volume"], ["", "n", "n", "n"]))
        p.append("</div><div><h2>À surveiller la semaine prochaine</h2><ul>")
        p.append("".join(f"<li>{html.escape(x)}</li>" for x in o.get("a_surveiller", [])) or "<li>Rien de particulier.</li>")
        p.append("</ul></div></div>")

    # Technique
    p.append("<h2>Analyse technique du MASI 20</h2><div class='grid2'><div>")
    p.append(_table([[s["Famille"], html.escape(s["Lecture"]), s["Verdict"]] for s in o.get("signaux", [])],
                    ["Famille", "Lecture", "Verdict"]))
    if o.get("fib"):
        fb = o["fib"]
        p.append(f"<p class='note'>Fibonacci sur 120 séances : plus haut {nombre(fb['haut'])} · plus bas {nombre(fb['bas'])} "
                 f"(tendance {fb['tendance']}).</p>")
    p.append("</div><div>")
    t = o["technique"].tail(90)
    p.append(_fig(G.indice(t, ema=True, bollinger=True, rsi=True), 330))
    p.append("</div></div>")

    # Avis
    p.append(f"<h2>Avis DRF</h2><div class='avis'>{html.escape(avis).replace(chr(10), '<br>')}</div>")
    p.append(f"<div class='foot'>{C.NOM_ENTREPRISE} · Généré par MASI20TRACKER{(' · ' + html.escape(auteur)) if auteur else ''} · "
             f"{date_longue(pd.Timestamp.today())}. Source : bulletins officiels de la Bourse de Casablanca. "
             "Poids approchés (nombre de titres × cours × facteur de flottant). Outil indépendant, non affilié à la "
             "Bourse de Casablanca. Ce document ne constitue pas un conseil en investissement.</div>")
    titre = f"MASI20TRACKER - Bilan hebdo {date_courte(fin)}"
    return (f"<!DOCTYPE html><html lang='fr'><head><meta charset='utf-8'><title>{titre}</title>"
            f"<script>{_plotly_js()}</script>"
            f"<style>{CSS}</style></head><body><div class='wrap'>{''.join(p)}</div></body></html>")
