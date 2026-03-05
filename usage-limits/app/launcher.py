"""Launch both Streamlit dashboard and FastAPI budget API."""

import logging
import os
import subprocess
import sys

import uvicorn

from core.config import AppConfig
from core.db import create_engine_from_config, init_schema, make_session_factory
from api import app as fastapi_app, set_session_factory

logger = logging.getLogger(__name__)


def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    config = AppConfig.from_env()
    logger.info("Starting usage-limits app")
    engine = create_engine_from_config(config)
    init_schema(engine)
    set_session_factory(make_session_factory(engine))

    # Start Streamlit on the port Databricks Apps expects
    app_port = os.environ.get("DATABRICKS_APP_PORT", "8501")
    streamlit_proc = subprocess.Popen([
        sys.executable, "-m", "streamlit", "run", "app.py",
        "--server.port", app_port, "--server.headless", "true",
    ])

    try:
        uvicorn.run(fastapi_app, host="0.0.0.0", port=config.budget_api_port)
    finally:
        streamlit_proc.terminate()


if __name__ == "__main__":
    main()
