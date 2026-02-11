"""
FastAPI server for the MFT Eval Platform.

Provides endpoints for the guided eval builder chat interface,
proxying LLM calls to Claude Sonnet 4.5 via Meta's Llama API.
"""

import logging

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from .config import API_HOST, API_PORT, CORS_ORIGINS, LLM_MODEL, LLM_PROVIDER
from .llm import (
    generate_metrics,
    handle_chat,
    handle_initial_description,
    handle_refine_followup,
)
from .schema import (
    ChatRequest,
    ChatResponse,
    GenerateMetricsRequest,
    MetricsResponse,
    Phase,
    RefinedPromptResponse,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="MFT Eval Platform API",
    description="Backend for the guided eval builder — proxies LLM calls to Claude via Llama API",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
async def health():
    """Health check endpoint."""
    return {
        "status": "ok",
        "provider": LLM_PROVIDER,
        "model": LLM_MODEL,
    }


@app.post("/api/chat", response_model=None)
async def chat(request: ChatRequest):
    """
    Main chat endpoint. Routes to the appropriate LLM handler based on the current phase.

    - OBJECTIVE phase: Handles initial description → returns refined prompt + clarifying questions
    - REFINE phase: Handles follow-up context → returns updated refined prompt
    - METRICS/AUTOMATION/REVIEW phases: General chat for config adjustments
    """
    try:
        if request.phase == Phase.OBJECTIVE:
            result = await handle_initial_description(request)
            return {
                "type": "refine",
                "data": result.dict(),
            }

        elif request.phase == Phase.REFINE:
            result = await handle_refine_followup(request)
            return {
                "type": "chat",
                "data": result.dict(),
            }

        else:
            result = await handle_chat(request)
            return {
                "type": "chat",
                "data": result.dict(),
            }

    except Exception as e:
        logger.error(f"Chat error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"LLM request failed: {str(e)}")


@app.post("/api/generate-metrics", response_model=MetricsResponse)
async def gen_metrics(request: GenerateMetricsRequest):
    """
    Generate metrics from a finalized description.
    Called when the user confirms their refined prompt.
    """
    try:
        return await generate_metrics(request)
    except Exception as e:
        logger.error(f"Generate metrics error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"LLM request failed: {str(e)}")


@app.post("/api/update-system-prompt")
async def update_system_prompt(body: dict):
    """
    Hot-reload the system prompt without restarting the server.
    Useful for iterating on the prompt during development.
    """
    from . import config

    new_prompt = body.get("system_prompt", "")
    if not new_prompt:
        raise HTTPException(status_code=400, detail="system_prompt is required")
    config.SYSTEM_PROMPT = new_prompt
    logger.info(f"System prompt updated ({len(new_prompt)} chars)")
    return {"status": "ok", "prompt_length": len(new_prompt)}


def start():
    """Entry point for running the server."""
    import uvicorn

    logger.info(f"Starting MFT Eval API on {API_HOST}:{API_PORT}")
    logger.info(f"LLM Provider: {LLM_PROVIDER} | Model: {LLM_MODEL}")
    uvicorn.run(
        "api.server:app",
        host=API_HOST,
        port=API_PORT,
        reload=True,
    )


if __name__ == "__main__":
    start()
