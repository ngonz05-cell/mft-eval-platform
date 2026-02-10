"""
MFT Eval - Scorers

From the reference doc:
"Decide how success is measured."

Options include:
- Exact match
- Structured field accuracy
- Binary pass/fail
- Graded scores (e.g. 1-5)
- Model-judged outputs (with care)

Rules of thumb:
- Start simple
- Prefer deterministic scoring where possible
- Accept imperfect metrics early—iterate later
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Union
import re


@dataclass
class ScorerResult:
    """Result from a single scorer"""
    score: float  # 0.0 to 1.0
    passed: bool
    details: Dict[str, Any] = None
    rationale: str = ""

    def __post_init__(self):
        if self.details is None:
            self.details = {}


class Scorer(ABC):
    """
    Base class for all scorers.

    Each scorer evaluates a specific aspect of the model output
    and returns a score between 0.0 and 1.0.
    """

    def __init__(self, name: str = None, weight: float = 1.0):
        self.name = name or self.__class__.__name__
        self.weight = weight

    @abstractmethod
    def score(self, expected: Any, actual: Any, **kwargs) -> ScorerResult:
        """
        Score the actual output against expected.

        Args:
            expected: The expected/ground truth output
            actual: The actual model output
            **kwargs: Additional context (e.g., full test case)

        Returns:
            ScorerResult with score and details
        """
        pass

    def __call__(self, expected: Any, actual: Any, **kwargs) -> ScorerResult:
        return self.score(expected, actual, **kwargs)


class ExactMatchScorer(Scorer):
    """
    Exact string match scorer.

    Use for:
    - Transaction IDs
    - Category classifications
    - Binary yes/no answers
    - Enum values

    Example:
        scorer = ExactMatchScorer(field="transaction_id")
        result = scorer.score(
            expected={"transaction_id": "TXN123"},
            actual={"transaction_id": "TXN123"}
        )
    """

    def __init__(
        self,
        field: Optional[str] = None,
        case_sensitive: bool = True,
        strip_whitespace: bool = True,
        name: str = None,
        weight: float = 1.0,
    ):
        super().__init__(name or f"exact_match_{field or 'value'}", weight)
        self.field = field
        self.case_sensitive = case_sensitive
        self.strip_whitespace = strip_whitespace

    def score(self, expected: Any, actual: Any, **kwargs) -> ScorerResult:
        # Extract field if specified
        if self.field:
            expected_val = self._get_field(expected, self.field)
            actual_val = self._get_field(actual, self.field)
        else:
            expected_val = expected
            actual_val = actual

        # Convert to string for comparison
        expected_str = str(expected_val) if expected_val is not None else ""
        actual_str = str(actual_val) if actual_val is not None else ""

        # Normalize
        if self.strip_whitespace:
            expected_str = expected_str.strip()
            actual_str = actual_str.strip()

        if not self.case_sensitive:
            expected_str = expected_str.lower()
            actual_str = actual_str.lower()

        # Compare
        matches = expected_str == actual_str

        return ScorerResult(
            score=1.0 if matches else 0.0,
            passed=matches,
            details={
                "expected": expected_str,
                "actual": actual_str,
                "field": self.field,
            },
            rationale=f"{'Match' if matches else 'No match'}: expected '{expected_str}', got '{actual_str}'"
        )

    def _get_field(self, obj: Any, field: str) -> Any:
        """Extract field from dict or object"""
        if isinstance(obj, dict):
            return obj.get(field)
        return getattr(obj, field, None)


class F1Scorer(Scorer):
    """
    F1 Score (harmonic mean of precision and recall).

    Use for:
    - Classification tasks
    - Entity extraction
    - Multi-label predictions

    Example:
        scorer = F1Scorer(field="categories")
        result = scorer.score(
            expected=["fraud", "high_value"],
            actual=["fraud", "suspicious"]
        )
    """

    def __init__(
        self,
        field: Optional[str] = None,
        average: str = "micro",  # micro, macro, binary
        name: str = None,
        weight: float = 1.0,
    ):
        super().__init__(name or f"f1_{field or 'value'}", weight)
        self.field = field
        self.average = average

    def score(self, expected: Any, actual: Any, **kwargs) -> ScorerResult:
        # Extract field if specified
        if self.field:
            expected_val = self._get_field(expected, self.field)
            actual_val = self._get_field(actual, self.field)
        else:
            expected_val = expected
            actual_val = actual

        # Convert to sets for comparison
        expected_set = self._to_set(expected_val)
        actual_set = self._to_set(actual_val)

        # Calculate precision, recall, F1
        if not actual_set:
            precision = 0.0
        else:
            precision = len(expected_set & actual_set) / len(actual_set)

        if not expected_set:
            recall = 1.0 if not actual_set else 0.0
        else:
            recall = len(expected_set & actual_set) / len(expected_set)

        if precision + recall == 0:
            f1 = 0.0
        else:
            f1 = 2 * (precision * recall) / (precision + recall)

        return ScorerResult(
            score=f1,
            passed=f1 > 0.5,  # Configurable threshold
            details={
                "precision": precision,
                "recall": recall,
                "f1": f1,
                "expected_set": list(expected_set),
                "actual_set": list(actual_set),
                "field": self.field,
            },
            rationale=f"F1={f1:.3f} (precision={precision:.3f}, recall={recall:.3f})"
        )

    def _get_field(self, obj: Any, field: str) -> Any:
        if isinstance(obj, dict):
            return obj.get(field)
        return getattr(obj, field, None)

    def _to_set(self, val: Any) -> set:
        if val is None:
            return set()
        if isinstance(val, set):
            return val
        if isinstance(val, (list, tuple)):
            return set(val)
        return {val}


class TokenF1Scorer(Scorer):
    """
    Token-level F1 for fuzzy string matching.

    Use for:
    - Merchant names (with variations)
    - Addresses
    - Free-form text where exact match is too strict

    Example:
        scorer = TokenF1Scorer(field="merchant")
        result = scorer.score(
            expected="STARBUCKS COFFEE #1234",
            actual="Starbucks Coffee"
        )
    """

    def __init__(
        self,
        field: Optional[str] = None,
        lowercase: bool = True,
        name: str = None,
        weight: float = 1.0,
    ):
        super().__init__(name or f"token_f1_{field or 'value'}", weight)
        self.field = field
        self.lowercase = lowercase

    def score(self, expected: Any, actual: Any, **kwargs) -> ScorerResult:
        # Extract field if specified
        if self.field:
            expected_val = self._get_field(expected, self.field)
            actual_val = self._get_field(actual, self.field)
        else:
            expected_val = expected
            actual_val = actual

        # Tokenize
        expected_tokens = self._tokenize(str(expected_val or ""))
        actual_tokens = self._tokenize(str(actual_val or ""))

        expected_set = set(expected_tokens)
        actual_set = set(actual_tokens)

        # Calculate F1
        if not actual_set:
            precision = 0.0
        else:
            precision = len(expected_set & actual_set) / len(actual_set)

        if not expected_set:
            recall = 1.0 if not actual_set else 0.0
        else:
            recall = len(expected_set & actual_set) / len(expected_set)

        if precision + recall == 0:
            f1 = 0.0
        else:
            f1 = 2 * (precision * recall) / (precision + recall)

        return ScorerResult(
            score=f1,
            passed=f1 > 0.5,
            details={
                "precision": precision,
                "recall": recall,
                "f1": f1,
                "expected_tokens": expected_tokens,
                "actual_tokens": actual_tokens,
            },
            rationale=f"Token F1={f1:.3f} ({len(expected_set & actual_set)}/{len(expected_set)} tokens matched)"
        )

    def _get_field(self, obj: Any, field: str) -> Any:
        if isinstance(obj, dict):
            return obj.get(field)
        return getattr(obj, field, None)

    def _tokenize(self, text: str) -> List[str]:
        if self.lowercase:
            text = text.lower()
        # Split on whitespace and punctuation, keep alphanumeric
        tokens = re.findall(r'\w+', text)
        return tokens


class NumericToleranceScorer(Scorer):
    """
    Numeric comparison with tolerance.

    Use for:
    - Payment amounts (within $0.01)
    - Percentages
    - Quantities where rounding may differ

    Example:
        scorer = NumericToleranceScorer(field="amount", tolerance=0.01)
        result = scorer.score(
            expected={"amount": 123.45},
            actual={"amount": 123.46}
        )
    """

    def __init__(
        self,
        field: Optional[str] = None,
        tolerance: float = 0.01,
        relative: bool = False,  # If True, tolerance is a percentage
        name: str = None,
        weight: float = 1.0,
    ):
        super().__init__(name or f"numeric_{field or 'value'}", weight)
        self.field = field
        self.tolerance = tolerance
        self.relative = relative

    def score(self, expected: Any, actual: Any, **kwargs) -> ScorerResult:
        # Extract field if specified
        if self.field:
            expected_val = self._get_field(expected, self.field)
            actual_val = self._get_field(actual, self.field)
        else:
            expected_val = expected
            actual_val = actual

        # Parse to numbers
        try:
            expected_num = self._parse_number(expected_val)
            actual_num = self._parse_number(actual_val)
        except (ValueError, TypeError) as e:
            return ScorerResult(
                score=0.0,
                passed=False,
                details={"error": str(e)},
                rationale=f"Could not parse numbers: {e}"
            )

        # Calculate difference
        diff = abs(expected_num - actual_num)

        if self.relative:
            # Relative tolerance (percentage)
            if expected_num == 0:
                within_tolerance = diff == 0
            else:
                within_tolerance = (diff / abs(expected_num)) <= self.tolerance
        else:
            # Absolute tolerance
            within_tolerance = diff <= self.tolerance

        # Exact match gets 1.0, within tolerance gets 0.9, otherwise proportional
        if diff == 0:
            score = 1.0
        elif within_tolerance:
            score = 0.9
        else:
            # Proportional score based on how close we are
            score = max(0.0, 1.0 - (diff / (abs(expected_num) + 1)))

        return ScorerResult(
            score=score,
            passed=within_tolerance,
            details={
                "expected": expected_num,
                "actual": actual_num,
                "difference": diff,
                "tolerance": self.tolerance,
                "relative": self.relative,
            },
            rationale=f"Diff={diff:.4f} ({'within' if within_tolerance else 'exceeds'} tolerance {self.tolerance})"
        )

    def _get_field(self, obj: Any, field: str) -> Any:
        if isinstance(obj, dict):
            return obj.get(field)
        return getattr(obj, field, None)

    def _parse_number(self, val: Any) -> float:
        if val is None:
            raise ValueError("Value is None")
        if isinstance(val, (int, float)):
            return float(val)
        # Try to parse string (handle currency symbols, commas)
        val_str = str(val)
        # Remove currency symbols and commas
        cleaned = re.sub(r'[,$€£¥]', '', val_str)
        return float(cleaned)


class LLMJudgeScorer(Scorer):
    """
    LLM-as-judge for subjective evaluations.

    From the reference doc:
    "For subjective tasks (e.g., 'Is this response helpful?'),
    you can use another LLM to score outputs."

    Best practices:
    - Use a stronger model to judge a weaker model
    - Validate LLM-judge scores against human labels on a sample
    - Watch for judge bias (preferring longer responses, specific phrasings)
    - Use structured rubrics

    When to avoid:
    - High-stakes decisions (e.g., fraud detection, compliance)
    - When ground truth is available (use deterministic scoring instead)

    Example:
        scorer = LLMJudgeScorer(
            rubric="Rate 1-5 on accuracy, completeness, and tone",
            model="llama-4"
        )
    """

    def __init__(
        self,
        rubric: str,
        model: str = "llama-4",
        temperature: float = 0.0,
        name: str = None,
        weight: float = 1.0,
    ):
        super().__init__(name or "llm_judge", weight)
        self.rubric = rubric
        self.model = model
        self.temperature = temperature

    def score(self, expected: Any, actual: Any, **kwargs) -> ScorerResult:
        """
        Note: This is a placeholder implementation.
        In production, this would call Meta's internal LLM infrastructure.
        """
        # Build the judge prompt
        prompt = self._build_prompt(expected, actual, **kwargs)

        # Call LLM (placeholder - would use MetaGen/MUTE in production)
        try:
            judge_response = self._call_llm(prompt)
            score, rationale = self._parse_response(judge_response)
        except Exception as e:
            return ScorerResult(
                score=0.0,
                passed=False,
                details={"error": str(e)},
                rationale=f"LLM judge failed: {e}"
            )

        return ScorerResult(
            score=score,
            passed=score >= 0.7,  # Configurable threshold
            details={
                "rubric": self.rubric,
                "model": self.model,
                "raw_response": judge_response,
            },
            rationale=rationale
        )

    def _build_prompt(self, expected: Any, actual: Any, **kwargs) -> str:
        input_text = kwargs.get("input", "")

        return f"""You are an expert evaluator. Evaluate the following response.

## Rubric
{self.rubric}

## Input/Query
{input_text}

## Expected Response
{expected}

## Actual Response
{actual}

## Instructions
Rate the actual response on a scale of 0.0 to 1.0.
Provide a brief rationale for your score.

Respond in this exact format:
SCORE: <number between 0.0 and 1.0>
RATIONALE: <your explanation>
"""

    def _call_llm(self, prompt: str) -> str:
        """
        Call LLM to get judgment.

        This is a placeholder - in production, this would use:
        - MetaGen's LLM infrastructure
        - MUTE's judge framework
        - Or direct API calls to model endpoints
        """
        # Placeholder: In production, replace with actual LLM call
        # For now, return a mock response for testing
        raise NotImplementedError(
            "LLM judge requires Meta internal infrastructure. "
            "Use deterministic scorers for local testing."
        )

    def _parse_response(self, response: str) -> tuple[float, str]:
        """Parse LLM response to extract score and rationale"""
        lines = response.strip().split('\n')
        score = 0.5
        rationale = ""

        for line in lines:
            if line.startswith("SCORE:"):
                try:
                    score = float(line.replace("SCORE:", "").strip())
                    score = max(0.0, min(1.0, score))  # Clamp to [0, 1]
                except ValueError:
                    pass
            elif line.startswith("RATIONALE:"):
                rationale = line.replace("RATIONALE:", "").strip()

        return score, rationale


class CompositeScorer(Scorer):
    """
    Combines multiple scorers with weights.

    From the reference doc example:
    Score = 0.3 * FullMatch + 0.25 * AmountF1 + 0.20 * DateAccuracy + ...

    Example:
        scorer = CompositeScorer([
            (ExactMatchScorer(field="txn_id"), 0.3),
            (NumericToleranceScorer(field="amount"), 0.25),
            (TokenF1Scorer(field="merchant"), 0.15),
        ])
    """

    def __init__(
        self,
        scorers: List[Union[Scorer, tuple[Scorer, float]]],
        name: str = None,
    ):
        super().__init__(name or "composite")

        self.scorers = []
        self.weights = []

        for item in scorers:
            if isinstance(item, tuple):
                scorer, weight = item
            else:
                scorer = item
                weight = getattr(scorer, 'weight', 1.0)

            self.scorers.append(scorer)
            self.weights.append(weight)

        # Normalize weights
        total_weight = sum(self.weights)
        if total_weight > 0:
            self.weights = [w / total_weight for w in self.weights]

    def score(self, expected: Any, actual: Any, **kwargs) -> ScorerResult:
        results = []
        weighted_score = 0.0

        for scorer, weight in zip(self.scorers, self.weights):
            result = scorer.score(expected, actual, **kwargs)
            results.append({
                "scorer": scorer.name,
                "weight": weight,
                "score": result.score,
                "passed": result.passed,
                "rationale": result.rationale,
            })
            weighted_score += result.score * weight

        all_passed = all(r["passed"] for r in results)

        return ScorerResult(
            score=weighted_score,
            passed=all_passed,
            details={
                "component_scores": results,
                "weights": dict(zip([s.name for s in self.scorers], self.weights)),
            },
            rationale=f"Composite score: {weighted_score:.3f} ({sum(1 for r in results if r['passed'])}/{len(results)} components passed)"
        )


class BinaryPassFailScorer(Scorer):
    """
    Simple binary pass/fail based on a predicate function.

    Use for:
    - Valid JSON output
    - Contains required fields
    - Meets basic format requirements

    Example:
        scorer = BinaryPassFailScorer(
            predicate=lambda actual: "error" not in actual.lower(),
            name="no_error"
        )
    """

    def __init__(
        self,
        predicate: Callable[[Any], bool],
        name: str = "binary",
        weight: float = 1.0,
    ):
        super().__init__(name, weight)
        self.predicate = predicate

    def score(self, expected: Any, actual: Any, **kwargs) -> ScorerResult:
        try:
            passed = self.predicate(actual)
        except Exception as e:
            return ScorerResult(
                score=0.0,
                passed=False,
                details={"error": str(e)},
                rationale=f"Predicate raised exception: {e}"
            )

        return ScorerResult(
            score=1.0 if passed else 0.0,
            passed=passed,
            rationale="Pass" if passed else "Fail"
        )


# Fintech-specific scorers

class PaymentAmountScorer(NumericToleranceScorer):
    """
    Specialized scorer for payment amounts.

    Handles:
    - Currency symbols ($, €, £, etc.)
    - Comma separators
    - Strict tolerance (default $0.01)
    """

    def __init__(
        self,
        field: str = "amount",
        tolerance: float = 0.01,
        name: str = None,
        weight: float = 1.0,
    ):
        super().__init__(
            field=field,
            tolerance=tolerance,
            relative=False,
            name=name or "payment_amount",
            weight=weight
        )


class CurrencyCodeScorer(ExactMatchScorer):
    """
    Validates currency codes against ISO 4217.
    """

    ISO_4217_CODES = {
        "USD", "EUR", "GBP", "JPY", "CNY", "INR", "BRL", "CAD", "AUD",
        "CHF", "HKD", "SGD", "MXN", "KRW", "RUB", "ZAR", "TRY", "SEK",
        "NOK", "DKK", "NZD", "THB", "MYR", "IDR", "PHP", "PLN", "CZK",
        "HUF", "ILS", "AED", "SAR", "CLP", "COP", "PEN", "ARS", "VND"
    }

    def __init__(
        self,
        field: str = "currency",
        name: str = None,
        weight: float = 1.0,
    ):
        super().__init__(
            field=field,
            case_sensitive=False,
            name=name or "currency_code",
            weight=weight
        )

    def score(self, expected: Any, actual: Any, **kwargs) -> ScorerResult:
        # First check if the actual currency is valid ISO 4217
        if self.field:
            actual_val = self._get_field(actual, self.field)
        else:
            actual_val = actual

        actual_code = str(actual_val).upper().strip() if actual_val else ""

        if actual_code not in self.ISO_4217_CODES:
            return ScorerResult(
                score=0.0,
                passed=False,
                details={"actual": actual_code, "valid": False},
                rationale=f"Invalid currency code: '{actual_code}' not in ISO 4217"
            )

        # Then check if it matches expected
        return super().score(expected, actual, **kwargs)
