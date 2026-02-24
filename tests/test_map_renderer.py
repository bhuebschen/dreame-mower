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
