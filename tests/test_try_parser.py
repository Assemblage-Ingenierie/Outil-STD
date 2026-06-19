"""Tests pour le parser .TRY (Météonorm)."""
import textwrap
import pytest
import pandas as pd

from core.try_parser import parse_try, humidite_absolue


# ---------------------------------------------------------------------------
# Helpers de génération de lignes TRY
# ---------------------------------------------------------------------------

def _ligne_try(t_dixieme: int, dni: int, dhi: int, hr: int, lineno: int = 1) -> str:
    """
    Construit une ligne TRY à largeur fixe cohérente avec les tranches :
      [0:3]  = numéro ligne (3 chars)
      [3]    = espace
      [4:7]  = T × 10 (3 chars, signé)
      [7:11] = DNI (4 chars)
      [11:15]= DHI (4 chars)
      [15:23]= 8 chars de remplissage
      [23:26]= HR % (3 chars)
    """
    n   = f"{lineno:3d}"           # ex "  1"
    t   = f"{t_dixieme:3d}"        # ex "200"
    d   = f"{dni:4d}"              # ex " 350"
    h   = f"{dhi:4d}"              # ex " 120"
    pad = " " * 8                  # positions 15-22
    hr_ = f"{hr:3d}"               # ex " 65" ou "100"
    return n + " " + t + d + h + pad + hr_ + "\n"


def _try_file(lines: list[str]) -> str:
    return "".join(lines)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def try_simple(tmp_path):
    """Fichier TRY minimal : 2 heures, T et HR normales."""
    content = _try_file([
        _ligne_try(200,  350, 120, 65, 1),   # T=20.0, HR=65
        _ligne_try(150,    0,   0, 80, 2),   # T=15.0, HR=80
    ])
    f = tmp_path / "test.try"
    f.write_text(content, encoding="latin-1")
    return f


@pytest.fixture
def try_hr100(tmp_path):
    """Cas limite HR=100 : 3 chiffres qui collent à la colonne voisine."""
    content = _try_file([
        _ligne_try(250, 1000, 500, 100, 1),  # T=25.0, HR=100
    ])
    f = tmp_path / "test_hr100.try"
    f.write_text(content, encoding="latin-1")
    return f


@pytest.fixture
def try_negative_t(tmp_path):
    """Température négative : -5°C = -50 en dixièmes → format '-50'."""
    content = _try_file([
        _ligne_try(-50, 0, 0, 75, 1),  # T=-5.0, HR=75
    ])
    f = tmp_path / "test_neg.try"
    f.write_text(content, encoding="latin-1")
    return f


@pytest.fixture
def try_with_header(tmp_path):
    """Fichier avec une ligne d'en-tête à ignorer (T hors plage -60..70)."""
    header = " " * 4 + "999" + " " * 23 + "\n"  # T=99.9°C → filtré
    data   = _ligne_try(200, 350, 120, 65, 1)
    f = tmp_path / "test_hdr.try"
    f.write_text(header + data, encoding="latin-1")
    return f


# ---------------------------------------------------------------------------
# Tests parse_try — structure de base
# ---------------------------------------------------------------------------

def test_colonnes_presentes(try_simple):
    df = parse_try(try_simple)
    assert set(df.columns) >= {"T_ext", "HR_ext", "DNI", "DHI", "w_ext"}


def test_nombre_lignes(try_simple):
    df = parse_try(try_simple)
    assert len(df) == 2


def test_valeurs_t_ext(try_simple):
    df = parse_try(try_simple)
    assert df["T_ext"].iloc[0] == pytest.approx(20.0)
    assert df["T_ext"].iloc[1] == pytest.approx(15.0)


def test_valeurs_hr_ext(try_simple):
    df = parse_try(try_simple)
    assert df["HR_ext"].iloc[0] == pytest.approx(65.0)
    assert df["HR_ext"].iloc[1] == pytest.approx(80.0)


def test_valeurs_dni_dhi(try_simple):
    df = parse_try(try_simple)
    assert df["DNI"].iloc[0] == pytest.approx(350.0)
    assert df["DHI"].iloc[0] == pytest.approx(120.0)
    assert df["DNI"].iloc[1] == pytest.approx(0.0)


def test_index_base_1(try_simple):
    df = parse_try(try_simple)
    assert df.index[0] == 1
    assert df.index[1] == 2
    assert df.index.name == "heure_annee"


# ---------------------------------------------------------------------------
# Test du bug HR=100 (le cas qui cassait avec split())
# ---------------------------------------------------------------------------

def test_hr_100_parsee_correctement(try_hr100):
    """Quand HR=100, les 3 chiffres collent ; split() lisait 0 — corrigé."""
    df = parse_try(try_hr100)
    assert len(df) == 1
    assert df["HR_ext"].iloc[0] == pytest.approx(100.0)
    assert df["T_ext"].iloc[0] == pytest.approx(25.0)


def test_hr_plafonnee_a_100(tmp_path):
    """HR > 100 est ramenée à 100 par sécurité."""
    line = _ligne_try(200, 0, 0, 105, 1)
    f = tmp_path / "test.try"
    f.write_text(line, encoding="latin-1")
    df = parse_try(f)
    assert df["HR_ext"].iloc[0] == pytest.approx(100.0)


# ---------------------------------------------------------------------------
# Test température négative
# ---------------------------------------------------------------------------

def test_temperature_negative(try_negative_t):
    df = parse_try(try_negative_t)
    assert df["T_ext"].iloc[0] == pytest.approx(-5.0)


# ---------------------------------------------------------------------------
# Test filtrage des lignes d'en-tête
# ---------------------------------------------------------------------------

def test_header_ignore(try_with_header):
    """Les lignes avec T hors plage (-60..70) sont ignorées."""
    df = parse_try(try_with_header)
    assert len(df) == 1
    assert df["T_ext"].iloc[0] == pytest.approx(20.0)


# ---------------------------------------------------------------------------
# Tests humidite_absolue
# ---------------------------------------------------------------------------

def test_humidite_absolue_scalaire():
    """À 20°C / 50% HR, w ≈ 7.2 g/kg (valeur psychrométrique connue)."""
    w = humidite_absolue(20.0, 50.0)
    assert 7.0 < w < 7.5


def test_humidite_absolue_nulle():
    """HR=0 → w=0."""
    w = humidite_absolue(20.0, 0.0)
    assert w == pytest.approx(0.0)


def test_w_ext_coherente(try_simple):
    """w_ext doit être > 0 quand HR > 0."""
    df = parse_try(try_simple)
    assert (df["w_ext"] > 0).all()


def test_w_ext_croissant_avec_hr(tmp_path):
    """À T fixe, humidité absolue croît avec HR."""
    lines = [
        _ligne_try(200, 0, 0, 30, 1),  # HR=30
        _ligne_try(200, 0, 0, 80, 2),  # HR=80
    ]
    f = tmp_path / "test.try"
    f.write_text("".join(lines), encoding="latin-1")
    df = parse_try(f)
    assert df["w_ext"].iloc[1] > df["w_ext"].iloc[0]
