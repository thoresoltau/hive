#!/bin/bash
# Hive Agent Swarm - Test Runner
# Runs pytest with common options

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_DIR"

# Check if venv exists
if [ ! -d "venv" ]; then
    echo "❌ Virtual environment not found. Run scripts/setup.sh first."
    exit 1
fi

# Activate venv
source venv/bin/activate

# Run tests
echo "🧪 Running tests..."
echo ""

# Parse arguments
if [ "$1" == "--coverage" ] || [ "$1" == "-c" ]; then
    pytest --cov=. --cov-report=term-missing --cov-report=html "${@:2}"
    echo ""
    echo "📊 Coverage report: htmlcov/index.html"
elif [ "$1" == "--watch" ] || [ "$1" == "-w" ]; then
    # Requires pytest-watch: pip install pytest-watch
    ptw "${@:2}"
else
    pytest -v "$@"
fi
