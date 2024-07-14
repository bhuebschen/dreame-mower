from __future__ import annotations

import voluptuous as vol
from typing import Final

from .coordinator import DreameMowerDataUpdateCoordinator
from .entity import DreameMowerEntity

from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv, entity_platform
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.icon import icon_for_battery_level
from homeassistant.components.lawn_mower import (
    LawnMowerActivity,
    LawnMowerEntity,
    LawnMowerEntityFeature,
)
from .recorder import MOWER_UNRECORDED_ATTRIBUTES

from .dreame.const import STATE_UNKNOWN
from .dreame import (
    DreameMowerState,
    DreameMowerAction,
    InvalidActionException,
    ACTION_AVAILABILITY,
)
from .const import (
    DOMAIN,
    FAN_SPEED_SILENT,
    FAN_SPEED_STANDARD,
    FAN_SPEED_STRONG,
    FAN_SPEED_TURBO,
    INPUT_CLEANING_SEQUENCE,
    INPUT_LANGUAGE_ID,
    INPUT_LINE,
    INPUT_MAP_ID,
    INPUT_MAP_NAME,
    INPUT_FILE_URL,
    INPUT_RECOVERY_MAP_INDEX,
    INPUT_MD5,
    INPUT_REPEATS,
    INPUT_CLEANING_MODE,
    INPUT_ROTATION,
    INPUT_SEGMENT,
    INPUT_SEGMENT_ID,
    INPUT_SEGMENT_NAME,
    INPUT_SEGMENTS_ARRAY,
    INPUT_SIZE,
    INPUT_URL,
    INPUT_VELOCITY,
    INPUT_WALL_ARRAY,
    INPUT_ZONE,
    INPUT_ZONE_ARRAY,
    INPUT_CONSUMABLE,
    INPUT_POINTS,
    INPUT_SHORTCUT_ID,
    INPUT_SHORTCUT_NAME,
    INPUT_PATHWAY_ARRAY,
    INPUT_X,
    INPUT_Y,
    INPUT_OBSTACLE_IGNORED,
    INPUT_KEY,
    INPUT_VALUE,
    SERVICE_CLEAN_ZONE,
    SERVICE_CLEAN_SEGMENT,
    SERVICE_CLEAN_SPOT,
    SERVICE_GOTO,
    SERVICE_FOLLOW_PATH,
    SERVICE_INSTALL_VOICE_PACK,
    SERVICE_MERGE_SEGMENTS,
    SERVICE_MOVE_REMOTE_CONTROL_STEP,
    SERVICE_RENAME_MAP,
    SERVICE_RENAME_SEGMENT,
    SERVICE_SET_PROPERTY,
    SERVICE_CALL_ACTION,
    SERVICE_REQUEST_MAP,
    SERVICE_SELECT_MAP,
    SERVICE_DELETE_MAP,
    SERVICE_RESTORE_MAP,
    SERVICE_RESTORE_MAP_FROM_FILE,
    SERVICE_BACKUP_MAP,
    SERVICE_SET_CLEANING_SEQUENCE,
    SERVICE_SET_CUSTOM_CLEANING,
    SERVICE_SET_RESTRICTED_ZONE,
    SERVICE_SET_PATHWAY,
    SERVICE_SET_PREDEFINED_POINTS,
    SERVICE_SPLIT_SEGMENTS,
    SERVICE_SAVE_TEMPORARY_MAP,
    SERVICE_DISCARD_TEMPORARY_MAP,
    SERVICE_REPLACE_TEMPORARY_MAP,
    SERVICE_RESET_CONSUMABLE,
    SERVICE_RENAME_SHORTCUT,
    SERVICE_SET_OBSTACLE_IGNORE,
    SERVICE_SET_ROUTER_POSITION,
    CONSUMABLE_BLADES,
    CONSUMABLE_SIDE_BRUSH,
    CONSUMABLE_FILTER,
    CONSUMABLE_TANK_FILTER,
    CONSUMABLE_SENSOR,
    CONSUMABLE_SILVER_ION,
    CONSUMABLE_LENSBRUSH,
    CONSUMABLE_SQUEEGEE,
)

SUPPORT_DREAME = (
    LawnMowerEntityFeature.START_MOWING
    | LawnMowerEntityFeature.PAUSE
    | LawnMowerEntityFeature.DOCK
)

STATE_CODE_TO_STATE: Final = {
    DreameMowerState.UNKNOWN: STATE_UNKNOWN,
    DreameMowerState.MOWING: LawnMowerActivity.MOWING,
    DreameMowerState.IDLE: LawnMowerActivity.DOCKED,
    DreameMowerState.PAUSED: LawnMowerActivity.PAUSED,
    DreameMowerState.ERROR: LawnMowerActivity.ERROR,
    DreameMowerState.RETURNING: LawnMowerActivity.MOWING,
    DreameMowerState.CHARGING: LawnMowerActivity.DOCKED,
    DreameMowerState.BUILDING: LawnMowerActivity.DOCKED,
    DreameMowerState.CHARGING_COMPLETED: LawnMowerActivity.DOCKED,
    DreameMowerState.UPGRADING: LawnMowerActivity.DOCKED,
    DreameMowerState.CLEAN_SUMMON: LawnMowerActivity.MOWING,
    DreameMowerState.STATION_RESET: LawnMowerActivity.DOCKED,
    DreameMowerState.REMOTE_CONTROL: LawnMowerActivity.MOWING,
    DreameMowerState.SMART_CHARGING: LawnMowerActivity.DOCKED,
    DreameMowerState.SECOND_CLEANING: LawnMowerActivity.MOWING,
    DreameMowerState.HUMAN_FOLLOWING: LawnMowerActivity.MOWING,
    DreameMowerState.SPOT_CLEANING: LawnMowerActivity.MOWING,
    DreameMowerState.SHORTCUT: LawnMowerActivity.MOWING,
    DreameMowerState.WAITING_FOR_TASK: LawnMowerActivity.DOCKED,
    DreameMowerState.SHORTCUT: LawnMowerActivity.MOWING,
    DreameMowerState.MONITORING: LawnMowerActivity.MOWING,
    DreameMowerState.MONITORING_PAUSED: LawnMowerActivity.DOCKED,
}

CONSUMABLE_RESET_ACTION = {
    CONSUMABLE_BLADES: DreameMowerAction.RESET_BLADES,
    CONSUMABLE_SIDE_BRUSH: DreameMowerAction.RESET_SIDE_BRUSH,
    CONSUMABLE_FILTER: DreameMowerAction.RESET_FILTER,
    CONSUMABLE_TANK_FILTER: DreameMowerAction.RESET_TANK_FILTER,
    CONSUMABLE_SENSOR: DreameMowerAction.RESET_SENSOR,
    CONSUMABLE_SILVER_ION: DreameMowerAction.RESET_SILVER_ION,
    CONSUMABLE_LENSBRUSH: DreameMowerAction.RESET_LENSBRUSH,
    CONSUMABLE_SQUEEGEE: DreameMowerAction.RESET_SQUEEGEE,
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up a Dreame Mower based on a config entry."""
    coordinator: DreameMowerDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    platform = entity_platform.current_platform.get()

    platform.async_register_entity_service(
        SERVICE_SET_PROPERTY,
        {
            vol.Required(INPUT_KEY): cv.string,
            vol.Optional(INPUT_VALUE): vol.Any(vol.Coerce(int), vol.Coerce(str), vol.Coerce(bool)),
        },
        DreameMower.async_set_property.__name__,
    )
    
    platform.async_register_entity_service(
        SERVICE_CALL_ACTION,
        {
            vol.Required(INPUT_KEY): cv.string
        },
        DreameMower.async_call_action.__name__,
    )
    
    platform.async_register_entity_service(
        SERVICE_REQUEST_MAP,
        {},
        DreameMower.async_request_map.__name__,
    )

    platform.async_register_entity_service(
        SERVICE_SELECT_MAP,
        {
            vol.Required(INPUT_MAP_ID): cv.positive_int,
        },
        DreameMower.async_select_map.__name__,
    )

    platform.async_register_entity_service(
        SERVICE_DELETE_MAP,
        {
            vol.Optional(INPUT_MAP_ID): cv.positive_int,
        },
        DreameMower.async_delete_map.__name__,
    )

    platform.async_register_entity_service(
        SERVICE_SAVE_TEMPORARY_MAP,
        {},
        DreameMower.async_save_temporary_map.__name__,
    )

    platform.async_register_entity_service(
        SERVICE_DISCARD_TEMPORARY_MAP,
        {},
        DreameMower.async_discard_temporary_map.__name__,
    )

    platform.async_register_entity_service(
        SERVICE_REPLACE_TEMPORARY_MAP,
        {
            vol.Optional(INPUT_MAP_ID): cv.positive_int,
        },
        DreameMower.async_replace_temporary_map.__name__,
    )

    platform.async_register_entity_service(
        SERVICE_CLEAN_ZONE,
        {
            vol.Required(INPUT_ZONE): vol.Any(
                [
                    vol.ExactSequence(
                        [
                            vol.Coerce(int),
                            vol.Coerce(int),
                            vol.Coerce(int),
                            vol.Coerce(int),
                        ]
                    )
                ],
                vol.ExactSequence(
                    [
                        vol.Coerce(int),
                        vol.Coerce(int),
                        vol.Coerce(int),
                        vol.Coerce(int),
                    ]
                ),
            ),
            vol.Optional(INPUT_REPEATS): vol.Any(vol.Coerce(int), [vol.Coerce(int)]),
        },
        DreameMower.async_clean_zone.__name__,
    )

    platform.async_register_entity_service(
        SERVICE_CLEAN_SEGMENT,
        {
            vol.Required(INPUT_SEGMENTS_ARRAY): vol.Any(vol.Coerce(int), [vol.Coerce(int)]),
            vol.Optional(INPUT_REPEATS): vol.Any(vol.Coerce(int), [vol.Coerce(int)]),
        },
        DreameMower.async_clean_segment.__name__,
    )

    platform.async_register_entity_service(
        SERVICE_CLEAN_SPOT,
        {
            vol.Required(INPUT_POINTS): vol.Any(
                [
                    vol.ExactSequence(
                        [
                            vol.Coerce(int),
                            vol.Coerce(int),
                        ]
                    )
                ],
                vol.ExactSequence(
                    [
                        vol.Coerce(int),
                        vol.Coerce(int),
                    ]
                ),
            ),
            vol.Optional(INPUT_REPEATS): vol.Any(vol.Coerce(int), [vol.Coerce(int)]),
        },
        DreameMower.async_clean_spot.__name__,
    )

    platform.async_register_entity_service(
        SERVICE_GOTO,
        {
            vol.Required(INPUT_X): vol.All(vol.Coerce(int)),
            vol.Required(INPUT_Y): vol.All(vol.Coerce(int)),
        },
        DreameMower.async_goto.__name__,
    )

    platform.async_register_entity_service(
        SERVICE_FOLLOW_PATH,
        {
            vol.Optional(INPUT_POINTS): vol.All(
                list,
                [
                    vol.ExactSequence(
                        [
                            vol.Coerce(int),
                            vol.Coerce(int),
                        ]
                    )
                ],
            ),
        },
        DreameMower.async_follow_path.__name__,
    )

    platform.async_register_entity_service(
        SERVICE_SET_RESTRICTED_ZONE,
        {
            vol.Optional(INPUT_WALL_ARRAY): vol.All(
                list,
                [
                    vol.ExactSequence(
                        [
                            vol.Coerce(int),
                            vol.Coerce(int),
                            vol.Coerce(int),
                            vol.Coerce(int),
                        ]
                    )
                ],
            ),
            vol.Optional(INPUT_ZONE_ARRAY): vol.All(
                list,
                [
                    vol.ExactSequence(
                        [
                            vol.Coerce(int),
                            vol.Coerce(int),
                            vol.Coerce(int),
                            vol.Coerce(int),
                        ]
                    )
                ],
            ),
        },
        DreameMower.async_set_restricted_zone.__name__,
    )

    platform.async_register_entity_service(
        SERVICE_SET_PATHWAY,
        {
            vol.Optional(INPUT_PATHWAY_ARRAY): vol.All(
                list,
                [
                    vol.ExactSequence(
                        [
                            vol.Coerce(int),
                            vol.Coerce(int),
                            vol.Coerce(int),
                            vol.Coerce(int),
                        ]
                    )
                ],
            ),
        },
        DreameMower.async_set_pathway.__name__,
    )

    platform.async_register_entity_service(
        SERVICE_SET_PREDEFINED_POINTS,
        {
            vol.Optional(INPUT_POINTS): vol.All(
                list,
                [
                    vol.ExactSequence(
                        [
                            vol.Coerce(int),
                            vol.Coerce(int),
                        ]
                    )
                ],
            ),
        },
        DreameMower.async_set_predefined_points.__name__,
    )

    platform.async_register_entity_service(
        SERVICE_MOVE_REMOTE_CONTROL_STEP,
        {
            vol.Required(INPUT_VELOCITY): vol.All(vol.Coerce(int), vol.Clamp(min=-600, max=600)),
            vol.Required(INPUT_ROTATION): vol.All(vol.Coerce(int), vol.Clamp(min=-360, max=360)),
            vol.Optional("prompt"): cv.boolean,
        },
        DreameMower.async_remote_control_move_step.__name__,
    )

    platform.async_register_entity_service(
        SERVICE_INSTALL_VOICE_PACK,
        {
            vol.Required(INPUT_LANGUAGE_ID): cv.string,
            vol.Required(INPUT_URL): cv.url,
            vol.Required(INPUT_MD5): cv.string,
            vol.Required(INPUT_SIZE): cv.positive_int,
        },
        DreameMower.async_install_voice_pack.__name__,
    )

    platform.async_register_entity_service(
        SERVICE_RENAME_MAP,
        {
            vol.Required(INPUT_MAP_ID): cv.positive_int,
            vol.Required(INPUT_MAP_NAME): cv.string,
        },
        DreameMower.async_rename_map.__name__,
    )

    platform.async_register_entity_service(
        SERVICE_RESTORE_MAP,
        {
            vol.Required(INPUT_RECOVERY_MAP_INDEX): cv.positive_int,
            vol.Optional(INPUT_MAP_ID): cv.positive_int,
        },
        DreameMower.async_restore_map.__name__,
    )

    platform.async_register_entity_service(
        SERVICE_RESTORE_MAP_FROM_FILE,
        {
            vol.Required(INPUT_FILE_URL): cv.url,
            vol.Optional(INPUT_MAP_ID): cv.positive_int,
        },
        DreameMower.async_restore_map_from_file.__name__,
    )

    platform.async_register_entity_service(
        SERVICE_BACKUP_MAP,
        {
            vol.Optional(INPUT_MAP_ID): cv.positive_int,
        },
        DreameMower.async_backup_map.__name__,
    )

    platform.async_register_entity_service(
        SERVICE_MERGE_SEGMENTS,
        {
            vol.Optional(INPUT_MAP_ID): cv.positive_int,
            vol.Required(INPUT_SEGMENTS_ARRAY): vol.All([vol.Coerce(int)]),
        },
        DreameMower.async_merge_segments.__name__,
    )

    platform.async_register_entity_service(
        SERVICE_SPLIT_SEGMENTS,
        {
            vol.Optional(INPUT_MAP_ID): cv.positive_int,
            vol.Required(INPUT_SEGMENT): vol.All(vol.Coerce(int)),
            vol.Required(INPUT_LINE): vol.All(
                list,
                vol.ExactSequence(
                    [
                        vol.Coerce(int),
                        vol.Coerce(int),
                        vol.Coerce(int),
                        vol.Coerce(int),
                    ]
                ),
            ),
        },
        DreameMower.async_split_segments.__name__,
    )

    platform.async_register_entity_service(
        SERVICE_RENAME_SEGMENT,
        {
            vol.Required(INPUT_SEGMENT_ID): cv.positive_int,
            vol.Required(INPUT_SEGMENT_NAME): cv.string,
        },
        DreameMower.async_rename_segment.__name__,
    )

    platform.async_register_entity_service(
        SERVICE_SET_CLEANING_SEQUENCE,
        {
            vol.Required(INPUT_CLEANING_SEQUENCE): cv.ensure_list,
        },
        DreameMower.async_set_cleaning_sequence.__name__,
    )

    platform.async_register_entity_service(
        SERVICE_SET_CUSTOM_CLEANING,
        {
            vol.Required(INPUT_SEGMENT_ID): cv.ensure_list,
            vol.Required(INPUT_REPEATS): cv.ensure_list,
            vol.Optional(INPUT_CLEANING_MODE): cv.ensure_list,
        },
        DreameMower.async_set_custom_cleaning.__name__,
    )

    platform.async_register_entity_service(
        SERVICE_RESET_CONSUMABLE,
        {
            vol.Required(INPUT_CONSUMABLE): vol.In(
                [
                    CONSUMABLE_BLADES,
                    CONSUMABLE_SIDE_BRUSH,
                    CONSUMABLE_FILTER,
                    CONSUMABLE_TANK_FILTER,
                    CONSUMABLE_SENSOR,
                    CONSUMABLE_SILVER_ION,
                    CONSUMABLE_LENSBRUSH,
                    CONSUMABLE_SQUEEGEE,
                ]
            ),
        },
        DreameMower.async_reset_consumable.__name__,
    )

    platform.async_register_entity_service(
        SERVICE_RENAME_SHORTCUT,
        {
            vol.Required(INPUT_SHORTCUT_ID): cv.positive_int,
            vol.Required(INPUT_SHORTCUT_NAME): cv.string,
        },
        DreameMower.async_rename_shortcut.__name__,
    )

    platform.async_register_entity_service(
        SERVICE_SET_OBSTACLE_IGNORE,
        {
            vol.Required(INPUT_X): vol.All(vol.Coerce(float)),
            vol.Required(INPUT_Y): vol.All(vol.Coerce(float)),
            vol.Required(INPUT_OBSTACLE_IGNORED): vol.All(vol.Coerce(bool)),
        },
        DreameMower.async_set_obstacle_ignore.__name__,
    )

    platform.async_register_entity_service(
        SERVICE_SET_ROUTER_POSITION,
        {
            vol.Required(INPUT_X): vol.All(vol.Coerce(int)),
            vol.Required(INPUT_Y): vol.All(vol.Coerce(int)),
        },
        DreameMower.async_set_router_position.__name__,
    )

    async_add_entities([DreameMower(coordinator)])


class DreameMower(DreameMowerEntity, LawnMowerEntity):
    """Representation of a Dreame Mower cleaner robot."""

    _unrecorded_attributes = frozenset(MOWER_UNRECORDED_ATTRIBUTES)

    def __init__(self, coordinator: DreameMowerDataUpdateCoordinator) -> None:
        """Initialize the mower entity."""
        super().__init__(coordinator)

        self._attr_device_class = DOMAIN
        self._attr_name = coordinator.device.name
        self._attr_unique_id = f"{coordinator.device.mac}_" + DOMAIN

        self._set_attrs()

    @callback
    def _handle_coordinator_update(self) -> None:
        self._set_attrs()
        self.async_write_ha_state()

    def _set_attrs(self):
        if self.device.status.has_error:
            self._attr_icon = "mdi:alert-octagon"
        elif (
            self.device.status.paused
        ):
            self._attr_icon = "mdi:pause-circle"
        elif self.device.status.sleeping:
            self._attr_icon = "mdi:sleep"
        elif self.device.status.charging:
            self._attr_icon = "mdi:lightning-bolt-circle"
        elif self.device.status.docked:
            self._attr_icon = "mdi:ev-station"
        elif self.device.status.cruising:
            self._attr_icon = "mdi:map-marker-path"
        else:
            self._attr_icon = "mdi:robot-mower"

        self._attr_supported_features = SUPPORT_DREAME
        if (
            not (
                self.device.status
                and self.device.status.started
                and (
                    self.device.status.customized_cleaning
                    and not (self.device.status.zone_cleaning or self.device.status.spot_cleaning)
                )
            )
            and not self.device.status.scheduled_clean
        ):
            self._attr_supported_features = self._attr_supported_features
            self._attr_fan_speed = None
            self._attr_fan_speed_list = []
        else:
            self._attr_fan_speed = None
            self._attr_fan_speed_list = []

        # if ACTION_AVAILABILITY[DreameMowerAction.START_MOWING.name](self.device):
        self._attr_supported_features = self._attr_supported_features | LawnMowerEntityFeature.START_MOWING
        # if ACTION_AVAILABILITY[DreameMowerAction.PAUSE.name](self.device):
        self._attr_supported_features = self._attr_supported_features | LawnMowerEntityFeature.PAUSE
        # if ACTION_AVAILABILITY[DreameMowerAction.STOP.name](self.device):
        self._attr_supported_features = self._attr_supported_features | LawnMowerEntityFeature.PAUSE
        # if ACTION_AVAILABILITY[DreameMowerAction.DOCK.name](self.device):
        self._attr_supported_features = self._attr_supported_features | LawnMowerEntityFeature.DOCK

        self._attr_battery_level = self.device.status.battery_level
        self._attr_charging = self.device.status.charging
        self._attr_state = STATE_CODE_TO_STATE.get(self.device.status.state, STATE_UNKNOWN)
        self._attr_extra_state_attributes = self.device.status.attributes

    @property
    def state(self) -> str | None:
        """Return the state of the mower cleaner."""
        return self._attr_state

    @property
    def supported_features(self) -> int:
        """Flag mower cleaner features that are supported."""
        return self._attr_supported_features

    @property
    def extra_state_attributes(self) -> dict[str, str] | None:
        """Return the extra state attributes of the entity."""
        return self._attr_extra_state_attributes

    @property
    def battery_icon(self) -> str:
        """Return the battery icon for the mower cleaner."""
        return icon_for_battery_level(battery_level=self._attr_battery_level, charging=self._attr_charging)

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self._attr_available and self.device.device_connected

    async def async_locate(self, **kwargs) -> None:
        """Locate the mower cleaner."""
        await self._try_command("Unable to call locate: %s", self.device.locate)

    async def async_start(self) -> None:
        """Start or resume the cleaning task."""
        await self._try_command("Unable to call start: %s", self.device.start)

    async def async_start_mowing(self) -> None:
        """Start or resume the cleaning task."""
        await self._try_command("Unable to call start: %s", self.device.start)

    async def async_start_pause(self) -> None:
        """Start or resume the cleaning task."""
        await self._try_command("Unable to call start_pause: %s", self.device.start_pause)

    async def async_stop(self, **kwargs) -> None:
        """Stop the mower cleaner."""
        await self._try_command("Unable to call stop: %s", self.device.stop)

    async def async_pause(self) -> None:
        """Pause the cleaning task."""
        await self._try_command("Unable to call pause: %s", self.device.pause)

    async def async_return_to_base(self, **kwargs) -> None:
        """Set the mower cleaner to return to the dock."""
        await self._try_command("Unable to call return_to_base: %s", self.device.return_to_base)

    async def async_dock(self, **kwargs) -> None:
        """Set the mower cleaner to return to the dock."""
        await self._try_command("Unable to call return_to_base: %s", self.device.dock)

    async def async_clean_zone(self, zone, repeats=1) -> None:
        await self._try_command(
            "Unable to call clean_zone: %s",
            self.device.clean_zone,
            zone,
            repeats,
        )

    async def async_clean_segment(self, segments, repeats=1) -> None:
        """Clean selected segments."""
        await self._try_command(
            "Unable to call clean_segment: %s",
            self.device.clean_segment,
            segments,
            repeats,
        )

    async def async_clean_spot(self, points, repeats=1) -> None:
        """Clean 1.5 square meters area of selected points."""
        await self._try_command(
            "Unable to call clean_spot: %s",
            self.device.clean_spot,
            points,
            repeats,
        )

    async def async_goto(self, x, y) -> None:
        """Go to a point and take pictures around."""
        if x is not None and y is not None and x != "" and y != "":
            await self._try_command("Unable to call go_to: %s", self.device.go_to, x, y)

    async def async_follow_path(self, points="") -> None:
        """Start a survaliance job."""
        await self._try_command("Unable to call follow_path: %s", self.device.follow_path, points)

    async def async_set_restricted_zone(self, walls="", zones="", no_mops="") -> None:
        """Create restricted zone."""
        await self._try_command(
            "Unable to call set_restricted_zone: %s",
            self.device.set_restricted_zone,
            walls,
            zones,
            no_mops,
        )

    async def async_set_pathway(self, pathways="") -> None:
        """Create or update pathways."""
        await self._try_command(
            "Unable to call set_pathway: %s",
            self.device.set_pathway,
            pathways,
        )

    async def async_set_predefined_points(self, points="") -> None:
        """Create or update predefined coordinates on the map."""
        await self._try_command(
            "Unable to call set_predefined_points: %s",
            self.device.set_predefined_points,
            points,
        )

    async def async_remote_control_move_step(
        self, rotation: int = 0, velocity: int = 0, prompt: bool | None = None
    ) -> None:
        """Remote control the robot."""
        await self._try_command(
            "Unable to call remote_control_move_step: %s",
            self.device.remote_control_move_step,
            rotation,
            velocity,
            prompt,
        )

    async def async_select_map(self, map_id) -> None:
        """Switch selected map."""
        await self._try_command("Unable to switch to selected map: %s", self.device.set_selected_map, map_id)

    async def async_delete_map(self, map_id=None) -> None:
        """Delete a map."""
        await self._try_command("Unable to delete map: %s", self.device.delete_map, map_id)

    async def async_save_temporary_map(self) -> None:
        """Save the temporary map."""
        await self._try_command("Unable to save map: %s", self.device.save_temporary_map)

    async def async_discard_temporary_map(self) -> None:
        """Discard the temporary map."""
        await self._try_command("Unable to discard temporary map: %s", self.device.discard_temporary_map)

    async def async_replace_temporary_map(self, map_id=None) -> None:
        """Replace the temporary map with another saved map."""
        await self._try_command(
            "Unable to replace temporary map: %s",
            self.device.replace_temporary_map,
            map_id,
        )

    async def async_request_map(self) -> None:
        """Request new map."""
        await self._try_command("Unable to call request_map: %s", self.device.request_map)

    async def async_set_property(self, key, value) -> None:
        """Set property."""
        if key is not None and value is not None and key != "" and value != "":
            await self._try_command("set_property failed: %s", self.device.set_property_value, key, value)

    async def async_call_action(self, key) -> None:
        """Call action."""
        if key is not None and key != "":
            await self._try_command("call_action failed: %s", self.device.call_action_value, key)

    async def async_rename_map(self, map_id, map_name="") -> None:
        """Rename a map"""
        if map_name != "":
            await self._try_command(
                "Unable to call rename_map: %s",
                self.device.rename_map,
                map_id,
                map_name,
            )

    async def async_restore_map(self, recovery_map_index, map_id=None) -> None:
        """Restore a map"""
        if recovery_map_index and recovery_map_index != "":
            await self._try_command(
                "Unable to call restore_map: %s",
                self.device.restore_map,
                recovery_map_index,
                map_id,
            )

    async def async_restore_map_from_file(self, file_url, map_id=None) -> None:
        """Restore a map from file"""
        if file_url and file_url != "":
            await self._try_command(
                "Unable to call restore_map_from_file: %s",
                self.device.restore_map_from_file,
                file_url,
                map_id,
            )

    async def async_backup_map(self, map_id=None) -> None:
        """Backup a map"""
        await self._try_command(
            "Unable to call backup_map: %s",
            self.device.backup_map,
            map_id,
        )

    async def async_rename_segment(self, segment_id, segment_name="") -> None:
        """Rename a segment"""
        if segment_name != "":
            await self._try_command(
                "Unable to call set_segment_name: %s",
                self.device.set_segment_name,
                segment_id,
                0,
                segment_name,
            )

    async def async_merge_segments(self, map_id=None, segments=None) -> None:
        """Merge segments"""
        if segments is not None:
            await self._try_command(
                "Unable to call merge_segments: %s",
                self.device.merge_segments,
                map_id,
                segments,
            )

    async def async_split_segments(self, map_id=None, segment=None, line=None) -> None:
        """Split segments"""
        if segment is not None and line is not None:
            await self._try_command(
                "Unable to call split_segments: %s",
                self.device.split_segments,
                map_id,
                segment,
                line,
            )

    async def async_set_cleaning_sequence(self, cleaning_sequence) -> None:
        """Set cleaning sequence"""
        if cleaning_sequence != "" and cleaning_sequence is not None:
            await self._try_command(
                "Unable to call cleaning_sequence: %s",
                self.device.set_cleaning_sequence,
                cleaning_sequence,
            )

    async def async_set_custom_cleaning(
        self, segment_id, repeats, cleaning_mode=None
    ) -> None:
        """Set custom cleaning"""
        if (
            segment_id != ""
            and segment_id is not None
            and repeats != ""
            and repeats is not None
        ):
            await self._try_command(
                "Unable to call set_custom_cleaning: %s",
                self.device.set_custom_cleaning,
                segment_id,
                repeats,
                cleaning_mode,
            )

    async def async_install_voice_pack(self, lang_id, url, md5, size, **kwargs) -> None:
        """install a custom language pack"""
        await self._try_command(
            "Unable to call install_voice_pack: %s",
            self.device.install_voice_pack,
            lang_id,
            url,
            md5,
            size,
        )

    async def async_send_command(self, command: str, params=None, **kwargs) -> None:
        """Send a command to a mower cleaner."""
        await self._try_command("Unable to call send_command: %s", self.device.send_command, command, params)

    async def async_reset_consumable(self, consumable: str) -> None:
        """Reset consumable"""
        action = CONSUMABLE_RESET_ACTION.get(consumable)
        if action:
            await self._try_command(
                "Unable to call reset_consumable: %s",
                self.device.call_action,
                action,
            )

    async def async_rename_shortcut(self, shortcut_id, shortcut_name) -> None:
        """Rename a shortcut"""
        if shortcut_name and shortcut_name != "":
            await self._try_command(
                "Unable to call rename_shortcut: %s",
                self.device.rename_shortcut,
                shortcut_id,
                shortcut_name,
            )

    async def async_set_obstacle_ignore(self, x, y, obstacle_ignored) -> None:
        """Set obstacle ignore status"""
        if x is not None and x != "" and y is not None and y != "":
            await self._try_command(
                "Unable to call set_obstacle_ignore: %s",
                self.device.set_obstacle_ignore,
                x,
                y,
                obstacle_ignored,
            )

    async def async_set_router_position(self, x, y) -> None:
        """Set router position on current map"""
        if x is not None and x != "" and y is not None and y != "":
            await self._try_command(
                "Unable to call set_router_position: %s",
                self.device.set_router_position,
                x,
                y,
            )
