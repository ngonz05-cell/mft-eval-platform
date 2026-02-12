#!/bin/bash
#
# Start the MFT Eval Platform (backend + frontend)
#
# Usage:
#   ./start.sh                    # Start both backend and frontend
#   ./start.sh --backend-only     # Start only the API server
#   ./start.sh --frontend-only    # Start only the React dev server
#
# Environment variables:
#   MFT_LLM_PROVIDER    "llama_api" (default, Meta internal) or "anthropic_direct"
#   ANTHROPIC_API_KEY    Required if MFT_LLM_PROVIDER=anthropic_direct
#   MFT_LLM_MODEL       Model name (default: claude-sonnet-4-5-20250514)
#   MFT_API_PORT         API server port (default: 8000)
#   REACT_APP_API_URL    Frontend API URL (default: http://localhost:8000)

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}  📊 MFT Eval Platform${NC}"
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

start_backend() {
    echo -e "${BLUE}[Backend]${NC} Installing Python dependencies..."
    pip install -q -r api/requirements.txt 2>/dev/null || pip3 install -q -r api/requirements.txt 2>/dev/null

    echo -e "${BLUE}[Backend]${NC} Starting API server on port ${MFT_API_PORT:-8000}..."
    echo -e "${BLUE}[Backend]${NC} Provider: ${MFT_LLM_PROVIDER:-llama_api} | Model: ${MFT_LLM_MODEL:-claude-sonnet-4-5-20250514}"
    echo ""
    python -m uvicorn api.server:app --host 0.0.0.0 --port "${MFT_API_PORT:-8000}" --reload &
    BACKEND_PID=$!
    echo -e "${BLUE}[Backend]${NC} PID: $BACKEND_PID"
}

start_frontend() {
    echo -e "${YELLOW}[Frontend]${NC} Starting React dev server on port 3000..."
    echo ""
    cd ui
    REACT_APP_API_URL="${REACT_APP_API_URL:-http://localhost:8000}" npx react-scripts start &
    FRONTEND_PID=$!
    echo -e "${YELLOW}[Frontend]${NC} PID: $FRONTEND_PID"
    cd ..
}

cleanup() {
    echo ""
    echo -e "${GREEN}Shutting down...${NC}"
    [ -n "$BACKEND_PID" ] && kill "$BACKEND_PID" 2>/dev/null
    [ -n "$FRONTEND_PID" ] && kill "$FRONTEND_PID" 2>/dev/null
    exit 0
}

trap cleanup SIGINT SIGTERM

case "${1:-}" in
    --backend-only)
        start_backend
        wait $BACKEND_PID
        ;;
    --frontend-only)
        start_frontend
        wait $FRONTEND_PID
        ;;
    *)
        start_backend
        sleep 2
        start_frontend
        echo ""
        echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
        echo -e "${GREEN}  ✅ Backend:  http://localhost:${MFT_API_PORT:-8000}/api/health${NC}"
        echo -e "${GREEN}  ✅ Frontend: http://localhost:3000${NC}"
        echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
        echo ""
        echo -e "Press Ctrl+C to stop both servers."
        wait
        ;;
esac
