"""
Configuration for the MFT Eval Platform API.

Endpoints, model names, and environment settings.
Loads from .env file if present (via python-dotenv).
"""
import os

from dotenv import load_dotenv

load_dotenv()

from .system_prompt import SYSTEM_PROMPT as _DEFAULT_SYSTEM_PROMPT

# --- LLM Provider Configuration ---
# Llama API passthrough for Anthropic (Meta internal)
LLAMA_API_ANTHROPIC_BASE_URL = "https://api.llama.com/experimental/passthrough/anthropic"

# Model to use
LLM_MODEL = os.environ.get("MFT_LLM_MODEL", "claude-sonnet-4-5-20250514")

# Llama API key (required for Llama API passthrough — get yours at https://llama.developer.meta.com/api-keys)
LLAMA_API_KEY = os.environ.get("LLAMA_API_KEY", "")

# Fallback: direct Anthropic API (for local dev outside corp network)
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
ANTHROPIC_DIRECT_BASE_URL = "https://api.anthropic.com"

# Which provider to use: "llama_api" (Meta internal) or "anthropic_direct" (public API)
LLM_PROVIDER = os.environ.get("MFT_LLM_PROVIDER", "llama_api")

# --- API Configuration ---
API_HOST = os.environ.get("MFT_API_HOST", "0.0.0.0")
API_PORT = int(os.environ.get("MFT_API_PORT", "8000"))

# CORS origins (React dev server + GitHub Pages)
CORS_ORIGINS = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "https://ngonz05-cell.github.io",
]

# --- System Prompt ---
# Uses the custom prompt from system_prompt.py, overridable via env var
SYSTEM_PROMPT = os.environ.get("MFT_SYSTEM_PROMPT", _DEFAULT_SYSTEM_PROMPT)

# Max tokens for LLM responses
MAX_TOKENS = int(os.environ.get("MFT_MAX_TOKENS", "2048"))

# Request timeout (seconds) — 3P models via Llama API don't support streaming
REQUEST_TIMEOUT = int(os.environ.get("MFT_REQUEST_TIMEOUT", "120"))
