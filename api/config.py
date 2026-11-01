"""Shared environment-backed settings for the Pi API."""

import os


def get_api_token() -> str | None:
    """Read the API token from the process environment.

    Read when each request is handled so tests and controlled local
    configuration changes see the current process environment.
    """
    return os.getenv("THASHU_API_TOKEN")
