import pytest
from unittest.mock import AsyncMock, MagicMock

from custom_components.dreame_mower.lawn_mower import DreameMower, STATE_CODE_TO_STATE
from custom_components.dreame_mower.dreame.types import DreameMowerState, DreameMowerAction
from custom_components.dreame_mower.dreame import ACTION_AVAILABILITY
from homeassistant.components.lawn_mower import LawnMowerActivity


class DummyCoordinator:
    """A mock coordinator for testing."""

    def __init__(self):
        self.device = MagicMock()
        self.device.name = "Test Mower"
        self.device.mac = "00:11:22:33:44:55"
        self.device.device_connected = True
        self.device.status = MagicMock()
        self.device.status.has_error = False
        self.device.status.paused = False
        self.device.status.sleeping = False        
        self.device.status.charging = False
        self.device.status.docked = False
        self.device.status.cruising = False
        self.device.status.battery_level = 80
        self.device.status.state = DreameMowerState.IDLE
        self.device.status.attributes = {"foo": "bar"}
        self.device.status.started = True
        self.device.status.customized_cleaning = False
        self.device.status.zone_cleaning = False
        self.device.status.spot_cleaning = False
        self.device.status.scheduled_clean = False
        self.async_request_refresh = AsyncMock()


@pytest.fixture
def mower():
    """Fixture for a DreameMower instance."""
    coordinator = DummyCoordinator()
    return DreameMower(coordinator)


@pytest.fixture
def bypass_try_command(mower):
    """Fixture to bypass the _try_command wrapper for easier testing of command calls."""
    async def fake_try_command(msg, func, *args, **kwargs):
        await func(*args, **kwargs)

    mower._try_command = fake_try_command
    return mower


def test_lawn_mower_properties(mower):
    """Test the basic properties of the lawn mower entity."""
    assert mower._attr_name == "Test Mower"
    assert mower._attr_unique_id.startswith("00:11:22:33:44:55_")
    assert mower.available is True
    assert mower.state == LawnMowerActivity.PAUSED  # Initial state is IDLE -> PAUSED
    assert isinstance(mower.extra_state_attributes, dict)
    assert mower.battery_icon.startswith("mdi:")
    assert isinstance(mower.supported_features, int)


@pytest.mark.parametrize(
    "status_updates, expected_icon",
    [
        ({"has_error": True}, "mdi:alert-octagon"),
        ({"paused": True}, "mdi:pause-circle"),
        ({"sleeping": True}, "mdi:sleep"),
        ({"charging": True}, "mdi:lightning-bolt-circle"),
        ({"docked": True}, "mdi:robot-mower"),
        ({"cruising": True}, "mdi:map-marker-path"),
        ({}, "mdi:robot-mower"),  # Default case
    ],
)
def test_icon_logic(mower, status_updates, expected_icon):
    """Test that the icon logic correctly reflects the mower's state."""
    # Apply the specific state for this test case
    for key, value in status_updates.items():
        setattr(mower.device.status, key, value)

    mower._set_attrs()
    assert mower.icon == expected_icon


@pytest.mark.asyncio
async def test_async_dock_when_idle(bypass_try_command):
    """Test that dock does not call stop when the mower is already idle."""
    # Arrange
    mower = bypass_try_command
    mower.device.stop = AsyncMock()
    mower.device.dock = AsyncMock()

    # Simulate mower is idle, making the STOP action unavailable
    mower.device.status.state = DreameMowerState.IDLE
    mower.device.status.started = False
    mower.device.status.returning = False
    mower.device.status.docking = False
    assert not ACTION_AVAILABILITY[DreameMowerAction.STOP.name](mower.device)

    # Act
    await mower.async_dock()

    # Assert
    mower.device.stop.assert_not_called()
    mower.coordinator.async_request_refresh.assert_not_called()
    mower.device.dock.assert_called_once()


@pytest.mark.asyncio
async def test_async_dock_when_mowing(bypass_try_command):
    """Test that dock calls stop and waits for the mower to stop before returning."""
    # Arrange
    mower = bypass_try_command
    mower.device.stop = AsyncMock()
    mower.device.dock = AsyncMock()

    # Simulate mower is mowing, making the STOP action available
    mower.device.status.state = DreameMowerState.MOWING
    mower.device.status.started = True
    mower.device.status.returning = False
    mower.device.status.docking = False
    assert ACTION_AVAILABILITY[DreameMowerAction.STOP.name](mower.device)
    assert STATE_CODE_TO_STATE.get(mower.device.status.state) == LawnMowerActivity.MOWING

    # Simulate the state change during polling to exit the wait loop
    async def refresh_side_effect():
        mower.device.status.state = DreameMowerState.IDLE
    mower.coordinator.async_request_refresh.side_effect = refresh_side_effect

    # Act
    await mower.async_dock()

    # Assert
    mower.device.stop.assert_called_once()
    mower.coordinator.async_request_refresh.assert_called_once()
    mower.device.dock.assert_called_once()

@pytest.mark.asyncio
async def test_stop_changes_state_from_mowing(bypass_try_command):
    """Test that calling stop correctly changes the entity's state from mowing."""
    # Arrange: Simulate mower is mowing
    mower = bypass_try_command
    mower.device.status.state = DreameMowerState.MOWING
    mower._set_attrs()
    assert mower.state == LawnMowerActivity.MOWING

    # Arrange: Patch device's stop method to simulate the state change
    # that would be reported back by the device after stopping.
    async def fake_stop():
        mower.device.status.state = DreameMowerState.IDLE
        mower._set_attrs()
        return None

    mower.device.stop = AsyncMock(side_effect=fake_stop)

    # Act
    await mower.async_stop()

    # Assert: After stopping, the state should be paused.
    # The underlying device state is 'IDLE', which maps to HA's 'PAUSED' state.
    assert mower.state == LawnMowerActivity.PAUSED
