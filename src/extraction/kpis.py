"""Définition des KPI à extraire des rapports annuels.

Chaque KPI a une définition précise : c'est ce que lit Claude, et c'est ce qui
rend l'extraction comparable d'une banque à l'autre.
"""

KPIS = {
    "cet1_ratio": {
        "label": "Ratio CET1 (Common Equity Tier 1)",
        "unit": "%",
        "definition": "Ratio CET1 phasé (transitional) du groupe, au 31/12 de l'exercice. "
                      "En %. Ne pas prendre le ratio 'fully loaded' sauf s'il est le seul publié.",
        "keywords": ["CET1", "Common Equity Tier 1", "ratio de fonds propres de base"],
        "comparable_eba": True,
    },
    "total_capital_ratio": {
        "label": "Ratio de solvabilité global",
        "unit": "%",
        "definition": "Total capital ratio (fonds propres totaux / RWA) du groupe au 31/12, en %.",
        "keywords": ["total capital ratio", "ratio de solvabilité global", "ratio global"],
        "comparable_eba": True,
    },
    "leverage_ratio": {
        "label": "Ratio de levier",
        "unit": "%",
        "definition": "Ratio de levier réglementaire (CRR) du groupe au 31/12, en %.",
        "keywords": ["leverage ratio", "ratio de levier"],
        "comparable_eba": True,
    },
    "net_banking_income": {
        "label": "Produit net bancaire (PNB) / revenus",
        "unit": "M EUR",
        "definition": "Produit net bancaire (net banking income / total revenues) du groupe "
                      "pour l'exercice, en millions d'euros.",
        "keywords": ["produit net bancaire", "net banking income", "revenues", "PNB"],
        "comparable_eba": False,
    },
    "cost_income_ratio": {
        "label": "Coefficient d'exploitation",
        "unit": "%",
        "definition": "Coefficient d'exploitation publié (frais de gestion / PNB) du groupe, en %.",
        "keywords": ["coefficient d'exploitation", "cost/income", "cost-income", "cost to income"],
        "comparable_eba": False,
    },
    "cost_of_risk_bp": {
        "label": "Coût du risque",
        "unit": "bp",
        "definition": "Coût du risque rapporté aux encours de crédit, en points de base (bp).",
        "keywords": ["coût du risque", "cost of risk"],
        "comparable_eba": False,
    },
    "net_income_group_share": {
        "label": "Résultat net part du groupe",
        "unit": "M EUR",
        "definition": "Résultat net part du groupe (net income attributable to shareholders) "
                      "de l'exercice, en millions d'euros.",
        "keywords": ["résultat net part du groupe", "net income attributable", "net profit"],
        "comparable_eba": False,
    },
    "rote": {
        "label": "Rentabilité des fonds propres tangibles (ROTE)",
        "unit": "%",
        "definition": "Return on tangible equity publié par la banque pour l'exercice, en %.",
        "keywords": ["ROTE", "return on tangible equity", "rentabilité des fonds propres tangibles"],
        "comparable_eba": False,
    },
}
