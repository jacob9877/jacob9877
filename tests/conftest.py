import pytest
from unittest.mock import MagicMock


@pytest.fixture(autouse=True)
def mock_llm(monkeypatch):
    fake_model = MagicMock()
    fake_model.invoke.return_value = MagicMock(content="Mocked response")

    from app import utils

    monkeypatch.setattr(utils.llm, "get_model", lambda: fake_model)

    yield
