import pytest

from custom_components.dreame_mower.dreame.device import DreameMowerDeviceStatus
from custom_components.dreame_mower.dreame.types import (
    DreameMowerProperty,
    DreameMowerErrorCode,
)


class DummyDevice:
    def __init__(self, error_code):
        self._error_code = error_code

    # Device API used by DreameMowerDeviceStatus._get_property
    def get_property(self, prop):
        if prop == DreameMowerProperty.ERROR:
            return self._error_code
        return None


@pytest.mark.parametrize(
    "code,expected,error_name,has_error,has_warning",
    [
        # Ignored / remapped error codes -> NO_ERROR
        (DreameMowerErrorCode.MOWING_STARTED.value, DreameMowerErrorCode.NO_ERROR, "no_error", False, False),
        (DreameMowerErrorCode.MOWING_COMPLETED.value, DreameMowerErrorCode.NO_ERROR, "no_error", False, False),
        
        # Real warning code -> warning (BLOCKED is in warning_codes list) => has_warning True, has_error False
        (DreameMowerErrorCode.BLOCKED.value, DreameMowerErrorCode.BLOCKED, "blocked", False, True),
        
        # Real non-warning error (choose ROUTE? but ROUTE is remapped) pick BATTERY_LOW maybe (treated as error but excluded from has_error logic?)
        # Use BATTERY_LOW to confirm it's not considered has_error (excluded explicitly) and not a warning.
        (DreameMowerErrorCode.BATTERY_LOW.value, DreameMowerErrorCode.BATTERY_LOW, "battery_low", False, False),
        
        # Unknown numeric code -> UNKNOWN
        (9999, DreameMowerErrorCode.UNKNOWN, "unknown", False, False),
    ],
)
def test_device_status_error_mapping(code, expected, error_name, has_error, has_warning):
    device = DummyDevice(code)
    status = DreameMowerDeviceStatus(device)

    # Core mapping
    assert status.error == expected

    # Derived flags
    assert status.has_error is has_error
    assert status.has_warning is has_warning

    # Name consistency (lowercase comparison)
    assert status.error_name.lower() == error_name


def test_other_error_codes_flagged_as_error():
    """All non-suppressed, non-warning, non-special (battery_low) positive codes should be errors."""
    suppressed = {
        DreameMowerErrorCode.LOW_BATTERY_TURN_OFF,
        DreameMowerErrorCode.UNKNOWN_WARNING_2,
        DreameMowerErrorCode.WATER_ON_LIDAR,
        DreameMowerErrorCode.MOWING_COMPLETED,
        DreameMowerErrorCode.MOWING_STARTED,
    }
    warnings = {
        DreameMowerErrorCode.BLOCKED,
        DreameMowerErrorCode.STATION_DISCONNECTED,
        DreameMowerErrorCode.SELF_TEST_FAILED,
        DreameMowerErrorCode.LOW_BATTERY_TURN_OFF,
        DreameMowerErrorCode.UNKNOWN_WARNING_2,
    }

    special_excluded = {DreameMowerErrorCode.BATTERY_LOW}

    checked = 0
    for code in DreameMowerErrorCode:
        if code.value <= 0:
            continue
        if code in suppressed or code in warnings or code in special_excluded:
            continue
        device = DummyDevice(code.value)
        status = DreameMowerDeviceStatus(device)
        assert status.error == code
        assert status.has_warning is False
        assert status.has_error is True, f"Expected has_error True for {code.name} ({code.value})"
        checked += 1

    # Safety: ensure we actually validated a meaningful subset
    assert checked > 5
