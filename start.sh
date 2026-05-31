#!/bin/bash

echo "==================================="
echo "CODM Bot Manager Starting on Railway"
echo "==================================="

# Create directories
mkdir -p combo combo/hits combo/clean combo/processed
mkdir -p proxy proxy/working proxy/bad proxy/all
mkdir -p data

# Install dependencies
pip install -r requirements.txt

# Start the manager bot
python3 main.py