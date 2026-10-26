"""Answer-certification harness.

For each question, run Prism's answer (semantic-layer SQL on DuckDB) and the
independent source-of-truth (pandas on the raw facts), then certify: do they match?
A mismatch means the business cannot trust that answer. Failing metrics are linked
to the seeded semantic-layer defect that causes them. Also sweeps every metric at
overall and by-brand grain, and re-certifies with the corrected semantic layer to
prove the fixes land.
"""
from __future__ import annotations

from market_access import ground_truth as gt
from market_access import nl_resolver as nl
from market_access import semantic_model as sm

REL_TOL = 1e-3


def _match(prism, truth):
    """Compare scalar or {group: value} results within relative tolerance."""
    if isinstance(prism, dict) or isinstance(truth, dict):
        if not (isinstance(prism, dict) and isinstance(truth, dict)):
            return False, 1.0
        keys = set(prism) | set(truth)
        worst = 0.0
        for k in keys:
            a, b = prism.get(k), truth.get(k)
            if a is None or b is None:
                return False, 1.0
            worst = max(worst, _rel(a, b))
        return worst <= REL_TOL, round(worst, 4)
    return (_rel(prism, truth) <= REL_TOL), round(_rel(prism, truth), 4)


def _rel(a, b):
    denom = max(abs(a), abs(b), 1.0)
    return abs(a - b) / denom


def certify_question(con, model, tables, question, corrected=False) -> dict:
    ans = nl.answer(con, model, question, corrected)
    if not ans["resolved"]:
        return {"question": question, "status": "unresolved", "metric": None}
    truth = gt.truth(tables, ans["metric"], group_by=ans["dimension"],
                     brand=ans["brand"], period=ans["period"])
    ok, err = _match(ans["result"], truth)
    spec = sm.metric_spec(model, ans["metric"])
    return {
        "question": question, "metric": ans["metric"], "dimension": ans["dimension"],
        "status": "certified" if ok else "failed",
        "prism_result": ans["result"], "source_of_truth": truth,
        "max_rel_error": err,
        "defect": spec.get("defect", {}).get("type") if not ok else None,
    }


def certify_metric_sweep(con, model, tables, corrected=False) -> dict:
    results = {}
    for metric in sm.all_metric_names(model):
        row = {}
        for dim in (None, "brand"):
            prism = sm.run(con, model, metric, dim=dim, corrected=corrected)
            truth = gt.truth(tables, metric, group_by=dim)
            ok, err = _match(prism, truth)
            row[dim or "overall"] = {"certified": ok, "max_rel_error": err}
        spec = sm.metric_spec(model, metric)
        row["has_seeded_defect"] = "defect" in spec
        results[metric] = row
    return results


def run_certification(con, model, tables, questions) -> dict:
    cases = [certify_question(con, model, tables, q) for q in questions]
    resolved = [c for c in cases if c["status"] != "unresolved"]
    passed = [c for c in resolved if c["status"] == "certified"]
    failed = [c for c in resolved if c["status"] == "failed"]

    sweep_prod = certify_metric_sweep(con, model, tables, corrected=False)
    sweep_fixed = certify_metric_sweep(con, model, tables, corrected=True)

    failing_metrics = sorted({m for m, r in sweep_prod.items()
                              if not (r["overall"]["certified"] and r["brand"]["certified"])})
    fixed_metrics = sorted({m for m, r in sweep_fixed.items()
                            if r["overall"]["certified"] and r["brand"]["certified"]})

    return {
        "n_questions": len(cases),
        "n_resolved": len(resolved),
        "n_certified": len(passed),
        "n_failed": len(failed),
        "certification_rate": round(len(passed) / len(resolved), 3) if resolved else 0.0,
        "cases": cases,
        "metric_sweep_production": sweep_prod,
        "failing_metrics": failing_metrics,
        "metrics_fixed_by_corrections": fixed_metrics,
        "all_fixed": fixed_metrics == sorted(sm.all_metric_names(model)),
    }
