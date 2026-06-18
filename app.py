"""
Outil STD — Assemblage ingénierie
Application Streamlit d'analyse des données de simulation thermique dynamique Pléiades.
"""
import streamlit as st
import toml
from pathlib import Path

# -- Config page (doit être le premier appel Streamlit) --
st.set_page_config(
    page_title="Outil STD — Assemblage ingénierie",
    page_icon="🌡️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# -- Imports internes --
from views.synthese_generale import render_synthese_generale
from views.focus_zone import render_focus_zone
from views.comparaison_zones import render_comparaison_zones
from views.description_variantes import render_description_variantes
from views.reglages import render_reglages
from core.file_picker import choisir_fichier, enregistrer_fichier
from core import projet as projet_io

# -- Chemins --
BASE_DIR = Path(__file__).parent
ASSETS_DIR = BASE_DIR / 'assets'
CONFIG_DEFAULT = BASE_DIR / 'config' / 'projet_defaut.toml'

# -- CSS charte Assemblage --
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Open+Sans:wght@400;600;700&display=swap');

    html, body, [class*="css"] { font-family: 'Open Sans', sans-serif; }

    [data-testid="stSidebar"] {
        background-color: #30323E;
    }
    [data-testid="stSidebar"] * { color: #FFFFFF !important; }

    /* Texte saisi dans les champs (input/textarea) en noir sur fond blanc */
    [data-testid="stSidebar"] input,
    [data-testid="stSidebar"] textarea,
    [data-testid="stSidebar"] input::placeholder {
        color: #000000 !important;
        -webkit-text-fill-color: #000000 !important;
    }
    [data-testid="stSidebar"] input::placeholder,
    [data-testid="stSidebar"] textarea::placeholder {
        color: #888888 !important;
        -webkit-text-fill-color: #888888 !important;
    }
    /* Valeur sélectionnée et options des selectbox/multiselect en noir */
    [data-testid="stSidebar"] [data-baseweb="select"] *,
    [data-testid="stSidebar"] [data-baseweb="tag"] * {
        color: #000000 !important;
        -webkit-text-fill-color: #000000 !important;
    }

    h1, h2, h3 { font-family: 'Open Sans', sans-serif; }
    h1 { color: #E30513; }
    h2 { color: #30323E; }

    .stButton>button {
        background-color: #E30513;
        color: white;
        border: none;
        border-radius: 4px;
    }
    .stButton>button:hover { background-color: #B0040F; }
</style>
""", unsafe_allow_html=True)


# -- État de session --
if 'variantes' not in st.session_state:
    st.session_state.variantes = []
if 'config_projet' not in st.session_state:
    if CONFIG_DEFAULT.exists():
        st.session_state.config_projet = toml.load(CONFIG_DEFAULT)
    else:
        st.session_state.config_projet = {}
# Valeurs de configuration (éditées dans l'onglet Réglages, lues par les vues)
st.session_state.setdefault('cfg_seuil_t1', 26.0)
st.session_state.setdefault('cfg_seuil_t2', 28.0)
st.session_state.setdefault('cfg_methode', 'givoni')
st.session_state.setdefault('cfg_dh_on', False)
st.session_state.setdefault('cfg_nom_projet',
                            st.session_state.config_projet.get('projet', {}).get('nom', ''))

# Appliquer les libellés météo aux variantes (tableaux/graphiques/rapport)
_labels = st.session_state.get('meteo_labels', {})
for _v in st.session_state.variantes:
    _v.meteo_label = _labels.get(_v.meteo_nom, '')


# ============================================================
# SIDEBAR (minimale) : variantes chargées + projet
# ============================================================
with st.sidebar:
    logo_path = ASSETS_DIR / 'logos' / 'logo_Ai_blanc_HD.png'
    if logo_path.exists():
        st.image(str(logo_path), width=150)
    else:
        st.markdown("## Assemblage ingénierie")

    st.markdown("### 🏗️ Outil STD")
    st.caption("Réglages, ajout de variantes et export : onglet **Réglages**.")
    st.markdown("---")

    vs = st.session_state.variantes
    st.markdown("### Variantes chargées")
    if vs:
        st.caption("↑/↓ pour réordonner, ✕ pour retirer.")
        for i, var in enumerate(vs):
            c_nom, c_up, c_down, c_del = st.columns([5, 1, 1, 1])
            with c_nom:
                st.markdown(f"• {var.nom} ({len(var.zones)} zones)")
            with c_up:
                if st.button("↑", key=f"up_var_{i}", disabled=(i == 0), help="Monter"):
                    vs[i - 1], vs[i] = vs[i], vs[i - 1]
                    st.rerun()
            with c_down:
                if st.button("↓", key=f"down_var_{i}", disabled=(i == len(vs) - 1), help="Descendre"):
                    vs[i + 1], vs[i] = vs[i], vs[i + 1]
                    st.rerun()
            with c_del:
                if st.button("✕", key=f"del_var_{i}", help="Retirer"):
                    vs.pop(i)
                    st.rerun()
    else:
        st.caption("Aucune variante. Ajoutez-en dans l'onglet **Réglages**.")

    st.markdown("---")
    st.markdown("### 💾 Projet")
    cpa, cpb = st.columns(2)
    with cpa:
        if st.button("Enregistrer", key="btn_save_projet", use_container_width=True):
            if not st.session_state.variantes:
                st.warning("Aucune variante à enregistrer.")
            else:
                nomp = st.session_state.get('cfg_nom_projet', '') or "projet"
                chemin = enregistrer_fichier(
                    "Enregistrer le projet STD", [("Projet STD", "*.stdproj")],
                    extension_defaut=".stdproj", nom_defaut=nomp + ".stdproj")
                if chemin:
                    try:
                        etat = {
                            'nom_projet': st.session_state.get('cfg_nom_projet', ''),
                            'params': {'seuil_t1': st.session_state.get('cfg_seuil_t1'),
                                       'seuil_t2': st.session_state.get('cfg_seuil_t2'),
                                       'methode': st.session_state.get('cfg_methode'),
                                       'config': st.session_state.config_projet},
                            'variantes': st.session_state.variantes,
                            'ameliorations': st.session_state.get('ameliorations'),
                            'recap_vals': st.session_state.get('recap_vals'),
                            'meteo_labels': st.session_state.get('meteo_labels'),
                            'selections': {k: v for k, v in st.session_state.items()
                                           if k.startswith('sel_')},
                        }
                        p = projet_io.sauvegarder_projet(chemin, etat)
                        st.success(f"✅ Enregistré : {p.name}")
                    except Exception as e:
                        st.error(f"Erreur enregistrement : {e}")
    with cpb:
        if st.button("Ouvrir", key="btn_open_projet", use_container_width=True):
            chemin = choisir_fichier("Ouvrir un projet STD",
                                     [("Projet STD", "*.stdproj"), ("Tous", "*.*")])
            if chemin:
                try:
                    charge = projet_io.charger_projet(chemin)
                    st.session_state.variantes = charge['variantes']
                    st.session_state.config_projet = charge['params'].get(
                        'config', st.session_state.config_projet)
                    prm = charge.get('params', {})
                    if prm.get('seuil_t1') is not None:
                        st.session_state['cfg_seuil_t1'] = prm['seuil_t1']
                    if prm.get('seuil_t2') is not None:
                        st.session_state['cfg_seuil_t2'] = prm['seuil_t2']
                    if prm.get('methode'):
                        st.session_state['cfg_methode'] = prm['methode']
                    st.session_state['cfg_nom_projet'] = charge.get('nom_projet', '')
                    if charge.get('ameliorations') is not None:
                        st.session_state['ameliorations'] = charge['ameliorations']
                    if charge.get('recap_vals') is not None:
                        st.session_state['recap_vals'] = charge['recap_vals']
                    if charge.get('meteo_labels') is not None:
                        st.session_state['meteo_labels'] = charge['meteo_labels']
                    # Réinitialiser les widgets dont la base dépend des données chargées
                    for k in ('desc_base', 'recap_base', '_recap_sig', 'ed_desc', 'ed_recap',
                              'cfg_nom_projet_w', 'cfg_seuil_t1_w', 'cfg_seuil_t2_w',
                              'cfg_methode_label_w'):
                        st.session_state.pop(k, None)
                    for k, v in (charge.get('selections') or {}).items():
                        st.session_state[k] = v
                    st.success(f"✅ Projet ouvert : {charge.get('nom_projet', '')}")
                    st.rerun()
                except Exception as e:
                    st.error(f"Erreur ouverture : {e}")


# ============================================================
# ZONE PRINCIPALE — navigation par onglets
# ============================================================
variantes = st.session_state.variantes
config = st.session_state.config_projet
seuil_t1 = st.session_state.get('cfg_seuil_t1', 26.0)
seuil_t2 = st.session_state.get('cfg_seuil_t2', 28.0)
methode = st.session_state.get('cfg_methode', 'givoni')
dh_on = st.session_state.get('cfg_dh_on', False)

VUES = ["Synthèse générale", "Focus zone", "Comparaison zones", "Variantes", "Réglages"]
if hasattr(st, "segmented_control"):
    vue = st.segmented_control("Vue", VUES, default="Synthèse générale",
                               key="nav_vue", label_visibility="collapsed")
else:
    vue = st.radio("Vue", VUES, horizontal=True, key="nav_vue", label_visibility="collapsed")
if not vue:
    vue = "Synthèse générale"

if vue == "Synthèse générale":
    render_synthese_generale(variantes, seuil_t1, seuil_t2, config, methode, dh_on)
elif vue == "Focus zone":
    render_focus_zone(variantes, seuil_t1, seuil_t2, config, methode, dh_on)
elif vue == "Comparaison zones":
    render_comparaison_zones(variantes, seuil_t1, seuil_t2, config, methode, dh_on)
elif vue == "Variantes":
    render_description_variantes(variantes)
elif vue == "Réglages":
    render_reglages()
