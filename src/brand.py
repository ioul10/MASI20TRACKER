"""Identité de l'entreprise : nom, logo et couleurs.

Déposez le logo officiel dans assets/ sous le nom logo_entreprise.png
(ou .jpg / .svg). L'application l'affiche dans le menu, les en-têtes et
les rapports, et en tire ses couleurs principales. Sans fichier, elle
garde son thème par défaut (bleu marine et or).
"""
from __future__ import annotations

import base64
import colorsys
from pathlib import Path

NOM = "CDG Capital"                 # nom affiché dans l'app et les rapports
SERVICE = "DRF"                     # service / direction (signature des rapports)

# Couleurs : laissez None pour les tirer automatiquement du logo,
# ou imposez vos codes officiels, par exemple PRIMAIRE = "#003A70".
PRIMAIRE = None
ACCENT = None

ASSETS = Path(__file__).resolve().parent.parent / "assets"
DEFAUT_PRIMAIRE, DEFAUT_ACCENT = "#0B2447", "#C9A227"


def logo_path() -> Path | None:
    for ext in ("png", "svg", "jpg", "jpeg", "webp"):
        p = ASSETS / f"logo_entreprise.{ext}"
        if p.exists():
            return p
    return None


def logo_data_uri() -> str | None:
    p = logo_path()
    if p is None:
        return None
    mime = {"svg": "image/svg+xml", "jpg": "image/jpeg", "jpeg": "image/jpeg"}.get(p.suffix[1:], f"image/{p.suffix[1:]}")
    return f"data:{mime};base64,{base64.b64encode(p.read_bytes()).decode()}"


def logo_png_bytes() -> bytes | None:
    """Logo en PNG pour Word (le SVG n'y est pas accepté)."""
    p = logo_path()
    if p is None or p.suffix == ".svg":
        return None
    if p.suffix == ".png":
        return p.read_bytes()
    from io import BytesIO
    from PIL import Image
    out = BytesIO()
    Image.open(p).convert("RGBA").save(out, format="PNG")
    return out.getvalue()


def _hex(rgb) -> str:
    return "#{:02X}{:02X}{:02X}".format(*[int(round(c)) for c in rgb])


def _lum(rgb) -> float:
    r, g, b = [c / 255 for c in rgb]
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def _assombrir(rgb, cible=0.22):
    """Assombrit une couleur jusqu'à ce que le texte blanc y soit lisible."""
    h, l, s = colorsys.rgb_to_hls(*[c / 255 for c in rgb])
    while _lum([c * 255 for c in colorsys.hls_to_rgb(h, l, s)]) > cible and l > 0.05:
        l -= 0.03
    return [c * 255 for c in colorsys.hls_to_rgb(h, l, s)]


def couleurs_du_logo() -> tuple[str, str] | None:
    """Couleur principale (foncée) et couleur d'accent (la plus vive d'une autre teinte)."""
    p = logo_path()
    if p is None or p.suffix == ".svg":
        return None
    try:
        from PIL import Image
        im = Image.open(p).convert("RGBA")
        im.thumbnail((200, 200))
        px = [(r, g, b) for r, g, b, a in im.getdata() if a > 200]
        px = [c for c in px if not (min(c) > 225)]           # sans le fond blanc
        if len(px) < 30:
            return None
        q = Image.new("RGB", (len(px), 1))
        q.putdata(px)
        pal = q.quantize(colors=6, method=Image.Quantize.MEDIANCUT)
        cols = pal.getpalette()[:18]
        comptes = sorted(pal.getcolors(), reverse=True)
        cand = []
        for n, i in comptes:
            rgb = cols[3 * i:3 * i + 3]
            h, l, s = colorsys.rgb_to_hls(*[c / 255 for c in rgb])
            cand.append({"rgb": rgb, "n": n, "h": h, "l": l, "s": s})
        colores = [c for c in cand if c["s"] > 0.25 and 0.08 < c["l"] < 0.85] or cand
        prim = colores[0]
        autres = [c for c in colores[1:] if min(abs(c["h"] - prim["h"]), 1 - abs(c["h"] - prim["h"])) > 0.08]
        acc = max(autres, key=lambda c: c["s"] * (c["n"] ** 0.3)) if autres else None
        primaire = _hex(_assombrir(prim["rgb"]))
        accent = _hex(acc["rgb"]) if acc else DEFAUT_ACCENT
        return primaire, accent
    except Exception:
        return None


def couleurs() -> tuple[str, str]:
    auto = couleurs_du_logo() or (DEFAUT_PRIMAIRE, DEFAUT_ACCENT)
    return PRIMAIRE or auto[0], ACCENT or auto[1]
