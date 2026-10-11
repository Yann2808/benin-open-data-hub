# Toutes les commandes utilisent l'environnement du projet (.venv) s'il existe,
# même s'il n'est pas activé : on évite ainsi de mélanger avec conda (base)
# ou un autre Python du système.
VENV := $(CURDIR)/.venv
PY   ?= $(if $(wildcard $(VENV)/bin/python),$(VENV)/bin/python,python3)
DBT  ?= $(if $(wildcard $(VENV)/bin/dbt),$(VENV)/bin/dbt,dbt)
STREAMLIT ?= $(if $(wildcard $(VENV)/bin/streamlit),$(VENV)/bin/streamlit,streamlit)
DBT_RUN = cd transform && $(DBT)

.PHONY: venv install demo run ingest transform test app docs diagnose clean

venv:               ## Crée l'environnement du projet (Python 3.10 à 3.12)
	python3 -m venv .venv

install:            ## Installe les dépendances (versions précompilées en priorité)
	@test -x "$(VENV)/bin/python" || (echo "Pas de .venv : lance d'abord 'make venv'" && exit 1)
	$(PY) -m pip install --upgrade pip
	$(PY) -m pip install --prefer-binary -r requirements.txt

demo:               ## Pipeline complet sur données de démo (sans réseau)
	$(PY) tests/fixtures/make_fixtures.py
	$(PY) -m ingestion.run --offline
	$(DBT_RUN) build --profiles-dir .

run: ingest transform   ## Pipeline complet sur les vraies sources

ingest:
	$(PY) -m ingestion.run

transform:
	$(DBT_RUN) build --profiles-dir .

test:               ## Tests Python + tests dbt
	$(PY) -m pytest -q
	$(DBT_RUN) test --profiles-dir .

app:                ## Lance le dashboard
	$(STREAMLIT) run app/streamlit_app.py

docs:               ## Documentation dbt (lignage, descriptions)
	$(DBT_RUN) docs generate --profiles-dir . && $(DBT) docs serve --profiles-dir .

diagnose:           ## Diagnostic à copier en cas de problème
	@$(PY) scripts/diagnose.py

clean:
	rm -rf warehouse/*.duckdb transform/target transform/logs data/raw/*
