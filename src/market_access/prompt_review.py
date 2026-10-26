"""Prompt review: flag ambiguous business questions and suggest better prompts.

Half of the certification work is upstream of SQL: a vague prompt makes Prism guess.
This module checks a user prompt against the semantic layer and flags the ambiguities
that would make the answer unreliable, then rewrites the prompt so it resolves to a
single, certifiable metric + slice.
"""
from __future__ import annotations

import re

from market_access import nl_resolver as nl

_REBATE_AMBIGUOUS = re.compile(r"\brebates?\b")
_REBATE_SPECIFIC = re.compile(r"\b(commercial|medicaid|total|government|pbm|ura)\b")


def review(model: dict, prompt: str) -> dict:
    intent = nl.resolve(model, prompt)
    issues, suggestions = [], []
    p = prompt.lower()

    if not intent["resolved"]:
        issues.append("No metric matched — the question does not map to a known measure.")
        suggestions.append("Name a specific metric, e.g. 'net sales', 'Medicaid rebates', 'GTN %'.")

    # ambiguous 'rebates' without a type
    if _REBATE_AMBIGUOUS.search(p) and not _REBATE_SPECIFIC.search(p) \
            and intent["metric"] in (None, "total_rebates"):
        issues.append("'Rebates' is ambiguous: commercial, Medicaid, or total?")
        suggestions.append("Specify the rebate type (commercial / Medicaid / total).")

    # no time frame
    if intent["period"] is None and not re.search(r"\b(all|ytd|full year|annual|by quarter)\b", p):
        issues.append("No time period specified — defaults to all periods, which may surprise the user.")
        suggestions.append("Add a period (e.g. 'in Q2') or say 'full year'.")

    # metric with no slice could return a single national number unexpectedly
    if intent["metric"] and intent["dimension"] is None and intent["brand"] is None:
        suggestions.append("Consider a breakdown ('by brand' / 'by quarter') if a single total isn't intended.")

    improved = _rewrite(intent, prompt)
    return {
        "prompt": prompt,
        "resolved_metric": intent["metric"],
        "ambiguity_flags": issues,
        "suggestions": suggestions,
        "is_ambiguous": bool(issues),
        "improved_prompt": improved,
    }


def _rewrite(intent, prompt):
    metric = intent["metric"] or "net_sales"
    label = metric.replace("_", " ")
    brand = intent["brand"] or "Brand A"
    period = intent["period"] or "2025-Q1"
    return f"What is {label} for {brand} in {period.split('-')[-1]}?"


def review_batch(model, prompts) -> dict:
    reviews = [review(model, p) for p in prompts]
    return {
        "n_prompts": len(reviews),
        "n_ambiguous": sum(1 for r in reviews if r["is_ambiguous"]),
        "reviews": reviews,
    }
