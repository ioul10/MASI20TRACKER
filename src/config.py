"""Paramètres de MASI20TRACKER (couleurs, libellés, sources)."""

APP_NAME = "MASI20TRACKER"
SOUS_TITRE = "Suivi de l'indice MASI 20, de ses composants et du marché à terme"

# --- Couleurs : celles du logo de l'entreprise (src/brand.py), sinon bleu marine et or
from . import brand as _brand  # noqa: E402

NAVY, GOLD = _brand.couleurs()


def _eclaircir(h: str, f: float = 0.25) -> str:
    r, g, b = (int(h[i:i + 2], 16) for i in (1, 3, 5))
    return "#{:02X}{:02X}{:02X}".format(*(int(c + (255 - c) * f) for c in (r, g, b)))


NAVY_2 = _eclaircir(NAVY, 0.18)
NOM_ENTREPRISE = _brand.NOM
SERVICE = _brand.SERVICE
BG = "#F4F6FA"
CARD = "#FFFFFF"
INK = "#14213D"
MUTED = "#5B6577"
GRID = "#E3E7EF"
UP = "#12804A"      # hausse (texte et barres)
DOWN = "#C23B3B"    # baisse
NEUTRE = "#8A94A6"

SERIES = ["#1F5FAD", "#D98A1E", "#1BA37A", "#6250D6", "#C2477A", "#008300"]  # palette validée (CVD)

MULTIPLICATEUR = 10  # MAD par point d'indice

# Libellés courts des secteurs (codes du bulletin de la cote)
SECTEURS = {
    "AGR": "Agroalimentaire", "ASS": "Assurances", "BAN": "Banques",
    "BMC": "BTP & matériaux", "BOI": "Boissons", "CHI": "Chimie",
    "DIS": "Distributeurs", "ELC": "Électricité", "IAG": "Industrie agricole",
    "IBE": "Biens d'équipement", "IMM": "Immobilier", "LH": "Loisirs & hôtels",
    "LSI": "Informatique", "MIN": "Mines", "PEG": "Pétrole & gaz",
    "PHA": "Pharmacie", "SAN": "Santé", "SDT": "Services de transport",
    "SFA": "Sociétés de financement", "SP": "Sylviculture & papier",
    "SPH": "Holdings", "SPI": "Foncières (SPI)", "TCO": "Télécoms", "TRP": "Transport",
}

# Seuils
SEUIL_BLOC_MAD = 5_000_000          # niveau de prix ≥ 5 M MAD = grosse transaction
SEUIL_ALERTE_VAR = 0.05             # variation quotidienne de l'indice jugée anormale (5 %)
TOLERANCE_CONTROLE_PB = 25          # écart toléré entre variation reconstituée et publiée

# Pondération du score de liquidité (somme = 1)
POIDS_LIQUIDITE = {"volume": 0.25, "rotation": 0.20, "amihud": 0.25, "spread": 0.20, "activite": 0.10}

# Flux d'actualités (RSS). Vérifiez et complétez : les adresses peuvent changer.
FLUX_NEWS = {
    "Médias24": "https://medias24.com/feed/",
    "La Vie Éco": "https://www.lavieeco.com/feed/",
    "LesEco.ma": "https://leseco.ma/feed/",
    "Challenge": "https://www.challenge.ma/feed/",
    "L'Economiste": "https://www.leconomiste.com/rss-leconomiste",
    "Le Desk (éco)": "https://ledesk.ma/feed/",
}
MOTS_CLES_MARCHE = ["MASI", "Bourse de Casablanca", "AMMC", "marché à terme", "future"]
