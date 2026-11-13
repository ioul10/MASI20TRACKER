"""Indice de liquidité du MASI 20 (prix × volume × composants).

Cinq mesures par valeur et par séance, toutes tirées du bulletin de la cote :
  volume     : volume du marché central en MAD (marché de blocs exclu)    ↑ = liquide
  rotation   : volume ÷ capitalisation flottante                          ↑ = liquide
  amihud     : |variation| ÷ volume (en M MAD) — impact prix               ↓ = liquide
  spread     : (offre − demande) ÷ milieu, à la clôture                   ↓ = liquide
  activite   : nombre de contrats                                         ↑ = liquide
+ concentration : part du volume réalisée sur un seul prix (pénalité).

Deux lectures :
  - score par valeur (0-100) : rang de la valeur parmi les 20, sur la période ;
  - indice de liquidité (0-100) : niveau de liquidité de l'ensemble du MASI 20
    par rapport à son propre historique.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from . import config as C

SENS = {"volume": 1, "rotation": 1, "amihud": -1, "spread": -1, "activite": 1}


def mesures_jour(p: pd.DataFrame, flux: pd.DataFrame) -> pd.DataFrame:
    """p : panel des composants (composants.panel). Une ligne par valeur et par séance."""
    if p.empty:
        return pd.DataFrame()
    m = p[["date", "isin", "nom", "secteur", "poids", "rendement", "capi_flottante", "demande", "offre"]].copy()
    if flux is not None and not flux.empty:
        c = flux[flux["marche"] == "central"][["date", "isin", "volume", "nb", "part_max_niveau", "volume_gros"]]
        m = m.merge(c, on=["date", "isin"], how="left")
    for col in ("volume", "nb", "volume_gros"):
        if col not in m:
            m[col] = np.nan
        m[col] = m[col].fillna(0.0)
    m["rotation"] = m["volume"] / m["capi_flottante"]
    m["amihud"] = (m["rendement"].abs() / (m["volume"] / 1e6)).where(m["volume"] > 0)
    mid = (m["offre"] + m["demande"]) / 2
    m["spread"] = ((m["offre"] - m["demande"]) / mid).where((m["offre"] > m["demande"]) & (m["demande"] > 0))
    m["activite"] = m["nb"]
    m["concentration"] = m["part_max_niveau"].where(m["volume"] > 0)
    return m


def score_valeurs(m: pd.DataFrame, debut=None, fin=None) -> pd.DataFrame:
    x = m
    if debut is not None:
        x = x[x["date"] >= pd.Timestamp(debut)]
    if fin is not None:
        x = x[x["date"] <= pd.Timestamp(fin)]
    if x.empty:
        return pd.DataFrame()
    g = x.groupby(["isin", "nom", "secteur"], as_index=False).agg(
        poids=("poids", "last"), volume=("volume", "mean"), rotation=("rotation", "mean"),
        amihud=("amihud", "median"), spread=("spread", "median"), activite=("activite", "mean"),
        concentration=("concentration", "mean"), seances_traitees=("volume", lambda s: int((s > 0).sum())),
        seances=("date", "nunique"), volume_gros=("volume_gros", "sum"), volume_total=("volume", "sum"))
    score = pd.Series(0.0, index=g.index)
    for k, w in C.POIDS_LIQUIDITE.items():
        r = g[k].rank(pct=True, ascending=SENS[k] > 0)
        score += w * r.fillna(0.0)  # mesure absente = pire rang
    # Pénalité si le volume est concentré sur un seul prix (transaction de bloc sur le central)
    conc = g["concentration"].fillna(0)
    penal = np.where(conc > 0.5, 1 - 0.4 * (conc - 0.5) / 0.5, 1.0)
    # Pénalité si la valeur n'a pas traité à toutes les séances
    regul = g["seances_traitees"] / g["seances"]
    g["score"] = (100 * score * penal * (0.5 + 0.5 * regul)).round(0)
    g["niveau"] = pd.cut(g["score"], [-1, 35, 65, 101], labels=["Peu liquide", "Moyenne", "Liquide"]).astype(str)
    return g.sort_values("score", ascending=False).reset_index(drop=True)


def indice_liquidite(m: pd.DataFrame, lissage: int = 5) -> pd.DataFrame:
    """Mesures agrégées du MASI 20 par séance, puis rang de chaque mesure dans
    son propre historique (jusqu'à 250 séances). 50 = liquidité habituelle."""
    if m.empty:
        return pd.DataFrame()
    def agg(g):
        w = g["poids"] / g["poids"].sum()
        return pd.Series({
            "volume": g["volume"].sum(),
            "rotation": g["volume"].sum() / g["capi_flottante"].sum(),
            "amihud": np.nansum(w * g["amihud"]) / w[g["amihud"].notna()].sum() if g["amihud"].notna().any() else np.nan,
            "spread": np.nansum(w * g["spread"]) / w[g["spread"].notna()].sum() if g["spread"].notna().any() else np.nan,
            "activite": g["activite"].sum(),
            "part_gros": g["volume_gros"].sum() / g["volume"].sum() if g["volume"].sum() else np.nan,
        })
    a = m.groupby("date").apply(agg, include_groups=False).sort_index()
    sc = pd.Series(0.0, index=a.index)
    for k, w in C.POIDS_LIQUIDITE.items():
        s = a[k] * SENS[k]
        pct = s.rolling(250, min_periods=1).apply(lambda v: (v[:-1] < v[-1]).mean() + 0.5 * (v[:-1] == v[-1]).mean()
                                                  if len(v) > 1 else 0.5, raw=True)
        sc += w * pct.fillna(0.5)
    a["indice"] = 100 * sc
    a["indice_lisse"] = a["indice"].rolling(lissage, min_periods=1).mean()
    a["historique"] = np.arange(1, len(a) + 1)
    return a.reset_index()


SEANCES_MIN_NOTE = 20  # ≈ 4 semaines de bulletins avant d'afficher la note globale


def note_disponible(m: pd.DataFrame, fin=None) -> tuple[bool, int]:
    """La note globale compare la période à l'historique : elle n'a de sens
    qu'avec au moins SEANCES_MIN_NOTE séances de bulletins."""
    d = m["date"] if fin is None else m.loc[m["date"] <= pd.Timestamp(fin), "date"]
    n = int(d.nunique())
    return n >= SEANCES_MIN_NOTE, n


def qualite_mouvement(rendement: float, tendance_volume: float) -> str:
    """Croise le sens du prix et l'évolution du volume."""
    if pd.isna(rendement) or abs(rendement) < 0.0025:
        return "Neutre"
    sens = "Hausse" if rendement > 0 else "Baisse"
    if pd.isna(tendance_volume):
        return sens
    if tendance_volume >= 1.15:
        return f"{sens} confirmée"
    if tendance_volume <= 0.85:
        return f"{sens}, volume en repli"
    return f"{sens}, volume stable"
