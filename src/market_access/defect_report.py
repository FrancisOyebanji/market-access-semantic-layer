"""Turn failed certifications into root-cause defect reports + technical requirements.

This is the written deliverable half of the job: for every metric that failed
certification, explain what went wrong (root cause from the semantic layer), the
business impact, and a clear requirement for Data Science / Engineering to fix it.
"""
from __future__ import annotations

from market_access import ground_truth as gt
from market_access import semantic_model as sm

_IMPACT = {
    "fanout_join": "Metric is massively overstated (rows multiplied by a many-to-many join).",
    "missing_component": "Metric is overstated because a required deduction is not subtracted.",
    "wrong_denominator": "Ratio is wrong because it divides by the wrong base.",
}
_REQUIREMENT = {
    "fanout_join": "Aggregate the fact table directly at its own grain; remove the join "
                   "to fact_sales. Add a row-count guard to the certification test.",
    "missing_component": "Add the missing deduction ({missing}) to the net-sales component "
                         "list so all gross-to-net deductions are included.",
    "wrong_denominator": "Change the GTN % denominator from net sales to gross sales to match "
                         "the standard definition (deductions / gross).",
}


def build_reports(con, model, tables) -> list:
    reports = []
    for metric in sm.all_metric_names(model):
        spec = sm.metric_spec(model, metric)
        defect = spec.get("defect")
        if not defect:
            continue
        prod = sm.run(con, model, metric)
        fixed = sm.run(con, model, metric, corrected=True)
        truth = gt.truth(tables, metric)
        dtype = defect["type"]
        req = _REQUIREMENT[dtype].format(missing=defect.get("missing", ""))
        variance = None
        if isinstance(prod, (int, float)) and isinstance(truth, (int, float)) and truth:
            variance = round((prod - truth) / abs(truth) * 100, 1)
        reports.append({
            "metric": metric,
            "label": spec["label"],
            "defect_type": dtype,
            "root_cause": " ".join(defect["note"].split()),
            "impact": _IMPACT[dtype],
            "prism_value": prod,
            "certified_value": fixed,
            "source_of_truth": truth,
            "variance_vs_truth_pct": variance,
            "requirement": req,
            "jira_summary": f"[Prism][Semantic Layer] Fix {spec['label']} ({dtype})",
        })
    return reports


def to_markdown(reports: list) -> str:
    lines = ["# Prism Certification — Defect & Requirements Report", ""]
    lines.append(f"{len(reports)} metrics failed certification against source data.\n")
    for i, r in enumerate(reports, 1):
        lines += [
            f"## {i}. {r['label']} (`{r['metric']}`) — {r['defect_type']}",
            f"**Jira:** {r['jira_summary']}  ",
            f"**Root cause:** {r['root_cause']}  ",
            f"**Impact:** {r['impact']}  ",
            f"**Prism returned:** {r['prism_value']:,} | **Source of truth:** {r['source_of_truth']:,}"
            + (f" | **{r['variance_vs_truth_pct']:+}% vs truth**" if r["variance_vs_truth_pct"] is not None else ""),
            f"**Requirement:** {r['requirement']}",
            f"**Verified fix returns:** {r['certified_value']:,}",
            "",
        ]
    return "\n".join(lines)
