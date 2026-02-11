"""
LLM client for Claude Sonnet 4.5 via Meta's Llama API Anthropic passthrough.

Supports two providers:
  - "llama_api": Meta internal Llama API proxy (for corp network / internal deployment)
  - "anthropic_direct": Direct Anthropic API (for local dev with API key)

Both use the Anthropic Messages API format. The Llama API passthrough
accepts the same request format and proxies to Anthropic.
"""
import json
import logging
from typing import Optional

import httpx

from .config import (
    LLAMA_API_ANTHROPIC_BASE_URL,
    ANTHROPIC_DIRECT_BASE_URL,
    ANTHROPIC_API_KEY,
    LLAMA_API_KEY,
    LLM_MODEL,
    LLM_PROVIDER,
    SYSTEM_PROMPT,
    MAX_TOKENS,
    REQUEST_TIMEOUT,
)
from .schema import (
    ChatRequest,
    GenerateMetricsRequest,
    RefinedPromptResponse,
    MetricsResponse,
    ChatResponse,
    MetricSuggestion,
    Phase,
)

logger = logging.getLogger(__name__)


def _get_base_url() -> str:
    if LLM_PROVIDER == "anthropic_direct":
        return ANTHROPIC_DIRECT_BASE_URL
    return LLAMA_API_ANTHROPIC_BASE_URL


def _get_headers() -> dict:
    headers = {
        "content-type": "application/json",
        "anthropic-version": "2023-06-01",
    }
    if LLM_PROVIDER == "anthropic_direct" and ANTHROPIC_API_KEY:
        headers["x-api-key"] = ANTHROPIC_API_KEY
    elif LLM_PROVIDER == "llama_api" and LLAMA_API_KEY:
        headers["x-api-key"] = LLAMA_API_KEY
    return headers


def _build_messages(
    system_prompt: str,
    conversation_history: list[dict],
    user_message: str,
    json_schema_instruction: str,
) -> tuple[str, list[dict]]:
    """Build the system prompt and messages array for the Anthropic API."""
    full_system = f"{system_prompt}\n\n{json_schema_instruction}"

    messages = []
    for msg in conversation_history:
        messages.append({
            "role": msg.get("role", "user"),
            "content": msg.get("content", ""),
        })
    messages.append({"role": "user", "content": user_message})

    return full_system, messages


async def _call_anthropic(
    system: str,
    messages: list[dict],
) -> str:
    """Make a request to the Anthropic Messages API (via Llama API or direct)."""
    base_url = _get_base_url()
    url = f"{base_url}/v1/messages"

    payload = {
        "model": LLM_MODEL,
        "max_tokens": MAX_TOKENS,
        "system": system,
        "messages": messages,
        # Streaming not supported via Llama API passthrough for 3P models
        "stream": False,
    }

    headers = _get_headers()

    logger.info(f"Calling {LLM_PROVIDER} ({LLM_MODEL}) at {url}")

    async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
        response = await client.post(url, json=payload, headers=headers)
        response.raise_for_status()
        data = response.json()

    # Extract text from the response
    content_blocks = data.get("content", [])
    text_parts = [block["text"] for block in content_blocks if block.get("type") == "text"]
    return "".join(text_parts)


def _parse_json_response(raw_text: str) -> dict:
    """Extract JSON from the LLM response, handling markdown code fences."""
    text = raw_text.strip()

    # Strip markdown code fences if present
    if text.startswith("```"):
        lines = text.split("\n")
        # Remove first line (```json or ```) and last line (```)
        lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()

    return json.loads(text)


# --- Public API Functions ---

async def handle_initial_description(request: ChatRequest) -> RefinedPromptResponse:
    """
    Handle the user's initial product description.
    Returns a refined prompt + clarifying questions.
    """
    schema_instruction = """You must respond with ONLY valid JSON matching this exact schema (no markdown, no extra text):

{
  "message": "Your conversational response to show in the chat",
  "refined_prompt": "An improved, more specific version of the user's description that will yield better eval metrics",
  "clarifying_questions": [
    {"question": "A clarifying question", "why": "Why this matters for eval design"}
  ],
  "is_detailed_enough": false
}

Rules:
- If the description is already very detailed (mentions inputs, outputs, failure modes, and success criteria), set is_detailed_enough to true and still provide a refined_prompt
- Ask 1-3 clarifying questions focused on what's missing for good eval design (inputs, outputs, failure modes, success criteria, data types)
- The refined_prompt should be a complete, self-contained description (not a diff)
- In your message, acknowledge what the user said, then explain what you're asking and why"""

    system, messages = _build_messages(
        SYSTEM_PROMPT,
        [m.dict() for m in request.conversation_history],
        request.message,
        schema_instruction,
    )

    raw = await _call_anthropic(system, messages)
    data = _parse_json_response(raw)
    return RefinedPromptResponse(**data)


async def handle_refine_followup(request: ChatRequest) -> ChatResponse:
    """
    Handle follow-up messages during the REFINE phase.
    User may be answering clarifying questions or providing more context.
    """
    current_prompt = request.eval_config.get("refinedPrompt", "") if request.eval_config else ""

    schema_instruction = f"""The user is answering clarifying questions or providing additional context about their product.
The current refined description is:
"{current_prompt}"

You must respond with ONLY valid JSON matching this exact schema:

{{
  "message": "Your conversational response acknowledging their answers",
  "refined_prompt": "The updated, improved description incorporating the new information",
  "config_updates": null,
  "metrics": null
}}

Rules:
- Incorporate the user's new information into the refined_prompt
- The refined_prompt should be a complete, self-contained description
- In your message, acknowledge what they said and note how it improves the eval description"""

    system, messages = _build_messages(
        SYSTEM_PROMPT,
        [m.dict() for m in request.conversation_history],
        request.message,
        schema_instruction,
    )

    raw = await _call_anthropic(system, messages)
    data = _parse_json_response(raw)
    return ChatResponse(**data)


async def generate_metrics(request: GenerateMetricsRequest) -> MetricsResponse:
    """
    Generate metrics, measurement methods, thresholds, and rationale
    from a finalized description.
    """
    schema_instruction = f"""Based on the following product description, suggest evaluation metrics.

PRODUCT DESCRIPTION:
"{request.description}"

You must respond with ONLY valid JSON matching this exact schema:

{{
  "message": "Brief conversational message about the metrics you suggested",
  "eval_name": "snake_case_eval_name",
  "metrics": [
    {{
      "field": "Metric Name",
      "measurement": ["measurement_method_id"],
      "description": "One-line description",
      "baseline": 80,
      "target": 95,
      "rationale": "2-3 sentences explaining WHY this metric, method, and thresholds were chosen"
    }}
  ]
}}

Valid measurement method IDs: exact_match_ratio, simple_pass_fail, weighted_composite, contains_check, numeric_tolerance, fuzzy_string_match, classification_f1, llm_judge, field_f1, task_success_rate, tool_correctness

Rules:
- Suggest 2-5 metrics that are most relevant to the described product
- Each metric should use the most appropriate measurement method for its data type
- Baseline thresholds should be the minimum acceptable quality (realistic starting point)
- Target thresholds should be the goal (ambitious but achievable)
- Rationale should explain the reasoning to educate the user — WHY this method, WHY these numbers
- eval_name should be descriptive, snake_case, and end with _eval"""

    system, messages = _build_messages(
        SYSTEM_PROMPT,
        [m.dict() for m in request.conversation_history],
        request.description,
        schema_instruction,
    )

    raw = await _call_anthropic(system, messages)
    data = _parse_json_response(raw)
    return MetricsResponse(**data)


async def handle_chat(request: ChatRequest) -> ChatResponse:
    """
    Handle general chat messages (metrics editing, automation, review phases).
    """
    phase_context = {
        Phase.METRICS: "The user is reviewing suggested metrics and may want to adjust them.",
        Phase.AUTOMATION: "The user is configuring automation settings (schedule, alerts, ownership).",
        Phase.REVIEW: "The user is reviewing the final eval draft before creating it.",
    }

    context = phase_context.get(request.phase, "The user needs help with their eval configuration.")
    config_json = json.dumps(request.eval_config, indent=2) if request.eval_config else "{}"

    schema_instruction = f"""{context}

Current eval configuration:
{config_json}

You must respond with ONLY valid JSON matching this exact schema:

{{
  "message": "Your conversational response",
  "config_updates": {{"key": "value"}},
  "refined_prompt": null,
  "metrics": null
}}

Rules:
- If the user asks to change specific config values, include them in config_updates
- If the user asks to update metrics, include the full updated metrics array in the metrics field
- If no config changes are needed, set config_updates to null
- Be helpful and concise"""

    system, messages = _build_messages(
        SYSTEM_PROMPT,
        [m.dict() for m in request.conversation_history],
        request.message,
        schema_instruction,
    )

    raw = await _call_anthropic(system, messages)
    data = _parse_json_response(raw)
    return ChatResponse(**data)
