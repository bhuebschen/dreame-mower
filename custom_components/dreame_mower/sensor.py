"""Support for Dreame Mower sensors."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from homeassistant.components.sensor import (
    ENTITY_ID_FORMAT,
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry

from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    DOMAIN,
    UNIT_MINUTES,
    UNIT_HOURS,
    UNIT_PERCENT,
    UNIT_AREA,
    UNIT_TIMES,
    UNIT_DAYS,
)
from .dreame import (
    DreameMowerProperty,
    DreameMowerRelocationStatus,
    DreameMowerStreamStatus,
)
from .dreame.const import ATTR_VALUE
from .dreame.types import ATTR_ZONE_ID, ATTR_ZONE_ICON

from .coordinator import DreameMowerDataUpdateCoordinator
from .entity import DreameMowerEntity, DreameMowerEntityDescription


STREAM_STATUS_TO_ICON = {
    DreameMowerStreamStatus.IDLE: "mdi:webcam",
    DreameMowerStreamStatus.VIDEO: "mdi:cctv",
    DreameMowerStreamStatus.AUDIO: "mdi:microphone",
    DreameMowerStreamStatus.RECORDING: "mdi:record-rec",
}

RELOCATION_STATUS_TO_ICON = {
    DreameMowerRelocationStatus.LOCATED: "mdi:map-marker-radius",
    DreameMowerRelocationStatus.SUCCESS: "mdi:map-marker-check",
    DreameMowerRelocationStatus.FAILED: "mdi:map-marker-alert",
    DreameMowerRelocationStatus.LOCATING: "mdi:map-marker-distance",
}


@dataclass
class DreameMowerSensorEntityDescription(DreameMowerEntityDescription, SensorEntityDescription):
    """Describes DreameMower sensor entity."""


SENSORS: tuple[DreameMowerSensorEntityDescription, ...] = (
    DreameMowerSensorEntityDescription(
        property_key=DreameMowerProperty.CLEANING_TIME,
        icon="mdi:timer-sand",
        native_unit_of_measurement=UNIT_MINUTES,
    ),
    DreameMowerSensorEntityDescription(
        property_key=DreameMowerProperty.CLEANING_TIME,
        name="Mapping Time",
        key="mapping_time",
        icon="mdi:map-clock",
        native_unit_of_measurement=UNIT_MINUTES,
        available_fn=lambda device: device.status.fast_mapping,
        exists_fn=lambda description, device: device.capability.lidar_navigation,
    ),
    DreameMowerSensorEntityDescription(
        property_key=DreameMowerProperty.CLEANED_AREA,
        icon="mdi:ruler-square",
        native_unit_of_measurement=UNIT_AREA,
    ),
    DreameMowerSensorEntityDescription(
        property_key=DreameMowerProperty.STATE,
        icon="mdi:robot-mower",
    ),
    DreameMowerSensorEntityDescription(
        property_key=DreameMowerProperty.STATUS,
        icon="mdi:mower",
    ),
    DreameMowerSensorEntityDescription(
        property_key=DreameMowerProperty.RELOCATION_STATUS,
        icon_fn=lambda value, device: RELOCATION_STATUS_TO_ICON.get(
            device.status.relocation_status, "mdi:map-marker-radius"
        ),
    ),
    DreameMowerSensorEntityDescription(
        property_key=DreameMowerProperty.TASK_TYPE,
        icon="mdi:sitemap",
        exists_fn=lambda description, device: device.capability.task_type,
    ),
    DreameMowerSensorEntityDescription(
        property_key=DreameMowerProperty.STREAM_STATUS,
        icon_fn=lambda value, device: STREAM_STATUS_TO_ICON.get(device.status.stream_status, "mdi:webcam-off"),
        exists_fn=lambda description, device: device.capability.camera_streaming
        or DreameMowerEntityDescription().exists_fn(description, device),
    ),
    DreameMowerSensorEntityDescription(
        property_key=DreameMowerProperty.ERROR,
        icon_fn=lambda value, device: (
            "mdi:alert-circle-outline"
            if device.status.has_error
            else "mdi:alert-outline" if device.status.has_warning else "mdi:check-circle-outline"
        ),
        attrs_fn=lambda device: {
            ATTR_VALUE: device.status.error,
            "faults": device.status.faults,
            "description": device.status.error_description[0],
        },
    ),
    DreameMowerSensorEntityDescription(
        property_key=DreameMowerProperty.CHARGING_STATUS,
        icon="mdi:home-lightning-bolt",
    ),
    DreameMowerSensorEntityDescription(
        property_key=DreameMowerProperty.BATTERY_LEVEL,
        device_class=SensorDeviceClass.BATTERY,
        native_unit_of_measurement=UNIT_PERCENT,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    DreameMowerSensorEntityDescription(
        property_key=DreameMowerProperty.BLADES_LEFT,
        icon="mdi:car-turbocharger",
        native_unit_of_measurement=UNIT_PERCENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        # entity_registry_enabled_default=False,
    ),
    DreameMowerSensorEntityDescription(
        property_key=DreameMowerProperty.BLADES_TIME_LEFT,
        icon="mdi:car-turbocharger",
        native_unit_of_measurement=UNIT_HOURS,
        entity_category=EntityCategory.DIAGNOSTIC,
        # entity_registry_enabled_default=False,
    ),
    DreameMowerSensorEntityDescription(
        property_key=DreameMowerProperty.SIDE_BRUSH_LEFT,
        icon="mdi:pinwheel-outline",
        native_unit_of_measurement=UNIT_PERCENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        # entity_registry_enabled_default=False,
    ),
    DreameMowerSensorEntityDescription(
        property_key=DreameMowerProperty.SIDE_BRUSH_TIME_LEFT,
        icon="mdi:pinwheel-outline",
        native_unit_of_measurement=UNIT_HOURS,
        entity_category=EntityCategory.DIAGNOSTIC,
        # entity_registry_enabled_default=False,
    ),
    DreameMowerSensorEntityDescription(
        property_key=DreameMowerProperty.FILTER_LEFT,
        icon="mdi:air-filter",
        native_unit_of_measurement=UNIT_PERCENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        # entity_registry_enabled_default=False,
    ),
    DreameMowerSensorEntityDescription(
        property_key=DreameMowerProperty.FILTER_TIME_LEFT,
        icon="mdi:air-filter",
        native_unit_of_measurement=UNIT_HOURS,
        entity_category=EntityCategory.DIAGNOSTIC,
        # entity_registry_enabled_default=False,
    ),
    DreameMowerSensorEntityDescription(
        property_key=DreameMowerProperty.SENSOR_DIRTY_LEFT,
        icon="mdi:radar",
        native_unit_of_measurement=UNIT_PERCENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        # entity_registry_enabled_default=False,
        exists_fn=lambda description, device: not device.capability.disable_sensor_cleaning,
    ),
    DreameMowerSensorEntityDescription(
        property_key=DreameMowerProperty.SENSOR_DIRTY_TIME_LEFT,
        icon="mdi:radar",
        native_unit_of_measurement=UNIT_HOURS,
        entity_category=EntityCategory.DIAGNOSTIC,
        # entity_registry_enabled_default=False,
        exists_fn=lambda description, device: not device.capability.disable_sensor_cleaning,
    ),
    DreameMowerSensorEntityDescription(
        property_key=DreameMowerProperty.TANK_FILTER_LEFT,
        icon="mdi:air-filter",
        native_unit_of_measurement=UNIT_PERCENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        # entity_registry_enabled_default=False,
    ),
    DreameMowerSensorEntityDescription(
        property_key=DreameMowerProperty.TANK_FILTER_TIME_LEFT,
        icon="mdi:air-filter",
        native_unit_of_measurement=UNIT_HOURS,
        entity_category=EntityCategory.DIAGNOSTIC,
        # entity_registry_enabled_default=False,
    ),
    DreameMowerSensorEntityDescription(
        property_key=DreameMowerProperty.SILVER_ION_LEFT,
        icon="mdi:shimmer",
        native_unit_of_measurement=UNIT_PERCENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        # entity_registry_enabled_default=False,
    ),
    DreameMowerSensorEntityDescription(
        property_key=DreameMowerProperty.SILVER_ION_TIME_LEFT,
        icon="mdi:shimmer",
        native_unit_of_measurement=UNIT_DAYS,
        entity_category=EntityCategory.DIAGNOSTIC,
        # entity_registry_enabled_default=False,
    ),
    DreameMowerSensorEntityDescription(
        property_key=DreameMowerProperty.LENSBRUSH_LEFT,
        icon="mdi:brush",
        native_unit_of_measurement=UNIT_PERCENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        exists_fn=lambda description, device: bool(
            DreameMowerEntityDescription().exists_fn(description, device) and device.capability.lensbrush
        )
        # entity_registry_enabled_default=False,
    ),
    DreameMowerSensorEntityDescription(
        property_key=DreameMowerProperty.LENSBRUSH_TIME_LEFT,
        icon="mdi:brush-outline",
        native_unit_of_measurement=UNIT_DAYS,
        entity_category=EntityCategory.DIAGNOSTIC,
        exists_fn=lambda description, device: bool(
            DreameMowerEntityDescription().exists_fn(description, device) and device.capability.lensbrush
        )
        # entity_registry_enabled_default=False,
    ),
    DreameMowerSensorEntityDescription(
        property_key=DreameMowerProperty.SQUEEGEE_LEFT,
        icon="mdi:squeegee",
        native_unit_of_measurement=UNIT_PERCENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        # entity_registry_enabled_default=False,
    ),
    DreameMowerSensorEntityDescription(
        property_key=DreameMowerProperty.SQUEEGEE_TIME_LEFT,
        icon="mdi:squeegee",
        native_unit_of_measurement=UNIT_DAYS,
        entity_category=EntityCategory.DIAGNOSTIC,
        # entity_registry_enabled_default=False,
    ),
    DreameMowerSensorEntityDescription(
        property_key=DreameMowerProperty.FIRST_CLEANING_DATE,
        icon="mdi:calendar-start",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda value, device: datetime.fromtimestamp(value).replace(
            tzinfo=datetime.now().astimezone().tzinfo
        ),
        # entity_registry_enabled_default=False,
    ),
    DreameMowerSensorEntityDescription(
        property_key=DreameMowerProperty.TOTAL_CLEANING_TIME,
        icon="mdi:timer-outline",
        native_unit_of_measurement=UNIT_MINUTES,
        device_class=SensorDeviceClass.DURATION,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    DreameMowerSensorEntityDescription(
        property_key=DreameMowerProperty.CLEANING_COUNT,
        icon="mdi:counter",
        native_unit_of_measurement=UNIT_TIMES,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    DreameMowerSensorEntityDescription(
        property_key=DreameMowerProperty.TOTAL_CLEANED_AREA,
        icon="mdi:set-square",
        native_unit_of_measurement=UNIT_AREA,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    DreameMowerSensorEntityDescription(
        key="current_zone",
        icon="mdi:home-map-marker",
        value_fn=lambda value, device: device.status.current_zone.name,
        exists_fn=lambda description, device: device.capability.map and device.capability.lidar_navigation,
        attrs_fn=lambda device: {
            ATTR_ZONE_ID: device.status.current_zone.segment_id,
            ATTR_ZONE_ICON: device.status.current_zone.icon,
        },
    ),
    DreameMowerSensorEntityDescription(
        key="cleaning_history",
        icon="mdi:clipboard-text-clock",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda value, device: device.status.last_cleaning_time,
        exists_fn=lambda description, device: device.capability.map,
        attrs_fn=lambda device: device.status.cleaning_history,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    DreameMowerSensorEntityDescription(
        key="cruising_history",
        icon="mdi:map-marker-path",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda value, device: device.status.last_cruising_time,
        exists_fn=lambda description, device: device.capability.map and device.capability.cruising,
        attrs_fn=lambda device: device.status.cruising_history,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    DreameMowerSensorEntityDescription(
        property_key=DreameMowerProperty.CLEANING_PROGRESS,
        icon="mdi:home-percent",
        native_unit_of_measurement=UNIT_PERCENT,
        entity_category=None,
    ),
    DreameMowerSensorEntityDescription(
        key="firmware_version",
        icon="mdi:chip",
        value_fn=lambda value, device: device.info.version,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Dreame Mower sensor based on a config entry."""
    coordinator: DreameMowerDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        DreameMowerSensorEntity(coordinator, description)
        for description in SENSORS
        if description.exists_fn(description, coordinator.device)
    )


class DreameMowerSensorEntity(DreameMowerEntity, SensorEntity):
    """Defines a Dreame Mower sensor entity."""

    def __init__(
        self,
        coordinator: DreameMowerDataUpdateCoordinator,
        description: DreameMowerSensorEntityDescription,
    ) -> None:
        """Initialize a Dreame Mower sensor entity."""
        if description.value_fn is None and (description.property_key is not None or description.key is not None):
            if description.property_key is not None:
                prop = f"{description.property_key.name.lower()}_name"
            else:
                prop = f"{description.key.lower()}_name"
            if hasattr(coordinator.device.status, prop):
                description.value_fn = lambda value, device: getattr(device.status, prop)

        super().__init__(coordinator, description)
        self._generate_entity_id(ENTITY_ID_FORMAT)
