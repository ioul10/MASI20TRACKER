"""Graphiques Plotly de MASI20TRACKER (un seul axe par graphique :
deux mesures d'échelles différentes vont dans deux panneaux superposés)."""
from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from . import config as C
from . import futures as F
from .fmt import jour, nombre

FONT = "Inter, Segoe UI, Arial, sans-serif"
CFG = {"displayModeBar": False, "locale": "fr"}


def _layout(fig: go.Figure, h: int = 420, legende: bool = True, **kw) -> go.Figure:
    kw.setdefault("hovermode", "x unified")
    fig.update_layout(
        height=h, margin=dict(l=10, r=10, t=36 if kw.get("title") else 14, b=10),
        paper_bgcolor="white", plot_bgcolor="white", font=dict(family=FONT, size=12, color=C.INK),
        showlegend=legende, separators=", ",
        legend=dict(orientation="h", yanchor="bottom", y=1.01, xanchor="left", x=0, bgcolor="rgba(0,0,0,0)"),
        hoverlabel=dict(bgcolor="white", bordercolor=C.GRID, font=dict(family=FONT, color=C.INK)), **kw)
    fig.update_xaxes(showgrid=False, linecolor=C.GRID, tickfont=dict(color=C.MUTED))
    fig.update_yaxes(gridcolor=C.GRID, zeroline=False, linecolor=C.GRID, tickfont=dict(color=C.MUTED),
                     tickformat=",.0f")
    return fig


def _jours_sans_seance(dates: pd.Series) -> list:
    """Masque week-ends et jours fériés sur l'axe des dates."""
    d = pd.to_datetime(dates)
    tous = pd.date_range(d.min(), d.max(), freq="D")
    return [x.strftime("%Y-%m-%d") for x in tous.difference(d)]


# ------------------------------------------------------------------ indice
def indice(tech: pd.DataFrame, ema=True, bollinger=False, fib: dict | None = None, rsi=True, h=560) -> go.Figure:
    t = tech
    rows = 2 if rsi else 1
    fig = make_subplots(rows=rows, cols=1, shared_xaxes=True, vertical_spacing=0.04,
                        row_heights=[0.74, 0.26] if rsi else [1])
    ohlc = t["plus_haut"].notna() & t["plus_bas"].notna() if "plus_haut" in t else pd.Series(False, index=t.index)
    if ohlc.mean() > 0.8:
        o = t["cloture"].shift().fillna(t["cloture"])
        fig.add_trace(go.Candlestick(x=t["date"], open=o, high=t["plus_haut"].fillna(t["cloture"]),
                                     low=t["plus_bas"].fillna(t["cloture"]), close=t["cloture"], name="MASI 20",
                                     increasing=dict(line=dict(color=C.UP, width=1), fillcolor=C.UP),
                                     decreasing=dict(line=dict(color=C.DOWN, width=1), fillcolor=C.DOWN)), 1, 1)
    else:
        fig.add_trace(go.Scatter(x=t["date"], y=t["cloture"], name="MASI 20", line=dict(color=C.NAVY, width=2)), 1, 1)
    if bollinger:
        fig.add_trace(go.Scatter(x=t["date"], y=t["bb_haut"], name="Bollinger", line=dict(color="#9AA7BD", width=1),
                                 hoverinfo="skip"), 1, 1)
        fig.add_trace(go.Scatter(x=t["date"], y=t["bb_bas"], name="Bollinger bas", line=dict(color="#9AA7BD", width=1),
                                 fill="tonexty", fillcolor="rgba(154,167,189,.12)", showlegend=False, hoverinfo="skip"), 1, 1)
    if ema:
        fig.add_trace(go.Scatter(x=t["date"], y=t["ema20"], name="EMA 20", line=dict(color=C.GOLD, width=1.6)), 1, 1)
        fig.add_trace(go.Scatter(x=t["date"], y=t["ema40"], name="EMA 40", line=dict(color=C.SERIES[3], width=1.6)), 1, 1)
    if fib:
        for r, v in fib["niveaux"].items():
            fig.add_hline(y=v, line=dict(color="#B8A15A", width=1, dash="dot"), row=1, col=1,
                          annotation_text=f"Fibo {r * 100:.1f} % · {nombre(v, 0)}".replace(".", ","),
                          annotation_position="right", annotation_font=dict(size=10, color="#8C7A3C"))
    if rsi:
        fig.add_trace(go.Scatter(x=t["date"], y=t["rsi14"], name="RSI 14", line=dict(color=C.NAVY_2, width=1.6),
                                 showlegend=False), 2, 1)
        for y, c in ((70, C.DOWN), (30, C.UP)):
            fig.add_hline(y=y, line=dict(color=c, width=1, dash="dash"), row=2, col=1)
        fig.update_yaxes(range=[0, 100], tickvals=[30, 50, 70], title_text="RSI", row=2, col=1)
    fig.update_xaxes(rangeslider_visible=False, rangebreaks=[dict(values=_jours_sans_seance(t["date"]))])
    return _layout(fig, h)


# ------------------------------------------------- indice & technique (v2)
COULEURS_MM = {5: "#D98A1E", 10: "#1BA37A", 20: "#6250D6", 40: "#C2477A"}


def _axes_dates(fig, dates):
    fig.update_xaxes(rangeslider_visible=False, rangebreaks=[dict(values=_jours_sans_seance(dates))])


def _trace_indice(t, bougies=False, largeur=2.0):
    """Le MASI 20 en courbe (clôtures) ou en chandeliers.
    Le bulletin ne donne pas d'ouverture : elle est prise égale à la clôture de la veille.
    Plus haut / plus bas absents : remplacés par le max / min de l'ouverture et de la clôture."""
    if not bougies:
        return go.Scatter(x=t["date"], y=t["cloture"], name="MASI 20", line=dict(color=C.NAVY, width=largeur),
                          hovertemplate="%{y:,.2f}")
    o = t["ouverture"] if "ouverture" in t else t["cloture"].shift()
    o = o.fillna(t["cloture"])
    hi = pd.concat([t["plus_haut"].astype(float), o, t["cloture"]], axis=1).max(axis=1)
    lo = pd.concat([t["plus_bas"].astype(float), o, t["cloture"]], axis=1).min(axis=1)
    return go.Candlestick(x=t["date"], open=o, high=hi, low=lo, close=t["cloture"], name="MASI 20",
                          increasing=dict(line=dict(color=C.UP, width=1), fillcolor=C.UP),
                          decreasing=dict(line=dict(color=C.DOWN, width=1), fillcolor=C.DOWN))


def _ligne_indice(fig, t, secondaire=True, bougies=False):
    """Le MASI 20 sur l'axe de droite (comme dans l'Excel), en courbe ou en chandeliers."""
    fig.add_trace(_trace_indice(t, bougies), secondary_y=secondaire)
    fig.update_yaxes(title_text="MASI 20 (pts)", showgrid=False, secondary_y=True, tickformat=",.0f")


def indice_moyennes(t: pd.DataFrame, periodes=(5, 10, 20, 40), prefixe="mm", h=470, bougies=False) -> go.Figure:
    """MASI 20 (courbe ou chandeliers) et ses moyennes mobiles 5, 10, 20, 40."""
    fig = go.Figure()
    fig.add_trace(_trace_indice(t, bougies, 2.6))
    lib = "MM" if prefixe == "mm" else "EMA"
    for n in periodes:
        fig.add_trace(go.Scatter(x=t["date"], y=t[f"{prefixe}{n}"], name=f"{lib} {n}",
                                 line=dict(color=COULEURS_MM[n], width=1.5), hovertemplate="%{y:,.2f}"))
    _axes_dates(fig, t["date"])
    return _layout(fig, h)


def rsi_barres(t: pd.DataFrame, n=14, h=420, bougies=False) -> go.Figure:
    """RSI en barres (couleur = zone), seuils 30 / 50 / 70, MASI 20 en ligne."""
    col = f"rsi{n}"
    v = t[col]
    couleurs = np.select([v >= 70, v >= 50, v > 30], ["#C23B3B", "#7FA7D9", "#B8C2D3"], "#12804A")
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    for y0, y1, c in ((70, 100, "rgba(194,59,59,.07)"), (0, 30, "rgba(18,128,74,.07)")):
        fig.add_hrect(y0=y0, y1=y1, fillcolor=c, line_width=0, layer="below")
    fig.add_trace(go.Bar(x=t["date"], y=v, name=f"RSI {n}", marker_color=couleurs, hovertemplate="%{y:.0f}"),
                  secondary_y=False)
    _ligne_indice(fig, t, bougies=bougies)
    for y, c, lab in ((70, C.DOWN, "70 · surachat"), (50, C.MUTED, "50"), (30, C.UP, "30 · survente")):
        fig.add_hline(y=y, line=dict(color=c, width=1, dash="dash"), annotation_text=lab,
                      annotation_position="top left", annotation_font=dict(size=10, color=c))
    fig.update_yaxes(range=[0, 100], tickvals=[0, 30, 50, 70, 100], title_text=f"RSI {n}", secondary_y=False)
    _axes_dates(fig, t["date"])
    fig = _layout(fig, h)
    fig.update_layout(bargap=0.15)
    fig.update_yaxes(tickformat=".0f", secondary_y=False)
    return fig


def atr_barres(t: pd.DataFrame, n=14, h=420, bougies=False) -> go.Figure:
    """ATR en barres (points d'indice), MASI 20 en ligne. Barres pâles = haut/bas absents (ATR estimé)."""
    col = f"atr{n}"
    estime = ~t["hl_connu"] if "hl_connu" in t else pd.Series(False, index=t.index)
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    fig.add_trace(go.Bar(x=t["date"], y=t[col], name=f"ATR {n} (pts)",
                         marker_color=np.where(estime, "#C9D3E6", "#5B7DB1"),
                         customdata=np.c_[t[f"{col}_pct"] * 100, np.where(estime, "estimé (haut/bas absents)", "")],
                         hovertemplate="%{y:,.1f} pts · %{customdata[0]:.2f} % %{customdata[1]}"), secondary_y=False)
    med = t[col].median()
    if pd.notna(med):
        fig.add_trace(go.Scatter(x=t["date"], y=[med] * len(t), name=f"Médiane de la période ({nombre(med, 1)} pts)",
                                 mode="lines", line=dict(color=C.GOLD, width=1.4, dash="dash"), hoverinfo="skip"),
                      secondary_y=False)
    _ligne_indice(fig, t, bougies=bougies)
    fig.update_yaxes(title_text=f"ATR {n} (pts)", secondary_y=False, rangemode="tozero")
    _axes_dates(fig, t["date"])
    fig = _layout(fig, h)
    fig.update_layout(bargap=0.15)
    fig.update_yaxes(tickformat=",.0f", secondary_y=False)
    return fig


def var5_barres(t: pd.DataFrame, seuil=0.03, h=420, bougies=False) -> go.Figure:
    """Variation sur 5 séances en barres, bande ±3 %, MASI 20 en ligne."""
    v = t["var_5j"] * 100
    s = seuil * 100
    couleurs = np.select([v >= s, v <= -s], [C.UP, C.DOWN], "#B8C2D3")
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    fig.add_hrect(y0=-s, y1=s, fillcolor="rgba(138,148,166,.10)", line_width=0, layer="below")
    fig.add_trace(go.Bar(x=t["date"], y=v, name="Variation 5 séances", marker_color=couleurs,
                         hovertemplate="%{y:+.2f} %"), secondary_y=False)
    for y, c, lab in ((s, C.UP, f"+{s:.0f} % · BOOM"), (-s, C.DOWN, f"−{s:.0f} % · SLUMP")):
        fig.add_hline(y=y, line=dict(color=c, width=1, dash="dash"), annotation_text=lab,
                      annotation_position="top left" if y > 0 else "bottom left", annotation_font=dict(size=10, color=c))
    _ligne_indice(fig, t, bougies=bougies)
    m = max(float(v.abs().max()) if v.notna().any() else 0, s) * 1.15
    fig.update_yaxes(range=[-m, m], title_text="Variation 5 séances (%)", secondary_y=False)
    _axes_dates(fig, t["date"])
    fig = _layout(fig, h)
    fig.update_layout(bargap=0.15)
    fig.update_yaxes(tickformat="+.0f", ticksuffix=" %", secondary_y=False)
    return fig


def volumes_evolution(v: pd.DataFrame, m20: pd.DataFrame | None = None, h=440) -> go.Figure:
    """Volume (marché central) par séance ou par semaine : courant + grosses transactions,
    moyenne mobile, MASI 20 en ligne. Axe en catégories : seules les séances importées apparaissent."""
    hebdo = v.attrs.get("hebdo", False)
    x = [("sem. " if hebdo else "") + d.strftime("%d/%m/%y") for d in v["date"]]
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    fig.add_trace(go.Bar(x=x, y=(v["volume"] - v["volume_gros"]) / 1e6, name="Volume courant",
                         marker_color="#5B7DB1", hovertemplate="%{y:,.1f} M MAD"), secondary_y=False)
    fig.add_trace(go.Bar(x=x, y=v["volume_gros"] / 1e6, name="Grosses transactions (≥ 5 M MAD)",
                         marker_color=C.GOLD, hovertemplate="%{y:,.1f} M MAD"), secondary_y=False)
    if "moyenne" in v:
        fig.add_trace(go.Scatter(x=x, y=v["moyenne"] / 1e6, name=v.attrs.get("lib_moyenne", "Moyenne"),
                                 line=dict(color=C.INK, width=1.6, dash="dot"), hovertemplate="%{y:,.1f} M MAD"),
                      secondary_y=False)
    if m20 is not None and not m20.empty:
        s = m20.set_index("date")["cloture"].sort_index()
        if hebdo:
            s = s.resample("W-FRI").last()
        y = s.reindex(v["date"]).values
        fig.add_trace(go.Scatter(x=x, y=y, name="MASI 20", mode="lines+markers", line=dict(color=C.NAVY, width=2),
                                 marker=dict(size=5), hovertemplate="%{y:,.2f}"), secondary_y=True)
        fig.update_yaxes(title_text="MASI 20 (pts)", showgrid=False, secondary_y=True)
    fig.update_layout(barmode="stack", bargap=0.25)
    fig.update_yaxes(title_text="Volume (M MAD)", secondary_y=False, rangemode="tozero")
    fig = _layout(fig, h)
    fig.update_xaxes(type="category")
    fig.update_yaxes(tickformat=",.0f")
    return fig


def bougies_hebdo(w: pd.DataFrame, h=320) -> go.Figure:
    fig = go.Figure(go.Candlestick(x=w["date"], open=w["ouverture"], high=w["plus_haut"], low=w["plus_bas"],
                                   close=w["cloture"], name="Semaine",
                                   increasing=dict(line=dict(color=C.UP), fillcolor=C.UP),
                                   decreasing=dict(line=dict(color=C.DOWN), fillcolor=C.DOWN)))
    fig.update_xaxes(rangeslider_visible=False)
    return _layout(fig, h, legende=False)


def semaine_indice_volume(o: dict, h=430) -> go.Figure:
    """Haut : MASI 20 séance par séance avec la variation du jour.
    Bas : volume du marché central, total et valeurs du MASI 20."""
    j = o["jours"]
    v = o.get("volumes_jour")
    rows = 2 if v is not None and len(v) else 1
    fig = make_subplots(rows=rows, cols=1, shared_xaxes=True, vertical_spacing=0.08,
                        row_heights=[0.55, 0.45] if rows == 2 else [1],
                        subplot_titles=("MASI 20 (pts)", "Volume du marché central (M MAD)") if rows == 2 else None)
    x = [jour(d) for d in j["date"]]
    fig.add_trace(go.Scatter(x=x, y=j["cloture"], mode="lines+markers+text", name="MASI 20",
                             line=dict(color=C.GOLD, width=3), marker=dict(size=9, color=C.GOLD),
                             text=[f"{v * 100:+.2f} %".replace(".", ",") if pd.notna(v) else "" for v in j["var"]],
                             textposition="top center", textfont=dict(size=11, color=C.INK)), 1, 1)
    if rows == 2:
        vv = v.set_index("date").reindex(j["date"]).fillna(0)
        fig.add_trace(go.Bar(x=x, y=vv["marche"] / 1e6, name="Marché total", marker_color="#D8DEEA"), 2, 1)
        fig.add_trace(go.Bar(x=x, y=vv["masi20"] / 1e6, name="Valeurs du MASI 20", marker_color=C.NAVY), 2, 1)
        fig.update_layout(barmode="overlay", bargap=0.35)
    fig.update_yaxes(tickformat=",.0f")
    fig = _layout(fig, h, hovermode="x unified")
    fig.update_layout(legend=dict(orientation="h", yanchor="top", y=-0.08, xanchor="left", x=0))
    fig.update_annotations(font=dict(size=12, color=C.MUTED), x=0, xanchor="left")
    fig.update_yaxes(range=[j["cloture"].min() - (j["cloture"].max() - j["cloture"].min()) * 0.35 - 2,
                            j["cloture"].max() + (j["cloture"].max() - j["cloture"].min()) * 0.35 + 2], row=1, col=1)
    return fig


# --------------------------------------------------------------- composants
def contributions(b: pd.DataFrame, h=None) -> go.Figure:
    d = b.sort_values("contribution_pb")
    plein = d.get("tendance_volume", pd.Series(np.nan, index=d.index)).fillna(1) >= 1
    col = [(C.UP if c >= 0 else C.DOWN) if p else ("#9BD3B4" if c >= 0 else "#EBA9A9")
           for c, p in zip(d["contribution_pb"], plein)]
    fig = go.Figure(go.Bar(y=d["nom"], x=d["contribution_pb"], orientation="h", marker_color=col,
                           customdata=np.c_[d["rendement"] * 100, d["poids"] * 100],
                           hovertemplate="<b>%{y}</b><br>Contribution : %{x:+.1f} pb<br>Variation : %{customdata[0]:+.2f} %"
                                         "<br>Poids : %{customdata[1]:.1f} %<extra></extra>"))
    fig.add_vline(x=0, line=dict(color=C.MUTED, width=1))
    fig = _layout(fig, h or 26 * len(d) + 60, legende=False, hovermode="closest")
    fig.update_xaxes(title_text="Contribution (pb) · pâle = volume en baisse", title_standoff=6, tickformat="+,.0f",
                     showgrid=True, gridcolor=C.GRID)
    fig.update_yaxes(showgrid=False)
    return fig


def volume_poids(b: pd.DataFrame, h=430) -> go.Figure:
    x, y = b["poids"] * 100, b["part_volume"] * 100
    m = max(x.max(), y.max()) * 1.1
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=[0, m], y=[0, m], mode="lines", line=dict(color=C.GRID, dash="dash"), hoverinfo="skip",
                             showlegend=False))
    lab = [n.title() if (pv >= 0.05 or pw >= 0.08) else "" for n, pv, pw in zip(b["nom"], b["part_volume"], b["poids"])]
    fig.add_trace(go.Scatter(x=x, y=y, mode="markers+text", text=lab, textposition="top center",
                             customdata=b["nom"].str.title(),
                             textfont=dict(size=10, color=C.INK), cliponaxis=False,
                             marker=dict(size=11, color=[C.UP if r >= 0 else C.DOWN for r in b["rendement"]],
                                         line=dict(color="white", width=2)),
                             hovertemplate="<b>%{customdata}</b><br>Poids : %{x:.1f} %<br>Part du volume : %{y:.1f} %<extra></extra>"))
    fig.add_annotation(x=m * 0.03, y=m * 0.95, text="Plus de volume que de poids", showarrow=False, xanchor="left",
                       font=dict(color=C.MUTED, size=11))
    fig.add_annotation(x=m * 0.97, y=m * 0.05, text="Moins de volume que de poids", showarrow=False, xanchor="right",
                       font=dict(color=C.MUTED, size=11))
    fig = _layout(fig, h, legende=False, hovermode="closest")
    fig.update_xaxes(title_text="Poids dans l'indice (%)", range=[0, m], showgrid=True, gridcolor=C.GRID, tickformat=",.0f")
    fig.update_yaxes(title_text="Part du volume de l'indice (%)", range=[0, m])
    return fig


def carte_composants(df: pd.DataFrame, taille="poids", h=520) -> go.Figure:
    """Carte des valeurs regroupées par secteur : surface = poids, couleur = variation."""
    d = df.copy()
    d["var_pct"] = d["rendement"] * 100
    sect = d.groupby("secteur").apply(lambda g: pd.Series({
        "taille": g[taille].sum(),
        "var_pct": np.average(g["var_pct"].fillna(0), weights=g[taille]) if g[taille].sum() else 0}),
        include_groups=False)
    tot = float(sect["taille"].sum())
    labels = ["MASI 20"] + list(sect.index) + list(d["nom"])
    ids = ["ROOT"] + ["S:" + s for s in sect.index] + list(d["isin"])
    parents = [""] + ["ROOT"] * len(sect) + ["S:" + s for s in d["secteur"]]
    values = [tot] + list(sect["taille"]) + list(d[taille])
    colors = [0.0] + list(sect["var_pct"]) + list(d["var_pct"].fillna(0))
    lim = max(3.0, float(d["var_pct"].abs().quantile(0.95)))
    fig = go.Figure(go.Treemap(
        ids=ids, labels=labels, parents=parents, values=values, branchvalues="total", maxdepth=3,
        customdata=colors, marker=dict(colors=colors, colorscale=[[0, C.DOWN], [0.5, "#E9ECF2"], [1, C.UP]],
                                       cmin=-lim, cmax=lim, line=dict(color="white", width=2),
                                       colorbar=dict(title="Var.", ticksuffix=" %", thickness=12)),
        texttemplate="<b>%{label}</b><br>%{customdata:+.2f} %", tiling=dict(pad=2),
        hovertemplate="<b>%{label}</b><br>Variation : %{customdata:+.2f} %<extra></extra>"))
    fig.update_layout(height=h, margin=dict(l=0, r=0, t=6, b=0), font=dict(family=FONT), separators=", ")
    return fig


# ------------------------------------------------------------------ futures
def futures_cours(f: pd.DataFrame, spot: pd.DataFrame | None = None, col="cloture", h=430) -> go.Figure:
    fig = go.Figure()
    if spot is not None and not spot.empty:
        s = spot[(spot["date"] >= f["date"].min()) & (spot["date"] <= f["date"].max())]
        fig.add_trace(go.Scatter(x=s["date"], y=s["cloture"], name="MASI 20 (spot)",
                                 line=dict(color=C.INK, width=2.2, dash="dot")))
    for t, g in sorted(f.groupby("ticker"), key=lambda kv: F.echeance(kv[0])[1]):
        fig.add_trace(go.Scatter(x=g["date"], y=g[col], name=F.libelle(t), line=dict(color=F.couleur(t), width=2)))
    fig.update_xaxes(rangebreaks=[dict(values=_jours_sans_seance(f["date"]))])
    return _layout(fig, h)


def courbe_terme(f: pd.DataFrame, dates: list, spot: pd.DataFrame, h=400) -> go.Figure:
    fig = go.Figure()
    styles = ["solid", "dash", "dot", "dashdot"]
    for i, d in enumerate(dates):
        g = f[f["date"] == d].sort_values("mois_echeance")
        if g.empty:
            continue
        sp = spot.loc[spot["date"] == d, "cloture"]
        x = ["Spot"] + [F.libelle(t) for t in g["ticker"]]
        y = ([float(sp.iloc[0])] if len(sp) else [None]) + list(g["cloture"])
        fig.add_trace(go.Scatter(x=x, y=y, mode="lines+markers", name=f"{d:%d/%m/%Y}",
                                 line=dict(color=[C.NAVY, C.GOLD, C.SERIES[2], C.SERIES[3]][i % 4], width=2.4, dash=styles[i % 4]),
                                 marker=dict(size=9, line=dict(color="white", width=2))))
    fig = _layout(fig, h, hovermode="x unified")
    fig.update_xaxes(title_text="Échéance")
    return fig


def base_series(f: pd.DataFrame, h=360) -> go.Figure:
    fig = go.Figure()
    for t, g in sorted(f.groupby("ticker"), key=lambda kv: F.echeance(kv[0])[1]):
        fig.add_trace(go.Scatter(x=g["date"], y=g["base_pct"] * 100, name=F.libelle(t),
                                 line=dict(color=F.couleur(t), width=2)))
    fig.add_hline(y=0, line=dict(color=C.MUTED, width=1))
    fig.update_xaxes(rangebreaks=[dict(values=_jours_sans_seance(f["date"]))])
    fig = _layout(fig, h)
    fig.update_yaxes(title_text="Base (% du spot)", tickformat="+.1f", ticksuffix=" %")
    return fig


def oi_volumes(f: pd.DataFrame, h=520) -> go.Figure:
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.08,
                        subplot_titles=("Positions ouvertes (contrats)", "Volume échangé (M MAD)"))
    for t, g in sorted(f.groupby("ticker"), key=lambda kv: F.echeance(kv[0])[1]):
        c = F.couleur(t)
        fig.add_trace(go.Bar(x=g["date"], y=g["open_interest"], name=F.libelle(t), marker_color=c,
                             legendgroup=t), 1, 1)
        fig.add_trace(go.Bar(x=g["date"], y=g["volume"] / 1e6, name=F.libelle(t), marker_color=c,
                             legendgroup=t, showlegend=False), 2, 1)
    fig.update_layout(barmode="stack", bargap=0.25)
    fig.update_xaxes(rangebreaks=[dict(values=_jours_sans_seance(f["date"]))])
    fig = _layout(fig, h)
    fig.update_yaxes(tickformat=",.1f", row=2, col=1)
    fig.update_annotations(font=dict(size=12, color=C.MUTED), x=0, xanchor="left")
    return fig


def futures_semaine(fj: pd.DataFrame, h=360) -> go.Figure:
    """Clôtures quotidiennes de chaque échéance pendant la semaine."""
    fig = go.Figure()
    for t, g in sorted(fj.groupby("ticker"), key=lambda kv: F.echeance(kv[0])[1]):
        fig.add_trace(go.Bar(x=[jour(d) for d in g["date"]], y=g["cloture"], name=F.libelle(t),
                             marker_color=F.couleur(t),
                             text=[nombre(v, 1) for v in g["cloture"]], textposition="outside", textfont=dict(size=9)))
    lo, hi = fj["cloture"].min(), fj["cloture"].max()
    pad = (hi - lo) * 0.6 + 5
    fig = _layout(fig, h)
    fig.update_layout(barmode="group", bargap=0.25, bargroupgap=0.08,
                      legend=dict(orientation="h", yanchor="top", y=-0.1, xanchor="left", x=0))
    fig.update_yaxes(range=[lo - pad, hi + pad])
    return fig


# ---------------------------------------------------------------- liquidité
def liquidite(li: pd.DataFrame, m20: pd.DataFrame, h=460) -> go.Figure:
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.08, row_heights=[0.5, 0.5],
                        subplot_titles=("Indice de liquidité MASI 20 (0-100, 50 = liquidité habituelle)", "MASI 20 (pts)"))
    fig.add_trace(go.Bar(x=li["date"], y=li["indice"], name="Séance", marker_color="#C9D3E6"), 1, 1)
    fig.add_trace(go.Scatter(x=li["date"], y=li["indice_lisse"], name="Moyenne 5 séances",
                             line=dict(color=C.NAVY, width=2.4)), 1, 1)
    fig.add_hline(y=50, line=dict(color=C.GOLD, dash="dash", width=1), row=1, col=1)
    s = m20[(m20["date"] >= li["date"].min()) & (m20["date"] <= li["date"].max())]
    fig.add_trace(go.Scatter(x=s["date"], y=s["cloture"], name="MASI 20", line=dict(color=C.GOLD, width=2),
                             showlegend=False), 2, 1)
    fig.update_yaxes(range=[0, 100], row=1, col=1)
    fig.update_xaxes(rangebreaks=[dict(values=_jours_sans_seance(s["date"]))] if len(s) > 1 else [])
    fig = _layout(fig, h)
    fig.update_annotations(font=dict(size=12, color=C.MUTED), x=0, xanchor="left")
    return fig


NIVEAUX = {"Liquide": C.UP, "Moyenne": "#E0A526", "Peu liquide": C.DOWN}


def scores(sc: pd.DataFrame, h=None) -> go.Figure:
    """Classement des 20 valeurs, de la plus liquide (en haut) à la moins liquide."""
    d = sc.sort_values("score")
    fig = go.Figure()
    for niv, col in NIVEAUX.items():
        x = d[d["niveau"] == niv]
        fig.add_trace(go.Bar(y=x["nom"], x=x["score"], orientation="h", name=niv, marker_color=col,
                             text=[f"{v:.0f}" for v in x["score"]], textposition="outside",
                             hovertemplate="<b>%{y}</b><br>Score : %{x:.0f} / 100<extra></extra>"))
    fig = _layout(fig, h or 26 * len(d) + 80, hovermode="closest")
    fig.update_layout(barmode="overlay", yaxis=dict(categoryorder="array", categoryarray=list(d["nom"])))
    fig.update_xaxes(range=[0, 108], title_text="Score (0 = difficile à échanger, 100 = facile)",
                     showgrid=True, gridcolor=C.GRID)
    fig.update_yaxes(showgrid=False)
    return fig


def note_semaines(hist: pd.DataFrame, h=320) -> go.Figure:
    """Note globale par semaine (barres, sans relier les semaines manquantes)."""
    fig = go.Figure(go.Bar(x=hist["semaine"], y=hist["note"], marker_color=[
        C.UP if v >= 65 else C.DOWN if v <= 35 else "#9AA7BD" for v in hist["note"]],
        text=[f"{v:.0f}" for v in hist["note"]], textposition="outside",
        hovertemplate="%{x}<br>Note : %{y:.0f} / 100<extra></extra>"))
    fig.add_hline(y=50, line=dict(color=C.GOLD, dash="dash", width=1),
                  annotation_text="50 = liquidité habituelle", annotation_position="top left")
    fig = _layout(fig, h, legende=False, hovermode="closest")
    fig.update_yaxes(range=[0, 105])
    fig.update_xaxes(type="category")
    return fig
