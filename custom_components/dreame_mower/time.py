"""Support for Dreame Mower times."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import time
from typing import Callable

from homeassistant.components.time import (
    ENTITY_ID_FORMAT,
    TimeEntity,
    TimeEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.exceptions import HomeAssistantError

from .const import DOMAIN

from .coordinator import DreameMowerDataUpdateCoordinator
from .entity import DreameMowerEntity, DreameMowerEntityDescription


@dataclass
class DreameMowerTimeEntityDescription(DreameMowerEntityDescription, TimeEntityDescription):
    """Describes Dreame Mower Time entity."""

    set_fn: Callable[[object, int]] = None


TIMES: tuple[DreameMowerTimeEntityDescription, ...] = (
    DreameMowerTimeEntityDescription(
        key="dnd_start",
        name="DnD Start",
        icon="mdi:clock-start",
        entity_category=EntityCategory.CONFIG,
        exists_fn=lambda description, device: device.capability.dnd,
    ),
    DreameMowerTimeEntityDescription(
        key="dnd_end",
        name="DnD End",
        icon="mdi:clock-end",
        entity_category=EntityCategory.CONFIG,
        exists_fn=lambda description, device: device.capability.dnd,
    ),
    DreameMowerTimeEntityDescription(
        key="off_peak_charging_start",
        name="Off-Peak Charging Start",
        icon="mdi:battery-lock-open",
        entity_category=EntityCategory.CONFIG,
        exists_fn=lambda description, device: device.capability.off_peak_charging,
    ),
    DreameMowerTimeEntityDescription(
        key="off_peak_charging_end",
        name="Off-Peak Charging End",
        icon="mdi:battery-lock",
        entity_category=EntityCategory.CONFIG,
        exists_fn=lambda description, device: device.capability.off_peak_charging,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Dreame Mower time based on a config entry."""
    coordinator: DreameMowerDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        DreameMowerTimeEntity(coordinator, description)
        for description in TIMES
        if description.exists_fn(description, coordinator.device)
    )


class DreameMowerTimeEntity(DreameMowerEntity, TimeEntity):
    """Defines a Dreame Mower time."""

    def __init__(
        self,
        coordinator: DreameMowerDataUpdateCoordinator,
        description: DreameMowerTimeEntityDescription,
    ) -> None:
        """Initialize Dreame Mower time."""
        if description.set_fn is None and (description.property_key is not None or description.key is not None):
            if description.property_key is not None:
                prop = f"set_{description.property_key.name.lower()}"
            else:
                prop = f"set_{description.key.lower()}"
            if hasattr(coordinator.device, prop):
                description.set_fn = lambda device, value: getattr(device, prop)(value)

        super().__init__(coordinator, description)
        self._generate_entity_id(ENTITY_ID_FORMAT)
        value = super().native_value
        if value:
            values = value.split(":")
            self._attr_native_value = time(int(values[0]), int(values[1]), 0)
        else:
            self._attr_native_value = None

    @callback
    def _handle_coordinator_update(self) -> None:
        value = super().native_value
        if value:
            values = value.split(":")
            self._attr_native_value = time(int(values[0]), int(values[1]), 0)
        else:
            self._attr_native_value = None
        super()._handle_coordinator_update()

    async def async_set_value(self, value: time) -> None:
        """Set the Dreame Mower time value."""
        if not self.available:
            raise HomeAssistantError("Entity unavailable")

        if value is None:
            raise HomeAssistantError("Invalid value")

        value = str(value)[0:-3]
        if self.entity_description.set_fn is not None:
            await self._try_command("Unable to call: %s", self.entity_description.set_fn, self.device, value)
        elif self.entity_description.property_key is not None:
            await self._try_command(
                "Unable to call: %s",
                self.device.set_property,
                self.entity_description.property_key,
                value,
            )
        else:
            raise HomeAssistantError("Not implemented")

    @property
    def native_value(self):
        """Return the current Dreame Mower time value."""
        return self._attr_native_value
