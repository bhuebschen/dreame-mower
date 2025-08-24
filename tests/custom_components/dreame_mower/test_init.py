"""Test integration_blueprint setup process."""
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.config_entries import ConfigEntryState
import pytest
from unittest.mock import patch

from homeassistant.core import HomeAssistant

from custom_components.dreame_mower import DreameMowerDataUpdateCoordinator
from pytest_homeassistant_custom_component.common import MockConfigEntry
from custom_components.dreame_mower.const import DOMAIN

from tests.const import MOCK_DATA, MOCK_OPTIONS

# We can pass fixtures as defined in conftest.py to tell pytest to use the fixture
# for a given test. We can also leverage fixtures and mocks that are available in
# Home Assistant using the pytest_homeassistant_custom_component plugin.
# Assertions allow you to verify that the return value of whatever is on the left
# side of the assertion matches with the right side.
async def test_setup_and_unload_entry(hass: HomeAssistant):
    """Test entry setup and unload."""
    # Patch the coordinator's first refresh to bypass device connection
    with patch("custom_components.dreame_mower.DreameMowerDataUpdateCoordinator.async_config_entry_first_refresh"):
        # Create a mock entry so we don't have to go through config flow
        config_entry = MockConfigEntry(
            domain=DOMAIN, data=MOCK_DATA, options=MOCK_OPTIONS, entry_id="test"
        )
        config_entry.add_to_hass(hass)

        # Set up the entry
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

        # Check that it is loaded
        assert config_entry.state is ConfigEntryState.LOADED
        assert DOMAIN in hass.data and config_entry.entry_id in hass.data[DOMAIN]
        assert isinstance(
            hass.data[DOMAIN][config_entry.entry_id], DreameMowerDataUpdateCoordinator
        )

        # Unload the entry
        assert await hass.config_entries.async_unload(config_entry.entry_id)
        await hass.async_block_till_done()

        # Check that it is unloaded
        assert config_entry.state is ConfigEntryState.NOT_LOADED
        assert config_entry.entry_id not in hass.data.get(DOMAIN, {})


async def test_setup_entry_not_ready(hass: HomeAssistant):
    """Test ConfigEntryNotReady when API raises an exception during entry setup."""
    config_entry = MockConfigEntry(
        domain=DOMAIN, data=MOCK_DATA, options=MOCK_OPTIONS, entry_id="test"
    )
    config_entry.add_to_hass(hass)

    # Patch the coordinator's refresh method to raise ConfigEntryNotReady.
    # This should cause the entry state to be SETUP_RETRY.
    with patch(
        "custom_components.dreame_mower.coordinator.DreameMowerDataUpdateCoordinator.async_config_entry_first_refresh",
        side_effect=ConfigEntryNotReady,
    ):
        assert not await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_setup_entry_error(hass: HomeAssistant):
    """Test for a generic exception during entry setup."""
    config_entry = MockConfigEntry(
        domain=DOMAIN, data=MOCK_DATA, options=MOCK_OPTIONS, entry_id="test"
    )
    config_entry.add_to_hass(hass)

    # Patch the coordinator's refresh method to raise a generic Exception.
    # This should cause the entry state to be SETUP_ERROR.
    with patch(
        "custom_components.dreame_mower.coordinator.DreameMowerDataUpdateCoordinator.async_config_entry_first_refresh",
        side_effect=Exception("Something went wrong"),
    ):
        assert not await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.SETUP_ERROR
