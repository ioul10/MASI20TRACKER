"""Import d'un bulletin : lecture, contrôles, puis enregistrement."""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from . import config as C
from . import store
from .composants import composition_au, rendements_jour
from .fmt import mad, nombre
from . import grosses as GT
from .parsers import _agreger_flux, detecter_type, lire_cote, lire_futures


@dataclass
class Rapport:
    type: str
    seance: pd.Timestamp
    resume: dict = field(default_factory=dict)
    alertes: list[str] = field(default_factory=list)   # bloquantes : à valider
    infos: list[str] = field(default_factory=list)
    tables: dict = field(default_factory=dict)          # données prêtes à enregistrer


def analyser(contenu: bytes, nom_fichier: str = "") -> Rapport:
    kind = detecter_type(contenu)
    return _analyser_cote(contenu) if kind == "cote" else _analyser_futures(contenu)


def _analyser_cote(contenu: bytes) -> Rapport:
    b = lire_cote(contenu)
    d = pd.Timestamp(b.seance)
    rep = Rapport("cote", d)
    # 1. Les 20 valeurs du MASI 20 sont-elles retrouvées par ISIN ?
    compo = composition_au(store.load("composition"), d)
    trouves = compo["isin"].isin(b.actions["isin"])
    rep.resume["Valeurs MASI 20 trouvées"] = f"{int(trouves.sum())} / {len(compo)}"
    if not trouves.all():
        manq = ", ".join(compo.loc[~trouves, "nom"])
        rep.alertes.append(f"Valeurs du MASI 20 absentes du bulletin : {manq}.")
    # 2. Indice publié
    ind = b.indices.set_index("indice") if not b.indices.empty else pd.DataFrame()
    if "MASI 20" not in ind.index:
        rep.alertes.append("Le MASI 20 est introuvable dans la page INDICES.")
        pub = None
    else:
        pub = ind.loc["MASI 20"]
        rep.resume["MASI 20"] = f"{nombre(pub['valeur'])} pts ({nombre(pub['var_veille'], signe=True)} %)"
        if abs(pub["var_veille"]) / 100 > C.SEUIL_ALERTE_VAR:
            rep.alertes.append(f"Variation inhabituelle du MASI 20 : {nombre(pub['var_veille'], signe=True)} %. Vérifiez avant de valider.")
    # 3. Contrôle des poids : variation reconstituée vs publiée
    if pub is not None and trouves.any():
        r = rendements_jour(b.actions, compo)
        recon = float((r["poids"] * r["rendement"]).sum() * 100)
        ecart_pb = (recon - pub["var_veille"]) * 100
        rep.resume["Contrôle des poids"] = (f"{nombre(recon, signe=True)} % reconstitué contre "
                                           f"{nombre(pub['var_veille'], signe=True)} % publié ({ecart_pb:+.0f} pb)")
        if abs(ecart_pb) > C.TOLERANCE_CONTROLE_PB:
            rep.infos.append(f"Écart de {ecart_pb:+.0f} pb entre la variation reconstituée et la variation publiée : "
                             "les poids approchés (sans flottant) peuvent être affinés dans la table de composition.")
    # 4. Doublon
    old = store.load("masi20")
    if not old.empty and (old["date"] == d).any():
        prev = old.loc[old["date"] == d].iloc[0]
        if pub is not None and abs(prev["cloture"] - pub["valeur"]) > 0.005:
            rep.alertes.append(f"La séance du {d:%d/%m/%Y} existe déjà avec un MASI 20 différent "
                               f"({nombre(prev['cloture'])} enregistré, {nombre(pub['valeur'])} dans le bulletin). "
                               "Le bulletin remplacera la valeur enregistrée.")
        else:
            rep.infos.append(f"La séance du {d:%d/%m/%Y} est déjà enregistrée : elle sera mise à jour.")
    blocs = b.totaux.get("blocs")
    if blocs:
        rep.infos.append(f"Marché de blocs : {mad(blocs['volume'])} (exclu des mesures de liquidité).")
    rep.resume["Actions lues"] = len(b.actions)
    rep.resume["Niveaux de prix lus"] = len(b.niveaux)
    non_rapproches = b.niveaux["isin"].isna().sum()
    if non_rapproches:
        rep.infos.append(f"{non_rapproches} lignes de transactions n'ont pas pu être rattachées à un code ISIN.")
    # 5. Grosses transactions (portes 1 et 2), avec le montant habituel tiré des séances précédentes
    niv = GT.classer(b.niveaux, GT.habituel(store.load("flux"), d))
    flux = _agreger_flux(niv)
    gros = GT.table_grosses(niv)
    cen = flux[flux["marche"] == "central"]
    if cen["volume"].sum():
        part = cen["volume_gros"].sum() / cen["volume"].sum()
        rep.resume["Grosses transactions"] = (f"{len(gros)} niveau(x) de prix · {mad(gros['volume'].sum())} · "
                                              f"{part:.0%} du marché central ({GT.lecture(part)})")
    rep.tables = {"actions": b.actions, "flux": flux, "indices": b.indices, "grosses": gros}
    if pub is not None:
        rep.tables["masi20"] = pd.DataFrame([{"date": d, "cloture": pub["valeur"], "source": "bulletin"}])
    return rep


def _analyser_futures(contenu: bytes) -> Rapport:
    b = lire_futures(contenu)
    d = pd.Timestamp(b.seance)
    rep = Rapport("futures", d)
    rep.resume["Contrats"] = ", ".join(b.cours["ticker"])
    rep.resume["Positions ouvertes"] = int(b.cours["open_interest"].sum())
    rep.resume["Transactions"] = f"{len(b.transactions)} ({mad(b.transactions['volume'].sum(), 2)})"
    if b.cours.empty:
        rep.alertes.append("Aucun contrat lu dans le bulletin.")
    old = store.load("futures")
    if not old.empty and (old["date"] == d).any():
        rep.infos.append(f"La séance du {d:%d/%m/%Y} est déjà enregistrée : elle sera mise à jour.")
    rep.tables = {"futures": b.cours, "futures_trades": b.transactions}
    return rep


def enregistrer(rep: Rapport, contenu: bytes | None = None, nom_fichier: str | None = None,
                haut: float | None = None, bas: float | None = None) -> None:
    for name, df in rep.tables.items():
        if name == "masi20":
            df = _fusion_masi20(df, haut, bas)
        if name in ("futures_trades", "grosses"):   # on remplace toute la séance (pas d'identifiant unique)
            old = store.load(name)
            if not old.empty:
                store.save(name, old[old["date"] != rep.seance])
        store.upsert(name, df, f"Import {rep.type} {rep.seance:%Y-%m-%d}")
    if contenu and nom_fichier:
        store.save_bulletin(nom_fichier, contenu)


def _fusion_masi20(new: pd.DataFrame, haut, bas) -> pd.DataFrame:
    """Le bulletin donne la clôture ; le plus haut et le plus bas viennent d'une
    saisie (Investing) ou de l'historique, et sont effacés s'ils sont incohérents."""
    old = store.load("masi20")
    row = new.iloc[0].to_dict()
    prev = old.loc[old["date"] == row["date"]] if not old.empty else pd.DataFrame()
    h = haut if haut else (prev["plus_haut"].iloc[0] if len(prev) else None)
    b = bas if bas else (prev["plus_bas"].iloc[0] if len(prev) else None)
    c = row["cloture"]
    if h is not None and b is not None and pd.notna(h) and pd.notna(b) and not (b - 0.01 <= c <= h + 0.01):
        h = b = None
    o = prev["ouverture"].iloc[0] if len(prev) and "ouverture" in prev else None
    if o is not None and pd.notna(o) and h is not None and b is not None and not (b - 0.01 <= o <= h + 0.01):
        o = None
    row.update({"plus_haut": h, "plus_bas": b, "ouverture": o})
    return pd.DataFrame([row])


# ------------------------------------------------ plus haut / plus bas du MASI 20
# Formats acceptés : saisie en grille, Excel (ex. feuille MASI20INDEX), export « Historical Data »
# d'Investing.com en anglais (Date, Price, Open, High, Low, Vol., Change %) ou en français
# (Date, Dernier, Ouv., Plus Haut, Plus Bas, Vol., Variation %).
_NOMS_DATE = ("date", "séance", "seance", "jour")
_NOMS_CLOTURE = ("clôture", "cloture", "price", "close", "dernier", "cours")
_NOMS_OUVERTURE = ("ouverture", "open", "ouv.", "ouv")
_NOMS_HAUT = ("plus haut", "plus_haut", "high", "haut", "+ haut", "+haut", "max")
_NOMS_BAS = ("plus bas", "plus_bas", "low", "bas", "+ bas", "+bas", "min")


def _nombre_fr(x):
    """'1 264,07' / '1,264.07' / '1264.07' / 1264.07 -> 1264.07"""
    if x is None or (isinstance(x, float) and pd.isna(x)):
        return None
    if isinstance(x, (int, float)):
        return float(x)
    t = str(x).replace("\u00a0", "").replace("\u202f", "").replace(" ", "").replace("%", "")
    if not t or t in ("-", "–"):
        return None
    if "," in t and "." in t:
        t = t.replace(".", "").replace(",", ".") if t.rfind(",") > t.rfind(".") else t.replace(",", "")
    else:
        t = t.replace(",", ".")
    try:
        return float(t)
    except ValueError:
        return None


def _dates(col: pd.Series, mois_d_abord: bool) -> pd.Series:
    """Dates jj/mm/aaaa (français) ou mm/jj/aaaa (anglais, Investing). Tranche d'après les données
    quand c'est possible (un premier nombre > 12 => jour d'abord ; un second > 12 => mois d'abord)."""
    if pd.api.types.is_datetime64_any_dtype(col):
        return col
    txt = col.astype(str).str.strip()
    parts = txt.str.extract(r"^(\d{1,2})[/.-](\d{1,2})[/.-](\d{2,4})")
    if parts.notna().all(axis=1).any():
        p1, p2 = pd.to_numeric(parts[0], errors="coerce"), pd.to_numeric(parts[1], errors="coerce")
        if (p1 > 12).any():
            mois_d_abord = False
        elif (p2 > 12).any():
            mois_d_abord = True
        return pd.to_datetime(txt, format="%m/%d/%Y" if mois_d_abord else "%d/%m/%Y", errors="coerce")
    return pd.to_datetime(txt, errors="coerce")


def lire_hauts_bas(fichier, nom: str) -> pd.DataFrame:
    """Lit un CSV ou un Excel : date, plus haut, plus bas (obligatoires), clôture et ouverture (facultatives).
    Renvoie date, cloture_fichier, ouverture, plus_haut, plus_bas."""
    def normaliser(df: pd.DataFrame) -> pd.DataFrame | None:
        cols = {str(c).strip().lower(): c for c in df.columns}

        def trouver(noms):
            for n in noms:
                if n in cols:
                    return cols[n]
            return next((cols[c] for c in cols if any(c.startswith(n) for n in noms)), None)
        d, h, b = trouver(_NOMS_DATE), trouver(_NOMS_HAUT), trouver(_NOMS_BAS)
        if d is None or h is None or b is None:
            return None
        c, o = trouver(_NOMS_CLOTURE), trouver(_NOMS_OUVERTURE)
        anglais = any(k in cols for k in ("price", "open", "high", "change %"))
        vide = pd.Series(None, index=df.index, dtype=float)
        out = pd.DataFrame({"date": _dates(df[d], mois_d_abord=anglais),
                            "cloture_fichier": df[c].map(_nombre_fr) if c is not None else vide,
                            "ouverture": df[o].map(_nombre_fr) if o is not None else vide,
                            "plus_haut": df[h].map(_nombre_fr), "plus_bas": df[b].map(_nombre_fr)})
        out = out.dropna(subset=["date"]).astype({"cloture_fichier": float, "ouverture": float,
                                                  "plus_haut": float, "plus_bas": float})
        return out.drop_duplicates("date", keep="first").sort_values("date").reset_index(drop=True)

    if nom.lower().endswith((".xlsx", ".xlsm", ".xls")):
        feuilles = pd.read_excel(fichier, sheet_name=None)
        for _, df in feuilles.items():
            for entete in range(0, 6):     # en-tête éventuellement décalé de quelques lignes
                x = df if entete == 0 else df.iloc[entete - 1:].set_axis(df.iloc[entete - 1].values, axis=1).iloc[1:]
                r = normaliser(x)
                if r is not None and len(r):
                    return r
        raise ValueError("Aucune feuille avec les colonnes Date, Plus haut et Plus bas.")
    df = pd.read_csv(fichier, sep=None, engine="python", encoding="utf-8-sig")
    r = normaliser(df)
    if r is None:
        raise ValueError("Colonnes attendues : Date, Plus haut (High), Plus bas (Low).")
    return r


def controler_hauts_bas(saisie: pd.DataFrame, masi20: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Rapproche la saisie de la base. Renvoie (lignes valides, lignes rejetées avec motif).
    - Séance déjà en base : la clôture du bulletin est gardée ; il faut plus bas ≤ clôture ≤ plus haut.
    - Séance absente de la base : ajoutée si le fichier donne la clôture (source « fichier ») ;
      le bulletin, importé plus tard, remplacera la clôture et gardera haut / bas / ouverture.
    - Ouverture (facultative) : elle doit aussi être entre le plus bas et le plus haut."""
    s = saisie.copy()
    for k in ("cloture_fichier", "ouverture"):
        if k not in s:
            s[k] = np.nan
    s = s.dropna(subset=["plus_haut", "plus_bas"], how="all")
    s["date"] = pd.to_datetime(s["date"]).dt.normalize()
    m = masi20.copy()
    if "ouverture" not in m:
        m["ouverture"] = np.nan
    m = m[["date", "cloture", "source", "ouverture"]].rename(columns={"ouverture": "ouverture_base"})
    m["date"] = pd.to_datetime(m["date"]).dt.normalize()
    x = s.merge(m, on="date", how="left")
    x["nouvelle"] = x["cloture"].isna() & x["cloture_fichier"].notna()
    x["cloture"] = x["cloture"].fillna(x["cloture_fichier"])
    x["source"] = x["source"].where(~x["nouvelle"], "fichier")
    x["ouverture"] = x["ouverture"].fillna(x["ouverture_base"])
    x["ecart_cloture"] = (x["cloture_fichier"] - x["cloture"]).where(~x["nouvelle"])
    tol = 0.01
    motif = np.select(
        [x["cloture"].isna(), x["plus_haut"].isna() | x["plus_bas"].isna(), x["plus_haut"] < x["plus_bas"],
         x["cloture"] > x["plus_haut"] + tol, x["cloture"] < x["plus_bas"] - tol,
         x["ouverture"].notna() & ((x["ouverture"] > x["plus_haut"] + tol) | (x["ouverture"] < x["plus_bas"] - tol))],
        ["séance absente de la base et clôture absente du fichier", "plus haut ou plus bas manquant",
         "plus haut inférieur au plus bas", "clôture au-dessus du plus haut", "clôture en dessous du plus bas",
         "ouverture hors de l'intervalle plus bas – plus haut"], "")
    x["motif"] = motif
    ok = x[x["motif"] == ""][["date", "cloture", "ouverture", "plus_haut", "plus_bas", "source", "nouvelle",
                              "ecart_cloture"]]
    return ok.reset_index(drop=True), x[x["motif"] != ""].reset_index(drop=True)


def enregistrer_hauts_bas(ok: pd.DataFrame) -> int:
    if ok.empty:
        return 0
    lignes = ok[["date", "cloture", "ouverture", "plus_haut", "plus_bas", "source"]]
    return store.upsert("masi20", lignes, f"Historique MASI 20 : plus haut / plus bas ({len(ok)} séances)")


# ------------------------------------------------ recalcul des grosses transactions sur l'historique
def recalculer_grosses(progression=None) -> dict:
    """Relit tous les bulletins de la cote conservés dans data/bulletins, dans l'ordre des dates, et
    recalcule les grosses transactions avec la règle actuelle (portes 1 et 2). Met à jour la colonne
    volume_gros de la table flux et la table grosses. Les séances sans PDF gardent leurs valeurs."""
    fichiers = sorted(store.BULLETINS.glob("cote_*.pdf")) if store.BULLETINS.exists() else []
    flux = store.load("flux")
    if not fichiers or flux.empty:
        return {"bulletins": 0, "niveaux": 0}
    toutes, maj = [], []
    for i, f in enumerate(fichiers):
        if progression:
            progression(i / len(fichiers), f.name)
        try:
            b = lire_cote(f.read_bytes())
        except Exception:
            continue
        d = pd.Timestamp(b.seance)
        niv = GT.classer(b.niveaux, GT.habituel(flux, d))
        g = _agreger_flux(niv)[["date", "isin", "marche", "volume_gros"]]
        maj.append(g)
        toutes.append(GT.table_grosses(niv))
    if progression:
        progression(1.0, "enregistrement")
    if not maj:
        return {"bulletins": 0, "niveaux": 0}
    m = pd.concat(maj).dropna(subset=["isin"])
    cle = ["date", "isin", "marche"]
    flux = flux.merge(m.rename(columns={"volume_gros": "_nv"}), on=cle, how="left")
    flux["volume_gros"] = flux["_nv"].where(flux["_nv"].notna(), flux["volume_gros"])
    flux = flux.drop(columns="_nv")
    store.save("flux", flux, "Recalcul des grosses transactions")
    gros = pd.concat(toutes, ignore_index=True)
    store.save("grosses", gros, "Recalcul des grosses transactions")
    return {"bulletins": len(maj), "niveaux": len(gros), "montant": float(gros["volume"].sum())}
