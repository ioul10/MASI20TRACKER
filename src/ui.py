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
.block-container {{ padding-top: 1.2rem; padding-bottom: 3rem; max-width: 1400px; }}
[data-testid="stSidebar"] {{ background: {C.NAVY}; }}
[data-testid="stSidebar"] * {{ color: #E8ECF4 !important; }}
[data-testid="stSidebar"] [data-testid="stSidebarNavLink"][aria-current="page"] {{ background: rgba(201,162,39,.18); border-left: 3px solid {C.GOLD}; }}
[data-testid="stSidebarNavSeparator"] {{ border-color: rgba(255,255,255,.15); }}
.m20-banner {{ background: linear-gradient(100deg, {C.NAVY} 0%, {C.NAVY_2} 100%); color: #fff;
  border-radius: 14px; padding: 18px 26px; margin-bottom: 18px; border-bottom: 4px solid {C.GOLD};
  display:flex; justify-content:space-between; align-items:center; gap: 16px; flex-wrap: wrap; }}
.m20-banner .m20-t {{ font-size: 1.55rem; margin: 0; padding: 0; letter-spacing: .5px; color:#fff !important; font-weight:700; }}
.m20-banner .m20-t span {{ color: {C.GOLD} !important; }}
.m20-banner p {{ margin: 2px 0 0; color: #C9D3E6; font-size: .9rem; }}
.m20-banner .m20-date {{ text-align:right; font-size:.85rem; color:#C9D3E6; }}
.m20-banner .m20-date b {{ color:#fff; font-size: 1.05rem; }}
.m20-section {{ background: {C.NAVY}; color: #fff; padding: 7px 14px; border-radius: 6px;
  font-weight: 600; font-size: .95rem; margin: 22px 0 10px; border-left: 4px solid {C.GOLD}; }}
.m20-kpis {{ display:grid; grid-template-columns: repeat(auto-fit, minmax(170px, 1fr)); gap: 12px; margin: 4px 0 8px; }}
.m20-kpi {{ background: {C.CARD}; border: 1px solid {C.GRID}; border-top: 3px solid {C.NAVY};
  border-radius: 10px; padding: 12px 14px; }}
.m20-kpi .lab {{ font-size: .72rem; text-transform: uppercase; letter-spacing: .6px; color: {C.MUTED}; font-weight:600; }}
.m20-kpi .val {{ font-size: 1.45rem; font-weight: 700; color: {C.INK}; margin-top: 2px; line-height:1.2; }}
.m20-kpi .sub {{ font-size: .8rem; color: {C.MUTED}; margin-top: 2px; }}
.m20-kpi.gold {{ border-top-color: {C.GOLD}; }}
.up {{ color: {C.UP} !important; }} .down {{ color: {C.DOWN} !important; }} .flat {{ color: {C.MUTED} !important; }}
.m20-note {{ background: #FFF8E6; border: 1px solid #F0DCA0; border-radius: 8px; padding: 9px 13px;
  font-size: .85rem; color: #5C4A12; margin: 6px 0 10px; }}
.m20-avis {{ background: #EEF2F9; border-left: 4px solid {C.NAVY}; border-radius: 8px; padding: 12px 16px; font-size: .93rem; }}
.m20-pill {{ display:inline-block; padding: 2px 10px; border-radius: 999px; font-size: .78rem; font-weight:600; }}
.m20-pill.up {{ background:#E3F4EA; }} .m20-pill.down {{ background:#FBE6E6; }} .m20-pill.flat {{ background:#EEF0F4; }}
.m20-foot {{ color:{C.MUTED}; font-size:.75rem; margin-top: 30px; border-top:1px solid {C.GRID}; padding-top:8px; }}
div[data-testid="stMetric"] {{ background:{C.CARD}; border:1px solid {C.GRID}; border-radius:10px; padding:10px 14px; }}
</style>
"""


def page(titre: str, sous_titre: str = "", date_ref=None) -> None:
    st.markdown(CSS, unsafe_allow_html=True)
    droite = f"<div class='m20-date'>Dernière séance<br><b>{date_courte(date_ref)}</b></div>" if date_ref is not None else ""
    st.markdown(f"<div class='m20-banner'><div><div class='m20-t'>MASI<span>20</span>TRACKER · {titre}</div>"
                f"<p>{sous_titre or C.SOUS_TITRE}</p></div>{droite}</div>", unsafe_allow_html=True)


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
    st.markdown("<div class='m20-foot'>Source : bulletins officiels de la Bourse de Casablanca (cote et marché à terme). "
                "Outil d'analyse interne, non affilié à la Bourse de Casablanca. Ne constitue pas un conseil en investissement."
                "</div>", unsafe_allow_html=True)


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
