import os

import pytest

# Testes sempre rodam offline e determinísticos, independente do .env local.
for key, value in {"LLM_PROVIDER": "fake", "EMBEDDER": "hash", "STORE": "memory"}.items():
    os.environ[key] = value

from delivery_agent.config import Settings  # noqa: E402
from delivery_agent.container import build_agent  # noqa: E402


@pytest.fixture(scope="session")
def agent():
    return build_agent(Settings.from_env())
