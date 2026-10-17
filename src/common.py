"""Chemins et utilitaires partagés par tous les scripts."""
from __future__ import annotations

import os
from pathlib import Path

import yaml
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")

DATA_DIR = ROOT / "data"
RAW_EBA_DIR = DATA_DIR / "raw" / "eba"
RAW_REPORTS_DIR = DATA_DIR / "raw" / "reports"
DB_PATH = Path(os.getenv("DUCKDB_PATH", DATA_DIR / "bank_insight.duckdb"))

# Modèle Claude utilisé pour l'extraction et l'agent (surchargeable dans .env)
CLAUDE_MODEL = os.getenv("CLAUDE_MODEL", "claude-sonnet-5-5")


def load_config() -> dict:
    with open(ROOT / "config" / "banks.yaml", encoding="utf-8") as f:
        return yaml.safe_load(f)


def get_connection(read_only: bool = False):
    import duckdb

    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(DB_PATH), read_only=read_only)
    if not read_only:
        con.execute("CREATE SCHEMA IF NOT EXISTS raw")
    return con
