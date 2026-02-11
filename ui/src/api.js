/**
 * API client for the MFT Eval Platform backend.
 *
 * Connects to the FastAPI server which proxies LLM calls
 * to Claude Sonnet 4.5 via Meta's Llama API.
 */

const API_BASE = process.env.REACT_APP_API_URL || 'http://localhost:8000';

/**
 * Send a chat message to the backend.
 * Routes to the appropriate LLM handler based on the current phase.
 *
 * @param {string} phase - Current phase (objective, refine, metrics, automation, review)
 * @param {string} message - User's message
 * @param {Array} conversationHistory - Previous messages [{role, content}]
 * @param {Object} evalConfig - Current evalConfig state
 * @returns {Promise<Object>} - { type: 'refine'|'chat', data: {...} }
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
 * Called when the user confirms their refined prompt.
 *
 * @param {string} description - Finalized product description
 * @param {Array} conversationHistory - Full conversation for context
 * @returns {Promise<Object>} - { message, eval_name, metrics: [...] }
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
 * @returns {Promise<Object>} - { status, provider, model }
 */
export async function checkHealth() {
  const response = await fetch(`${API_BASE}/api/health`);
  if (!response.ok) throw new Error('API not available');
  return response.json();
}

/**
 * Hot-update the system prompt without restarting the server.
 * @param {string} systemPrompt - New system prompt text
 * @returns {Promise<Object>} - { status, prompt_length }
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
