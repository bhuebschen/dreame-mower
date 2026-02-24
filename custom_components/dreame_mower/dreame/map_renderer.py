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
_BACKGROUND_COLOR = (245, 245, 240)  # Light warm grey background (matches app)
_ZONE_OUTLINE_WIDTH = 2
_PATH_COLOR = (180, 180, 180, 200)  # Light grey for navigation paths (matches app)
_PATH_WIDTH = 3
_MOW_PATH_COLOR = (50, 120, 50, 180)  # Dark green for mowing trails
_MOW_PATH_WIDTH = 2
_LABEL_COLOR = (60, 60, 60, 255)  # Dark text on light background
_FORBIDDEN_COLOR = (200, 50, 50, 120)  # Red for no-go zones

# Zone fill colors — soft pastels matching the Dreame app palette
_ZONE_COLORS = [
    ((164, 210, 145, 200), (134, 190, 115, 255)),  # Green (fill, outline)
    ((160, 200, 220, 200), (130, 170, 200, 255)),   # Blue
    ((240, 200, 170, 200), (220, 175, 140, 255)),   # Beige/tan
    ((240, 180, 180, 200), (220, 150, 150, 255)),   # Pink/salmon
    ((230, 220, 160, 200), (210, 200, 130, 255)),   # Yellow
    ((190, 170, 220, 200), (170, 145, 200, 255)),   # Purple
    ((170, 215, 210, 200), (140, 195, 190, 255)),   # Teal
    ((220, 190, 160, 200), (200, 165, 130, 255)),   # Warm brown
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
            """Convert map coordinates to pixel coordinates.

            X axis is mirrored to match the Dreame app's orientation.
            Y axis maps directly (higher Y = lower on screen).
            """
            px = img_w - (int((x - boundary.x1) * scale) + _PADDING)
            py = int((y - boundary.y1) * scale) + _PADDING
            return (px, py)

        # Load font for labels
        font = None
        for font_path in [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",      # Linux/Docker
            "/usr/share/fonts/truetype/freefont/FreeSans.ttf",       # Linux alt
            "/System/Library/Fonts/Helvetica.ttc",                    # macOS
            "/System/Library/Fonts/SFCompact.ttf",                    # macOS alt
        ]:
            try:
                font = ImageFont.truetype(font_path, size=48)
                break
            except (OSError, IOError):
                continue
        if font is None:
            try:
                font = ImageFont.load_default(size=40)
            except TypeError:
                font = ImageFont.load_default()

        # 1. Draw zone fills
        for i, zone in enumerate(vmap.zones):
            if len(zone.path) < 3:
                continue
            fill_color, outline_color = _ZONE_COLORS[i % len(_ZONE_COLORS)]
            polygon = [to_pixel(x, y) for x, y in zone.path]
            draw.polygon(polygon, fill=fill_color, outline=outline_color, width=_ZONE_OUTLINE_WIDTH)

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
            label = zone.name
            # Subtle white shadow for readability on colored zones
            for dx, dy in [(-2, -2), (-2, 2), (2, -2), (2, 2), (-2, 0), (2, 0), (0, -2), (0, 2)]:
                draw.text((px + dx, py + dy), label, fill=(255, 255, 255, 120), font=font, anchor="mm")
            draw.text((px, py), label, fill=_LABEL_COLOR, font=font, anchor="mm")

        return image
