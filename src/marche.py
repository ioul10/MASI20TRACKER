"""Vision « tout le marché » : MASI, indices sectoriels, volumes et grosses transactions par période.

Fonctions communes au tableau de bord, à la page Composants, à la page Grosses transactions et au bilan."""
from __future__ import annotations

import numpy as np
import pandas as pd

from . import composants as K
from . import grosses as GT

# Indices publiés qui ne sont pas des indices sectoriels
_NON_SECTORIELS = {"MASI", "MASI 20", "MASI ESG", "MASI (EUR)", "MASI (USD)", "MASI MID AND SMALL CAP",
                   "MASI RENTABILITE BRUT", "MASI RENTABILITE NET", "MASI 20 RENTABILITE BRUT", "MASI 20 RENTABILITE NET"}


def _nom_court(indice: str) -> str:
    s = indice.strip().strip('"').strip()
    s = s[5:] if s.upper().startswith("MASI ") else s
    s = s.capitalize()
    for a, b in (("Btp", "BTP"), ("Societe", "Société"), ("societe", "société"), ("Electricite", "Électricité"),
                 ("Materiels", "Matériels"), ("Materiaux", "Matériaux"), ("Batiment", "Bâtiment"), ("Petrole", "Pétrole"),
                 ("Sante", "Santé"), ("Telecommunications", "Télécommunications"), ("Ingenieries", "Ingénieries"),
                 ("equipement", "équipement"), ("Hotels", "Hôtels"), ("Societes", "Sociétés"), ("Participation", "Participation"),
                 ("immobilieres", "immobilières"), ("financement", "financement"), ("activites", "activités")):
        s = s.replace(a, b)
    return s


def _var_periode(serie: pd.DataFrame, debut, fin) -> float:
    """Variation d'un indice sur [debut, fin] : clôture de fin ÷ clôture de la séance précédant debut − 1,
    ou, à défaut, composition des variations publiées de la période."""
    w = serie[(serie["date"] >= debut) & (serie["date"] <= fin)]
    if w.empty:
        return np.nan
    a = serie[serie["date"] < debut]
    if not a.empty:
        return float(w["valeur"].iloc[-1] / a["valeur"].iloc[-1] - 1)
    return float(np.prod(1 + w["var_veille"].fillna(0) / 100) - 1)


def indices_sectoriels(ind: pd.DataFrame, debut, fin) -> pd.DataFrame:
    """Une ligne par indice sectoriel : valeur à fin, variation de la période, depuis le 31/12."""
    if ind is None or ind.empty:
        return pd.DataFrame(columns=["indice", "secteur", "valeur", "var", "var_ytd"])
    debut, fin = pd.Timestamp(debut), pd.Timestamp(fin)
    i = ind.copy()
    i["cle"] = i["indice"].str.strip().str.strip('"').str.strip().str.upper()
    i = i[i["cle"].str.startswith("MASI") & ~i["cle"].isin(_NON_SECTORIELS)]
    rows = []
    for nom, s in i.sort_values("date").groupby("indice"):
        w = s[s["date"] <= fin]
        if w.empty or w["date"].max() < debut:
            continue
        rows.append({"indice": nom, "secteur": _nom_court(nom), "valeur": float(w["valeur"].iloc[-1]),
                     "var": _var_periode(s, debut, fin), "var_ytd": float(w["var_ytd"].iloc[-1]) / 100})
    return pd.DataFrame(rows).sort_values("var", ascending=False).reset_index(drop=True) if rows else \
        pd.DataFrame(columns=["indice", "secteur", "valeur", "var", "var_ytd"])


def vision_masi(db: dict, debut, fin) -> dict:
    """MASI et tout le marché sur [debut, fin] : indice, volume, hausses / baisses de toutes les actions."""
    debut, fin = pd.Timestamp(debut), pd.Timestamp(fin)
    o: dict = {}
    ind = db.get("indices")
    if ind is not None and not ind.empty:
        m = ind[ind["indice"] == "MASI"].sort_values("date")
        w = m[m["date"] <= fin]
        if not w.empty and w["date"].max() >= debut:
            z = w.iloc[-1]
            o.update({"date": z["date"], "valeur": float(z["valeur"]), "var_jour": float(z["var_veille"]) / 100,
                      "var": _var_periode(m, debut, fin), "var_ytd": float(z["var_ytd"]) / 100})
        m20 = ind[ind["indice"] == "MASI 20"].sort_values("date")
        if not m20.empty:
            o["var_masi20_publie"] = _var_periode(m20, debut, fin)
    act, flux = db.get("actions"), db.get("flux")
    if act is not None and not act.empty:
        a = act[(act["date"] >= debut) & (act["date"] <= fin)].copy()
        if not a.empty:
            a["rendement"] = a["cours_ref_suivant"] / a["cours_ref"] - 1
            r = a.sort_values("date").groupby("isin")["rendement"].apply(lambda s: float(np.prod(1 + s.fillna(0)) - 1))
            o.update({"actions": int(len(r)), "hausses": int((r > 0).sum()), "baisses": int((r < 0).sum()),
                      "inchangees": int((r == 0).sum()), "seances": int(a["date"].nunique())})
    if flux is not None and not flux.empty:
        f = flux[(flux["date"] >= debut) & (flux["date"] <= fin) & (flux["marche"] == "central")]
        if not f.empty:
            o["volume"] = float(f["volume"].sum())
            o["volume_gros"] = float(f["volume_gros"].sum())
            o["part_gros"] = o["volume_gros"] / o["volume"] if o["volume"] else np.nan
            isins = set(K.composition_au(db["composition"], fin)["isin"])
            o["volume_masi20"] = float(f[f["isin"].isin(isins)]["volume"].sum())
            o["part_masi20"] = o["volume_masi20"] / o["volume"] if o["volume"] else np.nan
            # volume moyen par séance, comparé aux 20 séances précédentes
            tous = flux[(flux["marche"] == "central")].groupby("date")["volume"].sum()
            prec = tous[tous.index < debut].tail(20)
            n = f["date"].nunique()
            o["volume_par_seance"] = o["volume"] / n if n else np.nan
            o["volume_vs"] = o["volume_par_seance"] / prec.mean() if len(prec) else np.nan
    o["secteurs"] = indices_sectoriels(ind, debut, fin)
    return o


def base100(db: dict) -> pd.DataFrame:
    """MASI et MASI 20 en base 100 à la première séance commune (indices publiés dans les bulletins)."""
    ind = db.get("indices")
    if ind is None or ind.empty:
        return pd.DataFrame()
    p = ind[ind["indice"].isin(["MASI", "MASI 20"])].pivot_table(index="date", columns="indice", values="valeur").dropna()
    if p.empty:
        return pd.DataFrame()
    return (p / p.iloc[0] * 100).reset_index()


# ------------------------------------------------ grosses transactions et mouvement du MASI 20
SEUIL_PORTE = 0.50     # une valeur est « portée par des grosses transactions » si elles font ≥ 50 % de son volume


def concentration(b: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """À partir du bilan par valeur (K.bilan_periode) : part des grosses transactions dans le volume de chaque
    valeur, et part du mouvement du MASI 20 qui vient de valeurs portées par des grosses transactions.

    Mouvement d'une valeur = |sa contribution au MASI 20| (en pb).
    Part du mouvement portée par les grosses transactions = mouvement des valeurs dont au moins 50 % du volume
    vient de grosses transactions ÷ mouvement total des 20 valeurs."""
    if b is None or b.empty or "volume" not in b:
        return pd.DataFrame(), {}
    x = b.copy()
    x["part_gt"] = np.where(x["volume"] > 0, x["volume_gros"] / x["volume"].where(x["volume"] > 0), np.nan)
    x["mouvement"] = x["contribution_pb"].abs()
    tot = x["mouvement"].sum()
    x["part_mouvement"] = x["mouvement"] / tot if tot else np.nan
    x["portee"] = np.select([x["part_gt"] >= SEUIL_PORTE, x["part_gt"] >= GT.LECTURE[0]],
                            ["Grosses transactions", "Mixte"], "Marché")
    x.loc[x["volume"] <= 0, "portee"] = "Sans échange"
    g = x[x["portee"] == "Grosses transactions"]
    res = {"mouvement_total_pb": float(tot),
           "part_mouvement_gt": float(g["mouvement"].sum() / tot) if tot else np.nan,
           "valeurs_gt": int(len(g)),
           "contribution_gt_pb": float(g["contribution_pb"].sum()),
           "contribution_totale_pb": float(x["contribution_pb"].sum()),
           "volume": float(x["volume"].sum()), "volume_gros": float(x["volume_gros"].sum())}
    res["part_gros"] = res["volume_gros"] / res["volume"] if res["volume"] else np.nan
    return x.sort_values("mouvement", ascending=False).reset_index(drop=True), res


def gt_par_seance(db: dict) -> pd.DataFrame:
    """Par séance : part des grosses transactions sur le MASI 20 et sur tout le marché, et part du mouvement
    du MASI 20 portée par des valeurs dominées par les grosses transactions."""
    act, flux = db["actions"], db["flux"]
    if act.empty or flux.empty:
        return pd.DataFrame()
    p = K.panel(act, db["composition"])
    rows = []
    cen = flux[flux["marche"] == "central"]
    for d, g in p.groupby("date"):
        b = K.bilan_periode(g, flux)
        _, r = concentration(b)
        fj = cen[cen["date"] == d]
        rows.append({"date": d, "volume_masi20": r.get("volume", np.nan), "gros_masi20": r.get("volume_gros", np.nan),
                     "part_masi20": r.get("part_gros", np.nan), "part_marche": fj["volume_gros"].sum() / fj["volume"].sum()
                     if fj["volume"].sum() else np.nan, "part_mouvement_gt": r.get("part_mouvement_gt", np.nan)})
    return pd.DataFrame(rows)


def phrase_concentration(x: pd.DataFrame, r: dict, libelle: str) -> str:
    """Le résultat en deux ou trois phrases."""
    from .fmt import mad, nombre, pct
    if x is None or x.empty or not r:
        return "Pas de données de composants sur cette période."
    s = [f"Sur la {libelle}, les grosses transactions représentent <b>{pct(r['part_gros'], 0, False)}</b> du volume des "
         f"20 valeurs du MASI 20 ({mad(r['volume_gros'])} sur {mad(r['volume'])}) : {GT.lecture(r['part_gros'])}."]
    g = x[x["portee"] == "Grosses transactions"]
    if len(g):
        noms = ", ".join(f"{n.title()} ({nombre(c, 1, True)} pb, {pct(p, 0, False)} de grosses transactions)"
                         for n, c, p in zip(g["nom"].head(3), g["contribution_pb"].head(3), g["part_gt"].head(3)))
        s.append(f"<b>{pct(r['part_mouvement_gt'], 0, False)} du mouvement du MASI 20</b> vient de valeurs dont le volume est "
                 f"dominé par des grosses transactions : {noms}. Ce mouvement repose sur une ou deux opérations, il est à "
                 "lire avec prudence.")
    else:
        s.append("Aucune valeur qui a fait bouger le MASI 20 n'est dominée par des grosses transactions : "
                 "<b>le mouvement de l'indice est porté par des échanges ordinaires</b>.")
    m = x[x["portee"] == "Mixte"]
    if len(m):
        t = m.iloc[0]
        s.append(f"À noter : {t['nom'].title()} ({nombre(t['contribution_pb'], 1, True)} pb) a {pct(t['part_gt'], 0, False)} "
                 "de son volume en grosses transactions.")
    return " ".join(s)
