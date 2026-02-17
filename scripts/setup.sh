#!/bin/bash
# HR Multi-Agent Platform - First-Time Setup Script
# Initializes virtual environment, installs dependencies, and prepares the project

set -e

echo "================================================"
echo "HR Platform - First-Time Setup"
echo "================================================"
echo ""

# Get script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

echo "Project directory: $PROJECT_DIR"
echo ""

# Check Python version
echo "Checking Python version..."
if ! command -v python3 &> /dev/null; then
    echo "Error: Python 3 is not installed"
    exit 1
fi

PYTHON_VERSION=$(python3 --version | cut -d' ' -f2 | cut -d'.' -f1-2)
echo "Found Python $PYTHON_VERSION"
echo ""

# Create virtual environment if it doesn't exist
if [ ! -d "$PROJECT_DIR/venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv "$PROJECT_DIR/venv"
    echo "Virtual environment created"
else
    echo "Virtual environment already exists"
fi
echo ""

# Activate virtual environment
echo "Activating virtual environment..."
source "$PROJECT_DIR/venv/bin/activate"
echo ""

# Upgrade pip
echo "Upgrading pip..."
pip install --upgrade pip setuptools wheel
echo ""

# Install requirements
echo "Installing dependencies from requirements.txt..."
pip install -r "$PROJECT_DIR/requirements.txt"
echo "Dependencies installed successfully"
echo ""

# Copy .env file if it doesn't exist
if [ ! -f "$PROJECT_DIR/.env" ]; then
    echo "Creating .env from .env.example..."
    cp "$PROJECT_DIR/.env.example" "$PROJECT_DIR/.env"
    echo "Created .env file - please update with your actual values"
else
    echo ".env file already exists"
fi
echo ""

# Create necessary directories
echo "Creating data directories..."
mkdir -p "$PROJECT_DIR/data/chroma_db"
mkdir -p "$PROJECT_DIR/data/policies"
mkdir -p "$PROJECT_DIR/data/documents"
mkdir -p "$PROJECT_DIR/logs"
mkdir -p "$PROJECT_DIR/migrations"
echo "Data directories created"
echo ""

# Initialize database migrations
if command -v alembic &> /dev/null; then
    echo "Running database migrations..."
    cd "$PROJECT_DIR"
    alembic upgrade head
    echo "Database migrations completed"
else
    echo "Alembic not installed yet - skipping migrations"
fi
echo ""

echo "================================================"
echo "Setup completed successfully!"
echo "================================================"
echo ""
echo "Next steps:"
echo "  1. Update .env file with your configuration"
echo "  2. Run: source venv/bin/activate"
echo "  3. Run: python src/app_v2.py"
echo ""
