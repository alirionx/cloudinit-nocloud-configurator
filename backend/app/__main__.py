"""Entry point: `python -m app`. Host, port and log level come from the environment."""

import logging

import uvicorn

from app.main import create_app
from app.settings import Settings


def main() -> None:
    settings = Settings()
    logging.basicConfig(level=settings.log_level.upper())
    # A single worker process: TinyDB does not support concurrent writers (R-02).
    uvicorn.run(
        create_app(settings),
        host=settings.host,
        port=settings.port,
        log_level=settings.log_level,
        workers=1,
    )


if __name__ == "__main__":
    main()
