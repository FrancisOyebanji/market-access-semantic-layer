# Prism Certification — Defect & Requirements Report

3 metrics failed certification against source data.

## 1. Chargebacks (`chargebacks`) — fanout_join
**Jira:** [Prism][Semantic Layer] Fix Chargebacks (fanout_join)  
**Root cause:** Joins fact_chargebacks to fact_sales on product_id to "enrich" with sales, a many-to-many that fans out rows and multiplies the summed chargebacks.  
**Impact:** Metric is massively overstated (rows multiplied by a many-to-many join).  
**Prism returned:** 302,845,638.24 | **Source of truth:** 12,618,568.26 | **+2300.0% vs truth**
**Requirement:** Aggregate the fact table directly at its own grain; remove the join to fact_sales. Add a row-count guard to the certification test.
**Verified fix returns:** 12,618,568.26

## 2. Net Sales (`net_sales`) — missing_component
**Jira:** [Prism][Semantic Layer] Fix Net Sales (missing_component)  
**Root cause:** The net-sales definition subtracts chargebacks, commercial rebates and fees but NOT Medicaid rebates, so net sales is overstated. A classic "the layer only joined the commercial rebate table" error.  
**Impact:** Metric is overstated because a required deduction is not subtracted.  
**Prism returned:** -211,935,117.98 | **Source of truth:** 63,491,418.47 | **-433.8% vs truth**
**Requirement:** Add the missing deduction (medicaid_rebates) to the net-sales component list so all gross-to-net deductions are included.
**Verified fix returns:** 63,491,418.47

## 3. Gross-to-Net Percentage (`gtn_pct`) — wrong_denominator
**Jira:** [Prism][Semantic Layer] Fix Gross-to-Net Percentage (wrong_denominator)  
**Root cause:** GTN % is computed as deductions / NET sales instead of deductions / GROSS sales, inflating the percentage and breaking the standard definition.  
**Impact:** Ratio is wrong because it divides by the wrong base.  
**Prism returned:** -1.5912 | **Source of truth:** 0.4254 | **-474.0% vs truth**
**Requirement:** Change the GTN % denominator from net sales to gross sales to match the standard definition (deductions / gross).
**Verified fix returns:** 0.4254
