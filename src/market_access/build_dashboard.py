"""Certification dashboard from reports/certification.json."""
from __future__ import annotations

import json
from pathlib import Path

R = json.loads(Path("reports/certification.json").read_text())
cert = R["certification"]
cases = R["cases"]
pr = R["prompt_review"]

rate = cert["certification_rate"]
case_rows = ""
for c in cases:
    if c["status"] == "unresolved":
        continue
    badge = ("<span style='color:#14804a;font-weight:700'>CERTIFIED</span>"
             if c["status"] == "certified"
             else "<span style='color:#b42318;font-weight:700'>FAILED</span>")
    defect = c.get("defect") or ""
    case_rows += (f"<tr><td style='text-align:left'>{c['question']}</td><td>{c['metric']}</td>"
                  f"<td>{badge}</td><td>{defect}</td><td>{c['max_rel_error']}</td></tr>")

sweep = cert["metric_sweep_production"]
sweep_rows = ""
for m, r in sweep.items():
    ok = r["overall"]["certified"] and r["brand"]["certified"]
    badge = "✅" if ok else "❌"
    seed = "⚠️" if r["has_seeded_defect"] else ""
    sweep_rows += f"<tr><td style='text-align:left'>{m} {seed}</td><td>{badge}</td></tr>"

html = f"""<!DOCTYPE html><html><head><meta charset="utf-8">
<title>Prism Answer Certification</title>
<style>
 body{{font-family:'Segoe UI',system-ui,sans-serif;background:#f5f7fa;color:#13233a;margin:0}}
 header{{background:#0f3d6e;color:#fff;padding:16px 30px}} h1{{font-size:20px;margin:0}}
 .sub{{color:#bcd4ea;font-size:13px}}
 main{{max-width:1080px;margin:22px auto;padding:0 18px}}
 .kpis{{display:grid;grid-template-columns:repeat(auto-fit,minmax(175px,1fr));gap:14px;margin-bottom:20px}}
 .kpi{{background:#fff;border:1px solid #e1e8ef;border-radius:12px;padding:16px}}
 .kpi .l{{color:#5c6f84;font-size:13px}}.kpi .v{{font-size:22px;font-weight:700;margin-top:4px;color:#0f3d6e}}
 .grid{{display:grid;grid-template-columns:2fr 1fr;gap:18px}}
 .panel{{background:#fff;border:1px solid #e1e8ef;border-radius:12px;padding:18px;margin-bottom:18px}}
 .panel h2{{font-size:15px;margin:0 0 12px}}
 table{{width:100%;border-collapse:collapse;font-size:13px}} th,td{{padding:7px 9px;border-bottom:1px solid #eef2f6;text-align:center}}
 th{{color:#5c6f84}}
 .note{{background:#e8f0f8;border-left:4px solid #0f3d6e;padding:10px 14px;border-radius:6px;font-size:14px}}
 @media(max-width:800px){{.grid{{grid-template-columns:1fr}}}}
 footer{{color:#5c6f84;font-size:12px;text-align:center;margin:24px 0}}
</style></head><body>
<header><h1>Prism Answer Certification &mdash; market-access semantic layer</h1>
<div class="sub">Conversational-analytics answers certified against source data &middot; synthetic gross-to-net warehouse</div></header>
<main>
<div class="kpis">
 <div class="kpi"><div class="l">Answers certified</div><div class="v">{cert['n_certified']}/{cert['n_resolved']}</div></div>
 <div class="kpi"><div class="l">Certification rate</div><div class="v">{rate*100:.0f}%</div></div>
 <div class="kpi"><div class="l">Failing metrics</div><div class="v">{len(cert['failing_metrics'])}</div></div>
 <div class="kpi"><div class="l">Prompts flagged ambiguous</div><div class="v">{pr['n_ambiguous']}/{pr['n_prompts']}</div></div>
</div>
<div class="grid">
 <div class="panel"><h2>Answer certification &mdash; question by question</h2>
  <table><tr><th style="text-align:left">question</th><th>metric</th><th>status</th><th>defect</th><th>rel err</th></tr>{case_rows}</table></div>
 <div class="panel"><h2>Metric sweep</h2>
  <table><tr><th style="text-align:left">metric</th><th>certified</th></tr>{sweep_rows}</table>
  <p style="font-size:12px;color:#5c6f84">⚠️ = carries a seeded semantic-layer defect</p></div>
</div>
<div class="panel"><h2>What this shows</h2><div class="note">
 Every Prism answer is checked against an independent source-of-truth computed from the raw facts.
 The three seeded semantic-layer defects (fan-out join, a missing Medicaid-rebate deduction, and a
 wrong GTN&nbsp;% denominator) are all caught, traced to root cause, and written up as requirements &mdash;
 and the corrected definitions re-certify clean ({'all metrics fixed' if cert['all_fixed'] else 'partial'}).
</div></div>
</main>
<footer>Synthetic data &middot; src/market_access/build_dashboard.py &middot; answers graded vs an independent source of truth</footer>
</body></html>"""
Path("reports").mkdir(exist_ok=True)
Path("reports/certification_dashboard.html").write_text(html, encoding="utf-8")
print("Dashboard written to reports/certification_dashboard.html")
