"""Bilan hebdomadaire : rassemble l'indice, les composants, les futures,
l'analyse technique et la liquidité d'une semaine donnée."""
from __future__ import annotations

import numpy as np
import pandas as pd

from . import composants as K
from . import futures as F
from . import liquidite as L
from . import store
from . import technique as T
from .fmt import date_courte, pct


def semaines(masi20: pd.DataFrame) -> list[pd.Timestamp]:
    """Vendredis (fins de semaine) pour lesquels on a au moins une séance."""
    if masi20.empty:
        return []
    fins = masi20["date"].dt.to_period("W-FRI").dt.end_time.dt.normalize().unique()
    return sorted(pd.to_datetime(fins), reverse=True)


def charger() -> dict:
    return {k: store.load(k) for k in ("masi20", "indices", "actions", "flux", "futures",
                                       "futures_trades", "composition")}


def bilan(db: dict, fin_semaine) -> dict:
    fin = pd.Timestamp(fin_semaine)
    debut = fin - pd.Timedelta(days=4)
    m20 = db["masi20"].sort_values("date")
    wk = m20[(m20["date"] >= debut) & (m20["date"] <= fin)]
    if wk.empty:
        return {}
    avant = m20[m20["date"] < debut]
    ref = avant.iloc[-1] if not avant.empty else wk.iloc[0]
    out = {"debut": debut, "fin": fin, "seances": wk["date"].tolist(),
           "masi20": float(wk["cloture"].iloc[-1]), "masi20_ref": float(ref["cloture"]),
           "masi20_ref_date": ref["date"]}
    out["masi20_var"] = out["masi20"] / out["masi20_ref"] - 1
    out["jours"] = wk.assign(var=m20.set_index("date")["cloture"].pct_change().reindex(wk["date"]).values)

    # MASI (indice large), même méthode
    ind = db["indices"]
    if not ind.empty:
        masi = ind[ind["indice"] == "MASI"].sort_values("date")
        mw = masi[(masi["date"] >= debut) & (masi["date"] <= fin)]
        ma = masi[masi["date"] < debut]
        if not mw.empty and not ma.empty and ma["date"].max() >= out["masi20_ref_date"]:
            out["masi_var"] = mw["valeur"].iloc[-1] / ma["valeur"].iloc[-1] - 1
        elif not mw.empty:
            # à défaut de la séance précédente, on compose les variations publiées
            out["masi_var"] = float(np.prod(1 + mw["var_veille"] / 100) - 1)

    # Composants
    p = K.panel(db["actions"], db["composition"], debut, fin)
    out["composants_dispo"] = not p.empty
    if not p.empty:
        b = K.bilan_periode(p, db["flux"])
        # tendance du volume : moyenne par séance vs semaine précédente
        pp = K.panel(db["actions"], db["composition"], debut - pd.Timedelta(days=7), debut - pd.Timedelta(days=1))
        if not pp.empty and "volume" in b:
            bp = K.bilan_periode(pp, db["flux"])
            prev = (bp.set_index("isin")["volume"] / bp.set_index("isin")["seances"])
            cur = b.set_index("isin")["volume"] / b.set_index("isin")["seances"]
            b["tendance_volume"] = b["isin"].map(cur / prev.replace(0, np.nan))
        else:
            b["tendance_volume"] = np.nan
        b["qualite"] = [L.qualite_mouvement(r, t) for r, t in zip(b["rendement"], b["tendance_volume"])]
        m = L.mesures_jour(K.panel(db["actions"], db["composition"]), db["flux"])
        sc = L.score_valeurs(m, debut, fin)
        if not sc.empty:
            b = b.merge(sc[["isin", "score", "niveau", "spread", "amihud"]], on="isin", how="left")
        out["composants"] = b
        out["secteurs"] = K.par_secteur(b)
        out["hausses"] = int((b["rendement"] > 0).sum())
        out["baisses"] = int((b["rendement"] < 0).sum())
        out["controle_pb"] = (b["contribution"].sum() - out["masi20_var"]) * 1e4
        out["controle_recon"] = float(b["contribution"].sum())
        out["seances_composants"] = int(p["date"].nunique())
        manq = sorted(set(wk["date"]) - set(p["date"]))
        out["bulletins_manquants"] = [date_courte(d) for d in manq]
        # volumes par séance (marché total vs MASI 20)
        fx = db["flux"]
        fx = fx[(fx["date"] >= debut) & (fx["date"] <= fin) & (fx["marche"] == "central")]
        isins = set(b["isin"])
        out["volumes_jour"] = fx.groupby("date").apply(
            lambda g: pd.Series({"marche": g["volume"].sum(), "masi20": g.loc[g["isin"].isin(isins), "volume"].sum()}),
            include_groups=False).reset_index()
        tot_marche = out["volumes_jour"]["marche"].sum()
        out["volume_masi20"] = float(b["volume"].sum()) if "volume" in b else np.nan
        out["part_marche"] = out["volume_masi20"] / tot_marche if tot_marche else np.nan
        out["part_gros"] = float(b["volume_gros"].sum() / b["volume"].sum()) if b["volume"].sum() else np.nan
        pos = b.loc[b["contribution_pb"] > 0]
        out["qualite_hausse"] = (pos.loc[pos["tendance_volume"] > 1, "contribution_pb"].sum() / pos["contribution_pb"].sum()
                                 if len(pos) and pos["tendance_volume"].notna().any() else np.nan)
        li = L.indice_liquidite(m)
        out["liquidite"] = li
        lw = li[li["date"] <= fin]
        out["liquidite_fin"] = float(lw["indice_lisse"].iloc[-1]) if not lw.empty else np.nan
        out["liquidite_historique"] = int(lw["historique"].iloc[-1]) if not lw.empty else 0
        out["a_surveiller"] = a_surveiller(b)

    # Futures
    f = F.avec_base(F.preparer(db["futures"], db["futures_trades"]), m20)
    if not f.empty:
        out["futures"] = F.semaine(f, debut, fin)
        out["futures_jours"] = f[(f["date"] >= debut) & (f["date"] <= fin)]

    # Analyse technique (indice)
    tech = T.indicateurs(m20[m20["date"] <= fin])
    out["technique"] = tech
    out["signaux"] = T.signaux(tech)
    out["fib"] = T.fibonacci(tech) if len(tech) > 20 else None
    out["etat_marche"] = etat_marche(out)
    out["avis"] = avis_auto(out)
    return out


def a_surveiller(b: pd.DataFrame) -> list[str]:
    out = []
    for _, r in b.iterrows():
        if pd.notna(r.get("volume_sur_poids")) and r["volume_sur_poids"] >= 2.5 and r.get("part_volume", 0) >= 0.03:
            out.append(f"{r['nom']} : {pct(r['part_volume'], 0, False)} du volume de l'indice pour "
                       f"{pct(r['poids'], 1, False)} du poids, l'argent s'y concentre.")
        if pd.notna(r.get("haut_annuel")) and r["cloture"] >= 0.98 * r["haut_annuel"]:
            out.append(f"{r['nom']} : clôture à moins de 2 % de son plus haut annuel.")
        if pd.notna(r.get("bas_annuel")) and r["cloture"] <= 1.02 * r["bas_annuel"]:
            out.append(f"{r['nom']} : clôture à moins de 2 % de son plus bas annuel.")
        if pd.notna(r.get("volume_gros")) and r.get("volume", 0) and r["volume_gros"] / r["volume"] >= 0.5:
            out.append(f"{r['nom']} : {pct(r['volume_gros'] / r['volume'], 0, False)} de son volume vient de grosses transactions.")
    return out[:8]


def etat_marche(o: dict) -> str:
    v = o.get("masi20_var", 0)
    sig = {s["Famille"]: s["Verdict"] for s in o.get("signaux", [])}
    if v >= 0.01 and sig.get("Tendance") != "Baissier":
        return "Haussier"
    if v <= -0.01 and sig.get("Tendance") != "Haussier":
        return "Baissier"
    return "Neutre"


def _fr(x: float, d: int = 2, signe: bool = False) -> str:
    """Nombre au format français : 1 264,07"""
    t = f"{x:+,.{d}f}" if signe else f"{x:,.{d}f}"
    return t.replace(",", " ").replace(".", ",")


def avis_auto(o: dict) -> str:
    """Proposition d'Avis DRF, à relire et corriger avant diffusion."""
    s = []
    v = o["masi20_var"]
    sens = "progresse" if v > 0 else "recule" if v < 0 else "est stable"
    s.append(f"Le MASI 20 {sens} de {_fr(abs(v) * 100)} % sur la semaine, à {_fr(o['masi20'])} pts.")
    fu = o.get("futures")
    if fu and not fu["tableau"].empty:
        t = fu["tableau"]
        lo, hi = t["var_semaine"].min(), t["var_semaine"].max()
        s.append(f"Les futures évoluent entre {_fr(lo * 100, signe=True)} % et {_fr(hi * 100, signe=True)} %.")
        if t["base_pct"].notna().any():
            b1, b2 = t["base_pct"].iloc[0], t["base_pct"].iloc[-1]
            forme = "en déport" if b2 < 0 else "en report"
            s.append(f"La courbe est {forme} : base de {_fr(b1 * 100, 1, True)} % sur {t['contrat'].iloc[0]} "
                     f"et de {_fr(b2 * 100, 1, True)} % sur {t['contrat'].iloc[-1]}.")
        d_oi = fu.get("delta_oi_total")
        if pd.notna(d_oi) and d_oi != 0:
            lec = F.lecture_prix_oi(v, d_oi)[1].lower()
            s.append(f"Les positions ouvertes {'augmentent' if d_oi > 0 else 'reculent'} de "
                     f"{abs(d_oi):.0f} contrats ({lec}).")
        fin = (f", avec {fu['seances_sans_transaction']} séance(s) sans transaction."
               if fu["seances_sans_transaction"] else ".")
        s.append(f"Volume de la semaine sur les futures : {_fr(fu['volume_semaine'] / 1e6, 1)} M MAD{fin}")
    mom = next((x for x in o.get("signaux", []) if x["Famille"] == "Momentum"), None)
    if mom:
        s.append(f"Côté technique : {mom['Lecture']}.")
    return " ".join(s)
