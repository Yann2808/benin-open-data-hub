"""Bénin Open Data Hub — dashboard public.

    streamlit run app/streamlit_app.py
"""
from __future__ import annotations

import os
from pathlib import Path

import duckdb
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
WAREHOUSE = Path(os.environ.get("BODH_WAREHOUSE", ROOT / "warehouse" / "benin.duckdb"))
FOCUS = "BEN"
FOCUS_COLOR = "#0F7B4B"   # vert
PEER_COLOR = "#B8BEC6"
ACCENT = "#E8B200"       # jaune

st.set_page_config(page_title="Bénin Open Data Hub", page_icon="📊", layout="wide")


EXPORTS = ROOT / "exports"


def connect() -> duckdb.DuckDBPyConnection:
    """En local : l'entrepôt DuckDB. Hébergé (Streamlit Cloud) : les exports
    Parquet versionnés par la CI, exposés sous les mêmes noms marts.*."""
    if WAREHOUSE.exists():
        return duckdb.connect(str(WAREHOUSE), read_only=True)
    con = duckdb.connect()
    con.execute("create schema marts")
    for f in EXPORTS.glob("*.parquet"):
        if not f.stem.replace("_", "").isalnum():
            continue  # nom de vue non sûr : on ignore le fichier
        # Les vues n'acceptent pas de paramètres préparés : chemin échappé à la main.
        path = str(f).replace("'", "''")
        con.execute(f"create view marts.{f.stem} as select * from read_parquet('{path}')")
    return con


@st.cache_data(ttl=3600)
def query(sql: str) -> pd.DataFrame:
    con = connect()
    try:
        return con.sql(sql).df()
    finally:
        con.close()


def fmt(value: float | None, unit: str) -> str:
    if value is None or pd.isna(value):
        return "—"
    if "%" in unit:
        return f"{value:,.1f} %".replace(",", " ")
    if "USD" in unit or unit == "habitants":
        for threshold, suffix in ((1e9, " Md"), (1e6, " M")):
            if abs(value) >= threshold:
                return f"{value / threshold:,.1f}{suffix}".replace(",", " ")
        return f"{value:,.0f}".replace(",", " ")
    return f"{value:,.1f}".replace(",", " ")


def fmt_change(row: pd.Series) -> str | None:
    if pd.isna(row.change_abs):
        return None
    if row.change_in_points:
        return f"{row.change_abs:+.1f} pts depuis {int(row.baseline_year)}"
    return f"{row.change_pct * 100:+.0f} % depuis {int(row.baseline_year)}"


if not WAREHOUSE.exists() and not any(EXPORTS.glob("*.parquet")):
    st.error("Aucune donnée trouvée. Lance d'abord `make run` (ou `make demo` sans réseau).")
    st.stop()

scorecard = query("select * from marts.mart_benin_scorecard order by theme, label_fr")
countries = query("select * from marts.dim_country")
catalog = query("select * from marts.mart_data_catalog order by kind, title")
is_demo = bool(scorecard["is_demo"].any() or catalog["is_demo"].any())
freshness = query(
    "select max(source_last_updated) as src, max(ingested_at) as ing from marts.fct_indicator_values"
).iloc[0]

# --- En-tête -----------------------------------------------------------------
st.title("Bénin Open Data Hub")
st.caption(
    "Les grands indicateurs du Bénin, comparés à ses voisins d'Afrique de l'Ouest, "
    "et un catalogue des données publiques disponibles. Sources ouvertes, pipeline reproductible."
)
if is_demo:
    st.warning(
        "**Données de démonstration.** Les valeurs affichées sont synthétiques et servent à tester "
        "le pipeline. Lance `make run` pour charger les vraies données World Bank et INStaD.",
        icon="⚠️",
    )

tab_score, tab_compare, tab_catalog, tab_about = st.tabs(
    ["Tableau de bord", "Comparer", "Catalogue des données", "Méthode"]
)

# --- Tableau de bord ---------------------------------------------------------
with tab_score:
    better = (scorecard.position_vs_peers == "mieux que la médiane des pairs").sum()
    worse = (scorecard.position_vs_peers == "moins bien que la médiane des pairs").sum()
    peers = ", ".join(countries.loc[~countries.is_focus, "country_name_fr"].sort_values())
    st.markdown(
        f"Sur les indicateurs où « plus » veut dire « mieux » (ou l'inverse), le Bénin fait "
        f"**mieux que la médiane de ses pairs sur {better}** et **moins bien sur {worse}**. "
        f"Pairs : {peers}."
    )
    for theme, group in scorecard.groupby("theme", sort=False):
        st.subheader(theme)
        cols = st.columns(min(len(group), 3))
        for col, (_, row) in zip(cols * 10, group.iterrows()):
            with col:
                year = "" if pd.isna(row.latest_year) else f" ({int(row.latest_year)})"
                st.metric(
                    label=f"{row.label_fr}{year}",
                    value=fmt(row.latest_value, row.unit_fr),
                    delta=fmt_change(row),
                    delta_color="off" if pd.isna(row.higher_is_better)
                    else ("normal" if row.higher_is_better else "inverse"),
                    help=f"Unité : {row.unit_fr}. Source : World Bank, indicateur {row.indicator_code}.",
                )
                rank = (
                    f"Rang {int(row.rank_among_peers)}/{int(row.n_countries_compared)} · "
                    if not pd.isna(row.rank_among_peers) else ""
                )
                st.caption(
                    f"{rank}{row.position_vs_peers} "
                    f"(médiane : {fmt(row.peer_median, row.unit_fr)})"
                )

# --- Comparer ----------------------------------------------------------------
with tab_compare:
    options = dict(zip(scorecard.label_fr, scorecard.indicator_code))
    choice = st.selectbox("Indicateur", list(options), index=list(options).index("Utilisateurs d'Internet")
                          if "Utilisateurs d'Internet" in options else 0)
    code = options[choice]
    unit = scorecard.loc[scorecard.indicator_code == code, "unit_fr"].iloc[0]
    series = query(
        f"""
        select f.year, f.value, c.country_iso3, c.country_name_fr, c.is_focus
        from marts.fct_indicator_values f
        join marts.dim_country c using (country_iso3)
        where f.indicator_code = '{code.replace("'", "")}'
        order by f.year
        """
    )
    fig = go.Figure()
    for (iso, name, focus), g in series.groupby(["country_iso3", "country_name_fr", "is_focus"]):
        fig.add_trace(go.Scatter(
            x=g.year, y=g.value, name=name, mode="lines",
            line=dict(color=FOCUS_COLOR if focus else PEER_COLOR, width=4 if focus else 1.5),
            opacity=1 if focus else 0.8,
            hovertemplate=f"{name} %{{x}} : %{{y:,.1f}} {unit}<extra></extra>",
        ))
    # Bénin dessiné en dernier, donc au premier plan
    fig.data = tuple(sorted(fig.data, key=lambda t: t.line.width))
    fig.update_layout(
        height=460, margin=dict(l=10, r=10, t=30, b=10), yaxis_title=unit,
        legend=dict(orientation="h", y=-0.15), hovermode="x unified",
        plot_bgcolor="rgba(0,0,0,0)",
    )
    st.plotly_chart(fig, width="stretch")
    st.caption("Le Bénin est en vert. Les années sans donnée publiée apparaissent comme des trous.")

# --- Catalogue ---------------------------------------------------------------
with tab_catalog:
    st.markdown(
        "Ce que le hub sait des données disponibles sur le Bénin : indicateurs suivis, "
        "enquêtes de l'INStaD et fichiers ouverts ajoutés à la main (data.gouv.bj)."
    )
    kinds = st.multiselect("Type", sorted(catalog.kind.unique()), default=sorted(catalog.kind.unique()))
    search = st.text_input("Rechercher", placeholder="ex. santé, ménages, électricité…")
    view = catalog[catalog.kind.isin(kinds)]
    if search:
        view = view[view.title.str.contains(search, case=False, na=False)
                    | view.topic.fillna("").str.contains(search, case=False)]
    st.dataframe(
        view[["kind", "title", "source", "topic", "period_start", "period_end", "access", "url"]],
        column_config={
            "kind": "Type", "title": "Titre", "source": "Source", "topic": "Thème",
            "period_start": st.column_config.NumberColumn("Début", format="%d"),
            "period_end": st.column_config.NumberColumn("Fin", format="%d"),
            "access": "Accès", "url": st.column_config.LinkColumn("Lien", display_text="ouvrir"),
        },
        hide_index=True, width="stretch",
    )
    st.caption(f"{len(view)} entrée(s).")

# --- Méthode -----------------------------------------------------------------
with tab_about:
    st.markdown(
        f"""
**Sources**
- *World Bank — World Development Indicators*, API publique v2.
- *INStaD — catalogue de microdonnées (NADA)* : métadonnées des enquêtes uniquement.
- *data.gouv.bj* : fichiers téléchargés à la main (le portail n'autorise pas la collecte automatisée), avec URL et date de téléchargement tracées.

**Méthode de comparaison**
- Pour chaque pays, on prend la dernière valeur publiée. Un pays n'entre dans la comparaison que si sa donnée a moins de 5 ans d'écart avec la plus récente.
- Le rang n'est calculé que pour les indicateurs où le sens est clair (ex. plus d'accès à l'électricité = mieux, plus d'inflation = moins bien).
- Les évolutions des indicateurs en % sont données en points, les autres en % relatif.

**Fraîcheur**
- Dernière mise à jour publiée par la World Bank : {freshness.src or "inconnue"}.
- Dernière collecte par le hub : {freshness.ing if not pd.isna(freshness.ing) else "inconnue"}.

Projet open source : pipeline Python → DuckDB → dbt → Streamlit.
"""
    )
