"""Synthetic pharma market-access (gross-to-net) warehouse.

Models the raw SQL tables a market-access data team actually has, where every
gross-to-net deduction is an explicit row so the true metrics are computable
independently of the semantic layer:

  dim_product      brand + WAC (list price)
  dim_customer     wholesalers, commercial payers, state Medicaid, GPOs
  fact_sales       manufacturer -> wholesaler sales at WAC (gross sales)
  fact_chargebacks wholesaler resells to a contracted provider below WAC; the
                   manufacturer credits the difference (units x (WAC - contract))
  fact_rebates     commercial rebates (payer contracts) + Medicaid URA rebates
  fact_fees        distribution service fees + GPO admin fees

Net sales = gross - chargebacks - rebates - fees. Everything is seeded.
No real manufacturer, payer, pricing, or contract data is used or represented.
"""
from __future__ import annotations

from pathlib import Path

import duckdb
import numpy as np
import pandas as pd

BRANDS = [("P1", "Brand A", 1200.0), ("P2", "Brand B", 480.0),
          ("P3", "Brand C", 2600.0), ("P4", "Brand D", 95.0)]
PERIODS = ["2025-Q1", "2025-Q2", "2025-Q3", "2025-Q4"]
STATES = ["CA", "TX", "NY", "FL", "PA", "OH", "IL", "GA", "NC", "MI"]


def generate(seed: int = 3, db_path: str | None = None) -> dict:
    rng = np.random.default_rng(seed)

    dim_product = pd.DataFrame(BRANDS, columns=["product_id", "brand", "wac"])

    customers = []
    for i in range(6):
        customers.append((f"W{i:02d}", f"Wholesaler {i}", "wholesaler"))
    for i in range(8):
        customers.append((f"C{i:02d}", f"Commercial Payer {i}", "commercial_payer"))
    for s in STATES:
        customers.append((f"M_{s}", f"{s} Medicaid", "medicaid"))
    for i in range(4):
        customers.append((f"G{i:02d}", f"GPO {i}", "gpo"))
    dim_customer = pd.DataFrame(customers, columns=["customer_id", "customer_name", "class_of_trade"])

    wholesalers = dim_customer[dim_customer.class_of_trade == "wholesaler"].customer_id.tolist()
    payers = dim_customer[dim_customer.class_of_trade == "commercial_payer"].customer_id.tolist()
    gpos = dim_customer[dim_customer.class_of_trade == "gpo"].customer_id.tolist()

    # ---- fact_sales (gross) ----
    srows = []
    for pid, _, wac in BRANDS:
        for per in PERIODS:
            for w in wholesalers:
                units = int(rng.integers(200, 2000))
                srows.append((pid, w, per, units, wac, round(units * wac, 2)))
    fact_sales = pd.DataFrame(srows, columns=["product_id", "customer_id", "period",
                                              "units", "wac", "gross_sales"])

    # ---- fact_chargebacks ----
    crows = []
    for pid, _, wac in BRANDS:
        for per in PERIODS:
            for w in wholesalers:
                # a fraction of units are resold to contracted providers below WAC
                units_cb = int(rng.integers(50, 700))
                contract_price = round(wac * rng.uniform(0.55, 0.85), 2)
                crows.append((pid, w, per, units_cb, wac, contract_price,
                              round(units_cb * (wac - contract_price), 2)))
    fact_chargebacks = pd.DataFrame(crows, columns=["product_id", "customer_id", "period",
                                                    "units", "wac", "contract_price", "chargeback_amt"])

    # ---- fact_rebates (commercial + medicaid) ----
    rrows = []
    for pid, _, wac in BRANDS:
        for per in PERIODS:
            for p in payers:                       # commercial
                units = int(rng.integers(100, 1200))
                rpu = round(wac * rng.uniform(0.10, 0.28), 2)
                rrows.append((pid, p, per, "commercial", units, rpu, round(units * rpu, 2)))
            for s in STATES:                       # medicaid URA
                mid = f"M_{s}"
                units = int(rng.integers(40, 500))
                ura = round(wac * rng.uniform(0.23, 0.43), 2)   # statutory-ish rebate per unit
                rrows.append((pid, mid, per, "medicaid", units, ura, round(units * ura, 2)))
    fact_rebates = pd.DataFrame(rrows, columns=["product_id", "customer_id", "period",
                                                "rebate_type", "units", "rebate_per_unit", "rebate_amt"])

    # ---- fact_fees (distribution + GPO admin) ----
    frows = []
    for pid, _, wac in BRANDS:
        for per in PERIODS:
            for w in wholesalers:
                base = fact_sales[(fact_sales.product_id == pid) & (fact_sales.period == per)
                                  & (fact_sales.customer_id == w)]["gross_sales"].sum()
                frows.append((pid, w, per, "distribution", round(base * 0.02, 2)))
            for g in gpos:
                frows.append((pid, g, per, "gpo_admin", round(rng.uniform(2000, 15000), 2)))
    fact_fees = pd.DataFrame(frows, columns=["product_id", "customer_id", "period", "fee_type", "fee_amt"])

    tables = {"dim_product": dim_product, "dim_customer": dim_customer,
              "fact_sales": fact_sales, "fact_chargebacks": fact_chargebacks,
              "fact_rebates": fact_rebates, "fact_fees": fact_fees}

    # write to DuckDB (the "Snowflake" stand-in)
    path = db_path or "reports/market_access.duckdb"
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    if Path(path).exists():
        Path(path).unlink()
    con = duckdb.connect(path)
    for name, df in tables.items():
        con.register(f"_{name}", df)
        con.execute(f"CREATE TABLE {name} AS SELECT * FROM _{name}")
    con.close()

    return {"tables": tables, "db_path": path, "periods": PERIODS,
            "brands": [b[1] for b in BRANDS]}


if __name__ == "__main__":
    d = generate()
    for name, df in d["tables"].items():
        print(f"{name:18s} rows={len(df)}")
    print("db ->", d["db_path"])
