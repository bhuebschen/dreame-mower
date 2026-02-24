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
    batch = {"MAP.0": '["{\\\"hello\\\":\\\"world\\\"}"]', "MAP.info": "1"}
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
    batch = {"M_PATH.0": "[]", "M_PATH.info": "2"}
    result = parse_mow_paths(batch)
    assert len(result) == 0


def test_parse_mow_paths_with_sentinel():
    # M_PATH data is chunked: M_PATH.0 is first map (empty), rest is real data
    batch = {
        "M_PATH.0": "[]",
        "M_PATH.1": "[10,20],[30,40],[32767,-32768],[50,60],[70,80]",
        "M_PATH.info": "2",
    }
    result = parse_mow_paths(batch)
    assert len(result) == 1
    # Should have segments split on sentinel
    mow_path = result[0]
    assert len(mow_path.segments) == 2
    # Coordinates are scaled 10x (decimeters -> centimeters)
    assert mow_path.segments[0] == [(100, 200), (300, 400)]
    assert mow_path.segments[1] == [(500, 600), (700, 800)]
