"""Bank Insight : interface de démonstration.

Lancer depuis la racine du projet : streamlit run app/streamlit_app.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import streamlit as st  # noqa: E402

from src.agent.sql_agent import ask  # noqa: E402
from src.common import get_connection  # noqa: E402

st.set_page_config(page_title="Bank Insight", page_icon="🏦", layout="wide")
st.title("🏦 Bank Insight")
st.caption("Benchmark des grandes banques européennes : rapports annuels lus par Claude, "
           "contrôlés contre les données officielles de l'EBA.")


@st.cache_resource
def connection():
    return get_connection(read_only=True)


con = connection()
tab_bench, tab_quality, tab_ask = st.tabs(["Benchmark", "Fiabilité de l'extraction", "Poser une question"])

with tab_bench:
    df = con.execute("select * from marts.mart_bank_benchmark order by cet1_ratio_eba desc").df()
    c1, c2, c3 = st.columns(3)
    c1.metric("Banques couvertes", len(df))
    c2.metric("CET1 médian (EBA)", f"{df['cet1_ratio_eba'].median():.1f} %" if len(df) else "n/d")
    c3.metric("Coef. d'exploitation médian",
              f"{df['cost_income_ratio'].median():.1f} %" if df['cost_income_ratio'].notna().any() else "à extraire")
    kpi = st.selectbox("Indicateur", [c for c in df.columns
                                      if c not in ("lei_code", "bank_name", "country", "period_end")
                                      and df[c].notna().any()])
    st.bar_chart(df.set_index("bank_name")[kpi].sort_values())
    st.dataframe(df, use_container_width=True, hide_index=True)

with tab_quality:
    q = con.execute("select * from marts.mart_extraction_quality order by status, bank_name").df()
    compared = q[q["status"].isin(["concordant", "ecart"])]
    rate = (compared["status"] == "concordant").mean() * 100 if len(compared) else 0
    st.metric("Concordance Claude vs EBA", f"{rate:.0f} %", help=f"{len(compared)} valeurs comparées")
    st.dataframe(q, use_container_width=True, hide_index=True)

with tab_ask:
    st.write("Exemples : *Quelle banque française a le meilleur coefficient d'exploitation ?* · "
             "*Compare le CET1 de BNP Paribas et de Deutsche Bank.*")
    question = st.text_input("Ta question")
    if question:
        with st.spinner("Claude analyse les données…"):
            res = ask(question, con=con)
        st.markdown(res.answer)
        with st.expander("Requêtes SQL exécutées"):
            for query in res.queries:
                st.code(query, language="sql")
