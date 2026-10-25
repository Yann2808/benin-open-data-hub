"""Test de fumée du dashboard : chaque page s'exécute sans exception.

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

    # Pages déclarées par st.navigation sous forme de fonctions : AppTest.switch_page
    # n'accepte que des fichiers, on ouvre donc chaque page par son identifiant.
    pages = {info.get("url_pathname"): h for h, info in at._registered_pages.items()}
    assert {"fiche-pays", "investir", "comparer", "catalogue", "acces", "methode"} <= set(pages)
    for url_path, page_hash in pages.items():
        at._page_hash = page_hash
        at.run()
        assert not at.exception, (url_path, [e.value for e in at.exception])
