#!/bin/bash
# Hive Agent Swarm - Setup Script
# This script sets up the development environment

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

echo "🐝 Hive Agent Swarm - Setup"
echo "=========================="
echo ""

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check Python version
echo "Checking Python..."
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}❌ Python 3 not found. Please install Python 3.10+${NC}"
    exit 1
fi

PYTHON_VERSION=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
echo -e "${GREEN}✓ Python $PYTHON_VERSION found${NC}"

# Check for venv module and ensurepip
echo ""
echo "Checking venv module..."

# Test if venv actually works (not just importable)
VENV_TEST_DIR=$(mktemp -d)
if ! python3 -m venv "$VENV_TEST_DIR" &> /dev/null; then
    rm -rf "$VENV_TEST_DIR"
    echo -e "${YELLOW}⚠ python3-venv not fully installed${NC}"
    echo ""
    echo "Please install it first:"
    echo ""
    echo "  Ubuntu/Debian:"
    echo "    sudo apt install python3.10-venv python3-pip"
    echo ""
    echo "  Fedora:"
    echo "    sudo dnf install python3-virtualenv"
    echo ""
    echo "  Arch:"
    echo "    sudo pacman -S python-virtualenv"
    echo ""
    echo "Then run this script again."
    exit 1
fi
rm -rf "$VENV_TEST_DIR"
echo -e "${GREEN}✓ venv module available${NC}"

# Create virtual environment
echo ""
echo "Creating virtual environment..."
cd "$PROJECT_DIR"

# Check if venv exists and is valid
if [ -d "venv" ] && [ -f "venv/bin/activate" ]; then
    echo -e "${YELLOW}⚠ venv already exists. Skipping creation.${NC}"
else
    # Remove broken venv if exists
    if [ -d "venv" ]; then
        echo -e "${YELLOW}⚠ Removing broken venv...${NC}"
        rm -rf venv
    fi
    python3 -m venv venv
    echo -e "${GREEN}✓ Virtual environment created${NC}"
fi

# Activate venv
echo ""
echo "Activating virtual environment..."
source venv/bin/activate
echo -e "${GREEN}✓ Virtual environment activated${NC}"

# Upgrade pip
echo ""
echo "Upgrading pip..."
pip install --upgrade pip -q
echo -e "${GREEN}✓ pip upgraded${NC}"

# Install dependencies
echo ""
echo "Installing dependencies..."
pip install -r requirements.txt -q
echo -e "${GREEN}✓ Dependencies installed${NC}"

# Create .env if not exists
echo ""
if [ ! -f ".env" ]; then
    echo "Creating .env from template..."
    cp .env.example .env
    echo -e "${YELLOW}⚠ Please edit .env and add your OPENAI_API_KEY${NC}"
else
    echo -e "${GREEN}✓ .env already exists${NC}"
fi

# Summary
echo ""
echo "=========================="
echo -e "${GREEN}🎉 Setup complete!${NC}"
echo ""
echo "To activate the environment:"
echo "  source venv/bin/activate"
echo ""
echo "To run tests:"
echo "  pytest"
echo ""
echo "To start the swarm:"
echo "  python main.py run --codebase /path/to/project"
echo ""
