# MFT Eval Platform
# A simple, accessible evaluation framework for Meta Fintech

from mft_evals.eval import Eval, EvalConfig
from mft_evals.dataset import Dataset
from mft_evals.scorers import (
    BinaryPassFailScorer,
    CompositeScorer,
    CurrencyCodeScorer,
    ExactMatchScorer,
    F1Scorer,
    LLMJudgeScorer,
    NumericToleranceScorer,
    PaymentAmountScorer,
    TokenF1Scorer,
)
from mft_evals.results import EvalResults
from mft_evals.runner import EvalRunner

__version__ = "0.2.0"

__all__ = [
    "Eval",
    "EvalConfig",
    "Dataset",
    "BinaryPassFailScorer",
    "CompositeScorer",
    "CurrencyCodeScorer",
    "ExactMatchScorer",
    "F1Scorer",
    "LLMJudgeScorer",
    "NumericToleranceScorer",
    "PaymentAmountScorer",
    "TokenF1Scorer",
    "EvalResults",
    "EvalRunner",
]
