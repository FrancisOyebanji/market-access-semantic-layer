"""Tests for the semantic layer + answer-certification harness.

The pipeline runs once against the synthetic warehouse; tests assert the
certification catches exactly the seeded defects and that the corrected semantic
layer re-certifies clean.
"""
import os
import sys
from pathlib import Path

import duckdb
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))


@pytest.fixture(scope="module")
def ctx(tmp_path_factory):
    os.chdir(tmp_path_factory.mktemp("ma"))
    from market_access import (certification, generate_warehouse, ground_truth,
                               semantic_model)
    from market_access.test_questions import CERTIFICATION_QUESTIONS
    d = generate_warehouse.generate()
    model = semantic_model.load()
    con = duckdb.connect(d["db_path"])
    cert = certification.run_certification(con, model, d["tables"], CERTIFICATION_QUESTIONS)
    return {"con": con, "model": model, "tables": d["tables"], "cert": cert,
            "sm": semantic_model, "gt": ground_truth}


# ---------------- correct metrics match source of truth ----------------
def test_correct_metrics_certify(ctx):
    sm, gt, con, tables, model = ctx["sm"], ctx["gt"], ctx["con"], ctx["tables"], ctx["model"]
    for m in ["gross_sales", "commercial_rebates", "medicaid_rebates", "total_rebates", "fees"]:
        prism = sm.run(con, model, m)
        truth = gt.truth(tables, m)
        assert abs(prism - truth) <= max(1.0, abs(truth) * 1e-3), m


# ---------------- seeded defects are caught ----------------
def test_certification_catches_seeded_defects(ctx):
    failing = set(ctx["cert"]["failing_metrics"])
    # the three own-defect metrics must all fail
    assert {"chargebacks", "net_sales", "gtn_pct"} <= failing


def test_each_defect_metric_fails_a_question(ctx):
    failed_metrics = {c["metric"] for c in ctx["cert"]["cases"] if c["status"] == "failed"}
    assert {"chargebacks", "net_sales", "gtn_pct"} <= failed_metrics


def test_certification_rate_reflects_defects(ctx):
    cert = ctx["cert"]
    # 5 of the 10 questions hit defective metrics -> ~50% certified
    assert 0.4 <= cert["certification_rate"] <= 0.6


# ---------------- corrections fix everything ----------------
def test_corrections_recertify_clean(ctx):
    assert ctx["cert"]["all_fixed"] is True


def test_fanout_overstates_chargebacks(ctx):
    sm, gt, con, tables, model = ctx["sm"], ctx["gt"], ctx["con"], ctx["tables"], ctx["model"]
    prod = sm.run(con, model, "chargebacks")
    truth = gt.truth(tables, "chargebacks")
    assert prod > truth * 5            # fan-out massively inflates


# ---------------- prompt review ----------------
def test_prompt_review_flags_ambiguous_rebates(ctx):
    from market_access import prompt_review
    r = prompt_review.review(ctx["model"], "show me rebates")
    assert r["is_ambiguous"] is True
    assert r["improved_prompt"]


def test_unanswerable_question_is_unresolved(ctx):
    from market_access import nl_resolver
    r = nl_resolver.resolve(ctx["model"], "what is the weather today")
    assert r["resolved"] is False
