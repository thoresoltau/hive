#!/bin/bash
# Hive Agent Swarm - Setup Script
# Automatically detects uv or falls back to standard pip/venv.
# Installs hive-agents as an editable CLI tool.

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "🐝 ${BLUE}Hive Agent Swarm - Setup${NC}"
echo "=========================="

cd "$PROJECT_DIR"

# 1. Check for uv (Preferred)
if command -v uv &> /dev/null; then
    echo -e "\n${BLUE}Found uv! Using fast setup mode...${NC}"
    
    # Create venv if not exists
    if [ ! -d ".venv" ]; then
        echo "Creating .venv with uv..."
        # Try to use specific python versions if available, otherwise default
        if uv venv --python 3.12 &> /dev/null; then
            echo -e "${GREEN}✓ Created venv with Python 3.12${NC}"
        elif uv venv --python 3.11 &> /dev/null; then
             echo -e "${GREEN}✓ Created venv with Python 3.11${NC}"
        else
            uv venv
            echo -e "${GREEN}✓ Created venv with system Python${NC}"
        fi
    else
        echo -e "${GREEN}✓ .venv already exists${NC}"
    fi
    
    # Activate
    source .venv/bin/activate
    
    # Install dependencies and CLI
    echo "Installing dependencies..."
    uv pip install -r requirements.txt
    
    echo "Installing Hive CLI..."
    uv pip install -e .

else
    # 2. Fallback to standard pip/venv
    echo -e "\n${YELLOW}uv not found. Using standard pip/venv...${NC}"
    
    # Check Python version
    if ! command -v python3 &> /dev/null; then
        echo -e "${RED}❌ Python 3 not found.${NC}"
        exit 1
    fi
    
    # Create venv
    if [ ! -d "venv" ] && [ ! -d ".venv" ]; then
        echo "Creating venv..."
        python3 -m venv venv
        echo -e "${GREEN}✓ Created venv${NC}"
    fi
    
    # Activate
    if [ -f "venv/bin/activate" ]; then
        source venv/bin/activate
    elif [ -f ".venv/bin/activate" ]; then
        source .venv/bin/activate
    else
        echo -e "${RED}❌ Could not find activation script.${NC}"
        exit 1
    fi
    
    # Upgrade pip
    echo "Upgrading pip..."
    pip install --upgrade pip -q
    
    # Install dependencies
    echo "Installing dependencies..."
    pip install -r requirements.txt -q
    
    echo "Installing Hive CLI..."
    pip install -e . -q
fi

# 3. Setup Environment Config
echo ""
if [ ! -f ".env" ]; then
    echo "Creating .env from template..."
    cp .env.example .env
    echo -e "${YELLOW}⚠ Please edit .env and add your OPENAI_API_KEY${NC}"
else
    echo -e "${GREEN}✓ .env already exists${NC}"
fi

# 4. Setup Global Config (Phase 4 artifact)
echo "Checking global config..."
CONFIG_DIR="$HOME/.hive"
CONFIG_FILE="$CONFIG_DIR/config.yaml"

if [ ! -d "$CONFIG_DIR" ]; then
    mkdir -p "$CONFIG_DIR"
    echo -e "${GREEN}✓ Created ~/.hive/${NC}"
fi

if [ ! -f "$CONFIG_FILE" ]; then
    echo "openai_api_key: " > "$CONFIG_FILE"
    echo "tavily_api_key: " >> "$CONFIG_FILE"
    echo "model: gpt-4o" >> "$CONFIG_FILE"
    echo -e "${GREEN}✓ Created ~/.hive/config.yaml template${NC}"
    echo -e "${YELLOW}👉 Tip: Add your API keys to ~/.hive/config.yaml for global access.${NC}"
fi

# Summary
echo ""
echo "=========================="
echo -e "${GREEN}🎉 Setup complete!${NC}"
echo ""
echo "To activate the environment:"
if [ -d ".venv" ]; then
    echo -e "  ${BLUE}source .venv/bin/activate${NC}"
else
    echo -e "  ${BLUE}source venv/bin/activate${NC}"
fi
echo ""
echo "Try the CLI:"
echo -e "  ${BLUE}hive --help${NC}"
echo ""
echo "Initialize a new project:"
echo -e "  ${BLUE}cd ~/my-project && hive init${NC}"
echo ""
