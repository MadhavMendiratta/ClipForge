#!/bin/bash

# Activate virtual environment
source .venv/bin/activate

# Run the FastAPI application with reload for development
uvicorn main:app --host $(grep HOST .env | cut -d '=' -f2) --port $(grep PORT .env | cut -d '=' -f2) --reload