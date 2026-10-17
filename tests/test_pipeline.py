"""Tests unitaires (sans appel à l'API ni base de données). Lancer : pytest"""
import io

import pandas as pd
from reportlab.pdfgen import canvas

from evals.run_evals import is_correct
from src.agent.sql_agent import is_safe_query
from src.extraction.extract_kpis import build_excerpt, clean_results, select_pages

BANK = {"lei": "TESTLEI0000000000000", "name": "Banque Test", "report_pdf": "test.pdf"}


def _make_pdf(path, pages_text):
    buf = io.BytesIO()
    c = canvas.Canvas(buf)
    for text in pages_text:
        c.drawString(72, 720, text)
        c.showPage()
    c.save()
    path.write_bytes(buf.getvalue())


def test_select_pages_keeps_relevant_pages_in_order(tmp_path):
    pdf = tmp_path / "r.pdf"
    _make_pdf(pdf, ["Sommaire", "Ratio CET1 de 13,1 %", "Gouvernance",
                    "Coefficient d'exploitation 62 % et ratio de levier 4,4 %"])
    pages = select_pages(pdf, max_pages=5)
    assert pages == [1, 3]
    assert len(build_excerpt(pdf, pages)) > 0


def test_clean_results_maps_pages_and_flags_issues():
    raw = [
        {"kpi": "cet1_ratio", "value": 13.1, "unit": "%", "period_end": "2024-12-31",
         "page": 2, "quote": "ratio CET1 de 13,1 %", "confidence": "high"},
        {"kpi": "rote", "value": 10.2, "unit": "%", "period_end": "2024-12-31",
         "page": 9, "quote": "ROTE 10,2 %", "confidence": "medium"},
        {"kpi": "kpi_inconnu", "value": 1, "unit": "", "period_end": "", "page": 1,
         "quote": "", "confidence": "low"},
    ]
    df = clean_results(raw, page_indices=[10, 41, 87], bank=BANK)
    assert list(df["kpi"]) == ["cet1_ratio", "rote"]          # KPI inconnu écarté
    assert df.loc[0, "source_page"] == 42                     # page 2 de l'extrait = page 42 du PDF
    assert df.loc[1, "issues"] == "page hors extrait"


def test_is_safe_query():
    assert is_safe_query("select * from marts.fct_bank_kpis")
    assert is_safe_query("WITH x AS (select 1) select * from x")
    assert not is_safe_query("drop table marts.fct_bank_kpis")
    assert not is_safe_query("select 1; delete from raw.banks")
    assert not is_safe_query("-- commentaire\ninsert into raw.banks values (1)")


def test_eval_comparison():
    expected = pd.DataFrame({"bank_name": ["BNP Paribas"]})
    got = pd.DataFrame({"bank_name": ["BNP Paribas"], "cet1_ratio": [12.9]})
    assert is_correct(expected, got)
    assert not is_correct(expected, pd.DataFrame({"bank_name": ["BBVA"]}))
    assert not is_correct(expected, None)
