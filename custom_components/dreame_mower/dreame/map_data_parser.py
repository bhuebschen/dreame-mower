"""Parser for mower vector map data from the Dreame batch device data API.

The batch API returns map data split across numbered keys (MAP.0, MAP.1, ...).
These chunks must be concatenated in numeric order to form a complete JSON string.
The JSON contains polygon-based zone boundaries, navigation paths, and metadata.
"""
import json
import logging
import re
import time

from .types import (
    MowerMapBoundary,
    MowerMowPath,
    MowerPath,
    MowerVectorMap,
    MowerZone,
)

_LOGGER = logging.getLogger(__name__)

# Sentinel value in M_PATH data marking a path segment break
_PATH_SENTINEL = (32767, -32768)


def reassemble_map_chunks(batch_data: dict, prefix: str) -> str | None:
    """Reassemble chunked data from batch API into a single string.

    Keys like MAP.0, MAP.1, ... MAP.N are concatenated in numeric order.
    The MAP.info key is skipped (it's metadata, not map content).

    Args:
        batch_data: dict from get_batch_device_datas response
        prefix: key prefix to match, e.g. "MAP" or "M_PATH"

    Returns:
        Concatenated string, or None if no matching keys found.
    """
    pattern = re.compile(rf"^{re.escape(prefix)}\.(\d+)$")
    chunks = []
    for key, value in batch_data.items():
        match = pattern.match(key)
        if match:
            chunks.append((int(match.group(1)), value))

    if not chunks:
        return None

    chunks.sort(key=lambda x: x[0])
    return "".join(value for _, value in chunks)


def _parse_polygon_list(data_map: dict) -> list:
    """Parse a dataType:Map structure containing polygon entries."""
    if not data_map or data_map.get("dataType") != "Map":
        return []
    return data_map.get("value", [])


def _extract_path_coords(path_list: list) -> list[tuple[int, int]]:
    """Convert [{"x": ..., "y": ...}, ...] to [(x, y), ...]."""
    return [(p["x"], p["y"]) for p in path_list]


def parse_mower_map(map_json_str: str) -> MowerVectorMap:
    """Parse a single map JSON string into a MowerVectorMap.

    Args:
        map_json_str: JSON string for one map (after unescaping from the chunk array).

    Returns:
        MowerVectorMap with zones, paths, boundary, etc.
    """
    data = json.loads(map_json_str)
    vmap = MowerVectorMap()

    # Parse mowing area zones
    for entry in _parse_polygon_list(data.get("mowingAreas", {})):
        zone_id, zone_data = entry[0], entry[1]
        vmap.zones.append(MowerZone(
            zone_id=zone_id,
            path=_extract_path_coords(zone_data.get("path", [])),
            name=zone_data.get("name", ""),
            zone_type=zone_data.get("type", 0),
            shape_type=zone_data.get("shapeType", 0),
            area=zone_data.get("area", 0),
            time=zone_data.get("time", 0),
            etime=zone_data.get("etime", 0),
        ))

    # Parse forbidden areas
    for entry in _parse_polygon_list(data.get("forbiddenAreas", {})):
        zone_id, zone_data = entry[0], entry[1]
        vmap.forbidden_areas.append(MowerZone(
            zone_id=zone_id,
            path=_extract_path_coords(zone_data.get("path", [])),
            name=zone_data.get("name", ""),
            zone_type=zone_data.get("type", 0),
        ))

    # Parse navigation paths between zones
    for entry in _parse_polygon_list(data.get("paths", {})):
        path_id, path_data = entry[0], entry[1]
        vmap.paths.append(MowerPath(
            path_id=path_id,
            path=_extract_path_coords(path_data.get("path", [])),
            path_type=path_data.get("type", 0),
        ))

    # Parse boundary
    boundary = data.get("boundary")
    if boundary:
        vmap.boundary = MowerMapBoundary(
            x1=boundary["x1"], y1=boundary["y1"],
            x2=boundary["x2"], y2=boundary["y2"],
        )

    vmap.total_area = data.get("totalArea", 0)
    vmap.name = data.get("name", "")
    vmap.map_index = data.get("mapIndex", 0)
    vmap.last_updated = time.time()

    return vmap


def parse_mow_paths(batch_data: dict) -> list[MowerMowPath]:
    """Parse M_PATH.* keys from batch data into MowerMowPath objects.

    M_PATH data is chunked across numbered keys (M_PATH.0, M_PATH.1, ...)
    just like MAP data. The chunks must be reassembled into a single string.
    M_PATH.info contains the split position for multi-map data.

    The reassembled string contains [x,y] coordinate pairs with
    [32767,-32768] sentinels marking segment breaks.

    Args:
        batch_data: dict from get_batch_device_datas response

    Returns:
        List of MowerMowPath objects (one per zone, zone_id=0).
    """
    raw = reassemble_map_chunks(batch_data, "M_PATH")
    if not raw:
        return []

    # M_PATH.info is the split position (like MAP.info)
    # Skip the first map's data (typically empty "[]")
    info = batch_data.get("M_PATH.info", "")
    try:
        split_pos = int(info) if info.isdigit() else 0
    except (ValueError, AttributeError):
        split_pos = 0

    if split_pos > 0 and split_pos < len(raw):
        raw = raw[split_pos:]

    if not raw.strip() or raw.strip() == "[]":
        return []

    # Extract all [x,y] coordinate pairs using regex.
    # This is robust against chunk boundary artifacts since it
    # only matches well-formed [int,int] pairs.
    # M_PATH coordinates are at 1/10th scale compared to zone coordinates
    # (decimeters vs centimeters), so we scale by 10 after sentinel detection.
    pair_pattern = re.compile(r"\[(-?\d+),(-?\d+)\]")
    raw_pairs = [(int(m.group(1)), int(m.group(2))) for m in pair_pattern.finditer(raw)]

    if not raw_pairs:
        return []

    # Split on sentinel into segments, then scale coordinates
    segments = []
    current_segment = []
    for p in raw_pairs:
        if p == _PATH_SENTINEL:
            if current_segment:
                segments.append(current_segment)
                current_segment = []
        else:
            current_segment.append((p[0] * 10, p[1] * 10))

    if current_segment:
        segments.append(current_segment)

    if segments:
        return [MowerMowPath(zone_id=0, segments=segments)]

    return []


def parse_batch_map_data(batch_data: dict) -> MowerVectorMap | None:
    """Parse complete batch device data response into a MowerVectorMap.

    This is the main entry point. It:
    1. Reassembles MAP.* chunks into a full JSON string
    2. Parses the JSON array (may contain multiple maps by mapIndex)
    3. Returns the primary map (mapIndex 0)
    4. Attaches mowing paths from M_PATH.* keys

    Args:
        batch_data: Full response dict from get_batch_device_datas

    Returns:
        MowerVectorMap for the primary map, or None if parsing fails.
    """
    if not batch_data:
        return None

    raw_map = reassemble_map_chunks(batch_data, "MAP")
    if not raw_map:
        _LOGGER.debug("No MAP chunks found in batch data")
        return None

    # MAP.info contains the character length of the primary JSON array.
    # The full reassembled string may contain multiple JSON arrays
    # concatenated (one per map), so we use MAP.info to split them.
    map_info = batch_data.get("MAP.info", "")
    map_arrays = []
    try:
        split_pos = int(map_info) if map_info.isdigit() else 0
    except (ValueError, AttributeError):
        split_pos = 0

    if split_pos > 0 and split_pos < len(raw_map):
        # Split into individual JSON arrays
        parts = [raw_map[:split_pos], raw_map[split_pos:]]
    else:
        parts = [raw_map]

    for part in parts:
        part = part.strip()
        if not part:
            continue
        try:
            arr = json.loads(part)
            if isinstance(arr, list):
                map_arrays.extend(arr)
        except json.JSONDecodeError:
            _LOGGER.debug("Failed to parse MAP chunk part (len=%d)", len(part))

    if not map_arrays:
        _LOGGER.warning("No valid MAP arrays found in batch data")
        return None

    # Parse each map entry — they're JSON strings within the array
    primary_map = None
    for map_json_str in map_arrays:
        try:
            vmap = parse_mower_map(map_json_str)
            if vmap.map_index == 0:
                primary_map = vmap
        except (json.JSONDecodeError, KeyError, TypeError) as ex:
            _LOGGER.warning("Failed to parse map entry: %s", ex)
            continue

    if primary_map is None and map_arrays:
        # Fall back to first entry if no mapIndex 0 found
        try:
            primary_map = parse_mower_map(map_arrays[0])
        except (json.JSONDecodeError, KeyError, TypeError) as ex:
            _LOGGER.warning("Failed to parse fallback map entry: %s", ex)
            return None

    if primary_map is None:
        return None

    # Attach mowing paths
    primary_map.mow_paths = parse_mow_paths(batch_data)

    return primary_map
