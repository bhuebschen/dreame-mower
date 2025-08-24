import pytest
from custom_components.dreame_mower.dreame.device import DreameMowerDevice
from custom_components.dreame_mower.dreame.types import (
    DreameMowerAction,
    DreameMowerTaskStatus,
    DreameMowerStatus,
    DreameMowerState,
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

def test_stop_mowing(device: DreameMowerDevice, mocker):
    """Test stopping a mowing task."""
    # Mock the call_action method to prevent actual network calls
    mock_call_action = mocker.patch.object(device, "call_action", return_value={"code": 0})

    # Set initial state to mowing
    device.data[DreameMowerProperty.STATUS.value] = DreameMowerStatus.CLEANING.value
    device.data[DreameMowerProperty.TASK_STATUS.value] = DreameMowerTaskStatus.MOWING.value
    device.data[DreameMowerProperty.STATE.value] = DreameMowerState.MOWING.value

    # Call the method to test
    device.stop()

    # Assert that the state was updated optimistically
    assert device.data[DreameMowerProperty.STATUS.value] == DreameMowerStatus.STANDBY.value
    assert device.data[DreameMowerProperty.TASK_STATUS.value] == DreameMowerTaskStatus.COMPLETED.value

    # TODO: Shouldn't this be IDLE? Currently we keep it as MOWING.
    # The state may only change to IDLE after confirmation from the hardware/cloud,
    # or after a subsequent update. For now, we assert the optimistic update keeps it as MOWING.
    assert device.data[DreameMowerProperty.STATE.value] == DreameMowerState.MOWING.value

    # Assert that call_action was called with the correct action
    mock_call_action.assert_called_once_with(DreameMowerAction.STOP)

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

