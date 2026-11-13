"""Formats d'affichage à la française : 1 264,07 · +3,44 % · 644 M MAD."""
import math

MOIS_FR = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août",
           "septembre", "octobre", "novembre", "décembre"]
JOURS_FR = ["Lun", "Mar", "Mer", "Jeu", "Ven", "Sam", "Dim"]


def _ok(x):
    return x is not None and not (isinstance(x, float) and math.isnan(x))


def nombre(x, d=2, signe=False):
    if not _ok(x):
        return "–"
    t = f"{x:+,.{d}f}" if signe else f"{x:,.{d}f}"
    return t.replace(",", " ").replace(".", ",")


def pct(x, d=2, signe=True):
    """x en fraction (0,0344 -> +3,44 %)."""
    return "–" if not _ok(x) else nombre(x * 100, d, signe) + " %"


def mad(x, d=1):
    if not _ok(x):
        return "–"
    if abs(x) >= 1e9:
        return nombre(x / 1e9, d) + " Md MAD"
    if abs(x) >= 1e6:
        return nombre(x / 1e6, d) + " M MAD"
    return nombre(x, 0) + " MAD"


def pts(x, d=2):
    return "–" if not _ok(x) else nombre(x, d) + " pts"


def date_longue(d):
    return f"{d.day} {MOIS_FR[d.month - 1]} {d.year}"


def date_courte(d):
    return f"{d:%d/%m/%Y}"


def jour(d):
    return f"{JOURS_FR[d.weekday()]} {d:%d/%m}"
