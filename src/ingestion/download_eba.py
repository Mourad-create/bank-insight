"""Télécharge la base complète de l'exercice de transparence EBA 2025.

Source : https://www.eba.europa.eu/risk-and-data-analysis/risk-analysis/eu-wide-transparency-exercise
L'exercice 2025 couvre 119 banques, aux dates 30/09/2024, 31/12/2024,
31/03/2025 et 30/06/2025. C'est le dernier exercice publié : l'EBA renvoie
désormais vers son Pillar 3 Data Hub (piste d'évolution du projet).

Usage : python -m src.ingestion.download_eba
Le site de l'EBA bloque parfois les téléchargements automatiques (erreur 403).
Dans ce cas, télécharge les fichiers à la main depuis la page ci-dessus
(section « Full database ») et dépose-les dans data/raw/eba/.
"""
from __future__ import annotations

import requests

from src.common import RAW_EBA_DIR

PAGE_URL = "https://www.eba.europa.eu/risk-and-data-analysis/risk-analysis/eu-wide-transparency-exercise"
BASE_URL = "https://www.eba.europa.eu/assets/TE2025/Full_database/883401/"
FILES = [
    "tr_oth.csv",          # capital, ratios de solvabilité, levier, P&L, NPE (indispensable)
    "TR_Metadata.xlsx",    # libellés des codes "Item" (indispensable)
    "SDD.xlsx",            # dictionnaire de données (utile)
    "tr_cre.csv",          # risque de crédit (gros fichier, optionnel au début)
]

# Le site refuse les requêtes qui ne ressemblent pas à un navigateur.
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/129.0 Safari/537.36",
    "Accept": "text/csv,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet,*/*",
    "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.8",
    "Referer": PAGE_URL,
}


def download(session: requests.Session, name: str) -> bool:
    target = RAW_EBA_DIR / name
    if target.exists():
        print(f"✓ déjà présent : {name}")
        return True
    print(f"↓ {name} …")
    try:
        with session.get(BASE_URL + name, stream=True, timeout=120) as r:
            r.raise_for_status()
            tmp = target.with_suffix(target.suffix + ".part")
            with open(tmp, "wb") as f:
                for chunk in r.iter_content(chunk_size=1 << 20):
                    f.write(chunk)
            tmp.replace(target)
    except requests.RequestException as exc:
        print(f"✗ {name} : {exc}")
        return False
    print(f"✓ {name} ({target.stat().st_size / 1e6:.1f} Mo)")
    return True


def main() -> None:
    RAW_EBA_DIR.mkdir(parents=True, exist_ok=True)
    with requests.Session() as session:
        session.headers.update(HEADERS)
        failed = [name for name in FILES if not download(session, name)]

    if failed:
        print(
            "\n⚠ Téléchargement automatique refusé par le site de l'EBA.\n"
            f"  1. Ouvre {PAGE_URL}\n"
            "  2. Section « Full database », télécharge : " + ", ".join(failed) + "\n"
            f"  3. Dépose-les dans : {RAW_EBA_DIR}\n"
            "  4. Lance : python -m src.ingestion.load_eba"
        )


if __name__ == "__main__":
    main()
