"""Support for Dreame Mower buttons."""

from __future__ import annotations

from typing import Any
from dataclasses import dataclass
from collections.abc import Callable
from functools import partial
import copy

from homeassistant.components.button import (
    ENTITY_ID_FORMAT,
    ButtonEntity,
    ButtonEntityDescription,
)
from homeassistant.config_entries import ConfigEntry

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers import entity_registry
from homeassistant.exceptions import HomeAssistantError

from .const import DOMAIN

from .coordinator import DreameMowerDataUpdateCoordinator
from .entity import DreameMowerEntity, DreameMowerEntityDescription
from .dreame import DreameMowerAction


@dataclass
class DreameMowerButtonEntityDescription(DreameMowerEntityDescription, ButtonEntityDescription):
    """Describes Dreame Mower Button entity."""

    action_fn: Callable[[object]] = None


BUTTONS: tuple[ButtonEntityDescription, ...] = (
    DreameMowerButtonEntityDescription(
        action_key=DreameMowerAction.RESET_BLADES,
        icon="mdi:car-turbocharger",
        entity_category=EntityCategory.DIAGNOSTIC,
        exists_fn=lambda description, device: bool(
            DreameMowerEntityDescription().exists_fn(description, device)
            and device.status.blades_life is not None
        ),
    ),
    DreameMowerButtonEntityDescription(
        action_key=DreameMowerAction.RESET_SIDE_BRUSH,
        icon="mdi:pinwheel-outline",
        entity_category=EntityCategory.DIAGNOSTIC,
        exists_fn=lambda description, device: bool(
            DreameMowerEntityDescription().exists_fn(description, device)
            and device.status.side_brush_life is not None
        ),
    ),
    DreameMowerButtonEntityDescription(
        action_key=DreameMowerAction.RESET_FILTER,
        icon="mdi:air-filter",
        entity_category=EntityCategory.DIAGNOSTIC,
        exists_fn=lambda description, device: bool(
            DreameMowerEntityDescription().exists_fn(description, device) and device.status.filter_life is not None
        ),
    ),
    DreameMowerButtonEntityDescription(
        action_key=DreameMowerAction.RESET_SENSOR,
        icon="mdi:radar",
        entity_category=EntityCategory.DIAGNOSTIC,
        exists_fn=lambda description, device: not device.capability.disable_sensor_cleaning,
    ),
    DreameMowerButtonEntityDescription(
        action_key=DreameMowerAction.RESET_SILVER_ION,
        icon="mdi:shimmer",
        entity_category=EntityCategory.DIAGNOSTIC,
        exists_fn=lambda description, device: bool(
            DreameMowerEntityDescription().exists_fn(description, device)
            and device.status.silver_ion_life is not None
        ),
    ),
    DreameMowerButtonEntityDescription(
        action_key=DreameMowerAction.RESET_LENSBRUSH,
        icon="mdi:brush",
        entity_category=EntityCategory.DIAGNOSTIC,
        exists_fn=lambda description, device: bool(
            DreameMowerEntityDescription().exists_fn(description, device) and device.capability.lensbrush
        ),
    ),
    DreameMowerButtonEntityDescription(
        action_key=DreameMowerAction.RESET_SQUEEGEE,
        icon="mdi:squeegee",
        entity_category=EntityCategory.DIAGNOSTIC,
        exists_fn=lambda description, device: bool(
            DreameMowerEntityDescription().exists_fn(description, device) and device.status.squeegee_life is not None
        ),
    ),
    DreameMowerButtonEntityDescription(
        action_key=DreameMowerAction.CLEAR_WARNING,
        icon="mdi:clipboard-check-outline",
        entity_category=EntityCategory.DIAGNOSTIC,
        action_fn=lambda device: device.clear_warning(),
    ),
    DreameMowerButtonEntityDescription(
        key="start_fast_mapping",
        icon="mdi:map-plus",
        entity_category=EntityCategory.CONFIG,
        action_fn=lambda device: device.start_fast_mapping(),
        exists_fn=lambda description, device: device.capability.lidar_navigation,
    ),
    DreameMowerButtonEntityDescription(
        key="start_mapping",
        icon="mdi:broom",
        entity_category=EntityCategory.CONFIG,
        action_fn=lambda device: device.start_mapping(),
        entity_registry_enabled_default=False,
        exists_fn=lambda description, device: device.capability.lidar_navigation,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Dreame Mower Button based on a config entry."""
    coordinator: DreameMowerDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        DreameMowerButtonEntity(coordinator, description)
        for description in BUTTONS
        if description.exists_fn(description, coordinator.device)
    )

    if coordinator.device.capability.shortcuts or coordinator.device.capability.backup_map:
        update_buttons = partial(async_update_buttons, coordinator, {}, {}, async_add_entities)
        coordinator.async_add_listener(update_buttons)
        update_buttons()


@callback
def async_update_buttons(
    coordinator: DreameMowerDataUpdateCoordinator,
    current_shortcut: dict[str, list[DreameMowerShortcutButtonEntity]],
    current_map: dict[str, list[DreameMowerMapButtonEntity]],
    async_add_entities,
) -> None:
    new_entities = []
    if coordinator.device.capability.shortcuts:
        if coordinator.device.status.shortcuts:
            new_ids = set([k for k, v in coordinator.device.status.shortcuts.items()])
        else:
            new_ids = set([])

        current_ids = set(current_shortcut)

        for shortcut_id in current_ids - new_ids:
            async_remove_buttons(shortcut_id, coordinator, current_shortcut)

        for shortcut_id in new_ids - current_ids:
            current_shortcut[shortcut_id] = [
                DreameMowerShortcutButtonEntity(
                    coordinator,
                    DreameMowerButtonEntityDescription(
                        key="shortcut",
                        icon="mdi:play-speed",
                        available_fn=lambda device: not device.status.started
                        and not device.status.shortcut_task,
                    ),
                    shortcut_id,
                )
            ]
            new_entities = new_entities + current_shortcut[shortcut_id]

    if coordinator.device.capability.backup_map:
        new_indexes = set([k for k in range(1, len(coordinator.device.status.map_list) + 1)])
        current_ids = set(current_map)

        for map_index in current_ids - new_indexes:
            async_remove_buttons(map_index, coordinator, current_map)

        for map_index in new_indexes - current_ids:
            current_map[map_index] = [
                DreameMowerMapButtonEntity(
                    coordinator,
                    DreameMowerButtonEntityDescription(
                        key="backup",
                        icon="mdi:content-save",
                        entity_category=EntityCategory.DIAGNOSTIC,
                        available_fn=lambda device: not device.status.started and not device.status.map_backup_status,
                    ),
                    map_index,
                )
            ]

            new_entities = new_entities + current_map[map_index]

    if new_entities:
        async_add_entities(new_entities)


def async_remove_buttons(
    id: str,
    coordinator: DreameMowerDataUpdateCoordinator,
    current: dict[str, DreameMowerButtonEntity],
) -> None:
    registry = entity_registry.async_get(coordinator.hass)
    entities = current[id]
    for entity in entities:
        if entity.entity_id in registry.entities:
            registry.async_remove(entity.entity_id)
    del current[id]


class DreameMowerButtonEntity(DreameMowerEntity, ButtonEntity):
    """Defines a Dreame Mower Button entity."""

    def __init__(
        self,
        coordinator: DreameMowerDataUpdateCoordinator,
        description: DreameMowerButtonEntityDescription,
    ) -> None:
        """Initialize a Dreame Mower Button entity."""
        super().__init__(coordinator, description)
        self._generate_entity_id(ENTITY_ID_FORMAT)

    async def async_press(self, **kwargs: Any) -> None:
        """Press the button."""
        if not self.available:
            raise HomeAssistantError("Entity unavailable")

        if self.entity_description.action_fn is not None:
            await self._try_command(
                "Unable to call %s",
                self.entity_description.action_fn,
                self.device,
            )
        elif self.entity_description.action_key is not None:
            await self._try_command(
                "Unable to call %s",
                self.device.call_action,
                self.entity_description.action_key,
            )


class DreameMowerShortcutButtonEntity(DreameMowerEntity, ButtonEntity):
    """Defines a Dreame Mower Shortcut Button entity."""

    def __init__(
        self,
        coordinator: DreameMowerDataUpdateCoordinator,
        description: DreameMowerButtonEntityDescription,
        shortcut_id: int,
    ) -> None:
        """Initialize a Dreame Mower Shortcut Button entity."""
        self.shortcut_id = shortcut_id
        self.shortcut = None
        self.shortcuts = None
        if coordinator.device and coordinator.device.status.shortcuts:
            self.shortcuts = copy.deepcopy(coordinator.device.status.shortcuts)
            for k, v in self.shortcuts.items():
                if k == self.shortcut_id:
                    self.shortcut = v
                    break

        super().__init__(coordinator, description)
        self.id = shortcut_id
        if self.id >= 32:
            self.id = self.id - 31
        self._attr_unique_id = f"{self.device.mac}_shortcut_{self.id}"
        self.entity_id = f"button.{self.device.name.lower()}_shortcut_{self.id}"

    def _set_id(self) -> None:
        """Set name of the entity"""
        key = "shortcut"
        if self.shortcut:
            name = self.shortcut.name
            if name.lower().startswith(key):
                name = name[8:]
            name = f"{key}_{name}"
        else:
            name = f"{key}_{self.id}"

        self._attr_name = f"{self.device.name} {name.replace('_', ' ').title()}"

    @callback
    def _handle_coordinator_update(self) -> None:
        if self.shortcuts != self.device.status.shortcuts:
            self.shortcuts = copy.deepcopy(self.device.status.shortcuts)
            if self.shortcuts and self.shortcut_id in self.shortcuts:
                if self.shortcut != self.shortcuts[self.shortcut_id]:
                    self.shortcut = self.shortcuts[self.shortcut_id]
                    self._set_id()
            elif self.shortcut:
                self.shortcut = None
                self._set_id()

        self.async_write_ha_state()

    @property
    def extra_state_attributes(self) -> dict[str, str] | None:
        """Return the extra state attributes of the entity."""
        return self.shortcut.__dict__

    async def async_press(self, **kwargs: Any) -> None:
        """Press the button."""
        if not self.available:
            raise HomeAssistantError("Entity unavailable")

        await self._try_command(
            "Unable to call %s",
            self.device.start_shortcut,
            self.shortcut_id,
        )


class DreameMowerMapButtonEntity(DreameMowerEntity, ButtonEntity):
    """Defines a Dreame Mower Map Button entity."""

    def __init__(
        self,
        coordinator: DreameMowerDataUpdateCoordinator,
        description: DreameMowerButtonEntityDescription,
        map_index: int,
    ) -> None:
        """Initialize a Dreame Mower Map Button entity."""
        self.map_index = map_index
        map_data = coordinator.device.get_map(self.map_index)
        self._map_name = map_data.custom_name if map_data else None
        super().__init__(coordinator, description)
        self._set_id()
        self._attr_unique_id = f"{self.device.mac}_backup_map_{self.map_index}"
        self.entity_id = f"button.{self.device.name.lower()}_backup_map_{self.map_index}"

    def _set_id(self) -> None:
        """Set name of the entity"""
        name = (
            f"{self.map_index}"
            if self._map_name is None
            else f"{self._map_name.replace('_', ' ').replace('-', ' ').title()}"
        )
        self._attr_name = f"{self.device.name} Backup Saved Map {name}"

    @callback
    def _handle_coordinator_update(self) -> None:
        if self.device:
            map_data = self.device.get_map(self.map_index)
            if map_data and self._map_name != map_data.custom_name:
                self._map_name = map_data.custom_name
                self._set_id()

        self.async_write_ha_state()

    async def async_press(self, **kwargs: Any) -> None:
        """Press the button."""
        if not self.available:
            raise HomeAssistantError("Entity unavailable")

        await self._try_command(
            "Unable to call %s",
            self.device.backup_map,
            self.device.get_map(self.map_index).map_id,
        )
