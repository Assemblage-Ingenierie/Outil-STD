"""
Widgets persistants : conservent leur valeur même quand on change de vue.

Streamlit nettoie l'état d'un widget dès que sa vue cesse d'être rendue.
Pour persister, on stocke la valeur dans une clé session_state dédiée
(non rattachée à un widget, donc jamais nettoyée), et on l'utilise comme
valeur par défaut lors de la recréation du widget.

Les sélections sont ainsi partagées entre les vues ET réutilisées par
l'export du rapport Word (pas de double saisie).
"""
from __future__ import annotations
import streamlit as st


def persist_multiselect(label, options, store_key, defaut=None, **kwargs):
    """multiselect dont la sélection survit aux changements de vue."""
    if store_key not in st.session_state:
        st.session_state[store_key] = defaut if defaut is not None else []
    # Ne garder que les options encore valides
    stored = [o for o in st.session_state[store_key] if o in options]
    sel = st.multiselect(label, options, default=stored, key=store_key + "_w", **kwargs)
    st.session_state[store_key] = sel
    return sel


def persist_selectbox(label, options, store_key, defaut_index=0, **kwargs):
    """selectbox dont la sélection survit aux changements de vue."""
    if not options:
        return None
    if store_key not in st.session_state or st.session_state[store_key] not in options:
        st.session_state[store_key] = options[min(defaut_index, len(options) - 1)]
    idx = options.index(st.session_state[store_key])
    sel = st.selectbox(label, options, index=idx, key=store_key + "_w", **kwargs)
    st.session_state[store_key] = sel
    return sel
