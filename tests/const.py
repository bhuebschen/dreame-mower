"""Constants for dreame_mower tests."""

from homeassistant.const import (
    CONF_PASSWORD,
    CONF_USERNAME,
    CONF_TOKEN,
    CONF_HOST,
    CONF_NAME,
)

from custom_components.dreame_mower.const import (
    CONF_ACCOUNT_TYPE,
    CONF_COUNTRY,
    CONF_DID,
    CONF_MAC,
    CONF_NOTIFY,
    CONF_PREFER_CLOUD,
)

# Mock config data to be used across multiple tests
MOCK_DATA = {
    CONF_USERNAME: "test_username",
    CONF_PASSWORD: "test_password",
    CONF_TOKEN: "12345678901234567890123456789012",
    CONF_HOST: "127.0.0.1",
    CONF_NAME: "Test Mower",
    CONF_ACCOUNT_TYPE: "dreame",
    CONF_COUNTRY: "eu",
    CONF_MAC: "AB:CD:EF:12:34:56",
    CONF_DID: "did123",
}

MOCK_OPTIONS = {
    CONF_PREFER_CLOUD: True,
    CONF_NOTIFY: [],
}
