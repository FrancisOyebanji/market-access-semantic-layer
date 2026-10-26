# Market-Access Semantic Layer + Conversational-Analytics Answer Certification

**A semantic layer over a synthetic pharma gross-to-net (GTN) warehouse, a natural-language resolver that answers business questions in SQL ("Prism"), and a certification harness that checks every answer against an independent source of truth — catching seeded semantic-layer defects, tracing them to root cause, and writing them up as requirements. SQL (DuckDB) + Python.**

> **In one breath:** Built a market-access semantic layer over a synthetic gross-to-net warehouse (sales, chargebacks, commercial + Medicaid rebates, fees) and a plain-English resolver that maps questions to metrics and runs them in SQL, then wrapped it in an **answer-certification harness** that compares each answer to an independent source-of-truth computed from the raw facts. It catches three realistic semantic-layer defects — a fan-out join that inflates chargebacks 24×, a net-sales definition that forgets to subtract Medicaid rebates, and a GTN % that divides by the wrong base — traces each to root cause, writes a Jira-ready requirement, and proves the corrected definitions re-certify clean. Plus a prompt-review step that flags ambiguous questions before they ever hit SQL.

> ⚕️ All data is **synthetic** (`generate_warehouse.py`). No real manufacturer, payer, pricing, or contract data is used or represented.

## Why this maps to the role

The job is certifying that a conversational-analytics platform's answers actually match the data behind a semantic layer, in a pharma market-access (pricing / rebates / chargebacks) domain — half data-digging, half writing up what needs to change. This repo is that loop, end to end and runnable:

```bash
pip install -r requirements.txt
PYTHONPATH=src python -m market_access.run_certification   # warehouse -> certify -> defect reports -> prompt review
PYTHONPATH=src python -m market_access.build_docs          # generate the data dictionary
PYTHONPATH=src python -m market_access.build_dashboard     # certification dashboard
PYTHONPATH=src python -m pytest tests/ -q                  # 8 tests
```

## What it does

| Piece | Module | What it delivers |
|---|---|---|
| **GTN warehouse** | [generate_warehouse.py](src/market_access/generate_warehouse.py) | raw SQL tables (sales, chargebacks, commercial + Medicaid rebates, fees) in DuckDB |
| **Semantic layer** | [semantic_model.yaml](semantic_layer/semantic_model.yaml) · [semantic_model.py](src/market_access/semantic_model.py) | metrics → SQL, dimensions, a synonym taxonomy, and joins |
| **Prism (NL → SQL)** | [nl_resolver.py](src/market_access/nl_resolver.py) | maps a plain-English question to metric + slice and runs it |
| **Answer certification** | [certification.py](src/market_access/certification.py) | Prism answer vs independent source-of-truth → certify / fail |
| **Defect reports** | [defect_report.py](src/market_access/defect_report.py) | root cause + business impact + Jira-ready requirement per defect |
| **Prompt review** | [prompt_review.py](src/market_access/prompt_review.py) | flags ambiguous prompts and rewrites them to resolve cleanly |
| **Data dictionary** | [build_docs.py](src/market_access/build_docs.py) | generated lineage + business definitions ([docs/DATA_DICTIONARY.md](docs/DATA_DICTIONARY.md)) |

## The certification loop (the centerpiece)

For every business question, two numbers are produced by **independent code paths**: Prism's answer (semantic-layer SQL on DuckDB) and the source of truth (pandas straight off the raw facts). If they disagree, the answer can't be trusted — no matter which looks cleaner.

To prove the harness works, the semantic layer ships with **three intentionally seeded defects** — the kinds a real semantic layer actually has — and the certification catches all three:

| Metric | Seeded defect | Caught as | Fix (verified) |
|---|---|---|---|
| **Chargebacks** | fan-out join to `fact_sales` on `product_id` | **+2,300% vs truth** | aggregate the fact table at its own grain |
| **Net Sales** | definition omits Medicaid rebates | fails every net-sales question | add the missing deduction |
| **GTN %** | divides deductions by **net** instead of **gross** | ratio is wrong | fix the denominator |

Running it: **5 of 10 answers certify** (the five questions that hit a defective metric fail), each failure is linked to its root-cause defect, a [DEFECT_REPORT.md](src/market_access/defect_report.py) with Jira summaries and requirements is generated, and the **corrected definitions re-certify 100% clean**. The certification also surfaces *cascade* effects — because chargebacks feed net sales and GTN deductions, one upstream defect quietly breaks several trusted business numbers, which is exactly the kind of connection this work exists to find.

## Prompt review

Half the reliability problem is upstream of SQL: a vague prompt makes the resolver guess. `prompt_review` flags ambiguity against the semantic layer — e.g. *"show me rebates"* → "commercial, Medicaid, or total?" — and rewrites it into a prompt that resolves to a single, certifiable metric and slice.

## Semantic model (excerpt)

Metrics are business definitions mapped to SQL, with a synonym taxonomy so the resolver understands how people actually ask:

```yaml
net_sales:
  synonyms: [net sales, net, net revenue, net-to-gross sales]
  components: ["+gross_sales", "-chargebacks", "-commercial_rebates", "-fees"]   # defect: missing medicaid
gtn_pct:
  synonyms: [gtn, gross to net, gross-to-net, gtn %]
  ratio: {numerator: gtn_deductions, denominator: net_sales}                     # defect: should be gross_sales
```

## Design choices & honest limitations

- **Independent oracle.** The certification's source of truth is computed by a different code path (pandas) than the semantic layer (SQL), so a shared bug can't hide a wrong answer. This is the whole point of certification.
- **DuckDB stands in for Snowflake.** The semantic-layer SQL is standard and portable; swapping the engine for Snowflake (and the resolver for Snowflake Cortex / an LLM behind the same `resolve()` interface) doesn't change the certification logic.
- **The resolver is deterministic, not an LLM.** That keeps the whole run reproducible and testable offline; in production an LLM maps language → intent and this harness certifies what it returns.
- **Synthetic, simplified GTN.** Real market-access data has far more deduction categories, contract complexity, and edge cases; this models the core gross-to-net chain cleanly so the certification story is legible.

---

*Francis Oluwatobi · oluwatobi.ou@gmail.com*
