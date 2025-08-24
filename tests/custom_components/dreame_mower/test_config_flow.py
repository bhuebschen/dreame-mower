"""Test integration_blueprint config flow."""
from unittest.mock import patch, PropertyMock

from homeassistant.const import (
    CONF_PASSWORD,
    CONF_USERNAME,
    CONF_TOKEN,
    CONF_HOST,
)
from homeassistant import config_entries, data_entry_flow
import pytest

from custom_components.dreame_mower.const import (
    DOMAIN,
    CONF_TYPE,
    CONF_MAC,
)

from custom_components.dreame_mower.config_flow import (
    DREAMEHOME,
    MOVAHOME,
    LOCAL,
)

from tests.const import MOCK_DATA


# This fixture bypasses the actual setup of the integration
# since we only want to test the config flow. We test the
# actual functionality of the integration in other test modules.
@pytest.fixture(autouse=True)
def bypass_setup_fixture():
    """Prevent setup."""
    with patch(
        "custom_components.dreame_mower.async_setup_entry",
        return_value=True,
    ):
        yield

async def test_unsuccessful_local_config_flow_cannot_connect(hass):
    """Test a local config flow where connection fails."""
    # Initialize a config flow
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
    )

    # Step 1: user selects connection type
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_TYPE: LOCAL},
    )

    # Step 2: user enters host and token, but connection fails
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_HOST: MOCK_DATA[CONF_HOST],
            CONF_TOKEN: MOCK_DATA[CONF_TOKEN],
        },
    )

    # The flow should return to the 'local' step with a 'cannot_connect' error
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "local"
    assert result["errors"] == {"base": "cannot_connect"}

async def test_unsuccessful_dreamehome_config_flow_login_error(hass):
    """Test a Dreame Home config flow where login fails."""
    # Initialize a config flow
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
    )

    # Step 1: user selects connection type
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_TYPE: DREAMEHOME},
    )

    # Step 2: user enters credentials, but login fails
    with patch(
        "custom_components.dreame_mower.config_flow.DreameMowerProtocol.connect",
        side_effect=Exception("Connection failed"),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_USERNAME: MOCK_DATA[CONF_USERNAME],
                CONF_PASSWORD: MOCK_DATA[CONF_PASSWORD],
            },
        )

    # The flow should return to the 'dreame' step with a 'login_error' error
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "dreame"
    assert result["errors"] == {"base": "login_error"}

async def test_successful_dreamehome_config_flow(hass):
    """Test a successful Dreame Home config flow."""
    # Initialize a config flow
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
    )

    # Step 1: user selects connection type
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_TYPE: DREAMEHOME},
    )

    # Step 2: user enters credentials
    with patch(
        "custom_components.dreame_mower.dreame.protocol.DreameMowerDreameHomeCloudProtocol.connect",
        return_value={"mac": MOCK_DATA[CONF_MAC], "model": "dreame.mower.p2255"},
    ), patch(
        "custom_components.dreame_mower.dreame.protocol.DreameMowerDreameHomeCloudProtocol.logged_in",
        new_callable=PropertyMock,
        return_value=True,
    ), patch(
        "custom_components.dreame_mower.dreame.protocol.DreameMowerDreameHomeCloudProtocol.get_devices",
        return_value={
            "page": {
                "records": [
                    {
                        "customName": "Test Mower",
                        "deviceInfo": {"displayName": "Test Mower"},
                        "model": "dreame.mower.p2255",
                        "bindDomain": "test.domain",
                        "deviceId": "test.device.id",
                        "mac": "test.mac",
                        "did": "test.did"
                    }
                ]
            }
        },
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_USERNAME: MOCK_DATA[CONF_USERNAME],
                CONF_PASSWORD: MOCK_DATA[CONF_PASSWORD],
            },
        )

    # The flow should return to the 'options' step with no errors
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "options"
    assert result["errors"] == {}

    # Submit the options form to complete the flow
    options_input = {
        "name": "Test Mower",
        "notify": [],
        "color_scheme": "Dreame Light",
        "icon_set": "Dreame",
        "map_objects": [],
        "square": False,
        "low_resolution": False,
    }
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=options_input,
    )

    # The flow should now create the entry
    assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    
