/**
 * API client for the MFT Eval Platform backend.
 *
 * Connects to the FastAPI server which proxies LLM calls
 * and manages eval CRUD, runs, and results.
 */

const API_BASE = process.env.REACT_APP_API_URL || 'http://localhost:8000';

// ─── Chat / LLM Endpoints ────────────────────────────────────────────────────

/**
 * Send a chat message to the backend.
 * Routes to the appropriate LLM handler based on the current phase.
 */
export async function sendChatMessage(phase, message, conversationHistory, evalConfig) {
  const response = await fetch(`${API_BASE}/api/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      phase,
      message,
      conversation_history: conversationHistory.map(m => ({
        role: m.role,
        content: m.content || m.text,
      })),
      eval_config: evalConfig,
    }),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Unknown error' }));
    throw new Error(error.detail || `API error: ${response.status}`);
  }

  return response.json();
}

/**
 * Generate metrics from a finalized description.
 */
export async function generateMetrics(description, conversationHistory) {
  const response = await fetch(`${API_BASE}/api/generate-metrics`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      description,
      conversation_history: conversationHistory.map(m => ({
        role: m.role,
        content: m.content || m.text,
      })),
    }),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Unknown error' }));
    throw new Error(error.detail || `API error: ${response.status}`);
  }

  return response.json();
}

/**
 * Check if the backend API is available.
 */
export async function checkHealth() {
  const response = await fetch(`${API_BASE}/api/health`);
  if (!response.ok) throw new Error('API not available');
  return response.json();
}

/**
 * Hot-update the system prompt without restarting the server.
 */
export async function updateSystemPrompt(systemPrompt) {
  const response = await fetch(`${API_BASE}/api/update-system-prompt`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ system_prompt: systemPrompt }),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Unknown error' }));
    throw new Error(error.detail || `API error: ${response.status}`);
  }

  return response.json();
}

// ─── Eval CRUD Endpoints ─────────────────────────────────────────────────────

/**
 * Create a new eval from the frontend evalConfig.
 * @param {Object} evalConfig - Full evalConfig object
 * @returns {Promise<Object>} - { status, eval: {...} }
 */
export async function createEval(evalConfig) {
  const response = await fetch(`${API_BASE}/api/evals`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ eval_config: evalConfig }),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Unknown error' }));
    throw new Error(error.detail || `API error: ${response.status}`);
  }

  return response.json();
}

/**
 * List all evals with optional filtering.
 * @param {Object} opts - { team, status, limit, offset }
 * @returns {Promise<Object>} - { evals: [...], count }
 */
export async function listEvals({ team, status, limit = 50, offset = 0 } = {}) {
  const params = new URLSearchParams();
  if (team) params.set('team', team);
  if (status) params.set('status', status);
  params.set('limit', limit);
  params.set('offset', offset);

  const response = await fetch(`${API_BASE}/api/evals?${params}`);

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Unknown error' }));
    throw new Error(error.detail || `API error: ${response.status}`);
  }

  return response.json();
}

/**
 * Get a single eval by ID.
 * @param {string} evalId
 * @returns {Promise<Object>} - { eval: {...} }
 */
export async function getEval(evalId) {
  const response = await fetch(`${API_BASE}/api/evals/${evalId}`);

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Unknown error' }));
    throw new Error(error.detail || `API error: ${response.status}`);
  }

  return response.json();
}

/**
 * Update an eval's configuration.
 * @param {string} evalId
 * @param {Object} updates - Partial updates
 * @returns {Promise<Object>} - { status, eval: {...} }
 */
export async function updateEval(evalId, updates) {
  const response = await fetch(`${API_BASE}/api/evals/${evalId}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ updates }),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Unknown error' }));
    throw new Error(error.detail || `API error: ${response.status}`);
  }

  return response.json();
}

/**
 * Delete an eval and all its runs.
 * @param {string} evalId
 * @returns {Promise<Object>} - { status, deleted }
 */
export async function deleteEval(evalId) {
  const response = await fetch(`${API_BASE}/api/evals/${evalId}`, {
    method: 'DELETE',
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Unknown error' }));
    throw new Error(error.detail || `API error: ${response.status}`);
  }

  return response.json();
}

// ─── Eval Run Endpoints ──────────────────────────────────────────────────────

/**
 * Trigger an eval run.
 * @param {string} evalId
 * @param {string} trigger - What triggered this run (manual, ci, scheduled)
 * @returns {Promise<Object>} - { status, run: {...} }
 */
export async function runEval(evalId, trigger = 'manual') {
  const response = await fetch(`${API_BASE}/api/evals/${evalId}/run`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ trigger }),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Unknown error' }));
    throw new Error(error.detail || `API error: ${response.status}`);
  }

  return response.json();
}

/**
 * List all runs for an eval.
 * @param {string} evalId
 * @param {Object} opts - { status, limit, offset }
 * @returns {Promise<Object>} - { runs: [...], count }
 */
export async function listRuns(evalId, { status, limit = 20, offset = 0 } = {}) {
  const params = new URLSearchParams();
  if (status) params.set('status', status);
  params.set('limit', limit);
  params.set('offset', offset);

  const response = await fetch(`${API_BASE}/api/evals/${evalId}/runs?${params}`);

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Unknown error' }));
    throw new Error(error.detail || `API error: ${response.status}`);
  }

  return response.json();
}

/**
 * Get a single run with full results.
 * @param {string} runId
 * @returns {Promise<Object>} - { run: {...} }
 */
export async function getRun(runId) {
  const response = await fetch(`${API_BASE}/api/runs/${runId}`);

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Unknown error' }));
    throw new Error(error.detail || `API error: ${response.status}`);
  }

  return response.json();
}

/**
 * Get detailed results for a run.
 * @param {string} runId
 * @returns {Promise<Object>} - Detailed results with per-example scores
 */
export async function getRunResults(runId) {
  const response = await fetch(`${API_BASE}/api/runs/${runId}/results`);

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Unknown error' }));
    throw new Error(error.detail || `API error: ${response.status}`);
  }

  return response.json();
}

// ─── Dry-Run / Validate Metrics ──────────────────────────────────────────────

/**
 * Validate proposed metrics against sample data using LLM analysis.
 * @param {Array} metrics - Proposed metrics
 * @param {Array} sampleData - Sample test data
 * @param {string} description - Eval description for context
 * @returns {Promise<Object>} - { overall_assessment, message, metric_feedback: [...] }
 */
export async function validateMetrics(metrics, sampleData, description = '') {
  const response = await fetch(`${API_BASE}/api/validate-metrics`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      metrics,
      sample_data: sampleData,
      description,
    }),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Unknown error' }));
    throw new Error(error.detail || `API error: ${response.status}`);
  }

  return response.json();
}
