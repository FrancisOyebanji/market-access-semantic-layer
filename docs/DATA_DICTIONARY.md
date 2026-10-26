# Market-Access Semantic Layer — Data Dictionary

Business definitions, lineage, and synonyms for every Prism metric. Generated from `semantic_layer/semantic_model.yaml`.

## Dimensions

| Dimension | Source | Synonyms |
|---|---|---|
| **Brand** | `dim_product.brand` | brand, product, drug, therapy, ndc |
| **Period** | `period` | period, quarter, q1, q2, q3, q4, time, when |

## Base metrics (direct from raw tables)

| Metric | Definition | Source table | Synonyms |
|---|---|---|---|
| **Gross Sales** | Manufacturer sales to wholesalers valued at WAC (list price). | `fact_sales` (SUM(gross_sales)) | gross sales, gross, wac sales, list sales, sales at wac |
| **Chargebacks** ⚠️ seeded defect | Credits to wholesalers for the WAC-minus-contract-price spread. | `fact_chargebacks` (SUM(chargeback_amt)) | chargebacks, chargeback, cb, wholesaler chargebacks |
| **Commercial Rebates** | Rebates paid under commercial payer / PBM contracts. | `fact_rebates` (SUM(rebate_amt), rebate_type = 'commercial') | commercial rebates, payer rebates, pbm rebates, contract rebates |
| **Medicaid Rebates** | Medicaid unit-rebate-amount (URA) statutory rebates by state. | `fact_rebates` (SUM(rebate_amt), rebate_type = 'medicaid') | medicaid rebates, government rebates, ura, medicaid ura, statutory rebates |
| **Total Rebates** | Commercial plus Medicaid rebates. | `fact_rebates` (SUM(rebate_amt)) | total rebates, all rebates, rebates |
| **Fees** | Distribution service fees and GPO administrative fees. | `fact_fees` (SUM(fee_amt)) | fees, distribution fees, admin fees, service fees, gpo fees |

## Derived metrics (composed from base metrics)

| Metric | Definition | Composition | Synonyms |
|---|---|---|---|
| **Net Sales** ⚠️ seeded defect | Gross sales minus all gross-to-net deductions. | `+gross_sales -chargebacks -commercial_rebates -fees` | net sales, net, net revenue, net-to-gross sales |
| **Gross-to-Net Deductions** | Total dollars deducted from gross to reach net. | `+chargebacks +commercial_rebates +medicaid_rebates +fees` | deductions, gross to net deductions, gtn deductions, gross-to-net dollars |
| **Gross-to-Net Percentage** ⚠️ seeded defect | Deductions as a percent of gross sales. | `gtn_deductions / net_sales` | gtn, gross to net, gross-to-net, gtn percent, gtn %, gross to net percentage |

## Gross-to-net lineage

```
gross_sales (fact_sales @ WAC)
  − chargebacks        (fact_chargebacks)
  − commercial_rebates (fact_rebates: commercial)
  − medicaid_rebates   (fact_rebates: medicaid)
  − fees               (fact_fees)
  = net_sales
gtn_pct = (gross_sales − net_sales) / gross_sales
```
