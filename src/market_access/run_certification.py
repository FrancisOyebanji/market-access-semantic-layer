"""End-to-end run: build warehouse -> certify answers -> defect reports -> prompt review."""
from __future__ import annotations

import json
from pathlib import Path

import duckdb

from market_access import (certification, defect_report, generate_warehouse,
                          prompt_review, semantic_model)
from market_access.test_questions import AMBIGUOUS_PROMPTS, CERTIFICATION_QUESTIONS


def main() -> dict:
    print("=== Building market-access warehouse (DuckDB) ===")
    d = generate_warehouse.generate()
    tables, model = d["tables"], semantic_model.load()
    con = duckdb.connect(d["db_path"])

    print("=== Certifying Prism answers vs source of truth ===")
    cert = certification.run_certification(con, model, tables, CERTIFICATION_QUESTIONS)
    print(f"   {cert['n_certified']}/{cert['n_resolved']} answers certified "
          f"({cert['certification_rate']*100:.0f}%) | failing metrics: {cert['failing_metrics']}")
    for c in cert["cases"]:
        if c["status"] == "failed":
            print(f"     FAIL: \"{c['question']}\" -> {c['metric']} "
                  f"(defect: {c['defect']}, rel err {c['max_rel_error']})")

    print("=== Defect reports + requirements ===")
    reports = defect_report.build_reports(con, model, tables)
    for r in reports:
        extra = f", {r['variance_vs_truth_pct']:+}% vs truth" if r["variance_vs_truth_pct"] is not None else ""
        print(f"   - {r['label']} [{r['defect_type']}{extra}] -> {r['requirement'][:70]}...")

    print("=== Corrected semantic layer re-certification ===")
    print(f"   corrections fix all metrics: {cert['all_fixed']}")

    print("=== Prompt review (ambiguity detection) ===")
    pr = prompt_review.review_batch(model, AMBIGUOUS_PROMPTS)
    print(f"   {pr['n_ambiguous']}/{pr['n_prompts']} prompts flagged ambiguous")

    Path("reports").mkdir(exist_ok=True)
    Path("reports/certification.json").write_text(json.dumps(
        {"certification": {k: v for k, v in cert.items() if k != "cases"},
         "cases": cert["cases"], "prompt_review": pr}, indent=2, default=str))
    Path("reports/DEFECT_REPORT.md").write_text(defect_report.to_markdown(reports))
    print("\nResults -> reports/certification.json, reports/DEFECT_REPORT.md")
    return {"certification": cert, "defect_reports": reports, "prompt_review": pr}


if __name__ == "__main__":
    main()
