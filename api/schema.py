"""
Pydantic schemas for structured LLM output.

These define the JSON format the LLM must return at each conversation phase,
ensuring we can reliably parse responses into evalConfig fields.

Also includes request/response models for the eval runner API.
"""
from pydantic import BaseModel, Field
from typing import Any, Dict, List, Optional
from enum import Enum


class Phase(str, Enum):
    OBJECTIVE = "objective"
    REFINE = "refine"
    METRICS = "metrics"
    SAMPLE_DATA = "sample_data"
    CONNECT = "connect"
    MANAGE = "manage"
    REVIEW = "review"


class ClarifyingQuestion(BaseModel):
    question: str = Field(description="The clarifying question to ask the user")
    why: str = Field(description="Brief reason this question matters for eval design")


class RefinedPromptResponse(BaseModel):
    """Returned when the user gives an initial description — LLM refines it and asks questions."""
    message: str = Field(description="Conversational response to show in the chat bubble")
    refined_prompt: str = Field(description="An improved, more specific version of the user's description")
    clarifying_questions: list[ClarifyingQuestion] = Field(
        default_factory=list,
        description="0-3 clarifying questions to help improve the eval description"
    )
    is_detailed_enough: bool = Field(
        default=False,
        description="True if the description is already detailed enough to skip refinement"
    )


class MetricSuggestion(BaseModel):
    """A single suggested metric with measurement method, thresholds, and rationale."""
    field: str = Field(description="Short metric name, e.g. 'Field Accuracy'")
    measurement: list[str] = Field(
        description="Measurement method IDs. Valid values: exact_match_ratio, simple_pass_fail, "
                    "weighted_composite, contains_check, numeric_tolerance, fuzzy_string_match, "
                    "classification_f1, llm_judge, field_f1, task_success_rate, tool_correctness"
    )
    description: str = Field(description="One-line description of what this metric measures")
    baseline: int = Field(ge=0, le=100, description="Minimum acceptable threshold percentage")
    target: int = Field(ge=0, le=100, description="Goal threshold percentage")
    rationale: str = Field(
        description="2-3 sentence explanation of WHY this metric, measurement method, "
                    "and threshold values were chosen. Should educate the user."
    )


class MetricsResponse(BaseModel):
    """Returned when generating metrics from a finalized description."""
    message: str = Field(description="Conversational response to show in the chat bubble")
    eval_name: str = Field(description="Suggested snake_case eval name")
    metrics: list[MetricSuggestion] = Field(description="List of suggested metrics")


class ChatResponse(BaseModel):
    """General chat response for follow-up messages within any phase."""
    message: str = Field(description="Conversational response to show in the chat bubble")
    config_updates: Optional[dict] = Field(
        default=None,
        description="Optional partial updates to evalConfig fields"
    )
    refined_prompt: Optional[str] = Field(
        default=None,
        description="Updated refined prompt if the user provided additional context"
    )
    metrics: Optional[list[MetricSuggestion]] = Field(
        default=None,
        description="Updated metrics if the user requested changes"
    )


# --- Request schemas ---

class ConversationMessage(BaseModel):
    role: str = Field(description="'user' or 'assistant'")
    content: str


class ChatRequest(BaseModel):
    """Request body for the /api/chat endpoint."""
    phase: Phase = Field(description="Current conversation phase")
    message: str = Field(description="User's latest message")
    conversation_history: list[ConversationMessage] = Field(
        default_factory=list,
        description="Previous messages for context"
    )
    eval_config: Optional[dict] = Field(
        default=None,
        description="Current evalConfig state from the frontend"
    )


class GenerateMetricsRequest(BaseModel):
    """Request body for the /api/generate-metrics endpoint."""
    description: str = Field(description="Finalized description to generate metrics from")
    conversation_history: list[ConversationMessage] = Field(
        default_factory=list,
        description="Full conversation for context"
    )


# --- Eval CRUD schemas ---

class CreateEvalRequest(BaseModel):
    """Request body for POST /api/evals — creates a new eval from frontend evalConfig."""
    eval_config: dict = Field(description="Full evalConfig object from the frontend")


class UpdateEvalRequest(BaseModel):
    """Request body for PATCH /api/evals/{id}."""
    updates: dict = Field(description="Partial updates to apply to the eval config")


class RunEvalRequest(BaseModel):
    """Request body for POST /api/evals/{id}/run."""
    trigger: str = Field(default="manual", description="What triggered this run")


class ValidateMetricsRequest(BaseModel):
    """Request body for POST /api/validate-metrics (dry-run)."""
    metrics: list[dict] = Field(description="Proposed metrics to validate")
    sample_data: list[dict] = Field(description="Sample data to validate against")
    description: str = Field(default="", description="Eval description for context")


class MetricFeedback(BaseModel):
    field: str
    status: str  # good, adjust, problematic
    suggestion: str
    suggested_baseline: Optional[int] = None
    suggested_target: Optional[int] = None


class ValidateMetricsResponse(BaseModel):
    overall_assessment: str  # good, needs_adjustment, problematic, error
    message: str
    metric_feedback: list[MetricFeedback] = Field(default_factory=list)


class EvalRunResponse(BaseModel):
    """Response for an eval run."""
    id: str
    eval_id: str
    status: str
    primary_score: Optional[float] = None
    pass_rate: Optional[float] = None
    metrics: Optional[Dict[str, float]] = None
    num_examples: Optional[int] = None
    num_passed: Optional[int] = None
    num_failed: Optional[int] = None
    passed_baseline: Optional[bool] = None
    passed_target: Optional[bool] = None
    duration_ms: Optional[int] = None
    error_message: Optional[str] = None
    created_at: Optional[str] = None
    completed_at: Optional[str] = None
    detailed_results: Optional[List[Dict[str, Any]]] = None
    failures: Optional[List[Dict[str, Any]]] = None
