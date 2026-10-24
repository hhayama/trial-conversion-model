from unittest.mock import MagicMock, patch

import pytest


# autouse=True means this runs automatically before any tests/imports happen
@pytest.fixture(autouse=True, scope="session")
def mock_model_loading():
    with patch("trial_conversion_model.api.routes.load_model") as mock_load:
        mock_load.return_value = MagicMock()
        yield mock_load
