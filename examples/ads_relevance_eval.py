"""
MFT Eval — Partner Example: Ads Relevance Scoring
===================================================

Team:  Ads Ranking & Relevance
Goal:  Evaluate whether an LLM / ML model correctly classifies ads as
       relevant or irrelevant to a user query, and that the relevance
       explanation meets quality standards.

Integration time target: < 1 day using mft_evals.

What this file shows
--------------------
1. Quick-start eval with ExactMatchScorer       (< 15 lines of real code)
2. Multi-signal eval with CompositeScorer       (relevance + explanation quality)
3. SimpleEvalRunner for rapid iteration         (paste test cases, get score)
4. Production-grade config with thresholds      (CI blocking, Scuba tracking)

Run:
    python examples/ads_relevance_eval.py
"""

from mft_evals import (
    CompositeScorer,
    Dataset,
    Eval,
    EvalConfig,
    EvalRunner,
    ExactMatchScorer,
    F1Scorer,
    TokenF1Scorer,
)
from mft_evals.eval import EvalOwner, Threshold
from mft_evals.runner import SimpleEvalRunner
from mft_evals.scorers import BinaryPassFailScorer


# ── Mock Ads model (replace with your real model / endpoint) ─────────────────

def mock_ads_relevance_model(query_and_ad: str) -> dict:
    """
    Simulates an ads relevance model.  In production, replace this with a call
    to your ranking endpoint or LLM agent.
    """
    query_and_ad_lower = query_and_ad.lower()

    if "running shoes" in query_and_ad_lower and "nike" in query_and_ad_lower:
        return {
            "label": "relevant",
            "confidence": 0.96,
            "category": "footwear",
            "explanation": "Ad for Nike running shoes directly matches the user query for running shoes.",
        }
    if "running shoes" in query_and_ad_lower and "pizza" in query_and_ad_lower:
        return {
            "label": "irrelevant",
            "confidence": 0.99,
            "category": "food",
            "explanation": "Pizza delivery ad is unrelated to a running shoes query.",
        }
    if "laptop" in query_and_ad_lower and "macbook" in query_and_ad_lower:
        return {
            "label": "relevant",
            "confidence": 0.91,
            "category": "electronics",
            "explanation": "MacBook ad is a laptop, matching the user query.",
        }
    if "laptop" in query_and_ad_lower and "yoga mat" in query_and_ad_lower:
        return {
            "label": "irrelevant",
            "confidence": 0.94,
            "category": "fitness",
            "explanation": "Yoga mat ad is unrelated to a laptop search.",
        }
    if "headphones" in query_and_ad_lower and "sony" in query_and_ad_lower:
        return {
            "label": "relevant",
            "confidence": 0.88,
            "category": "electronics",
            "explanation": "Sony headphones match the user headphones query.",
        }
    if "headphones" in query_and_ad_lower and "dog food" in query_and_ad_lower:
        return {
            "label": "irrelevant",
            "confidence": 0.97,
            "category": "pet_supplies",
            "explanation": "Dog food ad does not match headphones query.",
        }
    if "winter jacket" in query_and_ad_lower and "north face" in query_and_ad_lower:
        return {
            "label": "relevant",
            "confidence": 0.93,
            "category": "apparel",
            "explanation": "North Face winter jacket directly matches winter jacket query.",
        }
    if "winter jacket" in query_and_ad_lower and "sunscreen" in query_and_ad_lower:
        return {
            "label": "irrelevant",
            "confidence": 0.92,
            "category": "skincare",
            "explanation": "Sunscreen ad is irrelevant to a winter jacket query.",
        }

    return {
        "label": "irrelevant",
        "confidence": 0.50,
        "category": "unknown",
        "explanation": "Could not determine relevance.",
    }


def main():
    # ==================================================================
    # Example 1 — Quick-Start: Relevance label accuracy (< 15 lines)
    # ==================================================================

    print("\n" + "=" * 60)
    print("ADS EXAMPLE 1: Quick-Start — Relevance Label Accuracy")
    print("=" * 60)

    test_cases = [
        {
            "input": "Query: running shoes | Ad: Nike Air Zoom Pegasus – $120",
            "expected": "relevant",
        },
        {
            "input": "Query: running shoes | Ad: Papa John's Pizza – 2 for $12",
            "expected": "irrelevant",
        },
        {
            "input": "Query: laptop | Ad: MacBook Pro 14\" – starting at $1,999",
            "expected": "relevant",
        },
        {
            "input": "Query: laptop | Ad: Premium Yoga Mat – $39.99",
            "expected": "irrelevant",
        },
        {
            "input": "Query: headphones | Ad: Sony WH-1000XM5 – $348",
            "expected": "relevant",
        },
        {
            "input": "Query: headphones | Ad: Premium Dog Food – $24.99/bag",
            "expected": "irrelevant",
        },
        {
            "input": "Query: winter jacket | Ad: North Face Thermoball – $199",
            "expected": "relevant",
        },
        {
            "input": "Query: winter jacket | Ad: SPF 50 Sunscreen – $14.99",
            "expected": "irrelevant",
        },
    ]

    runner = SimpleEvalRunner(
        test_cases=test_cases,
        scorer=ExactMatchScorer(case_sensitive=False),
        name="ads_relevance_quick",
    )

    results = runner.run(
        model_fn=lambda q: mock_ads_relevance_model(q)["label"]
    )

    print(f"\n  Score:       {results['score']:.0%}")
    print(f"  Pass Rate:   {results['pass_rate']:.0%}")
    print(f"  Passed 80%:  {'✅' if results['passed_80_threshold'] else '❌'}")

    if results["failures"]:
        print(f"\n  Failures ({len(results['failures'])}):")
        for f in results["failures"]:
            print(f"    • {f['input'][:50]}…  expected={f['expected']}  got={f['actual']}")

    # ==================================================================
    # Example 2 — Multi-Signal: Composite scorer (label + category + explanation)
    # ==================================================================

    print("\n" + "=" * 60)
    print("ADS EXAMPLE 2: Multi-Signal Composite Eval")
    print("=" * 60)

    composite_cases = [
        {
            "input": "Query: running shoes | Ad: Nike Air Zoom Pegasus – $120",
            "expected": {
                "label": "relevant",
                "category": "footwear",
                "explanation": "Ad for Nike running shoes matches user query for running shoes.",
            },
        },
        {
            "input": "Query: running shoes | Ad: Papa John's Pizza – 2 for $12",
            "expected": {
                "label": "irrelevant",
                "category": "food",
                "explanation": "Pizza delivery ad does not match running shoes query.",
            },
        },
        {
            "input": "Query: laptop | Ad: MacBook Pro 14\" – starting at $1,999",
            "expected": {
                "label": "relevant",
                "category": "electronics",
                "explanation": "MacBook Pro ad matches user laptop query.",
            },
        },
        {
            "input": "Query: laptop | Ad: Premium Yoga Mat – $39.99",
            "expected": {
                "label": "irrelevant",
                "category": "fitness",
                "explanation": "Yoga mat ad is unrelated to laptop query.",
            },
        },
        {
            "input": "Query: headphones | Ad: Sony WH-1000XM5 – $348",
            "expected": {
                "label": "relevant",
                "category": "electronics",
                "explanation": "Sony headphones ad matches headphones query.",
            },
        },
        {
            "input": "Query: winter jacket | Ad: North Face Thermoball – $199",
            "expected": {
                "label": "relevant",
                "category": "apparel",
                "explanation": "North Face winter jacket matches user winter jacket query.",
            },
        },
    ]

    dataset = Dataset.from_list(
        items=composite_cases,
        input_key="input",
        expected_key="expected",
        name="ads_relevance_composite",
    )

    scorer = CompositeScorer([
        (ExactMatchScorer(field="label", case_sensitive=False, name="relevance_label"), 0.50),
        (ExactMatchScorer(field="category", case_sensitive=False, name="category_match"), 0.20),
        (TokenF1Scorer(field="explanation", name="explanation_quality"), 0.30),
    ])

    eval_obj = Eval(
        name="ads_relevance_composite",
        dataset=dataset,
        scorers=[scorer],
        thresholds={"composite": 0.80},
    )

    runner = EvalRunner(eval_obj)
    results = runner.run(
        generate_fn=lambda q: mock_ads_relevance_model(q),
    )
    print(results.summary())

    # ==================================================================
    # Example 3 — Production Config with thresholds + GK + CI blocking
    # ==================================================================

    print("\n" + "=" * 60)
    print("ADS EXAMPLE 3: Production Config (thresholds + CI blocking)")
    print("=" * 60)

    prod_config = EvalConfig(
        name="ads_relevance_v2",
        version="2.0.0",
        description=(
            "Evaluate ads relevance model accuracy across all major query "
            "verticals. Measures label precision, category classification, "
            "and explanation quality."
        ),
        owner=EvalOwner(pm="@ads_pm", eng="@ads_ranking_oncall", team="Ads Ranking"),
        capability_what="Classify ad–query pairs as relevant/irrelevant with category and explanation",
        capability_why="Directly impacts ads revenue and user trust — irrelevant ads degrade CTR",
        dataset_source="hive://ads_evals/relevance_golden_set_v2",
        dataset_size=5000,
        primary_metric="weighted_score",
        metrics=[
            {"name": "label_accuracy", "type": "exact_match", "weight": 0.50},
            {"name": "category_f1", "type": "f1_score", "weight": 0.20},
            {"name": "explanation_token_f1", "type": "token_f1", "weight": 0.30},
        ],
        thresholds=Threshold(
            baseline={"label_accuracy": 0.90, "category_f1": 0.85, "explanation_token_f1": 0.70},
            target={"label_accuracy": 0.96, "category_f1": 0.92, "explanation_token_f1": 0.85},
            blocking=True,
        ),
        gk_name="ads_relevance_model_v2",
        task_id="T987654321",
        diff_ids=["D111222333"],
        feature_name="Ads Relevance Model v2",
        tags=["ads", "relevance", "ranking", "production"],
    )

    errors = prod_config.validate()
    if errors:
        print("  Validation errors:")
        for e in errors:
            print(f"    ✗ {e}")
    else:
        print("  ✅ Production config is valid!")

    print(f"\n  Eval:     {prod_config.name} v{prod_config.version}")
    print(f"  Team:     {prod_config.owner.team}")
    print(f"  Blocking: {prod_config.thresholds.blocking}")
    print(f"  GK:       {prod_config.gk_name}")
    print(f"  Baseline: {prod_config.thresholds.baseline}")
    print(f"  Target:   {prod_config.thresholds.target}")

    # ==================================================================
    # Example 4 — Category-level F1 for multi-label ad taxonomy
    # ==================================================================

    print("\n" + "=" * 60)
    print("ADS EXAMPLE 4: Multi-Label Category Taxonomy F1")
    print("=" * 60)

    taxonomy_cases = [
        {"input": "Ad: Nike shoes", "expected": ["footwear", "sports"], "actual": ["footwear", "sports"]},
        {"input": "Ad: iPhone 15",  "expected": ["electronics", "mobile"], "actual": ["electronics", "phones"]},
        {"input": "Ad: Tesla Model 3", "expected": ["automotive", "electric"], "actual": ["automotive", "electric", "luxury"]},
        {"input": "Ad: Peloton Bike", "expected": ["fitness", "equipment"], "actual": ["fitness"]},
        {"input": "Ad: Airbnb Stay",  "expected": ["travel", "accommodation"], "actual": ["travel", "accommodation"]},
    ]

    taxonomy_dataset = Dataset.from_list(
        items=taxonomy_cases,
        input_key="input",
        expected_key="expected",
        name="ads_taxonomy_categories",
    )

    taxonomy_eval = Eval(
        name="ads_category_taxonomy_f1",
        dataset=taxonomy_dataset,
        scorers=[F1Scorer(name="category_f1")],
        thresholds={"category_f1": 0.80},
    )

    taxonomy_runner = EvalRunner(taxonomy_eval)
    taxonomy_results = taxonomy_runner.run(
        generate_fn=lambda q: next(
            tc.metadata["actual"]
            for tc in taxonomy_dataset
            if tc.input == q
        ),
    )
    print(taxonomy_results.summary())


if __name__ == "__main__":
    main()
