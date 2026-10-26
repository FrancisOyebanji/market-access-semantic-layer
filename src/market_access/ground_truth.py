"""Independent source-of-truth metrics (pandas).

This is the certification oracle: gross-to-net metrics computed straight from the
raw facts, by a completely different code path than the semantic layer's SQL. If
the semantic-layer answer disagrees with this, the answer is wrong — regardless of
which side looks "nicer". Component amounts are summed at the (brand, period) grain
and derived metrics are computed after aggregation, so any slice is consistent.
"""
from __future__ import annotations

import pandas as pd

METRICS = ["gross_sales", "chargebacks", "commercial_rebates", "medicaid_rebates",
           "total_rebates", "fees", "net_sales", "gtn_deductions", "gtn_pct"]


def _components(tables: dict) -> pd.DataFrame:
    prod = tables["dim_product"][["product_id", "brand"]]

    gross = (tables["fact_sales"].groupby(["product_id", "period"])["gross_sales"].sum()
             .rename("gross_sales"))
    cb = (tables["fact_chargebacks"].groupby(["product_id", "period"])["chargeback_amt"].sum()
          .rename("chargebacks"))
    reb = tables["fact_rebates"]
    comm = (reb[reb.rebate_type == "commercial"].groupby(["product_id", "period"])["rebate_amt"]
            .sum().rename("commercial_rebates"))
    med = (reb[reb.rebate_type == "medicaid"].groupby(["product_id", "period"])["rebate_amt"]
           .sum().rename("medicaid_rebates"))
    fees = (tables["fact_fees"].groupby(["product_id", "period"])["fee_amt"].sum()
            .rename("fees"))

    df = pd.concat([gross, cb, comm, med, fees], axis=1).fillna(0.0).reset_index()
    df = df.merge(prod, on="product_id", how="left")
    df["total_rebates"] = df["commercial_rebates"] + df["medicaid_rebates"]
    df["net_sales"] = df["gross_sales"] - df["chargebacks"] - df["total_rebates"] - df["fees"]
    df["gtn_deductions"] = df["gross_sales"] - df["net_sales"]
    return df


def truth(tables: dict, metric: str, group_by: str | None = None,
          brand: str | None = None, period: str | None = None):
    """Return a scalar (no group_by) or {group: value} dict for the metric."""
    df = _components(tables)
    if brand:
        df = df[df["brand"] == brand]
    if period:
        df = df[df["period"] == period]

    addins = ["gross_sales", "chargebacks", "commercial_rebates", "medicaid_rebates",
              "fees", "total_rebates", "net_sales", "gtn_deductions"]

    def _derive(sub):
        g = sub["gross_sales"].sum()
        if metric in addins:
            return float(sub[metric].sum())
        if metric == "gtn_pct":
            ded = sub["gtn_deductions"].sum()
            return float(ded / g) if g else 0.0
        raise ValueError(metric)

    if group_by is None:
        return round(_derive(df), 4 if metric == "gtn_pct" else 2)
    key = {"brand": "brand", "period": "period"}[group_by]
    return {k: round(_derive(sub), 4 if metric == "gtn_pct" else 2)
            for k, sub in df.groupby(key)}
