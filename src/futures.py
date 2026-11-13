"""Marché à terme sur MASI 20 : échéances, base, courbe, open interest, volumes."""
from __future__ import annotations

import re

import numpy as np
import pandas as pd

from . import config as C

MOIS = {"MAR": 3, "JUI": 6, "JUN": 6, "SEP": 9, "DEC": 12}


def echeance(ticker: str) -> tuple[str, pd.Timestamp] | tuple[None, None]:
    """FMASI20DEC26 -> ('DEC', 2026-12-01)."""
    m = re.search(r"(MAR|JUI|JUN|SEP|DEC)(\d{2})$", str(ticker))
    if not m:
        return None, None
    return m.group(1), pd.Timestamp(2000 + int(m.group(2)), MOIS[m.group(1)], 1)


def libelle(ticker: str) -> str:
    return str(ticker).replace("FMASI20", "")


def couleur(ticker: str) -> str:
    """Couleur stable par échéance : rang trimestriel modulo 6 (palette validée),
    pour que SEP26 et SEP27 n'aient jamais la même couleur."""
    _, m = echeance(ticker)
    if m is None:
        return C.NEUTRE
    return C.SERIES[(m.year * 4 + (m.month - 1) // 3) % len(C.SERIES)]


def preparer(fut: pd.DataFrame, trades: pd.DataFrame) -> pd.DataFrame:
    """Ajoute l'échéance, la variation et les volumes du jour."""
    if fut.empty:
        return fut
    f = fut.copy()
    f["mois_echeance"] = f["ticker"].map(lambda t: echeance(t)[1])
    f = f.sort_values(["ticker", "date"])
    f["var"] = f.groupby("ticker")["cloture"].pct_change()
    f["delta_oi"] = f.groupby("ticker")["open_interest"].diff()
    if not trades.empty:
        v = trades.groupby(["date", "ticker"]).agg(volume=("volume", "sum"), contrats=("quantite", "sum"),
                                                   transactions=("nb", "sum")).reset_index()
        f = f.merge(v, on=["date", "ticker"], how="left")
    for col in ("volume", "contrats", "transactions"):
        if col not in f:
            f[col] = 0.0
        f[col] = f[col].fillna(0.0)
    return f.sort_values(["date", "mois_echeance"]).reset_index(drop=True)


def avec_base(f: pd.DataFrame, masi20: pd.DataFrame) -> pd.DataFrame:
    """Base = future − indice (points et %)."""
    if f.empty or masi20.empty:
        return f
    x = f.merge(masi20[["date", "cloture"]].rename(columns={"cloture": "spot"}), on="date", how="left")
    x["base"] = x["cloture"] - x["spot"]
    x["base_pct"] = x["base"] / x["spot"]
    return x


def lecture_prix_oi(var: float, d_oi: float) -> tuple[str, str]:
    """Lecture classique prix × positions ouvertes."""
    if pd.isna(var) or pd.isna(d_oi) or d_oi == 0 or var == 0:
        return "Indéterminé", "Prix ou positions ouvertes inchangés"
    if var > 0 and d_oi > 0:
        return "Hausse confirmée", "Nouvelles positions acheteuses"
    if var > 0 and d_oi < 0:
        return "Hausse fragile", "Rachats de positions vendeuses"
    if var < 0 and d_oi > 0:
        return "Baisse confirmée", "Nouvelles positions vendeuses"
    return "Baisse en fin de course", "Liquidation de positions acheteuses"


def semaine(f: pd.DataFrame, debut, fin) -> dict:
    """Synthèse d'une semaine. Les variations partent de la clôture de la
    dernière séance AVANT la semaine (et non du lundi)."""
    debut, fin = pd.Timestamp(debut), pd.Timestamp(fin)
    wk = f[(f["date"] >= debut) & (f["date"] <= fin)]
    if wk.empty:
        return {}
    dern = wk["date"].max()
    avant = f[f["date"] < debut]
    ref_date = avant["date"].max() if not avant.empty else None
    lignes = []
    for t, g in wk.groupby("ticker"):
        z = g.sort_values("date").iloc[-1]
        if z["date"] != dern:
            continue  # contrat échu pendant la semaine
        ref = avant[(avant["ticker"] == t) & (avant["date"] == ref_date)] if ref_date is not None else pd.DataFrame()
        c0 = ref["cloture"].iloc[0] if len(ref) else g.sort_values("date")["cours_ref"].iloc[0]
        oi0 = ref["open_interest"].iloc[0] if len(ref) else np.nan
        var = z["cloture"] / c0 - 1
        d_oi = z["open_interest"] - oi0
        sig, expl = lecture_prix_oi(var, d_oi)
        lignes.append({"ticker": t, "contrat": libelle(t), "mois_echeance": z["mois_echeance"],
                       "cloture": z["cloture"], "compensation": z["compensation"], "var_semaine": var,
                       "open_interest": z["open_interest"], "delta_oi": d_oi,
                       "volume": g["volume"].sum(), "contrats": g["contrats"].sum(),
                       "transactions": g["transactions"].sum(),
                       "base": z.get("base", np.nan), "base_pct": z.get("base_pct", np.nan),
                       "signal": sig, "explication": expl})
    tab = pd.DataFrame(lignes).sort_values("mois_echeance").reset_index(drop=True)
    jours = wk.groupby("date")["volume"].sum()
    hist = f[f["date"] <= fin]
    return {
        "tableau": tab,
        "derniere_seance": dern,
        "seances": int(wk["date"].nunique()),
        "seances_sans_transaction": int((jours == 0).sum()),
        "volume_semaine": float(wk["volume"].sum()),
        "oi_total": float(tab["open_interest"].sum()),
        "delta_oi_total": float(tab["delta_oi"].sum()) if tab["delta_oi"].notna().any() else np.nan,
        "seances_depuis_lancement": int(hist["date"].nunique()),
        "volume_depuis_lancement": float(hist["volume"].sum()),
    }


def contrat_continu(f: pd.DataFrame) -> pd.DataFrame:
    """Série continue sur l'échéance la plus proche (roulement à l'échéance)."""
    if f.empty:
        return f
    x = f.sort_values(["date", "mois_echeance"]).groupby("date").first().reset_index()
    return x[["date", "ticker", "cloture", "compensation", "open_interest"]]
