"""Résumé de la dernière séance : spot (MASI 20, MASI, composants, volumes) et marché à terme."""
from __future__ import annotations

import numpy as np
import pandas as pd

from . import composants as K
from . import futures as F
from . import grosses as GT
from . import technique as T
from .fmt import date_courte, mad, nombre, pct


def _fr_signe(x, d=2):
    return pct(x, d) if pd.notna(x) else "–"


def resume(db: dict) -> dict:
    m20 = db["masi20"].sort_values("date")
    o: dict = {}
    if m20.empty:
        return o
    tech = T.indicateurs(m20)
    z = tech.iloc[-1]
    d = z["date"]
    o.update({"date": d, "tech": tech, "z": z, "masi20": z["cloture"], "var": z["var"]})
    # semaine en cours et depuis le 1er janvier
    avant_sem = m20[m20["date"] < d - pd.Timedelta(days=d.weekday())]
    o["var_semaine"] = z["cloture"] / avant_sem["cloture"].iloc[-1] - 1 if not avant_sem.empty else np.nan
    avant_an = m20[m20["date"].dt.year < d.year]
    o["var_ytd"] = z["cloture"] / avant_an["cloture"].iloc[-1] - 1 if not avant_an.empty else np.nan
    # MASI (indice large)
    ind = db["indices"]
    masi = ind[ind["indice"] == "MASI"].sort_values("date") if not ind.empty else pd.DataFrame()
    if not masi.empty:
        o["masi"] = masi.iloc[-1]
    # composants : dernier bulletin de la cote
    act, flux = db["actions"], db["flux"]
    if not act.empty:
        dc = act["date"].max()
        p = K.panel(act, db["composition"], dc, dc)
        if not p.empty:
            b = K.bilan_periode(p, flux)
            o["cote_date"] = dc
            o["composants"] = b
            o["hausses"] = int((b["rendement"] > 0).sum())
            o["baisses"] = int((b["rendement"] < 0).sum())
            cen = flux[(flux["marche"] == "central")]
            jour = cen[cen["date"] == dc]
            isins = set(b["isin"])
            o["volume20"] = float(jour[jour["isin"].isin(isins)]["volume"].sum())
            o["volume_marche"] = float(jour["volume"].sum())
            o["part_marche"] = o["volume20"] / o["volume_marche"] if o["volume_marche"] else np.nan
            g = float(jour[jour["isin"].isin(isins)]["volume_gros"].sum())
            o["part_gros"] = g / o["volume20"] if o["volume20"] else np.nan
            prec = cen[(cen["date"] < dc) & cen["isin"].isin(isins)].groupby("date")["volume"].sum().tail(5)
            o["volume20_moy5"] = float(prec.mean()) if len(prec) else np.nan
            o["volume20_vs"] = o["volume20"] / o["volume20_moy5"] if o.get("volume20_moy5") else np.nan
            gt = db.get("grosses", pd.DataFrame())
            o["grosses"] = gt[gt["date"] == dc].sort_values("volume", ascending=False) if gt is not None and not gt.empty else pd.DataFrame()
    # futures : dernière séance
    f = F.avec_base(F.preparer(db["futures"], db["futures_trades"]), m20)
    if not f.empty:
        df = f["date"].max()
        x = f[f["date"] == df].sort_values("mois_echeance").copy()
        x["lecture"] = [F.lecture_prix_oi(v, oi)[0] for v, oi in zip(x["var"], x["delta_oi"])]
        o["futures_date"] = df
        o["futures"] = x
    o["phrase"] = phrase(o)
    return o


def _tendance(z) -> str:
    vals = [z.get(f"mm{k}") for k in (5, 10, 20, 40)]
    if any(pd.isna(v) for v in vals):
        return "tendance indéterminée"
    au_dessus = sum(z["cloture"] > v for v in vals)
    return f"au-dessus de {au_dessus} moyennes mobiles sur 4"


def phrase(o: dict) -> str:
    """Le résumé de la séance en quelques phrases."""
    if not o:
        return ""
    z = o["z"]
    s = [f"Séance du {date_courte(o['date'])} : le MASI 20 termine à {nombre(o['masi20'])} pts "
         f"({_fr_signe(o['var'])}), {_fr_signe(o['var_semaine'])} depuis le début de la semaine."]
    if "masi" in o and o["masi"]["date"] == o["date"]:
        s.append(f"Le MASI fait {nombre(o['masi']['var_veille'], 2, True)} %.")
    if "composants" in o and o["cote_date"] == o["date"]:
        b = o["composants"]
        haut, bas = b.iloc[0], b.iloc[-1]
        t = (f"Sur les 20 valeurs, {o['hausses']} hausses et {o['baisses']} baisses ; "
             f"{haut['nom'].title()} tire l'indice ({nombre(haut['contribution_pb'], 1, True)} pb)")
        if bas["contribution_pb"] < 0:
            t += f", {bas['nom'].title()} le freine ({nombre(bas['contribution_pb'], 1, True)} pb)"
        s.append(t + ".")
        v = f"Les 20 valeurs échangent {mad(o['volume20'])} ({pct(o['part_marche'], 0, False)} du marché central"
        if pd.notna(o.get("volume20_vs")):
            v += f", {nombre(o['volume20_vs'], 1)} fois la moyenne des 5 séances précédentes"
        v += f"), dont {pct(o['part_gros'], 0, False)} en grosses transactions ({GT.lecture(o['part_gros'])})."
        s.append(v)
    elif "cote_date" in o:
        s.append(f"Dernier bulletin de la cote importé : {date_courte(o['cote_date'])} (composants et volumes de cette séance).")
    if "futures" in o:
        x = o["futures"]
        prin = x.sort_values("open_interest", ascending=False).iloc[0]
        s.append(f"Marché à terme ({date_courte(o['futures_date'])}) : {F.libelle(prin['ticker'])} à {nombre(prin['cloture'])} pts "
                 f"({_fr_signe(prin['var'])}), base {pct(prin['base_pct'], 1)}, {nombre(x['open_interest'].sum(), 0)} positions ouvertes "
                 f"({nombre(x['delta_oi'].sum(), 0, True)}), "
                 + (f"volume {mad(x['volume'].sum())}." if x["volume"].sum() > 0 else "aucune transaction."))
    rsi = z.get("rsi14")
    s.append(f"Technique : indice {_tendance(z)}, RSI 14 à {nombre(rsi, 0)}, régime {z.get('regime') or '–'} sur 5 séances.")
    return " ".join(s)
