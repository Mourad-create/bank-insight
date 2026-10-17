"""Agent text-to-SQL : répond en langage naturel à partir des tables dbt.

Claude reçoit le schéma des tables marts et un outil `run_sql`. Il écrit ses
requêtes, lit les résultats, puis rédige une réponse qui cite les chiffres et
les pages sources. Garde-fous :
  - connexion DuckDB en lecture seule ;
  - seules les requêtes SELECT / WITH sont acceptées ;
  - résultats tronqués à 50 lignes ;
  - 6 appels d'outil maximum par question.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

import pandas as pd

from src.common import CLAUDE_MODEL, get_connection

MAX_TOOL_CALLS = 6
MAX_ROWS = 50
ALLOWED_SCHEMAS = ("marts",)

RUN_SQL_TOOL = {
    "name": "run_sql",
    "description": "Exécute une requête SQL DuckDB en lecture seule (SELECT ou WITH) "
                   "sur les tables du schéma marts et renvoie au plus 50 lignes.",
    "input_schema": {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Requête SQL DuckDB"},
            "purpose": {"type": "string", "description": "Ce que la requête cherche à vérifier"},
        },
        "required": ["query"],
    },
}


@dataclass
class AgentResult:
    answer: str
    queries: list[str] = field(default_factory=list)
    last_result: pd.DataFrame | None = None


def is_safe_query(query: str) -> bool:
    q = re.sub(r"--.*?$|/\*.*?\*/", "", query, flags=re.S | re.M).strip().lower()
    if not (q.startswith("select") or q.startswith("with")):
        return False
    forbidden = r"\b(insert|update|delete|drop|create|alter|attach|copy|install|load|pragma|export)\b"
    return re.search(forbidden, q) is None and ";" not in q.rstrip(";")


def describe_schema(con) -> str:
    cols = con.execute(
        """
        select table_name, column_name, data_type
        from information_schema.columns
        where table_schema in ('marts')
        order by table_name, ordinal_position
        """
    ).df()
    parts = []
    for table, grp in cols.groupby("table_name", sort=False):
        columns = ", ".join(f"{c} {t}" for c, t in zip(grp.column_name, grp.data_type))
        parts.append(f"marts.{table}({columns})")
    return "\n".join(parts)


SYSTEM_PROMPT = """Tu es l'assistant d'analyse de Bank Insight, un benchmark des grandes banques européennes.
Tu réponds en français, de façon concise, comme un analyste financier.

Tables disponibles (DuckDB) :
{schema}

Repères métier :
- kpi : cet1_ratio, total_capital_ratio, leverage_ratio, cost_income_ratio, rote (en %),
  net_banking_income, net_income_group_share (en millions d'euros), cost_of_risk_bp (en points de base).
- Un coefficient d'exploitation (cost_income_ratio) plus BAS est meilleur.
- value_report = valeur lue dans le rapport annuel ; value_eba = valeur officielle EBA.

Règles :
1. Utilise TOUJOURS l'outil run_sql pour obtenir les chiffres. N'invente jamais une valeur.
2. Dans ta réponse finale, cite les chiffres avec leur unité et, quand c'est disponible,
   la source (fichier et page) issue des colonnes source_file / source_page.
3. Si les données ne permettent pas de répondre, dis-le clairement.
"""


def run_sql(con, query: str) -> tuple[str, pd.DataFrame | None]:
    if not is_safe_query(query):
        return "ERREUR : seules les requêtes SELECT/WITH en lecture sont autorisées.", None
    try:
        df = con.execute(query).df()
    except Exception as exc:  # l'erreur est renvoyée à Claude pour qu'il corrige sa requête
        return f"ERREUR SQL : {exc}", None
    shown = df.head(MAX_ROWS)
    suffix = f"\n({len(df)} lignes au total, {MAX_ROWS} affichées)" if len(df) > MAX_ROWS else ""
    return shown.to_csv(index=False) + suffix, df


def ask(question: str, client=None, con=None) -> AgentResult:
    import anthropic

    client = client or anthropic.Anthropic()
    con = con or get_connection(read_only=True)
    system = SYSTEM_PROMPT.format(schema=describe_schema(con))
    messages = [{"role": "user", "content": question}]
    result = AgentResult(answer="")

    for _ in range(MAX_TOOL_CALLS + 1):
        response = client.messages.create(
            model=CLAUDE_MODEL, max_tokens=2048, system=system,
            tools=[RUN_SQL_TOOL], messages=messages,
        )
        messages.append({"role": "assistant", "content": response.content})

        if response.stop_reason != "tool_use":
            result.answer = "".join(b.text for b in response.content if b.type == "text")
            return result

        tool_results = []
        for block in response.content:
            if block.type == "tool_use" and block.name == "run_sql":
                query = block.input["query"]
                result.queries.append(query)
                text, df = run_sql(con, query)
                if df is not None:
                    result.last_result = df
                tool_results.append({"type": "tool_result", "tool_use_id": block.id, "content": text})
        messages.append({"role": "user", "content": tool_results})

    result.answer = "Je n'ai pas pu conclure dans la limite de requêtes autorisée."
    return result


if __name__ == "__main__":
    import sys

    res = ask(" ".join(sys.argv[1:]) or "Quelle banque a le ratio CET1 le plus élevé ?")
    print(res.answer)
    print("\nRequêtes exécutées :")
    for q in res.queries:
        print("---\n" + q)
