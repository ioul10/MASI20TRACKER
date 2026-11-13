"""Base de données de MASI20TRACKER : des fichiers CSV dans data/.

Sur Streamlit Cloud, le disque est effacé à chaque redémarrage. Si les secrets
GITHUB_TOKEN et GITHUB_REPO sont définis, chaque écriture est aussi envoyée
dans le repo GitHub (privé), qui devient la sauvegarde permanente.
"""
from __future__ import annotations

import base64
from pathlib import Path

import pandas as pd
import requests

DATA = Path(__file__).resolve().parent.parent / "data"
BULLETINS = DATA / "bulletins"

# nom de table -> clés d'unicité (pour les mises à jour sans doublon)
TABLES = {
    "masi20": ["date"],                       # date, cloture, plus_haut, plus_bas, source
    "indices": ["date", "indice"],            # tous les indices du bulletin
    "actions": ["date", "isin"],              # cote de toutes les actions
    "flux": ["date", "isin", "marche"],       # physionomie agrégée
    "futures": ["date", "ticker"],            # cours des futures
    "futures_trades": ["date", "ticker", "cours", "quantite", "volume"],
    "composition": ["isin", "date_debut"],    # composition du MASI 20
}
DATES = {"date", "date_debut", "date_fin"}


def _path(name: str) -> Path:
    return DATA / f"{name}.csv"


def load(name: str) -> pd.DataFrame:
    p = _path(name)
    if not p.exists():
        return pd.DataFrame()
    df = pd.read_csv(p)
    for c in DATES & set(df.columns):
        df[c] = pd.to_datetime(df[c], errors="coerce")
    return df


def save(name: str, df: pd.DataFrame, message: str | None = None) -> None:
    DATA.mkdir(parents=True, exist_ok=True)
    out = df.copy()
    for c in DATES & set(out.columns):
        out[c] = pd.to_datetime(out[c]).dt.strftime("%Y-%m-%d")
    out.to_csv(_path(name), index=False)
    github_push(f"data/{name}.csv", _path(name).read_bytes(), message or f"MAJ {name}")


def upsert(name: str, new: pd.DataFrame, message: str | None = None) -> int:
    """Ajoute ou remplace des lignes (selon les clés de la table).
    Renvoie le nombre de lignes ajoutées ou remplacées."""
    if new is None or new.empty:
        return 0
    keys = TABLES[name]
    old = load(name)
    both = pd.concat([old, new], ignore_index=True) if not old.empty else new.copy()
    for c in DATES & set(both.columns):
        both[c] = pd.to_datetime(both[c])
    both = both.drop_duplicates(keys, keep="last").sort_values(keys).reset_index(drop=True)
    save(name, both, message)
    return len(new)


def save_bulletin(filename: str, content: bytes) -> None:
    BULLETINS.mkdir(parents=True, exist_ok=True)
    (BULLETINS / filename).write_bytes(content)
    github_push(f"data/bulletins/{filename}", content, f"Bulletin {filename}")


# ---------------------------------------------------------------- GitHub
def _secrets() -> tuple[str | None, str | None, str]:
    try:
        import streamlit as st
        s = st.secrets
        return s.get("GITHUB_TOKEN"), s.get("GITHUB_REPO"), s.get("GITHUB_BRANCH", "main")
    except Exception:
        return None, None, "main"


def github_actif() -> bool:
    tok, repo, _ = _secrets()
    return bool(tok and repo)


def github_push(path: str, content: bytes, message: str) -> bool:
    tok, repo, branch = _secrets()
    if not (tok and repo):
        return False
    url = f"https://api.github.com/repos/{repo}/contents/{path}"
    h = {"Authorization": f"Bearer {tok}", "Accept": "application/vnd.github+json"}
    sha = None
    r = requests.get(url, headers=h, params={"ref": branch}, timeout=20)
    if r.status_code == 200:
        sha = r.json().get("sha")
    body = {"message": message, "content": base64.b64encode(content).decode(), "branch": branch}
    if sha:
        body["sha"] = sha
    r = requests.put(url, headers=h, json=body, timeout=30)
    if r.status_code not in (200, 201):
        raise RuntimeError(f"Sauvegarde GitHub refusée ({r.status_code}) : {r.text[:200]}")
    return True
