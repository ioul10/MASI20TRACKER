"""Construit la base de départ de MASI20TRACKER (à lancer une seule fois).

    python scripts/initialiser.py --excel BASEMASI20TRACKER.xlsx --bulletins dossier_pdf/

1. Historique MASI 20 (feuille MSI20INDEX : Date, MASI20, High, Low)
2. Historique futures (feuilles DATA_SUIVI et DATA_TRANS)
3. Tous les bulletins PDF du dossier (cote et futures) : les valeurs des
   bulletins remplacent celles de l'Excel pour les mêmes séances.
"""
import argparse
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src import store  # noqa: E402
from src.importer import analyser, enregistrer  # noqa: E402
from src.parsers import to_num  # noqa: E402


def _num(s):
    return s.map(lambda v: v if isinstance(v, (int, float)) else to_num(v)).astype(float)


def depuis_excel(path):
    x = pd.ExcelFile(path)
    i = pd.read_excel(x, "MSI20INDEX")
    i = i[pd.to_datetime(i["Date"], errors="coerce").notna()]
    m = pd.DataFrame({"date": pd.to_datetime(i["Date"]), "cloture": _num(i["MASI20"]),
                      "plus_haut": _num(i["High"]), "plus_bas": _num(i["Low"]), "source": "excel"})
    store.upsert("masi20", m.dropna(subset=["cloture"]))

    s = pd.read_excel(x, "DATA_SUIVI")
    s.columns = [str(c).strip() for c in s.columns]
    s = s[pd.to_datetime(s["Date"], errors="coerce").notna()]
    fut = pd.DataFrame({"date": pd.to_datetime(s["Date"]), "ticker": s["Ticker"].str.strip(),
                        "isin": s["Code ISIN"], "instrument": s["Instrument"],
                        "cours_ref": _num(s["Cours_Ref"]), "ouverture": _num(s["Ouverture"]),
                        "plus_bas": _num(s["Bas"]), "plus_haut": _num(s["Haut"]),
                        "cloture": _num(s["Cloture"]), "compensation": _num(s["Cours_Comp"]),
                        "open_interest": _num(s["Open_Interest"])})
    store.upsert("futures", fut)

    t = pd.read_excel(x, "DATA_TRANS")
    t.columns = [str(c).strip() for c in t.columns]
    t = t[pd.to_datetime(t["Date"], errors="coerce").notna()]
    tr = pd.DataFrame({"date": pd.to_datetime(t["Date"]), "ticker": t["Ticker"].str.strip(),
                       "carnet": t["Carnet"], "cours": _num(t["Cours_Transaction"]),
                       "multiplicateur": _num(t["Multiplicateur"]), "volume": _num(t["Volume_MAD"]),
                       "quantite": _num(t["Quantite"]), "nb": _num(t["Nb_Transactions"])})
    store.save("futures_trades", tr.sort_values(["date", "ticker"]))
    print(f"Excel : {len(m)} séances MASI 20, {len(fut)} lignes futures, {len(tr)} transactions")


def depuis_bulletins(dossier):
    for f in sorted(Path(dossier).glob("*.pdf")):
        contenu = f.read_bytes()
        try:
            rep = analyser(contenu, f.name)
        except ValueError as e:
            print(f"  ignoré {f.name} : {e}")
            continue
        enregistrer(rep, contenu, f"{rep.type}_{rep.seance:%Y%m%d}.pdf")
        print(f"  {rep.type:8} {rep.seance:%d/%m/%Y}  {rep.resume}")
        for a in rep.alertes:
            print("    ALERTE :", a)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--excel")
    ap.add_argument("--bulletins")
    a = ap.parse_args()
    if a.excel:
        depuis_excel(a.excel)
    if a.bulletins:
        depuis_bulletins(a.bulletins)
