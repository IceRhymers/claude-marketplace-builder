"""Launch both Streamlit dashboard and FastAPI budget API."""

import subprocess
import sys

import uvicorn

from core.config import AppConfig
from core.db import create_pool, init_schema
from api import app as fastapi_app, set_pool


def main():
    config = AppConfig.from_env()
    pool = create_pool(config)
    init_schema(pool)
    set_pool(pool)

    # Start Streamlit as subprocess
    streamlit_proc = subprocess.Popen([
        sys.executable, "-m", "streamlit", "run", "app.py",
        "--server.port", "8501", "--server.headless", "true",
    ])

    try:
        uvicorn.run(fastapi_app, host="0.0.0.0", port=config.budget_api_port)
    finally:
        streamlit_proc.terminate()


if __name__ == "__main__":
    main()
