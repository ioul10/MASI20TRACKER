"""Habillage de l'application : thème, en-têtes, cartes et accès aux données."""
from __future__ import annotations

import pandas as pd
import streamlit as st

from . import config as C
from . import store
from .fmt import date_courte

CSS = f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
html, body, [class*="css"], .stMarkdown, .stDataFrame {{ font-family: 'Inter', sans-serif; }}
.block-container {{ padding-top: 3rem; padding-bottom: 3rem; max-width: 1420px; }}
/* Menu latéral clair : le logo de l'entreprise s'y affiche sur fond blanc */
[data-testid="stSidebar"] {{ background: #FFFFFF; border-right: 1px solid {C.GRID}; }}
[data-testid="stSidebarNavLink"] {{ border-radius: 8px; margin: 1px 0; }}
[data-testid="stSidebarNavLink"] span {{ color: {C.INK}; font-weight: 500; }}
[data-testid="stSidebarNavLink"]:hover {{ background: {C.BG}; }}
[data-testid="stSidebarNavLink"][aria-current="page"] {{ background: {C.NAVY}14; box-shadow: inset 3px 0 0 {C.GOLD}; }}
[data-testid="stSidebarNavLink"][aria-current="page"] span {{ color: {C.NAVY}; font-weight: 700; }}
[data-testid="stNavSectionHeader"], [data-testid="stSidebarNavSeparator"] + div span {{ color: {C.MUTED} !important;
  text-transform: uppercase; letter-spacing: .8px; font-size: .72rem !important; font-weight: 600; }}
[data-testid="stLogo"] {{ height: 3rem; max-width: 100%; }}
/* En-tête de page */
.m20-banner {{ background: #FFFFFF; border: 1px solid {C.GRID}; border-radius: 14px; padding: 16px 22px;
  margin-bottom: 18px; display:flex; justify-content:space-between; align-items:center; gap: 18px; flex-wrap: wrap;
  box-shadow: 0 1px 2px rgba(16,24,40,.04); border-left: 6px solid {C.NAVY}; }}
.m20-banner .m20-g {{ display:flex; align-items:center; gap: 18px; }}
.m20-banner img {{ height: 46px; width: auto; }}
.m20-banner .m20-sep {{ width:1px; height: 44px; background: {C.GRID}; }}
.m20-banner .m20-app {{ font-size: .74rem; font-weight: 700; letter-spacing: 1.2px; color: {C.MUTED}; text-transform: uppercase; }}
.m20-banner .m20-app span {{ color: {C.GOLD}; }}
.m20-banner .m20-t {{ font-size: 1.5rem; font-weight: 700; color: {C.NAVY} !important; line-height: 1.2; margin-top: 1px; }}
.m20-banner p {{ margin: 3px 0 0; color: {C.MUTED}; font-size: .88rem; }}
.m20-banner .m20-date {{ text-align:right; font-size:.78rem; color:{C.MUTED}; background:{C.BG}; border-radius:10px; padding: 8px 14px; }}
.m20-banner .m20-date b {{ color:{C.NAVY}; font-size: 1.05rem; display:block; }}
/* Titres de section */
.m20-section {{ color: {C.NAVY}; font-weight: 700; font-size: 1rem; margin: 26px 0 10px; padding: 2px 0 6px 12px;
  border-left: 4px solid {C.GOLD}; border-bottom: 1px solid {C.GRID}; }}
/* Cartes de chiffres clés */
.m20-kpis {{ display:grid; grid-template-columns: repeat(auto-fit, minmax(175px, 1fr)); gap: 12px; margin: 4px 0 10px; }}
.m20-kpi {{ background: {C.CARD}; border: 1px solid {C.GRID}; border-radius: 12px; padding: 13px 15px;
  box-shadow: 0 1px 2px rgba(16,24,40,.04); position: relative; overflow: hidden; }}
.m20-kpi:before {{ content:""; position:absolute; left:0; top:0; bottom:0; width:4px; background:{C.NAVY}; }}
.m20-kpi.gold:before {{ background:{C.GOLD}; }}
.m20-kpi .lab {{ font-size: .7rem; text-transform: uppercase; letter-spacing: .7px; color: {C.MUTED}; font-weight:600; }}
.m20-kpi .val {{ font-size: 1.42rem; font-weight: 700; color: {C.INK}; margin-top: 3px; line-height:1.2; }}
.m20-kpi .sub {{ font-size: .8rem; color: {C.MUTED}; margin-top: 3px; }}
.up {{ color: {C.UP} !important; }} .down {{ color: {C.DOWN} !important; }} .flat {{ color: {C.MUTED} !important; }}
.m20-note {{ background: #FFF8E6; border: 1px solid #F0DCA0; border-radius: 10px; padding: 9px 13px;
  font-size: .85rem; color: #5C4A12; margin: 6px 0 10px; }}
.m20-pill {{ display:inline-block; padding: 2px 10px; border-radius: 999px; font-size: .78rem; font-weight:600; }}
.m20-pill.up {{ background:#E3F4EA; }} .m20-pill.down {{ background:#FBE6E6; }} .m20-pill.flat {{ background:#EEF0F4; }}
.m20-foot {{ color:{C.MUTED}; font-size:.75rem; margin-top: 34px; border-top:1px solid {C.GRID}; padding-top:10px;
  display:flex; justify-content:space-between; gap: 12px; flex-wrap: wrap; }}
[data-testid="stPlotlyChart"], [data-testid="stDataFrame"] {{ background:#fff; border:1px solid {C.GRID}; border-radius:12px; padding: 6px; }}
div[data-testid="stMetric"] {{ background:{C.CARD}; border:1px solid {C.GRID}; border-radius:12px; padding:10px 14px; }}
</style>
"""


def page(titre: str, sous_titre: str = "", date_ref=None) -> None:
    from . import brand
    st.markdown(CSS, unsafe_allow_html=True)
    logo = brand.logo_data_uri()
    gauche = (f"<img src='{logo}' alt='{C.NOM_ENTREPRISE}'><div class='m20-sep'></div>" if logo else "")
    droite = f"<div class='m20-date'>Dernière séance<b>{date_courte(date_ref)}</b></div>" if date_ref is not None else ""
    st.markdown(f"<div class='m20-banner'><div class='m20-g'>{gauche}<div>"
                f"<div class='m20-app'>MASI<span>20</span>TRACKER · {C.NOM_ENTREPRISE}</div>"
                f"<div class='m20-t'>{titre}</div><p>{sous_titre or C.SOUS_TITRE}</p></div></div>{droite}</div>",
                unsafe_allow_html=True)


def section(titre: str) -> None:
    st.markdown(f"<div class='m20-section'>{titre}</div>", unsafe_allow_html=True)


def note(texte: str) -> None:
    st.markdown(f"<div class='m20-note'>{texte}</div>", unsafe_allow_html=True)


def classe(x) -> str:
    if x is None or pd.isna(x) or x == 0:
        return "flat"
    return "up" if x > 0 else "down"


def kpis(items: list[dict]) -> None:
    """items : {lab, val, sub, sens (valeur signée pour la couleur du sous-titre), gold}"""
    html = "<div class='m20-kpis'>"
    for it in items:
        cls = classe(it.get("sens")) if "sens" in it else ""
        html += (f"<div class='m20-kpi {'gold' if it.get('gold') else ''}'><div class='lab'>{it['lab']}</div>"
                 f"<div class='val'>{it['val']}</div><div class='sub {cls}'>{it.get('sub', '')}</div></div>")
    st.markdown(html + "</div>", unsafe_allow_html=True)


def pied() -> None:
    st.markdown(f"<div class='m20-foot'><span>MASI20TRACKER · {C.NOM_ENTREPRISE} – {C.SERVICE} · usage interne</span>"
                "<span>Source : bulletins officiels de la Bourse de Casablanca. Ne constitue pas un conseil en investissement."
                "</span></div>", unsafe_allow_html=True)


# ------------------------------------------------------------- données
def _empreinte() -> tuple:
    return tuple((p.name, p.stat().st_mtime) for p in sorted(store.DATA.glob("*.csv")))


@st.cache_data(show_spinner=False)
def _charger(_empreinte_):
    from .hebdo import charger
    return charger()


def db() -> dict:
    return _charger(_empreinte())


def vider_cache() -> None:
    _charger.clear()


def couleur_var(v) -> str:
    return C.UP if v > 0 else C.DOWN if v < 0 else C.NEUTRE


def style_table(df: pd.DataFrame, pct_cols=(), signe_cols=(), fmt=None):
    """Mise en forme d'un tableau : % en vert/rouge, formats français."""
    from .fmt import nombre, pct
    fmt = dict(fmt or {})
    df = df.copy()
    for c in set(fmt) | set(pct_cols) | set(signe_cols):
        if c in df.columns and df[c].dtype == object:
            try:
                df[c] = pd.to_numeric(df[c])
            except (ValueError, TypeError):
                pass
    for c in pct_cols:
        fmt.setdefault(c, lambda v: pct(v))
    sty = df.style.format(fmt, na_rep="–")

    def col(v):
        if v is None or pd.isna(v) or not isinstance(v, (int, float)):
            return ""
        return f"color: {C.UP}; font-weight:600" if v > 0 else f"color: {C.DOWN}; font-weight:600" if v < 0 else ""
    cols = [c for c in list(pct_cols) + list(signe_cols) if c in df.columns]
    if cols:
        sty = sty.map(col, subset=cols)
    return sty.hide(axis="index")
