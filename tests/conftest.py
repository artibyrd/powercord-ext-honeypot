# ruff: noqa: E402
import os
import sys

# Add powercord to sys.path so we have access to app.common etc.
# Uses POWERCORD_PATH environment variable if set, otherwise falls back to assuming sibling directory.
powercord_dir = os.environ.get(
    "POWERCORD_PATH", 
    os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "powercord"))
)

if not os.path.exists(powercord_dir):
    raise RuntimeError(
        f"Could not locate the powercord core repository at {powercord_dir}. "
        "Please ensure it is cloned natively adjacent to the extensions folder, or set the POWERCORD_PATH environment variable."
    )

if powercord_dir not in sys.path:
    sys.path.insert(0, powercord_dir)

from app.common.testing import setup_extension_test_env
setup_extension_test_env("honeypot", __file__)

import pytest
from unittest.mock import AsyncMock, MagicMock

@pytest.fixture
def session():
    return MagicMock()