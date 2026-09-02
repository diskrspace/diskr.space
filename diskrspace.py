"""Development/standalone entry point for the FastAPI backend."""
import logging

import uvicorn

from db import Config
from web.index import app

config = Config.load("web")
application = app


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG if config["DEBUG"] else logging.INFO)
    uvicorn.run("web.index:app", host=config["WEB_IP"], port=int(config["WEB_PORT"]),
                reload=bool(config["DEBUG"]))
