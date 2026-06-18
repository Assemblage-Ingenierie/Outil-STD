"""
Vue Variantes — deux tableaux synchronisés par la liste d'améliorations :
  1. Récapitulatif : améliorations (lignes) × variantes (colonnes), cases à cocher.
  2. Descriptif    : améliorations (lignes) × descriptif libre (1 colonne).

La liste des améliorations est UNIQUE (source = tableau descriptif). Tout ajout /
renommage / suppression d'amélioration dans le descriptif se répercute dans le
récapitulatif. Les deux tableaux figurent dans le rapport Word.
"""
import streamlit as st
import pandas as pd


AMELIORATIONS_DEFAUT = [
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


def _init_state():
    ss = st.session_state
    if "ameliorations" not in ss or ss["ameliorations"] is None:
        ss["ameliorations"] = pd.DataFrame({
            "Amélioration": AMELIORATIONS_DEFAUT,
            "Descriptif": [""] * len(AMELIORATIONS_DEFAUT),
        })
    if "recap_vals" not in ss:
        ss["recap_vals"] = {}   # { amélioration: { variante: bool } }


def liste_ameliorations() -> list[str]:
    """Noms d'améliorations (source = tableau descriptif), nettoyés et non vides."""
    _init_state()
    df = st.session_state["ameliorations"]
    return [str(a).strip() for a in df["Amélioration"].tolist() if str(a).strip()]


def construire_recap(noms_variantes: list[str]) -> pd.DataFrame:
    """DataFrame récap : index = améliorations, colonnes = variantes (bool)."""
    ams = liste_ameliorations()
    vals = st.session_state.get("recap_vals", {})
    data = {v: [bool(vals.get(a, {}).get(v, False)) for a in ams] for v in noms_variantes}
    df = pd.DataFrame(data, index=ams)
    df.index.name = "Amélioration"
    return df


def render_description_variantes(variantes: list):
    st.header("Description des variantes")

    if not variantes:
        st.info("Chargez au moins une variante pour décrire ses caractéristiques.")
        return

    _init_state()
    ss = st.session_state
    noms = [v.nom for v in variantes]
    ams = liste_ameliorations()

    # ------------------------------------------------------------------
    # 1. Tableau récapitulatif (cases à cocher) — lignes dérivées des améliorations
    # ------------------------------------------------------------------
    st.subheader("Récapitulatif des améliorations par variante")
    st.caption("Cochez les améliorations présentes dans chaque variante. "
               "Les améliorations se gèrent dans le tableau « Descriptif » ci-dessous.")

    # Base STABLE passée à l'éditeur : reconstruite seulement si la structure
    # (améliorations ou variantes) change → édition fluide des cases.
    sig = (tuple(ams), tuple(noms))
    if ss.get("_recap_sig") != sig or "recap_base" not in ss:
        base = construire_recap(noms).reset_index()
        ss["recap_base"] = base
        ss["_recap_sig"] = sig
        ss.pop("ed_recap", None)

    col_cfg = {"Amélioration": st.column_config.TextColumn("Amélioration", disabled=True,
                                                           width="large")}
    for v in noms:
        col_cfg[v] = st.column_config.CheckboxColumn(v, default=False)

    if ams:
        edited_recap = st.data_editor(
            ss["recap_base"], column_config=col_cfg, num_rows="fixed",
            hide_index=True, use_container_width=True, key="ed_recap",
        )
        # Mémoriser l'état des cases (par nom d'amélioration)
        vals = {}
        for _, row in edited_recap.iterrows():
            a = str(row["Amélioration"]).strip()
            if a:
                vals[a] = {v: bool(row.get(v, False)) for v in noms}
        ss["recap_vals"] = vals
    else:
        st.info("Ajoutez des améliorations dans le tableau « Descriptif » ci-dessous.")

    st.divider()

    # ------------------------------------------------------------------
    # 2. Tableau descriptif (source des améliorations + description libre)
    # ------------------------------------------------------------------
    st.subheader("Descriptif des améliorations")
    st.caption("Ajoutez, renommez ou supprimez des améliorations (bouton + en bas) "
               "et décrivez-les. Les modifications se répercutent dans le récapitulatif.")

    if "desc_base" not in ss or ss["desc_base"] is None:
        ss["desc_base"] = ss["ameliorations"].copy()

    edited_desc = st.data_editor(
        ss["desc_base"],
        column_config={
            "Amélioration": st.column_config.TextColumn("Amélioration", required=True,
                                                        width="medium"),
            "Descriptif": st.column_config.TextColumn("Descriptif", width="large"),
        },
        num_rows="dynamic", hide_index=True, use_container_width=True, key="ed_desc",
    )
    ss["ameliorations"] = edited_desc

    # Export CSV des deux tables
    c1, c2 = st.columns(2)
    c1.download_button("⬇️ Récapitulatif (CSV)",
                       data=construire_recap(noms).to_csv().encode("utf-8-sig"),
                       file_name="recap_ameliorations.csv", mime="text/csv",
                       key="dl_recap")
    c2.download_button("⬇️ Descriptif (CSV)",
                       data=edited_desc.to_csv(index=False).encode("utf-8-sig"),
                       file_name="descriptif_ameliorations.csv", mime="text/csv",
                       key="dl_desc")
