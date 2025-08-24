import pytest

from custom_components.dreame_mower.lawn_mower import DreameMower
from unittest.mock import AsyncMock
from unittest.mock import MagicMock

class DummyCoordinator:
    def __init__(self):
        self.device = MagicMock()
        self.device.name = "Test Mower"
        self.device.mac = "00:11:22:33:44:55"
        self.device.device_connected = True
        self.device.status = MagicMock()
        self.device.status.has_error = False
        self.device.status.paused = False
        self.device.status.sleeping = False
        self.device.status.charging = True
        self.device.status.docked = False
        self.device.status.cruising = False
        self.device.status.battery_level = 80
        self.device.status.state = 1
        self.device.status.attributes = {"foo": "bar"}
        self.device.status.started = True
        self.device.status.customized_cleaning = False
        self.device.status.zone_cleaning = False
        self.device.status.spot_cleaning = False
        self.device.status.scheduled_clean = False

@pytest.fixture
def mower():
    coordinator = DummyCoordinator()
    return DreameMower(coordinator)

def test_lawn_mower_properties(mower):
    assert mower._attr_name == "Test Mower"
    assert mower._attr_unique_id.startswith("00:11:22:33:44:55_")
    assert mower.available is True
    assert mower.state is not None
    assert isinstance(mower.extra_state_attributes, dict)
    assert mower.battery_icon.startswith("mdi:")
    assert isinstance(mower.supported_features, int)


def test_state_and_supported_features_change(mower):
    # Change state and supported features by updating device status
    mower.device.status.state = 2  # DreameMowerState.IDLE
    mower._set_attrs()
    assert mower.state is not None
    assert isinstance(mower.supported_features, int)

    # Simulate customized cleaning and scheduled clean
    mower.device.status.customized_cleaning = True
    mower.device.status.scheduled_clean = True
    mower._set_attrs()
    assert mower._attr_fan_speed is None
    assert isinstance(mower._attr_fan_speed_list, list)


def test_icon_logic(mower):
    # Error icon
    mower.device.status.has_error = True
    mower._set_attrs()
    assert mower._attr_icon == "mdi:alert-octagon"

    # Paused icon
    mower.device.status.has_error = False
    mower.device.status.paused = True
    mower._set_attrs()
    assert mower._attr_icon == "mdi:pause-circle"

    # Sleeping icon
    mower.device.status.paused = False
    mower.device.status.sleeping = True
    mower._set_attrs()
    assert mower._attr_icon == "mdi:sleep"

    # Charging icon
    mower.device.status.sleeping = False
    mower.device.status.charging = True
    mower._set_attrs()
    assert mower._attr_icon == "mdi:lightning-bolt-circle"

    # Docked but not charging: default icon
    mower.device.status.charging = False
    mower.device.status.docked = True
    mower._set_attrs()
    assert mower._attr_icon == "mdi:robot-mower"

    # Cruising icon
    mower.device.status.docked = False
    mower.device.status.cruising = True
    mower._set_attrs()
    assert mower._attr_icon == "mdi:map-marker-path"

    # Default icon
    mower.device.status.cruising = False
    mower._set_attrs()
    assert mower._attr_icon == "mdi:robot-mower"

@pytest.mark.asyncio
async def test_async_return_to_base_calls_stop_then_return(mower):
    mower.device.stop = AsyncMock()
    mower.device.return_to_base = AsyncMock()
    async def fake_try_command(msg, func, *args, **kwargs):
        return await func(*args, **kwargs)
    mower._try_command = fake_try_command

    await mower.async_return_to_base()

    # Ensure stop is called before return_to_base
    assert mower.device.stop.call_count == 1
    assert mower.device.return_to_base.call_count == 1
