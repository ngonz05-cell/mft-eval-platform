"""
MFT Eval — Partner Example: Marketplace Listing Quality
========================================================

Team:  Marketplace Trust & Quality
Goal:  Evaluate whether an LLM / ML system correctly assesses listing
       quality (title clarity, price accuracy, category classification,
       policy compliance) for Facebook Marketplace.

Integration time target: < 1 day using mft_evals.

What this file shows
--------------------
1. Quick-start eval with ExactMatchScorer       (listing policy compliance)
2. Multi-field eval with CompositeScorer        (title + price + category + policy)
3. SimpleEvalRunner for rapid iteration         (paste listings, get score)
4. Production-grade config with thresholds      (CI blocking, Scuba tracking)
5. Edge-case dataset for prohibited items       (policy-critical eval)

Run:
    python examples/marketplace_listing_eval.py
"""

from mft_evals import (
    CompositeScorer,
    Dataset,
    Eval,
    EvalConfig,
    EvalRunner,
    ExactMatchScorer,
    F1Scorer,
    NumericToleranceScorer,
    TokenF1Scorer,
)
from mft_evals.eval import EvalOwner, Threshold
from mft_evals.runner import SimpleEvalRunner
from mft_evals.scorers import BinaryPassFailScorer


# ── Mock Marketplace model (replace with your real model / endpoint) ─────────

MOCK_LISTINGS_DB = [
    {
        "id": "L001",
        "title": "iPhone 14 Pro Max 256GB – mint condition",
        "description": "Barely used iPhone 14 Pro Max. Includes box and charger.",
        "asking_price": 899.00,
        "model_output": {
            "quality_label": "high",
            "suggested_price": 879.00,
            "category": "electronics",
            "policy_compliant": True,
            "title_clear": True,
            "issues": [],
        },
    },
    {
        "id": "L002",
        "title": "couch",
        "description": "selling my couch",
        "asking_price": 150.00,
        "model_output": {
            "quality_label": "low",
            "suggested_price": 120.00,
            "category": "furniture",
            "policy_compliant": True,
            "title_clear": False,
            "issues": ["title_too_short", "missing_condition", "missing_dimensions"],
        },
    },
    {
        "id": "L003",
        "title": "2019 Honda Civic EX – 42k miles, clean title",
        "description": "Well-maintained 2019 Honda Civic EX. Single owner, no accidents.",
        "asking_price": 18500.00,
        "model_output": {
            "quality_label": "high",
            "suggested_price": 18200.00,
            "category": "vehicles",
            "policy_compliant": True,
            "title_clear": True,
            "issues": [],
        },
    },
    {
        "id": "L004",
        "title": "RARE JORDANS 🔥🔥🔥 DM ME!!!",
        "description": "hmu for price no lowballers",
        "asking_price": 0.00,
        "model_output": {
            "quality_label": "low",
            "suggested_price": 0.00,
            "category": "footwear",
            "policy_compliant": False,
            "title_clear": False,
            "issues": ["spam_title", "no_price", "contact_outside_platform"],
        },
    },
    {
        "id": "L005",
        "title": "KitchenAid Stand Mixer – Artisan 5qt, Empire Red",
        "description": "Used twice. Retails for $449. Comes with all attachments.",
        "asking_price": 275.00,
        "model_output": {
            "quality_label": "high",
            "suggested_price": 260.00,
            "category": "kitchen",
            "policy_compliant": True,
            "title_clear": True,
            "issues": [],
        },
    },
    {
        "id": "L006",
        "title": "FREE PUPPIES need gone today",
        "description": "Puppies free to good home, must pick up today.",
        "asking_price": 0.00,
        "model_output": {
            "quality_label": "medium",
            "suggested_price": 0.00,
            "category": "pets",
            "policy_compliant": False,
            "title_clear": True,
            "issues": ["animal_sale_policy"],
        },
    },
    {
        "id": "L007",
        "title": "Vitamix Professional 750 Blender – like new",
        "description": "Used for 2 months, selling because I upgraded. Includes recipe book.",
        "asking_price": 350.00,
        "model_output": {
            "quality_label": "high",
            "suggested_price": 340.00,
            "category": "kitchen",
            "policy_compliant": True,
            "title_clear": True,
            "issues": [],
        },
    },
    {
        "id": "L008",
        "title": "4K TV Samsung 55 inch",
        "description": "Samsung 55\" 4K UHD Smart TV. Model UN55TU7000. 2020 model.",
        "asking_price": 300.00,
        "model_output": {
            "quality_label": "medium",
            "suggested_price": 280.00,
            "category": "electronics",
            "policy_compliant": True,
            "title_clear": True,
            "issues": ["missing_model_in_title"],
        },
    },
]


def mock_listing_quality_model(listing_text: str) -> dict:
    """
    Simulates a Marketplace listing quality model.
    In production, replace with your actual model endpoint call.
    """
    for listing in MOCK_LISTINGS_DB:
        if listing["title"] in listing_text:
            return listing["model_output"]

    return {
        "quality_label": "medium",
        "suggested_price": 0.00,
        "category": "other",
        "policy_compliant": True,
        "title_clear": False,
        "issues": ["unknown_listing"],
    }


def main():
    # ==================================================================
    # Example 1 — Quick-Start: Policy compliance check (< 15 lines)
    # ==================================================================

    print("\n" + "=" * 60)
    print("MARKETPLACE EXAMPLE 1: Quick-Start — Policy Compliance")
    print("=" * 60)

    compliance_cases = [
        {"input": "iPhone 14 Pro Max 256GB – mint condition", "expected": "True"},
        {"input": "couch", "expected": "True"},
        {"input": "2019 Honda Civic EX – 42k miles, clean title", "expected": "True"},
        {"input": "RARE JORDANS 🔥🔥🔥 DM ME!!!", "expected": "False"},
        {"input": "KitchenAid Stand Mixer – Artisan 5qt, Empire Red", "expected": "True"},
        {"input": "FREE PUPPIES need gone today", "expected": "False"},
        {"input": "Vitamix Professional 750 Blender – like new", "expected": "True"},
        {"input": "4K TV Samsung 55 inch", "expected": "True"},
    ]

    runner = SimpleEvalRunner(
        test_cases=compliance_cases,
        scorer=ExactMatchScorer(case_sensitive=False),
        name="marketplace_policy_compliance",
    )

    results = runner.run(
        model_fn=lambda title: str(mock_listing_quality_model(title)["policy_compliant"])
    )

    print(f"\n  Score:       {results['score']:.0%}")
    print(f"  Pass Rate:   {results['pass_rate']:.0%}")
    print(f"  Passed 80%:  {'✅' if results['passed_80_threshold'] else '❌'}")

    if results["failures"]:
        print(f"\n  Failures ({len(results['failures'])}):")
        for f in results["failures"]:
            print(f"    • {f['input'][:50]}…  expected={f['expected']}  got={f['actual']}")

    # ==================================================================
    # Example 2 — Multi-Field: Quality + Category + Price + Title
    # ==================================================================

    print("\n" + "=" * 60)
    print("MARKETPLACE EXAMPLE 2: Multi-Field Listing Quality Eval")
    print("=" * 60)

    quality_cases = [
        {
            "input": "iPhone 14 Pro Max 256GB – mint condition | $899",
            "expected": {
                "quality_label": "high",
                "category": "electronics",
                "suggested_price": 879.00,
                "title_clear": True,
            },
        },
        {
            "input": "couch | $150",
            "expected": {
                "quality_label": "low",
                "category": "furniture",
                "suggested_price": 120.00,
                "title_clear": False,
            },
        },
        {
            "input": "2019 Honda Civic EX – 42k miles, clean title | $18500",
            "expected": {
                "quality_label": "high",
                "category": "vehicles",
                "suggested_price": 18200.00,
                "title_clear": True,
            },
        },
        {
            "input": "RARE JORDANS 🔥🔥🔥 DM ME!!! | $0",
            "expected": {
                "quality_label": "low",
                "category": "footwear",
                "suggested_price": 0.00,
                "title_clear": False,
            },
        },
        {
            "input": "KitchenAid Stand Mixer – Artisan 5qt, Empire Red | $275",
            "expected": {
                "quality_label": "high",
                "category": "kitchen",
                "suggested_price": 260.00,
                "title_clear": True,
            },
        },
        {
            "input": "Vitamix Professional 750 Blender – like new | $350",
            "expected": {
                "quality_label": "high",
                "category": "kitchen",
                "suggested_price": 340.00,
                "title_clear": True,
            },
        },
    ]

    dataset = Dataset.from_list(
        items=quality_cases,
        input_key="input",
        expected_key="expected",
        name="marketplace_listing_quality",
    )

    scorer = CompositeScorer([
        (ExactMatchScorer(field="quality_label", case_sensitive=False, name="quality_label"), 0.30),
        (ExactMatchScorer(field="category", case_sensitive=False, name="category_match"), 0.20),
        (NumericToleranceScorer(field="suggested_price", tolerance=50.0, name="price_accuracy"), 0.30),
        (ExactMatchScorer(field="title_clear", name="title_clarity"), 0.20),
    ])

    eval_obj = Eval(
        name="marketplace_listing_quality",
        dataset=dataset,
        scorers=[scorer],
        thresholds={"composite": 0.80},
    )

    eval_runner = EvalRunner(eval_obj)
    results = eval_runner.run(
        generate_fn=lambda q: mock_listing_quality_model(q.split(" | ")[0]),
    )
    print(results.summary())

    # ==================================================================
    # Example 3 — Edge Cases: Prohibited items detection
    # ==================================================================

    print("\n" + "=" * 60)
    print("MARKETPLACE EXAMPLE 3: Prohibited Items Detection")
    print("=" * 60)

    prohibited_cases = [
        {"input": "Prescription medication – Adderall 30mg", "expected": "blocked"},
        {"input": "Handgun Glock 19 Gen 5",                  "expected": "blocked"},
        {"input": "Fake Louis Vuitton bag – great quality",   "expected": "blocked"},
        {"input": "Concert tickets – Taylor Swift Eras Tour", "expected": "allowed"},
        {"input": "Vintage vinyl records collection",         "expected": "allowed"},
        {"input": "Homemade CBD oil – organic",               "expected": "blocked"},
        {"input": "Nintendo Switch OLED – barely used",       "expected": "allowed"},
        {"input": "Stolen bike – need cash fast",             "expected": "blocked"},
        {"input": "Hand-knitted baby blanket",                "expected": "allowed"},
        {"input": "Fireworks – professional grade",           "expected": "blocked"},
    ]

    BLOCKED_KEYWORDS = [
        "prescription", "medication", "adderall", "handgun", "glock",
        "gun", "fake", "counterfeit", "replica", "cbd", "thc", "marijuana",
        "stolen", "fireworks", "explosive",
    ]

    def mock_prohibited_detector(title: str) -> str:
        title_lower = title.lower()
        for kw in BLOCKED_KEYWORDS:
            if kw in title_lower:
                return "blocked"
        return "allowed"

    prohibited_runner = SimpleEvalRunner(
        test_cases=prohibited_cases,
        scorer=ExactMatchScorer(case_sensitive=False),
        name="prohibited_items_detection",
    )

    prohibited_results = prohibited_runner.run(model_fn=mock_prohibited_detector)

    print(f"\n  Score:       {prohibited_results['score']:.0%}")
    print(f"  Pass Rate:   {prohibited_results['pass_rate']:.0%}")
    print(f"  Passed 80%:  {'✅' if prohibited_results['passed_80_threshold'] else '❌'}")

    if prohibited_results["failures"]:
        print(f"\n  Failures ({len(prohibited_results['failures'])}):")
        for f in prohibited_results["failures"]:
            print(f"    • {f['input'][:50]}…  expected={f['expected']}  got={f['actual']}")

    # ==================================================================
    # Example 4 — Category taxonomy F1 (multi-label)
    # ==================================================================

    print("\n" + "=" * 60)
    print("MARKETPLACE EXAMPLE 4: Category Taxonomy F1")
    print("=" * 60)

    taxonomy_cases = [
        {"input": "iPhone 14 case",            "expected": ["electronics", "accessories"],      "actual": ["electronics", "accessories"]},
        {"input": "Leather sectional sofa",     "expected": ["furniture", "living_room"],        "actual": ["furniture"]},
        {"input": "Mountain bike – Specialized","expected": ["sports", "cycling"],               "actual": ["sports", "cycling", "outdoors"]},
        {"input": "PS5 Digital Edition",        "expected": ["electronics", "gaming"],           "actual": ["electronics", "gaming"]},
        {"input": "Vintage dining table set",   "expected": ["furniture", "dining", "vintage"],  "actual": ["furniture", "dining"]},
    ]

    taxonomy_dataset = Dataset.from_list(
        items=taxonomy_cases,
        input_key="input",
        expected_key="expected",
        name="marketplace_taxonomy",
    )

    taxonomy_eval = Eval(
        name="marketplace_category_f1",
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

    # ==================================================================
    # Example 5 — Production Config with thresholds + GK + CI blocking
    # ==================================================================

    print("\n" + "=" * 60)
    print("MARKETPLACE EXAMPLE 5: Production Config")
    print("=" * 60)

    prod_config = EvalConfig(
        name="marketplace_listing_quality_v3",
        version="3.0.0",
        description=(
            "End-to-end evaluation of the Marketplace listing quality model. "
            "Measures policy compliance, category classification, price "
            "suggestion accuracy, and title clarity across all listing types."
        ),
        owner=EvalOwner(
            pm="@marketplace_pm",
            eng="@marketplace_quality_oncall",
            team="Marketplace Trust & Quality",
        ),
        capability_what=(
            "Assess listing quality (policy compliance, category, price "
            "suggestion, title clarity) for Marketplace submissions"
        ),
        capability_why=(
            "Directly impacts buyer trust, GMV, and regulatory compliance. "
            "Poor quality listings reduce conversion and increase C2C disputes."
        ),
        dataset_source="hive://marketplace_evals/listing_quality_golden_set_v3",
        dataset_size=10000,
        primary_metric="weighted_score",
        metrics=[
            {"name": "policy_compliance", "type": "exact_match", "weight": 0.35},
            {"name": "category_f1", "type": "f1_score", "weight": 0.20},
            {"name": "price_accuracy", "type": "numeric_tolerance", "weight": 0.25},
            {"name": "title_quality", "type": "token_f1", "weight": 0.20},
        ],
        thresholds=Threshold(
            baseline={
                "policy_compliance": 0.95,
                "category_f1": 0.85,
                "price_accuracy": 0.80,
                "title_quality": 0.75,
            },
            target={
                "policy_compliance": 0.99,
                "category_f1": 0.92,
                "price_accuracy": 0.90,
                "title_quality": 0.85,
            },
            blocking=True,
        ),
        gk_name="marketplace_listing_quality_v3",
        task_id="T112233445",
        diff_ids=["D556677889"],
        feature_name="Marketplace Listing Quality Model v3",
        tags=["marketplace", "trust", "quality", "production", "policy"],
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
    print(f"  Dataset:  {prod_config.dataset_size} examples")
    print(f"  Baseline: {prod_config.thresholds.baseline}")
    print(f"  Target:   {prod_config.thresholds.target}")


if __name__ == "__main__":
    main()
