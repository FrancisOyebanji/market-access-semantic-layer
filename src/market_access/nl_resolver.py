"""Natural-language resolver ("Prism"): plain-English question -> semantic intent.

Maps a business question to (metric, dimension, brand filter, period filter) using
the semantic layer's taxonomy of synonyms, then hands off to semantic_model to
generate and run the SQL. This is a deterministic stand-in for Snowflake Cortex /
an LLM text-to-SQL layer: the production system swaps the LLM in behind the same
`resolve()` interface, while this keeps the certification reproducible.
"""
from __future__ import annotations

import re

from market_access import semantic_model as sm


def _synonym_table(model: dict):
    """Return list of (synonym, kind, name) sorted longest-first for greedy match."""
    entries = []
    for group in ("base_metrics", "derived_metrics"):
        for name, spec in model[group].items():
            entries.append((name.replace("_", " "), "metric", name))
            for syn in spec.get("synonyms", []):
                entries.append((syn.lower(), "metric", name))
    for name, spec in model["dimensions"].items():
        for syn in spec.get("synonyms", []):
            entries.append((syn.lower(), "dimension", name))
    entries.sort(key=lambda e: len(e[0]), reverse=True)
    return entries


def resolve(model: dict, question: str) -> dict:
    q = " " + question.lower().strip() + " "
    entries = _synonym_table(model)

    metric = None
    for syn, kind, name in entries:
        if kind == "metric" and re.search(r"(?<![a-z])" + re.escape(syn) + r"(?![a-z])", q):
            metric = name
            break

    # dimension: "by X"
    dim = None
    if re.search(r"\bby (brand|product|drug|therapy)\b", q):
        dim = "brand"
    elif re.search(r"\bby (quarter|period|time)\b", q):
        dim = "period"

    # brand filter
    brand = None
    m = re.search(r"brand ([a-d])\b", q)
    if m:
        brand = "Brand " + m.group(1).upper()

    # period filter
    period = None
    m = re.search(r"\bq([1-4])\b", q)
    if m:
        period = f"2025-Q{m.group(1)}"

    return {"question": question, "metric": metric, "dimension": dim,
            "brand": brand, "period": period,
            "resolved": metric is not None}


def answer(con, model, question: str, corrected: bool = False) -> dict:
    intent = resolve(model, question)
    if not intent["resolved"]:
        return {**intent, "sql": None, "result": None}
    sql = sm.build_sql(model, intent["metric"], intent["dimension"],
                       intent["brand"], intent["period"], corrected)
    result = sm.run(con, model, intent["metric"], intent["dimension"],
                    intent["brand"], intent["period"], corrected)
    return {**intent, "sql": sql, "result": result}
