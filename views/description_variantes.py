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

    # Initialiser / synchroniser SEULEMENT quand la liste des variantes change.
    # (Re-synchroniser à chaque rerun reconstruit le DataFrame et fait « sauter »
    #  la sélection lors de clics rapides dans l'éditeur.)
    sig = tuple(noms)
    if "descriptions" not in st.session_state or st.session_state["descriptions"] is None:
        st.session_state["descriptions"] = _table_vierge(noms)
        st.session_state["_desc_sig"] = sig
    elif st.session_state.get("_desc_sig") != sig:
        st.session_state["descriptions"] = _synchroniser_colonnes(
            st.session_state["descriptions"], noms
        )
        st.session_state["_desc_sig"] = sig

    df = st.session_state["descriptions"]

    col_config = {"Caractéristique": st.column_config.TextColumn(
        "Caractéristique", width="large", required=True)}
    for nom in noms:
        col_config[nom] = st.column_config.CheckboxColumn(nom, default=False)

    edited = st.data_editor(
        df,
        column_config=col_config,
        num_rows="dynamic",
        use_container_width=True,
        hide_index=True,
        key="editor_descriptions",
    )
    st.session_state["descriptions"] = edited

    # Export CSV
    csv = edited.to_csv(index=False).encode("utf-8-sig")
    st.download_button("⬇️ Exporter le tableau (CSV)", data=csv,
                       file_name="description_variantes.csv", mime="text/csv",
                       key="dl_descriptions")
