"""Styles par page : chaque page choisit un habillage (CSS + couleurs des graphiques).

- classique : le style de base de l'application ;
- antique   : journal financier d'autrefois (tableau de bord) ;
- bourse    : esprit tableau de cotation de la Bourse de Casablanca (composants, marché à terme) ;
- trading   : écran de salle de marché, fond sombre (indice & technique).
"""
from __future__ import annotations

import threading

from . import config as C

_etat = threading.local()


def actif() -> str:
    return getattr(_etat, "nom", "classique")


def activer(nom: str) -> None:
    _etat.nom = nom if nom in ("antique", "trading", "bourse") else "classique"


def roman(n) -> str:
    try:
        n = int(n)
    except (TypeError, ValueError):
        return str(n)
    v = [(10, "X"), (9, "IX"), (5, "V"), (4, "IV"), (1, "I")]
    s = ""
    for a, r in v:
        while n >= a:
            s, n = s + r, n - a
    return s


# ------------------------------------------------------------------ couleurs des graphiques
# « map » : couleur de base → couleur du thème (appliquée à tous les traits, barres, repères).
_BASE = {"NAVY": C.NAVY, "GOLD": C.GOLD, "INK": C.INK, "MUTED": C.MUTED, "GRID": C.GRID, "UP": C.UP, "DOWN": C.DOWN,
         "NAVY_2": C.NAVY_2}

GRAPHES = {
    "antique": {
        "paper": "#FBF7EE", "plot": "#FBF7EE", "font": "EB Garamond, Georgia, serif", "texte": "#2A1F14",
        "muet": "#7A6A55", "grille": "#E4D8BF", "survol": "#FFFDF7",
        "map": {C.NAVY: "#2A1F14", C.NAVY_2: "#5A4632", C.GOLD: "#A9802F", C.INK: "#2A1F14", C.MUTED: "#7A6A55",
                C.GRID: "#DCCFB4", C.UP: "#3D6B35", C.DOWN: "#9B2C22", "#D98A1E": "#B07A2A", "#1BA37A": "#4F7A4A",
                "#6250D6": "#5B4A7A", "#C2477A": "#8E3B4F", "#1F5FAD": "#3B5875", "#5B7DB1": "#6F7F94",
                "#B8C2D3": "#CDBFA3", "#C9D3E6": "#E2D6BC", "#D8DEEA": "#E6DCC5", "#9BD3B4": "#B9CDA8",
                "#EBA9A9": "#DDB0A6", "#C8A24A": "#A9802F", "#E9D7A5": "#E3CF9E", "#7FA7D9": "#8C9AAB",
                "#12804A": "#3D6B35", "#C23B3B": "#9B2C22", "#E9ECF2": "#EFE6D2", "white": "#FBF7EE"},
    },
    "trading": {
        "paper": "#111723", "plot": "#0D121C", "font": "IBM Plex Sans, Inter, sans-serif", "texte": "#D5DCE8",
        "muet": "#7F8BA3", "grille": "#1C2433", "survol": "#171E2C",
        "map": {C.NAVY: "#E8EDF5", C.NAVY_2: "#9FB3D1", C.GOLD: "#F0B90B", C.INK: "#D5DCE8", C.MUTED: "#7F8BA3",
                C.GRID: "#232C3D", C.UP: "#16C784", C.DOWN: "#EA3943", "#D98A1E": "#F0B90B", "#1BA37A": "#3BA7FF",
                "#6250D6": "#A78BFA", "#C2477A": "#F472B6", "#1F5FAD": "#3BA7FF", "#5B7DB1": "#3BA7FF",
                "#B8C2D3": "#3A4558", "#C9D3E6": "#2A3446", "#D8DEEA": "#2A3446", "#9BD3B4": "#0F5E43",
                "#EBA9A9": "#6B2329", "#C8A24A": "#F0B90B", "#E9D7A5": "#8A6D12", "#7FA7D9": "#5B7FB0",
                "#12804A": "#16C784", "#C23B3B": "#EA3943", "#E9ECF2": "#1C2433", "#9AA7BD": "#55627A",
                "#B8A15A": "#F0B90B", "#8C7A3C": "#F0B90B", "white": "#111723",
                "rgba(194,59,59,.07)": "rgba(234,57,67,.10)", "rgba(18,128,74,.07)": "rgba(22,199,132,.10)",
                "rgba(138,148,166,.10)": "rgba(127,139,163,.10)"},
    },
    "bourse": {
        "paper": "#FFFFFF", "plot": "#FFFFFF", "font": "Roboto, Inter, sans-serif", "texte": "#0D1B2E",
        "muet": "#5E6B80", "grille": "#E3E8F0", "survol": "#FFFFFF",
        "map": {C.NAVY: "#0A2B5C", C.NAVY_2: "#2D5597", C.GOLD: "#F18A00", C.INK: "#0D1B2E", C.MUTED: "#5E6B80",
                C.UP: "#0E9F59", C.DOWN: "#E03B3B", "#12804A": "#0E9F59", "#C23B3B": "#E03B3B",
                "#C8A24A": "#F18A00", "#E9D7A5": "#FAD7A6", "#5B7DB1": "#2D5597", "#1F5FAD": "#0A2B5C",
                "#D98A1E": "#F18A00"},
    },
}


# ------------------------------------------------------------------ CSS
def css(nom: str) -> str:
    if nom == "antique":
        return _ANTIQUE
    if nom == "trading":
        return _TRADING
    if nom == "bourse":
        return _BOURSE
    return ""


_ANTIQUE = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Playfair+Display:ital,wght@0,600;0,700;0,800;1,600&family=EB+Garamond:ital,wght@0,400;0,500;0,600;0,700;1,400&display=swap');
:root { --enc:#2A1F14; --sep:#7A6A55; --par:#F2EBDC; --pap:#FBF7EE; --bor:#7B2D26; --or:#A9802F; --fil:#CDBFA3; }
.stApp, [data-testid="stAppViewContainer"] { background: var(--par)
  radial-gradient(circle at 20% 0%, rgba(255,255,255,.55), rgba(242,235,220,0) 60%); }
[data-testid="stHeader"] { background: transparent; }
[data-testid="stSidebar"] { background: #EDE3CF; border-right: 3px double var(--fil); }
[data-testid="stSidebarNavLink"] span:not([data-testid="stIconMaterial"]) { color: var(--enc) !important; font-family: 'EB Garamond', serif; font-size: 1.02rem; }
[data-testid="stSidebarNavLink"][aria-current="page"] { background: rgba(123,45,38,.08); box-shadow: inset 3px 0 0 var(--bor); }
.m20-etat { background: var(--pap); border: 1px solid var(--fil); border-radius: 0; font-family: 'EB Garamond', serif; }
[data-testid="stMain"] .stMarkdown, [data-testid="stMain"] p, [data-testid="stMain"] li, [data-testid="stMain"] label,
[data-testid="stMain"] [data-testid="stCaptionContainer"] { font-family: 'EB Garamond', Georgia, serif !important; color: var(--enc); }
[data-testid="stMain"] p, [data-testid="stMain"] li { font-size: 1.04rem; }
/* bandeau : manchette de journal */
.m20-banner { background: var(--pap); border: none; border-top: 5px double var(--enc); border-bottom: 5px double var(--enc);
  border-radius: 0; box-shadow: none; padding: 14px 6px; }
.m20-banner .m20-sep { background: var(--fil); }
.m20-banner .m20-app { font-family: 'EB Garamond', serif; letter-spacing: 3px; color: var(--sep); }
.m20-banner .m20-app span { color: var(--bor); }
.m20-banner .m20-t { font-family: 'Playfair Display', serif; font-weight: 800; font-size: 2.15rem; color: var(--enc) !important;
  letter-spacing: .3px; }
.m20-banner p { font-family: 'EB Garamond', serif; font-style: italic; font-size: 1.02rem; color: var(--sep); }
.m20-banner .m20-date { background: transparent; border: 1px solid var(--enc); border-radius: 0; font-family: 'EB Garamond', serif;
  text-transform: uppercase; letter-spacing: 1.5px; color: var(--sep); }
.m20-banner .m20-date b { font-family: 'Playfair Display', serif; color: var(--enc); letter-spacing: 0; text-transform: none; font-size: 1.15rem; }
/* chapitres et sections */
.m20-chap { background: transparent; border: none; border-top: 2px solid var(--enc); border-bottom: 1px solid var(--enc);
  border-radius: 0; box-shadow: none; padding: 12px 2px 10px; margin-top: 44px; }
.m20-chap .num { background: transparent; color: var(--bor); box-shadow: none; font-family: 'Playfair Display', serif;
  font-size: 1.9rem; font-weight: 800; min-width: 46px; border-right: 1px solid var(--fil); border-radius: 0; }
.m20-chap .t { font-family: 'Playfair Display', serif; font-size: 1.55rem; font-weight: 700; color: var(--enc); }
.m20-chap .s { font-family: 'EB Garamond', serif; font-style: italic; font-size: .98rem; color: var(--sep); }
.m20-section { font-family: 'EB Garamond', serif; font-variant: small-caps; letter-spacing: 1.2px; font-size: 1.15rem;
  color: var(--enc); border-left: none; padding-left: 0; border-bottom: 1px solid var(--enc); box-shadow: 0 3px 0 -2px var(--fil); }
/* chiffres clés */
.m20-kpi { background: var(--pap); border: 1px solid var(--fil); border-top: 3px double var(--enc); border-radius: 0; box-shadow: none; }
.m20-kpi:before { display: none; }
.m20-kpi.gold { border-top-color: var(--bor); }
.m20-kpi:hover { box-shadow: 2px 3px 0 var(--fil); transform: none; }
.m20-kpi .lab { font-family: 'EB Garamond', serif; font-variant: small-caps; text-transform: none; font-size: .92rem; letter-spacing: 1px; color: var(--sep); }
.m20-kpi .val { font-family: 'Playfair Display', serif; font-size: 1.6rem; color: var(--enc); font-variant-numeric: lining-nums; }
.m20-kpi .sub { font-family: 'EB Garamond', serif; font-size: .95rem; font-style: italic; }
.up { color: #3D6B35 !important; } .down { color: #9B2C22 !important; }
/* encadré : chapeau d'article avec lettrine */
.m20-box { background: var(--pap); border: 1px solid var(--fil); border-left: 4px solid var(--bor); border-radius: 0;
  font-family: 'EB Garamond', serif; font-size: 1.1rem; line-height: 1.6; color: var(--enc); }
.m20-box:not(:has(ul))::first-letter { font-family: 'Playfair Display', serif; font-size: 3.1rem; float: left; line-height: .9;
  padding: 4px 8px 0 0; color: var(--bor); font-weight: 800; }
.m20-note { background: #F7EDD5; border-color: #E0CB97; border-radius: 0; font-family: 'EB Garamond', serif; }
[data-testid="stPlotlyChart"] { background: var(--pap); border: 1px solid var(--fil); border-radius: 0; }
[data-testid="stTabs"] button[role="tab"] p { font-family: 'Playfair Display', serif !important; font-size: 1.08rem; }
[data-testid="stTabs"] [data-baseweb="tab-highlight"] { background-color: var(--bor); }
[data-testid="stTabs"] [data-baseweb="tab-border"] { background-color: var(--enc); }
[data-testid="stBaseButton-primary"] { background: var(--bor); border-color: var(--bor); border-radius: 0; }
[data-testid="stTextArea"] textarea, [data-testid="stTextInput"] input { font-family: 'EB Garamond', serif; font-size: 1.05rem; background: var(--pap); }
.m20-foot { font-family: 'EB Garamond', serif; border-top: 3px double var(--enc); }
[data-testid="stMain"] [data-testid="stButtonGroup"] button { border-radius: 0 !important; background: var(--pap) !important; }
[data-testid="stMain"] [data-testid="stButtonGroup"] button:is([aria-checked="true"], [data-selected="true"], [kind$="Active"]) {
  background: var(--enc) !important; border-color: var(--enc) !important; }
[data-testid="stMain"] [data-testid="stButtonGroup"] button:is([aria-checked="true"], [data-selected="true"], [kind$="Active"]) p { color: var(--pap) !important; }
[data-testid="stMain"] [data-baseweb="select"] > div { background: var(--pap); border-radius: 0; }
/* tableaux (HTML) */
.m20-tab { max-width: 100%; overflow: auto; border: 1px solid var(--fil); background: var(--pap); margin-bottom: 8px; }
.m20-tab table { width: 100%; border-collapse: collapse; font-family: 'EB Garamond', serif; font-size: 1rem; color: var(--enc); }
.m20-tab th { position: sticky; top: 0; background: #EFE5CF; font-variant: small-caps; letter-spacing: .8px; font-weight: 600;
  text-align: left; padding: 6px 10px; border-bottom: 2px solid var(--enc); }
.m20-tab td { padding: 5px 10px; border-bottom: 1px dotted var(--fil); font-variant-numeric: lining-nums tabular-nums; }
.m20-tab td:not(:first-child) { white-space: nowrap; }
.m20-tab tr:nth-child(even) td { background: rgba(239,229,207,.35); }
</style>
"""

_TRADING = """
<style>
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500;700&display=swap');
:root { --bg:#0A0E15; --pan:#111723; --pan2:#161D2B; --bd:#232C3D; --tx:#D5DCE8; --mu:#7F8BA3; --am:#F0B90B; --up:#16C784; --dn:#EA3943; --cy:#3BA7FF; }
.stApp, [data-testid="stAppViewContainer"] { background: var(--bg); }
[data-testid="stHeader"] { background: transparent; }
[data-testid="stHeader"] * { color: var(--mu) !important; }
[data-testid="stSidebar"] { background: #0D121C; border-right: 1px solid var(--bd); }
[data-testid="stSidebar"] [data-testid="stLogo"], [data-testid="stSidebarLogo"] { background: #fff; border-radius: 8px; padding: 6px 8px; }
[data-testid="stSidebarNavLink"] span:not([data-testid="stIconMaterial"]) { color: #B7C1D3 !important; }
[data-testid="stSidebarNavLink"]:hover { background: var(--pan2); }
[data-testid="stSidebarNavLink"][aria-current="page"] { background: rgba(240,185,11,.10); box-shadow: inset 3px 0 0 var(--am); }
[data-testid="stSidebarNavLink"][aria-current="page"] span { color: var(--am) !important; }
[data-testid="stSidebar"] [data-testid="stIconMaterial"] { color: var(--mu); }
.m20-etat { background: var(--pan); border-color: var(--bd); color: var(--mu); }
.m20-etat b { color: var(--tx); font-family: 'JetBrains Mono', monospace; }
[data-testid="stMain"], [data-testid="stMain"] p, [data-testid="stMain"] li, [data-testid="stMain"] label,
[data-testid="stMain"] span:not([data-testid="stIconMaterial"]), [data-testid="stMain"] [data-testid="stCaptionContainer"] { font-family: 'IBM Plex Sans', sans-serif; color: var(--tx); }
[data-testid="stIconMaterial"] { font-family: 'Material Symbols Rounded' !important; }
[data-testid="stMain"] [data-testid="stCaptionContainer"] p { color: var(--mu); }
[data-testid="stMain"] strong { color: #fff; }
/* bandeau : barre de terminal */
.m20-banner { background: linear-gradient(90deg, #121A28, #0E1420); border: 1px solid var(--bd); border-left: 4px solid var(--am); box-shadow: 0 0 0 1px rgba(240,185,11,.05), 0 8px 24px rgba(0,0,0,.35); }
.m20-banner img { background: #fff; border-radius: 6px; padding: 4px 8px; height: 40px; }
.m20-banner .m20-sep { background: var(--bd); }
.m20-banner .m20-app { color: var(--mu); font-family: 'JetBrains Mono', monospace; letter-spacing: 2px; }
.m20-banner .m20-app span { color: var(--am); }
.m20-banner .m20-t { color: #fff !important; font-family: 'IBM Plex Sans', sans-serif; }
.m20-banner p { color: var(--mu); }
.m20-banner .m20-date { background: #0A0E15; border: 1px solid var(--bd); color: var(--mu); font-family: 'JetBrains Mono', monospace; }
.m20-banner .m20-date b { color: var(--am); font-family: 'JetBrains Mono', monospace; }
.m20-banner .m20-date:before { content: "● "; color: var(--up); }
.m20-section { color: #fff; border-left: 3px solid var(--am); border-bottom: 1px solid var(--bd); font-family: 'IBM Plex Sans', sans-serif;
  text-transform: uppercase; letter-spacing: 1px; font-size: .9rem; }
.m20-chap { background: var(--pan); border-color: var(--bd); box-shadow: none; }
.m20-chap .num { background: transparent; color: var(--am); border: 1px solid var(--am); box-shadow: none; font-family: 'JetBrains Mono', monospace; }
.m20-chap .t { color: #fff; } .m20-chap .s { color: var(--mu); }
/* chiffres clés : cotation */
.m20-kpi { background: var(--pan); border: 1px solid var(--bd); box-shadow: none; border-radius: 8px; }
.m20-kpi:before { background: var(--bd); width: 3px; }
.m20-kpi.gold:before { background: var(--am); }
.m20-kpi:hover { border-color: #33405A; box-shadow: 0 0 0 1px rgba(240,185,11,.15); }
.m20-kpi .lab { color: var(--mu); font-family: 'JetBrains Mono', monospace; font-size: .66rem; letter-spacing: 1px; }
.m20-kpi .val { color: #fff; font-family: 'JetBrains Mono', monospace; font-weight: 700; font-size: 1.45rem; letter-spacing: -.5px; }
.m20-kpi .sub { color: var(--mu); }
.up { color: var(--up) !important; } .down { color: var(--dn) !important; } .flat { color: var(--mu) !important; }
.m20-note { background: rgba(240,185,11,.08); border-color: rgba(240,185,11,.35); color: #F3D67A; }
.m20-box { background: var(--pan); border-color: var(--bd); border-left-color: var(--am); color: var(--tx); }
[data-testid="stPlotlyChart"] { background: var(--pan); border: 1px solid var(--bd); border-radius: 8px; }
/* contrôles */
[data-testid="stMain"] [data-testid="stWidgetLabel"] p { color: var(--mu) !important; font-size: .8rem; text-transform: uppercase; letter-spacing: .8px; }
[data-testid="stMain"] [data-testid="stButtonGroup"] button { background: var(--pan) !important; border-color: var(--bd) !important; }
[data-testid="stMain"] [data-testid="stButtonGroup"] button p { color: var(--mu) !important; }
[data-testid="stMain"] [data-testid="stButtonGroup"] button:is([aria-checked="true"], [data-selected="true"], [kind$="Active"]) {
  background: rgba(240,185,11,.14) !important; border-color: var(--am) !important; }
[data-testid="stMain"] [data-testid="stButtonGroup"] button:is([aria-checked="true"], [data-selected="true"], [kind$="Active"]) p { color: var(--am) !important; }
[data-testid="stMain"] [data-testid="stPopover"] button, [data-testid="stMain"] [data-testid="stBaseButton-secondary"] {
  background: var(--pan); border-color: var(--bd); color: var(--tx); }
[data-testid="stExpander"] details { background: var(--pan); border-color: var(--bd); }
[data-testid="stExpander"] summary:hover { background: var(--pan2); }
[data-testid="stMain"] [data-baseweb="select"] > div { background: var(--pan); border-color: var(--bd); color: var(--tx); }
[data-testid="stTabs"] button[role="tab"] p { color: var(--mu); }
[data-testid="stTabs"] button[role="tab"][aria-selected="true"] p { color: var(--am); }
[data-testid="stTabs"] [data-baseweb="tab-highlight"] { background-color: var(--am); }
[data-testid="stTabs"] [data-baseweb="tab-border"] { background-color: var(--bd); }
.m20-foot { border-top-color: var(--bd); color: var(--mu); }
.m20-foot span { color: var(--mu) !important; }
/* tableaux (HTML) */
.m20-tab { max-width: 100%; overflow: auto; border: 1px solid var(--bd); border-radius: 8px; background: var(--pan); margin-bottom: 8px; }
.m20-tab table { width: 100%; border-collapse: collapse; font-family: 'JetBrains Mono', monospace; font-size: .8rem; color: var(--tx); }
.m20-tab th { position: sticky; top: 0; background: #0D121C; color: var(--mu); font-weight: 500; text-transform: uppercase;
  letter-spacing: .6px; font-size: .7rem; text-align: right; padding: 7px 10px; border-bottom: 1px solid var(--bd); white-space: nowrap; }
.m20-tab th:first-child, .m20-tab td:first-child { text-align: left; }
.m20-tab td { padding: 6px 10px; border-bottom: 1px solid #1A2130; text-align: right; white-space: nowrap; }
.m20-tab tr:hover td { background: var(--pan2); }
.m20-tab td[style*="#12804A"], .m20-tab td[style*="#12804a"] { color: var(--up) !important; }
.m20-tab td[style*="#C23B3B"], .m20-tab td[style*="#c23b3b"] { color: var(--dn) !important; }
</style>
"""

_BOURSE = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Roboto:wght@400;500;700&family=Roboto+Condensed:wght@500;700&display=swap');
:root { --mar:#0A2B5C; --mar2:#12396F; --or:#F18A00; --fd:#EEF2F7; --tx:#0D1B2E; --mu:#5E6B80; --bd:#D9E0EA; --up:#0E9F59; --dn:#E03B3B; }
.stApp, [data-testid="stAppViewContainer"] { background: var(--fd); }
[data-testid="stHeader"] { background: transparent; }
[data-testid="stMain"] p, [data-testid="stMain"] li, [data-testid="stMain"] label { font-family: 'Roboto', sans-serif; }
[data-testid="stSidebarNavLink"][aria-current="page"] { background: rgba(10,43,92,.08); box-shadow: inset 3px 0 0 var(--or); }
[data-testid="stSidebarNavLink"][aria-current="page"] span { color: var(--mar) !important; }
/* bandeau : en-tête de cotation */
.m20-banner { background: linear-gradient(100deg, var(--mar) 0%, var(--mar2) 70%, #1B4A8A 100%); border: none; border-radius: 6px 6px 0 0;
  margin-bottom: 0; box-shadow: none; border-bottom: 4px solid var(--or); }
.m20-banner img { background: #fff; border-radius: 4px; padding: 4px 8px; height: 40px; }
.m20-banner .m20-sep { background: rgba(255,255,255,.25); }
.m20-banner .m20-app { color: rgba(255,255,255,.7); font-family: 'Roboto Condensed', sans-serif; letter-spacing: 2px; }
.m20-banner .m20-app span { color: var(--or); }
.m20-banner .m20-t { color: #fff !important; font-family: 'Roboto Condensed', sans-serif; font-weight: 700; text-transform: uppercase;
  letter-spacing: .6px; font-size: 1.6rem; }
.m20-banner p { color: rgba(255,255,255,.78); }
.m20-banner .m20-date { background: var(--or); color: rgba(255,255,255,.9); border-radius: 4px; font-family: 'Roboto Condensed', sans-serif;
  text-transform: uppercase; letter-spacing: 1px; }
.m20-banner .m20-date b { color: #fff; }
/* bandeau défilant des cours */
.m20-ticker { background: #061D40; color: #fff; overflow: hidden; white-space: nowrap; border-radius: 0 0 6px 6px; margin-bottom: 18px;
  font-family: 'Roboto Condensed', sans-serif; font-size: .9rem; position: relative; }
.m20-ticker .lbl { position: absolute; left: 0; top: 0; bottom: 0; z-index: 2; background: var(--or); color: #fff; font-weight: 700;
  padding: 8px 14px; letter-spacing: 1px; text-transform: uppercase; font-size: .78rem; display: flex; align-items: center; }
.m20-ticker .rail { display: inline-block; padding: 8px 0 8px 100%; animation: m20defile 90s linear infinite; }
.m20-ticker:hover .rail { animation-play-state: paused; }
.m20-ticker .it { display: inline-block; margin-right: 30px; }
.m20-ticker .it b { color: #fff; font-weight: 700; margin-right: 6px; letter-spacing: .3px; }
.m20-ticker .it .c { color: #C9D6EA; margin-right: 6px; }
.m20-ticker .it .h { color: #3BE08A; } .m20-ticker .it .b { color: #FF6B6B; } .m20-ticker .it .s { color: #C9D6EA; }
@keyframes m20defile { 0% { transform: translateX(0); } 100% { transform: translateX(-100%); } }
/* sections : bandeaux bleus façon tableau de cotation */
.m20-section { background: var(--mar); color: #fff; border: none; border-left: 4px solid var(--or); padding: 7px 12px;
  font-family: 'Roboto Condensed', sans-serif; text-transform: uppercase; letter-spacing: .8px; font-size: .92rem; border-radius: 3px; }
.m20-chap { background: #fff; border: 1px solid var(--bd); border-top: 3px solid var(--mar); border-radius: 4px; box-shadow: none; }
.m20-chap .num { background: var(--or); box-shadow: none; border-radius: 4px; }
.m20-chap .t { color: var(--mar); font-family: 'Roboto Condensed', sans-serif; text-transform: uppercase; letter-spacing: .5px; }
/* chiffres clés : cartes de cotation */
.m20-kpi { border-radius: 4px; border: 1px solid var(--bd); border-top: 3px solid var(--mar); box-shadow: 0 1px 2px rgba(10,43,92,.06); }
.m20-kpi:before { display: none; }
.m20-kpi.gold { border-top-color: var(--or); }
.m20-kpi .lab { font-family: 'Roboto Condensed', sans-serif; color: var(--mar); font-size: .74rem; letter-spacing: .8px; }
.m20-kpi .val { font-family: 'Roboto', sans-serif; color: var(--tx); font-variant-numeric: tabular-nums; }
.up { color: var(--up) !important; } .down { color: var(--dn) !important; }
.m20-box { border-left-color: var(--or); background: #FFF6EA; border-color: #F6D9AE; }
[data-testid="stPlotlyChart"], [data-testid="stDataFrame"] { border-radius: 4px; border-color: var(--bd); }
[data-testid="stTabs"] button[role="tab"] p { font-family: 'Roboto Condensed', sans-serif; text-transform: uppercase; letter-spacing: .6px; font-size: .9rem; }
[data-testid="stTabs"] button[role="tab"][aria-selected="true"] p { color: var(--mar); }
[data-testid="stTabs"] [data-baseweb="tab-highlight"] { background-color: var(--or); }
[data-testid="stMain"] [data-testid="stButtonGroup"] button:is([aria-checked="true"], [data-selected="true"], [kind$="Active"]) {
  background: var(--mar) !important; border-color: var(--mar) !important; }
[data-testid="stMain"] [data-testid="stButtonGroup"] button:is([aria-checked="true"], [data-selected="true"], [kind$="Active"]) p { color: #fff !important; }
[data-testid="stBaseButton-primary"] { background: var(--or); border-color: var(--or); }
</style>
"""
