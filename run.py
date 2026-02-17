#!/usr/bin/env python3
"""
HR Multi-Agent Platform — Application Entry Point

Run from project root:
    python run.py

Or with gunicorn:
    gunicorn --bind 0.0.0.0:5050 --workers 4 run:app
"""
import sys
import os

# Ensure project root is on the Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.app_v2 import app, create_app

# Always call create_app() so Gunicorn (which imports `run:app`)
# gets a fully initialized application with DB tables, blueprints, etc.
create_app()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5050))
    debug = os.environ.get("DEBUG", "false").lower() == "true"
    print(f"\n  HR Multi-Agent Platform running at http://localhost:{port}\n")
    app.run(host="0.0.0.0", port=port, debug=debug)
