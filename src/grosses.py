"""Grosses transactions : repérage par niveau de prix (fiche méthode du 22/11/2026).

Le bulletin donne, pour chaque action, les échanges par niveau de prix : montant (MAD) et nombre de
contrats. Un niveau de prix du marché central est une grosse transaction s'il passe l'une des portes :
  - porte 1 (absolue)  : montant ≥ 5 M MAD et montant par contrat ≥ 1 M MAD ;
  - porte 2 (relative) : montant ≥ 1 M MAD et montant par contrat ≥ 10 × le montant habituel par
    contrat de la valeur (médiane des 20 dernières séances échangées ; il en faut au moins 5).
Montant des grosses transactions d'une valeur = somme des montants de ses niveaux « gros ».
Part des grosses transactions = montant des grosses transactions ÷ volume total.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from . import config as C


def habituel(flux: pd.DataFrame, avant: pd.Timestamp | None = None) -> pd.DataFrame:
    """Montant habituel par contrat de chaque valeur, calculé sur les séances strictement antérieures à `avant`.
    Renvoie isin, habituel (MAD), seances (nombre de séances utilisées)."""
    if flux is None or flux.empty:
        return pd.DataFrame(columns=["isin", "habituel", "seances"])
    f = flux[(flux["marche"] == "central") & (flux["nb"] > 0) & (flux["volume"] > 0)]
    if avant is not None:
        f = f[f["date"] < pd.Timestamp(avant)]
    f = f.sort_values("date").groupby("isin").tail(C.GT_HABITUEL_SEANCES)
    f = f.assign(par_contrat=f["volume"] / f["nb"])
    return f.groupby("isin").agg(habituel=("par_contrat", "median"), seances=("date", "nunique")).reset_index()


def classer(niv: pd.DataFrame, hab: pd.DataFrame) -> pd.DataFrame:
    """Ajoute aux niveaux de prix : par_contrat, habituel, multiple, porte ('1', '2', '1 et 2' ou ''), gros."""
    n = niv.copy()
    n["par_contrat"] = n["volume"] / n["nb"].clip(lower=1)
    h = hab.set_index("isin") if not hab.empty else pd.DataFrame(columns=["habituel", "seances"])
    n["habituel"] = n["isin"].map(h["habituel"]) if len(h) else np.nan
    n["seances_habituel"] = n["isin"].map(h["seances"]).fillna(0) if len(h) else 0
    n.loc[n["seances_habituel"] < C.GT_HABITUEL_MIN, "habituel"] = np.nan
    n["multiple"] = n["par_contrat"] / n["habituel"]
    central = n["marche"] == "central"
    p1 = central & (n["volume"] >= C.GT_P1_MONTANT) & (n["par_contrat"] >= C.GT_P1_PAR_CONTRAT)
    p2 = central & n["habituel"].notna() & (n["volume"] >= C.GT_P2_PLANCHER) & (n["multiple"] >= C.GT_P2_MULTIPLE)
    n["porte"] = np.select([p1 & p2, p1, p2], ["1 et 2", "1", "2"], "")
    n["gros"] = p1 | p2
    return n


def lecture(part: float) -> str:
    if part is None or pd.isna(part):
        return "–"
    bas, haut = C.GT_LECTURE
    return "normal" if part < bas else "notable" if part < haut else "séance dominée"


def table_grosses(niv_classes: pd.DataFrame) -> pd.DataFrame:
    """Les niveaux « gros », au format de la table data/grosses.csv."""
    g = niv_classes[niv_classes["gros"]]
    return g[["date", "isin", "nom", "cours", "volume", "nb", "par_contrat", "habituel", "multiple", "porte"]].reset_index(drop=True)
