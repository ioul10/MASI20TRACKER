import pandas as pd
import streamlit as st

from src import charts as G
from src import technique as T
from src import ui
from src.fmt import date_courte, nombre, pct

db = ui.db()
m20 = db["masi20"].sort_values("date")
if m20.empty:
    ui.page("Indice & technique")
    st.info("Aucune donnée. Importez des bulletins.")
    st.stop()
tech = T.indicateurs(m20)
z = tech.iloc[-1]
ui.page("Indice & technique", "Le MASI 20, ses moyennes mobiles, le RSI, l'ATR et la variation sur 5 séances",
        tech["date"].iloc[-1])


def entete(titre: str, role: str, choix: list | None = None, key: str | None = None):
    """Titre de section + choix de la période (facultatif) + bouton « Rôle de la méthode »."""
    a, m, b = st.columns([4, 1.3, 1], vertical_alignment="bottom")
    with a:
        ui.section(titre)
    sel = m.segmented_control(key, choix, default=choix[0], key=key, label_visibility="collapsed") if choix else None
    with b.popover("La méthode", icon=":material/help:", width="stretch"):
        st.markdown(role)
    return sel or (choix[0] if choix else None)


c = st.columns([2.4, 1.6, 1.6, 1])
periode = c[0].segmented_control("Période affichée", ["1 mois", "3 mois", "6 mois", "1 an", "Tout"], default="6 mois")
type_mm = c[1].segmented_control("Moyennes", ["Simples", "Exponentielles"], default="Simples")
affichage = c[2].segmented_control("MASI 20 affiché en", ["Courbe", "Chandeliers"], default="Courbe",
                                   help="Chandeliers : ouverture = clôture de la veille (le bulletin ne publie pas "
                                        "d'ouverture) ; sans plus haut / plus bas, la bougie n'a pas de mèches.")
bougies = affichage == "Chandeliers"
n = {"1 mois": 21, "3 mois": 63, "6 mois": 126, "1 an": 250}.get(periode or "6 mois", len(tech))
vue = tech.tail(n)
prefixe = "ema" if type_mm == "Exponentielles" else "mm"

# ------------------------------------------------------------ lecture du jour
au_dessus = sum(z["cloture"] > z[f"{prefixe}{k}"] for k in (5, 10, 20, 40) if pd.notna(z[f"{prefixe}{k}"]))
rangees = all(pd.notna(z[f"{prefixe}{k}"]) for k in (5, 10, 20, 40))
if rangees and z[f"{prefixe}5"] > z[f"{prefixe}10"] > z[f"{prefixe}20"] > z[f"{prefixe}40"]:
    ordre = "moyennes rangées à la hausse"
elif rangees and z[f"{prefixe}5"] < z[f"{prefixe}10"] < z[f"{prefixe}20"] < z[f"{prefixe}40"]:
    ordre = "moyennes rangées à la baisse"
else:
    ordre = "moyennes emmêlées"


def zone_rsi(r):
    return "–" if pd.isna(r) else "surachat" if r >= 70 else "survente" if r <= 30 else "haussier" if r > 50 else "baissier"


med_atr = tech["atr14"].tail(120).median()
regime = z["regime"] or "–"
ui.kpis([
    {"lab": f"MASI 20 · {date_courte(z['date'])}", "val": nombre(z["cloture"]), "sub": pct(z["var"]) + " sur la séance",
     "sens": z["var"], "gold": True},
    {"lab": "Tendance (moyennes)", "val": f"{au_dessus} / 4", "sub": f"moyennes sous l'indice · {ordre}"},
    {"lab": "RSI 14 · RSI 5", "val": f"{nombre(z['rsi14'], 0)} · {nombre(z['rsi5'], 0)}",
     "sub": f"{zone_rsi(z['rsi14'])} (14) · {zone_rsi(z['rsi5'])} (5)"},
    {"lab": "ATR 14 · ATR 5", "val": f"{nombre(z['atr14'], 1)} · {nombre(z['atr5'], 1)} pts",
     "sub": (f"{pct(z['atr14_pct'], 2, False)} de l'indice · ATR 5 "
             f"{'au-dessus' if z['atr5'] > z['atr14'] else 'en dessous'} de l'ATR 14")},
    {"lab": "Variation 5 séances", "val": pct(z["var_5j"]), "sub": f"régime {regime} (seuil ± 3 %)", "sens": z["var_5j"]},
])

# ------------------------------------------------------------ 1. moyennes
lib = "EMA" if prefixe == "ema" else "MM"
entete("1 · Indice et moyennes mobiles 5 · 10 · 20 · 40",
       f"""**À quoi ça sert** : lisser les à-coups de la séance pour voir **la tendance**.

**Calcul** : MM *n* = moyenne des *n* dernières clôtures (la moyenne exponentielle donne plus de poids aux séances récentes).
- **MM 5** ≈ une semaine de séances, **MM 10** ≈ deux semaines : le court terme ;
- **MM 20** ≈ un mois : la tendance de fond courte ;
- **MM 40** ≈ deux mois : la tendance de fond.

**Lecture**
- indice au-dessus de ses 4 moyennes et moyennes rangées 5 > 10 > 20 > 40 : **tendance haussière installée** ;
- ordre inverse : **tendance baissière installée** ;
- moyennes emmêlées : **pas de tendance claire** ;
- la MM 5 qui croise la MM 20 vers le haut (ou le bas) : **premier signal** de changement de tendance.

**Limite** : une moyenne est toujours **en retard** sur le cours ; en marché sans tendance, les croisements donnent beaucoup de faux signaux.

**Aujourd'hui** : l'indice est au-dessus de **{au_dessus} moyennes sur 4**, {ordre}.""")
choix_mm = st.pills("Moyennes affichées", [5, 10, 20, 40], selection_mode="multi", default=[5, 10, 20, 40],
                    format_func=lambda k: f"{lib} {k}", key="mm_affichees",
                    help="Cliquez sur une moyenne pour l'afficher ou la masquer.")
st.plotly_chart(G.indice_moyennes(vue, periodes=sorted(choix_mm or []), prefixe=prefixe, bougies=bougies), width="stretch", config=G.CFG)

# ------------------------------------------------------------ 2. RSI
rn = 5 if st.session_state.get("rsi_n") == "RSI 5" else 14
entete("2 · RSI (force relative)",
       f"""**À quoi ça sert** : mesurer **la force du mouvement** (momentum) : les hausses récentes l'emportent-elles sur les baisses ? Le résultat va de 0 à 100.

**Calcul** : RSI = 100 − 100 ÷ (1 + moyenne des hausses ÷ moyenne des baisses), sur *n* séances (lissage de Wilder).
- **RSI 5** réagit très vite : signaux de court terme, plus nombreux et moins fiables ;
- **RSI 14** est la référence.

**Lecture**
- **au-dessus de 70** (barres rouges) : **surachat**, la hausse a été rapide, risque d'essoufflement ;
- **sous 30** (barres vertes) : **survente**, la baisse a été rapide, rebond possible ;
- **50** : ligne de partage entre acheteurs et vendeurs.

**Limite** : dans une forte tendance, le RSI peut rester longtemps en zone extrême ; ce n'est jamais un signal à lui seul.

**Aujourd'hui** : RSI 14 = **{nombre(z['rsi14'], 0)}** ({zone_rsi(z['rsi14'])}), RSI 5 = **{nombre(z['rsi5'], 0)}** ({zone_rsi(z['rsi5'])}).""",
       ["RSI 14", "RSI 5"], "rsi_n")
st.plotly_chart(G.rsi_barres(vue, rn, bougies=bougies), width="stretch", config=G.CFG)

# ------------------------------------------------------------ 3. ATR
an = 5 if st.session_state.get("atr_n") == "ATR 5" else 14
manq = int((~vue["hl_connu"]).sum())
entete("3 · ATR (amplitude moyenne d'une séance)",
       f"""**À quoi ça sert** : mesurer **la volatilité** : de combien de points l'indice bouge en moyenne sur une séance, **quel que soit le sens**.

**Calcul**
- vrai range d'une séance = le plus grand de : plus haut − plus bas, |plus haut − clôture de la veille|, |plus bas − clôture de la veille| ;
- ATR *n* = moyenne lissée (Wilder) des vrais ranges des *n* dernières séances, en points d'indice.
- **ATR 5** = la volatilité récente, **ATR 14** = la référence.

**Lecture**
- ATR qui monte : le marché devient **nerveux** (souvent en baisse ou à un tournant) ;
- ATR qui baisse : marché **calme** ;
- ATR 5 au-dessus de l'ATR 14 : la nervosité **augmente** ;
- usage pratique : placer un stop à 1,5 ou 2 ATR du cours, dimensionner une position.

**Limite** : sans plus haut ni plus bas, le vrai range est remplacé par |clôture − clôture de la veille| : l'ATR est alors **sous-estimé** (barres pâles).

**Aujourd'hui** : ATR 14 = **{nombre(z['atr14'], 1)} pts** ({pct(z['atr14_pct'], 2, False)} de l'indice), médiane des 120 dernières séances = {nombre(med_atr, 1)} pts.""",
       ["ATR 14", "ATR 5"], "atr_n")
st.plotly_chart(G.atr_barres(vue, an, bougies=bougies), width="stretch", config=G.CFG)
if manq:
    ui.note(f"{manq} séance(s) de la période sans plus haut ni plus bas (barres pâles) : ATR estimé à partir des clôtures. "
            "Complétez-les dans la page <b>Import des bulletins → Compléter les hauts et les bas</b>.")

# ------------------------------------------------------------ 4. Variation 5 jours
entete("4 · Variation sur 5 séances",
       f"""**À quoi ça sert** : résumer **le mouvement de la semaine glissante** et classer le marché en trois régimes.

**Calcul** : variation 5 séances = clôture du jour ÷ clôture d'il y a 5 séances − 1.

**Lecture** (même règle que l'Excel, seuil ± 3 %)
- **≥ + 3 %** (barres vertes) : **BOOM**, hausse marquée ;
- **≤ − 3 %** (barres rouges) : **SLUMP**, baisse marquée ;
- entre les deux (barres grises) : **STABLE**.

Plusieurs barres d'affilée hors de la bande grise = **mouvement de fond** ; un retour dans la bande = **essoufflement**.

**Limite** : fenêtre glissante, une seule grosse séance reste « dans » la variation pendant 5 séances.

**Aujourd'hui** : **{pct(z['var_5j'])}**, régime **{regime}**.""")
st.plotly_chart(G.var5_barres(vue, bougies=bougies), width="stretch", config=G.CFG)

# ------------------------------------------------------------ tableau
ui.section("Dernières séances")
x = tech.tail(15).iloc[::-1]
tab = pd.DataFrame({"Date": x["date"].dt.strftime("%d/%m/%Y"), "Clôture": x["cloture"], "Var.": x["var"],
                    "Plus haut": x["plus_haut"].astype(float), "Plus bas": x["plus_bas"].astype(float),
                    f"{lib} 5": x[f"{prefixe}5"], f"{lib} 10": x[f"{prefixe}10"], f"{lib} 20": x[f"{prefixe}20"],
                    f"{lib} 40": x[f"{prefixe}40"], "RSI 5": x["rsi5"], "RSI 14": x["rsi14"],
                    "ATR 5": x["atr5"], "ATR 14": x["atr14"], "Var. 5 s.": x["var_5j"], "Régime": x["regime"]})
st.dataframe(ui.style_table(tab, pct_cols=["Var.", "Var. 5 s."],
                            fmt={k: (lambda v: nombre(v)) for k in ["Clôture", "Plus haut", "Plus bas", f"{lib} 5",
                                                                     f"{lib} 10", f"{lib} 20", f"{lib} 40"]}
                            | {k: (lambda v: nombre(v, 0)) for k in ["RSI 5", "RSI 14"]}
                            | {k: (lambda v: nombre(v, 1)) for k in ["ATR 5", "ATR 14"]}),
             width="stretch", hide_index=True)

ind = db["indices"]
if not ind.empty:
    d = ind["date"].max()
    with st.expander(f"Tous les indices de la Bourse · séance du {date_courte(d)}"):
        y = ind[ind["date"] == d]
        st.dataframe(ui.style_table(pd.DataFrame({"Indice": y["indice"], "Valeur": y["valeur"],
                                                  "Var. veille": y["var_veille"] / 100, "Depuis le 31/12": y["var_ytd"] / 100}),
                                    pct_cols=["Var. veille", "Depuis le 31/12"], fmt={"Valeur": lambda v: nombre(v)}),
                     width="stretch", hide_index=True, height=420)
ui.pied()
