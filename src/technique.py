"""Analyse technique de l'indice : moyennes, RSI, ATR, Bollinger, Fibonacci, régime.

Tout est recalculé à partir des cours bruts : ajouter une séance suffit.
Quand le plus haut / plus bas manque, l'ATR utilise l'écart de clôture à clôture.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .fmt import nombre, pct


def indicateurs(df: pd.DataFrame) -> pd.DataFrame:
    """df : date, cloture, [plus_haut, plus_bas] -> mêmes lignes + indicateurs."""
    d = df.sort_values("date").reset_index(drop=True).copy()
    c = d["cloture"].astype(float)
    d["var"] = c.pct_change()
    d["var_5j"] = c.pct_change(5)
    for n in (5, 10, 20, 40, 60):
        d[f"mm{n}"] = c.rolling(n).mean()
        d[f"ema{n}"] = c.ewm(span=n, adjust=False, min_periods=n).mean()
    # RSI 14 (lissage de Wilder)
    delta = c.diff()
    gain = delta.clip(lower=0).ewm(alpha=1 / 14, adjust=False, min_periods=14).mean()
    perte = (-delta.clip(upper=0)).ewm(alpha=1 / 14, adjust=False, min_periods=14).mean()
    d["rsi14"] = 100 - 100 / (1 + gain / perte.replace(0, np.nan))
    # ATR 14 : vrai range si plus haut/bas connus, sinon |Δ clôture|
    h = d.get("plus_haut", pd.Series(np.nan, index=d.index)).astype(float)
    b = d.get("plus_bas", pd.Series(np.nan, index=d.index)).astype(float)
    pc = c.shift()
    tr = pd.concat([h - b, (h - pc).abs(), (b - pc).abs()], axis=1).max(axis=1, skipna=True)
    tr = tr.where(h.notna() & b.notna(), (c - pc).abs())
    d["atr14"] = tr.ewm(alpha=1 / 14, adjust=False, min_periods=14).mean()
    d["atr_pct"] = d["atr14"] / c
    # Bandes de Bollinger 20, 2 écarts-types
    sd = c.rolling(20).std()
    d["bb_haut"], d["bb_bas"] = d["mm20"] + 2 * sd, d["mm20"] - 2 * sd
    d["bb_pctb"] = (c - d["bb_bas"]) / (d["bb_haut"] - d["bb_bas"])
    # Régime de marché sur 5 séances (même règle que l'Excel : ±3 %)
    d["regime"] = np.select([d["var_5j"] >= 0.03, d["var_5j"] <= -0.03], ["BOOM", "SLUMP"], "STABLE")
    d.loc[d["var_5j"].isna(), "regime"] = None
    return d


def fibonacci(d: pd.DataFrame, fenetre: int = 120) -> dict:
    """Retracements entre le plus haut et le plus bas des `fenetre` dernières séances."""
    x = d.tail(fenetre)
    hi_col = x["plus_haut"].fillna(x["cloture"]) if "plus_haut" in x else x["cloture"]
    lo_col = x["plus_bas"].fillna(x["cloture"]) if "plus_bas" in x else x["cloture"]
    hi, lo = float(hi_col.max()), float(lo_col.min())
    i_hi, i_lo = hi_col.idxmax(), lo_col.idxmin()
    tendance = "baissière" if i_hi < i_lo else "haussière"
    niveaux = {}
    for r in (0, 0.236, 0.382, 0.5, 0.618, 0.786, 1):
        # en tendance baissière, les retracements se mesurent depuis le plus bas
        niveaux[r] = lo + (hi - lo) * r if tendance == "baissière" else hi - (hi - lo) * r
    return {"haut": hi, "bas": lo, "tendance": tendance, "niveaux": niveaux,
            "date_haut": x.loc[i_hi, "date"], "date_bas": x.loc[i_lo, "date"]}


def niveaux_proches(cours: float, fib: dict) -> tuple[tuple, tuple]:
    sup = [(r, v) for r, v in fib["niveaux"].items() if v <= cours]
    res = [(r, v) for r, v in fib["niveaux"].items() if v > cours]
    support = max(sup, key=lambda t: t[1]) if sup else (None, None)
    resistance = min(res, key=lambda t: t[1]) if res else (None, None)
    return support, resistance


def hebdo(d: pd.DataFrame) -> pd.DataFrame:
    """Bougies hebdomadaires (semaine du lundi au vendredi)."""
    x = d.set_index("date")
    h = x["plus_haut"].fillna(x["cloture"]) if "plus_haut" in x else x["cloture"]
    b = x["plus_bas"].fillna(x["cloture"]) if "plus_bas" in x else x["cloture"]
    w = pd.DataFrame({"ouverture": x["cloture"].shift().resample("W-FRI").first(),
                      "plus_haut": h.resample("W-FRI").max(), "plus_bas": b.resample("W-FRI").min(),
                      "cloture": x["cloture"].resample("W-FRI").last()}).dropna(subset=["cloture"])
    w["ouverture"] = w["ouverture"].fillna(w["cloture"])
    w["plus_haut"] = w[["plus_haut", "ouverture"]].max(axis=1)
    w["plus_bas"] = w[["plus_bas", "ouverture"]].min(axis=1)
    return w.reset_index()


def signaux(d: pd.DataFrame) -> list[dict]:
    """Tableau de lecture : un verdict par famille d'indicateurs."""
    if len(d) < 2:
        return []
    z = d.iloc[-1]
    c = z["cloture"]
    out = []

    def add(famille, lecture, verdict):
        out.append({"Famille": famille, "Lecture": lecture, "Verdict": verdict})

    if pd.notna(z.get("ema20")) and pd.notna(z.get("ema40")):
        if c > z["ema20"] > z["ema40"]:
            add("Tendance", f"Cours au-dessus des EMA20 ({nombre(z['ema20'], 0)}) et EMA40 ({nombre(z['ema40'], 0)})", "Haussier")
        elif c < z["ema20"] < z["ema40"]:
            add("Tendance", f"Cours sous les EMA20 ({nombre(z['ema20'], 0)}) et EMA40 ({nombre(z['ema40'], 0)})", "Baissier")
        else:
            add("Tendance", f"Cours entre ses moyennes (EMA20 {nombre(z['ema20'], 0)}, EMA40 {nombre(z['ema40'], 0)})", "Neutre")
    if pd.notna(z.get("rsi14")):
        r = z["rsi14"]
        prev = d["rsi14"].iloc[-6] if len(d) > 6 else np.nan
        sens = "" if pd.isna(prev) else f" (contre {prev:.0f} il y a 5 séances)"
        if r >= 70:
            add("Momentum", f"RSI14 à {r:.0f}{sens} : zone de surachat", "Prudence")
        elif r <= 30:
            add("Momentum", f"RSI14 à {r:.0f}{sens} : zone de survente", "Rebond possible")
        else:
            add("Momentum", f"RSI14 à {r:.0f}{sens}", "Haussier" if r > 50 else "Baissier")
    if pd.notna(z.get("bb_pctb")):
        p = z["bb_pctb"]
        lec = ("au-dessus de la bande haute" if p > 1 else "sous la bande basse" if p < 0
               else "dans la moitié haute des bandes" if p >= 0.5 else "dans la moitié basse des bandes")
        add("Bollinger", f"%B = {nombre(p)} : cours {lec}", "Extension" if p > 1 or p < 0 else "Neutre")
    if pd.notna(z.get("atr_pct")):
        med = d["atr_pct"].tail(120).median()
        etat = "élevée" if z["atr_pct"] > 1.25 * med else "faible" if z["atr_pct"] < 0.8 * med else "normale"
        add("Volatilité", f"ATR14 = {nombre(z['atr14'], 1)} pts ({pct(z['atr_pct'], signe=False)}), volatilité {etat}", etat.capitalize())
    if z.get("regime"):
        add("Régime", f"Variation sur 5 séances : {pct(z['var_5j'])}", z["regime"])
    return out
