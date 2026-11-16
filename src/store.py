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
    _push_sans_bloquer(f"data/{name}.csv", _path(name).read_bytes(), message or f"MAJ {name}")


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
    _push_sans_bloquer(f"data/bulletins/{filename}", content, f"Bulletin {filename}")


def _push_sans_bloquer(path: str, content: bytes, message: str) -> None:
    """Les données sont toujours enregistrées sur le serveur ; un échec de
    sauvegarde GitHub est noté (et affiché) au lieu de faire planter l'import."""
    try:
        github_push(path, content, message)
    except Exception as e:  # réseau, droits…
        msg = str(e) if isinstance(e, GithubError) else f"Sauvegarde GitHub impossible : {type(e).__name__}"
        if msg not in ERREURS_GITHUB:
            ERREURS_GITHUB.append(msg)


# ---------------------------------------------------------------- GitHub
ERREURS_GITHUB: list[str] = []   # erreurs de sauvegarde de la session (affichées par la page Import)


class GithubError(RuntimeError):
    pass


def _secrets() -> tuple[str | None, str | None, str]:
    try:
        import streamlit as st
        s = st.secrets
        tok = (s.get("GITHUB_TOKEN") or "").strip() or None
        repo = (s.get("GITHUB_REPO") or "").strip()
        branch = (s.get("GITHUB_BRANCH") or "main").strip()
    except Exception:
        return None, None, "main"
    # tolère une adresse complète : https://github.com/compte/repo(.git)
    repo = repo.replace("https://", "").replace("http://", "").replace("github.com/", "").strip("/")
    repo = repo[:-4] if repo.endswith(".git") else repo
    return tok, (repo or None), branch


def github_actif() -> bool:
    tok, repo, _ = _secrets()
    return bool(tok and repo)


def _expliquer(code: int, texte: str, repo: str, branch: str) -> str:
    if code == 401:
        return ("Jeton GitHub refusé (401) : il est incorrect, incomplet ou expiré. "
                "Recopiez-le entièrement dans les secrets (il commence par github_pat_), ou créez-en un nouveau.")
    if code == 403:
        return ("Jeton GitHub sans droit d'écriture (403). Dans les réglages du jeton : Repository permissions → "
                "Contents → Read and write, et vérifiez que le repo est bien sélectionné.")
    if code == 404:
        return (f"Repo « {repo} » introuvable pour ce jeton (404). Vérifiez GITHUB_REPO (format compte/repo, "
                "exactement comme dans l'adresse GitHub) et que le jeton a accès à ce repo (Only select repositories).")
    if code in (409, 422) and ("branch" in texte.lower() or "ref" in texte.lower()):
        return (f"Branche « {branch} » introuvable ({code}). Vérifiez GITHUB_BRANCH : souvent « main », parfois « master ».")
    return f"Sauvegarde GitHub refusée ({code}) : {texte[:200]}"


def _headers(tok: str) -> dict:
    return {"Authorization": f"Bearer {tok}", "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28"}


def github_push(path: str, content: bytes, message: str) -> bool:
    tok, repo, branch = _secrets()
    if not (tok and repo):
        return False
    url = f"https://api.github.com/repos/{repo}/contents/{path}"
    h = _headers(tok)
    sha = None
    r = requests.get(url, headers=h, params={"ref": branch}, timeout=20)
    if r.status_code == 200:
        sha = r.json().get("sha")
    elif r.status_code in (401, 403):
        raise GithubError(_expliquer(r.status_code, r.text, repo, branch))
    body = {"message": message, "content": base64.b64encode(content).decode(), "branch": branch}
    if sha:
        body["sha"] = sha
    r = requests.put(url, headers=h, json=body, timeout=60)
    if r.status_code not in (200, 201):
        raise GithubError(_expliquer(r.status_code, r.text, repo, branch))
    return True


def diagnostic_github() -> tuple[bool, list[str]]:
    try:
        return _diagnostic()
    except requests.RequestException as e:
        return False, [f"❌ GitHub injoignable depuis le serveur ({type(e).__name__}). Réessayez dans quelques minutes."]


def _diagnostic() -> tuple[bool, list[str]]:
    """Vérifie pas à pas : secrets, jeton, accès au repo, droit d'écriture, branche."""
    tok, repo, branch = _secrets()
    etapes = []
    if not tok:
        return False, ["❌ GITHUB_TOKEN absent des secrets."]
    if not repo:
        return False, ["❌ GITHUB_REPO absent des secrets."]
    etapes.append(f"✅ Secrets lus : repo « {repo} », branche « {branch} ».")
    h = _headers(tok)
    r = requests.get("https://api.github.com/user", headers=h, timeout=20)
    if r.status_code == 401:
        return False, etapes + ["❌ " + _expliquer(401, r.text, repo, branch)]
    etapes.append("✅ Jeton valide." + (f" Compte : {r.json().get('login')}." if r.status_code == 200 else ""))
    r = requests.get(f"https://api.github.com/repos/{repo}", headers=h, timeout=20)
    if r.status_code != 200:
        return False, etapes + ["❌ " + _expliquer(r.status_code, r.text, repo, branch)]
    info = r.json()
    etapes.append(f"✅ Repo trouvé ({'privé' if info.get('private') else 'public'}). Branche par défaut : « {info.get('default_branch')} ».")
    if not info.get("permissions", {}).get("push", False):
        return False, etapes + ["❌ " + _expliquer(403, "", repo, branch)]
    etapes.append("✅ Droit d'écriture accordé.")
    r = requests.get(f"https://api.github.com/repos/{repo}/branches/{branch}", headers=h, timeout=20)
    if r.status_code != 200:
        return False, etapes + [f"❌ Branche « {branch} » introuvable. Mettez GITHUB_BRANCH = \"{info.get('default_branch')}\" dans les secrets."]
    etapes.append(f"✅ Branche « {branch} » trouvée.")
    try:
        github_push("data/.test_sauvegarde", b"ok", "Test de sauvegarde MASI20TRACKER")
        etapes.append("✅ Écriture de test réussie : la sauvegarde fonctionne.")
        return True, etapes
    except GithubError as e:
        return False, etapes + [f"❌ {e}"]
