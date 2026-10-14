"""Bénin Open Data Hub — dashboard public.

    streamlit run app/streamlit_app.py
"""
from __future__ import annotations

import html
import os
from pathlib import Path

import duckdb
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
import yaml

import odfa_catalog

ROOT = Path(__file__).resolve().parents[1]
WAREHOUSE = Path(os.environ.get("BODH_WAREHOUSE", ROOT / "warehouse" / "benin.duckdb"))
EXPORTS = ROOT / "exports"
FOCUS = "BEN"
REPO_URL = "https://github.com/Yann2808/benin-open-data-hub"
ODFA_URL = "https://benin.opendataforafrica.org"
FOCUS_COLOR = "#0F7B4B"   # vert
NEUTRAL = "#B8BEC6"
INK_MUTED = "#5B6169"
# Une couleur fixe par voisin (attribuée par code ISO, jamais par rang) : un pays
# garde sa couleur d'un graphique à l'autre et quand on filtre. Pas de vert, réservé
# au Bénin. Palette vérifiée daltonisme ; avec 7 pays les couleurs ne suffisent pas
# seules, d'où le nom écrit au bout de chaque courbe.
PEER_PALETTE = ["#2a78d6", "#eb6834", "#4a3aa7", "#eda100", "#e87ba4", "#17becf"]
# Ordre de lecture des thèmes et icône associée (Material Symbols)
THEMES = {
    "Économie": ":material/payments:",
    "Démographie": ":material/groups:",
    "Santé": ":material/favorite:",
    "Éducation": ":material/school:",
    "Numérique": ":material/wifi:",
    "Infrastructures": ":material/bolt:",
    "Emploi": ":material/work:",
}

st.set_page_config(page_title="Bénin Open Data Hub", page_icon=":material/insights:", layout="wide")

# Quelques styles que le thème (.streamlit/config.toml) ne couvre pas : marge
# haute, barre d'onglets, bandeau d'en-tête et listes « points forts / à surveiller ».
st.html(
    """
<style>
/* Marge haute par défaut (~6rem) trop large : l'en-tête remonte sous la barre Streamlit. */
[data-testid="stMainBlockContainer"] { padding-top: 2.5rem; }
[data-testid="stHeader"] { background: transparent; }
/* Onglets : barre de navigation pleine largeur, libellés plus lisibles. */
[data-testid="stTabs"] [role="tablist"] { gap: .25rem; background: #F0F2EC; padding: .3rem; border-radius: .7rem; border: 0; box-shadow: none; }
[data-testid="stTab"] { padding: .5rem 1rem; border-radius: .5rem; height: auto; }
[data-testid="stTab"] p { font-size: .98rem; font-weight: 500; }
[data-testid="stTab"][aria-selected="true"] { background: #FFFFFF; box-shadow: 0 1px 2px rgba(31,35,40,.10); }
[data-testid="stTabs"] .react-aria-SelectionIndicator { display: none; }
.bodh-hero { padding: 0 0 0.5rem 0; }
.bodh-flag { display: flex; height: 6px; width: 96px; border-radius: 3px; overflow: hidden; margin-bottom: 1rem; }
.bodh-flag span:nth-child(1) { flex: 1; background: #0F7B4B; }
.bodh-flag span:nth-child(2) { flex: 1; background: #E8B200; }
.bodh-flag span:nth-child(3) { flex: 1; background: #D3272E; }
.bodh-eyebrow { text-transform: uppercase; letter-spacing: .08em; font-size: .78rem; font-weight: 600; color: #0F7B4B; }
.bodh-title { font-family: "Space Grotesk", sans-serif; font-size: 2.6rem; font-weight: 700; line-height: 1.1; margin: .25rem 0 .5rem 0; color: #1F2328; }
.bodh-lede { font-size: 1.05rem; color: #5B6169; max-width: 52rem; margin: 0; }
.bodh-list { list-style: none; padding: 0; margin: 0; }
.bodh-list li { display: flex; justify-content: space-between; gap: 1rem; padding: .55rem 0; border-bottom: 1px solid #E3E5DF; }
.bodh-list li:last-child { border-bottom: 0; }
.bodh-list .lbl { font-weight: 500; color: #1F2328; }
.bodh-list .val { color: #5B6169; font-size: .9rem; white-space: nowrap; }
.bodh-list .rank { font-weight: 600; color: #1F2328; }
</style>
"""
)


def comparison_window() -> int:
    """Même fenêtre que les marts dbt, lue dans dbt_project.yml pour ne pas diverger."""
    try:
        cfg = yaml.safe_load((ROOT / "transform" / "dbt_project.yml").read_text())
        return int(cfg["vars"]["comparison_window_years"])
    except Exception:  # noqa: BLE001 — fichier absent une fois hébergé : valeur par défaut
        return 5


WINDOW = comparison_window()


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
def query(sql: str, params: tuple = ()) -> pd.DataFrame:
    con = connect()
    try:
        return con.execute(sql, list(params)).df()
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


def fmt_date(value) -> str:
    if value is None or pd.isna(value):
        return "inconnue"
    return pd.Timestamp(value).strftime("%d/%m/%Y")


def ordinal(rank: int) -> str:
    return "1er" if rank == 1 else f"{rank}e"


def share(part: int, total: int) -> str:
    """Part en % à la française, sans afficher « 0 % » pour une part non nulle."""
    ratio = part / total if total else 0
    return "< 1 %" if 0 < ratio < 0.01 else f"{ratio:.0%}".replace("%", " %")


def to_csv(df: pd.DataFrame) -> bytes:
    # utf-8-sig : accents lisibles quand le fichier est ouvert dans Excel
    return df.to_csv(index=False).encode("utf-8-sig")


def style_fig(fig: go.Figure, height: int) -> go.Figure:
    fig.update_layout(
        height=height, margin=dict(l=10, r=10, t=30, b=10),
        plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Inter, sans-serif", color="#1F2328"),
        hoverlabel=dict(font_family="Inter, sans-serif"),
    )
    fig.update_xaxes(gridcolor="#E9EBE5", linecolor="#E3E5DF")
    fig.update_yaxes(gridcolor="#E9EBE5", automargin=True)  # libellés longs jamais coupés
    return fig


def rank_list(rows: pd.DataFrame) -> str:
    """Liste HTML « indicateur · rang · valeur » (points forts / à surveiller)."""
    items = "".join(
        f'<li><span class="lbl">{html.escape(r.label_fr)}</span>'
        f'<span class="val"><span class="rank">{ordinal(int(r.rank_among_peers))}</span>'
        f" sur {int(r.n_countries_compared)} · {html.escape(fmt(r.latest_value, r.unit_fr))}</span></li>"
        for r in rows.itertuples()
    )
    return f'<ul class="bodh-list">{items}</ul>'


def indicator_cards(rows: pd.DataFrame, history: pd.DataFrame, median_label: str) -> None:
    """Une carte par indicateur, rangées par thème, avec la courbe du pays depuis 2000.
    `rows` suit le schéma de mart_benin_scorecard ; grille continue pour ne pas laisser de trous."""
    theme_order = {t: i for i, t in enumerate(THEMES)}
    cards = rows.assign(_t=rows.theme.map(theme_order).fillna(99)).sort_values(["_t", "label_fr"])
    cols = st.columns(4)
    for i, (_, row) in enumerate(cards.iterrows()):
        values = history.loc[history.indicator_code == row.indicator_code, "value"].tolist()
        year = "" if pd.isna(row.latest_year) else f" ({int(row.latest_year)})"
        if pd.isna(row.latest_value):
            short = "pas de donnée"
        elif not pd.isna(row.rank_among_peers):
            short = f"{ordinal(int(row.rank_among_peers))} sur {int(row.n_countries_compared)}"
        elif row.position_vs_peers.startswith("au-dessus"):
            # Pas de sens « mieux / moins bien » : on situe juste par rapport à la médiane
            short = "sup. à la médiane"
        elif row.position_vs_peers.startswith("en dessous"):
            short = "inf. à la médiane"
        else:
            short = "hors comparaison"
        stale = f" Attention : donnée de plus de {WINDOW} ans, hors comparaison." if row.is_stale else ""
        with cols[i % 4]:
            st.metric(
                label=f"{row.label_fr}{year}",
                value=fmt(row.latest_value, row.unit_fr),
                delta=fmt_change(row),
                delta_color="off" if pd.isna(row.higher_is_better)
                else ("normal" if row.higher_is_better else "inverse"),
                delta_description=("⚠️ " if row.is_stale else "") + short,
                icon=THEMES.get(row.theme, ":material/label:"),
                help=f"{row.theme} · unité : {row.unit_fr}. {row.position_vs_peers.capitalize()} "
                     f"({median_label} : {fmt(row.peer_median, row.unit_fr)}).{stale} "
                     f"Source : World Bank, indicateur {row.indicator_code}.",
                chart_data=values if len(values) > 1 else None,
                chart_type="area",
                border=True,
            )


def country_profile(iso: str) -> pd.DataFrame:
    """Même calcul que mart_benin_scorecard, pour n'importe lequel des 7 pays : dernière
    valeur, évolution, rang parmi les pays à donnée récente et médiane des autres pays."""
    lv = latest.copy()
    lv["max_year"] = lv.groupby("indicator_code").latest_year.transform("max")
    comparable = lv[lv.latest_year >= lv.max_year - WINDOW]
    out = []
    for ind in indicators.itertuples():
        own = lv[(lv.indicator_code == ind.indicator_code) & (lv.country_iso3 == iso)]
        comp = comparable[comparable.indicator_code == ind.indicator_code]
        others = comp[comp.country_iso3 != iso].latest_value
        row = own.iloc[0] if len(own) else None
        value = row.latest_value if row is not None else None
        median = others.median() if len(others) else None
        rank = None
        if pd.notna(ind.higher_is_better) and iso in set(comp.country_iso3):
            ranks = comp.latest_value.rank(method="min", ascending=not bool(ind.higher_is_better))
            rank = int(ranks[comp.country_iso3 == iso].iloc[0])
        if value is None or pd.isna(value) or median is None:
            position = "données insuffisantes"
        elif pd.isna(ind.higher_is_better):
            position = "au-dessus de la médiane" if value >= median else "en dessous de la médiane"
        elif (value >= median) == bool(ind.higher_is_better):
            position = "mieux que la médiane des pairs"
        else:
            position = "moins bien que la médiane des pairs"
        out.append({
            "indicator_code": ind.indicator_code, "label_fr": ind.label_fr, "theme": ind.theme,
            "unit_fr": ind.unit_fr, "higher_is_better": ind.higher_is_better,
            "latest_year": row.latest_year if row is not None else None, "latest_value": value,
            "baseline_year": row.baseline_year if row is not None else None,
            "change_abs": row.change_abs if row is not None else None,
            "change_pct": row.change_pct if row is not None else None,
            "change_in_points": "%" in ind.unit_fr, "peer_median": median,
            "rank_among_peers": rank, "n_countries_compared": len(comp),
            "position_vs_peers": position,
            "is_stale": value is not None and pd.notna(value) and iso not in set(comp.country_iso3),
        })
    return pd.DataFrame(out)


if not WAREHOUSE.exists() and not any(EXPORTS.glob("*.parquet")):
    st.error("Aucune donnée trouvée. Lance d'abord `make run` (ou `make demo` sans réseau).")
    st.stop()

scorecard = query("select * from marts.mart_benin_scorecard order by theme, label_fr")
countries = query("select * from marts.dim_country")
indicators = query("select * from marts.dim_indicator")
latest = query(
    """
    select l.*, c.country_name_fr, c.is_focus
    from marts.mart_latest_values l
    join marts.dim_country c using (country_iso3)
    """
)
focus_series = query(
    "select indicator_code, year, value from marts.fct_indicator_values where country_iso3 = ? order by year",
    (FOCUS,),
)
catalog = query("select * from marts.mart_data_catalog order by kind, title")
try:
    odfa = odfa_catalog.enrich(query("select * from marts.mart_odfa_datasets"))
except duckdb.Error:  # entrepôt antérieur à l'ajout d'ODFA
    odfa = pd.DataFrame()
freshness = query(
    "select max(source_last_updated) as src, max(ingested_at) as ing from marts.fct_indicator_values"
).iloc[0]

# Démo : tout le tableau de bord est synthétique (make demo), ou seulement des
# restes de démo dans le catalogue à côté de vraies données. Dans le second cas
# on masque ces lignes plutôt que de les mélanger aux vraies.
is_demo = bool(scorecard["is_demo"].any())
hidden_demo = 0
if not is_demo and catalog["is_demo"].any():
    hidden_demo = int(catalog["is_demo"].sum())
    catalog = catalog[~catalog["is_demo"]]

# Jeux ODFA du catalogue général : titre lisible et thème estimé à la place du slug et de
# la catégorie unique « Manual » renvoyée par le portail
is_odfa = catalog.source.fillna("").str.startswith("Open Data for Africa")
if is_odfa.any():
    catalog.loc[is_odfa, "topic"] = [odfa_catalog.estimate_theme(t, s.removeprefix("Open Data for Africa — "))
                                     for t, s in zip(catalog.loc[is_odfa, "title"], catalog.loc[is_odfa, "source"])]
    catalog.loc[is_odfa, "title"] = catalog.loc[is_odfa, "title"].map(odfa_catalog.humanize_title)

focus_name = countries.loc[countries.is_focus, "country_name_fr"].iloc[0]
peer_names = countries.loc[~countries.is_focus, "country_name_fr"].sort_values().tolist()
peer_isos = sorted(countries.loc[~countries.is_focus, "country_iso3"])
COLORS = {iso: PEER_PALETTE[i % len(PEER_PALETTE)] for i, iso in enumerate(peer_isos)}
COLORS[FOCUS] = FOCUS_COLOR

# --- En-tête -----------------------------------------------------------------
st.html(
    f"""
<div class="bodh-hero">
  <div class="bodh-flag"><span></span><span></span><span></span></div>
  <div class="bodh-eyebrow">Open data · Afrique de l'Ouest</div>
  <div class="bodh-title">Bénin Open Data Hub</div>
  <p class="bodh-lede">Les grands indicateurs du {html.escape(focus_name)} comparés à ses
  {len(peer_names)} voisins, et un catalogue des données publiques disponibles sur le pays.
  Sources ouvertes, pipeline reproductible.</p>
</div>
"""
)
st.markdown(
    f":green-badge[:material/monitoring: {len(scorecard)} indicateurs] "
    f":gray-badge[:material/public: {len(countries)} pays] "
    ":gray-badge[:material/database: World Bank WDI] "
    + (f":gray-badge[:material/folder_open: {len(odfa):,} jeux Open Data for Africa] ".replace(",", " ")
       if len(odfa) else "")
    + f":gray-badge[:material/update: Collecte du {fmt_date(freshness.ing)}]"
)

if is_demo:
    st.warning(
        "**Données de démonstration.** Les valeurs affichées sont synthétiques et servent à tester "
        "le pipeline. Lance `make run` pour charger les vraies données World Bank et INStaD.",
        icon=":material/warning:",
    )

tab_score, tab_country, tab_compare, tab_odfa, tab_catalog, tab_about = st.tabs([
    ":material/dashboard: Tableau de bord",
    ":material/flag: Fiche pays",
    ":material/compare_arrows: Comparer",
    ":material/folder_open: Open Data for Africa",
    ":material/menu_book: Catalogue",
    ":material/info: Méthode",
])

# --- Tableau de bord ---------------------------------------------------------
with tab_score:
    ranked = scorecard[scorecard.higher_is_better.notna() & scorecard.rank_among_peers.notna()]
    better = (scorecard.position_vs_peers == "mieux que la médiane des pairs").sum()
    worse = (scorecard.position_vs_peers == "moins bien que la médiane des pairs").sum()
    firsts = (ranked.rank_among_peers == 1).sum()

    st.space("small")
    k1, k2, k3 = st.columns(3)
    k1.metric("Mieux que la médiane des voisins", f"{better} / {len(ranked)}", border=True,
              help="Indicateurs où le sens de lecture est clair (plus = mieux, ou l'inverse).")
    k2.metric("Moins bien que la médiane", f"{worse} / {len(ranked)}", border=True)
    k3.metric(f"Indicateurs où le {focus_name} est 1er", f"{firsts}", border=True)

    # Points forts / à surveiller : les 3 meilleurs et les 3 moins bons rangs
    by_rank = ranked.sort_values(["rank_among_peers", "label_fr"])
    s1, s2 = st.columns(2)
    with s1.container(border=True):
        st.markdown(":material/trending_up: **Points forts**")
        st.html(rank_list(by_rank.head(3)))
    with s2.container(border=True):
        st.markdown(":material/visibility: **À surveiller**")
        st.html(rank_list(by_rank.tail(3).iloc[::-1]))

    # Vue d'ensemble : chaque ligne place les pays entre le moins bon (0) et le
    # meilleur (100) sur l'indicateur. Le sens « mieux » est toujours à droite.
    st.space("small")
    st.subheader(f"Où se situe le {focus_name} ?")
    st.caption(
        "Sur chaque ligne, les pays sont placés du moins bien classé (à gauche) au mieux classé "
        f"(à droite), parmi ceux qui ont une donnée de moins de {WINDOW} ans. Survolez un point pour voir la valeur."
    )
    max_year = latest.groupby("indicator_code").latest_year.transform("max")
    comparable = latest[latest.latest_year >= max_year - WINDOW].merge(
        ranked[["indicator_code", "label_fr", "unit_fr", "higher_is_better", "rank_among_peers"]],
        on="indicator_code",
    )
    if comparable.empty:
        st.info("Pas assez de données comparables pour cette vue.")
    else:
        bounds = comparable.groupby("indicator_code").latest_value.agg(["min", "max"])
        comparable = comparable.join(bounds, on="indicator_code")
        spread = (comparable["max"] - comparable["min"]).replace(0, pd.NA)
        score = ((comparable.latest_value - comparable["min"]) / spread * 100).fillna(50).astype(float)
        comparable["score"] = score.where(comparable.higher_is_better.astype(bool), 100 - score)
        # Tri : indicateurs où le Bénin est le mieux classé en haut
        order = ranked.sort_values("rank_among_peers", ascending=False).label_fr.tolist()
        comparable["value_txt"] = [fmt(v, u) for v, u in zip(comparable.latest_value, comparable.unit_fr)]

        fig = go.Figure()
        # Bénin en premier dans la légende
        for (is_focus, name, iso), g in comparable.groupby(["is_focus", "country_name_fr", "country_iso3"]):
            fig.add_trace(go.Scatter(
                x=g.score, y=g.label_fr, mode="markers",
                name=name, legendrank=1 if is_focus else 10,
                marker=dict(size=16 if is_focus else 10, color=COLORS[iso], line=dict(width=2, color="white")),
                customdata=g[["country_name_fr", "value_txt", "latest_year"]],
                hovertemplate="<b>%{customdata[0]}</b><br>%{y} : %{customdata[1]} (%{customdata[2]})<extra></extra>",
            ))
        fig.data = tuple(sorted(fig.data, key=lambda t: t.marker.size))  # Bénin au premier plan
        fig.update_yaxes(categoryorder="array", categoryarray=order, title=None, showgrid=True)
        fig.update_xaxes(range=[-5, 105], showgrid=False, zeroline=False,
                         tickvals=[0, 100], ticktext=["◀ moins bien", "mieux ▶"])
        fig.add_vline(x=50, line=dict(color=NEUTRAL, dash="dot", width=1))
        style_fig(fig, height=80 + 42 * len(order))
        fig.update_layout(legend=dict(orientation="h", y=1.02, x=0, yanchor="bottom"), hovermode="closest")
        with st.container(border=True):
            st.plotly_chart(fig, width="stretch")

    # Détail : une carte par indicateur, rangées par thème (icône), avec la
    # courbe du Bénin. Grille continue pour ne pas laisser de trous.
    st.space("small")
    st.subheader("Détail par indicateur")
    st.caption("Dernière valeur, évolution sur 5 ans, rang parmi les 7 pays et courbe du Bénin depuis 2000. "
               "Icônes : " + " · ".join(f"{icon} {name}" for name, icon in THEMES.items()
                                        if name in set(scorecard.theme)) + ".")
    indicator_cards(scorecard, focus_series, "médiane des voisins")

# --- Fiche pays --------------------------------------------------------------
with tab_country:
    st.space("small")
    names = dict(zip(countries.country_iso3, countries.country_name_fr))
    with st.container(border=True):
        c1, c2 = st.columns([2, 3], vertical_alignment="bottom")
        # Lié à l'URL (?pays=Togo) : une fiche peut être partagée telle quelle
        iso = c1.selectbox("Pays", [FOCUS] + peer_isos, format_func=names.get, key="pays",
                           bind="query-params")
        info = countries.set_index("country_iso3").loc[iso]
        c2.markdown(
            f":gray-badge[:material/public: {info.region_fr}] "
            + (":green-badge[:material/handshake: UEMOA] " if info.is_uemoa else ":gray-badge[Hors UEMOA] ")
            + f":gray-badge[Comparé aux {len(countries) - 1} autres pays du hub]"
        )

    profile = country_profile(iso)
    country_series = query(
        "select indicator_code, year, value from marts.fct_indicator_values where country_iso3 = ? order by year",
        (iso,),
    )
    p_ranked = profile[profile.higher_is_better.notna() & profile.rank_among_peers.notna()]
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Mieux que la médiane des autres", f"{(profile.position_vs_peers == 'mieux que la médiane des pairs').sum()}"
              f" / {len(p_ranked)}", border=True,
              help="Indicateurs où le sens de lecture est clair (plus = mieux, ou l'inverse).")
    k2.metric("Moins bien que la médiane", f"{(profile.position_vs_peers == 'moins bien que la médiane des pairs').sum()}"
              f" / {len(p_ranked)}", border=True)
    k3.metric(f"Indicateurs classés 1er sur {len(countries)}", int((p_ranked.rank_among_peers == 1).sum()), border=True)
    k4.metric("Données anciennes ou absentes", int(profile.is_stale.sum() + profile.latest_value.isna().sum()),
              border=True, help=f"Dernière valeur publiée il y a plus de {WINDOW} ans, ou aucune valeur.")

    p_by_rank = p_ranked.sort_values(["rank_among_peers", "label_fr"])
    if len(p_by_rank):
        s1, s2 = st.columns(2)
        with s1.container(border=True):
            st.markdown(":material/trending_up: **Points forts**")
            st.html(rank_list(p_by_rank.head(3)))
        with s2.container(border=True):
            st.markdown(":material/visibility: **À surveiller**")
            st.html(rank_list(p_by_rank.tail(3).iloc[::-1]))

    if iso != FOCUS:
        # Face-à-face avec le Bénin, indicateur par indicateur
        st.space("small")
        st.subheader(f"{names[iso]} face au {focus_name}")
        duel = profile.merge(
            scorecard[["indicator_code", "latest_value", "latest_year"]].rename(
                columns={"latest_value": "focus_value", "latest_year": "focus_year"}),
            on="indicator_code",
        )

        def advantage(r) -> str:
            if pd.isna(r.latest_value) or pd.isna(r.focus_value) or pd.isna(r.higher_is_better):
                return "—"
            if r.latest_value == r.focus_value:
                return "égalité"
            return names[iso] if (r.latest_value > r.focus_value) == bool(r.higher_is_better) else focus_name

        duel_view = pd.DataFrame({
            "Indicateur": duel.label_fr,
            names[iso]: [f"{fmt(v, u)} ({int(y)})" if pd.notna(v) else "—"
                         for v, u, y in zip(duel.latest_value, duel.unit_fr, duel.latest_year)],
            focus_name: [f"{fmt(v, u)} ({int(y)})" if pd.notna(v) else "—"
                         for v, u, y in zip(duel.focus_value, duel.unit_fr, duel.focus_year)],
            "Avantage": [advantage(r) for r in duel.itertuples()],
            "Unité": duel.unit_fr,
        })
        st.dataframe(duel_view, hide_index=True, width="stretch",
                     alt=f"Tableau comparant {names[iso]} et le {focus_name} sur chaque indicateur")
        wins = (duel_view.Avantage == names[iso]).sum()
        losses = (duel_view.Avantage == focus_name).sum()
        st.caption(f"Sur les indicateurs à sens de lecture clair : avantage {names[iso]} sur {wins}, "
                   f"avantage {focus_name} sur {losses}. Population et urbanisation ne sont pas jugées. "
                   "Les années peuvent différer d'un pays à l'autre (dernière valeur publiée).")

    st.space("small")
    st.subheader("Détail par indicateur")
    st.caption(f"{names[iso]} : dernière valeur, évolution sur 5 ans, rang parmi les {len(countries)} pays "
               "et courbe depuis 2000.")
    indicator_cards(profile, country_series, "médiane des autres pays")

# --- Comparer ----------------------------------------------------------------
with tab_compare:
    options = dict(zip(scorecard.label_fr, scorecard.indicator_code))
    labels = sorted(options)
    st.space("small")
    with st.container(border=True):
        c1, c2 = st.columns([2, 3])
        choice = c1.selectbox(
            "Indicateur", labels,
            index=labels.index("Utilisateurs d'Internet") if "Utilisateurs d'Internet" in labels else 0,
        )
        selected_peers = c2.multiselect(f"Pays comparés au {focus_name}", peer_names, default=peer_names)
        code = options[choice]
        meta = indicators.loc[indicators.indicator_code == code].iloc[0]
        unit = meta.unit_fr

        series = query(
            """
            select f.year, f.value, c.country_iso3, c.country_name_fr, c.is_focus
            from marts.fct_indicator_values f
            join marts.dim_country c using (country_iso3)
            where f.indicator_code = ?
            order by f.year
            """,
            (code,),
        )
        series = series[series.is_focus | series.country_name_fr.isin(selected_peers)]
        if not series.empty and series.year.min() < series.year.max():
            years = st.slider("Période", int(series.year.min()), int(series.year.max()),
                              (int(series.year.min()), int(series.year.max())))
            series = series[series.year.between(*years)]

    if series.empty:
        st.info("Aucune donnée pour cet indicateur.")
    else:
        left, right = st.columns([3, 2])
        with left.container(border=True):
            st.markdown(f"**Évolution** · {unit}")
            fig = go.Figure()
            ends = []
            for (name, iso, focus), g in series.groupby(["country_name_fr", "country_iso3", "is_focus"]):
                fig.add_trace(go.Scatter(
                    x=g.year, y=g.value, name=name, mode="lines+markers" if focus else "lines",
                    line=dict(color=COLORS[iso], width=4 if focus else 2),
                    marker=dict(size=6), legendrank=1 if focus else 10,
                    hovertemplate=f"{name} : %{{y:,.1f}} {unit}<extra></extra>",
                ))
                ends.append((g.year.iloc[-1], g.value.iloc[-1], name, iso, focus))
            # Bénin dessiné en dernier, donc au premier plan
            fig.data = tuple(sorted(fig.data, key=lambda t: t.line.width))
            # Nom du pays au bout de sa courbe, en écartant les étiquettes trop proches
            span = (series.value.max() - series.value.min()) or 1
            gap, prev = span * 0.055, None
            for x, y, name, iso, focus in sorted(ends, key=lambda e: e[1]):
                y_label = y if prev is None else max(y, prev + gap)
                prev = y_label
                fig.add_annotation(
                    x=x, y=y_label, text=f"<b>{name}</b>" if focus else name,
                    xanchor="left", xshift=8, showarrow=False, font=dict(size=12),
                )
                fig.add_shape(type="line", x0=x, y0=y, x1=x, y1=y_label, xref="x", yref="y",
                              line=dict(color=COLORS[iso], width=1))
            style_fig(fig, height=440)
            fig.update_layout(
                legend=dict(orientation="h", y=-0.12), hovermode="x unified",
                margin=dict(l=10, r=110, t=20, b=10),
            )
            st.plotly_chart(fig, width="stretch")

        with right.container(border=True):
            st.markdown("**Dernière valeur publiée**")
            last = (series.sort_values("year").groupby("country_name_fr", as_index=False).last()
                    .sort_values("value"))
            fig = go.Figure(go.Bar(
                x=last.value, y=last.country_name_fr, orientation="h",
                marker=dict(color=[COLORS[iso] for iso in last.country_iso3], cornerradius=4),
                text=[f"{fmt(v, unit)} ({int(y)})" for v, y in zip(last.value, last.year)],
                # Texte à l'extérieur, à l'encre normale : lisible quelle que soit la couleur de la barre
                textposition="outside", cliponaxis=False,
                hovertemplate="%{y} : %{x:,.1f}<extra></extra>",
            ))
            style_fig(fig, height=440)
            fig.update_layout(showlegend=False, bargap=0.35, margin=dict(l=10, r=90, t=20, b=10))
            fig.update_xaxes(showticklabels=False, showgrid=False)
            st.plotly_chart(fig, width="stretch")

        notes = [f"Le {focus_name} est en vert ; chaque voisin garde la même couleur sur tous les graphiques."]
        if pd.notna(meta.higher_is_better):
            notes.append("Plus la valeur est haute, mieux c'est." if bool(meta.higher_is_better)
                         else "Plus la valeur est basse, mieux c'est.")
        notes.append("Les années sans donnée publiée apparaissent comme des trous.")
        notes.append(f"Source : [{meta.source_name}]({meta.source_url}).")
        n1, n2 = st.columns([4, 1])
        n1.caption(" ".join(notes))
        n2.download_button(
            "Télécharger (CSV)",
            to_csv(series[["country_iso3", "country_name_fr", "year", "value"]]
                   .assign(indicator_code=code, unit=unit)),
            file_name=f"{code}.csv", mime="text/csv", icon=":material/download:", width="stretch",
        )

# --- Open Data for Africa ----------------------------------------------------
with tab_odfa:
    st.space("small")
    st.markdown(
        f"Le portail [Open Data for Africa — Bénin]({ODFA_URL}), animé par la Banque africaine de "
        "développement, publie les tableaux de l'INStaD et des ministères. Le hub en tient l'inventaire "
        "à jour chaque semaine pour savoir **ce qui existe, qui le produit et à quand remonte la "
        "dernière mise à jour**."
    )
    if odfa.empty:
        st.info("Inventaire Open Data for Africa pas encore chargé : lance `make run`.", icon=":material/info:")
    else:
        st.info(
            "**Inventaire uniquement.** Les valeurs de ces jeux ne sont pas encore intégrées au hub : "
            "le portail bloque les téléchargements automatisés. Chaque ligne renvoie vers le jeu sur le portail.",
            icon=":material/inventory_2:",
        )
        recent = (odfa.freshness == "moins d'un an").sum()
        licensed = odfa.license.notna().sum()
        k1, k2, k3, k4 = st.columns(4)
        k1.metric("Jeux inventoriés", f"{len(odfa):,}".replace(",", "\u202f"), border=True)
        k2.metric("Producteurs", odfa.source_name.nunique(), border=True,
                  help="Noms tels que saisis sur le portail (une même institution peut apparaître sous plusieurs noms).")
        k3.metric("Mis à jour depuis moins d'un an", int(recent), border=True,
                  delta=f"{share(recent, len(odfa))} du total", delta_color="off", delta_arrow="off")
        k4.metric("Licence déclarée", int(licensed), border=True,
                  delta=f"{share(licensed, len(odfa))} du total", delta_color="off", delta_arrow="off",
                  help="Sans licence déclarée, vérifier les conditions d'utilisation sur le portail.")

        g1, g2 = st.columns([3, 2])
        with g1.container(border=True):
            st.markdown("**Jeux par thème** · estimé d'après le titre et le producteur")
            by_theme = odfa.theme.value_counts().sort_values()
            fig = go.Figure(go.Bar(
                x=by_theme.values, y=by_theme.index, orientation="h",
                marker=dict(color=FOCUS_COLOR, cornerradius=4),
                text=by_theme.values, textposition="outside", cliponaxis=False,
                hovertemplate="%{y} : %{x} jeux<extra></extra>",
            ))
            style_fig(fig, height=60 + 30 * len(by_theme))
            fig.update_layout(showlegend=False, bargap=0.3, margin=dict(l=10, r=40, t=10, b=10))
            fig.update_xaxes(showticklabels=False, showgrid=False)
            st.plotly_chart(fig, width="stretch")
        with g2.container(border=True):
            st.markdown("**Année de dernière mise à jour**")
            by_year = odfa.last_updated_on.dt.year.value_counts().sort_index()
            fig = go.Figure(go.Bar(
                x=by_year.index.astype(str), y=by_year.values,
                marker=dict(color=FOCUS_COLOR, cornerradius=4),
                text=by_year.values, textposition="outside", cliponaxis=False,
                hovertemplate="%{x} : %{y} jeux<extra></extra>",
            ))
            style_fig(fig, height=60 + 30 * len(by_theme))
            fig.update_layout(showlegend=False, bargap=0.3, margin=dict(l=10, r=10, t=30, b=10))
            fig.update_yaxes(showticklabels=False, showgrid=False)
            fig.update_xaxes(type="category")
            st.plotly_chart(fig, width="stretch")
            oldest = by_year.idxmax()
            st.caption(f"{by_year.max()} jeux ont été mis à jour pour la dernière fois en {oldest} : "
                       "de bons candidats à une actualisation.")

        with st.container(border=True):
            f1, f2 = st.columns([1, 1])
            themes = f1.multiselect("Thème", sorted(odfa.theme.unique()), placeholder="Tous les thèmes")
            freshness_choice = f2.segmented_control(
                "Dernière mise à jour", ["moins d'un an", "1 à 3 ans", "plus de 3 ans"],
                selection_mode="multi", default=None,
            )
            f3, f4 = st.columns([1, 1])
            search = f3.text_input("Rechercher", placeholder="ex. vaccination, coton, électricité…",
                                   icon=":material/search:", key="odfa_search")
            producers = f4.pills("Producteur", sorted(odfa.producer.unique()), selection_mode="multi")
        view = odfa
        if themes:
            view = view[view.theme.isin(themes)]
        if freshness_choice:
            view = view[view.freshness.isin(freshness_choice)]
        if producers:
            view = view[view.producer.isin(producers)]
        if search:
            mask = pd.Series(False, index=view.index)
            for col in ("title_fr", "source_name", "theme", "survey"):
                mask |= view[col].fillna("").str.contains(search, case=False, regex=False)
            view = view[mask]

        table = view.assign(license=view.license.fillna("non précisée")).sort_values(
            "last_updated_on", ascending=False)
        # Sigle de l'enquête déjà en tête du titre ; licence presque toujours absente : CSV seulement
        columns = ["title_fr", "last_updated_on", "theme", "source_name", "url"]
        st.dataframe(
            table[columns],
            column_config={
                "title_fr": st.column_config.TextColumn("Titre", width="large"),
                "last_updated_on": st.column_config.DateColumn("Mis à jour", format="DD/MM/YYYY", width="small"),
                "theme": "Thème (estimé)",
                "source_name": st.column_config.TextColumn("Producteur", width="medium"),
                "url": st.column_config.LinkColumn("Lien", display_text="ouvrir", width="small"),
            },
            hide_index=True, width="stretch",
            alt="Inventaire des jeux de données Open Data for Africa — Bénin",
        )
        c1, c2 = st.columns([4, 1])
        c1.caption(f"{len(view)} jeu(x) sur {len(odfa)}. Titres reconstitués à partir des identifiants du "
                   "portail (sigle de l'enquête en tête : EDS, MICS, RGE…) ; certains sont tronqués à la source.")
        c2.download_button("Télécharger (CSV)", to_csv(table[columns + ["survey", "license", "producer", "dataset_id"]]),
                           file_name="odfa_benin_inventaire.csv", mime="text/csv",
                           icon=":material/download:", width="stretch")

# --- Catalogue ---------------------------------------------------------------
with tab_catalog:
    st.space("small")
    st.markdown(
        "Tout ce que le hub sait des données disponibles sur le Bénin, au même endroit : indicateurs "
        "suivis, jeux du portail Open Data for Africa, enquêtes de l'INStaD et fichiers ouverts ajoutés "
        "à la main (data.gouv.bj)."
    )
    counts = catalog.kind.value_counts()
    if len(counts):
        for col, (kind, n) in zip(st.columns(len(counts) + 1), counts.items()):
            plural = {"jeu de données": "jeux de données", "fichier déposé": "fichiers déposés"}.get(kind, kind + "s")
            col.metric((plural if n > 1 else kind).capitalize(), int(n), border=True)

    with st.container(border=True):
        f1, f2 = st.columns([1, 2])
        all_kinds = sorted(catalog.kind.unique())
        kinds = f1.multiselect("Type", all_kinds, default=all_kinds)
        search = f2.text_input("Rechercher", placeholder="ex. santé, ménages, électricité…",
                               icon=":material/search:")
    view = catalog[catalog.kind.isin(kinds)]
    if search:
        view = view[view.title.str.contains(search, case=False, na=False, regex=False)
                    | view.topic.fillna("").str.contains(search, case=False, regex=False)
                    | view.source.fillna("").str.contains(search, case=False, regex=False)]
    columns = ["kind", "title", "source", "topic", "period_start", "period_end", "access", "url"]
    st.dataframe(
        view[columns],
        column_config={
            "kind": "Type", "title": st.column_config.TextColumn("Titre", width="large"),
            "source": "Source", "topic": "Thème",
            "period_start": st.column_config.NumberColumn("Début", format="%d"),
            "period_end": st.column_config.NumberColumn("Fin", format="%d"),
            "access": "Accès", "url": st.column_config.LinkColumn("Lien", display_text="ouvrir"),
        },
        hide_index=True, width="stretch",
    )
    c1, c2 = st.columns([4, 1])
    c1.caption(f"{len(view)} entrée(s).")
    c2.download_button("Télécharger (CSV)", to_csv(view[columns]), file_name="catalogue_benin.csv",
                       mime="text/csv", icon=":material/download:", width="stretch")
    if hidden_demo:
        st.info(
            f"{hidden_demo} entrée(s) de démonstration masquée(s) : le catalogue INStaD (NADA) est "
            "momentanément indisponible, les vraies enquêtes apparaîtront dès que le site sera de "
            "nouveau en ligne.", icon=":material/info:",
        )
    elif "enquête" not in set(catalog.kind.str.lower()):
        st.info("Le catalogue INStaD (NADA) est momentanément indisponible : les enquêtes "
                "réapparaîtront dès que le site sera de nouveau en ligne.", icon=":material/info:")

# --- Méthode -----------------------------------------------------------------
with tab_about:
    st.space("small")
    m1, m2, m3 = st.columns(3)
    with m1.container(border=True, height="stretch"):
        st.markdown(
            """
:material/database: **Sources**

- *World Bank — World Development Indicators*, API publique v2.
- *INStaD — catalogue de microdonnées (NADA)* : métadonnées des enquêtes uniquement.
- *Open Data for Africa — Bénin* (BAD) : inventaire des jeux via l'API du portail (titre, producteur, mise à jour, licence).
- *data.gouv.bj* : fichiers téléchargés à la main (le portail n'autorise pas la collecte automatisée), avec URL et date de téléchargement tracées.
"""
        )
    with m2.container(border=True, height="stretch"):
        st.markdown(
            f"""
:material/balance: **Méthode de comparaison**

- Pour chaque pays, on prend la dernière valeur publiée. Un pays n'entre dans la comparaison que si sa donnée a moins de {WINDOW} ans d'écart avec la plus récente.
- Le rang n'est calculé que pour les indicateurs où le sens est clair (ex. plus d'accès à l'électricité = mieux, plus d'inflation = moins bien).
- Les évolutions des indicateurs en % sont données en points, les autres en % relatif.
"""
        )
    with m3.container(border=True, height="stretch"):
        st.markdown(
            f"""
:material/update: **Fraîcheur**

- Dernière mise à jour publiée par la World Bank : {fmt_date(freshness.src)}.
- Dernière collecte par le hub : {fmt_date(freshness.ing)}.

Projet open source : pipeline Python → DuckDB → dbt → Streamlit. [Code sur GitHub]({REPO_URL}).
"""
        )

st.divider()
st.caption(
    f"Bénin Open Data Hub · données World Bank, Open Data for Africa, INStaD, data.gouv.bj · "
    f"dernière collecte le {fmt_date(freshness.ing)} · [code source]({REPO_URL})"
)
