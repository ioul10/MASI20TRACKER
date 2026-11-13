"""Actualités : flux RSS de la presse financière marocaine, filtrés sur le
MASI 20, ses valeurs et le marché à terme."""
from __future__ import annotations

import re
from datetime import datetime

import pandas as pd

from . import config as C


def mots_cles(composition: pd.DataFrame) -> dict[str, list[str]]:
    """Mots-clés de recherche par valeur (nom du bulletin + appellations courantes)."""
    alias = {
        "ITISSALAT AL-MAGHRIB": ["Maroc Telecom", "IAM", "Itissalat"],
        "ATTIJARIWAFA BANK": ["Attijariwafa", "AWB"],
        "BANK OF AFRICA": ["Bank of Africa", "BOA"],
        "BCP": ["Banque Populaire", "BCP"],
        "CDM": ["Crédit du Maroc", "CDM"],
        "SODEP MARSA MAROC": ["Marsa Maroc"],
        "DOUJA PROM ADDOHA": ["Addoha"],
        "TAQA MOROCCO": ["Taqa"],
        "HOLCIM MAROC": ["Holcim"],
        "CIMENTS DU MAROC": ["Ciments du Maroc"],
        "RESIDENCES DAR SAADA": ["Dar Saada"],
        "LABEL VIE": ["Label'Vie", "Label Vie", "LabelVie"],
        "JET CONTRACTORS": ["Jet Contractors"],
        "CMGP GROUP": ["CMGP"],
        "CFG BANK": ["CFG Bank"],
        "TGCC": ["TGCC"],
    }
    out = {}
    for n in composition.get("nom", []):
        out[n] = alias.get(n, [n.title()])
    return out


def lire_flux(flux: dict[str, str] | None = None, timeout: int = 10) -> tuple[pd.DataFrame, dict]:
    import feedparser
    import requests
    flux = flux or C.FLUX_NEWS
    lignes, etat = [], {}
    for source, url in flux.items():
        try:
            r = requests.get(url, timeout=timeout, headers={"User-Agent": "Mozilla/5.0 MASI20TRACKER"})
            r.raise_for_status()
            f = feedparser.parse(r.content)
            for e in f.entries:
                d = None
                for k in ("published_parsed", "updated_parsed"):
                    if e.get(k):
                        d = datetime(*e[k][:6])
                        break
                resume = re.sub("<[^>]+>", " ", e.get("summary", ""))
                lignes.append({"date": d, "source": source, "titre": e.get("title", "").strip(),
                               "lien": e.get("link", ""), "resume": re.sub(r"\s+", " ", resume).strip()[:300]})
            etat[source] = f"{len(f.entries)} articles"
        except Exception as ex:  # un flux en panne ne bloque pas les autres
            etat[source] = f"indisponible ({type(ex).__name__})"
    df = pd.DataFrame(lignes, columns=["date", "source", "titre", "lien", "resume"])
    return df.sort_values("date", ascending=False, na_position="last").reset_index(drop=True), etat


def filtrer(df: pd.DataFrame, cles: dict[str, list[str]]) -> pd.DataFrame:
    """Ajoute la colonne « valeurs » (sociétés citées) et « marche » (sujet de marché)."""
    if df.empty:
        return df.assign(valeurs=[], marche=[])
    txt = (df["titre"] + " " + df["resume"]).fillna("")
    vals = []
    for t in txt:
        cites = [n for n, mots in cles.items()
                 if any(re.search(rf"(?<![\w']){re.escape(m)}(?![\w'])", t, re.I) for m in mots)]
        vals.append(cites)
    out = df.copy()
    out["valeurs"] = vals
    out["marche"] = txt.str.contains("|".join(re.escape(m) for m in C.MOTS_CLES_MARCHE), case=False, regex=True)
    return out
