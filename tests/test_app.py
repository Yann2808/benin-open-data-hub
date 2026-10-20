"""Test de fumée du dashboard : chaque onglet s'exécute sans exception.

Nécessite un entrepôt (make demo / make run) ou des exports Parquet ;
sinon le test est ignoré.
"""
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "app" / "streamlit_app.py"


@pytest.mark.skipif(
    not (ROOT / "warehouse" / "benin.duckdb").exists() and not any((ROOT / "exports").glob("*.parquet")),
    reason="pas de données : lance make demo",
)
def test_app_runs_without_exception():
    from streamlit.testing.v1 import AppTest

    at = AppTest.from_file(str(APP), default_timeout=180).run()
    assert not at.exception, [e.value for e in at.exception]
    labels = [t.label for t in at.tabs]
    assert any("Accès aux données" in label for label in labels)
