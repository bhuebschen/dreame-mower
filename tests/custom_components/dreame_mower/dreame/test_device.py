import pytest
from custom_components.dreame_mower.dreame.device import DreameMowerDevice
from custom_components.dreame_mower.dreame.types import (
    DreameMowerAction,
    DreameMowerTaskStatus,
    DreameMowerStatus,
    DreameMowerState,
    DreameMowerStateOld,
    DreameMowerProperty,
)
from homeassistant.const import (
    CONF_NAME,
    CONF_HOST,
    CONF_TOKEN,
)
from tests.const import MOCK_DATA

@pytest.fixture(autouse=True)
def patch_timer(mocker):
    # Patch Timer in the device module to prevent real threads
    mocker.patch("custom_components.dreame_mower.dreame.device.Timer", autospec=True)
    # Patch threading.Timer to prevent real threads
    mocker.patch("threading.Timer", autospec=True)

@pytest.fixture
def device(mocker):
    # Patch DreameMowerDreameHomeCloudProtocol in the protocol module
    mock_cloud_protocol = mocker.patch("custom_components.dreame_mower.dreame.protocol.DreameMowerDreameHomeCloudProtocol")
    mock_cloud_protocol.return_value.cloud = None
    mock_cloud_protocol.return_value.connected = True
    mock_cloud_protocol.return_value.dreame_cloud = False
    mock_cloud_protocol.return_value.action.return_value = {"code": 0}
    mock_cloud_protocol.return_value.get_properties.return_value = []
    mock_cloud_protocol.return_value.set_property.return_value = [{"code": 0}]
    return DreameMowerDevice(
        name=MOCK_DATA[CONF_NAME],
        host=MOCK_DATA[CONF_HOST],
        token=MOCK_DATA[CONF_TOKEN],
        prefer_cloud=True
    )

def test_device_name_property(device: DreameMowerDevice):
    assert device.name == MOCK_DATA[CONF_NAME]

def test_device_host_property(device: DreameMowerDevice):
    assert device.host == MOCK_DATA[CONF_HOST]

def test_device_status_property(device: DreameMowerDevice):
    # By default, status should be DreameMowerStatus.UNKNOWN
    status = device.status.status
    from custom_components.dreame_mower.dreame.types import DreameMowerStatus
    assert status == DreameMowerStatus.UNKNOWN

def test_start_mowing(device: DreameMowerDevice, mocker):
    """Test starting a mowing task."""
    # Mock the call_action method to prevent actual network calls
    mock_call_action = mocker.patch.object(device, "call_action", return_value={"code": 0})

    # Set initial state to idle
    device.data[DreameMowerProperty.STATUS.value] = DreameMowerStatus.IDLE.value
    device.data[DreameMowerProperty.TASK_STATUS.value] = DreameMowerTaskStatus.COMPLETED.value
    device.data[DreameMowerProperty.STATE.value] = DreameMowerState.IDLE.value
    device.data[DreameMowerProperty.CLEANING_PAUSED.value] = False

    # Ensure status.started is False
    assert not device.status.started

    # Call the method to test
    device.start_mowing()

    # Assert that the state was updated optimistically
    assert device.data[DreameMowerProperty.STATUS.value] == DreameMowerStatus.CLEANING.value
    assert device.data[DreameMowerProperty.TASK_STATUS.value] == DreameMowerTaskStatus.MOWING.value
    assert device.data[DreameMowerProperty.STATE.value] == DreameMowerState.MOWING.value

    # Assert that call_action was called with the correct action
    mock_call_action.assert_called_once_with(DreameMowerAction.START_MOWING)

def test_stop_and_state_update(device: DreameMowerDevice, mocker):
    """Test stopping a mowing task and the subsequent state update."""
    # Mock the call_action method to prevent actual network calls
    mock_call_action = mocker.patch.object(device, "call_action", return_value={"code": 0})

    # Set initial state to mowing
    device.data[DreameMowerProperty.STATUS.value] = DreameMowerStatus.CLEANING.value
    device.data[DreameMowerProperty.TASK_STATUS.value] = DreameMowerTaskStatus.MOWING.value
    device.data[DreameMowerProperty.STATE.value] = DreameMowerState.MOWING.value
    device.data[DreameMowerProperty.CLEANING_PAUSED.value] = False

    # Call the method to test
    device.stop()

    # Assert that status properties were updated optimistically right after calling stop()
    assert device.data[DreameMowerProperty.STATUS.value] == DreameMowerStatus.STANDBY.value
    assert device.data[DreameMowerProperty.TASK_STATUS.value] == DreameMowerTaskStatus.COMPLETED.value

    # The 'state' property is not updated optimistically on stop.
    # It will be updated to IDLE upon receiving the next status update from the device.
    # We assert that it remains MOWING immediately after the command for now.
    assert device.data[DreameMowerProperty.STATE.value] == DreameMowerState.MOWING.value

    # Assert that call_action was called with the correct action
    mock_call_action.assert_called_once_with(DreameMowerAction.STOP)

    # Simulate a property update from the device, which happens after the stop command is processed.
    # The device should now report being idle.
    # This payload mimics the format of a push notification from the cloud, which is a list of property dictionaries.
    from custom_components.dreame_mower.dreame.types import DreameMowerPropertyMapping
    update_payload = [
        {
            "siid": DreameMowerPropertyMapping[DreameMowerProperty.STATE]["siid"],
            "piid": DreameMowerPropertyMapping[DreameMowerProperty.STATE]["piid"],
            "value": DreameMowerState.IDLE.value,
        },
        {
            "siid": DreameMowerPropertyMapping[DreameMowerProperty.STATUS]["siid"],
            "piid": DreameMowerPropertyMapping[DreameMowerProperty.STATUS]["piid"],
            "value": DreameMowerStatus.IDLE.value,
        },
    ]

    # Ensure the device is ready to process messages
    device._ready = True
    device._message_callback({"method": "properties_changed", "params": update_payload})

    # Assert that the state is now updated
    assert device.data[DreameMowerProperty.STATE.value] == DreameMowerState.IDLE.value
    assert device.data[DreameMowerProperty.STATUS.value] == DreameMowerStatus.IDLE.value


def test_return_to_base(device: DreameMowerDevice, mocker):
    """Test returning the mower to base."""
    # Mock the call_action method to prevent actual network calls
    mock_call_action = mocker.patch.object(device, "call_action", return_value={"code": 0})

    # Set initial state to mowing
    device.data[DreameMowerProperty.STATUS.value] = DreameMowerStatus.CLEANING.value
    device.data[DreameMowerProperty.TASK_STATUS.value] = DreameMowerTaskStatus.MOWING.value
    device.data[DreameMowerProperty.STATE.value] = DreameMowerState.MOWING.value

    # Call the method to test
    device.return_to_base()

    # Assert that the state was updated optimistically
    assert device.data[DreameMowerProperty.STATUS.value] == DreameMowerStatus.BACK_HOME.value
    # TODO: Shouldn't this be DreameMowerTaskStatus.RETURNING or similar?
    assert device.data[DreameMowerProperty.TASK_STATUS.value] == DreameMowerTaskStatus.MOWING.value
    assert device.data[DreameMowerProperty.STATE.value] == DreameMowerState.RETURNING.value

    # Assert that call_action was called with the correct action
    mock_call_action.assert_called_once_with(DreameMowerAction.DOCK)


def test_pause(device: DreameMowerDevice, mocker):
    """Test pausing the mowing task."""
    # Mock the call_action method to prevent actual network calls
    mock_call_action = mocker.patch.object(device, "call_action", return_value={"code": 0})

    # Set initial state to mowing and not paused
    device.data[DreameMowerProperty.STATUS.value] = DreameMowerStatus.CLEANING.value
    device.data[DreameMowerProperty.TASK_STATUS.value] = DreameMowerTaskStatus.MOWING.value
    device.data[DreameMowerProperty.STATE.value] = DreameMowerState.MOWING.value
    device.data[DreameMowerProperty.CLEANING_PAUSED.value] = False


    # Simulate started and not paused using PropertyMock
    mocker.patch.object(type(device.status), "started", new_callable=mocker.PropertyMock, return_value=True)
    mocker.patch.object(type(device.status), "paused", new_callable=mocker.PropertyMock, return_value=False)
    mocker.patch.object(type(device.status), "cruising", new_callable=mocker.PropertyMock, return_value=False)

    # Call the method to test
    device.pause()

    # Assert that the state was updated optimistically
    assert device.data[DreameMowerProperty.STATE.value] == DreameMowerState.PAUSED.value
    # TODO: Shouldn't this be DreameMowerTaskStatus.AUTO_CLEANING_PAUSED or similar?
    assert device.data[DreameMowerProperty.TASK_STATUS.value] == DreameMowerTaskStatus.MOWING.value
    assert device.data[DreameMowerProperty.STATUS.value] == DreameMowerStatus.PAUSED.value

    # Assert that call_action was called with the correct action
    mock_call_action.assert_called_once_with(DreameMowerAction.PAUSE)


def test_update_property_no_change(device: DreameMowerDevice, mocker):
    # Arrange
    device.data[DreameMowerProperty.STATUS.value] = DreameMowerStatus.IDLE.value
    prop_changed_spy = mocker.patch.object(device, "_property_changed")

    # Act
    result = device._update_property(DreameMowerProperty.STATUS, DreameMowerStatus.IDLE.value)

    # Assert
    assert result is None
    prop_changed_spy.assert_not_called()
    assert device.data[DreameMowerProperty.STATUS.value] == DreameMowerStatus.IDLE.value


def test_update_property_initial_set(device: DreameMowerDevice, mocker):
    # Arrange
    prop_changed_spy = mocker.patch.object(device, "_property_changed")

    # Act
    result = device._update_property(DreameMowerProperty.STATUS, DreameMowerStatus.IDLE.value)

    # Assert
    assert result == DreameMowerStatus.IDLE.value  # returns new value when no previous value
    prop_changed_spy.assert_called_once()
    assert device.data[DreameMowerProperty.STATUS.value] == DreameMowerStatus.IDLE.value


def test_update_property_changed_value(device: DreameMowerDevice, mocker):
    # Arrange previous value
    device.data[DreameMowerProperty.STATUS.value] = DreameMowerStatus.IDLE.value
    prop_changed_spy = mocker.patch.object(device, "_property_changed")

    # Act
    result = device._update_property(DreameMowerProperty.STATUS, DreameMowerStatus.CLEANING.value)

    # Assert
    assert result == DreameMowerStatus.IDLE.value  # returns previous value
    prop_changed_spy.assert_called_once()
    assert device.data[DreameMowerProperty.STATUS.value] == DreameMowerStatus.CLEANING.value


def test_update_property_callbacks(device: DreameMowerDevice, mocker):
    # Arrange
    captured = []

    def _cb(prev):
        captured.append(prev)

    device.listen(_cb, DreameMowerProperty.STATUS)

    # First set (no previous value)
    device._update_property(DreameMowerProperty.STATUS, DreameMowerStatus.IDLE.value)
    # Second update (previous value should be passed)
    device._update_property(DreameMowerProperty.STATUS, DreameMowerStatus.CLEANING.value)

    # Assert callback sequence
    assert captured == [None, DreameMowerStatus.IDLE.value]
    assert device.data[DreameMowerProperty.STATUS.value] == DreameMowerStatus.CLEANING.value


def test_update_property_state_translation_when_new_state_disabled(device: DreameMowerDevice, mocker):
    # Ensure capability.new_state is False (default)
    assert device.capability.new_state is False
    prop_changed_spy = mocker.patch.object(device, "_property_changed")

    # Use a state value > 18 that exists in DreameMowerState (REMOTE_CONTROL = 23)
    new_value = DreameMowerState.REMOTE_CONTROL.value
    result = device._update_property(DreameMowerProperty.STATE, new_value)

    # Should translate to old enum (REMOTE_CONTROL = 19 in DreameMowerStateOld)
    assert device.data[DreameMowerProperty.STATE.value] == int(DreameMowerStateOld.REMOTE_CONTROL)
    assert result == int(DreameMowerStateOld.REMOTE_CONTROL)
    prop_changed_spy.assert_called_once()


def test_update_property_state_no_translation_when_new_state_enabled(device: DreameMowerDevice, mocker):
    # Enable new_state capability
    device.capability.new_state = True
    prop_changed_spy = mocker.patch.object(device, "_property_changed")

    new_value = DreameMowerState.REMOTE_CONTROL.value
    result = device._update_property(DreameMowerProperty.STATE, new_value)

    # Should not translate
    assert device.data[DreameMowerProperty.STATE.value] == new_value
    assert result == new_value
    prop_changed_spy.assert_called_once()
