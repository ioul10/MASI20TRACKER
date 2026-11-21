"""Import d'un bulletin : lecture, contrôles, puis enregistrement."""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from . import config as C
from . import store
from .composants import composition_au, rendements_jour
from .fmt import mad, nombre
from .parsers import detecter_type, lire_cote, lire_futures


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
    rep.tables = {"actions": b.actions, "flux": b.flux, "indices": b.indices}
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
        if name == "futures_trades":   # on remplace toute la séance (pas d'identifiant de transaction)
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
    row.update({"plus_haut": h, "plus_bas": b})
    return pd.DataFrame([row])


# ------------------------------------------------ plus haut / plus bas du MASI 20
_NOMS_HAUT = ("plus haut", "plus_haut", "haut", "high", "+ haut", "+haut", "max")
_NOMS_BAS = ("plus bas", "plus_bas", "bas", "low", "+ bas", "+bas", "min")
_NOMS_DATE = ("date", "séance", "seance", "jour")


def _nombre_fr(x):
    """'1 264,07' / '1264.07' / 1264.07 -> 1264.07"""
    if x is None or (isinstance(x, float) and pd.isna(x)):
        return None
    if isinstance(x, (int, float)):
        return float(x)
    t = str(x).replace(" ", "").replace(" ", "").replace(" ", "")
    if "," in t and "." in t:
        t = t.replace(".", "").replace(",", ".") if t.rfind(",") > t.rfind(".") else t.replace(",", "")
    else:
        t = t.replace(",", ".")
    try:
        return float(t)
    except ValueError:
        return None


def lire_hauts_bas(fichier, nom: str) -> pd.DataFrame:
    """Lit un CSV ou un Excel contenant au moins : date, plus haut, plus bas.
    Pour un Excel, prend la première feuille qui contient ces colonnes (ex. MASI20INDEX)."""
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
        out = pd.DataFrame({"date": pd.to_datetime(df[d], dayfirst=True, errors="coerce"),
                            "plus_haut": df[h].map(_nombre_fr), "plus_bas": df[b].map(_nombre_fr)})
        return out.dropna(subset=["date"])

    if nom.lower().endswith((".xlsx", ".xlsm", ".xls")):
        feuilles = pd.read_excel(fichier, sheet_name=None)
        for _, df in feuilles.items():
            for entete in range(0, 6):     # en-tête éventuellement décalé de quelques lignes
                x = df if entete == 0 else df.iloc[entete - 1:].set_axis(df.iloc[entete - 1].values, axis=1).iloc[1:]
                r = normaliser(x)
                if r is not None and len(r):
                    return r
        raise ValueError("Aucune feuille avec les colonnes Date, Plus haut et Plus bas.")
    df = pd.read_csv(fichier, sep=None, engine="python")
    r = normaliser(df)
    if r is None:
        raise ValueError("Colonnes attendues : Date, Plus haut, Plus bas.")
    return r


def controler_hauts_bas(saisie: pd.DataFrame, masi20: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Rapproche la saisie des clôtures connues. Renvoie (lignes valides, lignes rejetées avec motif).
    Règle : plus bas ≤ clôture ≤ plus haut (tolérance 0,01 pt)."""
    s = saisie.dropna(subset=["plus_haut", "plus_bas"], how="all").copy()
    s["date"] = pd.to_datetime(s["date"]).dt.normalize()
    m = masi20[["date", "cloture", "source"]].copy()
    m["date"] = pd.to_datetime(m["date"]).dt.normalize()
    x = s.merge(m, on="date", how="left")
    motif = np.select(
        [x["cloture"].isna(), x["plus_haut"].isna() | x["plus_bas"].isna(), x["plus_haut"] < x["plus_bas"],
         x["cloture"] > x["plus_haut"] + 0.01, x["cloture"] < x["plus_bas"] - 0.01],
        ["séance absente de la base (importez d'abord le bulletin)", "plus haut ou plus bas manquant",
         "plus haut inférieur au plus bas", "clôture au-dessus du plus haut", "clôture en dessous du plus bas"], "")
    x["motif"] = motif
    ok = x[x["motif"] == ""][["date", "cloture", "plus_haut", "plus_bas", "source"]]
    return ok.reset_index(drop=True), x[x["motif"] != ""].reset_index(drop=True)


def enregistrer_hauts_bas(ok: pd.DataFrame) -> int:
    if ok.empty:
        return 0
    return store.upsert("masi20", ok, f"Plus haut / plus bas MASI 20 ({len(ok)} séances)")
