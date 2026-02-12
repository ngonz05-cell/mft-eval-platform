"""
LLM client for the MFT Eval Platform.

Supports four providers:
  - "llama_native": Native Llama API (Llama 4 Maverick) — OpenAI-compatible chat/completions
  - "openai": OpenAI API (GPT-4o) — standard chat/completions
  - "llama_api": Llama API Anthropic passthrough (Claude Sonnet 4.5) — Anthropic Messages API
  - "anthropic_direct": Direct Anthropic API (Claude Sonnet 4.5) — Anthropic Messages API

The native Llama API and OpenAI use OpenAI's chat/completions format.
The passthrough and direct Anthropic use the Anthropic Messages API format.
"""
import json
import logging
from typing import Optional

import httpx

from .config import (
    LLAMA_API_ANTHROPIC_BASE_URL,
    LLAMA_API_NATIVE_BASE_URL,
    ANTHROPIC_DIRECT_BASE_URL,
    ANTHROPIC_API_KEY,
    LLAMA_API_KEY,
    OPENAI_API_BASE_URL,
    OPENAI_API_KEY,
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


# --- Provider-specific API calls ---

async def _call_anthropic(system: str, messages: list[dict]) -> str:
    """Call the Anthropic Messages API (via Llama API passthrough or direct)."""
    if LLM_PROVIDER == "anthropic_direct":
        base_url = ANTHROPIC_DIRECT_BASE_URL
    else:
        base_url = LLAMA_API_ANTHROPIC_BASE_URL

    url = f"{base_url}/v1/messages"

    headers = {
        "content-type": "application/json",
        "anthropic-version": "2023-06-01",
    }
    if LLM_PROVIDER == "anthropic_direct" and ANTHROPIC_API_KEY:
        headers["x-api-key"] = ANTHROPIC_API_KEY
    elif LLM_PROVIDER == "llama_api" and LLAMA_API_KEY:
        headers["x-api-key"] = LLAMA_API_KEY

    payload = {
        "model": LLM_MODEL,
        "max_tokens": MAX_TOKENS,
        "system": system,
        "messages": messages,
        "stream": False,
    }

    logger.info(f"Calling {LLM_PROVIDER} ({LLM_MODEL}) at {url}")

    async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
        response = await client.post(url, json=payload, headers=headers)
        response.raise_for_status()
        data = response.json()

    content_blocks = data.get("content", [])
    text_parts = [block["text"] for block in content_blocks if block.get("type") == "text"]
    return "".join(text_parts)


async def _call_llama_native(system: str, messages: list[dict]) -> str:
    """Call the native Llama API (OpenAI-compatible chat/completions format)."""
    url = f"{LLAMA_API_NATIVE_BASE_URL}/v1/chat/completions"

    headers = {
        "content-type": "application/json",
        "Authorization": f"Bearer {LLAMA_API_KEY}",
    }

    # Convert to OpenAI format: system message + user/assistant messages
    oai_messages = [{"role": "system", "content": system}]
    for msg in messages:
        oai_messages.append({
            "role": msg.get("role", "user"),
            "content": msg.get("content", ""),
        })

    payload = {
        "model": LLM_MODEL,
        "max_tokens": MAX_TOKENS,
        "messages": oai_messages,
        "stream": False,
    }

    logger.info(f"Calling llama_native ({LLM_MODEL}) at {url}")

    async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
        response = await client.post(url, json=payload, headers=headers)
        response.raise_for_status()
        data = response.json()

    # Native Llama API returns OpenAI-compatible format
    # Response shape: {"completion_message": {"content": {"text": "..."}}} or
    #                 {"choices": [{"message": {"content": "..."}}]}
    completion = data.get("completion_message")
    if completion:
        content = completion.get("content", {})
        if isinstance(content, dict):
            return content.get("text", "")
        return str(content)

    choices = data.get("choices", [])
    if choices:
        return choices[0].get("message", {}).get("content", "")

    return ""


async def _call_openai(system: str, messages: list[dict]) -> str:
    """Call the OpenAI API (GPT-4o, o1, etc.) — standard chat/completions format."""
    url = f"{OPENAI_API_BASE_URL}/v1/chat/completions"

    headers = {
        "content-type": "application/json",
        "Authorization": f"Bearer {OPENAI_API_KEY}",
    }

    oai_messages = [{"role": "system", "content": system}]
    for msg in messages:
        oai_messages.append({
            "role": msg.get("role", "user"),
            "content": msg.get("content", ""),
        })

    payload = {
        "model": LLM_MODEL,
        "max_tokens": MAX_TOKENS,
        "messages": oai_messages,
        "stream": False,
    }

    logger.info(f"Calling openai ({LLM_MODEL}) at {url}")

    async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
        response = await client.post(url, json=payload, headers=headers)
        response.raise_for_status()
        data = response.json()

    choices = data.get("choices", [])
    if choices:
        return choices[0].get("message", {}).get("content", "")

    return ""


async def _call_llm(system: str, messages: list[dict]) -> str:
    """Route to the correct provider."""
    if LLM_PROVIDER == "llama_native":
        return await _call_llama_native(system, messages)
    elif LLM_PROVIDER == "openai":
        return await _call_openai(system, messages)
    else:
        return await _call_anthropic(system, messages)


# --- Shared helpers ---

def _build_messages(
    system_prompt: str,
    conversation_history: list[dict],
    user_message: str,
    json_schema_instruction: str,
) -> tuple[str, list[dict]]:
    """Build the system prompt and messages array."""
    full_system = f"{system_prompt}\n\n{json_schema_instruction}"

    messages = []
    for msg in conversation_history:
        messages.append({
            "role": msg.get("role", "user"),
            "content": msg.get("content", ""),
        })
    messages.append({"role": "user", "content": user_message})

    return full_system, messages


def _parse_json_response(raw_text: str) -> dict:
    """Extract JSON from the LLM response, handling markdown code fences and common LLM errors."""
    text = raw_text.strip()
    logger.debug(f"Raw LLM response (first 500 chars): {text[:500]}")

    # Strip markdown code fences if present
    if text.startswith("```"):
        lines = text.split("\n")
        lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()

    # Try direct parse first
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Sometimes LLMs wrap JSON in extra text. Try to find the outermost JSON object.
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        candidate = text[start:end + 1]
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            pass

    # Try fixing common issues: trailing commas before closing braces/brackets
    import re
    cleaned = re.sub(r',\s*([}\]])', r'\1', text)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    # Last resort: extract JSON object from any position
    if start != -1 and end != -1:
        candidate = text[start:end + 1]
        cleaned = re.sub(r',\s*([}\]])', r'\1', candidate)
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            pass

    # Log the problematic response for debugging
    logger.error(f"Failed to parse JSON from LLM response:\n{text[:2000]}")
    raise ValueError(f"Could not parse JSON from LLM response")


# --- Public API Functions ---

async def handle_initial_description(request: ChatRequest) -> RefinedPromptResponse:
    """
    Handle the user's initial product description.
    Returns a refined prompt + clarifying questions.
    """
    schema_instruction = """You must respond with ONLY valid JSON matching this exact schema (no markdown, no extra text):

{
  "message": "Your conversational response to show in the chat. Acknowledge what the user described, summarize what you understood, and tell the user you've drafted a refined description they can review and edit. Tell them you'll have a few follow-up questions once they're ready.",
  "refined_prompt": "An improved, more specific version of the user's description that will yield better eval metrics. Should be a complete, self-contained description.",
  "clarifying_questions": [],
  "is_detailed_enough": false
}

Rules:
- If the description is already very detailed (mentions inputs, outputs, failure modes, and success criteria), set is_detailed_enough to true and still provide a refined_prompt
- Do NOT ask clarifying questions in this phase — leave clarifying_questions as an empty array. Questions come in the next phase (REFINE).
- The refined_prompt should be a complete, self-contained description (not a diff) that adds specificity about inputs, outputs, success criteria, and failure modes
- In your message, acknowledge what the user said, summarize your understanding, and let them know you've drafted a refined version for their review"""

    system, messages = _build_messages(
        SYSTEM_PROMPT,
        [m.dict() for m in request.conversation_history],
        request.message,
        schema_instruction,
    )

    raw = await _call_llm(system, messages)
    data = _parse_json_response(raw)
    return RefinedPromptResponse(**data)


async def handle_refine_followup(request: ChatRequest) -> ChatResponse:
    """
    Handle follow-up messages during the REFINE phase.
    User may be answering clarifying questions or providing more context.
    """
    current_prompt = request.eval_config.get("refinedPrompt", "") if request.eval_config else ""

    schema_instruction = f"""The user is in the REFINE phase. They may be answering your clarifying questions, providing additional context, or asking you to adjust the refined description.
The current refined description is:
"{current_prompt}"

You must respond with ONLY valid JSON matching this exact schema:

{{
  "message": "Your conversational response. If you still have clarifying questions (up to 3), ask them here. If you're satisfied, tell the user the description looks good and they can proceed.",
  "refined_prompt": "The updated, improved description incorporating any new information from the user",
  "config_updates": null,
  "metrics": null
}}

Rules:
- Incorporate the user's new information into the refined_prompt
- The refined_prompt should be a complete, self-contained description
- If there are still important gaps (inputs, outputs, failure modes, success criteria, data types), ask up to 3 clarifying questions in your message
- If the description is now comprehensive enough, tell the user it looks good and they can click the button to generate metrics
- In your message, acknowledge what they said and note how it improves the eval description"""

    system, messages = _build_messages(
        SYSTEM_PROMPT,
        [m.dict() for m in request.conversation_history],
        request.message,
        schema_instruction,
    )

    raw = await _call_llm(system, messages)
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

You must respond with ONLY valid JSON matching this exact schema (no markdown, no extra text):

{{
  "message": "Your chat message MUST include a per-metric breakdown. Use this exact format for each metric:\n\n**Metric Name → Method (baseline% → target%)**\n2-3 sentences: why this metric, why this method, why these thresholds.\n\nEnd with a 2-3 sentence hill-climbing summary explaining how the metrics work together.",
  "eval_name": "snake_case_eval_name",
  "metrics": [
    {{
      "field": "Metric Name",
      "measurement": ["measurement_method_id"],
      "description": "One-line description",
      "baseline": 80,
      "target": 95,
      "rationale": "One sentence summary"
    }}
  ]
}}

Valid measurement method IDs: exact_match_ratio, simple_pass_fail, weighted_composite, contains_check, numeric_tolerance, fuzzy_string_match, classification_f1, llm_judge, field_f1, task_success_rate, tool_correctness

Rules:
- Suggest 2-5 metrics
- CRITICAL: The "message" field MUST contain a per-metric rationale breakdown. This is what the user sees in the chat.
- The "rationale" field in each metric should be ONE short sentence (the full explanation goes in "message")
- Baseline = minimum acceptable quality, Target = ambitious goal
- eval_name: descriptive, snake_case, ending with _eval
- Keep total response under 3000 tokens"""

    system, messages = _build_messages(
        SYSTEM_PROMPT,
        [m.dict() for m in request.conversation_history],
        request.description,
        schema_instruction,
    )

    raw = await _call_llm(system, messages)
    data = _parse_json_response(raw)
    return MetricsResponse(**data)


async def handle_chat(request: ChatRequest) -> ChatResponse:
    """
    Handle general chat messages (metrics editing, automation, review phases).
    """
    phase_context = {
        Phase.METRICS: "The user is reviewing suggested metrics and may want to adjust them.",
        Phase.SAMPLE_DATA: "The user is configuring test data for their eval. Help them structure inputs and expected outputs.",
        Phase.CONNECT: "The user is configuring their model endpoint and production log monitoring.",
        Phase.MANAGE: "The user is configuring automation settings (schedule, alerts, ownership).",
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

    raw = await _call_llm(system, messages)
    data = _parse_json_response(raw)
    return ChatResponse(**data)
