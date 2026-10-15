"""Entry point: `python -m app`. All configuration comes from the environment (NFR-003)."""

import logging
import sys

import uvicorn
from pydantic import ValidationError

from app.main import create_app
from app.settings import Settings


def load_settings() -> Settings:
    """Load settings or exit with a readable error message (DS-004)."""
    try:
        return Settings()
    except ValidationError as exc:
        # Input values are deliberately not printed; they may contain secrets (NFR-007).
        lines = [
            f"  {'.'.join(str(loc) for loc in error['loc']).upper() or 'settings'}: {error['msg']}"
            for error in exc.errors()
        ]
        print("Invalid configuration:\n" + "\n".join(lines), file=sys.stderr)
        sys.exit(1)


def main() -> None:
    settings = load_settings()
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
