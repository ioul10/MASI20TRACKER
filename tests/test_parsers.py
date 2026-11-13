"""Tests de non-régression du lecteur de bulletins.

Placez des bulletins dans data/bulletins/ puis : python -m pytest tests
"""
from pathlib import Path

import pytest

from src.parsers import detecter_type, lire_cote, lire_futures, to_num

BUL = Path(__file__).resolve().parent.parent / "data" / "bulletins"


def test_to_num():
    assert to_num("1 398,00") == 1398.0
    assert to_num("-3,44 %") == -3.44
    assert to_num("-") is None


@pytest.mark.parametrize("f", sorted(BUL.glob("cote_*.pdf")), ids=lambda p: p.name)
def test_cote(f):
    b = lire_cote(f.read_bytes())
    assert len(b.actions) > 60
    assert b.actions["isin"].str.match(r"^MA\d{10}$").all()
    assert "MASI 20" in set(b.indices["indice"])
    assert b.niveaux["isin"].notna().all()
    central = b.niveaux[b.niveaux["marche"] == "central"]["volume"].sum()
    assert central == pytest.approx(b.totaux["central"]["volume"], rel=1e-3)


@pytest.mark.parametrize("f", sorted(BUL.glob("futures_*.pdf")), ids=lambda p: p.name)
def test_futures(f):
    assert detecter_type(f.read_bytes()) == "futures"
    b = lire_futures(f.read_bytes())
    assert len(b.cours) >= 4
    assert b.cours["ticker"].str.startswith("FMASI20").all()
