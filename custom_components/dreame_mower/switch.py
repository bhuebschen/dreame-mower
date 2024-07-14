"""Support for Dreame Mower switches."""

from __future__ import annotations

from typing import Any
from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.switch import (
    ENTITY_ID_FORMAT,
    SwitchEntity,
    SwitchEntityDescription,
)
from homeassistant.config_entries import ConfigEntry

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.exceptions import HomeAssistantError

from .const import DOMAIN

from .coordinator import DreameMowerDataUpdateCoordinator
from .entity import DreameMowerEntity, DreameMowerEntityDescription
from .dreame import (
    DreameMowerProperty,
    DreameMowerAutoSwitchProperty,
    DreameMowerStrAIProperty,
    DreameMowerAIProperty,
)


@dataclass
class DreameMowerSwitchEntityDescription(DreameMowerEntityDescription, SwitchEntityDescription):
    """Describes Dreame Mower Switch entity."""

    set_fn: Callable[[object, int]] = None


SWITCHES: tuple[DreameMowerSwitchEntityDescription, ...] = (
    DreameMowerSwitchEntityDescription(
        property_key=DreameMowerProperty.RESUME_CLEANING,
        value_fn=lambda value, device: bool(value),
        icon="mdi:play-pause",
        entity_category=EntityCategory.CONFIG,
    ),
    DreameMowerSwitchEntityDescription(
        property_key=DreameMowerProperty.OBSTACLE_AVOIDANCE,
        icon_fn=lambda value, device: "mdi:video-3d-off" if value == 0 else "mdi:video-3d",
        entity_category=EntityCategory.CONFIG,
    ),
    DreameMowerSwitchEntityDescription(
        property_key=DreameMowerProperty.CUSTOMIZED_CLEANING,
        icon="mdi:home-search",
    ),
    DreameMowerSwitchEntityDescription(
        property_key=DreameMowerProperty.CHILD_LOCK,
        icon_fn=lambda value, device: "mdi:lock-off" if value == 0 else "mdi:lock",
        entity_category=EntityCategory.CONFIG,
    ),
    DreameMowerSwitchEntityDescription(
        key="dnd",
        name="DnD",
        icon_fn=lambda value, device: "mdi:minus-circle-off-outline" if not value else "mdi:minus-circle-outline",
        entity_category=EntityCategory.CONFIG,
    ),
    DreameMowerSwitchEntityDescription(
        property_key=DreameMowerProperty.MULTI_FLOOR_MAP,
        icon_fn=lambda value, device: "mdi:layers-off" if value == 0 else "mdi:layers",
        entity_category=EntityCategory.CONFIG,
        exists_fn=lambda description, device: bool(
            DreameMowerEntityDescription().exists_fn(description, device) and device.capability.lidar_navigation
        ),
    ),
    DreameMowerSwitchEntityDescription(
        property_key=DreameMowerProperty.INTELLIGENT_RECOGNITION,
        icon_fn=lambda value, device: "mdi:wifi-remove" if value == 0 else "mdi:wifi-marker",
        entity_category=EntityCategory.CONFIG,
        exists_fn=lambda description, device: device.capability.wifi_map
        and DreameMowerEntityDescription().exists_fn(description, device),
    ),
    DreameMowerSwitchEntityDescription(
        property_key=DreameMowerProperty.MAP_SAVING,
        icon="mdi:map-legend",
        entity_category=EntityCategory.CONFIG,
        format_fn=lambda value, device: int(value),
    ),
    DreameMowerSwitchEntityDescription(
        property_key=DreameMowerProperty.VOICE_ASSISTANT,
        icon_fn=lambda value, device: "mdi:microphone-message-off" if not value else "mdi:microphone-message",
        entity_category=EntityCategory.CONFIG,
        format_fn=lambda value, device: int(value),
    ),
    DreameMowerSwitchEntityDescription(
        key="cleaning_sequence",
        icon="mdi:order-numeric-ascending",
        value_fn=lambda value, device: device.status.custom_order,
        exists_fn=lambda description, device: device.capability.customized_cleaning and device.capability.map,
        set_fn=lambda device, value: device.set_cleaning_sequence(
            []
            if not value
            else (
                device.status.previous_cleaning_sequence
                if device.status.previous_cleaning_sequence
                else list(sorted(device.status.current_segments.keys()))
            )
        ),
        format_fn=lambda value, device: int(value),
        entity_category=None,
    ),
    DreameMowerSwitchEntityDescription(
        property_key=DreameMowerAIProperty.AI_OBSTACLE_DETECTION,
        icon_fn=lambda value, device: "mdi:robot-off" if not value else "mdi:robot",
        entity_category=EntityCategory.CONFIG,
    ),
    DreameMowerSwitchEntityDescription(
        property_key=DreameMowerAIProperty.AI_OBSTACLE_IMAGE_UPLOAD,
        icon="mdi:cloud-upload",
        entity_category=EntityCategory.CONFIG,
    ),
    DreameMowerSwitchEntityDescription(
        property_key=DreameMowerAIProperty.AI_OBSTACLE_PICTURE,
        icon_fn=lambda value, device: "mdi:camera-off" if not value else "mdi:camera",
        entity_category=EntityCategory.CONFIG,
    ),
    DreameMowerSwitchEntityDescription(
        property_key=DreameMowerAIProperty.AI_PET_DETECTION,
        icon_fn=lambda value, device: "mdi:dog-side-off" if not value else "mdi:dog-side",
        entity_category=EntityCategory.CONFIG,
    ),
    DreameMowerSwitchEntityDescription(
        property_key=DreameMowerStrAIProperty.AI_HUMAN_DETECTION,
        icon_fn=lambda value, device: "mdi:account-off" if not value else "mdi:account",
        entity_category=EntityCategory.CONFIG,
    ),
    DreameMowerSwitchEntityDescription(
        property_key=DreameMowerAIProperty.FUZZY_OBSTACLE_DETECTION,
        icon="mdi:blur-linear",
        entity_category=EntityCategory.CONFIG,
    ),
    DreameMowerSwitchEntityDescription(
        property_key=DreameMowerAIProperty.AI_PET_AVOIDANCE,
        icon="mdi:dog-service",
        exists_fn=lambda description, device: device.capability.pet_detective,
        entity_category=EntityCategory.CONFIG,
    ),
    DreameMowerSwitchEntityDescription(
        property_key=DreameMowerAIProperty.PET_PICTURE,
        icon="mdi:cat",
        entity_category=EntityCategory.CONFIG,
    ),
    DreameMowerSwitchEntityDescription(
        property_key=DreameMowerAIProperty.PET_FOCUSED_DETECTION,
        icon="mdi:dog",
        exists_fn=lambda description, device: device.capability.pet_furniture,
        entity_category=EntityCategory.CONFIG,
    ),
    DreameMowerSwitchEntityDescription(
        property_key=DreameMowerAutoSwitchProperty.FILL_LIGHT,
        icon_fn=lambda value, device: "mdi:lightbulb-off" if not value else "mdi:lightbulb-on",
        exists_fn=lambda description, device: bool(
            device.capability.fill_light and DreameMowerEntityDescription().exists_fn(description, device)
        ),
        entity_category=EntityCategory.CONFIG,
    ),
    DreameMowerSwitchEntityDescription(
        property_key=DreameMowerAutoSwitchProperty.COLLISION_AVOIDANCE,
        icon_fn=lambda value, device: "mdi:sign-direction-remove" if not value else "mdi:sign-direction",
        entity_category=EntityCategory.CONFIG,
    ),
    DreameMowerSwitchEntityDescription(
        property_key=DreameMowerAutoSwitchProperty.STAIN_AVOIDANCE,
        icon="mdi:liquid-spot",
        format_fn=lambda value, device: 2 if value else 1,
        exists_fn=lambda description, device: bool(
            device.capability.fluid_detection and DreameMowerEntityDescription().exists_fn(description, device)
        ),
        entity_category=EntityCategory.CONFIG,
    ),
    DreameMowerSwitchEntityDescription(
        property_key=DreameMowerAutoSwitchProperty.FLOOR_DIRECTION_CLEANING,
        exists_fn=lambda description, device: bool(
            device.capability.floor_direction_cleaning
            and DreameMowerEntityDescription().exists_fn(description, device)
        ),
        icon="mdi:arrow-decision-auto",
        entity_category=EntityCategory.CONFIG,
    ),
    DreameMowerSwitchEntityDescription(
        property_key=DreameMowerAutoSwitchProperty.PET_FOCUSED_CLEANING,
        exists_fn=lambda description, device: bool(
            device.capability.pet_detective and DreameMowerEntityDescription().exists_fn(description, device)
        ),
        icon="mdi:paw",
        entity_category=EntityCategory.CONFIG,
    ),
    DreameMowerSwitchEntityDescription(
        property_key=DreameMowerAutoSwitchProperty.GAP_CLEANING_EXTENSION,
        icon="mdi:plus-circle-multiple",
        exists_fn=lambda description, device: bool(
            DreameMowerEntityDescription().exists_fn(description, device)
        ),
        entity_category=EntityCategory.CONFIG,
    ),
    DreameMowerSwitchEntityDescription(
        property_key=DreameMowerProperty.OFF_PEAK_CHARGING,
        icon="mdi:battery-clock",
        entity_category=EntityCategory.CONFIG,
    ),
    DreameMowerSwitchEntityDescription(
        property_key=DreameMowerAutoSwitchProperty.AUTO_CHARGING,
        icon="mdi:battery-sync",
        exists_fn=lambda description, device: bool(
            device.capability.auto_charging and DreameMowerEntityDescription().exists_fn(description, device)
        ),
        entity_category=EntityCategory.CONFIG,
    ),
    DreameMowerSwitchEntityDescription(
        property_key=DreameMowerAutoSwitchProperty.HUMAN_FOLLOW,
        icon_fn=lambda value, device: "mdi:account-off" if not value else "mdi:account-arrow-left",
        exists_fn=lambda description, device: bool(
            DreameMowerEntityDescription().exists_fn(description, device)
        ),
        entity_category=EntityCategory.CONFIG,
    ),
    DreameMowerSwitchEntityDescription(
        property_key=DreameMowerAutoSwitchProperty.STREAMING_VOICE_PROMPT,
        icon_fn=lambda value, device: "mdi:account-tie-voice-off" if not value else "mdi:account-tie-voice",
        exists_fn=lambda description, device: bool(
            device.capability.camera_streaming and DreameMowerEntityDescription().exists_fn(description, device)
        ),
        entity_category=EntityCategory.CONFIG,
    ),
    DreameMowerSwitchEntityDescription(
        key="camera_light_brightness_auto",
        icon_fn=lambda value, device: "mdi:brightness-percent" if not value else "mdi:brightness-auto",
        value_fn=lambda value, device: bool(device.status.camera_light_brightness == 101),
        exists_fn=lambda description, device: device.capability.camera_streaming
        and device.capability.fill_light,  # and DreameMowerEntityDescription().exists_fn(description, device),
        format_fn=lambda value, device: 101 if value else 40,
        entity_category=EntityCategory.CONFIG,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Dreame Mower switch based on a config entry."""
    coordinator: DreameMowerDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        DreameMowerSwitchEntity(coordinator, description)
        for description in SWITCHES
        if description.exists_fn(description, coordinator.device)
    )


class DreameMowerSwitchEntity(DreameMowerEntity, SwitchEntity):
    """Defines a Dreame Mower Switch entity."""

    entity_description: DreameMowerSwitchEntityDescription

    def __init__(
        self,
        coordinator: DreameMowerDataUpdateCoordinator,
        description: DreameMowerSwitchEntityDescription,
    ) -> None:
        """Initialize a Dreame Mower switch entity."""
        if description.set_fn is None and (description.property_key is not None or description.key is not None):
            if description.property_key is not None:
                prop = f"set_{description.property_key.name.lower()}"
            else:
                prop = f"set_{description.key.lower()}"
            if hasattr(coordinator.device, prop):
                description.set_fn = lambda device, value: getattr(device, prop)(value)

        super().__init__(coordinator, description)
        self._generate_entity_id(ENTITY_ID_FORMAT)
        self._attr_is_on = bool(self.native_value)

    @callback
    def _handle_coordinator_update(self) -> None:
        self._attr_is_on = bool(self.native_value)
        super()._handle_coordinator_update()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the Dreame Mower sync receive switch."""
        await self.async_set_state(0)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the Dreame Mower sync receive switch."""
        await self.async_set_state(1)

    async def async_set_state(self, state) -> None:
        """Turn on or off the Dreame Mower sync receive switch."""
        if not self.available:
            raise HomeAssistantError("Entity unavailable")

        value = int(state)
        if self.entity_description.format_fn is not None:
            value = self.entity_description.format_fn(state, self.device)

        if self.entity_description.set_fn is not None:
            await self._try_command("Unable to call: %s", self.entity_description.set_fn, self.device, value)
        elif self.entity_description.property_key is not None:
            await self._try_command(
                "Unable to call: %s",
                self.device.set_property,
                self.entity_description.property_key,
                value,
            )
