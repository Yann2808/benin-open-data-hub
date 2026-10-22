"""Abonnements et utilisateurs ne doivent jamais être confondus : un abonnement
n'est pas une personne (une personne peut avoir plusieurs cartes SIM)."""
import re
from pathlib import Path

from ingestion.common import load_config

ROOT = Path(__file__).resolve().parents[1]
# Indicateurs World Bank exprimés en abonnements pour 100 habitants
SUBSCRIPTIONS = {"IT.CEL.SETS.P2", "IT.NET.BBND.P2"}
# Indicateurs exprimés en personnes (part de la population)
USERS = {"IT.NET.USER.ZS"}


def indicators():
    return {i["code"]: i for i in load_config()["worldbank"]["indicators"]}


def test_subscription_indicators_say_subscriptions_per_100():
    for code, ind in indicators().items():
        if code in SUBSCRIPTIONS:
            assert ind["label"].startswith("Abonnements"), ind["label"]
            assert ind["unit"] == "abonnements pour 100 habitants", ind["unit"]


def test_user_indicators_say_people_share_of_population():
    for code, ind in indicators().items():
        if code in USERS:
            assert ind["label"].startswith("Personnes"), ind["label"]
            assert "abonn" not in ind["label"].lower()
            assert ind["unit"] == "% de la population"


def test_app_text_never_mixes_users_and_subscriptions():
    text = (ROOT / "app" / "streamlit_app.py").read_text(encoding="utf-8").lower()
    # « abonnés » et « utilisateurs d'internet » sont ambigus : on écrit abonnements / personnes
    assert not re.search(r"abonné", text)
    assert "utilisateurs d'internet" not in text
