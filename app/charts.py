"""Graphiques Altair (Vega-Lite) du dashboard.

Altair plutôt que Plotly : le moteur Plotly pèse 4,6 Mo de JavaScript et retardait
le premier graphique d'environ 20 s sur un téléphone d'entrée de gamme simulé
(processeur ralenti 4×, 4G lente ; mesure du 2026-10-25). Vega-Lite est le moteur
des graphiques natifs de Streamlit, beaucoup plus léger.

Règles communes :
- aucun zoom ni déplacement : rien ne capte le doigt quand on fait défiler la page ;
- textes d'au moins 12 px ;
- un pays n'est jamais reconnaissable par sa seule couleur : nom sur l'axe, nom au
  bout de la courbe, ou forme du point (voir SHAPES) ;
- au toucher, la valeur s'écrit en haut du graphique (`_tap`, `_detail`) : Vega n'affiche
  ses infobulles qu'au survol de la souris, qui n'existe pas sur téléphone.

Chaque fonction reçoit un DataFrame déjà préparé, aux colonnes nommées dans sa
docstring, et renvoie un graphique prêt pour st.altair_chart.
"""
from __future__ import annotations

import altair as alt
import pandas as pd

FONT = "Inter, sans-serif"
INK = "#1F2328"
MUTED = "#5B6169"
GRID = "#E9EBE5"
LINE = "#E3E5DF"
TEXT_SIZE = 12

# Formes des pays (le Bénin en cercle) et le caractère qui les représente dans les légendes HTML
FOCUS_SHAPE = "circle"
SHAPES = ["square", "triangle-up", "diamond", "triangle-down", "cross", "triangle-right"]
GLYPHS = {"circle": "●", "square": "■", "triangle-up": "▲", "diamond": "◆", "triangle-down": "▼",
          "cross": "✚", "triangle-right": "▶"}


def luminance(color: str) -> float:
    """Luminance relative WCAG d'une couleur #RRGGBB."""
    r, g, b = (int(color.lstrip("#")[i:i + 2], 16) / 255 for i in (0, 2, 4))
    return sum(w * (c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4)
               for w, c in zip((0.2126, 0.7152, 0.0722), (r, g, b)))


def contrast(a: str, b: str) -> float:
    """Rapport de contraste WCAG entre deux couleurs (1 à 21 ; 4,5 minimum pour du texte)."""
    hi, lo = sorted((luminance(a), luminance(b)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)


def text_color(fill: str) -> str:
    """Encre la plus lisible sur un fond donné : la plus contrastée entre le noir du texte et le blanc."""
    return max((INK, "#FFFFFF"), key=lambda ink: contrast(ink, fill))


def finish(chart: alt.TopLevelMixin, height: int, right: int = 10) -> alt.TopLevelMixin:
    """Style commun : police, axes discrets, fond transparent, marge droite pour les étiquettes."""
    return (
        chart.properties(height=height, padding={"left": 5, "top": 26, "bottom": 5, "right": right})
        .configure(font=FONT, background="transparent")
        .configure_view(stroke=None)
        .configure_axis(labelFontSize=TEXT_SIZE, titleFontSize=TEXT_SIZE, labelColor=MUTED, titleColor=MUTED,
                        titleFontWeight="normal", gridColor=GRID, domainColor=LINE, tickColor=LINE,
                        labelFont=FONT, titleFont=FONT)
        .configure_text(font=FONT, fontSize=TEXT_SIZE, color=INK)
    )


def _tap(fields: list[str], nearest: bool = True) -> alt.Parameter:
    """Sélection au survol (souris) et au toucher (le toucher produit un « click »)."""
    return alt.selection_point(fields=fields, nearest=nearest, on="click, pointerover", empty=False,
                               clear="dblclick")


def _detail(df: pd.DataFrame, selection: alt.Parameter) -> alt.Chart:
    """Ligne de texte au-dessus du tracé : la colonne `detail` de l'élément sélectionné."""
    return alt.Chart(df).transform_filter(selection).mark_text(
        align="left", baseline="bottom", fontWeight=600, dy=-6).encode(
        x=alt.value(0), y=alt.value(0), text="detail:N")


def _multiline_axis(**kwargs) -> alt.Axis:
    """Axe dont les libellés contenant « \\n » s'affichent sur plusieurs lignes."""
    return alt.Axis(labelExpr="split(datum.label, '\\n')", labelLimit=0, ticks=False, domain=False, **kwargs)


def hbars(df: pd.DataFrame, *, value_title: str, label_title: str = "Pays", x_max: float | None = None,
          ascending: bool = False, right: int = 70) -> alt.TopLevelMixin:
    """Barres horizontales triées, la plus grande valeur en haut (la plus petite si `ascending`).
    Colonnes : label, value, color, text (valeur affichée au bout)."""
    order = df.sort_values("value", ascending=ascending).label.tolist()
    base = alt.Chart(df).encode(
        y=alt.Y("label:N", sort=order, title=None, axis=_multiline_axis(),
                scale=alt.Scale(paddingInner=0.35)),
        x=alt.X("value:Q", title=None, axis=None,
                scale=alt.Scale(domain=[0, x_max]) if x_max else alt.Scale(zero=True, nice=False)),
        tooltip=[alt.Tooltip("label:N", title=label_title), alt.Tooltip("text:N", title=value_title)],
    )
    bars = base.mark_bar(cornerRadiusEnd=4).encode(color=alt.Color("color:N", scale=None))
    # Valeur au bout de la barre, à droite si positive, à gauche si négative
    pos = base.transform_filter("datum.value >= 0").mark_text(align="left", dx=4).encode(text="text:N")
    neg = base.transform_filter("datum.value < 0").mark_text(align="right", dx=-4).encode(text="text:N")
    return finish(bars + pos + neg, height=34 * len(df) + 10, right=right)


def vbars(df: pd.DataFrame, *, value_title: str, label_title: str, color: str, height: int = 260,
          every: int | None = None, show_text: bool = True) -> alt.TopLevelMixin:
    """Barres verticales d'une seule couleur. Colonnes : label (texte), value, text.
    `every` : n'afficher qu'un libellé d'axe sur `every` (années nombreuses)."""
    labels = df.label.tolist()
    axis = alt.Axis(labelAngle=0, ticks=False,
                    values=labels[::every] if every else alt.Undefined)
    base = alt.Chart(df).encode(
        x=alt.X("label:O", sort=labels, title=None, axis=axis, scale=alt.Scale(paddingInner=0.2)),
        y=alt.Y("value:Q", title=None, axis=None),
        tooltip=[alt.Tooltip("label:O", title=label_title), alt.Tooltip("text:N", title=value_title)],
    )
    chart = base.mark_bar(cornerRadiusEnd=3, color=color)
    if show_text:
        chart = chart + base.mark_text(baseline="bottom", dy=-3).encode(text="text:N")
    else:
        df = df.assign(detail=df.label + " : " + df.text)
        tap = _tap(["label"], nearest=False)
        chart = chart.encode(opacity=alt.condition(tap, alt.value(0.7), alt.value(1))).add_params(tap)
        chart = chart + _detail(df, tap)
    return finish(chart, height=height)


def stacked_hbars(df: pd.DataFrame, *, order: list[str], series: list[str], colors: list[str],
                  value_title: str, inside_text: bool = False, totals: pd.DataFrame | None = None,
                  right: int = 10) -> alt.TopLevelMixin:
    """Barres horizontales empilées. Colonnes : label, series, value, text (valeur lisible).
    `order` : ordre des barres ; `series` et `colors` : ordre et couleur des segments.
    `totals` (facultatif) : label, value, text, affiché au bout de chaque barre."""
    rank = {s: i for i, s in enumerate(series)}
    df = df.assign(_rank=df.series.map(rank)).sort_values(["label", "_rank"])
    df["x1"] = df.groupby("label").value.cumsum()
    df["x0"] = df.x1 - df.value
    df["mid"] = df.x0 + df.value / 2
    df["ink"] = df.series.map(dict(zip(series, (text_color(c) for c in colors))))
    y = alt.Y("label:N", sort=order, title=None, axis=_multiline_axis(), scale=alt.Scale(paddingInner=0.3))
    df["detail"] = df.label.str.replace("\n", " ") + " · " + df.series + " : " + df.text
    tap = _tap(["label", "series"], nearest=False)
    bars = alt.Chart(df).mark_bar(stroke="white").encode(
        y=y, x=alt.X("x0:Q", title=None, axis=None), x2="x1:Q",
        color=alt.Color("series:N", scale=alt.Scale(domain=series, range=colors), legend=None),
        strokeWidth=alt.condition(tap, alt.value(2.5), alt.value(1)),
        tooltip=[alt.Tooltip("label:N", title=" "), alt.Tooltip("series:N", title=" "),
                 alt.Tooltip("text:N", title=value_title)],
    ).add_params(tap)
    chart = bars + _detail(df, tap)
    if inside_text:
        # Valeur dans le segment, seulement s'il est assez large : 12 % de la plus longue barre
        shown = df.assign(share=df.value / df.groupby("label").value.sum().max())
        chart = chart + alt.Chart(shown).transform_filter("datum.share >= 0.12").mark_text().encode(
            y=y, x="mid:Q", text="text:N", color=alt.Color("ink:N", scale=None))
    if totals is not None:
        chart = chart + alt.Chart(totals).mark_text(align="left", dx=6, fontWeight=600).encode(
            y=y, x="value:Q", text="text:N")
    return finish(chart, height=48 * len(order) + 10, right=right)


def lines(df: pd.DataFrame, *, value_title: str, y_domain: tuple[float, float] | None = None,
          x_ticks: list[int] | None = None, rule_y: float | None = None, end_labels: bool = False,
          shapes: bool = False, height: int = 300) -> alt.TopLevelMixin:
    """Courbes par série. Colonnes : x (année), y, series (nom), color, weight (épaisseur),
    shape (si `shapes`), text (valeur lisible, pour l'infobulle).
    `end_labels` : nom de chaque série au bout de sa courbe, écarté de ses voisins."""
    x = alt.X("x:Q", title=None, scale=alt.Scale(domain=[df.x.min(), df.x.max()], nice=False),
              axis=alt.Axis(format="d", values=x_ticks or alt.Undefined, labelAngle=0, grid=False))
    y_scale = alt.Scale(domain=list(y_domain)) if y_domain else alt.Scale(zero=False)
    y = alt.Y("y:Q", title=None, scale=y_scale, axis=alt.Axis(tickCount=5))
    # Série mise en avant dessinée en dernier, donc au premier plan
    df = df.sort_values(["weight", "series", "x"])
    tooltip = [alt.Tooltip("series:N", title=" "), alt.Tooltip("x:Q", title="Année", format="d"),
               alt.Tooltip("text:N", title=value_title)]
    line = alt.Chart(df).mark_line().encode(
        x=x, y=y, detail="series:N", color=alt.Color("color:N", scale=None),
        strokeWidth=alt.StrokeWidth("weight:Q", scale=None))
    # Points : toutes les séries si les formes servent à les distinguer, sinon la série mise en avant
    shown = df if shapes else df[df.weight >= df.weight.max()]
    points = alt.Chart(shown).mark_point(filled=True, opacity=1).encode(
        x=x, y=y, color=alt.Color("color:N", scale=None),
        size=alt.Size("weight:Q", scale=alt.Scale(domain=[2, 4], range=[30, 60]), legend=None),
        shape=alt.Shape("shape:N", scale=None) if shapes else alt.value("circle"))
    # Survol ou toucher : le point le plus proche est marqué et sa valeur écrite en haut
    df = df.assign(detail=df.series + " · " + df.x.astype(int).astype(str) + " : " + df.text)
    hover = _tap(["series", "x"])
    nearest = alt.Chart(df).mark_point(filled=True, stroke="white", strokeWidth=1.5).encode(
        x=x, y=y, color=alt.Color("color:N", scale=None),
        size=alt.condition(hover, alt.value(110), alt.value(0)),
        opacity=alt.condition(hover, alt.value(1), alt.value(0)),
        tooltip=tooltip).add_params(hover)
    chart = line + points + nearest + _detail(df, hover)
    right = 10
    if rule_y is not None:
        chart = alt.Chart(pd.DataFrame({"y": [rule_y]})).mark_rule(strokeDash=[3, 3], color="#B8BEC6").encode(
            y=alt.Y("y:Q", scale=y_scale)) + chart
    if end_labels:
        ends = df.sort_values("x").groupby("series", as_index=False).last().sort_values("y")
        span = (df.y.max() - df.y.min()) or 1
        gap, prev, placed = span * 0.06, None, []
        for v in ends.y:
            placed.append(v if prev is None else max(v, prev + gap))
            prev = placed[-1]
        ends["y_label"] = placed
        label = alt.Chart(ends).encode(x=x, y=alt.Y("y_label:Q", scale=y_scale), text="series:N")
        # Série mise en avant en gras (la graisse ne s'encode pas : deux calques)
        chart = (chart + label.transform_filter("datum.weight < 4").mark_text(align="left", dx=8)
                 + label.transform_filter("datum.weight >= 4").mark_text(align="left", dx=8, fontWeight=700))
        right = 110
    return finish(chart, height=height, right=right)


def position_strip(df: pd.DataFrame, *, order: list[str]) -> alt.TopLevelMixin:
    """Position de chaque pays entre le moins bien (0) et le mieux classé (100), par indicateur.
    Colonnes : axis_label (\\n pour couper), score, color, shape, size, country, indicator, value_txt."""
    y = alt.Y("axis_label:N", sort=order, title=None, axis=_multiline_axis(grid=True))
    x = alt.X("score:Q", title=None, scale=alt.Scale(domain=[-5, 105], nice=False),
              axis=alt.Axis(values=[0, 100], grid=False, ticks=False, domain=False,
                            labelExpr="datum.value == 0 ? '◀ moins bien' : 'mieux ▶'"))
    mid = alt.Chart(pd.DataFrame({"score": [50]})).mark_rule(strokeDash=[2, 3], color="#B8BEC6").encode(x=x)
    df = df.assign(detail=df.country + " · " + df.indicator.str.replace("\n", " ") + " : " + df.value_txt)
    tap = _tap(["country", "indicator"])
    # Bénin (taille la plus grande) dessiné en dernier, donc au premier plan
    dots = alt.Chart(df.sort_values("size")).mark_point(filled=True, opacity=1, stroke="white",
                                                        strokeWidth=1.5).encode(
        x=x, y=y, color=alt.Color("color:N", scale=None), shape=alt.Shape("shape:N", scale=None),
        size=alt.Size("size:Q", scale=None), order="size:Q",
        tooltip=[alt.Tooltip("country:N", title="Pays"), alt.Tooltip("indicator:N", title="Indicateur"),
                 alt.Tooltip("value_txt:N", title="Valeur")],
        strokeWidth=alt.condition(tap, alt.value(3), alt.value(1.5)),
    ).add_params(tap)
    lines_per_label = max((label.count("\n") + 1 for label in order), default=1)
    row = max(46, 16 * lines_per_label + 18)
    return finish(mid + dots + _detail(df, tap), height=row * len(order) + 30)


def labeled_scatter(df: pd.DataFrame, *, x_title: str, y_title: str, height: int = 360) -> alt.TopLevelMixin:
    """Nuage de points nommés. Colonnes : x, y, country, color, shape, size, bold (poids du nom), tip_x, tip_y."""
    base = alt.Chart(df).encode(
        x=alt.X("x:Q", title=x_title, scale=alt.Scale(zero=False, padding=20)),
        y=alt.Y("y:Q", title=y_title, scale=alt.Scale(zero=False, padding=20)),
    )
    tap = _tap(["country"])
    df = df.assign(detail=df.country + " · " + y_title.rstrip(" →").lower() + " : " + df.tip_y + ", "
                   + x_title.rstrip(" →").lower() + " : " + df.tip_x)
    dots = base.mark_point(filled=True, opacity=1, stroke="white", strokeWidth=1.5).encode(
        color=alt.Color("color:N", scale=None), shape=alt.Shape("shape:N", scale=None),
        size=alt.Size("size:Q", scale=None),
        tooltip=[alt.Tooltip("country:N", title="Pays"), alt.Tooltip("tip_y:N", title=y_title.rstrip(" →")),
                 alt.Tooltip("tip_x:N", title=x_title.rstrip(" →"))],
    ).add_params(tap)
    names = base.encode(text="country:N")
    names = (names.transform_filter("datum.bold < 700").mark_text(dy=-13)
             + names.transform_filter("datum.bold >= 700").mark_text(align="left", dx=12, fontWeight=700))
    return finish(dots + names + _detail(df, tap), height=height, right=20)
