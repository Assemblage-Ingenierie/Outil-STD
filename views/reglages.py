"""
Onglet Réglages — configuration du projet et opérations.

Regroupe ce qui était dans la sidebar (devenue minimale) : paramètres projet,
seuils + degré-heures, modèle de confort + bornes Givoni, météo par défaut +
renommage, ajout de variante, export Word, nouveau projet.

Les valeurs de configuration sont stockées sous des clés session_state « cfg_* »
(persistantes même quand l'onglet n'est pas affiché) et lues par les autres vues.
"""
from __future__ import annotations
import dataclasses
from pathlib import Path

import streamlit as st

from core.variante import charger_variante, Variante
from core.slk_parser import FichierInvalideError
from core.file_picker import choisir_fichier, enregistrer_fichier
from core import projet as projet_io
from views.widgets import persist_number, persist_radio, persist_checkbox, persist_text


# ----------------------------------------------------------------------
# Chargement de variante mis en cache (par chemin + date de modification)
# ----------------------------------------------------------------------
def _mtime(path: str) -> float:
    try:
        return Path(path).stat().st_mtime if path else 0.0
    except OSError:
        return 0.0


@st.cache_data(show_spinner=False, max_entries=12)
def _charger_cache(res: str, syn: str, met: str,
                   res_m: float, syn_m: float, met_m: float) -> Variante:
    return charger_variante("", res, syn, met)


def charger_variante_rapide(nom: str, res: str, syn: str, met: str) -> Variante:
    var = _charger_cache(res, syn, met, _mtime(res), _mtime(syn), _mtime(met))
    return dataclasses.replace(var, nom=nom)


def render_reglages():
    st.header("Réglages")
    ss = st.session_state

    col_g, col_d = st.columns(2)

    # ==================================================================
    # Colonne gauche : paramètres d'analyse
    # ==================================================================
    with col_g:
        st.subheader("Projet")
        nom = persist_text("Nom du projet", "cfg_nom_projet",
                           default=ss.config_projet.get('projet', {}).get('nom', ''))
        ss.config_projet.setdefault('projet', {})['nom'] = nom

        st.subheader("Seuils de température")
        persist_number("Seuil T0 — température basse (°C)", "cfg_seuil_t0", 18.0,
                       step=0.5, min_value=5.0, max_value=25.0,
                       help="Heures sous ce seuil comptabilisées (inconfort par le froid).")
        persist_number("Seuil T1 (°C)", "cfg_seuil_t1", 26.0,
                       step=0.5, min_value=15.0, max_value=40.0)
        persist_number("Seuil T2 (°C)", "cfg_seuil_t2", 28.0,
                       step=0.5, min_value=15.0, max_value=45.0)
        persist_checkbox("Afficher le degré-heures d'inconfort (DH)", "cfg_dh_on",
                         default=False,
                         help="Sévérité de l'inconfort : somme des écarts (T − seuil T1) "
                              "sur les heures d'occupation, en °C·h.")

        st.subheader("Plages horaires jour / nuit")
        cj1, cj2 = st.columns(2)
        with cj1:
            persist_number("Début du jour (h)", "cfg_jour_debut", 7.0,
                           step=1.0, min_value=0.0, max_value=23.0)
        with cj2:
            persist_number("Fin du jour (h)", "cfg_jour_fin", 22.0,
                           step=1.0, min_value=1.0, max_value=24.0)
        st.caption("« Jour » = heures dans [début, fin) ; « Nuit » = le complément. "
                   "Sert au tableau d'inconfort jour/nuit (Synthèse générale).")

        st.subheader("Bande de confort hygrométrique")
        sc = ss.config_projet.setdefault('seuils', {})
        ch1, ch2 = st.columns(2)
        with ch1:
            hr_min = persist_number("HR min confort (%)", "cfg_hr_confort_min",
                                    float(sc.get('hr_confort_min', 40.0)),
                                    step=1.0, min_value=0.0, max_value=100.0)
        with ch2:
            hr_max = persist_number("HR max confort (%)", "cfg_hr_confort_max",
                                    float(sc.get('hr_confort_max', 70.0)),
                                    step=1.0, min_value=0.0, max_value=100.0)
        sc['hr_confort_min'] = hr_min
        sc['hr_confort_max'] = hr_max
        st.caption("Plage HR cible tracée en fond du graphe d'humidité (Focus zone).")

        st.subheader("Modèle de confort")
        methode_label = persist_radio(
            "Diagramme bioclimatique", ["Givoni", "COCO (tropical)"], "cfg_methode_label",
            default="Givoni",
            help="Givoni : diagramme classique (4 zones par vitesse d'air). "
                 "COCO : adaptation pour climat tropical humide.")
        ss['cfg_methode'] = "coco" if methode_label.startswith("COCO") else "givoni"

        if ss['cfg_methode'] == "givoni":
            with st.expander("⚙️ Bornes Givoni (avancé)"):
                gc = ss.config_projet.setdefault('givoni', {})
                t_min = persist_number("Température min confort (°C)", "cfg_giv_tmin",
                                       float(gc.get('t_confort_min', 20.0)),
                                       step=0.5, min_value=10.0, max_value=25.0)
                st.caption("Seuils HR max par zone (vitesse d'air) :")
                c1, c2 = st.columns(2)
                with c1:
                    hr0 = persist_number("HR max 0 m/s (%)", "cfg_giv_hr0", 80.0, step=1.0, min_value=50.0, max_value=100.0)
                    hr2 = persist_number("HR max 1 m/s (%)", "cfg_giv_hr1", 90.0, step=1.0, min_value=50.0, max_value=100.0)
                with c2:
                    hr1 = persist_number("HR max 0,5 m/s (%)", "cfg_giv_hr05", 85.0, step=1.0, min_value=50.0, max_value=100.0)
                    hr3 = persist_number("HR max 1,5 m/s (%)", "cfg_giv_hr15", 95.0, step=1.0, min_value=50.0, max_value=100.0)
                gc['t_confort_min'] = t_min
                gc['hr_max_zones'] = [hr0, hr1, hr2, hr3]
        else:
            st.caption("Zones COCO : standard tropical (non éditable).")

        st.subheader("Période d'analyse")
        periodes = {
            "Année entière": None,
            "Été (mai → octobre)": (5, 10),
            "Hiver (nov → avril)": (11, 4),
            "Personnalisée": "custom",
        }
        choix = persist_radio("Centrer les analyses sur", list(periodes.keys()),
                              "cfg_periode_label", default="Année entière",
                              help="Restreint tous les indicateurs et graphiques à la période choisie.")
        val = periodes[choix]
        if val == "custom":
            mois_noms = ['Janvier', 'Février', 'Mars', 'Avril', 'Mai', 'Juin', 'Juillet',
                         'Août', 'Septembre', 'Octobre', 'Novembre', 'Décembre']
            cc1, cc2 = st.columns(2)
            with cc1:
                m1 = persist_number("Mois de début", "cfg_per_m1", 1.0, step=1.0, min_value=1.0, max_value=12.0)
            with cc2:
                m2 = persist_number("Mois de fin", "cfg_per_m2", 12.0, step=1.0, min_value=1.0, max_value=12.0)
            ss['cfg_periode'] = (int(m1), int(m2))
            st.caption(f"De {mois_noms[int(m1)-1]} à {mois_noms[int(m2)-1]}"
                       + (" (à cheval sur l'année)" if int(m1) > int(m2) else ""))
        else:
            ss['cfg_periode'] = val

        st.subheader("Périodes de focus (module optionnel)")
        persist_checkbox(
            "Activer les périodes de focus", "cfg_periodes_on", default=False,
            help="Segmente l'année en plages de mois nommées (ex. Été / Hiver). "
                 "Alternative à la saison Pléiades : colore le diagramme de Givoni "
                 "par période et produit un tableau récap (heures + % d'inconfort) "
                 "dans la vue Focus zone.")
        if ss.get('cfg_periodes_on'):
            periodes = ss.get('cfg_periodes') or [{'nom': 'Été', 'm1': 5, 'm2': 10}]
            mois_noms = ['Jan', 'Fév', 'Mar', 'Avr', 'Mai', 'Jun', 'Jul', 'Aoû',
                         'Sep', 'Oct', 'Nov', 'Déc']
            n_per = int(st.number_input("Nombre de périodes", min_value=1, max_value=6,
                                        value=min(max(len(periodes), 1), 6), step=1,
                                        key="cfg_n_periodes"))
            nouvelles = []
            for i in range(n_per):
                base = periodes[i] if i < len(periodes) else {
                    'nom': f'Période {i + 1}', 'm1': 1, 'm2': 12}
                pc1, pc2, pc3 = st.columns([3, 2, 2])
                nom = pc1.text_input("Nom", value=base.get('nom', f'Période {i + 1}'),
                                     key=f"per_nom_{i}", label_visibility="collapsed",
                                     placeholder=f"Nom période {i + 1}")
                m1 = pc2.selectbox("Mois début", list(range(1, 13)),
                                   index=int(base.get('m1', 1)) - 1,
                                   format_func=lambda m: mois_noms[m - 1],
                                   key=f"per_m1_{i}", label_visibility="collapsed")
                m2 = pc3.selectbox("Mois fin", list(range(1, 13)),
                                   index=int(base.get('m2', 12)) - 1,
                                   format_func=lambda m: mois_noms[m - 1],
                                   key=f"per_m2_{i}", label_visibility="collapsed")
                nouvelles.append({'nom': nom or f'Période {i + 1}',
                                  'm1': int(m1), 'm2': int(m2)})
            ss['cfg_periodes'] = nouvelles
            st.caption("Le 1er intervalle de mois correspondant l'emporte (ordre ci-dessus). "
                       "Une plage à cheval sur l'année (ex. Nov→Avr) est admise.")

        st.subheader("Affichage")
        persist_checkbox("Nombres au format français (virgule décimale)",
                         "cfg_format_fr", default=True)
        persist_checkbox("Points sans distinction de saison (diagrammes)",
                         "cfg_saison_off", default=False,
                         help="Affiche les points en une couleur unique, sans séparer "
                              "saison de chauffe / refroidissement.")
        persist_checkbox("Mode sombre (graphiques)",
                         "cfg_dark_mode", default=False,
                         help="Adapte les couleurs des graphiques Plotly au fond sombre. "
                              "À activer si le thème Streamlit est en mode sombre.")

    # ==================================================================
    # Colonne droite : météo, ajout de variante
    # ==================================================================
    with col_d:
        _section_meteo_projet()
        _section_ajout_variante()

    st.divider()
    _section_export()
    st.divider()
    _section_nouveau_projet()
    st.divider()
    _section_maintenance()


# ----------------------------------------------------------------------
def _section_maintenance():
    with st.expander("🛠️ Maintenance"):
        st.caption("Le chargement des variantes est mis en cache sur le disque "
                   "(rechargement quasi instantané). Videz le cache si un fichier "
                   ".slk a été modifié sans changer sa date, ou en cas de doute.")
        if st.button("Vider le cache de chargement", key="btn_vider_cache"):
            from core import cache_disque
            n = cache_disque.vider()
            st.cache_data.clear()   # vide aussi le cache RAM (L1)
            st.success(f"Cache vidé ({n} fichier(s) supprimé(s)).")


# ----------------------------------------------------------------------
def _section_meteo_projet():
    st.subheader("Météo par défaut du projet")
    ss = st.session_state
    if 'meteo_projet' not in ss:
        ss['meteo_projet'] = ''
    if st.button("📂 Définir la météo par défaut (.try)", key="btn_meteo_projet",
                 width='stretch'):
        chemin = choisir_fichier("Météo par défaut du projet",
                                 [("Fichiers météo", "*.try"), ("Tous", "*.*")])
        if chemin:
            ss['meteo_projet'] = chemin
            st.rerun()
    if ss['meteo_projet']:
        m1, m2 = st.columns([4, 1])
        m1.caption(f"🌤️ {Path(ss['meteo_projet']).name}")
        if m2.button("✕", key="clear_meteo_projet", help="Retirer la météo par défaut"):
            ss['meteo_projet'] = ''
            st.rerun()
    else:
        st.caption("Aucune — sera demandée par variante.")

    # Renommage des météos chargées
    if 'meteo_labels' not in ss:
        ss['meteo_labels'] = {}
    fichiers = sorted({v.meteo_nom for v in ss.variantes if v.meteo_nom})
    if fichiers:
        with st.expander("🌤️ Renommer les météos"):
            st.caption("Libellé affiché dans les tableaux et graphiques "
                       "(ex. « Climat actuel », « RCP 8.5 »).")
            for f in fichiers:
                lbl = st.text_input(f, value=ss['meteo_labels'].get(f, ''),
                                    key=f"meteolbl_{f}", placeholder=f)
                ss['meteo_labels'][f] = lbl.strip()


# ----------------------------------------------------------------------
def _section_ajout_variante():
    ss = st.session_state
    st.subheader("Ajouter une variante")
    for k in ('sel_resultats', 'sel_synthese', 'sel_meteo'):
        ss.setdefault(k, '')

    with st.container(border=True):
        nom_var = st.text_input("Nom de la variante", value="Variante 1", key="nom_var_input")

        if st.button("📂 Résultats (.slk)", key="btn_pick_resultats", width='stretch'):
            c = choisir_fichier("Sélectionner le fichier Résultats",
                                [("Fichiers Pléiades", "*.slk"), ("Tous", "*.*")])
            if c:
                ss.sel_resultats = c
                st.rerun()
        if ss.sel_resultats:
            st.caption(f"✓ {Path(ss.sel_resultats).name}")

        if st.button("📂 Synthèse (.slk)", key="btn_pick_synthese", width='stretch'):
            c = choisir_fichier("Sélectionner le fichier Synthèse",
                                [("Fichiers Pléiades", "*.slk"), ("Tous", "*.*")])
            if c:
                ss.sel_synthese = c
                st.rerun()
        if ss.sel_synthese:
            st.caption(f"✓ {Path(ss.sel_synthese).name}")

        meteo_projet = ss.get('meteo_projet', '')
        if st.button("📂 Météo spécifique (.try)", key="btn_pick_meteo", width='stretch'):
            c = choisir_fichier("Météo spécifique à cette variante",
                                [("Fichiers météo", "*.try"), ("Tous", "*.*")])
            if c:
                ss.sel_meteo = c
                st.rerun()
        if ss.sel_meteo:
            mm1, mm2 = st.columns([4, 1])
            mm1.caption(f"✓ {Path(ss.sel_meteo).name} (spécifique)")
            if mm2.button("↺", key="reset_meteo_var", help="Revenir à la météo du projet"):
                ss.sel_meteo = ''
                st.rerun()
        elif meteo_projet:
            st.caption(f"✓ {Path(meteo_projet).name} (météo projet)")
        else:
            st.caption("Aucune météo — Givoni/confort indisponibles.")

        path_r = ss.sel_resultats
        path_s = ss.sel_synthese
        path_m = ss.sel_meteo or meteo_projet

        if st.button("Charger la variante", key="btn_charger", type="primary"):
            if not path_r or not path_s:
                st.error("Les fichiers Résultats et Synthèse sont obligatoires.")
            elif not Path(path_r).exists():
                st.error(f"Fichier introuvable : {path_r}")
            elif not Path(path_s).exists():
                st.error(f"Fichier introuvable : {path_s}")
            elif path_m and not Path(path_m).exists():
                st.error(f"Fichier météo introuvable : {path_m}")
            elif any(v.nom == nom_var for v in ss.variantes):
                st.error(f"Une variante « {nom_var} » existe déjà.")
            else:
                with st.spinner(f"Chargement de « {nom_var} »…"):
                    try:
                        var = charger_variante_rapide(nom_var, path_r, path_s, path_m or '')
                        ss.variantes.append(var)
                        ss.sel_resultats = ss.sel_synthese = ss.sel_meteo = ''
                        st.success(f"✅ « {nom_var} » chargée ({len(var.zones)} zones)")
                        st.rerun()
                    except FichierInvalideError as e:
                        st.error("⛔ Fichier non conforme")
                        st.warning(str(e))
                    except Exception as e:
                        st.error(f"Erreur : {e}")


# ----------------------------------------------------------------------
def _section_export():
    ss = st.session_state
    st.subheader("📄 Export du rapport Word")
    st.caption("Le rapport reprend les sélections faites dans les vues "
               "(variantes, zone de focus, échantillon de zones).")
    if st.button("Générer le rapport Word", key="btn_rapport", type="primary"):
        if not ss.variantes:
            st.error("Chargez au moins une variante.")
            return
        variantes_rapport = [v for v in ss.variantes
                             if v.nom in ss.get('sel_syn_variantes', [v.nom for v in ss.variantes])]
        if not variantes_rapport:
            variantes_rapport = ss.variantes
        zone_focus = ss.get('sel_focus_zone')
        zones_focus = [zone_focus] if zone_focus else []
        zones_comp = ss.get('sel_comp_zones', [])

        from views.description_variantes import construire_recap
        noms = [v.nom for v in variantes_rapport]
        df_recap = construire_recap(noms)
        df_detail = ss.get('ameliorations')

        with st.spinner("Génération du rapport…"):
            try:
                from export.word_report import generer_rapport
                buf = generer_rapport(
                    variantes=variantes_rapport,
                    config=ss.config_projet,
                    seuil_t1=ss.get('cfg_seuil_t1', 26.0),
                    seuil_t2=ss.get('cfg_seuil_t2', 28.0),
                    zones_focus=zones_focus,
                    zones_comparaison=zones_comp,
                    nom_projet=ss.get('cfg_nom_projet', ''),
                    methode=ss.get('cfg_methode', 'givoni'),
                    df_recap=df_recap,
                    df_detail=df_detail,
                    seuil_t0=ss.get('cfg_seuil_t0', 18.0),
                    jour_debut=ss.get('cfg_jour_debut', 7.0),
                    jour_fin=ss.get('cfg_jour_fin', 22.0),
                    periodes_on=ss.get('cfg_periodes_on', False),
                    periodes=ss.get('cfg_periodes', []),
                )
                st.download_button(
                    "⬇️ Télécharger le rapport", data=buf,
                    file_name=f"rapport_STD_{ss.get('cfg_nom_projet','projet').replace(' ', '_')}.docx",
                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    key="dl_rapport")
            except Exception as e:
                st.error(f"Erreur rapport : {e}")


# ----------------------------------------------------------------------
def _section_nouveau_projet():
    ss = st.session_state
    st.subheader("🗑️ Nouveau projet")
    st.caption("Efface toutes les variantes et remises à zéro des sélections.")
    if not ss.get('_confirm_new'):
        if st.button("Nouveau projet (tout effacer)", key="btn_new_projet"):
            ss['_confirm_new'] = True
            st.rerun()
    else:
        st.warning("Confirmer l'effacement de toutes les variantes et données ?")
        c1, c2 = st.columns(2)
        if c1.button("Oui, tout effacer", key="btn_new_yes", type="primary"):
            cles = [k for k in list(ss.keys())
                    if k.startswith(('sel_', 'cfg_', 'meteo_', 'desc_', 'recap_',
                                     '_recap', 'ed_', 'editor_'))]
            for k in cles:
                ss.pop(k, None)
            ss.variantes = []
            for k in ('ameliorations', 'recap_vals', 'descriptions', '_confirm_new'):
                ss.pop(k, None)
            st.rerun()
        if c2.button("Annuler", key="btn_new_no"):
            ss['_confirm_new'] = False
            st.rerun()
