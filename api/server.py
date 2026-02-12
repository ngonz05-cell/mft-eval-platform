"""
FastAPI server for the MFT Eval Platform.

Provides endpoints for:
  - Guided eval builder chat interface (LLM proxy)
  - Eval CRUD (create, read, update, delete)
  - Eval run execution and results
  - Dry-run metric validation
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
    CreateEvalRequest,
    GenerateMetricsRequest,
    MetricsResponse,
    Phase,
    RefinedPromptResponse,
    RunEvalRequest,
    UpdateEvalRequest,
    ValidateMetricsRequest,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="MFT Eval Platform API",
    description="Backend for the guided eval builder — proxies LLM calls to Claude via Llama API",
    version="0.2.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─── Startup: initialize database ────────────────────────────────────────────

@app.on_event("startup")
async def startup_event():
    from mft_evals.storage import init_db
    init_db()
    logger.info("Database initialized")


# ─── Health Check ─────────────────────────────────────────────────────────────

@app.get("/api/health")
async def health():
    """Health check endpoint."""
    return {
        "status": "ok",
        "provider": LLM_PROVIDER,
        "model": LLM_MODEL,
    }


# ─── Chat / LLM Endpoints ────────────────────────────────────────────────────

@app.post("/api/chat", response_model=None)
async def chat(request: ChatRequest):
    """
    Main chat endpoint. Routes to the appropriate LLM handler based on the current phase.
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
    """Generate metrics from a finalized description."""
    try:
        return await generate_metrics(request)
    except Exception as e:
        logger.error(f"Generate metrics error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"LLM request failed: {str(e)}")


@app.post("/api/update-system-prompt")
async def update_system_prompt(body: dict):
    """Hot-reload the system prompt without restarting the server."""
    from . import config

    new_prompt = body.get("system_prompt", "")
    if not new_prompt:
        raise HTTPException(status_code=400, detail="system_prompt is required")
    config.SYSTEM_PROMPT = new_prompt
    logger.info(f"System prompt updated ({len(new_prompt)} chars)")
    return {"status": "ok", "prompt_length": len(new_prompt)}


# ─── Eval CRUD Endpoints ─────────────────────────────────────────────────────

@app.post("/api/evals")
async def create_eval(request: CreateEvalRequest):
    """Create a new eval from the frontend evalConfig."""
    try:
        from mft_evals.storage import create_eval as db_create
        eval_record = db_create(request.eval_config)
        return {"status": "ok", "eval": eval_record}
    except Exception as e:
        logger.error(f"Create eval error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/evals")
async def list_evals(team: str = None, status: str = None, limit: int = 50, offset: int = 0):
    """List all evals with optional filtering."""
    try:
        from mft_evals.storage import list_evals as db_list
        evals = db_list(team=team, status=status, limit=limit, offset=offset)
        return {"evals": evals, "count": len(evals)}
    except Exception as e:
        logger.error(f"List evals error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/evals/{eval_id}")
async def get_eval(eval_id: str):
    """Get a single eval by ID."""
    from mft_evals.storage import get_eval as db_get
    eval_record = db_get(eval_id)
    if not eval_record:
        raise HTTPException(status_code=404, detail=f"Eval not found: {eval_id}")
    return {"eval": eval_record}


@app.patch("/api/evals/{eval_id}")
async def update_eval(eval_id: str, request: UpdateEvalRequest):
    """Update an eval's configuration."""
    try:
        from mft_evals.storage import update_eval as db_update
        updated = db_update(eval_id, request.updates)
        if not updated:
            raise HTTPException(status_code=404, detail=f"Eval not found: {eval_id}")
        return {"status": "ok", "eval": updated}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Update eval error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/evals/{eval_id}")
async def delete_eval(eval_id: str):
    """Delete an eval and all its runs."""
    from mft_evals.storage import delete_eval as db_delete
    deleted = db_delete(eval_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Eval not found: {eval_id}")
    return {"status": "ok", "deleted": eval_id}


# ─── Eval Run Endpoints ──────────────────────────────────────────────────────

@app.post("/api/evals/{eval_id}/run")
async def run_eval(eval_id: str, request: RunEvalRequest = None):
    """
    Trigger an eval run. Executes the eval against the configured
    dataset and model, scores results, and stores them.
    """
    try:
        from mft_evals.eval_service import execute_eval_run
        trigger = request.trigger if request else "manual"
        result = await execute_eval_run(eval_id, trigger=trigger)
        return {"status": "ok", "run": result}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Run eval error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Eval run failed: {str(e)}")


@app.get("/api/evals/{eval_id}/runs")
async def list_runs(eval_id: str, status: str = None, limit: int = 20, offset: int = 0):
    """List all runs for an eval."""
    try:
        from mft_evals.storage import list_runs as db_list_runs
        runs = db_list_runs(eval_id, status=status, limit=limit, offset=offset)
        return {"runs": runs, "count": len(runs)}
    except Exception as e:
        logger.error(f"List runs error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/runs/{run_id}")
async def get_run(run_id: str):
    """Get a single run by ID with full results."""
    from mft_evals.storage import get_run as db_get_run
    run = db_get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail=f"Run not found: {run_id}")
    return {"run": run}


@app.get("/api/runs/{run_id}/results")
async def get_run_results(run_id: str):
    """Get detailed results for a run (per-example scores, failures)."""
    from mft_evals.storage import get_run as db_get_run
    run = db_get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail=f"Run not found: {run_id}")
    return {
        "run_id": run_id,
        "status": run.get("status"),
        "primary_score": run.get("primary_score"),
        "pass_rate": run.get("pass_rate"),
        "metrics": run.get("metrics"),
        "num_examples": run.get("num_examples"),
        "num_passed": run.get("num_passed"),
        "num_failed": run.get("num_failed"),
        "passed_baseline": run.get("passedBaseline"),
        "passed_target": run.get("passedTarget"),
        "detailed_results": run.get("detailed_results", []),
        "failures": run.get("failures", []),
        "duration_ms": run.get("duration_ms"),
        "error_message": run.get("error_message"),
    }


# ─── Dry-Run / Validate Metrics ──────────────────────────────────────────────

@app.post("/api/validate-metrics")
async def validate_metrics(request: ValidateMetricsRequest):
    """
    Dry-run: validate proposed metrics against sample data.
    Uses the LLM to assess whether metrics and thresholds are realistic.
    """
    try:
        from mft_evals.eval_service import validate_metrics_against_data
        result = await validate_metrics_against_data(
            metrics=request.metrics,
            sample_data=request.sample_data,
            description=request.description,
        )
        return result
    except Exception as e:
        logger.error(f"Validate metrics error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Validation failed: {str(e)}")


# ─── Production Log Source Endpoints ──────────────────────────────────────────

@app.post("/api/evals/{eval_id}/test-connection")
async def test_log_connection(eval_id: str):
    """
    Test connectivity to the eval's configured production log source.
    Returns connection status, message, and a sample row if available.
    """
    try:
        from mft_evals.storage import get_eval as db_get
        from mft_evals.integrations.log_sources import config_from_eval_data, create_log_source

        eval_data = db_get(eval_id)
        if not eval_data:
            raise HTTPException(status_code=404, detail=f"Eval not found: {eval_id}")

        log_config = config_from_eval_data(eval_data)
        if not log_config:
            return {
                "connected": False,
                "message": "Production logging not enabled for this eval. Configure it in the CONNECT phase.",
                "sample_row": None,
            }

        source = create_log_source(log_config)
        result = await source.test_connection()
        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Test connection error: {e}", exc_info=True)
        return {"connected": False, "message": f"Connection test failed: {str(e)}", "sample_row": None}


@app.post("/api/evals/{eval_id}/ingest")
async def ingest_production_logs(eval_id: str, trigger_run: bool = False, max_rows: int = 500):
    """
    Ingest production logs for an eval. Fetches recent logs from the
    configured source, converts to test cases, and optionally triggers
    an eval run.
    """
    try:
        from mft_evals.integrations.log_worker import LogIngestionWorker

        if not hasattr(app.state, "log_worker"):
            app.state.log_worker = LogIngestionWorker()

        result = await app.state.log_worker.ingest_eval(
            eval_id=eval_id,
            trigger_run=trigger_run,
            max_rows=max_rows,
        )
        return {"status": result.status, "result": result.to_dict()}

    except Exception as e:
        logger.error(f"Ingest error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Ingestion failed: {str(e)}")


@app.get("/api/evals/{eval_id}/log-schema")
async def get_log_schema(eval_id: str):
    """
    Get the schema of the eval's configured production log source.
    Returns available columns/fields for mapping.
    """
    try:
        from mft_evals.storage import get_eval as db_get
        from mft_evals.integrations.log_sources import config_from_eval_data, create_log_source

        eval_data = db_get(eval_id)
        if not eval_data:
            raise HTTPException(status_code=404, detail=f"Eval not found: {eval_id}")

        log_config = config_from_eval_data(eval_data)
        if not log_config:
            return {"schema": [], "message": "Production logging not configured"}

        source = create_log_source(log_config)
        schema = await source.get_schema()
        return {"schema": schema}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Schema fetch error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Schema fetch failed: {str(e)}")


# ─── Server Entry Point ──────────────────────────────────────────────────────

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
