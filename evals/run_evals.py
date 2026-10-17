"""Mesure la précision de l'agent text-to-SQL sur evals/questions.yaml.

Usage : python -m evals.run_evals
Écrit un rapport dans evals/results/AAAA-MM-JJ_HHMM.csv : garde l'historique
pour montrer la progression (ex. 60 % → 90 %) dans ton README.
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pandas as pd
import yaml

from src.agent.sql_agent import ask
from src.common import get_connection

EVAL_DIR = Path(__file__).parent


def normalize(df: pd.DataFrame | None) -> set:
    """Ensemble des valeurs (arrondies) d'un résultat, indépendamment des noms de colonnes."""
    if df is None:
        return set()
    values = set()
    for v in df.to_numpy().ravel():
        if v is None or (isinstance(v, float) and pd.isna(v)):
            continue
        values.add(round(float(v), 2) if isinstance(v, (int, float)) else str(v).strip().lower())
    return values


def is_correct(expected: pd.DataFrame, got: pd.DataFrame | None) -> bool:
    # Correct si toutes les valeurs attendues se trouvent dans le résultat de l'agent
    # (l'agent peut renvoyer des colonnes en plus, par exemple le nom de la banque).
    exp = normalize(expected)
    return bool(exp) and exp.issubset(normalize(got))


def main() -> None:
    questions = yaml.safe_load((EVAL_DIR / "questions.yaml").read_text(encoding="utf-8"))
    con = get_connection(read_only=True)
    rows = []
    for q in questions:
        expected = con.execute(q["expected_sql"]).df()
        res = ask(q["question"], con=con)
        ok = is_correct(expected, res.last_result)
        rows.append({"id": q["id"], "question": q["question"], "correct": ok,
                     "n_queries": len(res.queries), "answer": res.answer})
        print(f"{'✓' if ok else '✗'} {q['id']} {q['question']}")

    report = pd.DataFrame(rows)
    out = EVAL_DIR / "results" / f"{datetime.now():%Y-%m-%d_%H%M}.csv"
    out.parent.mkdir(exist_ok=True)
    report.to_csv(out, index=False)
    print(f"\nPrécision : {report['correct'].mean():.0%} ({report['correct'].sum()}/{len(report)})")
    print(f"Rapport : {out}")


if __name__ == "__main__":
    main()
