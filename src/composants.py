"""Composants du MASI 20 : composition, poids, rendements et contributions."""
from __future__ import annotations

import numpy as np
import pandas as pd

from . import config as C


def composition_au(compo: pd.DataFrame, d) -> pd.DataFrame:
    """Valeurs du MASI 20 en vigueur à la date d (rapprochement par ISIN)."""
    if compo.empty:
        return compo
    d = pd.Timestamp(d)
    fin = compo["date_fin"] if "date_fin" in compo else pd.Series(pd.NaT, index=compo.index)
    m = (compo["date_debut"] <= d) & (fin.isna() | (fin >= d))
    out = compo.loc[m].copy()
    for col, default in (("facteur_flottant", 1.0), ("plafond", 1.0)):
        if col not in out:
            out[col] = default
        out[col] = out[col].fillna(default)
    return out.reset_index(drop=True)


def _plafonner(w: pd.Series, plafond: pd.Series) -> pd.Series:
    """Plafonnement itératif : l'excédent est redistribué au prorata."""
    w = w / w.sum()
    for _ in range(20):
        exc = w > plafond + 1e-12
        if not exc.any():
            break
        surplus = (w[exc] - plafond[exc]).sum()
        w[exc] = plafond[exc]
        libres = ~exc & (w < plafond)
        w[libres] += surplus * w[libres] / w[libres].sum()
    return w


def rendements_jour(actions_jour: pd.DataFrame, compo: pd.DataFrame) -> pd.DataFrame:
    """Poids (sur le cours de référence, avant séance) et rendement du jour
    de chaque valeur du MASI 20. Le rendement utilise le cours de référence
    de la séance suivante, déjà ajusté des opérations sur titres."""
    a = actions_jour.merge(compo[["isin", "facteur_flottant", "plafond"]], on="isin", how="inner")
    a["capi"] = a["nb_titres"] * a["cours_ref"]
    a["capi_flottante"] = a["capi"] * a["facteur_flottant"]
    a["poids"] = _plafonner(a["capi_flottante"].astype(float), a["plafond"].astype(float))
    a["rendement"] = a["cours_ref_suivant"] / a["cours_ref"] - 1
    return a


def panel(actions: pd.DataFrame, compo: pd.DataFrame, debut=None, fin=None) -> pd.DataFrame:
    """Une ligne par séance et par valeur du MASI 20 : poids, rendement, contribution."""
    if actions.empty:
        return pd.DataFrame()
    a = actions
    if debut is not None:
        a = a[a["date"] >= pd.Timestamp(debut)]
    if fin is not None:
        a = a[a["date"] <= pd.Timestamp(fin)]
    out = []
    for d, g in a.groupby("date"):
        r = rendements_jour(g, composition_au(compo, d))
        r["contribution"] = r["poids"] * r["rendement"]
        out.append(r)
    if not out:
        return pd.DataFrame()
    p = pd.concat(out, ignore_index=True)
    p["secteur"] = p["secteur_code"].map(C.SECTEURS).fillna(p["secteur_code"])
    return p


def bilan_periode(p: pd.DataFrame, flux: pd.DataFrame | None = None) -> pd.DataFrame:
    """Synthèse par valeur sur une période (semaine…) : variation composée,
    contribution en points de base, poids de fin, volume hors blocs."""
    if p.empty:
        return pd.DataFrame()
    p = p.sort_values("date")
    g = p.groupby(["isin", "nom", "secteur"], as_index=False)
    out = g.agg(poids=("poids", "last"), contribution=("contribution", "sum"),
                rendement=("rendement", lambda s: float(np.prod(1 + s.fillna(0)) - 1)),
                cloture=("cours_ref_suivant", "last"), seances=("date", "nunique"),
                haut_annuel=("haut_annuel", "last"), bas_annuel=("bas_annuel", "last"))
    out["contribution_pb"] = out["contribution"] * 1e4
    if flux is not None and not flux.empty:
        f = flux[(flux["date"] >= p["date"].min()) & (flux["date"] <= p["date"].max())]
        c = f[f["marche"] == "central"].groupby("isin").agg(
            volume=("volume", "sum"), nb=("nb", "sum"), volume_gros=("volume_gros", "sum"))
        bl = f[f["marche"] == "blocs"].groupby("isin")["volume"].sum().rename("volume_blocs")
        out = out.merge(c, on="isin", how="left").merge(bl, on="isin", how="left")
        out[["volume", "nb", "volume_blocs"]] = out[["volume", "nb", "volume_blocs"]].fillna(0)
        tot = out["volume"].sum()
        out["part_volume"] = out["volume"] / tot if tot else 0
        out["volume_sur_poids"] = out["part_volume"] / out["poids"]
    return out.sort_values("contribution_pb", ascending=False).reset_index(drop=True)


def par_secteur(b: pd.DataFrame) -> pd.DataFrame:
    if b.empty:
        return b
    agg = {"poids": "sum", "contribution_pb": "sum"}
    if "part_volume" in b:
        agg["part_volume"] = "sum"
    return b.groupby("secteur", as_index=False).agg(agg).sort_values("contribution_pb", ascending=False)


def poids_implicites(p: pd.DataFrame, masi20: pd.DataFrame, n_seances: int = 60) -> pd.DataFrame | None:
    """Poids qui expliquent le mieux les variations publiées du MASI 20
    (moindres carrés non négatifs). Nécessite au moins 15 séances."""
    try:
        from scipy.optimize import nnls
    except ImportError:
        return None
    if p.empty or masi20.empty:
        return None
    x = p.pivot_table(index="date", columns="isin", values="rendement").tail(n_seances)
    y = masi20.set_index("date")["cloture"].pct_change().reindex(x.index)
    ok = y.notna() & x.notna().all(axis=1)
    x, y = x[ok], y[ok]
    if len(y) < 15:
        return None
    w, _ = nnls(x.values, y.values)
    w = w / w.sum()
    fit = x.values @ w
    err = (fit - y.values) * 1e4
    noms = p.drop_duplicates("isin").set_index("isin")["nom"]
    return pd.DataFrame({"isin": x.columns, "nom": noms.reindex(x.columns).values, "poids_implicite": w}), \
        float(np.sqrt(np.mean(err ** 2))), len(y)
