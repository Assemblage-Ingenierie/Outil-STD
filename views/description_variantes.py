"""Vue Variantes — tableau comparatif à double entrée (caractéristiques × variantes)."""
import streamlit as st
import pandas as pd


# Caractéristiques proposées par défaut (l'utilisateur peut éditer / ajouter / retirer)
CARACTERISTIQUES_DEFAUT = [
    "Brise-soleil / protections solaires",
    "Isolation renforcée en toiture",
    "Isolation des murs",
    "Ventilation naturelle traversante",
    "Brasseurs d'air / ventilateurs",
    "Consigne de climatisation à 26 °C",
    "Consigne de climatisation à 28 °C",
    "Vitrages performants (faible facteur solaire)",
    "Surventilation nocturne",
]


def _table_vierge(noms_variantes: list[str]) -> pd.DataFrame:
    df = pd.DataFrame({"Caractéristique": CARACTERISTIQUES_DEFAUT})
    for nom in noms_variantes:
        df[nom] = False
    return df


def _synchroniser_colonnes(df: pd.DataFrame, noms_variantes: list[str]) -> pd.DataFrame:
    """Ajoute/retire les colonnes de variantes pour coller aux variantes chargées."""
    if "Caractéristique" not in df.columns:
        df.insert(0, "Caractéristique", CARACTERISTIQUES_DEFAUT[:len(df)])
    # Ajouter les variantes manquantes
    for nom in noms_variantes:
        if nom not in df.columns:
            df[nom] = False
    # Retirer les colonnes qui ne correspondent plus à une variante
    cols = ["Caractéristique"] + [n for n in noms_variantes]
    df = df[[c for c in cols if c in df.columns]]
    return df


def render_description_variantes(variantes: list):
    """Tableau éditable : lignes = caractéristiques, colonnes = variantes, cases à cocher."""
    st.header("Description des variantes")

    if not variantes:
        st.info("Chargez au moins une variante pour décrire ses caractéristiques.")
        return

    noms = [v.nom for v in variantes]

    st.caption(
        "Décrivez ce qui distingue chaque variante : cochez les caractéristiques présentes. "
        "Ajoutez vos propres lignes (bouton + en bas du tableau), renommez-les librement. "
        "Ce tableau est enregistré avec le projet."
    )

    ss = st.session_state
    sig = tuple(noms)

    # IMPORTANT pour la fluidité : la donnée PASSÉE à l'éditeur ("_desc_base")
    # doit rester STABLE entre les reruns. Streamlit applique lui-même les
    # éditions (stockées sous la clé du widget) par-dessus cette base. Si on
    # réinjecte le résultat édité dans la base à chaque rerun, l'éditeur se
    # réinitialise et la sélection « saute » sur des clics rapides.
    # On ne reconstruit la base QUE si la liste des variantes change.
    if "_desc_base" not in ss or ss["_desc_base"] is None:
        src = ss.get("descriptions")
        ss["_desc_base"] = (_synchroniser_colonnes(src.copy(), noms)
                            if src is not None else _table_vierge(noms))
        ss["_desc_sig"] = sig
    elif ss.get("_desc_sig") != sig:
        # repartir des dernières éditions connues, puis réajuster les colonnes
        src = ss.get("descriptions", ss["_desc_base"])
        ss["_desc_base"] = _synchroniser_colonnes(src.copy(), noms)
        ss["_desc_sig"] = sig
        ss.pop("editor_descriptions", None)  # reset du widget sur la nouvelle base

    col_config = {"Caractéristique": st.column_config.TextColumn(
        "Caractéristique", width="large", required=True)}
    for nom in noms:
        col_config[nom] = st.column_config.CheckboxColumn(nom, default=False)

    edited = st.data_editor(
        ss["_desc_base"],                 # base stable
        column_config=col_config,
        num_rows="dynamic",
        use_container_width=True,
        hide_index=True,
        key="editor_descriptions",
    )
    # Donnée courante (pour la sauvegarde projet) — NE PAS la réinjecter dans la base
    ss["descriptions"] = edited

    # Export CSV
    csv = edited.to_csv(index=False).encode("utf-8-sig")
    st.download_button("⬇️ Exporter le tableau (CSV)", data=csv,
                       file_name="description_variantes.csv", mime="text/csv",
                       key="dl_descriptions")
