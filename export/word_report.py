"""Génération du rapport Word selon la charte Assemblage ingénierie."""
from __future__ import annotations
from pathlib import Path
from io import BytesIO
import tempfile
import os

from docx import Document
from docx.shared import Pt, Cm, RGBColor, Inches
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.oxml import OxmlElement
import plotly.graph_objects as go


# Chemins assets
ASSETS_DIR = Path(__file__).parent.parent / 'assets'
LOGO_PATH = ASSETS_DIR / 'logos' / 'logo_Ai_rouge_HD.png'
SIGLE_PATH = ASSETS_DIR / 'sigles' / 'sigle_A_rouge_HD.png'

# Couleurs charte
C_ROUGE = RGBColor(0xE3, 0x05, 0x13)
C_VIOLET = RGBColor(0x30, 0x32, 0x3E)
C_GRIS_CLAIR = RGBColor(0xDF, 0xE4, 0xE8)
C_ROUGE_CLAIR = RGBColor(0xF9, 0xE1, 0xE3)
C_GRIS_TC = RGBColor(0xF2, 0xF2, 0xF2)
C_BLANC = RGBColor(0xFF, 0xFF, 0xFF)
C_NOIR70 = RGBColor(0x4D, 0x4D, 0x4D)


def _set_cell_bg(cell, rgb: tuple[int, int, int]):
    tc = cell._tc
    tcPr = tc.get_or_add_tcPr()
    shd = OxmlElement('w:shd')
    shd.set(qn('w:fill'), '{:02X}{:02X}{:02X}'.format(*rgb))
    shd.set(qn('w:val'), 'clear')
    tcPr.append(shd)


def _para_rouge(doc: Document, text: str, level: int = 1) -> None:
    sizes = {1: 28, 2: 18, 3: 14}
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(24 if level == 1 else 16 if level == 2 else 10)
    p.paragraph_format.space_after = Pt(12 if level == 1 else 8 if level == 2 else 6)
    run = p.add_run(text)
    run.bold = True
    run.font.size = Pt(sizes.get(level, 14))
    run.font.color.rgb = C_ROUGE if level == 1 else C_VIOLET
    run.font.name = 'Open Sans'


def _fig_to_image(fig: go.Figure) -> BytesIO:
    """Exporte une figure Plotly en PNG dans un buffer."""
    buf = BytesIO()
    fig.write_image(buf, format='png', width=1400, height=700, scale=2)
    buf.seek(0)
    return buf


def generer_rapport(
    variantes: list,
    config: dict,
    seuil_t1: float,
    seuil_t2: float,
    zones_focus: list[str] | None = None,
    zones_comparaison: list[str] | None = None,
    nom_projet: str = "Projet STD",
    methode: str = "givoni",
) -> BytesIO:
    """
    Génère le rapport Word complet selon la trame fixe:
      1. Page de couverture
      2. Synthèse générale (tableau par variante)
      3. Focus zones sélectionnées (Givoni + graphiques)
      4. Comparaison de zones
    """
    from charts.temperature import (
        graphique_heures_depassement,
        graphique_temp_min_moy_max,
        graphique_apports_solaires,
        graphique_apports_par_zone_mensuel,
        graphique_temp_horaire,
        graphique_text_vs_text_op,
    )
    from charts.givoni import creer_givoni

    doc = Document()

    # -- Marges A4 --
    section = doc.sections[0]
    section.page_width = Cm(21)
    section.page_height = Cm(29.7)
    section.left_margin = Cm(1.5)
    section.right_margin = Cm(1.5)
    section.top_margin = Cm(3)
    section.bottom_margin = Cm(1.5)

    # -- Couverture --
    if LOGO_PATH.exists():
        doc.add_picture(str(LOGO_PATH), width=Inches(1.57))
        doc.paragraphs[-1].alignment = WD_ALIGN_PARAGRAPH.LEFT

    titre_p = doc.add_paragraph()
    titre_p.paragraph_format.space_before = Pt(48)
    run_titre = titre_p.add_run(config.get('rapport', {}).get('titre', 'Étude Thermique Dynamique'))
    run_titre.font.size = Pt(24)
    run_titre.font.name = 'Open Sans'
    run_titre.font.color.rgb = C_VIOLET

    sous_titre = doc.add_paragraph(nom_projet)
    sous_titre.runs[0].font.size = Pt(16)
    sous_titre.runs[0].font.color.rgb = C_ROUGE

    doc.add_page_break()

    # -- 1. Synthèse générale --
    _para_rouge(doc, "1. Synthèse générale", level=1)

    for var in variantes:
        _para_rouge(doc, f"Variante : {var.nom}", level=2)
        df_table = var.tableau_synthese_global(seuil_t1, seuil_t2, config=config, methode=methode)
        if df_table.empty:
            doc.add_paragraph("Aucune donnée disponible.")
            continue

        cols = list(df_table.columns)
        table = doc.add_table(rows=1 + len(df_table), cols=len(cols))
        table.style = 'Table Grid'

        # En-tête
        for j, col_name in enumerate(cols):
            cell = table.rows[0].cells[j]
            cell.text = col_name
            _set_cell_bg(cell, (0xE3, 0x05, 0x13))
            run = cell.paragraphs[0].runs[0]
            run.font.color.rgb = C_BLANC
            run.font.bold = True
            run.font.size = Pt(8)
            run.font.name = 'Open Sans'

        # Données
        for i, row in df_table.iterrows():
            for j, (col_name, val) in enumerate(row.items()):
                cell = table.rows[i+1].cells[j]
                # Formatage : NaN -> '—', colonnes '% hors' -> 'xx.x %'
                if isinstance(val, float) and val != val:      # NaN
                    txt = '—'
                elif col_name.startswith('% hors') and isinstance(val, (int, float)):
                    txt = f"{val:.1f} %"
                else:
                    txt = str(val)
                cell.text = txt
                run = cell.paragraphs[0].runs[0] if cell.paragraphs[0].runs else cell.paragraphs[0].add_run(txt)
                run.font.size = Pt(8)
                run.font.name = 'Open Sans'
                if i % 2 == 1:
                    _set_cell_bg(cell, (0xF2, 0xF2, 0xF2))

        doc.add_paragraph()

    # -- 2. Focus zones --
    if zones_focus and variantes:
        doc.add_page_break()
        _para_rouge(doc, "2. Focus zones", level=1)

        for zone in zones_focus:
            _para_rouge(doc, zone, level=2)

            # Série temporelle
            fig_temp = graphique_temp_horaire(variantes, zone, seuil_t1, seuil_t2)
            img = _fig_to_image(fig_temp)
            doc.add_picture(img, width=Cm(17))
            doc.paragraphs[-1].alignment = WD_ALIGN_PARAGRAPH.CENTER

            # T_op vs T_ext (première variante)
            fig_op = graphique_text_vs_text_op(variantes[0], zone)
            img2 = _fig_to_image(fig_op)
            doc.add_picture(img2, width=Cm(17))
            doc.paragraphs[-1].alignment = WD_ALIGN_PARAGRAPH.CENTER

            # Diagramme bioclimatique (Givoni / COCO, coloration par saison)
            if not variantes[0].df_meteo.empty:
                fig_giv = creer_givoni(
                    variantes[0].df_meteo, config=config, methode=methode,
                    saison=variantes[0].df_horaire.get('saison'),
                )
                img3 = _fig_to_image(fig_giv)
                doc.add_picture(img3, width=Cm(17))
                doc.paragraphs[-1].alignment = WD_ALIGN_PARAGRAPH.CENTER

            # Apports solaires + internes
            fig_sol = graphique_apports_solaires(variantes, zone, type_apport="solaires")
            doc.add_picture(_fig_to_image(fig_sol), width=Cm(17))
            doc.paragraphs[-1].alignment = WD_ALIGN_PARAGRAPH.CENTER
            fig_int = graphique_apports_solaires(variantes, zone, type_apport="internes")
            doc.add_picture(_fig_to_image(fig_int), width=Cm(17))
            doc.paragraphs[-1].alignment = WD_ALIGN_PARAGRAPH.CENTER

            doc.add_page_break()

    # -- 3. Comparaison zones --
    if zones_comparaison and variantes:
        _para_rouge(doc, "3. Comparaison de zones", level=1)
        var = variantes[0]

        fig_t = graphique_temp_min_moy_max([var], zones_comparaison)
        doc.add_picture(_fig_to_image(fig_t), width=Cm(17))
        doc.paragraphs[-1].alignment = WD_ALIGN_PARAGRAPH.CENTER

        fig_dep = graphique_heures_depassement([var], zones_comparaison, seuil_t1, seuil_t2)
        doc.add_picture(_fig_to_image(fig_dep), width=Cm(17))
        doc.paragraphs[-1].alignment = WD_ALIGN_PARAGRAPH.CENTER

        fig_sol = graphique_apports_par_zone_mensuel(var, zones_comparaison, type_apport="solaires")
        doc.add_picture(_fig_to_image(fig_sol), width=Cm(17))
        doc.paragraphs[-1].alignment = WD_ALIGN_PARAGRAPH.CENTER

    # Sauvegarder dans un buffer
    buf = BytesIO()
    doc.save(buf)
    buf.seek(0)
    return buf
