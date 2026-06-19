"""Tests pour le parser .SLK (résultats + synthèse Pléiades)."""
import pytest
import numpy as np

from core.slk_parser import (
    parse_resultats, parse_synthese, parse_slk_auto,
    FichierInvalideError,
)


# ---------------------------------------------------------------------------
# Helpers de génération SLK
# ---------------------------------------------------------------------------

def _cell(row: int, col: int, val) -> str:
    """Génère une ligne SLK de type cellule."""
    if isinstance(val, str):
        return f'C;Y{row};X{col};K"{val}"\n'
    return f'C;Y{row};X{col};K{val}\n'


def _slk_header() -> str:
    return "ID;PWXL;N;E\n"


def _resultats_slk(zones: list[str], n_rows: int = 3) -> str:
    """
    Génère un SLK de résultats minimal valide.

    Structure :
      Y1 = types de grandeurs
      Y2 = noms de zones
      Y3..Y(2+n_rows) = données horaires

    Colonnes :
      1 = mois, 2 = jour, 3 = heure
      4 = Températures (T_ext global)
      5..5+nz-1 = Température (°C) par zone
      5+nz..   = Humidité relative (%) par zone
      5+2nz..  = Apports occupants (W) par zone
    """
    nz = len(zones)
    lines = [_slk_header()]

    # Y1 : types
    lines.append(_cell(1, 1, "Mois"))
    lines.append(_cell(1, 2, "Jour"))
    lines.append(_cell(1, 3, "Heure"))
    lines.append(_cell(1, 4, "Températures"))
    for i in range(nz):
        lines.append(_cell(1, 5 + i,        "Température (°C)"))
        lines.append(_cell(1, 5 + nz + i,   "Humidité relative (%)"))
        lines.append(_cell(1, 5 + 2*nz + i, "Apports occupants (W)"))

    # Y2 : noms de zones (col 4 = global, pas de zone)
    lines.append(_cell(2, 4, ""))
    for i, z in enumerate(zones):
        lines.append(_cell(2, 5 + i,        z))
        lines.append(_cell(2, 5 + nz + i,   z))
        lines.append(_cell(2, 5 + 2*nz + i, z))

    # Y3..Y(2+n_rows) : données
    for r in range(n_rows):
        row = 3 + r
        mois  = (r % 12) + 1
        jour  = (r % 28) + 1
        heure = (r % 24) + 1
        t_ext = 15.0 + r
        lines.append(_cell(row, 1, mois))
        lines.append(_cell(row, 2, jour))
        lines.append(_cell(row, 3, heure))
        lines.append(_cell(row, 4, t_ext))
        for i in range(nz):
            lines.append(_cell(row, 5 + i,        20.0 + i + r))
            lines.append(_cell(row, 5 + nz + i,   50.0 + i))
            lines.append(_cell(row, 5 + 2*nz + i, 100.0 * (r % 2)))  # 0 ou 100 W

    lines.append("E\n")
    return "".join(lines)


def _synthese_slk(zones: list[str]) -> str:
    """
    Génère un SLK de synthèse minimal valide (2 tableaux).
    Tableau 1 : header à Y1, données à Y4..
    Tableau 2 : header à Y65, données à Y68..
    """
    lines = [_slk_header()]

    # En-tête tableau 1 (Y1)
    lines.append(_cell(1, 1, "Zones"))
    lines.append(_cell(2, 2, "Besoins Ch kWh"))   # contient "Besoin" → validation
    lines.append(_cell(2, 3, "kWh/m²"))
    lines.append(_cell(2, 4, "Besoins Fr kWh"))
    # (Y3 = unités, skippé par r_start1 = 1+3 = 4)

    # Données tableau 1 (Y4..)
    for i, z in enumerate(zones):
        r = 4 + i
        lines.append(_cell(r, 1, z))
        lines.append(_cell(r, 2, 500.0 * (i+1)))   # besoins_chaud_kwh
        lines.append(_cell(r, 3, 25.0))              # besoins_chaud_kwh_m2
        lines.append(_cell(r, 4, 200.0 * (i+1)))    # besoins_froid_kwh
        lines.append(_cell(r, 5, 10.0))              # besoins_froid_kwh_m2
        lines.append(_cell(r, 6, 3000.0))            # puiss_chaud_w
        lines.append(_cell(r, 7, 2500.0))            # puiss_froid_w
        lines.append(_cell(r, 8, -3.0))              # t_min
        lines.append(_cell(r, 9, 19.0))              # t_moy
        lines.append(_cell(r, 10, 35.0))             # t_max

    # En-tête tableau 2 (Y65)
    lines.append(_cell(65, 1, "Zones"))

    # Données tableau 2 (Y68..)
    for i, z in enumerate(zones):
        r = 68 + i
        lines.append(_cell(r, 1, z))
        lines.append(_cell(r, 4, 400.0))   # heures_inconfort
        lines.append(_cell(r, 8, 20.0))    # surface_m2
        lines.append(_cell(r, 9, 60.0))    # volume_m3

    lines.append("E\n")
    return "".join(lines)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def resultats_1zone(tmp_path):
    content = _resultats_slk(["Séjour"], n_rows=3)
    f = tmp_path / "resultats.slk"
    f.write_text(content, encoding="latin-1")
    return f


@pytest.fixture
def resultats_2zones(tmp_path):
    content = _resultats_slk(["Séjour", "Chambre"], n_rows=4)
    f = tmp_path / "resultats2.slk"
    f.write_text(content, encoding="latin-1")
    return f


@pytest.fixture
def synthese_2zones(tmp_path):
    content = _synthese_slk(["Séjour", "Chambre"])
    f = tmp_path / "synthese.slk"
    f.write_text(content, encoding="latin-1")
    return f


@pytest.fixture
def resultats_sans_hr(tmp_path):
    """Fichier résultats sans Humidité relative → doit lever FichierInvalideError."""
    nz = 1
    lines = [_slk_header()]
    lines.append(_cell(1, 1, "Mois"))
    lines.append(_cell(1, 2, "Jour"))
    lines.append(_cell(1, 3, "Heure"))
    lines.append(_cell(1, 4, "Températures"))
    lines.append(_cell(1, 5, "Température (°C)"))
    lines.append(_cell(1, 6, "Apports occupants (W)"))
    lines.append(_cell(2, 5, "Zone A"))
    lines.append(_cell(2, 6, "Zone A"))
    lines.append(_cell(3, 1, 1)); lines.append(_cell(3, 2, 1))
    lines.append(_cell(3, 3, 1)); lines.append(_cell(3, 4, 15.0))
    lines.append(_cell(3, 5, 20.0)); lines.append(_cell(3, 6, 100.0))
    lines.append("E\n")
    f = tmp_path / "sans_hr.slk"
    f.write_text("".join(lines), encoding="latin-1")
    return f


@pytest.fixture
def synthese_sans_besoins(tmp_path):
    """Fichier synthèse sans en-tête 'Besoins' → doit lever FichierInvalideError."""
    lines = [_slk_header()]
    lines.append(_cell(1, 1, "Zones"))
    lines.append(_cell(2, 2, "Puissance"))  # pas de "Besoin"
    lines.append(_cell(4, 1, "Zone A"))
    lines.append(_cell(4, 2, 1000.0))
    lines.append("E\n")
    f = tmp_path / "bad_synthese.slk"
    f.write_text("".join(lines), encoding="latin-1")
    return f


# ---------------------------------------------------------------------------
# Tests parse_resultats
# ---------------------------------------------------------------------------

def test_resultats_colonnes_de_base(resultats_1zone):
    df = parse_resultats(resultats_1zone)
    assert set(df.columns) >= {"mois", "jour", "heure", "T_ext"}


def test_resultats_nombre_lignes(resultats_1zone):
    df = parse_resultats(resultats_1zone)
    assert len(df) == 3


def test_resultats_t_ext(resultats_1zone):
    df = parse_resultats(resultats_1zone)
    assert df["T_ext"].iloc[0] == pytest.approx(15.0)
    assert df["T_ext"].iloc[1] == pytest.approx(16.0)


def test_resultats_zones_detectees(resultats_1zone):
    df = parse_resultats(resultats_1zone)
    assert df.attrs["zones"] == ["Séjour"]


def test_resultats_2zones_detectees(resultats_2zones):
    df = parse_resultats(resultats_2zones)
    assert set(df.attrs["zones"]) == {"Séjour", "Chambre"}


def test_resultats_colonne_temperature_zone(resultats_1zone):
    df = parse_resultats(resultats_1zone)
    col = "Température (°C)|Séjour"
    assert col in df.columns
    assert df[col].iloc[0] == pytest.approx(20.0)


def test_resultats_colonne_hr_zone(resultats_1zone):
    df = parse_resultats(resultats_1zone)
    col = "Humidité relative (%)|Séjour"
    assert col in df.columns
    assert df[col].iloc[0] == pytest.approx(50.0)


def test_resultats_occupation(resultats_1zone):
    """Apports occupants alternent 0/100 → occupation déduite correctement."""
    df = parse_resultats(resultats_1zone)
    col = "Apports occupants (W)|Séjour"
    assert col in df.columns
    # Ligne 0 : r=0 → 100 * (0 % 2) = 0
    assert df[col].iloc[0] == pytest.approx(0.0)
    # Ligne 1 : r=1 → 100 * (1 % 2) = 100
    assert df[col].iloc[1] == pytest.approx(100.0)


def test_resultats_invalide_sans_hr(resultats_sans_hr):
    with pytest.raises(FichierInvalideError, match="Humidité relative"):
        parse_resultats(resultats_sans_hr)


# ---------------------------------------------------------------------------
# Tests parse_synthese
# ---------------------------------------------------------------------------

def test_synthese_zones(synthese_2zones):
    df = parse_synthese(synthese_2zones)
    assert set(df["zone"]) == {"Séjour", "Chambre"}


def test_synthese_besoins_chaud(synthese_2zones):
    df = parse_synthese(synthese_2zones).set_index("zone")
    assert df.loc["Séjour", "besoins_chaud_kwh"] == pytest.approx(500.0)
    assert df.loc["Chambre", "besoins_chaud_kwh"] == pytest.approx(1000.0)


def test_synthese_besoins_froid(synthese_2zones):
    df = parse_synthese(synthese_2zones).set_index("zone")
    assert df.loc["Séjour", "besoins_froid_kwh"] == pytest.approx(200.0)


def test_synthese_surface(synthese_2zones):
    df = parse_synthese(synthese_2zones).set_index("zone")
    assert df.loc["Séjour", "surface_m2"] == pytest.approx(20.0)
    assert df.loc["Chambre", "surface_m2"] == pytest.approx(20.0)


def test_synthese_temperatures(synthese_2zones):
    df = parse_synthese(synthese_2zones).set_index("zone")
    assert df.loc["Séjour", "t_min"] == pytest.approx(-3.0)
    assert df.loc["Séjour", "t_moy"] == pytest.approx(19.0)
    assert df.loc["Séjour", "t_max"] == pytest.approx(35.0)


def test_synthese_heures_inconfort(synthese_2zones):
    df = parse_synthese(synthese_2zones).set_index("zone")
    assert df.loc["Séjour", "heures_inconfort"] == pytest.approx(400.0)


def test_synthese_invalide_sans_besoins(synthese_sans_besoins):
    with pytest.raises(FichierInvalideError):
        parse_synthese(synthese_sans_besoins)


# ---------------------------------------------------------------------------
# Test parse_slk_auto
# ---------------------------------------------------------------------------

@pytest.fixture
def resultats_large(tmp_path):
    """Fixture résultats avec >500 colonnes Y1 pour tromper _detecter_type correctement."""
    nz = 1
    lines = [_slk_header()]
    # Colonnes de base (1-3 + T_ext + grandeurs zone)
    lines.append(_cell(1, 1, "Mois"))
    lines.append(_cell(1, 2, "Jour"))
    lines.append(_cell(1, 3, "Heure"))
    lines.append(_cell(1, 4, "Températures"))
    lines.append(_cell(1, 5, "Température (°C)"))
    lines.append(_cell(1, 6, "Humidité relative (%)"))
    lines.append(_cell(1, 7, "Apports occupants (W)"))
    # Rembourrage pour dépasser 500 colonnes (simule les ~1500 cols réelles)
    for c in range(8, 502):
        lines.append(_cell(1, c, "Conso éclairage (kWh)"))
    lines.append(_cell(2, 5, "Zone A"))
    lines.append(_cell(2, 6, "Zone A"))
    lines.append(_cell(2, 7, "Zone A"))
    lines.append(_cell(3, 1, 1)); lines.append(_cell(3, 2, 1))
    lines.append(_cell(3, 3, 1)); lines.append(_cell(3, 4, 15.0))
    lines.append(_cell(3, 5, 20.0))
    lines.append(_cell(3, 6, 60.0))
    lines.append(_cell(3, 7, 100.0))
    lines.append("E\n")
    f = tmp_path / "resultats_large.slk"
    f.write_text("".join(lines), encoding="latin-1")
    return f


def test_auto_detecte_resultats(resultats_large):
    type_f, df = parse_slk_auto(resultats_large)
    assert type_f == "resultats"
    assert "T_ext" in df.columns


def test_auto_detecte_synthese(synthese_2zones):
    type_f, df = parse_slk_auto(synthese_2zones)
    assert type_f == "synthese"
    assert "zone" in df.columns
