# Mower Map Rendering Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Render the mower's vector/polygon map data in Home Assistant via the existing camera entity, by fetching map data from the Dreame cloud batch API and drawing zone polygons with PIL.

**Architecture:** The mower stores map data as vector polygons (zone boundaries, paths, contours) in the Dreame cloud `get_batch_device_datas` API, split across `MAP.0`-`MAP.N` keys. We add a new fetch+parse pipeline that reassembles these chunks into structured polygon data, then render it with PIL into PNG images served through the existing camera entity. The existing binary pixel-based decoder is bypassed entirely — this is a parallel data path.

**Tech Stack:** Python, PIL/Pillow (already a dependency), existing `DreameMowerDreameHomeCloudProtocol.get_batch_device_datas()`, existing camera entity infrastructure.

---

## Background: Map Data Format

The batch API returns data split across numbered keys:
- `MAP.0` through `MAP.N` — chunks of one large JSON string. Concatenate in numeric order to get: `["<json_map_0>", "<json_map_1>"]`
- `M_PATH.0` through `M_PATH.N` — mowing path coordinate arrays per zone
- `SETTINGS.0` through `SETTINGS.N` — per-zone mowing settings JSON
- `MAP.info`, `M_PATH.info`, `SETTINGS.info` — metadata (counts/versions)

Each map JSON object contains:
```json
{
  "mowingAreas": {"dataType": "Map", "value": [[id, {"id": 1, "type": 0, "shapeType": 0, "path": [{"x": ..., "y": ...}, ...], "name": "Backyard", "time": 566, "area": 15.7}], ...]},
  "forbiddenAreas": {"dataType": "Map", "value": [...]},
  "paths": {"dataType": "Map", "value": [[id, {"id": 201, "type": 1, "path": [...]}], ...]},
  "contours": {"dataType": "Map", "value": [...]},
  "obstacles": {"dataType": "Map", "value": [...]},
  "boundary": {"x1": -15160, "y1": -29010, "x2": 4900, "y2": 5200},
  "totalArea": 157,
  "name": "",
  "cut": [[1,6],[6,7]],
  "mapIndex": 0,
  "hasBack": 1
}
```

Coordinates are in centimeters (roughly -15000 to +5000 range). Zone polygons have 10-40 vertices. The `[32767, -32768]` sentinel in M_PATH data marks path segment breaks.

---

### Task 1: Add Vector Map Data Types

**Files:**
- Modify: `custom_components/dreame_mower/dreame/types.py` (append to end)

**Step 1: Add the new data classes**

Add these classes at the end of `types.py`, before any trailing blank lines:

```python
class MowerZone:
    """A mowing zone defined by a polygon boundary."""
    def __init__(self, zone_id: int, path: list, name: str = "", zone_type: int = 0,
                 shape_type: int = 0, area: float = 0, time: int = 0, etime: int = 0) -> None:
        self.zone_id = zone_id
        self.path = path  # list of (x, y) tuples
        self.name = name
        self.zone_type = zone_type
        self.shape_type = shape_type
        self.area = area
        self.time = time
        self.etime = etime


class MowerPath:
    """A navigation path between zones."""
    def __init__(self, path_id: int, path: list, path_type: int = 0) -> None:
        self.path_id = path_id
        self.path = path  # list of (x, y) tuples
        self.path_type = path_type


class MowerMapBoundary:
    """Bounding box for the entire map."""
    def __init__(self, x1: int, y1: int, x2: int, y2: int) -> None:
        self.x1 = x1
        self.y1 = y1
        self.x2 = x2
        self.y2 = y2

    @property
    def width(self) -> int:
        return self.x2 - self.x1

    @property
    def height(self) -> int:
        return self.y2 - self.y1


class MowerMowPath:
    """Mowing path trace for a zone — the actual trail the mower followed."""
    def __init__(self, zone_id: int, segments: list) -> None:
        self.zone_id = zone_id
        self.segments = segments  # list of lists of (x, y) tuples, split on sentinel


class MowerVectorMap:
    """Complete vector map data for a mower, fetched from batch API."""
    def __init__(self) -> None:
        self.zones: list[MowerZone] = []
        self.forbidden_areas: list[MowerZone] = []
        self.paths: list[MowerPath] = []
        self.contours: list = []
        self.obstacles: list = []
        self.boundary: MowerMapBoundary | None = None
        self.total_area: float = 0
        self.name: str = ""
        self.map_index: int = 0
        self.mow_paths: list[MowerMowPath] = []
        self.last_updated: float | None = None
```

**Step 2: Verify no syntax errors**

Run: `python -c "import ast; ast.parse(open('custom_components/dreame_mower/dreame/types.py').read()); print('OK')"`
Expected: `OK`

**Step 3: Commit**

```bash
git add custom_components/dreame_mower/dreame/types.py
git commit -m "feat: add vector map data types for mower map rendering"
```

---

### Task 2: Implement Batch Map Data Parser

**Files:**
- Create: `custom_components/dreame_mower/dreame/map_data_parser.py`
- Create: `tests/test_map_data_parser.py`

This is a pure-data module with no dependencies on HA or the protocol layer — easy to test in isolation.

**Step 1: Write failing tests**

Create `tests/test_map_data_parser.py`:

```python
"""Tests for mower vector map data parser."""
import json
import pytest

from custom_components.dreame_mower.dreame.map_data_parser import (
    reassemble_map_chunks,
    parse_mower_map,
    parse_mow_paths,
)
from custom_components.dreame_mower.dreame.types import MowerVectorMap


# --- reassemble_map_chunks tests ---

def test_reassemble_single_chunk():
    batch = {"MAP.0": '["{\\"hello\\":\\"world\\"}"]', "MAP.info": "1"}
    result = reassemble_map_chunks(batch, "MAP")
    assert result == '["{\\\"hello\\\":\\\"world\\\"}"]'


def test_reassemble_multiple_chunks_ordered():
    batch = {"MAP.0": "abc", "MAP.1": "def", "MAP.2": "ghi", "MAP.info": "1"}
    result = reassemble_map_chunks(batch, "MAP")
    assert result == "abcdefghi"


def test_reassemble_skips_info_key():
    batch = {"MAP.0": "hello", "MAP.info": "999"}
    result = reassemble_map_chunks(batch, "MAP")
    assert result == "hello"


def test_reassemble_empty_batch():
    result = reassemble_map_chunks({}, "MAP")
    assert result is None


def test_reassemble_no_matching_keys():
    batch = {"SETTINGS.0": "data"}
    result = reassemble_map_chunks(batch, "MAP")
    assert result is None


# --- parse_mower_map tests ---

MINIMAL_MAP_JSON = json.dumps({
    "mowingAreas": {"dataType": "Map", "value": [
        [1, {"id": 1, "type": 0, "shapeType": 0,
             "path": [{"x": 0, "y": 0}, {"x": 100, "y": 0}, {"x": 100, "y": 100}, {"x": 0, "y": 100}],
             "name": "Front Yard", "time": 120, "etime": 90, "area": 10.5}]
    ]},
    "forbiddenAreas": {"dataType": "Map", "value": []},
    "paths": {"dataType": "Map", "value": [
        [201, {"id": 201, "type": 1, "shapeType": 0,
               "path": [{"x": 50, "y": 50}, {"x": 200, "y": 200}]}]
    ]},
    "spotAreas": {"dataType": "Map", "value": []},
    "cleanPoints": {"dataType": "Map", "value": []},
    "cruisePoints": {"dataType": "Map", "value": []},
    "obstacles": {"dataType": "Map", "value": []},
    "contours": {"dataType": "Map", "value": []},
    "notObsAreas": {"dataType": "Map", "value": []},
    "md5sum": "abc123",
    "totalArea": 10,
    "boundary": {"x1": -100, "y1": -100, "x2": 200, "y2": 200},
    "name": "",
    "cut": [],
    "merged": False,
    "mapIndex": 0,
    "hasBack": 1,
})


def test_parse_mower_map_zones():
    result = parse_mower_map(MINIMAL_MAP_JSON)
    assert isinstance(result, MowerVectorMap)
    assert len(result.zones) == 1
    assert result.zones[0].zone_id == 1
    assert result.zones[0].name == "Front Yard"
    assert result.zones[0].area == 10.5
    assert len(result.zones[0].path) == 4
    assert result.zones[0].path[0] == (0, 0)
    assert result.zones[0].path[2] == (100, 100)


def test_parse_mower_map_boundary():
    result = parse_mower_map(MINIMAL_MAP_JSON)
    assert result.boundary is not None
    assert result.boundary.x1 == -100
    assert result.boundary.y2 == 200
    assert result.boundary.width == 300
    assert result.boundary.height == 300


def test_parse_mower_map_paths():
    result = parse_mower_map(MINIMAL_MAP_JSON)
    assert len(result.paths) == 1
    assert result.paths[0].path_id == 201
    assert result.paths[0].path[0] == (50, 50)


def test_parse_mower_map_total_area():
    result = parse_mower_map(MINIMAL_MAP_JSON)
    assert result.total_area == 10


# --- parse_mow_paths tests ---

def test_parse_mow_paths_empty():
    batch = {"M_PATH.0": "[]", "M_PATH.info": "1"}
    result = parse_mow_paths(batch)
    assert len(result) == 0 or (len(result) == 1 and len(result[0].segments) == 0)


def test_parse_mow_paths_with_sentinel():
    batch = {
        "M_PATH.1": "[10,20],[30,40],[32767,-32768],[50,60],[70,80]",
        "M_PATH.info": "1",
    }
    result = parse_mow_paths(batch)
    assert len(result) >= 1
    # Should have segments split on sentinel
    mow_path = result[0]
    assert len(mow_path.segments) == 2
    assert mow_path.segments[0] == [(10, 20), (30, 40)]
    assert mow_path.segments[1] == [(50, 60), (70, 80)]
```

**Step 2: Create a minimal conftest so imports work**

Create `tests/conftest.py`:

```python
"""Test configuration."""
import sys
from pathlib import Path

# Add the custom_components directory to the path so imports work
sys.path.insert(0, str(Path(__file__).parent.parent))
```

**Step 3: Run tests to verify they fail**

Run: `cd /Users/ben/dev/Personal/dreame-mower && python -m pytest tests/test_map_data_parser.py -v 2>&1 | head -30`
Expected: ERRORS — `ModuleNotFoundError` because `map_data_parser` doesn't exist yet

**Step 4: Implement the parser**

Create `custom_components/dreame_mower/dreame/map_data_parser.py`:

```python
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

    Each M_PATH.N key contains a coordinate array for zone N.
    Coordinates are comma-separated pairs: [x1,y1],[x2,y2],...
    The sentinel [32767,-32768] marks a segment break.

    Args:
        batch_data: dict from get_batch_device_datas response

    Returns:
        List of MowerMowPath objects.
    """
    pattern = re.compile(r"^M_PATH\.(\d+)$")
    paths = []

    for key, value in batch_data.items():
        match = pattern.match(key)
        if not match:
            continue

        zone_id = int(match.group(1))
        value = value.strip()

        if not value or value == "[]":
            continue

        # Parse the coordinate pairs from the string
        # Format: [x,y],[x,y],... or just x,y,x,y,...
        # We need to handle: ",[32767,-32768],[10,20],[30,40]"
        # Strip leading/trailing brackets and commas
        coords_str = value.strip("[], ")
        if not coords_str:
            continue

        # Parse all numbers
        numbers = re.findall(r"-?\d+", coords_str)
        if len(numbers) % 2 != 0:
            _LOGGER.warning("Odd number of coordinates in M_PATH.%d, skipping last", zone_id)
            numbers = numbers[:-1]

        # Build coordinate pairs, splitting on sentinel
        segments = []
        current_segment = []
        for i in range(0, len(numbers), 2):
            x, y = int(numbers[i]), int(numbers[i + 1])
            if (x, y) == _PATH_SENTINEL:
                if current_segment:
                    segments.append(current_segment)
                    current_segment = []
            else:
                current_segment.append((x, y))

        if current_segment:
            segments.append(current_segment)

        if segments:
            paths.append(MowerMowPath(zone_id=zone_id, segments=segments))

    return paths


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

    try:
        # The reassembled string is a JSON array of JSON strings
        map_array = json.loads(raw_map)
    except json.JSONDecodeError:
        _LOGGER.warning("Failed to parse reassembled MAP data as JSON")
        return None

    if not map_array:
        return None

    # Parse each map entry — they're JSON strings within the array
    primary_map = None
    for map_json_str in map_array:
        try:
            vmap = parse_mower_map(map_json_str)
            if vmap.map_index == 0:
                primary_map = vmap
        except (json.JSONDecodeError, KeyError, TypeError) as ex:
            _LOGGER.warning("Failed to parse map entry: %s", ex)
            continue

    if primary_map is None and map_array:
        # Fall back to first entry if no mapIndex 0 found
        try:
            primary_map = parse_mower_map(map_array[0])
        except (json.JSONDecodeError, KeyError, TypeError) as ex:
            _LOGGER.warning("Failed to parse fallback map entry: %s", ex)
            return None

    if primary_map is None:
        return None

    # Attach mowing paths
    primary_map.mow_paths = parse_mow_paths(batch_data)

    return primary_map
```

**Step 5: Run tests to verify they pass**

Run: `cd /Users/ben/dev/Personal/dreame-mower && python -m pytest tests/test_map_data_parser.py -v`
Expected: All tests PASS

**Step 6: Commit**

```bash
git add custom_components/dreame_mower/dreame/map_data_parser.py tests/conftest.py tests/test_map_data_parser.py
git commit -m "feat: add vector map data parser for batch API response"
```

---

### Task 3: Implement Vector Map Renderer

**Files:**
- Create: `custom_components/dreame_mower/dreame/map_renderer.py`
- Create: `tests/test_map_renderer.py`

A standalone PIL-based renderer that draws zone polygons onto a canvas. No dependency on the existing `DreameMowerMapRenderer` — that one expects pixel grids and segments. This one takes `MowerVectorMap` directly.

**Step 1: Write failing tests**

Create `tests/test_map_renderer.py`:

```python
"""Tests for mower vector map renderer."""
import pytest
from PIL import Image
import io

from custom_components.dreame_mower.dreame.map_renderer import MowerVectorMapRenderer
from custom_components.dreame_mower.dreame.types import (
    MowerVectorMap, MowerZone, MowerMapBoundary, MowerPath, MowerMowPath,
)


def _make_simple_map() -> MowerVectorMap:
    """Create a simple test map with one square zone."""
    vmap = MowerVectorMap()
    vmap.boundary = MowerMapBoundary(x1=0, y1=0, x2=1000, y2=1000)
    vmap.zones = [
        MowerZone(
            zone_id=1,
            path=[(100, 100), (900, 100), (900, 900), (100, 900)],
            name="Test Zone",
            area=64.0,
        ),
    ]
    vmap.last_updated = 1.0
    return vmap


def _make_multi_zone_map() -> MowerVectorMap:
    """Create a map with multiple zones and a path."""
    vmap = MowerVectorMap()
    vmap.boundary = MowerMapBoundary(x1=0, y1=0, x2=2000, y2=1000)
    vmap.zones = [
        MowerZone(zone_id=1, path=[(100, 100), (900, 100), (900, 900), (100, 900)], name="Zone A", area=64.0),
        MowerZone(zone_id=2, path=[(1100, 100), (1900, 100), (1900, 900), (1100, 900)], name="Zone B", area=64.0),
    ]
    vmap.paths = [
        MowerPath(path_id=201, path=[(900, 500), (1100, 500)], path_type=1),
    ]
    vmap.last_updated = 1.0
    return vmap


class TestMowerVectorMapRenderer:
    def test_render_returns_png_bytes(self):
        renderer = MowerVectorMapRenderer()
        result = renderer.render(_make_simple_map())
        assert isinstance(result, bytes)
        # Verify it's a valid PNG
        img = Image.open(io.BytesIO(result))
        assert img.format == "PNG"

    def test_render_none_returns_none(self):
        renderer = MowerVectorMapRenderer()
        result = renderer.render(None)
        assert result is None

    def test_render_no_boundary_returns_none(self):
        renderer = MowerVectorMapRenderer()
        vmap = MowerVectorMap()
        vmap.zones = [MowerZone(zone_id=1, path=[(0, 0), (1, 0), (1, 1)], name="X")]
        result = renderer.render(vmap)
        assert result is None

    def test_render_image_dimensions_reasonable(self):
        renderer = MowerVectorMapRenderer()
        result = renderer.render(_make_simple_map())
        img = Image.open(io.BytesIO(result))
        # Image should be at least 100x100 and at most 4096x4096
        assert 100 <= img.width <= 4096
        assert 100 <= img.height <= 4096

    def test_render_multi_zone(self):
        renderer = MowerVectorMapRenderer()
        result = renderer.render(_make_multi_zone_map())
        assert isinstance(result, bytes)
        img = Image.open(io.BytesIO(result))
        # Wider map should produce wider image
        assert img.width > img.height

    def test_render_with_mow_paths(self):
        vmap = _make_simple_map()
        vmap.mow_paths = [
            MowerMowPath(zone_id=1, segments=[[(200, 200), (800, 200), (800, 400)]]),
        ]
        renderer = MowerVectorMapRenderer()
        result = renderer.render(vmap)
        assert isinstance(result, bytes)

    def test_render_caches_when_unchanged(self):
        renderer = MowerVectorMapRenderer()
        vmap = _make_simple_map()
        result1 = renderer.render(vmap)
        result2 = renderer.render(vmap)
        # Same object, same last_updated — should return cached
        assert result1 is result2

    def test_render_re_renders_when_updated(self):
        renderer = MowerVectorMapRenderer()
        vmap = _make_simple_map()
        result1 = renderer.render(vmap)
        vmap.last_updated = 2.0
        result2 = renderer.render(vmap)
        # Different last_updated — should re-render (different bytes object)
        assert result1 is not result2
```

**Step 2: Run tests to verify they fail**

Run: `cd /Users/ben/dev/Personal/dreame-mower && python -m pytest tests/test_map_renderer.py -v 2>&1 | head -20`
Expected: ERRORS — `ModuleNotFoundError`

**Step 3: Implement the renderer**

Create `custom_components/dreame_mower/dreame/map_renderer.py`:

```python
"""Vector polygon map renderer for Dreame mower.

Renders MowerVectorMap data (zone polygons, paths, mowing trails) into
PNG images using PIL. This is a standalone renderer that does NOT use the
existing DreameMowerMapRenderer (which expects pixel-grid/bitmap data).
"""
import io
import logging
from PIL import Image, ImageDraw, ImageFont

from .types import MowerVectorMap

_LOGGER = logging.getLogger(__name__)

# Rendering constants
_MAX_IMAGE_SIZE = 2048  # Max pixels on longest side
_MIN_IMAGE_SIZE = 400   # Min pixels on longest side
_PADDING = 40           # Pixel padding around map edges
_BACKGROUND_COLOR = (30, 30, 30)  # Dark grey background
_ZONE_OUTLINE_COLOR = (255, 255, 255, 180)  # White outlines
_ZONE_OUTLINE_WIDTH = 2
_PATH_COLOR = (200, 200, 100, 150)  # Yellow-ish for navigation paths
_PATH_WIDTH = 2
_MOW_PATH_COLOR = (100, 200, 100, 100)  # Green for mowing trails
_MOW_PATH_WIDTH = 1
_LABEL_COLOR = (255, 255, 255, 220)  # White text
_FORBIDDEN_COLOR = (200, 50, 50, 120)  # Red for no-go zones

# Zone fill colors — distinct colors for up to 8 zones, cycling after
_ZONE_COLORS = [
    (76, 153, 0, 140),    # Green
    (0, 128, 128, 140),   # Teal
    (0, 102, 204, 140),   # Blue
    (153, 102, 0, 140),   # Brown
    (102, 51, 153, 140),  # Purple
    (204, 102, 0, 140),   # Orange
    (0, 153, 153, 140),   # Cyan
    (153, 153, 0, 140),   # Olive
]


class MowerVectorMapRenderer:
    """Renders MowerVectorMap to PNG images."""

    def __init__(self) -> None:
        self._cached_image: bytes | None = None
        self._cached_last_updated: float | None = None
        self.render_complete: bool = True

    def render(self, vector_map: MowerVectorMap | None) -> bytes | None:
        """Render a MowerVectorMap to PNG bytes.

        Args:
            vector_map: The vector map data to render.

        Returns:
            PNG image as bytes, or None if map data is invalid.
        """
        if vector_map is None:
            return None

        if not vector_map.boundary:
            _LOGGER.debug("No boundary in vector map, cannot render")
            return None

        # Cache check
        if (self._cached_image is not None
                and self._cached_last_updated == vector_map.last_updated):
            return self._cached_image

        self.render_complete = False
        try:
            image = self._render_to_image(vector_map)
            buf = io.BytesIO()
            image.save(buf, format="PNG")
            self._cached_image = buf.getvalue()
            self._cached_last_updated = vector_map.last_updated
            return self._cached_image
        finally:
            self.render_complete = True

    def _render_to_image(self, vmap: MowerVectorMap) -> Image.Image:
        """Render vector map data to a PIL Image."""
        boundary = vmap.boundary

        # Calculate image dimensions preserving aspect ratio
        map_w = boundary.width
        map_h = boundary.height

        if map_w == 0 or map_h == 0:
            return Image.new("RGBA", (100, 100), _BACKGROUND_COLOR)

        scale = min(
            (_MAX_IMAGE_SIZE - 2 * _PADDING) / max(map_w, 1),
            (_MAX_IMAGE_SIZE - 2 * _PADDING) / max(map_h, 1),
        )
        # Ensure minimum size
        scale = max(scale, _MIN_IMAGE_SIZE / max(map_w, map_h, 1))

        img_w = int(map_w * scale) + 2 * _PADDING
        img_h = int(map_h * scale) + 2 * _PADDING

        image = Image.new("RGBA", (img_w, img_h), _BACKGROUND_COLOR)
        draw = ImageDraw.Draw(image)

        def to_pixel(x: int, y: int) -> tuple[int, int]:
            """Convert map coordinates to pixel coordinates."""
            px = int((x - boundary.x1) * scale) + _PADDING
            # Flip Y axis — map coords have Y increasing downward,
            # but we want Y=0 at top of image for natural "north up" view
            py = img_h - (int((y - boundary.y1) * scale) + _PADDING)
            return (px, py)

        # 1. Draw zone fills
        for i, zone in enumerate(vmap.zones):
            if len(zone.path) < 3:
                continue
            color = _ZONE_COLORS[i % len(_ZONE_COLORS)]
            polygon = [to_pixel(x, y) for x, y in zone.path]
            draw.polygon(polygon, fill=color, outline=_ZONE_OUTLINE_COLOR, width=_ZONE_OUTLINE_WIDTH)

        # 2. Draw forbidden areas
        for zone in vmap.forbidden_areas:
            if len(zone.path) < 3:
                continue
            polygon = [to_pixel(x, y) for x, y in zone.path]
            draw.polygon(polygon, fill=_FORBIDDEN_COLOR, outline=(200, 50, 50, 220), width=2)

        # 3. Draw mowing paths (trails)
        for mow_path in vmap.mow_paths:
            for segment in mow_path.segments:
                if len(segment) < 2:
                    continue
                points = [to_pixel(x, y) for x, y in segment]
                draw.line(points, fill=_MOW_PATH_COLOR, width=_MOW_PATH_WIDTH)

        # 4. Draw navigation paths between zones
        for path in vmap.paths:
            if len(path.path) < 2:
                continue
            points = [to_pixel(x, y) for x, y in path.path]
            draw.line(points, fill=_PATH_COLOR, width=_PATH_WIDTH)

        # 5. Draw zone labels
        for zone in vmap.zones:
            if not zone.name or len(zone.path) < 3:
                continue
            # Calculate centroid for label placement
            cx = sum(x for x, y in zone.path) // len(zone.path)
            cy = sum(y for x, y in zone.path) // len(zone.path)
            px, py = to_pixel(cx, cy)
            # Draw label with area
            label = zone.name
            if zone.area > 0:
                label += f"\n{zone.area:.0f}m\u00b2"
            try:
                font = ImageFont.load_default()
            except Exception:
                font = None
            bbox = draw.textbbox((px, py), label, font=font, anchor="mm")
            # Draw background rectangle for readability
            draw.rectangle(
                [bbox[0] - 3, bbox[1] - 2, bbox[2] + 3, bbox[3] + 2],
                fill=(0, 0, 0, 160),
            )
            draw.text((px, py), label, fill=_LABEL_COLOR, font=font, anchor="mm")

        return image
```

**Step 4: Run tests to verify they pass**

Run: `cd /Users/ben/dev/Personal/dreame-mower && python -m pytest tests/test_map_renderer.py -v`
Expected: All tests PASS

**Step 5: Commit**

```bash
git add custom_components/dreame_mower/dreame/map_renderer.py tests/test_map_renderer.py
git commit -m "feat: add vector polygon map renderer for mower zones"
```

---

### Task 4: Add Batch Map Data Fetching to Map Manager

**Files:**
- Modify: `custom_components/dreame_mower/dreame/map.py` (DreameMapMowerMapManager class)

This task wires the parser into the map manager so it fetches vector map data from the batch API on each update cycle.

**Step 1: Add imports to map.py**

At the top of `custom_components/dreame_mower/dreame/map.py`, near the existing imports (around line 1-20), add:

```python
from .map_data_parser import parse_batch_map_data
from .types import MowerVectorMap
```

**Step 2: Add vector map storage to _init_data()**

In `DreameMapMowerMapManager._init_data()` (around line 170-197), add at the end of the method body:

```python
        self._vector_map: MowerVectorMap | None = None
```

**Step 3: Add vector map property**

Add a public property to `DreameMapMowerMapManager` (after `_init_data`, around line 198):

```python
    @property
    def vector_map(self) -> MowerVectorMap | None:
        """Get the current vector map data (for mower polygon rendering)."""
        return self._vector_map
```

**Step 4: Add batch data fetch method**

Add a new method to `DreameMapMowerMapManager` (after the `vector_map` property):

```python
    def _fetch_vector_map_from_batch_api(self) -> bool:
        """Fetch vector map data from the batch device data API.

        Requests MAP.*, M_PATH.*, and SETTINGS.* keys from the cloud
        batch API and parses them into a MowerVectorMap.

        Returns:
            True if map data was updated, False otherwise.
        """
        if not self._protocol.cloud or not self._protocol.cloud.logged_in:
            return False

        try:
            # Build the list of keys to fetch
            keys = []
            # MAP chunks — request up to 40 (typical is 0-32)
            for i in range(40):
                keys.append(f"MAP.{i}")
            keys.append("MAP.info")
            # M_PATH chunks
            for i in range(10):
                keys.append(f"M_PATH.{i}")
            keys.append("M_PATH.info")
            # Settings
            for i in range(5):
                keys.append(f"SETTINGS.{i}")
            keys.append("SETTINGS.info")

            batch_data = self._protocol.cloud.get_batch_device_datas(keys)
            if not batch_data:
                _LOGGER.debug("No batch data returned from cloud API")
                return False

            vector_map = parse_batch_map_data(batch_data)
            if vector_map is None:
                _LOGGER.debug("Failed to parse batch map data")
                return False

            self._vector_map = vector_map
            _LOGGER.debug(
                "Vector map updated: %d zones, %d paths, boundary=%s",
                len(vector_map.zones),
                len(vector_map.paths),
                vector_map.boundary,
            )
            return True

        except Exception as ex:
            _LOGGER.warning("Failed to fetch vector map from batch API: %s", ex)
            return False
```

**Step 5: Hook into the update() method**

In `DreameMapMowerMapManager.update()` (around line 1195-1282), find the section that handles cloud-connected devices. Near the end of the `try` block (before the `except` on approximately line 1275), add:

```python
        # Fetch vector map data from batch API (for mower polygon rendering)
        if self._protocol.dreame_cloud and self._protocol.cloud.connected:
            if (self._vector_map is None
                    or self._device_running
                    or (self._vector_map.last_updated and time.time() - self._vector_map.last_updated > 300)):
                if self._fetch_vector_map_from_batch_api():
                    self._map_data_changed()
```

This fetches vector map data when:
- No vector map exists yet (first load)
- Device is actively running (mowing)
- Map data is older than 5 minutes (background refresh)

**Step 6: Verify syntax**

Run: `python -c "import ast; ast.parse(open('custom_components/dreame_mower/dreame/map.py').read()); print('OK')"`
Expected: `OK`

**Step 7: Commit**

```bash
git add custom_components/dreame_mower/dreame/map.py
git commit -m "feat: fetch vector map data from batch API in map manager"
```

---

### Task 5: Wire Vector Map Renderer into Camera Entity

**Files:**
- Modify: `custom_components/dreame_mower/camera.py`
- Modify: `custom_components/dreame_mower/dreame/device.py`

This is the final wiring task. The camera entity needs to use the vector renderer when vector map data is available.

**Step 1: Add vector map access to device.py**

In `custom_components/dreame_mower/dreame/device.py`, add a property to `DreameMowerDevice` (near `get_map()` around line 1829):

```python
    @property
    def vector_map(self):
        """Get the current vector map data from the map manager."""
        if self._map_manager:
            return self._map_manager.vector_map
        return None
```

**Step 2: Add imports to camera.py**

At the top of `custom_components/dreame_mower/camera.py`, add:

```python
from .dreame.map_renderer import MowerVectorMapRenderer
```

**Step 3: Add vector renderer to DreameMowerCameraEntity.__init__()**

In `DreameMowerCameraEntity.__init__()` (around line 432-509), after the existing renderer initialization (around line 490), add:

```python
        # Vector map renderer for polygon-based mower maps
        self._vector_renderer = MowerVectorMapRenderer()
```

**Step 4: Modify _update_image to prefer vector map**

In `DreameMowerCameraEntity._update_image()` (around line 776-783), replace the method body. The current code is approximately:

```python
    async def _update_image(self, map_data, robot_status, station_status) -> None:
        self._image = self._renderer.render_map(map_data, robot_status, station_status)
        ...
```

Replace with:

```python
    async def _update_image(self, map_data, robot_status, station_status) -> None:
        # Prefer vector map rendering for mower polygon data
        vector_map = self.device.vector_map if self.device else None
        if vector_map and vector_map.boundary:
            rendered = await self.coordinator.hass.async_add_executor_job(
                self._vector_renderer.render, vector_map
            )
            if rendered:
                self._image = rendered
                if self._renderer._calibration_points != self._calibration_points:
                    self._calibration_points = self._renderer._calibration_points
                    self.coordinator.set_updated_data()
                return

        # Fall back to existing pixel-based renderer
        self._image = self._renderer.render_map(map_data, robot_status, station_status)
        if self._renderer._calibration_points != self._calibration_points:
            self._calibration_points = self._renderer._calibration_points
            self.coordinator.set_updated_data()
```

**Step 5: Verify syntax**

Run the following commands:
```bash
python -c "import ast; ast.parse(open('custom_components/dreame_mower/camera.py').read()); print('camera OK')"
python -c "import ast; ast.parse(open('custom_components/dreame_mower/dreame/device.py').read()); print('device OK')"
```
Expected: Both print OK

**Step 6: Commit**

```bash
git add custom_components/dreame_mower/camera.py custom_components/dreame_mower/dreame/device.py
git commit -m "feat: wire vector map renderer into camera entity"
```

---

### Task 6: Integration Test — Manual Verification

**Files:** None (verification only)

**Step 1: Run the unit tests**

Run: `cd /Users/ben/dev/Personal/dreame-mower && python -m pytest tests/ -v`
Expected: All tests pass

**Step 2: Verify all modified files parse correctly**

```bash
cd /Users/ben/dev/Personal/dreame-mower
python -c "
import ast
files = [
    'custom_components/dreame_mower/dreame/types.py',
    'custom_components/dreame_mower/dreame/map_data_parser.py',
    'custom_components/dreame_mower/dreame/map_renderer.py',
    'custom_components/dreame_mower/dreame/map.py',
    'custom_components/dreame_mower/dreame/device.py',
    'custom_components/dreame_mower/camera.py',
]
for f in files:
    ast.parse(open(f).read())
    print(f'OK: {f}')
print('All files parse successfully')
"
```
Expected: All files OK

**Step 3: Test the parser against real device data**

Create a quick test script to verify against the actual API response captured in `device-info.txt`. This validates the parser works with real-world data shapes:

```bash
cd /Users/ben/dev/Personal/dreame-mower
python -c "
from custom_components.dreame_mower.dreame.map_data_parser import parse_batch_map_data

# Simulate batch data with a minimal real-world-shaped response
import json
batch = {}

# Create a realistic MAP.0 chunk
map_data = json.dumps([json.dumps({
    'mowingAreas': {'dataType': 'Map', 'value': [
        [1, {'id': 1, 'type': 0, 'shapeType': 0,
             'path': [{'x': 4900, 'y': -10750}, {'x': 4880, 'y': -10450},
                      {'x': 4880, 'y': -9350}, {'x': 4840, 'y': -8850}],
             'name': 'Backyard', 'time': 1288, 'etime': 966, 'area': 141}],
    ]},
    'forbiddenAreas': {'dataType': 'Map', 'value': []},
    'paths': {'dataType': 'Map', 'value': []},
    'spotAreas': {'dataType': 'Map', 'value': []},
    'cleanPoints': {'dataType': 'Map', 'value': []},
    'cruisePoints': {'dataType': 'Map', 'value': []},
    'obstacles': {'dataType': 'Map', 'value': []},
    'contours': {'dataType': 'Map', 'value': []},
    'notObsAreas': {'dataType': 'Map', 'value': []},
    'md5sum': 'test',
    'totalArea': 141,
    'boundary': {'x1': -15160, 'y1': -29010, 'x2': 4900, 'y2': 5200},
    'name': '',
    'cut': [],
    'merged': False,
    'mapIndex': 0,
    'hasBack': 1,
})])
batch['MAP.0'] = map_data
batch['MAP.info'] = '1'

result = parse_batch_map_data(batch)
print(f'Zones: {len(result.zones)}')
print(f'Zone 1: {result.zones[0].name} ({result.zones[0].area}m²)')
print(f'Boundary: ({result.boundary.x1},{result.boundary.y1}) to ({result.boundary.x2},{result.boundary.y2})')
print(f'Boundary size: {result.boundary.width}x{result.boundary.height}')
print('Parser working correctly!')
"
```
Expected: Output showing zone data parsed correctly

**Step 4: Test the renderer produces a viewable image**

```bash
cd /Users/ben/dev/Personal/dreame-mower
python -c "
from custom_components.dreame_mower.dreame.map_renderer import MowerVectorMapRenderer
from custom_components.dreame_mower.dreame.types import (
    MowerVectorMap, MowerZone, MowerMapBoundary, MowerPath,
)
import time

vmap = MowerVectorMap()
vmap.boundary = MowerMapBoundary(x1=-15160, y1=-29010, x2=4900, y2=5200)
vmap.zones = [
    MowerZone(1, [(4900,-10750),(4880,-10450),(4880,-9350),(4840,-8850),
                  (4550,-5580),(3580,-4520),(1640,-4080),(1130,-2430),
                  (1390,-810),(700,3820),(-270,4150),(-3220,4270),
                  (-3220,1820),(-2520,-4070),(-2870,-7020),(-1620,-7170),
                  (970,-7420),(1820,-9220),(2920,-11720),(3970,-18570)],
                 'Backyard', area=141),
    MowerZone(2, [(-920,-26220),(-3870,-26270),(-4270,-24920),(-2570,-23120),
                  (470,-23520),(20,-25920),(-820,-26220)],
                 'Front2', area=8.89),
    MowerZone(5, [(-5790,-27450),(-11220,-27120),(-11570,-27690),
                  (-11190,-28310),(-9860,-28500),(-5720,-27570)],
                 'Street2', area=5.14),
]
vmap.paths = [
    MowerPath(201, [(3810,-17840),(1060,-22490),(-770,-24060)], path_type=1),
]
vmap.last_updated = time.time()

renderer = MowerVectorMapRenderer()
png_bytes = renderer.render(vmap)
with open('/tmp/mower_map_test.png', 'wb') as f:
    f.write(png_bytes)
print(f'Rendered {len(png_bytes)} bytes to /tmp/mower_map_test.png')
print('Open the file to verify it looks correct!')
"
```
Expected: PNG file at `/tmp/mower_map_test.png` that shows colored zone polygons with labels on a dark background

**Step 5: Open and visually verify the test image**

Run: `open /tmp/mower_map_test.png`
Expected: See a map with colored zones labeled "Backyard", "Front2", "Street2" with area labels, and a yellow navigation path line.

---

## Summary of Changes

| File | Change |
|------|--------|
| `dreame/types.py` | Add `MowerZone`, `MowerPath`, `MowerMapBoundary`, `MowerMowPath`, `MowerVectorMap` classes |
| `dreame/map_data_parser.py` | **NEW** — Parse batch API response into `MowerVectorMap` |
| `dreame/map_renderer.py` | **NEW** — Render `MowerVectorMap` to PNG with PIL |
| `dreame/map.py` | Add `_vector_map` storage, `_fetch_vector_map_from_batch_api()`, hook into `update()` |
| `dreame/device.py` | Add `vector_map` property |
| `camera.py` | Add `MowerVectorMapRenderer`, prefer vector rendering in `_update_image()` |
| `tests/conftest.py` | **NEW** — Test path config |
| `tests/test_map_data_parser.py` | **NEW** — Parser unit tests |
| `tests/test_map_renderer.py` | **NEW** — Renderer unit tests |

## Future Enhancements (Not in This Plan)

- SVG output via custom HTTP view for interactive maps
- Zone-specific settings overlay (mowing height, direction)
- Robot/charger position rendering (needs position data from device properties)
- Contour rendering
- Obstacle icons
- Color scheme customization matching the existing vacuum renderer's options
- Live mowing path updates during active mowing sessions
