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
from core.variante import charger_variante, Variante
from views.synthese_generale import render_synthese_generale
from views.focus_zone import render_focus_zone
from views.comparaison_zones import render_comparaison_zones

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
    [data-testid="stSidebar"] .stSelectbox label,
    [data-testid="stSidebar"] .stNumberInput label,
    [data-testid="stSidebar"] .stTextInput label,
    [data-testid="stSidebar"] .stFileUploader label { color: #FFFFFF !important; }

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

    .metric-card {
        background: #F2F2F2;
        border-left: 4px solid #E30513;
        padding: 12px 16px;
        border-radius: 4px;
        margin: 4px 0;
    }
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



# ============================================================
# SIDEBAR
# ============================================================
with st.sidebar:
    logo_path = ASSETS_DIR / 'logos' / 'logo_Ai_blanc_HD.png'
    if logo_path.exists():
        st.image(str(logo_path), width=150)
    else:
        st.markdown("## Assemblage ingénierie")

    st.markdown("---")
    st.markdown("### 🏗️ Outil STD")

    # -- Navigation --
    vue = st.radio(
        "Vue",
        ["Synthèse générale", "Focus zone", "Comparaison zones"],
        key="nav_vue"
    )

    st.markdown("---")
    st.markdown("### Paramètres projet")

    nom_projet = st.text_input(
        "Nom du projet",
        value=st.session_state.config_projet.get('projet', {}).get('nom', ''),
        key="nom_projet"
    )
    st.session_state.config_projet.setdefault('projet', {})['nom'] = nom_projet

    st.markdown("---")
    st.markdown("### Seuils de température")

    seuil_t1 = st.number_input("Seuil T1 (°C)", value=26.0, step=0.5, min_value=15.0, max_value=40.0, key="seuil_t1")
    seuil_t2 = st.number_input("Seuil T2 (°C)", value=28.0, step=0.5, min_value=15.0, max_value=45.0, key="seuil_t2")

    st.markdown("---")
    st.markdown("### Variantes")

    with st.expander("➕ Ajouter une variante", expanded=len(st.session_state.variantes) == 0):
        nom_var = st.text_input("Nom de la variante", value="Variante 1", key="nom_var_input")

        st.caption("Collez les chemins complets vers vos fichiers (pas de limite de taille)")
        path_r_input = st.text_input("Résultats (.slk)", placeholder=r"C:\Projet\Résultats.slk", key="path_resultats")
        path_s_input = st.text_input("Synthèse (.slk)",  placeholder=r"C:\Projet\Synthèse.slk",  key="path_synthese")
        path_m_input = st.text_input("Météo (.try) — optionnel", placeholder=r"C:\Projet\meteo.try", key="path_meteo")

        if st.button("Charger la variante", key="btn_charger"):
            if not path_r_input or not path_s_input:
                st.error("Les chemins Résultats et Synthèse sont obligatoires.")
            elif not Path(path_r_input).exists():
                st.error(f"Fichier introuvable : {path_r_input}")
            elif not Path(path_s_input).exists():
                st.error(f"Fichier introuvable : {path_s_input}")
            elif path_m_input and not Path(path_m_input).exists():
                st.error(f"Fichier météo introuvable : {path_m_input}")
            elif any(v.nom == nom_var for v in st.session_state.variantes):
                st.error(f"Une variante '{nom_var}' existe déjà.")
            else:
                with st.spinner(f"Chargement de '{nom_var}'... (peut prendre 30-60s pour les gros fichiers)"):
                    try:
                        var = charger_variante(
                            nom=nom_var,
                            fichier_resultats=path_r_input,
                            fichier_synthese=path_s_input,
                            fichier_meteo=path_m_input or '',
                        )
                        st.session_state.variantes.append(var)
                        st.success(f"✅ '{nom_var}' chargée ({len(var.zones)} zones)")
                    except Exception as e:
                        st.error(f"Erreur : {e}")

    # Liste des variantes chargées
    if st.session_state.variantes:
        st.markdown("**Variantes chargées :**")
        for i, var in enumerate(st.session_state.variantes):
            col_a, col_b = st.columns([3, 1])
            with col_a:
                st.markdown(f"• {var.nom} ({len(var.zones)} zones)")
            with col_b:
                if st.button("✕", key=f"del_var_{i}"):
                    st.session_state.variantes.pop(i)
                    st.rerun()

    st.markdown("---")

    # -- Export rapport --
    st.markdown("### Export rapport Word")
    zones_focus_rapport = []
    zones_comp_rapport = []

    if st.session_state.variantes:
        all_zones = st.session_state.variantes[0].zones
        zones_focus_rapport = st.multiselect(
            "Zones focus dans le rapport",
            all_zones,
            default=[],
            key="rapport_zones_focus"
        )
        zones_comp_rapport = st.multiselect(
            "Zones comparaison dans le rapport",
            all_zones,
            default=[],
            key="rapport_zones_comp"
        )

    if st.button("📄 Générer rapport Word", key="btn_rapport"):
        if not st.session_state.variantes:
            st.error("Chargez au moins une variante.")
        else:
            with st.spinner("Génération du rapport..."):
                try:
                    from export.word_report import generer_rapport
                    buf = generer_rapport(
                        variantes=st.session_state.variantes,
                        config=st.session_state.config_projet,
                        seuil_t1=seuil_t1,
                        seuil_t2=seuil_t2,
                        zones_focus=zones_focus_rapport,
                        zones_comparaison=zones_comp_rapport,
                        nom_projet=nom_projet,
                    )
                    st.download_button(
                        "⬇️ Télécharger le rapport",
                        data=buf,
                        file_name=f"rapport_STD_{nom_projet.replace(' ','_')}.docx",
                        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                        key="dl_rapport"
                    )
                except Exception as e:
                    st.error(f"Erreur rapport : {e}")


# ============================================================
# ZONE PRINCIPALE
# ============================================================
variantes = st.session_state.variantes
config = st.session_state.config_projet

if vue == "Synthèse générale":
    render_synthese_generale(variantes, seuil_t1, seuil_t2)

elif vue == "Focus zone":
    render_focus_zone(variantes, seuil_t1, seuil_t2, config)

elif vue == "Comparaison zones":
    render_comparaison_zones(variantes, seuil_t1, seuil_t2)
