"""Generate the semantic-layer data dictionary (documentation deliverable).

Writes docs/DATA_DICTIONARY.md: every metric's business definition, source tables
(lineage), synonyms the resolver understands, and any known defect — so business
owners can see where a number comes from and trust Prism's answer.
"""
from __future__ import annotations

from pathlib import Path

from market_access import semantic_model as sm


def build(model: dict) -> str:
    lines = ["# Market-Access Semantic Layer — Data Dictionary", "",
             "Business definitions, lineage, and synonyms for every Prism metric. "
             "Generated from `semantic_layer/semantic_model.yaml`.", ""]

    lines += ["## Dimensions", "", "| Dimension | Source | Synonyms |", "|---|---|---|"]
    for name, spec in model["dimensions"].items():
        lines.append(f"| **{spec['label']}** | `{spec['column']}` | {', '.join(spec['synonyms'])} |")
    lines.append("")

    lines += ["## Base metrics (direct from raw tables)", "",
              "| Metric | Definition | Source table | Synonyms |", "|---|---|---|---|"]
    for name, spec in model["base_metrics"].items():
        flag = " ⚠️ seeded defect" if "defect" in spec else ""
        lines.append(f"| **{spec['label']}**{flag} | {spec.get('description','')} | "
                     f"`{spec['table']}` ({spec['measure']}"
                     + (f", {spec['filter']}" if spec.get("filter") else "") + f") | {', '.join(spec.get('synonyms', []))} |")
    lines.append("")

    lines += ["## Derived metrics (composed from base metrics)", "",
              "| Metric | Definition | Composition | Synonyms |", "|---|---|---|---|"]
    for name, spec in model["derived_metrics"].items():
        flag = " ⚠️ seeded defect" if "defect" in spec else ""
        if "ratio" in spec:
            comp = f"{spec['ratio']['numerator']} / {spec['ratio']['denominator']}"
        else:
            comp = " ".join(spec.get("components", []))
        lines.append(f"| **{spec['label']}**{flag} | {spec.get('description','')} | `{comp}` | "
                     f"{', '.join(spec.get('synonyms', []))} |")
    lines.append("")

    lines += ["## Gross-to-net lineage", "",
              "```", "gross_sales (fact_sales @ WAC)",
              "  − chargebacks        (fact_chargebacks)",
              "  − commercial_rebates (fact_rebates: commercial)",
              "  − medicaid_rebates   (fact_rebates: medicaid)",
              "  − fees               (fact_fees)",
              "  = net_sales",
              "gtn_pct = (gross_sales − net_sales) / gross_sales", "```", ""]
    return "\n".join(lines)


def main():
    model = sm.load()
    Path("docs").mkdir(exist_ok=True)
    Path("docs/DATA_DICTIONARY.md").write_text(build(model))
    print("Data dictionary -> docs/DATA_DICTIONARY.md")


if __name__ == "__main__":
    main()
