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
from core.slk_parser import FichierInvalideError
from views.synthese_generale import render_synthese_generale
from views.focus_zone import render_focus_zone
from views.comparaison_zones import render_comparaison_zones
from views.description_variantes import render_description_variantes
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
    st.markdown("### Modèle de confort")
    methode_label = st.radio(
        "Diagramme bioclimatique",
        ["Givoni", "COCO (tropical)"],
        key="methode_confort",
        help="Givoni : diagramme classique (4 zones par vitesse d'air). "
             "COCO : adaptation pour climat tropical humide (Antilles, Réunion, Mayotte).",
    )
    methode = "coco" if methode_label.startswith("COCO") else "givoni"

    # -- Bornes Givoni éditables (gestion dynamique) --
    if methode == "givoni":
        with st.expander("⚙️ Bornes Givoni (avancé)"):
            gc = st.session_state.config_projet.setdefault('givoni', {})
            t_min = st.number_input(
                "Température min confort (°C)", value=float(gc.get('t_confort_min', 20.0)),
                step=0.5, min_value=10.0, max_value=25.0, key="giv_t_min")
            st.caption("Seuils HR max par zone (vitesse d'air) :")
            c1, c2 = st.columns(2)
            hr0 = c1.number_input("HR max 0 m/s (%)", value=80.0, step=1.0, min_value=50.0, max_value=100.0, key="giv_hr0")
            hr1 = c2.number_input("HR max 0,5 m/s (%)", value=85.0, step=1.0, min_value=50.0, max_value=100.0, key="giv_hr05")
            hr2 = c1.number_input("HR max 1 m/s (%)", value=90.0, step=1.0, min_value=50.0, max_value=100.0, key="giv_hr1")
            hr3 = c2.number_input("HR max 1,5 m/s (%)", value=95.0, step=1.0, min_value=50.0, max_value=100.0, key="giv_hr15")
            gc['t_confort_min'] = t_min
            gc['hr_max_zones'] = [hr0, hr1, hr2, hr3]
    else:
        st.caption("Zones COCO : standard tropical (non éditable).")

    st.markdown("---")
    st.markdown("### Variantes")

    # Stockage des chemins sélectionnés via le sélecteur natif
    for k in ('sel_resultats', 'sel_synthese', 'sel_meteo'):
        if k not in st.session_state:
            st.session_state[k] = ''

    with st.expander("➕ Ajouter une variante", expanded=len(st.session_state.variantes) == 0):
        nom_var = st.text_input("Nom de la variante", value="Variante 1", key="nom_var_input")

        st.caption("Sélectionnez vos fichiers (aucune limite de taille)")

        # --- Résultats ---
        if st.button("📂 Résultats (.slk)", key="btn_pick_resultats", use_container_width=True):
            chemin = choisir_fichier("Sélectionner le fichier Résultats",
                                     [("Fichiers Pléiades", "*.slk"), ("Tous", "*.*")])
            if chemin:
                st.session_state.sel_resultats = chemin
        if st.session_state.sel_resultats:
            st.caption(f"✓ {Path(st.session_state.sel_resultats).name}")

        # --- Synthèse ---
        if st.button("📂 Synthèse (.slk)", key="btn_pick_synthese", use_container_width=True):
            chemin = choisir_fichier("Sélectionner le fichier Synthèse",
                                     [("Fichiers Pléiades", "*.slk"), ("Tous", "*.*")])
            if chemin:
                st.session_state.sel_synthese = chemin
        if st.session_state.sel_synthese:
            st.caption(f"✓ {Path(st.session_state.sel_synthese).name}")

        # --- Météo (optionnel) ---
        if st.button("📂 Météo (.try) — optionnel", key="btn_pick_meteo", use_container_width=True):
            chemin = choisir_fichier("Sélectionner le fichier météo",
                                     [("Fichiers météo", "*.try"), ("Tous", "*.*")])
            if chemin:
                st.session_state.sel_meteo = chemin
        if st.session_state.sel_meteo:
            st.caption(f"✓ {Path(st.session_state.sel_meteo).name}")

        path_r_input = st.session_state.sel_resultats
        path_s_input = st.session_state.sel_synthese
        path_m_input = st.session_state.sel_meteo

        if st.button("Charger la variante", key="btn_charger", type="primary"):
            if not path_r_input or not path_s_input:
                st.error("Les fichiers Résultats et Synthèse sont obligatoires.")
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
                        # Réinitialiser les sélections pour la variante suivante
                        st.session_state.sel_resultats = ''
                        st.session_state.sel_synthese = ''
                        st.session_state.sel_meteo = ''
                        st.success(f"✅ '{nom_var}' chargée ({len(var.zones)} zones)")
                    except FichierInvalideError as e:
                        st.error("⛔ Fichier non conforme")
                        st.warning(str(e))
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

    # -- Projet : enregistrer / ouvrir --
    st.markdown("### 💾 Projet")
    cpa, cpb = st.columns(2)
    with cpa:
        if st.button("Enregistrer", key="btn_save_projet", use_container_width=True):
            if not st.session_state.variantes:
                st.warning("Aucune variante à enregistrer.")
            else:
                chemin = enregistrer_fichier(
                    "Enregistrer le projet STD",
                    [("Projet STD", "*.stdproj")],
                    extension_defaut=".stdproj",
                    nom_defaut=(nom_projet or "projet") + ".stdproj",
                )
                if chemin:
                    try:
                        etat = {
                            'nom_projet': nom_projet,
                            'params': {'seuil_t1': seuil_t1, 'seuil_t2': seuil_t2,
                                       'methode': methode, 'config': st.session_state.config_projet},
                            'variantes': st.session_state.variantes,
                            'descriptions': st.session_state.get('descriptions'),
                            'selections': {k: v for k, v in st.session_state.items()
                                           if k.startswith('sel_')},
                        }
                        p = projet_io.sauvegarder_projet(chemin, etat)
                        st.success(f"✅ Projet enregistré : {p.name}")
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
                    st.session_state.config_projet = charge['params'].get('config', st.session_state.config_projet)
                    if charge.get('descriptions') is not None:
                        st.session_state['descriptions'] = charge['descriptions']
                    # Forcer l'éditeur de variantes à reprendre les descriptions chargées
                    for k in ('_desc_base', '_desc_sig', 'editor_descriptions'):
                        st.session_state.pop(k, None)
                    # Restaurer les sélections persistantes
                    for k, v in (charge.get('selections') or {}).items():
                        st.session_state[k] = v
                    st.session_state['_projet_charge'] = charge.get('nom_projet', '')
                    st.success(f"✅ Projet ouvert : {charge.get('nom_projet','')}")
                    st.rerun()
                except Exception as e:
                    st.error(f"Erreur ouverture : {e}")

    st.markdown("---")

    # -- Export rapport --
    st.markdown("### Export rapport Word")
    st.caption("Le rapport reprend les sélections faites dans les vues "
               "(variantes, zone de focus, échantillon de zones).")

    if st.button("📄 Générer rapport Word", key="btn_rapport"):
        if not st.session_state.variantes:
            st.error("Chargez au moins une variante.")
        else:
            # Récupérer les sélections faites dans les différentes vues
            ss = st.session_state
            variantes_rapport = [v for v in ss.variantes
                                 if v.nom in ss.get('sel_syn_variantes', [v.nom for v in ss.variantes])]
            if not variantes_rapport:
                variantes_rapport = ss.variantes

            zone_focus = ss.get('sel_focus_zone')
            zones_focus_rapport = [zone_focus] if zone_focus else []
            zones_comp_rapport = ss.get('sel_comp_zones', [])

            with st.spinner("Génération du rapport..."):
                try:
                    from export.word_report import generer_rapport
                    buf = generer_rapport(
                        variantes=variantes_rapport,
                        config=st.session_state.config_projet,
                        seuil_t1=seuil_t1,
                        seuil_t2=seuil_t2,
                        zones_focus=zones_focus_rapport,
                        zones_comparaison=zones_comp_rapport,
                        nom_projet=nom_projet,
                        methode=methode,
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
# ZONE PRINCIPALE — navigation par onglets
# ============================================================
variantes = st.session_state.variantes
config = st.session_state.config_projet

VUES = ["Synthèse générale", "Focus zone", "Comparaison zones", "Variantes"]
if hasattr(st, "segmented_control"):
    vue = st.segmented_control("Vue", VUES, default="Synthèse générale",
                               key="nav_vue", label_visibility="collapsed")
else:
    vue = st.radio("Vue", VUES, horizontal=True, key="nav_vue",
                   label_visibility="collapsed")
if not vue:
    vue = "Synthèse générale"

if vue == "Synthèse générale":
    render_synthese_generale(variantes, seuil_t1, seuil_t2, config, methode)

elif vue == "Focus zone":
    render_focus_zone(variantes, seuil_t1, seuil_t2, config, methode)

elif vue == "Comparaison zones":
    render_comparaison_zones(variantes, seuil_t1, seuil_t2, config, methode)

elif vue == "Variantes":
    render_description_variantes(variantes)
