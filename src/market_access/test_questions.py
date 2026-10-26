"""The answer-accuracy test battery (the QA cases a Product Analyst sets each sprint)."""

CERTIFICATION_QUESTIONS = [
    "What were gross sales in Q1?",
    "Show total rebates by brand",
    "How much did we pay in Medicaid rebates?",
    "What were commercial rebates by quarter?",
    "What are total fees for Brand B?",
    "What were net sales in Q1?",                 # hits the missing-medicaid defect
    "Show net sales by brand",                    # hits the defect
    "What is gross-to-net percentage by brand?",  # hits the wrong-denominator defect
    "Total chargebacks for Brand C",              # hits the fan-out-join defect
    "Show chargebacks by quarter",                # hits the fan-out-join defect
]

AMBIGUOUS_PROMPTS = [
    "show me rebates",
    "how are sales doing",
    "what is the gtn",
    "rebates for Brand A",
    "net sales by brand in Q2",      # already specific
]
