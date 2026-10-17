"""Extraction des KPI financiers des rapports annuels avec l'API Claude.

Étapes pour chaque banque :
  1. Pré-sélection des pages utiles : un rapport annuel fait 500+ pages, on ne
     garde que les ~30 pages qui contiennent les mots-clés des KPI
     (moins cher, plus rapide, et sous la limite de pages de l'API).
  2. Envoi de l'extrait PDF à Claude avec un outil `record_kpis` imposé :
     la réponse est forcément un JSON structuré (valeur, unité, page, citation).
  3. Contrôles automatiques (KPI connu, valeur numérique, page existante) et
     écriture dans DuckDB (raw.extracted_kpis) + cache JSON.

Usage :
  python -m src.extraction.extract_kpis                  # toutes les banques
  python -m src.extraction.extract_kpis --bank "BNP"     # une seule banque
  python -m src.extraction.extract_kpis --force          # ignorer le cache
"""
from __future__ import annotations

import argparse
import base64
import io
import json
from datetime import datetime, timezone

import pandas as pd
from pypdf import PdfReader, PdfWriter

from src.common import CLAUDE_MODEL, DATA_DIR, RAW_REPORTS_DIR, get_connection, load_config
from src.extraction.kpis import KPIS

CACHE_DIR = DATA_DIR / "extracted"
MAX_PAGES = 30

RECORD_KPIS_TOOL = {
    "name": "record_kpis",
    "description": "Enregistre les KPI financiers trouvés dans l'extrait de rapport annuel.",
    "input_schema": {
        "type": "object",
        "properties": {
            "kpis": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "kpi": {"type": "string", "enum": list(KPIS)},
                        "value": {"type": ["number", "null"],
                                  "description": "Valeur numérique dans l'unité demandée, null si introuvable."},
                        "unit": {"type": "string"},
                        "period_end": {"type": "string", "description": "Date de référence AAAA-MM-JJ"},
                        "page": {"type": ["integer", "null"],
                                 "description": "Numéro de page DANS L'EXTRAIT fourni (1 = première page)."},
                        "quote": {"type": "string",
                                  "description": "Citation exacte et courte du passage contenant la valeur."},
                        "confidence": {"type": "string", "enum": ["high", "medium", "low"]},
                    },
                    "required": ["kpi", "value", "unit", "period_end", "page", "quote", "confidence"],
                },
            }
        },
        "required": ["kpis"],
    },
}


# ---------------------------------------------------------------- 1. pages utiles
def select_pages(pdf_path, max_pages: int = MAX_PAGES) -> list[int]:
    """Renvoie les indices (0-based) des pages les plus pertinentes, dans l'ordre du document."""
    reader = PdfReader(str(pdf_path))
    keywords = [k.lower() for kpi in KPIS.values() for k in kpi["keywords"]]
    scores = []
    for i, page in enumerate(reader.pages):
        text = (page.extract_text() or "").lower()
        score = sum(text.count(k) for k in keywords)
        if score:
            scores.append((score, i))
    best = sorted(scores, reverse=True)[:max_pages]
    return sorted(i for _, i in best)


def build_excerpt(pdf_path, page_indices: list[int]) -> bytes:
    reader = PdfReader(str(pdf_path))
    writer = PdfWriter()
    for i in page_indices:
        writer.add_page(reader.pages[i])
    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue()


# ---------------------------------------------------------------- 2. appel Claude
def build_prompt(bank_name: str, reference_date: str) -> str:
    lines = [f"- {k} ({v['unit']}) : {v['definition']}" for k, v in KPIS.items()]
    return (
        f"Tu es analyste financier. Voici un extrait du rapport annuel de {bank_name}.\n"
        f"Extrais les KPI suivants à la date de référence {reference_date} "
        f"(exercice clos à cette date) :\n" + "\n".join(lines) + "\n\n"
        "Règles strictes :\n"
        "- Ne reporte QUE des valeurs écrites dans le document. Si un KPI est introuvable, "
        "mets value = null et page = null. N'estime et ne calcule jamais une valeur.\n"
        "- Convertis dans l'unité demandée (ex. 'milliards' → millions ; 13,1 % → 13.1).\n"
        "- `page` = numéro de page dans l'extrait fourni (la première page vaut 1).\n"
        "- `quote` = citation exacte, courte, contenant le chiffre.\n"
        "Appelle l'outil record_kpis une seule fois avec tous les KPI."
    )


def call_claude(pdf_bytes: bytes, bank_name: str, reference_date: str) -> list[dict]:
    import anthropic

    client = anthropic.Anthropic()  # lit ANTHROPIC_API_KEY dans l'environnement
    response = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=4096,
        tools=[RECORD_KPIS_TOOL],
        tool_choice={"type": "tool", "name": "record_kpis"},
        messages=[{
            "role": "user",
            "content": [
                {"type": "document",
                 "source": {"type": "base64", "media_type": "application/pdf",
                            "data": base64.standard_b64encode(pdf_bytes).decode()}},
                {"type": "text", "text": build_prompt(bank_name, reference_date)},
            ],
        }],
    )
    for block in response.content:
        if block.type == "tool_use" and block.name == "record_kpis":
            return block.input["kpis"]
    raise RuntimeError(f"Pas d'appel à record_kpis dans la réponse ({response.stop_reason})")


# ---------------------------------------------------------------- 3. contrôles
def clean_results(raw: list[dict], page_indices: list[int], bank: dict) -> pd.DataFrame:
    """Valide la sortie de Claude et remet les numéros de page du PDF original."""
    rows = []
    for item in raw:
        issues = []
        if item.get("kpi") not in KPIS:
            continue
        value = item.get("value")
        if value is not None and not isinstance(value, (int, float)):
            issues.append("valeur non numérique")
            value = None
        page = item.get("page")
        original_page = None
        if page is not None:
            if 1 <= page <= len(page_indices):
                original_page = page_indices[page - 1] + 1  # 1-based dans le PDF complet
            else:
                issues.append("page hors extrait")
        if value is not None and not item.get("quote"):
            issues.append("citation manquante")
        rows.append({
            "lei_code": bank["lei"],
            "bank_name": bank["name"],
            "kpi": item["kpi"],
            "value": value,
            "unit": item.get("unit"),
            "period_end": item.get("period_end"),
            "source_file": bank["report_pdf"],
            "source_page": original_page,
            "quote": item.get("quote"),
            "confidence": item.get("confidence"),
            "issues": "; ".join(issues) or None,
            "model": CLAUDE_MODEL,
            "extracted_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        })
    return pd.DataFrame(rows)


# ---------------------------------------------------------------- orchestration
def extract_bank(bank: dict, reference_date: str, force: bool = False) -> pd.DataFrame | None:
    pdf_path = RAW_REPORTS_DIR / bank["report_pdf"]
    if not pdf_path.exists():
        print(f"⚠ {bank['name']} : {pdf_path.name} absent de data/raw/reports/, ignoré")
        return None
    cache = CACHE_DIR / f"{pdf_path.stem}.json"
    if cache.exists() and not force:
        print(f"✓ {bank['name']} : depuis le cache")
        return pd.DataFrame(json.loads(cache.read_text(encoding="utf-8")))

    pages = select_pages(pdf_path)
    print(f"→ {bank['name']} : {len(pages)} pages envoyées à Claude")
    raw = call_claude(build_excerpt(pdf_path, pages), bank["name"], reference_date)
    df = clean_results(raw, pages, bank)
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache.write_text(df.to_json(orient="records", force_ascii=False, indent=2), encoding="utf-8")
    found = df["value"].notna().sum()
    print(f"✓ {bank['name']} : {found}/{len(KPIS)} KPI trouvés")
    return df


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--bank", help="filtre sur le nom de la banque")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    config = load_config()
    banks = [b for b in config["banks"]
             if not args.bank or args.bank.lower() in b["name"].lower()]
    frames = [df for b in banks
              if (df := extract_bank(b, config["reference_date"], args.force)) is not None]
    if not frames:
        raise SystemExit("Aucun rapport traité.")

    # On recharge tout le cache pour que la table contienne toutes les banques.
    all_rows = pd.concat([pd.read_json(p, dtype=False, convert_dates=False) for p in CACHE_DIR.glob("*.json")], ignore_index=True)
    con = get_connection()
    con.execute("CREATE OR REPLACE TABLE raw.extracted_kpis AS SELECT * FROM all_rows")
    con.close()
    print(f"✓ raw.extracted_kpis : {len(all_rows)} lignes")


if __name__ == "__main__":
    main()
