"""Charge les fichiers EBA dans DuckDB (schéma raw).

Usage :
  python -m src.ingestion.load_eba                 # charge tr_oth + métadonnées
  python -m src.ingestion.load_eba --search cet1   # cherche un code Item par libellé

La recherche sert à remplir dbt/seeds/eba_item_mapping.csv : pour chaque KPI
(cet1_ratio, total_capital_ratio, leverage_ratio…), on note le code Item EBA
correspondant. C'est une étape volontairement manuelle et documentée : tu dois
comprendre ce que mesure chaque code.
"""
from __future__ import annotations

import argparse
import csv

import pandas as pd

from src.common import RAW_EBA_DIR, get_connection, load_config

# Les noms de colonnes varient légèrement d'un exercice à l'autre :
# on les ramène à un format standard.
COLUMN_ALIASES = {
    "lei_code": "lei_code", "lei": "lei_code",
    "nsa": "country", "country": "country",
    "period": "period",
    "item": "item",
    "label": "label",
    "amount": "amount", "value": "amount",
    "bank_name": "bank_name", "name": "bank_name",
}


def _sniff_delimiter(path) -> str:
    with open(path, encoding="utf-8", errors="replace") as f:
        sample = f.read(20_000)
    return csv.Sniffer().sniff(sample, delimiters=",;|\t").delimiter


def read_eba_csv(path) -> pd.DataFrame:
    df = pd.read_csv(path, sep=_sniff_delimiter(path), dtype=str, encoding="utf-8",
                     encoding_errors="replace")
    df.columns = [c.strip().lower() for c in df.columns]
    df = df.rename(columns={c: COLUMN_ALIASES[c] for c in df.columns if c in COLUMN_ALIASES})
    missing = {"lei_code", "period", "item", "amount"} - set(df.columns)
    if missing:
        raise ValueError(
            f"Colonnes attendues absentes de {path.name}: {missing}. "
            f"Colonnes trouvées : {list(df.columns)} → complète COLUMN_ALIASES."
        )
    if "label" not in df.columns:  # libellés absents : on les cherchera dans TR_Metadata.xlsx
        df["label"] = None
    df["source_file"] = path.name
    return df


def read_metadata() -> pd.DataFrame | None:
    path = RAW_EBA_DIR / "TR_Metadata.xlsx"
    if not path.exists():
        return None
    # On concatène toutes les feuilles : la structure exacte change selon les années.
    sheets = pd.read_excel(path, sheet_name=None, dtype=str)
    frames = []
    for name, df in sheets.items():
        df.columns = [str(c).strip().lower() for c in df.columns]
        df["sheet"] = name
        frames.append(df)
    return pd.concat(frames, ignore_index=True)


def load() -> None:
    con = get_connection()
    frames = [read_eba_csv(p) for p in sorted(RAW_EBA_DIR.glob("tr_*.csv"))]
    if not frames:
        raise SystemExit("Aucun fichier tr_*.csv dans data/raw/eba/ → lance d'abord download_eba.")
    eba = pd.concat(frames, ignore_index=True)
    con.execute("CREATE OR REPLACE TABLE raw.eba_transparency AS SELECT * FROM eba")
    print(f"✓ raw.eba_transparency : {len(eba):,} lignes, {eba['lei_code'].nunique()} banques")

    banks = pd.DataFrame(load_config()["banks"]).rename(columns={"lei": "lei_code", "name": "bank_name"})
    con.execute("CREATE OR REPLACE TABLE raw.banks AS SELECT * FROM banks")
    print(f"✓ raw.banks : {len(banks)} banques suivies")

    meta = read_metadata()
    if meta is not None:
        con.execute("CREATE OR REPLACE TABLE raw.eba_metadata AS SELECT * FROM meta")
        print(f"✓ raw.eba_metadata : {len(meta):,} lignes")
    con.close()


def search(term: str) -> None:
    """Cherche `term` dans les libellés des données ET dans les métadonnées EBA."""
    con = get_connection(read_only=True)
    pd.set_option("display.max_colwidth", 90)
    pd.set_option("display.width", 200)

    print(f"=== Données (raw.eba_transparency) : libellés contenant « {term} » ===")
    q = """
        SELECT item, any_value(label) AS label, count(*) AS n_rows
        FROM raw.eba_transparency
        WHERE lower(coalesce(label, '')) LIKE '%' || lower(?) || '%'
        GROUP BY item ORDER BY item
    """
    found = con.execute(q, [term]).df()
    print(found.to_string(index=False) if len(found) else "(aucun résultat)")

    # Les métadonnées ne servent qu'en dernier recours (elles contiennent surtout des notes).
    if len(found) == 0:
        print(f"\n=== Métadonnées (TR_Metadata.xlsx) : lignes contenant « {term} » ===")
        meta = con.execute("select * from raw.eba_metadata").df().astype(str)
        mask = meta.apply(lambda col: col.str.contains(term, case=False, na=False)).any(axis=1)
        hits = meta[mask]
        hits = hits.loc[:, (hits != "None").any() & (hits != "nan").any()]
        print(hits.head(20).to_string(index=False) if len(hits) else "(aucun résultat)")


def check_banks(items: list[str]) -> None:
    """Vérifie que les LEI de config/banks.yaml existent dans l'EBA et affiche
    les valeurs des items demandés au 31/12/2024 (pour voir leur unité)."""
    con = get_connection(read_only=True)
    banks = pd.DataFrame(load_config()["banks"])
    present = set(r[0] for r in con.execute("select distinct lei_code from raw.eba_transparency").fetchall())
    print("=== Banques de config/banks.yaml présentes dans les données EBA ===")
    for _, b in banks.iterrows():
        print(f"{'✓' if b['lei'] in present else '✗ LEI INTROUVABLE'}  {b['name']:<25} {b['lei']}")
    if not items:
        return
    print(f"\n=== Valeurs au 31/12/2024 pour les items {', '.join(items)} ===")
    q = f"""
        select b.name as bank, e.item, any_value(e.label) as label, any_value(e.amount) as amount
        from raw.eba_transparency e
        join banks b on b.lei = e.lei_code
        where e.period = '202412' and e.item in ({",".join("?" * len(items))})
        group by 1, 2 order by 2, 1
    """
    pd.set_option("display.width", 200)
    pd.set_option("display.max_colwidth", 60)
    print(con.execute(q, items).df().to_string(index=False))


def inspect() -> None:
    """Affiche la structure des tables pour comprendre les données."""
    con = get_connection(read_only=True)
    pd.set_option("display.width", 200)
    pd.set_option("display.max_columns", 30)
    for table in ("eba_transparency", "eba_metadata"):
        print(f"\n=== raw.{table} : colonnes ===")
        print(con.execute(f"describe raw.{table}").df()[["column_name", "column_type"]].to_string(index=False))
        print(f"\n=== raw.{table} : 5 premières lignes ===")
        print(con.execute(f"select * from raw.{table} limit 5").df().to_string(index=False))
    print("\n=== Périodes disponibles ===")
    print(con.execute("select period, count(*) n from raw.eba_transparency group by 1 order by 1").df()
          .to_string(index=False))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--search", help="mot-clé à chercher dans les libellés EBA")
    parser.add_argument("--inspect", action="store_true", help="affiche la structure des données")
    parser.add_argument("--check-banks", nargs="*", metavar="ITEM",
                        help="vérifie les LEI et affiche les valeurs des items donnés")
    args = parser.parse_args()
    if args.inspect:
        inspect()
    elif args.check_banks is not None:
        check_banks(args.check_banks)
    elif args.search:
        search(args.search)
    else:
        load()
