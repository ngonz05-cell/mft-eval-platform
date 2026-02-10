#!/bin/bash
# MFT Eval Platform - Setup Script for On Demand Instance
# Run this script after copying the project to your OD instance

set -e  # Exit on error

echo "🚀 MFT Eval Platform - Setup Script"
echo "===================================="

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if we're in the right directory
if [ ! -d "ui" ]; then
    echo -e "${RED}Error: Please run this script from the mft-eval-platform root directory${NC}"
    exit 1
fi

echo -e "\n${YELLOW}Step 1: Checking Node.js installation...${NC}"
if command -v node &> /dev/null; then
    NODE_VERSION=$(node -v)
    echo -e "${GREEN}✓ Node.js found: $NODE_VERSION${NC}"
else
    echo -e "${YELLOW}Node.js not found. Installing via feature...${NC}"
    feature install nodejs
    echo -e "${GREEN}✓ Node.js installed${NC}"
fi

echo -e "\n${YELLOW}Step 2: Installing UI dependencies...${NC}"
cd ui
npm install
echo -e "${GREEN}✓ Dependencies installed${NC}"

echo -e "\n${YELLOW}Step 3: Building production version...${NC}"
npm run build
echo -e "${GREEN}✓ Production build complete${NC}"

echo -e "\n${GREEN}===================================="
echo "✅ Setup complete!"
echo "===================================="
echo -e "${NC}"
echo "To start the development server:"
echo "  cd ui && npm start"
echo ""
echo "To serve the production build:"
echo "  cd ui && npx serve -s build"
echo ""
echo "The app will be available at the URL shown in the terminal."
echo "Share this URL with your team for feedback!"
