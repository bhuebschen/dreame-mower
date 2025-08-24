"""Global fixtures for Dreame Mower integration tests."""
# This file contains global fixtures for the Dreame Mower integration tests.
# Fixtures are defined once and can be used in any test function in the project
# by passing them as a parameter. If a fixture is marked with `autouse=True`,
# it will be automatically used in all tests.
#
# For more information on pytest fixtures, see:
# https://docs.pytest.org/en/latest/fixture.html
#
# For Home Assistant specific fixtures provided by the `pytest-homeassistant-custom-component`
# plugin, see:
# https://github.com/MatthewFlamm/pytest-homeassistant-custom-component/blob/master/pytest_homeassistant_custom_component/common.py
from unittest.mock import patch

import pytest

pytest_plugins = "pytest_homeassistant_custom_component"


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations: None) -> None:
    """Enable custom integrations defined in the test dir."""
    pass

# This fixture is used to prevent HomeAssistant from attempting to create and dismiss persistent
# notifications. These calls would fail without this fixture since the persistent_notification
# integration is never loaded during a test.
@pytest.fixture(name="skip_notifications", autouse=True)
def skip_notifications_fixture():
    """Skip notification calls."""
    with patch("homeassistant.components.persistent_notification.async_create"), patch(
        "homeassistant.components.persistent_notification.async_dismiss"
    ):
        yield