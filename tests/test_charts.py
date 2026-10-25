import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))
import charts  # noqa: E402


def layers(chart) -> list[dict]:
    """Calques Vega-Lite d'un graphique, à plat (les filtres sont dans `transform`)."""
    spec = chart.to_dict()
    out = []
    for layer in spec.get("layer", [spec]):
        out.extend(layer.get("layer", [layer]))
    return out


def test_text_color_contrasts_with_background():
    assert charts.text_color("#0F7B4B") == "#FFFFFF"  # vert du Bénin : texte blanc
    assert charts.text_color("#D2BF9E") == charts.INK  # beige des services : texte foncé
    assert charts.text_color("#E8B200") == charts.INK


def test_hbars_order_and_negative_values():
    df = pd.DataFrame({"label": ["A", "B", "C"], "value": [2.0, -1.0, 5.0], "color": "#000000",
                       "text": ["2", "−1", "5"]})
    spec = layers(charts.hbars(df, value_title="v"))
    assert spec[0]["encoding"]["y"]["sort"] == ["C", "A", "B"]
    low_first = layers(charts.hbars(df, value_title="v", ascending=True))
    assert low_first[0]["encoding"]["y"]["sort"] == ["B", "A", "C"]
    # Deux calques de texte : valeurs positives à droite, négatives à gauche
    aligns = sorted(layer["mark"].get("align") for layer in spec if layer["mark"]["type"] == "text")
    assert aligns == ["left", "right"]


def test_stacked_hbars_segments_follow_series_order():
    df = pd.DataFrame({"label": ["X", "X", "Y"], "series": ["b", "a", "a"], "value": [3.0, 1.0, 2.0],
                       "text": ["3", "1", "2"]})
    chart = charts.stacked_hbars(df, order=["X", "Y"], series=["a", "b"], colors=["#0F7B4B", "#D2BF9E"],
                                 value_title="v", inside_text=True)
    data = chart.to_dict()["datasets"]
    bars = next(v for v in data.values() if v and "x0" in v[0])
    x = {(r["label"], r["series"]): (r["x0"], r["x1"]) for r in bars}
    assert x[("X", "a")] == (0.0, 1.0) and x[("X", "b")] == (1.0, 4.0) and x[("Y", "a")] == (0.0, 2.0)


def test_lines_end_labels_do_not_overlap():
    df = pd.DataFrame({"x": [2020, 2021] * 3, "y": [10, 50, 10, 50.5, 10, 51],
                       "series": ["A", "A", "B", "B", "C", "C"], "color": "#000000",
                       "weight": [4, 4, 2, 2, 2, 2], "text": "t"})
    chart = charts.lines(df, value_title="v", end_labels=True)
    data = chart.to_dict()["datasets"]
    ends = next(v for v in data.values() if v and "y_label" in v[0])
    placed = sorted(r["y_label"] for r in ends)
    gap = (51 - 10) * 0.06
    assert all(b - a >= gap - 1e-9 for a, b in zip(placed, placed[1:]))


def test_every_country_shape_has_a_legend_glyph():
    assert set(charts.SHAPES + [charts.FOCUS_SHAPE]) <= set(charts.GLYPHS)
    assert len(set(charts.SHAPES)) == len(charts.SHAPES) == 6  # une forme par voisin


def test_axis_text_is_at_least_12px():
    df = pd.DataFrame({"label": ["A"], "value": [1.0], "text": ["1"]})
    config = charts.vbars(df, value_title="v", label_title="l", color="#000000").to_dict()["config"]
    assert config["axis"]["labelFontSize"] >= 12 and config["text"]["fontSize"] >= 12


def test_text_inside_colored_segments_meets_wcag_aa():
    """Texte écrit dans un segment coloré : contraste d'au moins 4,5 (WCAG AA)."""
    fills = ["#0F7B4B", "#E8B200", "#B8BEC6", "#8B5A33", "#5F6B7A", "#D2BF9E"]  # âges ODFA, secteurs
    for fill in fills:
        assert charts.contrast(charts.text_color(fill), fill) >= 4.5, fill
