"""Load the semantic layer and compile metrics to SQL (honoring seeded defects).

The semantic model (semantic_layer/semantic_model.yaml) maps business metrics to
SQL over the raw tables. This module turns a (metric, dimension, filters) request
into runnable DuckDB SQL. When a metric carries a seeded `defect`, the compiled SQL
reproduces that defect (a fan-out join, a missing deduction, a wrong denominator);
passing use_corrected=True compiles the documented fix instead.
"""
from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
MODEL_PATH = ROOT / "semantic_layer" / "semantic_model.yaml"


def load(path=MODEL_PATH) -> dict:
    return yaml.safe_load(Path(path).read_text())


def all_metric_names(model: dict) -> list:
    return list(model["base_metrics"]) + list(model["derived_metrics"])


def metric_spec(model: dict, name: str) -> dict:
    return model["base_metrics"].get(name) or model["derived_metrics"].get(name)


# ------------------------- base-metric CTE ---------------------------------
def _base_cte(name: str, spec: dict, corrected: bool) -> str:
    table, measure = spec["table"], spec["measure"]
    filt = spec.get("filter")
    where = f"WHERE {filt}" if filt else ""
    defect = spec.get("defect", {})
    if defect.get("type") == "fanout_join" and not corrected:
        col_expr = measure.replace("(", "(t.")          # SUM(x) -> SUM(t.x)
        return (f"{name} AS (SELECT t.product_id, t.period, {col_expr} AS val "
                f"FROM {table} t JOIN fact_sales fs ON t.product_id = fs.product_id "
                f"{where} GROUP BY t.product_id, t.period)")
    return (f"{name} AS (SELECT product_id, period, {measure} AS val "
            f"FROM {table} {where} GROUP BY product_id, period)")


# ------------------------- metric expansion --------------------------------
def _expand_additive(model, name, corrected):
    """Return list of (sign, base_metric_name) for an additive metric."""
    if name in model["base_metrics"]:
        return [(1, name)]
    spec = model["derived_metrics"][name]
    comps = spec["components"]
    if corrected and "corrected" in spec and "components" in spec["corrected"]:
        comps = spec["corrected"]["components"]
    out = []
    for c in comps:
        sign = -1 if c[0] == "-" else 1
        out.append((sign, c.lstrip("+-")))
    return out


def expand(model, name, corrected):
    """Return ('add', terms) or ('ratio', num_terms, den_terms)."""
    spec = metric_spec(model, name)
    if "ratio" in spec or (corrected and "ratio" in spec.get("corrected", {})):
        r = spec["ratio"]
        if corrected and "ratio" in spec.get("corrected", {}):
            r = spec["corrected"]["ratio"]
        num = _expand_additive(model, r["numerator"], corrected)
        den = _expand_additive(model, r["denominator"], corrected)
        return ("ratio", num, den)
    return ("add", _expand_additive(model, name, corrected))


# ------------------------- SQL builder -------------------------------------
def build_sql(model, metric, dim=None, brand=None, period=None, corrected=False) -> str:
    kind = expand(model, metric, corrected)
    needed = set()
    if kind[0] == "add":
        needed |= {n for _, n in kind[1]}
    else:
        needed |= {n for _, n in kind[1]} | {n for _, n in kind[2]}

    ctes = ["spine AS (SELECT p.product_id, d.period FROM dim_product p "
            "CROSS JOIN (SELECT DISTINCT period FROM fact_sales) d)"]
    for n in sorted(needed):
        ctes.append(_base_cte(n, model["base_metrics"][n], corrected))

    joins = ["FROM spine s", "JOIN dim_product p ON p.product_id = s.product_id"]
    for n in sorted(needed):
        joins.append(f"LEFT JOIN {n} ON {n}.product_id = s.product_id AND {n}.period = s.period")

    def _sumexpr(terms):
        parts = [f"{'-' if sg < 0 else '+'} COALESCE({n}.val,0)" for sg, n in terms]
        return "SUM(" + " ".join(parts).lstrip("+ ") + ")"

    if kind[0] == "add":
        value_expr = _sumexpr(kind[1])
    else:
        value_expr = f"{_sumexpr(kind[1])} / NULLIF({_sumexpr(kind[2])}, 0)"

    if dim == "brand":
        grp_sel, grp_by = "p.brand AS grp", "GROUP BY p.brand"
    elif dim == "period":
        grp_sel, grp_by = "s.period AS grp", "GROUP BY s.period"
    else:
        grp_sel, grp_by = "'ALL' AS grp", ""

    wheres = []
    if brand:
        wheres.append(f"p.brand = '{brand}'")
    if period:
        wheres.append(f"s.period = '{period}'")
    where = ("WHERE " + " AND ".join(wheres)) if wheres else ""

    sql = ("WITH " + ",\n".join(ctes) + "\n"
           f"SELECT {grp_sel}, {value_expr} AS value\n"
           + "\n".join(joins) + "\n"
           + (where + "\n" if where else "") + grp_by)
    return sql


def run(con, model, metric, dim=None, brand=None, period=None, corrected=False):
    sql = build_sql(model, metric, dim, brand, period, corrected)
    rows = con.execute(sql).fetchall()
    if dim is None:
        return round(float(rows[0][1]), 4 if metric == "gtn_pct" else 2)
    return {r[0]: round(float(r[1]), 4 if metric == "gtn_pct" else 2) for r in rows}
