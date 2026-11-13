"""Lecture des bulletins officiels de la Bourse de Casablanca.

Deux documents sont lus :
- le bulletin de la cote (BCFR_AAAAMMJJ.pdf) : actions, physionomie des transactions, indices ;
- le bulletin du marché à terme (BCFR_D_AAAAMMJJ.pdf) : cours et transactions des futures.

Méthode : pdfplumber donne la position de chaque mot. Deux mots séparés par
un simple espace (≈1,7 pt, comme dans « 1 050,00 ») sont regroupés ; un écart
plus grand marque une nouvelle colonne. Les sections sont repérées par leur
titre, jamais par leur numéro de page (le nombre de pages varie de 20 à 26).
"""
from __future__ import annotations

import io
import re
from dataclasses import dataclass, field
from datetime import date, datetime

import pandas as pd
import pdfplumber

GAP_COLONNE = 2.6  # pt : au-delà, deux mots appartiennent à deux colonnes

RE_NUM = re.compile(r"^-?\d{1,3}(?: \d{3})*(?:,\d+)?$")
RE_ISIN = re.compile(r"^MA\d{10}$")
RE_DATE_SEANCE = re.compile(r"Séance du (\d{2}/\d{2}/\d{2,4})")


# ---------------------------------------------------------------- utilitaires
def to_num(tok: str | None) -> float | None:
    """'1 398,00' -> 1398.0 ; '-' ou vide -> None ; '3,44 %' -> 3.44"""
    if tok is None:
        return None
    t = str(tok).replace("%", "").replace(" ", " ").strip()
    if t in {"", "-", "—"}:
        return None
    t = t.replace(" ", "").replace(",", ".")
    try:
        return float(t)
    except ValueError:
        return None


def is_num(tok: str) -> bool:
    return bool(RE_NUM.match(tok.strip()))


def parse_date(s: str) -> date:
    fmt = "%d/%m/%Y" if len(s.split("/")[-1]) == 4 else "%d/%m/%y"
    return datetime.strptime(s, fmt).date()


def norm_nom(s: str) -> str:
    """Normalise un nom de société pour le rapprochement (secours seulement :
    la clé de référence reste le code ISIN)."""
    s = s.upper().replace("-", " ").replace(".", " ")
    s = re.sub(r"\b(S A|SA|SCA)\b", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def _lignes(page) -> list[list[str]]:
    mots = page.extract_words(x_tolerance=1.5, keep_blank_chars=False)
    mots.sort(key=lambda w: (round(w["top"]), w["x0"]))
    rangs: list[list] = []
    for w in mots:
        if rangs and abs(rangs[-1][0] - w["top"]) < 2.5:
            rangs[-1][1].append(w)
        else:
            rangs.append([w["top"], [w]])
    out = []
    for _, r in rangs:
        r.sort(key=lambda w: w["x0"])
        toks, prev = [], None
        for w in r:
            if prev is not None and w["x0"] - prev["x1"] < GAP_COLONNE:
                toks[-1] += " " + w["text"]
            else:
                toks.append(w["text"])
            prev = w
        out.append(toks)
    return out


def _ouvrir(src) -> pdfplumber.PDF:
    if isinstance(src, (bytes, bytearray)):
        return pdfplumber.open(io.BytesIO(src))
    return pdfplumber.open(src)


# ------------------------------------------------------------- bulletin cote
@dataclass
class BulletinCote:
    seance: date
    actions: pd.DataFrame
    flux: pd.DataFrame          # physionomie agrégée par valeur et par marché
    niveaux: pd.DataFrame       # physionomie détaillée (un prix = une ligne)
    indices: pd.DataFrame
    secteurs: dict = field(default_factory=dict)
    totaux: dict = field(default_factory=dict)


COLS_ACTIONS = ["ouverture", "cloture", "plus_haut", "plus_bas", "statut",
                "demande", "offre", "haut_annuel", "bas_annuel"]


def _ligne_action(t: list[str], compartiment: str) -> dict | None:
    i_isin = next((i for i, x in enumerate(t) if RE_ISIN.match(x)), None)
    if i_isin is None or i_isin + 1 >= len(t):
        return None
    avant, nom, apres = t[:i_isin], t[i_isin + 1], t[i_isin + 2:]
    # Partie droite : 9 colonnes, statut au milieu (T / NT / S)
    i_stat = next((i for i, x in enumerate(apres) if x in {"T", "NT", "S", "R"}), None)
    if i_stat is None:
        return None
    gauche, droite = apres[:i_stat], apres[i_stat + 1:]
    gauche = (["-"] * (4 - len(gauche)) + gauche)[-4:]
    droite = (droite + ["-"] * 4)[:4]
    rec = {"isin": t[i_isin], "nom": nom.strip(), "compartiment": compartiment,
           "ouverture": to_num(gauche[0]), "cloture": to_num(gauche[1]),
           "plus_haut": to_num(gauche[2]), "plus_bas": to_num(gauche[3]),
           "statut": apres[i_stat],
           "demande": to_num(droite[0]), "offre": to_num(droite[1]),
           "haut_annuel": to_num(droite[2]), "bas_annuel": to_num(droite[3])}
    # Partie gauche : capital, valeur nominale, secteur, cycle, [dividende], ex, date, cours réf, date réf, cours réf suivant
    rec["nb_titres"] = to_num(avant[0]) if avant else None
    rec["secteur_code"] = next((x for x in avant[1:4] if re.fullmatch(r"[A-Z]{2,3}", x)), None)
    rec["cours_ref"] = to_num(avant[-3]) if len(avant) >= 3 else None
    rec["cours_ref_suivant"] = to_num(avant[-1]) if avant else None
    i_cyc = next((i for i, x in enumerate(avant) if x in {"C", "F"}), None)
    if i_cyc is not None and i_cyc + 1 < len(avant):
        nxt = avant[i_cyc + 1]
        rec["dividende"] = to_num(nxt) if "," in nxt else None
    return rec


def _ligne_flux(t: list[str]):
    """Ligne de transaction : nom | cours | quantité | volume | nb.
    Ligne de sous-total : libellé | quantité | volume | nb."""
    if len(t) == 5 and all(is_num(x) for x in t[1:]):
        return "niveau", t[0], to_num(t[1]), to_num(t[2]), to_num(t[3]), to_num(t[4])
    if len(t) == 4 and all(is_num(x) for x in t[1:]):
        return "total", t[0], None, to_num(t[1]), to_num(t[2]), to_num(t[3])
    return None


MARCHES = {"MARCHE CENTRAL": "central", "MARCHE DE BLOCS": "blocs",
           "TRANSFERTS": "transferts", "APPORTS DE TITRES": "apports",
           "OFFRES PUBLIQUES": "offres", "INTRODUCTIONS": "introductions"}
SOUS_SECTIONS = {"ACTIONS", "DROITS", "OBLIGATIONS", "BONS", "TITRES DE CREANCES"}


def lire_cote(src) -> BulletinCote:
    pdf = _ouvrir(src)
    seance = None
    actions, niveaux, indices, secteurs, totaux = [], [], [], {}, {}
    zone, compartiment, marche, sous = None, None, None, None
    for page in pdf.pages:
        for t in _lignes(page):
            ligne = " ".join(t)
            if seance is None and (m := RE_DATE_SEANCE.search(ligne)):
                seance = parse_date(m.group(1))
            # --- repérage des zones
            if ligne.startswith("MARCHE PRINCIPAL - ACTIONS") or ligne.startswith("MARCHE ALTERNATIF - ACTIONS"):
                zone = "actions"; continue
            if ligne.startswith("MARCHE PRINCIPAL -") or ligne.startswith("MARCHE ALTERNATIF -"):
                zone = "autre"; continue
            if ligne.startswith("PHYSIONOMIE DES TRANSACTIONS"):
                zone = "flux"; continue
            if ligne == "INDICES" or ligne.startswith("INDICES |"):
                zone = "indices"; continue
            if ligne.startswith("COMMENT LIRE"):
                zone = "legende"; continue
            # --- lecture selon la zone
            if zone == "actions":
                if re.fullmatch(r"(Principal|Alternatif|Croissance|Développement) [A-Z]", ligne):
                    compartiment = ligne; continue
                rec = _ligne_action(t, compartiment)
                if rec:
                    actions.append(rec)
            elif zone == "flux":
                r = _ligne_flux(t)
                if not r:
                    continue
                kind, lib, cours, qte, vol, nb = r
                if kind == "total":
                    if lib in MARCHES:
                        marche, sous = MARCHES[lib], None
                        totaux[marche] = {"quantite": qte, "volume": vol, "nb": nb}
                    elif lib in SOUS_SECTIONS:
                        sous = lib
                    elif lib == "TOTAL GENERAL":
                        totaux["general"] = {"quantite": qte, "volume": vol, "nb": nb}
                    continue
                if sous == "ACTIONS" and marche:
                    niveaux.append({"marche": marche, "nom": lib, "cours": cours,
                                    "quantite": qte, "volume": vol, "nb": nb})
            elif zone == "indices":
                if len(t) == 4 and is_num(t[1]):
                    indices.append({"indice": t[0], "valeur": to_num(t[1]),
                                    "var_veille": to_num(t[2]), "var_ytd": to_num(t[3])})
            elif zone == "legende":
                if len(t) >= 2 and re.fullmatch(r"[A-Z]{2,3}", t[0]) and t[0] not in {"NT"}:
                    secteurs[t[0]] = t[1]
    pdf.close()
    if seance is None:
        raise ValueError("Date de séance introuvable : ce n'est pas un bulletin de la cote.")

    act = pd.DataFrame(actions)
    if not act.empty:
        act.insert(0, "date", pd.Timestamp(seance))
        act = act.drop_duplicates("isin")
    niv = pd.DataFrame(niveaux, columns=["marche", "nom", "cours", "quantite", "volume", "nb"])
    niv.insert(0, "date", pd.Timestamp(seance))
    # Rapprochement nom (physionomie) -> ISIN (cote du même jour)
    table = {norm_nom(n): i for n, i in zip(act.get("nom", []), act.get("isin", []))}

    def _isin(n):
        k = norm_nom(n)
        if k in table:
            return table[k]
        cands = [v for kk, v in table.items() if kk.startswith(k) or k.startswith(kk)]
        return cands[0] if len(cands) == 1 else None

    niv["isin"] = niv["nom"].map(_isin)
    flux = _agreger_flux(niv)
    ind = pd.DataFrame(indices)
    if not ind.empty:
        ind.insert(0, "date", pd.Timestamp(seance))
        ind = ind.drop_duplicates("indice")
    return BulletinCote(seance, act, flux, niv, ind, secteurs, totaux)


def _agreger_flux(niv: pd.DataFrame) -> pd.DataFrame:
    """Une ligne par valeur et par marché : volume, quantité, contrats,
    prix moyen pondéré et concentration (part du plus gros niveau de prix)."""
    if niv.empty:
        return pd.DataFrame(columns=["date", "isin", "nom", "marche", "volume", "quantite", "nb", "vwap",
                                     "niveaux", "part_max_niveau", "volume_max_niveau", "volume_gros"])
    niv = niv.copy()
    # « Grosse transaction » : niveau de prix ≥ 5 M MAD et ≥ 1 M MAD par contrat
    gros = (niv["volume"] >= 5e6) & (niv["volume"] / niv["nb"].clip(lower=1) >= 1e6)
    niv["volume_gros"] = niv["volume"].where(gros, 0.0)
    g = niv.groupby(["date", "isin", "nom", "marche"], dropna=False)
    out = g.agg(volume=("volume", "sum"), quantite=("quantite", "sum"), nb=("nb", "sum"),
                niveaux=("cours", "size"), volume_max_niveau=("volume", "max"),
                volume_gros=("volume_gros", "sum")).reset_index()
    out["vwap"] = out["volume"] / out["quantite"]
    out["part_max_niveau"] = out["volume_max_niveau"] / out["volume"]
    return out


# ---------------------------------------------------------- bulletin futures
@dataclass
class BulletinFutures:
    seance: date
    cours: pd.DataFrame
    transactions: pd.DataFrame


def lire_futures(src) -> BulletinFutures:
    pdf = _ouvrir(src)
    seance, cours, trans = None, [], []
    for page in pdf.pages:
        for t in _lignes(page):
            ligne = " ".join(t)
            if seance is None and (m := RE_DATE_SEANCE.search(ligne)):
                seance = parse_date(m.group(1))
            if len(t) >= 6 and t[1].startswith("F") and RE_ISIN.match(t[2]):
                nums = [to_num(x) for x in t[5:]]
                if len(nums) == 7:
                    ref, ouv, bas, haut, clo, comp, oi = nums
                elif len(nums) == 4:
                    ref, clo, comp, oi = nums
                    ouv = bas = haut = None
                else:
                    continue
                cours.append({"ticker": t[1], "isin": t[2], "instrument": t[0], "cours_ref": ref,
                              "ouverture": ouv, "plus_bas": bas, "plus_haut": haut,
                              "cloture": clo, "compensation": comp, "open_interest": oi})
            elif len(t) == 8 and t[1].startswith("F") and t[2] in {"Central", "Blocs", "Bloc"}:
                trans.append({"ticker": t[1], "carnet": t[2], "cours": to_num(t[3]),
                              "multiplicateur": to_num(t[4]), "volume": to_num(t[5]),
                              "quantite": to_num(t[6]), "nb": to_num(t[7])})
    pdf.close()
    if seance is None:
        raise ValueError("Date de séance introuvable : ce n'est pas un bulletin du marché à terme.")
    c = pd.DataFrame(cours, columns=["ticker", "isin", "instrument", "cours_ref", "ouverture", "plus_bas",
                                     "plus_haut", "cloture", "compensation", "open_interest"])
    c.insert(0, "date", pd.Timestamp(seance))
    tr = pd.DataFrame(trans, columns=["ticker", "carnet", "cours", "multiplicateur", "volume", "quantite", "nb"])
    tr.insert(0, "date", pd.Timestamp(seance))
    return BulletinFutures(seance, c, tr)


def detecter_type(src) -> str:
    """'cote' ou 'futures' d'après le contenu de la première page."""
    pdf = _ouvrir(src)
    txt = pdf.pages[0].extract_text() or ""
    pdf.close()
    if "instruments dérivés" in txt or "FMASI20" in txt:
        return "futures"
    if "Bulletin de la cote" in txt or "MARCHE PRINCIPAL" in txt:
        return "cote"
    raise ValueError("Document non reconnu (ni bulletin de la cote, ni bulletin des futures).")
