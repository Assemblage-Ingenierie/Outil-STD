"""Export « annexe » : un maximum d'indicateurs et de graphiques des variantes
chargées, pour être repris dans un autre document.

Trois livrables, produits en une passe :
  - un .docx (A4 paysage, charte Assemblage) : titres Word natifs (volet de
    navigation, table des matières), tableaux et figures numérotés et légendés
    avec des champs SEQ (Word peut générer une table des illustrations) ;
  - un .xlsx : chaque tableau du Word en valeurs numériques brutes (un onglet par
    tableau, code T01, T02… identique à la légende du Word) + une feuille « Zones »
    consolidée (toutes variantes × toutes zones, format long, prête pour un TCD) ;
  - un .zip : chaque figure en PNG, nommée « F001 - <légende>.png ».

Structure (par thème) :
  1. Paramètres et variantes
  2. Bâtiment (une ligne par variante + graphiques comparatifs)
  3. Indicateurs par zone — TOUTES les zones de chaque variante (tableaux)
  4. Comparaison des zones détaillées (graphiques par variante)
  5. Fiches zone — zones détaillées uniquement (toutes variantes comparées)

Les graphiques sont rendus en mode clair, quel que soit le mode d'affichage écran ;
leur langue suit le réglage « Langue des graphiques ». Le texte du document reste
en français.
"""
from __future__ import annotations

import re
import warnings
import zipfile
from dataclasses import dataclass, field
from types import SimpleNamespace
from datetime import date
from io import BytesIO
from pathlib import Path
from typing import Callable

import numpy as np
import pandas as pd
from docx import Document
from docx.enum.section import WD_ORIENT
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

from core.confort import vitesses_modele
from core.confort_en16798 import CATEGORIES

ASSETS_DIR = Path(__file__).parent.parent / 'assets'
LOGO_PATH = ASSETS_DIR / 'logos' / 'logo_Ai_rouge_HD.png'

C_ROUGE = RGBColor(0xE3, 0x05, 0x13)
C_VIOLET = RGBColor(0x30, 0x32, 0x3E)
C_NOIR70 = RGBColor(0x4D, 0x4D, 0x4D)
C_BLANC = RGBColor(0xFF, 0xFF, 0xFF)
POLICE = 'Open Sans'
ROMAIN = {1: 'I', 2: 'II', 3: 'III'}
NOMS_MOIS = ['Jan', 'Fév', 'Mar', 'Avr', 'Mai', 'Jun', 'Jul', 'Aoû', 'Sep', 'Oct', 'Nov', 'Déc']

# Page A4 paysage : zone utile pour les figures
LARGEUR_UTILE_CM = 25.5
HAUTEUR_FIG_MAX_CM = 15.5
# Rendu PNG
PX_LARGEUR = 1400
PX_HAUTEUR_DEFAUT = 700
ECHELLE_PNG = 2


@dataclass
class ResultatAnnexe:
    docx: BytesIO
    xlsx: BytesIO
    zip_png: BytesIO | None
    n_tableaux: int
    n_figures: int
    erreurs: list[str] = field(default_factory=list)


# ======================================================================
# Helpers Word bas niveau
# ======================================================================

def _shading(cell, hex_fill: str) -> None:
    tcPr = cell._tc.get_or_add_tcPr()
    for old in tcPr.findall(qn('w:shd')):
        tcPr.remove(old)
    shd = OxmlElement('w:shd')
    shd.set(qn('w:val'), 'clear')
    shd.set(qn('w:fill'), hex_fill)
    tcPr.append(shd)


def _repeter_entete(row) -> None:
    """Ligne d'en-tête répétée en haut de chaque page (tableaux longs)."""
    trPr = row._tr.get_or_add_trPr()
    el = OxmlElement('w:tblHeader')
    el.set(qn('w:val'), 'true')
    trPr.append(el)


def _champ(paragraph, instruction: str, texte_cache: str) -> None:
    """Insère un champ Word (SEQ, TOC…) avec sa valeur affichée en cache."""
    def _fld(typ):
        el = OxmlElement('w:fldChar')
        el.set(qn('w:fldCharType'), typ)
        return el
    r = paragraph.add_run()
    r._r.append(_fld('begin'))
    r = paragraph.add_run()
    instr = OxmlElement('w:instrText')
    instr.set(qn('xml:space'), 'preserve')
    instr.text = f' {instruction} '
    r._r.append(instr)
    r = paragraph.add_run()
    r._r.append(_fld('separate'))
    paragraph.add_run(texte_cache)
    r = paragraph.add_run()
    r._r.append(_fld('end'))


def _avec_index(df: pd.DataFrame) -> bool:
    """L'index porte-t-il de l'information (nommé, ou autre qu'un 0..n-1) ?"""
    if any(n is not None for n in df.index.names):
        return True
    return not (isinstance(df.index, pd.RangeIndex) and df.index.start == 0
                and df.index.step == 1)


def _texte_titre(s) -> str:
    """Titre Plotly → texte brut (balises HTML <br>, <b>… retirées)."""
    s = re.sub(r'<[^>]+>', ' ', str(s or ''))
    return re.sub(r'\s+', ' ', s).strip()


def _nom_fichier(s: str, n: int = 110) -> str:
    s = _texte_titre(s)
    s = re.sub(r'[\\/:*?"<>|]+', ' ', s)
    s = re.sub(r'\s+', ' ', s).strip(' .')
    return s[:n].rstrip(' .') or 'figure'


def _preparer_document(titre: str, nom_projet: str, version: str) -> Document:
    doc = Document()
    sec = doc.sections[0]
    sec.orientation = WD_ORIENT.LANDSCAPE
    sec.page_width, sec.page_height = Cm(29.7), Cm(21)
    sec.left_margin = sec.right_margin = Cm(2)
    sec.top_margin, sec.bottom_margin = Cm(2), Cm(1.5)

    st = doc.styles
    st['Normal'].font.name = POLICE
    st['Normal'].font.size = Pt(9)
    for nom, taille, couleur in (('Heading 1', 18, C_ROUGE), ('Heading 2', 14, C_VIOLET),
                                 ('Heading 3', 11, C_VIOLET), ('Title', 26, C_VIOLET)):
        s = st[nom]
        s.font.name = POLICE
        s.font.size = Pt(taille)
        s.font.color.rgb = couleur
        s.font.bold = nom != 'Title'
        rpr = s.element.get_or_add_rPr()
        fonts = rpr.find(qn('w:rFonts'))
        if fonts is not None:                       # supprime les polices de thème
            for a in ('w:asciiTheme', 'w:hAnsiTheme', 'w:eastAsiaTheme', 'w:cstheme'):
                fonts.attrib.pop(qn(a), None)
    cap = st['Caption']
    cap.font.name = POLICE
    cap.font.size = Pt(8)
    cap.font.italic = True
    cap.font.bold = False
    cap.font.color.rgb = C_NOIR70

    # Pied de page : projet + pagination
    p = sec.footer.paragraphs[0]
    p.text = f"{nom_projet or 'Projet'} — {titre} — page "
    _champ(p, 'PAGE', '1')
    for r in p.runs:
        r.font.size = Pt(7)
        r.font.color.rgb = C_NOIR70
    p.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    return doc


# ======================================================================
# Collecteur : écrit dans le Word ET mémorise pour l'Excel / le ZIP
# ======================================================================

class _Annexe:
    def __init__(self, doc: Document, format_fr: bool, graphiques: bool,
                 progression: Callable[[str], None] | None = None):
        self.doc = doc
        self.dec = ',' if format_fr else '.'
        self.milliers = ' ' if format_fr else ','     # espace fine insécable / virgule
        self.graphiques = graphiques
        self.progression = progression or (lambda _msg: None)
        self.tables: list[tuple[str, str, str, pd.DataFrame]] = []   # code, section, titre, df
        self.figures: list[tuple[str, str, str, bytes]] = []         # code, section, titre, png
        self.erreurs: list[str] = []
        self.section = ''

    # -- structure --------------------------------------------------------
    def titre(self, texte: str, niveau: int = 1, saut_page: bool = False) -> None:
        if saut_page:
            self.doc.add_page_break()
        self.doc.add_heading(texte, level=niveau)
        if niveau == 1:
            self.section = texte

    def note(self, texte: str) -> None:
        p = self.doc.add_paragraph()
        r = p.add_run(texte)
        r.font.size = Pt(8)
        r.font.color.rgb = C_NOIR70

    def _legende(self, etiquette: str, numero: int, texte: str):
        p = self.doc.add_paragraph(style='Caption')
        p.add_run(f'{etiquette} ')
        _champ(p, f'SEQ {etiquette} \\* ARABIC', str(numero))
        p.add_run(f' — {texte}')
        return p

    # -- tableaux ---------------------------------------------------------
    def _fmt(self, col: str, val) -> str:
        if val is None:
            return ''
        if isinstance(val, (bool, np.bool_)):
            return 'oui' if val else 'non'
        if isinstance(val, (int, np.integer)):
            return f'{int(val):,}'.replace(',', self.milliers)
        if isinstance(val, (float, np.floating)):
            if val != val:
                return 'NA'
            c = str(col)
            if '%' in c and 'HR' not in c:
                s = f'{val:.1f} %'
            elif (abs(val) >= 1000 or c.startswith(('H <', 'H >', 'HR', 'Heures', 'Nb'))
                  or any(k in c for k in ('(h)', '(kWh)', 'Occupation', '°C·h'))):
                s = f'{val:.0f}'
            else:
                s = f'{val:.1f}'
            entier, _, frac = s.partition('.')
            entier = f'{int(entier):,}'.replace(',', self.milliers) if entier.lstrip('-').isdigit()                 else entier
            return entier + (self.dec + frac if frac else '')
        return str(val)

    def tableau(self, titre: str, df: pd.DataFrame, excel: bool = True,
                texte_cellules: Callable | None = None) -> None:
        """Ajoute un tableau légendé (« Tableau N — titre ») ; l'index du DataFrame
        est rendu en premières colonnes s'il est nommé."""
        if df is None or df.empty:
            return
        num = len(self.tables) + 1
        code = f'T{num:02d}'
        self.tables.append((code, self.section, titre, df if excel else pd.DataFrame()))
        cap = self._legende('Tableau', num, titre)
        cap.paragraph_format.keep_with_next = True

        d = df.reset_index() if _avec_index(df) else df
        cols = [str(c) for c in d.columns]
        table = self.doc.add_table(rows=1, cols=len(cols))
        table.style = 'Table Grid'
        table.alignment = WD_TABLE_ALIGNMENT.CENTER
        taille = Pt(7 if len(cols) > 12 else 8)
        hdr = table.rows[0]
        _repeter_entete(hdr)
        for cell, name in zip(hdr.cells, cols):
            cell.text = ''
            r = cell.paragraphs[0].add_run(name)
            r.font.bold = True
            r.font.size = taille
            r.font.color.rgb = C_BLANC
            _shading(cell, 'E30513')
        fmt = texte_cellules or self._fmt
        textes = [[fmt(cols[j], val) for j, val in enumerate(row)]
                  for row in d.itertuples(index=False)]
        self._largeurs(table, cols, textes)
        for i, (row, txts) in enumerate(zip(d.itertuples(index=False), textes)):
            cells = table.add_row().cells
            for j, (cell, val, txt) in enumerate(zip(cells, row, txts)):
                r = cell.paragraphs[0].add_run(txt)
                r.font.size = taille
                if j > 0 and not isinstance(val, str):
                    cell.paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.RIGHT
                if i % 2 == 1:
                    _shading(cell, 'F2F2F2')
        self.doc.add_paragraph()

    @staticmethod
    def _largeurs(table, cols, textes) -> None:
        """Largeurs de colonnes proportionnelles au contenu (les colonnes texte,
        ex. noms de zone, ne sont plus coupées), dans la largeur utile."""
        def _long(j):
            mots = max((len(m) for m in cols[j].split()), default=4)
            return max([mots] + [len(r[j]) for r in textes[:300]])
        poids = [min(30, max(4, _long(j))) + 2.5 for j in range(len(cols))]   # + marges de cellule
        total = sum(poids)
        largeur = Cm(LARGEUR_UTILE_CM + 0.2)
        table.autofit = False
        for j, col in enumerate(table.columns):
            w = int(largeur * poids[j] / total)
            col.width = w
            for cell in col.cells:
                cell.width = w

    # -- figures ----------------------------------------------------------
    def figure(self, fig, titre: str | None = None) -> None:
        if not self.graphiques or fig is None or not len(fig.data):
            return
        if titre is None:
            t = fig.layout.title.text if fig.layout.title else None
            titre = _texte_titre(t) or 'Figure'
        h_px = int(fig.layout.height or PX_HAUTEUR_DEFAUT)
        try:
            png = fig.to_image(format='png', width=PX_LARGEUR, height=h_px, scale=ECHELLE_PNG)
        except Exception as e:      # une figure en échec ne bloque pas l'annexe
            self.erreurs.append(f'{titre} : {e}')
            return
        num = len(self.figures) + 1
        code = f'F{num:03d}'
        self.figures.append((code, self.section, titre, png))
        largeur = min(LARGEUR_UTILE_CM, HAUTEUR_FIG_MAX_CM * PX_LARGEUR / h_px)
        self.doc.add_picture(BytesIO(png), width=Cm(largeur))
        p = self.doc.paragraphs[-1]
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.paragraph_format.keep_with_next = True
        self._legende('Figure', num, titre).alignment = WD_ALIGN_PARAGRAPH.CENTER
        self.progression(f'Figure {num} : {titre}')


# ======================================================================
# Indicateurs (DataFrames numériques)
# ======================================================================

def _surface(var, zone) -> float:
    syn = var.synthese_zone(zone)
    s = syn.get('surface_m2', np.nan) if syn else np.nan
    return float(s) if s == s else np.nan


def _en16798_batiment(var, zones) -> dict:
    """Agrégat bâtiment EN 16798 : heures d'inconfort / heures évaluées, toutes
    zones confondues (même pondération que les « % hors » Givoni : par heures)."""
    out = {}
    for c in CATEGORIES:
        ev = disc = chaud = froid = 0
        for z in zones:
            r = var.en16798(z, c)
            if r is None:
                continue
            ev += r['total_occupied_valid']
            disc += r['discomfort_hours']
            chaud += r['discomfort_hours_warm']
            froid += r['discomfort_hours_cold']
        rom = ROMAIN[c]
        out[f'Heures évaluées Cat.{rom}'] = ev
        out[f'Inconfort Cat.{rom} (h)'] = disc
        out[f'dont chaud Cat.{rom} (h)'] = chaud
        out[f'dont froid Cat.{rom} (h)'] = froid
        out[f'% inconfort EN 16798 Cat.{rom}'] = (100.0 * disc / ev) if ev else np.nan
    return out


def _vit(v: float) -> str:
    """Vitesse d'air au format FR : 0 / 0,5 / 1 / 1,5 m/s."""
    return f"{v:g}".replace('.', ',') + ' m/s'


def _par_m2(x, surf) -> float:
    return x / surf if (x == x and surf == surf and surf > 0) else np.nan


def _ligne_thermique(var, zone, seuils) -> dict:
    """Besoins, températures, humidité, dépassements, degré-heures, puissances max."""
    t0, t1, t2 = seuils
    syn = var.synthese_zone(zone) or {}
    st_t, st_h = var.stats_temp(zone), var.stats_hr(zone)
    surf = _surface(var, zone)
    pmax = var.puissances_max(zone)
    return {
        'Surface (m²)': surf,
        'Besoins ch. (kWh)': syn.get('besoins_chaud_kwh', np.nan),
        'Besoins fr. (kWh)': syn.get('besoins_froid_kwh', np.nan),
        'Besoins ch. (kWh/m²)': syn.get('besoins_chaud_kwh_m2', np.nan),
        'Besoins fr. (kWh/m²)': syn.get('besoins_froid_kwh_m2', np.nan),
        'P max ch. (W)': pmax['chauffage'], 'P max ch. (W/m²)': _par_m2(pmax['chauffage'], surf),
        'P max fr. (W)': pmax['climatisation'],
        'P max fr. (W/m²)': _par_m2(pmax['climatisation'], surf),
        'T min (°C)': st_t['t_min'], 'T moy (°C)': st_t['t_moy'], 'T max (°C)': st_t['t_max'],
        'HR min (%)': st_h['hr_min'], 'HR moy (%)': st_h['hr_moy'], 'HR max (%)': st_h['hr_max'],
        f'H < {t0:g}°C': var.heures_sous_seuil(zone, t0),
        f'H > {t1:g}°C': var.heures_dessus_seuil(zone, t1),
        f'H > {t2:g}°C': var.heures_dessus_seuil(zone, t2),
        f'DH > {t1:g}°C (°C·h)': var.degre_heures(zone, t1),
        f'DH > {t2:g}°C (°C·h)': var.degre_heures(zone, t2),
    }


def _ligne_confort(var, zone, config, methode) -> dict:
    """Confort bioclimatique à TOUTES les vitesses d'air du modèle + EN 16798 I/II/III."""
    lib = 'COCO' if methode == 'coco' else 'Givoni'
    row = {'Occupation (h)': var.heures_occupation(zone)}
    exemptees = np.nan
    for vit in vitesses_modele(methode):
        d = var.confort_detail(zone, config, vit, methode)
        row[f'Hors {lib} {_vit(vit)} (h)'] = d['heures_hors']
        row[f'% hors {lib} {_vit(vit)}'] = d['pct']
        exemptees = d['heures_exemptees']
    row['Chauffe sous consigne écartée (h)'] = exemptees
    for c in CATEGORIES:
        r = var.en16798(zone, c)
        row[f'% EN 16798 Cat.{ROMAIN[c]}'] = r['discomfort_pct'] if r else np.nan
    return row


def _ligne_jour_nuit(var, zone, config, methode, jour_debut, jour_fin) -> dict:
    """% hors confort jour / nuit de la zone, à toutes les vitesses."""
    t = var.col_temp(zone)
    row = {}
    if t.empty:
        return row
    mj = var.masque_jour(len(t), jour_debut, jour_fin)
    for vit in vitesses_modele(methode):
        for plage, m in (('jour', mj), ('nuit', ~mj)):
            row[f'% hors {plage} {_vit(vit)}'] = var.confort_detail(
                zone, config, vit, methode, masque_extra=m)['pct']
    return row


def _ligne_apports(var, zone) -> dict:
    surf = _surface(var, zone)
    row = {'Surface (m²)': surf}
    for k, val in var.apports_annuels(zone).items():
        row[f'Apports {k} (kWh)'] = val
    for k in ('solaires', 'internes'):
        row[f'Apports {k} (kWh/m²)'] = _par_m2(row[f'Apports {k} (kWh)'], surf)
    return row


def _confort_batiment(var, config, methode) -> dict:
    """Agrégat bâtiment, toutes vitesses : heures hors confort cumulées / heures
    d'occupation cumulées (même pondération que la synthèse : par heures)."""
    lib = 'COCO' if methode == 'coco' else 'Givoni'
    row = {}
    for vit in vitesses_modele(methode):
        occ = hors = exe = 0
        for z in var.zones:
            d = var.confort_detail(z, config, vit, methode)
            occ += d['heures_occ']
            hors += d['heures_hors']
            exe += d['heures_exemptees']
        row["Heures d'occupation (toutes zones)"] = occ
        row[f'Hors {lib} {_vit(vit)} (h)'] = hors
        row[f'% hors {lib} {_vit(vit)}'] = (100.0 * hors / occ) if occ else np.nan
        row['Chauffe sous consigne écartée (h)'] = exe
    return row


def _puissances_batiment(var) -> dict:
    """Puissances max simultanées du bâtiment (somme horaire des zones) et apports annuels."""
    out = {}
    for nom, col in (('chauffage', var.col_p_chaud), ('climatisation', var.col_p_froid)):
        series = [col(z).values for z in var.zones if not col(z).empty]
        out[f'P max simultanée {nom} (W)'] = np.nan
        if series:
            n = min(len(x) for x in series)
            tot = np.sum([x[:n] for x in series], axis=0)[var.masque_periode(n)]
            if tot.size:
                out[f'P max simultanée {nom} (W)'] = float(np.nanmax(tot))
    tot = {}
    for z in var.zones:
        for k, val in var.apports_annuels(z).items():
            if val == val:
                tot[k] = tot.get(k, 0.0) + val
    for k in ('solaires', 'éclairage', 'occupants', 'équipements', 'internes'):
        out[f'Apports {k} (kWh)'] = tot.get(k, np.nan)
    return out


def _lignes_periodes(var, zone, config, methode, periodes) -> list[dict]:
    """Inconfort par période de focus, à toutes les vitesses d'air."""
    lib = 'COCO' if methode == 'coco' else 'Givoni'
    par_vit = {vit: {r['periode']: r for r in var.inconfort_periodes(zone, config, periodes,
                                                                       methode, vit)}
               for vit in vitesses_modele(methode)}
    rows = []
    for p_ in periodes:
        nom = p_.get('nom', '')
        row = {'Variante': var.nom, 'Période': nom}
        for vit, rr in par_vit.items():
            r = rr.get(nom, {})
            row["Heures d'occupation"] = r.get('heures_occ', 0)
            row[f'Hors {lib} {_vit(vit)} (h)'] = r.get('heures_inconfort', 0)
            row[f'% hors {lib} {_vit(vit)}'] = r.get('pct', np.nan)
        rows.append(row)
    return rows


def _df_en16798_zones(var, zones, cat) -> pd.DataFrame:
    rows = []
    for z in zones:
        r = var.en16798(z, cat)
        if r is None:
            continue
        rows.append({'zone': z, 'surface': _surface(var, z),
                     'occupied': r['total_occupied'], 'evaluated': r['total_occupied_valid'],
                     'out_of_range': r['occupied_out_of_range'],
                     'discomfort_hours': r['discomfort_hours'],
                     'discomfort_pct': r['discomfort_pct'],
                     'discomfort_warm': r['discomfort_hours_warm'],
                     'discomfort_cold': r['discomfort_hours_cold']})
    return pd.DataFrame(rows)


def _renommer_en16798(df: pd.DataFrame, cat: int) -> pd.DataFrame:
    rom = ROMAIN[cat]
    return df.rename(columns={
        'zone': 'Zone', 'surface': 'Surface (m²)', 'occupied': 'Heures occupées',
        'evaluated': 'Heures évaluées', 'out_of_range': 'Heures θrm hors domaine',
        'discomfort_hours': f'Inconfort Cat.{rom} (h)',
        'discomfort_pct': f'% inconfort Cat.{rom}',
        'discomfort_warm': 'dont chaud (h)', 'discomfort_cold': 'dont froid (h)'})


def _apports_batiment(variantes, type_apport) -> pd.DataFrame:
    """Apports mensuels bâtiment (kWh) : somme des zones, une colonne par variante."""
    data = {}
    for v in variantes:
        tot = pd.Series(0.0, index=range(1, 13))
        for z in v.zones:
            s = v.apports_mensuels(z, type_apport)
            if len(s):
                tot = tot.add(s, fill_value=0.0)
        data[v.nom] = tot
    df = pd.DataFrame(data)
    df.index = [NOMS_MOIS[m - 1] for m in df.index]
    df.index.name = 'Mois'
    df.loc['Total'] = df.sum()
    return df


def _libelle_periode(var) -> str:
    if not getattr(var, 'periode', None):
        return 'Année entière'
    m1, m2 = var.periode
    return f'{NOMS_MOIS[m1 - 1]} → {NOMS_MOIS[m2 - 1]}'


# ======================================================================
# Point d'entrée
# ======================================================================

def estimer_figures(n_variantes: int, n_zones_detail: int, periodes_on: bool = False,
                    graphiques: bool = True) -> int:
    """Ordre de grandeur du nombre de figures (affiché avant génération)."""
    if not graphiques:
        return 0
    v, z = n_variantes, n_zones_detail
    bat = 7 + v                                      # synthèse + météo + barres EN 16798
    comp = 7 * v if z else 0
    fiche = 5 + (1 if v > 1 else 0) + 5 * v + (v if periodes_on else 0)
    return bat + comp + z * fiche


def generer_annexe(
    variantes: list,
    config: dict,
    *,
    seuil_t0: float = 18.0,
    seuil_t1: float = 26.0,
    seuil_t2: float = 28.0,
    zones_detail: list[str] | None = None,
    nom_projet: str = '',
    methode: str = 'givoni',
    categorie_en16798: int = 2,
    df_recap: pd.DataFrame | None = None,
    df_detail: pd.DataFrame | None = None,
    jour_debut: float = 7.0,
    jour_fin: float = 22.0,
    periodes_on: bool = False,
    periodes: list[dict] | None = None,
    format_fr: bool = True,
    dh_on: bool = False,
    inclure_graphiques: bool = True,
    par_saison: bool = True,
    progression: Callable[[float, str], None] | None = None,
) -> ResultatAnnexe:
    """Génère l'annexe (docx + xlsx + zip PNG). Voir la docstring du module."""
    from config.version import version_affichee
    import config.charte as charte

    cat = int(categorie_en16798) if int(categorie_en16798) in CATEGORIES else 2
    zones_detail = list(zones_detail or [])
    P = SimpleNamespace(
        variantes=list(variantes), config=config or {}, methode=methode, cat=cat,
        rom=ROMAIN[cat], lib='COCO' if methode == 'coco' else 'Givoni',
        noms=[v.nom for v in variantes], seuils=(seuil_t0, seuil_t1, seuil_t2),
        zones_detail=zones_detail, nom_projet=nom_projet, df_recap=df_recap,
        df_detail=df_detail, jour_debut=jour_debut, jour_fin=jour_fin,
        periodes=list(periodes or []) if periodes_on else [], dh_on=dh_on,
        graphiques=inclure_graphiques, par_saison=par_saison,
        note_chauffe=any(v.a_chauffage() for v in variantes),
        titre_doc='Annexe — résultats de simulation thermique dynamique',
        version=version_affichee(),
    )

    # Progression : figures estimées + blocs de tableaux
    total = max(1, estimer_figures(len(variantes), len(zones_detail), bool(P.periodes),
                                   inclure_graphiques) + len(variantes) + len(zones_detail) + 1)
    compteur = [0]

    def _avance(msg: str) -> None:
        compteur[0] += 1
        if progression:
            progression(min(0.99, compteur[0] / total), msg)

    doc = _preparer_document(P.titre_doc, nom_projet, P.version)
    A = _Annexe(doc, format_fr, inclure_graphiques, _avance)

    prev_dark = charte.is_dark()
    charte.set_dark_mode(False)
    serveur = False
    if inclure_graphiques:
        # Un seul navigateur headless pour toutes les figures (≈ 3× plus rapide).
        try:
            import kaleido
            kaleido.start_sync_server(silence_warnings=True)
            serveur = True
        except Exception:
            pass
    try:
        with warnings.catch_warnings():
            warnings.simplefilter('ignore', UserWarning)   # « kopts ignored if using a server »
            _contenu(A, P)
    finally:
        charte.set_dark_mode(prev_dark)
        if serveur:
            try:
                import kaleido
                kaleido.stop_sync_server(silence_warnings=True)
            except Exception:
                pass

    buf_docx = BytesIO()
    doc.save(buf_docx)
    buf_docx.seek(0)
    if progression:
        progression(1.0, 'Terminé')
    return ResultatAnnexe(docx=buf_docx, xlsx=_excel(A), zip_png=_zip(A) if A.figures else None,
                          n_tableaux=len(A.tables), n_figures=len(A.figures), erreurs=A.erreurs)


def _contenu(A: _Annexe, P: SimpleNamespace) -> None:
    """Corps du document (sections 1 à 5)."""
    from charts import synthese as gsyn
    from charts.temperature import (
        graphique_temp_horaire, graphique_text_vs_text_op, graphique_apports_solaires,
        graphique_meteo_comparaison, heatmap_temp_jour_heure, graphique_temp_min_moy_max,
        graphique_heures_depassement, graphique_apports_par_zone_mensuel,
        graphique_besoins_par_zone,
    )
    from charts.givoni import creer_givoni
    from charts.humidite import graphique_hr_horaire, heatmap_hr_jour_heure, graphique_hr_min_moy_max
    from charts.adaptatif import creer_scatter_adaptatif, creer_barres_en16798
    from config.i18n import t

    variantes, config, methode = P.variantes, P.config, P.methode
    cat, rom, lib, noms = P.cat, P.rom, P.lib, P.noms
    seuil_t0, seuil_t1, seuil_t2 = P.seuils
    zd = P.zones_detail
    doc = A.doc

    # ------------------------------------------------------------ couverture
    if LOGO_PATH.exists():
        doc.add_picture(str(LOGO_PATH), width=Cm(4))
    p = doc.add_paragraph(P.titre_doc, style='Title')
    p.paragraph_format.space_before = Pt(36)
    p = doc.add_paragraph()
    r = p.add_run(P.nom_projet or '')
    r.font.size = Pt(16)
    r.font.color.rgb = C_ROUGE
    A.note(f"Généré le {date.today():%d/%m/%Y} — Assemblage STD {P.version} — "
           f"{len(variantes)} variante(s) : {', '.join(noms)}")
    A.note("Tableaux et figures sont numérotés par des champs Word : dans Word, "
           "Références › Insérer une table des illustrations permet d'en dresser la liste. "
           "Les valeurs brutes de chaque tableau sont dans le classeur Excel joint "
           "(onglet = code du tableau, ex. T05) ; les figures en PNG dans l'archive ZIP "
           "(fichier = numéro de figure).")
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(18)
    _champ(p, 'TOC \\o "1-2" \\h \\z \\u',
           'Table des matières : clic droit › Mettre à jour les champs.')

    # ------------------------------------------- 1. paramètres et variantes
    A.titre('1. Paramètres et variantes', saut_page=True)
    seuils_cfg = config.get('seuils', {}) if isinstance(config, dict) else {}
    params = [
        ('Modèle de confort bioclimatique', lib),
        ('Seuil T0 (froid)', f'{seuil_t0:g} °C'),
        ('Seuils T1 / T2 (surchauffe)', f'{seuil_t1:g} °C / {seuil_t2:g} °C'),
        ('Bande de confort HR', f"{float(seuils_cfg.get('hr_confort_min', 40.0)):g} – "
                                f"{float(seuils_cfg.get('hr_confort_max', 70.0)):g} %"),
        ('Plage « jour »', f"[{P.jour_debut:.0f} h ; {P.jour_fin:.0f} h["),
        ("Période d'analyse", _libelle_periode(variantes[0]) if variantes else '—'),
        ('Catégorie EN 16798-1 retenue (graphiques)', f'Catégorie {rom}'),
        ('Périodes de focus', ', '.join(f"{p_.get('nom', '')} ({NOMS_MOIS[int(p_['m1']) - 1]}→"
                                        f"{NOMS_MOIS[int(p_['m2']) - 1]})" for p_ in P.periodes)
         if P.periodes else 'désactivées'),
        ("Vitesses d'air du modèle", ' / '.join(_vit(v_) for v_ in vitesses_modele(methode))),
        ('Zones détaillées (graphiques)', ', '.join(P.zones_detail) or 'aucune'),
    ]
    A.tableau('Paramètres de calcul', pd.DataFrame(params, columns=['Paramètre', 'Valeur']))

    rows = []
    for v in variantes:
        met = v.infos_meteo()
        rows.append({'Variante': v.nom, 'Fichier météo': met['Fichier météo'],
                     'Libellé météo': met['Libellé météo'],
                     'Origine météo': met['Origine météo'],
                     'T extérieure utilisée': met['T extérieure utilisée'],
                     'Nb zones': len(v.zones),
                     'Surface totale (m²)': np.nansum([_surface(v, z) for z in v.zones]),
                     'Heures simulées': len(v.df_horaire), 'Chauffée': v.a_chauffage()})
    A.tableau('Variantes chargées et fichier météo associé',
              pd.DataFrame(rows).set_index('Variante'))

    # Un fichier météo par ligne : où il se trouvait et quelles variantes l'utilisent
    fichiers = {}
    for v in variantes:
        if v.meteo_nom:
            f = fichiers.setdefault((v.meteo_nom, v.meteo_chemin), {
                'Fichier météo': v.meteo_nom, 'Libellé': v.meteo_label or '—',
                'Chemin au chargement': v.meteo_chemin or 'non renseigné', 'Variantes': []})
            f['Variantes'].append(v.nom)
    if fichiers:
        df_f = pd.DataFrame(fichiers.values())
        df_f['Variantes'] = df_f['Variantes'].str.join(', ')
        A.tableau('Fichiers météo utilisés', df_f)
    sans = [v.nom for v in variantes if not v.meteo_nom]
    if sans:
        A.note("Sans fichier météo .try : " + ', '.join(sans) + ". La température extérieure "
               "est alors lue dans les résultats Pléiades si la colonne est présente "
               "(cf. « T extérieure utilisée »).")

    df_recap, df_detail = P.df_recap, P.df_detail
    if df_recap is not None and not df_recap.empty:
        A.tableau('Améliorations par variante', df_recap,
                  texte_cellules=lambda c, v: ('✕' if v else '') if isinstance(v, (bool, np.bool_))
                  else A._fmt(c, v))
    if df_detail is not None and not df_detail.empty:
        A.tableau('Descriptif des améliorations', df_detail.reset_index(drop=True))

    # --------------------------------------------------------- 2. bâtiment
    A.titre('2. Bâtiment', saut_page=True)
    rows = []
    for v in variantes:
        ind = v.indicateurs_batiment(config, methode, seuil_t0=seuil_t0,
                                     seuil_t1=seuil_t1, seuil_t2=seuil_t2)
        ind[f'DH > {seuil_t1:g}°C (°C·h)'] = v.dh_batiment(seuil_t1)
        ind[f'DH > {seuil_t2:g}°C (°C·h)'] = v.dh_batiment(seuil_t2)
        rows.append({'Variante': v.nom, **ind})
    df_syn = pd.DataFrame(rows).set_index('Variante')    # (sert aussi aux graphiques)
    A.tableau('Synthèse bâtiment — une ligne par variante',
              df_syn[[c for c in df_syn.columns if not c.startswith('% hors')]])
    A.note("T moy / HR moy pondérées par la surface ; min / max = extrêmes toutes zones. "
           "H < / H > et DH : moyennes par zone, pondérées par la surface (DH = somme des "
           "écarts au-dessus du seuil sur les heures d'occupation).")

    rows = [{'Variante': v.nom, **_confort_batiment(v, config, methode)} for v in variantes]
    A.tableau(f"Confort {lib} du bâtiment — toutes vitesses d'air",
              pd.DataFrame(rows).set_index('Variante'))
    A.note(f"Heures d'occupation hors zone de confort {lib}, toutes zones cumulées. Les "
           "heures de chauffe sous la consigne (T < borne basse de confort, local chauffé) "
           "sont considérées confortables et écartées du décompte.")

    vits = tuple(vitesses_modele(methode))
    rows_dn = [{'Variante': v.nom, **v.inconfort_plages_horaires(
        config, methode, P.jour_debut, P.jour_fin, vitesses=vits)} for v in variantes]
    df_dn = pd.DataFrame(rows_dn).set_index('Variante')
    A.tableau(f"Inconfort {lib} par plage horaire (jour / nuit) — toutes vitesses d'air", df_dn)
    A.note("Moyenne des % par zone pondérée par la surface utile.")

    rows_en = [{'Variante': v.nom, **_en16798_batiment(v, v.zones)} for v in variantes]
    A.tableau('Confort adaptatif EN 16798-1 — bâtiment, catégories I / II / III',
              pd.DataFrame(rows_en).set_index('Variante'))

    rows = [{'Variante': v.nom, **_puissances_batiment(v)} for v in variantes]
    A.tableau('Puissances maximales et apports annuels du bâtiment',
              pd.DataFrame(rows).set_index('Variante'))
    A.note("P max simultanée : maximum horaire de la somme des puissances de toutes les zones.")

    for typ, lab in (('solaires', 'solaires'), ('internes', 'internes (éclairage + occupants + équipements)')):
        A.tableau(f'Apports {lab} mensuels du bâtiment (kWh)', _apports_batiment(variantes, typ))
    A.progression('Tableaux bâtiment')

    df_g = df_syn.reset_index()
    A.figure(gsyn.graphique_besoins(df_g, noms))
    A.figure(gsyn.graphique_temperatures(df_g, noms))
    A.figure(gsyn.graphique_heures_depassement_batiment(df_g, noms, seuil_t0, seuil_t1, seuil_t2))
    A.figure(gsyn.graphique_humidite(df_g, noms))
    A.figure(gsyn.graphique_part_inconfort(df_g, noms))
    A.figure(gsyn.graphique_inconfort_jour_nuit(df_dn, noms))
    if any(v.a_meteo() for v in variantes):
        A.figure(graphique_meteo_comparaison(variantes))

    # ------------------------------------------- 3. indicateurs par zone
    A.titre('3. Indicateurs par zone (toutes zones)', saut_page=True)
    A.note("Une ligne par zone, pour chaque variante. « NA » : grandeur indisponible "
           "(zone inoccupée, colonne absente des résultats ou T extérieure manquante). "
           "Toutes les données par zone, y compris le confort jour / nuit, l'EN 16798 détaillé, "
           "les apports mensuels et les périodes de focus, sont dans le classeur Excel "
           "(onglets Zones, Zones_EN16798, Zones_mensuel, Zones_periodes).")
    for i, v in enumerate(variantes):
        if i:
            doc.add_page_break()
        A.titre(v.nom, 2)
        blocs = (('Indicateurs thermiques par zone', lambda z: _ligne_thermique(v, z, P.seuils)),
                 (f'Confort {lib} et EN 16798 par zone',
                  lambda z: _ligne_confort(v, z, config, methode)),
                 ('Apports annuels par zone', lambda z: _ligne_apports(v, z)))
        for titre_t, fn in blocs:
            df_z = pd.DataFrame([{'Zone': z, **fn(z)} for z in v.zones]).set_index('Zone')
            A.tableau(f'{titre_t} — {v.nom}', df_z, excel=False)
        df_en = _df_en16798_zones(v, v.zones, cat)
        if not df_en.empty:
            A.tableau(f'EN 16798-1 Cat. {rom} par zone — {v.nom}',
                      _renommer_en16798(df_en, cat).set_index('Zone'))
            A.figure(creer_barres_en16798(df_en, cat, v.nom))
        A.progression(f'Zones — {v.nom}')

    # ---------------------------------- 4. comparaison des zones détaillées
    if zd and P.graphiques:
        A.titre('4. Comparaison des zones détaillées', saut_page=True)
        for i, v in enumerate(variantes):
            zv = [z for z in zd if z in v.zones]
            if not zv:
                continue
            if i:
                doc.add_page_break()
            A.titre(v.nom, 2)
            A.figure(graphique_temp_min_moy_max([v], zv))
            A.figure(graphique_hr_min_moy_max([v], zv))
            A.figure(graphique_heures_depassement([v], zv, seuil_t1, seuil_t2))
            A.figure(graphique_besoins_par_zone(v, zv))
            A.figure(graphique_apports_par_zone_mensuel(v, zv, type_apport='solaires'))
            A.figure(graphique_apports_par_zone_mensuel(v, zv, type_apport='internes'))

    # ------------------------------------------------------- 5. fiches zone
    if zd:
        A.titre('5. Fiches zone', saut_page=True)
    hr_min = float(seuils_cfg.get('hr_confort_min', 40.0))
    hr_max = float(seuils_cfg.get('hr_confort_max', 70.0))
    for k, zone in enumerate(zd):
        if k:
            doc.add_page_break()
        A.titre(zone, 2)
        vz = [v for v in variantes if zone in v.zones]
        if not vz:
            A.note('Zone absente de toutes les variantes.')
            continue

        rows = [{'Variante': v.nom, 'Météo': v.meteo_trace(), **_ligne_thermique(v, zone, P.seuils)}
                for v in vz]
        A.tableau(f'Comparatif des variantes — thermique — {zone}',
                  pd.DataFrame(rows).set_index('Variante'))
        rows = [{'Variante': v.nom, **_ligne_confort(v, zone, config, methode),
                 **_ligne_jour_nuit(v, zone, config, methode, P.jour_debut, P.jour_fin)}
                for v in vz]
        A.tableau(f'Comparatif des variantes — confort {lib} et EN 16798 — {zone}',
                  pd.DataFrame(rows).set_index('Variante'))

        rows = []
        for v in vz:
            for c in CATEGORIES:
                r = v.en16798(zone, c)
                if r is None:
                    continue
                rows.append({'Variante': v.nom, 'Catégorie': ROMAIN[c],
                             'Heures occupées': r['total_occupied'],
                             'Heures évaluées': r['total_occupied_valid'],
                             'Heures θrm hors domaine': r['occupied_out_of_range'],
                             'Inconfort (h)': r['discomfort_hours'],
                             'dont chaud (h)': r['discomfort_hours_warm'],
                             'dont froid (h)': r['discomfort_hours_cold'],
                             '% inconfort': r['discomfort_pct']})
        if rows:
            A.tableau(f'EN 16798-1 par catégorie — {zone}',
                      pd.DataFrame(rows).set_index(['Variante', 'Catégorie']))

        if P.periodes:
            rows = []
            for v in vz:
                rows += _lignes_periodes(v, zone, config, methode, P.periodes)
            A.tableau(f'Inconfort {lib} par période de focus — {zone}',
                      pd.DataFrame(rows).set_index(['Variante', 'Période']))
        A.progression(f'Fiche {zone}')

        if not P.graphiques:
            continue

        A.titre('Températures', 3)
        A.figure(graphique_temp_horaire(vz, zone, seuil_t1, seuil_t2))
        stats = [v.stats_temp(zone) for v in vz]
        tmins = [s['t_min'] for s in stats if s['t_min'] == s['t_min']]
        tmaxs = [s['t_max'] for s in stats if s['t_max'] == s['t_max']]
        for v in vz:
            A.figure(heatmap_temp_jour_heure(v, zone, zmin=min(tmins) if tmins else None,
                                                  zmax=max(tmaxs) if tmaxs else None))
        A.figure(graphique_text_vs_text_op(vz, zone, par_saison=P.par_saison))

        A.titre(f'Confort bioclimatique ({lib})', 3)
        series = []
        for v in vz:
            pts = v.points_interieurs_givoni(zone, config, methode)
            if len(pts['T']):
                pts['label'] = v.nom
                series.append(pts)
        if len(series) > 1:
            A.figure(creer_givoni(series, config=config, methode=methode,
                                  titre=t("Diagramme de {nom} — {zone} (toutes variantes)",
                                          nom=lib, zone=zone),
                                  par_saison=P.par_saison, note_chauffe=P.note_chauffe))
        for s in series:
            A.figure(creer_givoni([s], config=config, methode=methode,
                                  titre=t("Diagramme de {nom} — {zone} · {variante}",
                                          nom=lib, zone=zone, variante=s['label']),
                                  par_saison=P.par_saison, note_chauffe=P.note_chauffe))
        if P.periodes:
            for v in vz:
                pts = v.points_interieurs_par_periode(zone, config, P.periodes, methode)
                if not len(pts['T']):
                    continue
                pts['label'] = v.nom
                A.figure(creer_givoni([pts], config=config, methode=methode,
                                      titre=t("Diagramme de {nom} — {zone} · {variante} (par période)",
                                              nom=lib, zone=zone, variante=v.nom),
                                      par_periode=True, note_chauffe=P.note_chauffe))

        dispo = [v for v in vz if v.en16798(zone, cat) is not None]
        if dispo:
            A.titre(f'Confort adaptatif EN 16798-1 (Cat. {rom})', 3)
            for v in dispo:
                res = v.en16798(zone, cat)
                p = res['discomfort_pct']
                pct = (f'{p:.1f} %'.replace('.', A.dec)) if p == p else 'NA'
                titre = t("{zone} — {variante} — EN 16798-1 Cat. {c} : {pct} d'inconfort",
                          zone=zone, variante=v.nom, c=rom, pct=pct)
                A.figure(creer_scatter_adaptatif(
                    [{'label': v.nom, 'res': res, 't_int': v.col_temp(zone),
                      'horodatage': v.horodatage()}], titre))

        if any(not v.col_hr(zone).empty for v in vz):
            A.titre('Humidité relative', 3)
            A.figure(graphique_hr_horaire(vz, zone, hr_min=hr_min, hr_max=hr_max,
                                               agregation='journalier'))
            for v in vz:
                A.figure(heatmap_hr_jour_heure(v, zone))

        A.titre('Apports', 3)
        A.figure(graphique_apports_solaires(vz, zone, type_apport='solaires'))
        A.figure(graphique_apports_solaires(vz, zone, type_apport='internes'))

    # Feuilles Excel consolidées (format long) : toutes variantes × toutes zones
    A.progression('Feuilles Excel détaillées')
    zones, en, mens, per = [], [], [], []
    for v in variantes:
        tete = {'Variante': v.nom, 'Fichier météo': v.meteo_nom or '',
                'Libellé météo': v.meteo_label or ''}
        for z in v.zones:
            ap = _ligne_apports(v, z)
            ap.pop('Surface (m²)')
            zones.append({**tete, 'Zone': z, **_ligne_thermique(v, z, P.seuils),
                          **_ligne_confort(v, z, config, methode),
                          **_ligne_jour_nuit(v, z, config, methode, P.jour_debut, P.jour_fin),
                          **ap})
            for c in CATEGORIES:
                r = v.en16798(z, c)
                if r is not None:
                    en.append({'Variante': v.nom, 'Zone': z, 'Catégorie': ROMAIN[c],
                               'Heures occupées': r['total_occupied'],
                               'Heures évaluées': r['total_occupied_valid'],
                               'Heures θrm hors domaine': r['occupied_out_of_range'],
                               'Inconfort (h)': r['discomfort_hours'],
                               'dont chaud (h)': r['discomfort_hours_warm'],
                               'dont froid (h)': r['discomfort_hours_cold'],
                               '% inconfort': r['discomfort_pct']})
            sol, inte = v.apports_mensuels(z, 'solaires'), v.apports_mensuels(z, 'internes')
            for m in sorted(set(sol.index) | set(inte.index)):
                mens.append({'Variante': v.nom, 'Zone': z, 'Mois': int(m),
                             'Mois (libellé)': NOMS_MOIS[int(m) - 1],
                             'Apports solaires (kWh)': sol.get(m, np.nan),
                             'Apports internes (kWh)': inte.get(m, np.nan)})
            if P.periodes:
                per += [{'Zone': z, **r_} for r_ in _lignes_periodes(v, z, config, methode, P.periodes)]
    A.feuilles = {
        'Zones': ('Toutes variantes × toutes zones : thermique, confort (toutes vitesses, '
                  'jour / nuit), EN 16798, apports', pd.DataFrame(zones)),
        'Zones_EN16798': ('EN 16798-1 détaillé : toutes zones × catégories I / II / III',
                          pd.DataFrame(en)),
        'Zones_mensuel': ('Apports mensuels par zone (kWh)', pd.DataFrame(mens)),
    }
    if per:
        df_per = pd.DataFrame(per)
        cols = ['Variante', 'Zone'] + [c for c in df_per.columns if c not in ('Variante', 'Zone')]
        A.feuilles['Zones_periodes'] = (f'Inconfort {lib} par période de focus, toutes zones '
                                        "et vitesses d'air", df_per[cols])


# ======================================================================
# Excel / ZIP
# ======================================================================

def _excel(A: _Annexe) -> BytesIO:
    buf = BytesIO()
    sommaire = [{'Code': c, 'Section': s, 'Titre': ti, 'Onglet': c if not df.empty else 'Zones'}
                for c, s, ti, df in A.tables]
    feuilles = getattr(A, 'feuilles', {})
    for i, (nom, (titre, _df)) in enumerate(feuilles.items()):
        sommaire.insert(i, {'Code': nom, 'Section': 'Données détaillées (format long, pour TCD)',
                            'Titre': titre, 'Onglet': nom})
    figures = [{'Code': c, 'Section': s, 'Titre': ti, 'Fichier PNG': f'{c} - {_nom_fichier(ti)}.png'}
               for c, s, ti, _png in A.figures]
    with pd.ExcelWriter(buf, engine='openpyxl') as xw:
        pd.DataFrame(sommaire).to_excel(xw, sheet_name='Sommaire', index=False)
        for nom, (_titre, df) in feuilles.items():
            df.to_excel(xw, sheet_name=nom, index=False)
        for c, _s, _ti, df in A.tables:
            if df.empty:
                continue
            df.to_excel(xw, sheet_name=c, index=_avec_index(df))
        if figures:
            pd.DataFrame(figures).to_excel(xw, sheet_name='Figures', index=False)
        for ws in xw.book.worksheets:          # largeur de colonnes lisible
            for col in ws.columns:
                n = max((len(str(c.value)) for c in col if c.value is not None), default=8)
                ws.column_dimensions[col[0].column_letter].width = min(60, max(8, n + 2))
            ws.freeze_panes = ('A2' if ws.title in ('Sommaire', 'Figures')
                               else 'E2' if ws.title == 'Zones'
                               else 'C2' if ws.title in feuilles else 'B2')
    buf.seek(0)
    return buf


def _zip(A: _Annexe) -> BytesIO:
    buf = BytesIO()
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_STORED) as zf:   # PNG déjà compressés
        for code, _s, titre, png in A.figures:
            zf.writestr(f'{code} - {_nom_fichier(titre)}.png', png)
    buf.seek(0)
    return buf
