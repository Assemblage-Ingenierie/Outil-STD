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
import numpy as np
import streamlit as st

# Palette ColorBrewer YlOrRd (9 classes) — identique au cmap matplotlib 'YlOrRd'.
_YLORRD = np.array([
    (255, 255, 204), (255, 237, 160), (254, 217, 118), (254, 178, 76), (253, 141, 60),
    (252, 78, 42), (227, 26, 28), (189, 0, 38), (128, 0, 38)], dtype=float)


def degrade(col):
    """Dégradé jaune → rouge par colonne, à utiliser via ``Styler.apply(degrade,
    subset=...)``. Remplace ``Styler.background_gradient`` (cmap 'YlOrRd') qui
    exige matplotlib (exclu de l'exécutable). Même rendu : normalisation min-max
    par colonne, texte blanc sur fond sombre, NaN / non numérique sans style."""
    import pandas as pd
    v = pd.to_numeric(pd.Series(col), errors='coerce').to_numpy(dtype=float)
    ok = ~np.isnan(v)
    if not ok.any():
        return [''] * len(v)
    lo, hi = np.nanmin(v), np.nanmax(v)
    t = np.zeros(len(v)) if hi == lo else (np.where(ok, v, lo) - lo) / (hi - lo)
    pos = t * (len(_YLORRD) - 1)
    i0 = np.clip(np.floor(pos).astype(int), 0, len(_YLORRD) - 2)
    frac = (pos - i0)[:, None]
    rgb = _YLORRD[i0] * (1 - frac) + _YLORRD[i0 + 1] * frac
    # Luminance relative (seuil 0,408 = celui de pandas background_gradient)
    lin = rgb / 255.0
    lin = np.where(lin <= 0.04045, lin / 12.92, ((lin + 0.055) / 1.055) ** 2.4)
    lum = lin @ np.array([0.2126, 0.7152, 0.0722])
    out = []
    for k in range(len(v)):
        if not ok[k]:
            out.append('')
            continue
        r, g, b = (int(round(c)) for c in rgb[k])
        texte = '#f1f1f1' if lum[k] < 0.408 else '#000000'
        out.append(f'background-color: #{r:02x}{g:02x}{b:02x}; color: {texte};')
    return out


def show_plotly(fig, **kwargs):
    """st.plotly_chart avec la config charte : snapshot 📷 nommé d'après le titre
    du graphique, logo Plotly masqué. Passe le reste des kwargs (width, key…)."""
    import config.charte as charte
    st.plotly_chart(fig, config=charte.plotly_config(fig), **kwargs)


def persist_multiselect(label, options, store_key, defaut=None,
                        auto_new=False, **kwargs):
    """
    multiselect dont la sélection survit aux changements de vue.

    auto_new=True : toute NOUVELLE option (ex. variante fraîchement chargée)
    est automatiquement ajoutée à la sélection — pratique pour les
    comparateurs où l'on veut toutes les variantes sélectionnées par défaut.
    """
    ss = st.session_state
    seen_key = store_key + "_seen"
    wkey = store_key + "_w"

    if store_key not in ss:
        ss[store_key] = list(defaut) if defaut is not None else list(options)
        ss[seen_key] = list(options)

    if auto_new:
        nouveaux = [o for o in options if o not in ss.get(seen_key, [])]
        if nouveaux:
            ss[store_key] = ss[store_key] + [o for o in nouveaux if o not in ss[store_key]]
            # Forcer le widget (s'il existe déjà) à intégrer les nouvelles options
            if wkey in ss:
                ss[wkey] = [o for o in ss[wkey] if o in options] + \
                           [o for o in nouveaux if o not in ss[wkey]]
        ss[seen_key] = list(options)

    # Ne garder que les options encore valides
    stored = [o for o in ss[store_key] if o in options]
    if wkey not in ss:
        ss[wkey] = stored
    else:
        purge = [o for o in ss[wkey] if o in options]
        if purge != ss[wkey]:
            ss[wkey] = purge

    sel = st.multiselect(label, options, key=wkey, **kwargs)
    ss[store_key] = sel
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


def persist_number(label, store_key, default, **kwargs):
    """number_input dont la valeur survit aux changements d'onglet."""
    ss = st.session_state
    if store_key not in ss:
        ss[store_key] = default
    wkey = store_key + "_w"
    if wkey not in ss:
        ss[wkey] = ss[store_key]
    val = st.number_input(label, key=wkey, **kwargs)
    ss[store_key] = val
    return val


def persist_radio(label, options, store_key, default=None, **kwargs):
    """radio dont la valeur survit aux changements d'onglet."""
    ss = st.session_state
    if store_key not in ss:
        ss[store_key] = default if default is not None else options[0]
    wkey = store_key + "_w"
    if wkey not in ss or ss[wkey] not in options:
        ss[wkey] = ss[store_key] if ss[store_key] in options else options[0]
    val = st.radio(label, options, key=wkey, **kwargs)
    ss[store_key] = val
    return val


def persist_checkbox(label, store_key, default=False, **kwargs):
    """checkbox dont la valeur survit aux changements d'onglet."""
    ss = st.session_state
    if store_key not in ss:
        ss[store_key] = default
    wkey = store_key + "_w"
    if wkey not in ss:
        ss[wkey] = ss[store_key]
    val = st.checkbox(label, key=wkey, **kwargs)
    ss[store_key] = val
    return val


def persist_text(label, store_key, default="", **kwargs):
    """text_input dont la valeur survit aux changements d'onglet."""
    ss = st.session_state
    if store_key not in ss:
        ss[store_key] = default
    wkey = store_key + "_w"
    if wkey not in ss:
        ss[wkey] = ss[store_key]
    val = st.text_input(label, key=wkey, **kwargs)
    ss[store_key] = val
    return val
