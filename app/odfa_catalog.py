"""Mise en forme du catalogue Open Data for Africa pour le dashboard.

Le portail n'expose que des identifiants « slug » (ex. ``eds-prévalence-et-traitement-de-l-ira``),
une catégorie unique (« Manual ») et un nom de producteur saisi librement. On en tire un titre
lisible, un thème et une famille de producteur. Le thème est une estimation par mots-clés,
présentée comme telle dans l'app.
"""
from __future__ import annotations

import re

import pandas as pd

# Sigles d'enquêtes et de recensements de l'INStaD/INSAE en tête des slugs
SURVEYS = {
    "mics": "MICS", "eds": "EDS", "eri": "ERI-ESI", "rge": "RGE", "rge3": "RGE-3", "ehcvm": "EHCVM",
    "emb2": "EMB-2", "etva": "ETVA", "eet": "EET", "agvsa": "AGVSA", "emicov": "EMICoV",
    "ecene": "ECENE", "esa": "ESA", "rgph": "RGPH", "tic": "TIC", "insae": "INSAE",
}
# Thème connu de chaque enquête : prioritaire sur les mots-clés (« RGE … inscription au
# registre du commerce » parle d'entreprises, pas d'éducation)
SURVEY_THEMES = {
    "MICS": "Enfance et protection sociale", "EDS": "Santé", "ERI-ESI": "Emploi et revenus",
    "RGE": "Entreprises et commerce", "RGE-3": "Entreprises et commerce", "EHCVM": "Conditions de vie",
    "EMB-2": "Population", "ETVA": "Emploi et revenus", "EET": "Emploi et revenus",
    "AGVSA": "Agriculture et alimentation", "EMICoV": "Conditions de vie",
    "ECENE": "Entreprises et commerce", "RGPH": "Population",
}
# Sigles en minuscules dans les slugs, remis en capitales dans les titres
ACRONYMS = {"ist": "IST", "vih": "VIH", "tic": "TIC", "tpi": "TPI", "pib": "PIB", "ong": "ONG",
            "uemoa": "UEMOA", "cnss": "CNSS", "odd": "ODD", "benin": "Bénin", "bénin": "Bénin"}
# Le slug est tronqué par le portail à 100 caractères
SLUG_MAX = 100

# Thème estimé : premier groupe dont un mot-clé apparaît dans le titre ou le producteur.
# L'ordre compte (ex. « sécurité alimentaire » doit tomber dans Agriculture, pas Sécurité).
THEME_KEYWORDS: list[tuple[str, tuple[str, ...]]] = [
    ("Agriculture et alimentation", ("agvsa", "agricult", "agruclture", "élevage", "elevage", "pêche",
                                     "alimentaire", "agricol", "cultures vivrières")),
    ("Santé", ("eds", "santé", "sante", "sida", "ist", "mortalité", "prévalence", "vaccin",
               "paludisme", "nutrition", "allaitement", "contracept", "fécondité", "maternelle et infantile")),
    ("Enfance et protection sociale", ("mics", "enfant", "affaires sociales", "protection", "cnss",
                                       "sécurité sociale", "microfinance")),
    ("Éducation", ("enseignement", "école", "scolar", "étudiant", "etudiant", "alphab", "inscription",
                   "éducation", "education", "université")),
    ("Emploi et revenus", ("eri", "etva", "emploi", "chômage", "travail", "eet", "fonction publique",
                           "salaire", "secteur informel")),
    ("Conditions de vie", ("ehcvm", "emicov", "ménage", "menage", "pauvreté", "conditions de vie")),
    ("Population", ("rgph", "emb2", "migra", "population", "démograph", "recensement général de la population")),
    ("Entreprises et commerce", ("rge", "ecene", "commerce", "industri", "entreprise", "prix",
                                 "comptes nationaux", "cci", "chambre de commerce")),
    ("Sécurité et justice", ("sécurité", "securite", "justice", "défense", "defense", "accident",
                             "cnsr", "police", "routière", "intérieur", "affaires étrangères", "coopération")),
    ("Environnement et climat", ("environnement", "climat", "météo", "meteo", "emission", "pluviom",
                                 "effet de serre")),
    ("Infrastructures et énergie", ("energie", "énergie", "électri", "sbee", "eau", "soneb", "transport",
                                    "infrastructure", "tic", "communication", "mines", "asecna",
                                    "cadre de vie", "navigation aérienne", "port autonome")),
    ("Culture, sports et tourisme", ("culture", "sport", "tourisme")),
]
OTHER_THEME = "Autre"


def humanize_title(slug: str | None) -> str:
    """``eds-prévalence-et-traitement-de-l-ira`` → ``EDS — Prévalence et traitement de l'ira``."""
    if not slug:
        return ""
    words = slug.strip("-").split("-")
    prefix = SURVEYS.get(words[0].lower())
    if prefix and len(words) > 1:
        words = words[1:]
    if prefix == "ERI-ESI" and words and words[0].lower() in ("eri", "esi"):
        words = words[1:]  # « eri-esi-… » : sigle répété dans le slug
    text = " ".join(ACRONYMS.get(w.lower(), w) for w in words if w)
    # Élisions perdues dans le slug : « de l emploi » → « de l'emploi », « qu il » → « qu'il »
    text = re.sub(r"\b([ldjmnst]|qu|jusqu|lorsqu|puisqu) (?=[aeiouhyàâéèêëîïôûü])", r"\1'", text,
                  flags=re.IGNORECASE)
    text = text.replace("vis à vis", "vis-à-vis")
    if len(slug) >= SLUG_MAX:
        text = text.rstrip() + "…"
    text = text[:1].upper() + text[1:]
    return f"{prefix} — {text}" if prefix else text


def survey_code(slug: str | None) -> str | None:
    """Sigle de l'enquête source quand le slug en commence par un (MICS, EDS…)."""
    if not slug:
        return None
    return SURVEYS.get(slug.split("-")[0].lower())


def estimate_theme(title: str | None, source: str | None) -> str:
    survey = survey_code(title)
    if survey in SURVEY_THEMES:
        return SURVEY_THEMES[survey]
    # Mots entiers pour les mots-clés courts (« eds », « eau », « tic »…), sous-chaîne sinon
    text = f" {(title or '').replace('-', ' ')} {source or ''} ".lower()
    for theme, keywords in THEME_KEYWORDS:
        for kw in keywords:
            if (len(kw) <= 4 and re.search(rf"\b{re.escape(kw)}\b", text)) or (len(kw) > 4 and kw in text):
                return theme
    return OTHER_THEME


def producer_family(source: str | None) -> str:
    s = (source or "").lower()
    if any(k in s for k in ("insae", "instad", "institut national de la statistique")) and "rwanda" not in s:
        return "INStaD"
    if any(k in s for k in ("ministère", "ministere", "miinistère", "direction de")):
        return "Ministères"
    if any(k in s for k in ("united nations", "rwanda")):
        return "International"
    return "Agences publiques"


def freshness_bucket(days: float | None) -> str:
    if days is None or pd.isna(days):
        return "inconnue"
    if days <= 365:
        return "moins d'un an"
    if days <= 3 * 365:
        return "1 à 3 ans"
    return "plus de 3 ans"


# Âge des jeux : année de la dernière mise à jour déclarée par le portail
UPDATE_PERIODS = ("depuis 2024", "2020 à 2023", "avant 2020", "date inconnue")


def update_period(last_updated) -> str:
    if last_updated is None or pd.isna(last_updated):
        return "date inconnue"
    year = pd.Timestamp(last_updated).year
    if year >= 2024:
        return "depuis 2024"
    if year >= 2020:
        return "2020 à 2023"
    return "avant 2020"


def age_table(datasets: pd.DataFrame, by: str) -> pd.DataFrame:
    """Nombre de jeux par période de dernière mise à jour, ventilé selon `by`
    (ex. producer), avec une colonne total ; colonnes dans l'ordre des périodes."""
    periods = datasets["last_updated_on"].map(update_period)
    table = pd.crosstab(datasets[by], periods).reindex(columns=list(UPDATE_PERIODS), fill_value=0)
    table = table.loc[:, (table.sum() > 0) | (table.columns != "date inconnue")]
    table["total"] = table.sum(axis=1)
    return table.sort_values("total", ascending=False)


def enrich(datasets: pd.DataFrame) -> pd.DataFrame:
    """Ajoute titre lisible, sigle, thème estimé, famille de producteur et fraîcheur."""
    df = datasets.copy()
    df["title_fr"] = df["title"].map(humanize_title)
    df["survey"] = df["title"].map(survey_code)
    df["theme"] = [estimate_theme(t, s) for t, s in zip(df["title"], df["source_name"])]
    df["producer"] = df["source_name"].map(producer_family)
    df["freshness"] = df["days_since_update"].map(freshness_bucket)
    df["update_period"] = df.get("last_updated_on", pd.Series(None, index=df.index)).map(update_period)
    return df
