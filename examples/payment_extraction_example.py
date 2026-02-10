"""
MFT Eval - Example: Payment Metadata Extraction

This example demonstrates how to create and run an eval
matching the example from the MFT reference doc.

From the reference doc:
"Measure how accurately our AI system extracts structured payment data
from raw transaction descriptions and receipts."
"""

from mft_evals import (
    Eval,
    EvalConfig,
    Dataset,
    ExactMatchScorer,
    NumericToleranceScorer,
    TokenF1Scorer,
    CompositeScorer,
    EvalRunner,
)
from mft_evals.scorers import PaymentAmountScorer, CurrencyCodeScorer


def main():
    # ==========================================================
    # Example 1: Minimum Viable Eval (50-100 examples)
    # ==========================================================

    print("\n" + "="*60)
    print("EXAMPLE 1: Minimum Viable Eval")
    print("="*60)

    # Create a simple dataset
    test_cases = [
        {
            "input": "Receipt: Starbucks Coffee $4.50 USD on 2024-01-15",
            "expected": {"amount": 4.50, "currency": "USD", "merchant": "Starbucks Coffee"},
            "actual": {"amount": 4.50, "currency": "USD", "merchant": "Starbucks"},
        },
        {
            "input": "Payment to Amazon.com for $123.45 EUR",
            "expected": {"amount": 123.45, "currency": "EUR", "merchant": "Amazon.com"},
            "actual": {"amount": 123.45, "currency": "EUR", "merchant": "Amazon"},
        },
        {
            "input": "Transfer: $1,000.00 to John Doe",
            "expected": {"amount": 1000.00, "currency": "USD", "merchant": "John Doe"},
            "actual": {"amount": 1000.01, "currency": "USD", "merchant": "John Doe"},
        },
        {
            "input": "Netflix subscription $15.99 monthly",
            "expected": {"amount": 15.99, "currency": "USD", "merchant": "Netflix"},
            "actual": {"amount": 15.99, "currency": "USD", "merchant": "Netflix Inc"},
        },
        {
            "input": "Uber ride €12.30",
            "expected": {"amount": 12.30, "currency": "EUR", "merchant": "Uber"},
            "actual": {"amount": 12.30, "currency": "EUR", "merchant": "Uber"},
        },
    ]

    dataset = Dataset.from_list(
        items=test_cases,
        input_key="input",
        expected_key="expected",
        name="payment_extraction_mve"
    )

    # Create composite scorer matching the reference doc example
    scorer = CompositeScorer([
        (PaymentAmountScorer(field="amount", tolerance=0.01), 0.30),
        (CurrencyCodeScorer(field="currency"), 0.20),
        (TokenF1Scorer(field="merchant"), 0.20),
    ])

    # Create eval
    eval = Eval(
        name="payment_metadata_extraction_mve",
        dataset=dataset,
        scorers=[scorer],
        thresholds={
            "composite": 0.80,  # 80% pass rate for MVE
        }
    )

    # Run eval (using pre-generated outputs from metadata)
    runner = EvalRunner(eval)
    results = runner.run(
        generate_fn=lambda x: next(
            tc.metadata["actual"]
            for tc in dataset
            if tc.input == x
        )
    )

    print(results.summary())

    # ==========================================================
    # Example 2: Production-Grade Eval with Full Config
    # ==========================================================

    print("\n" + "="*60)
    print("EXAMPLE 2: Production-Grade Eval (from YAML config)")
    print("="*60)

    # Load eval from YAML config
    config = EvalConfig(
        name="payment_metadata_extraction",
        version="1.2.0",
        description="""
        Measure how accurately our AI system extracts structured payment data
        from raw transaction descriptions and receipts.
        """,
        capability_what="Extract payment metadata (amount, currency, date, merchant, etc.)",
        capability_why="Enable automated dispute resolution and reconciliation",
        dataset_source="hive://mft_evals/payment_extraction_v2",
        dataset_size=3000,
        primary_metric="weighted_score",
        metrics=[
            {"name": "full_match", "type": "exact_match", "weight": 0.30},
            {"name": "amount_f1", "type": "f1_score", "field": "amount", "weight": 0.25},
            {"name": "date_accuracy", "type": "exact_match", "field": "date", "weight": 0.20},
            {"name": "currency_f1", "type": "f1_score", "field": "currency", "weight": 0.15},
            {"name": "merchant_f1", "type": "token_f1", "field": "merchant", "weight": 0.10},
        ],
        tags=["payments", "extraction", "production"],
    )

    # Validate config
    errors = config.validate()
    if errors:
        print("Config validation errors:")
        for error in errors:
            print(f"  - {error}")
    else:
        print("✅ Config is valid!")

    # Show config as YAML
    print("\nConfig as YAML:")
    print("-" * 40)
    import yaml
    print(yaml.dump(config.to_dict(), default_flow_style=False))

    # ==========================================================
    # Example 3: SimpleEvalRunner for Quick Testing
    # ==========================================================

    print("\n" + "="*60)
    print("EXAMPLE 3: SimpleEvalRunner for Quick Testing")
    print("="*60)

    from mft_evals.runner import SimpleEvalRunner
    from mft_evals.scorers import ExactMatchScorer

    # Simple test cases
    simple_tests = [
        {"input": "What currency is $50?", "expected": "USD"},
        {"input": "What currency is €100?", "expected": "EUR"},
        {"input": "What currency is £75?", "expected": "GBP"},
        {"input": "What currency is ¥1000?", "expected": "JPY"},
    ]

    # Mock model function
    def mock_currency_detector(input_text: str) -> str:
        if "$" in input_text:
            return "USD"
        elif "€" in input_text:
            return "EUR"
        elif "£" in input_text:
            return "GBP"
        elif "¥" in input_text:
            return "JPY"
        return "UNKNOWN"

    simple_runner = SimpleEvalRunner(
        test_cases=simple_tests,
        scorer=ExactMatchScorer(),
        name="currency_detection"
    )

    simple_results = simple_runner.run(model_fn=mock_currency_detector)

    print(f"\nSimple Eval Results:")
    print(f"  Score: {simple_results['score']:.2%}")
    print(f"  Pass Rate: {simple_results['pass_rate']:.2%}")
    print(f"  Passed 80% Threshold: {'✅' if simple_results['passed_80_threshold'] else '❌'}")

    # ==========================================================
    # Example 4: Running Eval with Custom Thresholds
    # ==========================================================

    print("\n" + "="*60)
    print("EXAMPLE 4: Custom Thresholds (Baseline vs Target)")
    print("="*60)

    from mft_evals.eval import Threshold

    config_with_thresholds = EvalConfig(
        name="transaction_classifier",
        version="1.0.0",
        description="Classify transaction disputes into categories",
        capability_what="Correctly classifies transaction disputes into one of 8 categories",
        capability_why="Enable automated dispute resolution",
        primary_metric="accuracy",
        thresholds=Threshold(
            baseline={
                "accuracy": 0.90,
                "precision": 0.85,
                "recall": 0.85,
            },
            target={
                "accuracy": 0.95,
                "precision": 0.92,
                "recall": 0.92,
            },
            blocking=True,  # Blocks deploy if below baseline
        ),
    )

    print(f"Eval: {config_with_thresholds.name}")
    print(f"Baseline thresholds: {config_with_thresholds.thresholds.baseline}")
    print(f"Target thresholds: {config_with_thresholds.thresholds.target}")
    print(f"Blocking: {config_with_thresholds.thresholds.blocking}")


if __name__ == "__main__":
    main()
