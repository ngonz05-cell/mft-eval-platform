# MFT Eval Platform
# A simple, accessible evaluation framework for Meta Fintech

from mft_evals.eval import Eval, EvalConfig
from mft_evals.dataset import Dataset
from mft_evals.scorers import (
    ExactMatchScorer,
    F1Scorer,
    TokenF1Scorer,
    NumericToleranceScorer,
    LLMJudgeScorer,
    CompositeScorer,
)
from mft_evals.results import EvalResults
from mft_evals.runner import EvalRunner

__version__ = "0.1.0"

__all__ = [
    "Eval",
    "EvalConfig",
    "Dataset",
    "ExactMatchScorer",
    "F1Scorer",
    "TokenF1Scorer",
    "NumericToleranceScorer",
    "LLMJudgeScorer",
    "CompositeScorer",
    "EvalResults",
    "EvalRunner",
]
