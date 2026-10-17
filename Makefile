# Raccourcis (sous Windows, lance les commandes à la main ou utilise Git Bash)
.PHONY: setup data extract dbt app evals test all

setup:
	python -m venv .venv && . .venv/bin/activate && pip install -r requirements.txt

data:
	python -m src.ingestion.download_eba
	python -m src.ingestion.load_eba

extract:
	python -m src.extraction.extract_kpis

dbt:
	cd dbt && dbt build --profiles-dir .

app:
	streamlit run app/streamlit_app.py

evals:
	python -m evals.run_evals

test:
	pytest -q

all: data extract dbt
