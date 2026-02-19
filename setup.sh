#!/bin/bash

echo "Setting up Video Processing Application..."

# Create necessary directories
echo "Creating directories..."
mkdir -p static uploads processed

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv .venv
fi

# Activate virtual environment
source .venv/bin/activate

# Install/upgrade pip
echo "Upgrading pip..."
python -m pip install --upgrade pip

# Install requirements
echo "Installing requirements..."
pip install -r requirements.txt

echo "Setup complete! Run ./start.sh to start the application."