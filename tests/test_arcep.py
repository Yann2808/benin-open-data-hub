"""Prototype ARCEP : tests sur un texte SYNTHÉTIQUE (opérateurs et chiffres fictifs),
pour ne reproduire aucun contenu de l'ARCEP dans le dépôt."""
from ingestion import arcep

PAGE = """
 I. INTERNET FIXE
  Tableau 1 : Évolution Abonnements Fictifs

            OPERATEURS                       T3_2025       T4_2025        T1_2026

                OPERATEUR A                    1 234          2 345          3 456
                OPERATEUR B                      -             12              7
         Parc total                            1 234          2 357          3 463
  Pénétration (%)                              0,10%          0,20%          0,30%
   Ligne repliée sur
                            1 234 2 357 3 463
 Source : (Observatoire fictif, 2026)
 Graphique 1 : Répartition
                OPERATEUR C                      9             9              9
"""


def test_parse_page_keeps_provenance_and_parses_numbers():
    records, unread = arcep.parse_page_text(PAGE, 2, "fictif.pdf", "t")
    by = {(r["row_label"], r["period"]): r for r in records}

    assert len(records) == 4 * 3
    first = by[("OPERATEUR A", "T3_2025")]
    assert first["value"] == 1234 and first["unit"] == "nombre" and first["value_raw"] == "1 234"
    assert (first["source_file"], first["page"], first["table"]) == ("fictif.pdf", 2, "Évolution Abonnements Fictifs")
    assert first["status"] == "à vérifier"
    assert by[("OPERATEUR B", "T3_2025")]["value"] is None  # « - » : pas de valeur inventée
    assert by[("Pénétration (%)", "T1_2026")]["value"] == 0.30
    assert by[("Pénétration (%)", "T1_2026")]["unit"] == "%"
    # Après « Source : », les lignes ne font plus partie du tableau
    assert not any(r["row_label"] == "OPERATEUR C" for r in records)
    # Ligne dont les nombres ne sont pas séparés : signalée, jamais devinée
    assert unread == ["page 2, Évolution Abonnements Fictifs : 1 234 2 357 3 463"]
    assert all(set(r) == set(arcep.COLUMNS) for r in records)


def test_parse_value():
    assert arcep.parse_value("36 475") == (36475, "nombre")
    assert arcep.parse_value("23,17") == (23.17, "nombre")
    assert arcep.parse_value("0,95%") == (0.95, "%")
    assert arcep.parse_value("-") == (None, "nombre")
