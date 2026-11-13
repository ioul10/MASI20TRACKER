# MASI20TRACKER

Application Streamlit de suivi de l'indice **MASI 20**, de ses **20 composants** et du **marché à terme** (futures sur MASI 20), alimentée par les **bulletins officiels de la Bourse de Casablanca**.

| Page | Contenu |
|---|---|
| **Tableau de bord** | Chiffres clés, MASI 20 sur 6 mois, futures du jour, signaux techniques, carte des composants, liquidité |
| **Indice & technique** | Chandeliers, EMA 20/40, Bollinger, Fibonacci, RSI, ATR, régime, bougies hebdo, tous les indices de la Bourse |
| **Composants** | MASI 20 ou MASI complet : carte, contributions, poids, volumes, secteurs, « où va l'argent », calibration des poids |
| **Marché à terme** | Cours et base, courbe des échéances, positions ouvertes et volumes, lecture prix × OI, transactions, calculateur (P&L, levier, couverture) |
| **Liquidité** | Indice de liquidité MASI 20 (0-100) et score par valeur : volume, rotation, Amihud, spread, activité, concentration |
| **Bilan hebdo** | Le rapport de la semaine (futures + composants + technique + liquidité + Avis DRF), export HTML imprimable en PDF |
| **Actualités** | Flux RSS de la presse financière filtrés sur le MASI 20 et ses valeurs |
| **Import des bulletins** | Dépôt des PDF du jour, contrôles automatiques, enregistrement |
| **Composition & paramètres** | Composition du MASI 20 par code ISIN, flottant, plafond |

## Routine

**Chaque jour** : téléchargez sur le site de la Bourse le bulletin de la cote (`BCFR_AAAAMMJJ.pdf`) et celui du marché à terme (`BCFR_D_AAAAMMJJ.pdf`), puis déposez-les dans **Import des bulletins**. L'application :
- retrouve les 20 valeurs **par code ISIN** (jamais par nom : la Bourse modifie parfois les libellés) ;
- compare la variation reconstituée à la variation publiée du MASI 20 ;
- signale les doublons, les variations anormales (> 5 %) et le marché de blocs.

**Chaque vendredi** : page **Bilan hebdo** → choisir la semaine → relire l'Avis DRF → télécharger. Ouvrir le fichier HTML dans le navigateur, puis Ctrl+P → « Enregistrer au format PDF » (A4 paysage).

**À chaque révision annuelle du MASI 20** : page **Composition & paramètres** → date de fin pour les sortants, nouvelles lignes pour les entrants, facteurs de flottant.

## Règles de calcul

- **Variations hebdomadaires** : depuis la clôture de la **dernière séance de la semaine précédente** (et non depuis le lundi).
- **Rendement d'une valeur** : cours de référence de la séance suivante ÷ cours de référence (déjà ajusté des opérations sur titres).
- **Poids** : nombre de titres × cours de référence × facteur de flottant, plafonnés si un plafond est défini. Sans facteur de flottant, les poids sont approchés ; le contrôle (reconstitué vs publié) et la calibration (page Composants, à partir de 15 séances) aident à les affiner.
- **Volumes** : marché central uniquement ; le marché de blocs est compté à part. « Grosse transaction » = niveau de prix ≥ 5 M MAD et ≥ 1 M MAD par contrat.
- **Indicateurs techniques** : recalculés à partir des cours bruts. Le bulletin ne donne que la clôture de l'indice ; le plus haut et le plus bas peuvent être saisis à l'import (sinon l'ATR utilise l'écart de clôture à clôture).

## Installation

```bash
pip install -r requirements.txt
streamlit run app.py
```

### Mise en ligne (GitHub + Streamlit Community Cloud)

1. Créez un **repo GitHub privé** `MASI20TRACKER` et poussez-y ce dossier (y compris `data/`).
2. Sur [share.streamlit.io](https://share.streamlit.io) : *New app* → ce repo → `app.py`.
3. Dans *Settings → Sharing*, limitez l'accès aux personnes autorisées.
4. **Sauvegarde des imports** : le disque de Streamlit Cloud est effacé à chaque redémarrage. Créez un jeton GitHub *fine-grained* (accès *Contents : Read and write* sur ce seul repo) et collez dans *Settings → Secrets* le contenu de `.streamlit/secrets.toml.exemple` complété. Chaque import est alors enregistré dans le repo (`data/*.csv` et `data/bulletins/*.pdf`).

### Reconstruire la base depuis l'Excel et les bulletins

```bash
python scripts/initialiser.py --excel BASEMASI20TRACKER.xlsx --bulletins dossier_des_pdf/
```

L'Excel fournit l'historique (feuilles `MSI20INDEX`, `DATA_SUIVI`, `DATA_TRANS`) ; les bulletins remplacent ses valeurs pour les mêmes séances.

## Structure

```
app.py                  navigation
vues/                   une page par fichier
src/parsers.py          lecture des bulletins PDF (cote, futures)
src/importer.py         contrôles et enregistrement
src/store.py            base CSV + sauvegarde GitHub
src/composants.py       composition, poids, contributions
src/technique.py        EMA, RSI, ATR, Bollinger, Fibonacci, régime
src/futures.py          échéances, base, courbe, lecture prix × OI
src/liquidite.py        score et indice de liquidité
src/hebdo.py            assemblage du bilan hebdomadaire + Avis DRF proposé
src/report.py           export HTML du bilan
src/charts.py           graphiques Plotly
src/news.py             flux RSS
src/config.py           couleurs, seuils, flux d'actualités
data/                   base (CSV) et bulletins archivés
scripts/initialiser.py  construction de la base de départ
tests/                  tests du lecteur de bulletins (pytest)
```

---
Source des données : bulletins officiels de la Bourse de Casablanca. Outil d'analyse interne, non affilié à la Bourse de Casablanca. Ne constitue pas un conseil en investissement.
