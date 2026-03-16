"""Interactive ROI (Region of Interest) selection utility.

Supports both rectangular and polygon ROI selection with a full GUI.
Points are clickable, draggable, and coordinates are copyable to clipboard.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from aiops.core.log import get_logger
from aiops.core.types import ImageArray

logger = get_logger(__name__)

# Colors (BGR)
_GREEN = (0, 255, 0)
_RED = (0, 0, 255)
_BLUE = (255, 100, 0)
_YELLOW = (0, 255, 255)
_WHITE = (255, 255, 255)
_BLACK = (0, 0, 0)
_OVERLAY_COLOR = (0, 255, 0)

_POINT_RADIUS = 6
_LINE_THICKNESS = 2
_FONT = cv2.FONT_HERSHEY_SIMPLEX
_FONT_SCALE = 0.45
_HELP_TEXT = [
    "LEFT CLICK  - add point",
    "RIGHT CLICK - remove last point",
    "M           - toggle move mode (drag points)",
    "C           - copy coordinates to clipboard",
    "R           - reset all points",
    "ENTER       - confirm selection",
    "ESC         - cancel",
]


class PolygonROI:
    """Polygon region of interest defined by a list of points.

    Attributes:
        points: list of (x, y) tuples defining the polygon vertices.
    """

    def __init__(self, points: list[tuple[int, int]] | None = None) -> None:
        self.points: list[tuple[int, int]] = list(points) if points else []

    @property
    def num_points(self) -> int:
        return len(self.points)

    @property
    def bounding_rect(self) -> tuple[int, int, int, int]:
        """Return (x, y, w, h) bounding rectangle."""
        if not self.points:
            return (0, 0, 0, 0)
        xs = [p[0] for p in self.points]
        ys = [p[1] for p in self.points]
        x, y = min(xs), min(ys)
        return (x, y, max(xs) - x, max(ys) - y)

    def as_numpy(self) -> np.ndarray:
        """Return points as numpy array of shape (N, 1, 2) for OpenCV."""
        return np.array(self.points, dtype=np.int32).reshape((-1, 1, 2))

    def crop(self, image: ImageArray) -> ImageArray:
        """Crop image to the bounding rect of the polygon, with mask applied."""
        if len(self.points) < 3:
            x, y, w, h = self.bounding_rect
            return image[y : y + h, x : x + w]

        mask = np.zeros(image.shape[:2], dtype=np.uint8)
        cv2.fillPoly(mask, [self.as_numpy()], 255)

        x, y, w, h = self.bounding_rect
        cropped = image[y : y + h, x : x + w].copy()
        mask_crop = mask[y : y + h, x : x + w]

        # Apply mask — black out pixels outside polygon
        result = cv2.bitwise_and(cropped, cropped, mask=mask_crop)
        return result

    def contains(self, x: int, y: int) -> bool:
        """Check if a point is inside the polygon."""
        if len(self.points) < 3:
            return False
        return cv2.pointPolygonTest(self.as_numpy(), (float(x), float(y)), False) >= 0

    def to_list(self) -> list[list[int]]:
        """Return points as [[x1,y1], [x2,y2], ...]."""
        return [[x, y] for x, y in self.points]

    def to_string(self) -> str:
        """Return a copyable string representation."""
        return json.dumps(self.to_list())

    def __repr__(self) -> str:
        return f"PolygonROI(points={self.to_list()})"


class ROISelector:
    """Interactive ROI selection with polygon support and coordinate copying.

    Usage:
        selector = ROISelector()

        # Polygon selection (click points)
        roi = selector.select("image.png")
        print(roi.points)           # [(x1,y1), (x2,y2), ...]
        cropped = roi.crop(image)

        # Copy coordinates
        print(roi.to_string())      # [[x1,y1],[x2,y2],...]

    Controls:
        LEFT CLICK  - add point
        RIGHT CLICK - remove last point
        M           - toggle move mode (drag points)
        C           - copy coordinates to clipboard
        R           - reset all points
        ENTER       - confirm selection
        ESC         - cancel
    """

    def __init__(self, presets_file: str | Path | None = None) -> None:
        self._presets_file = Path(presets_file) if presets_file else None
        self._presets: dict[str, PolygonROI] = {}
        if self._presets_file and self._presets_file.exists():
            self._load_presets()

    def select(
        self,
        image: ImageArray | str | Path,
        window_name: str = "ROI Selector",
    ) -> PolygonROI:
        """Open interactive window to select polygon ROI by clicking points.

        Returns:
            PolygonROI with the selected polygon vertices.
        """
        if isinstance(image, (str, Path)):
            img = cv2.imread(str(image))
            if img is None:
                raise FileNotFoundError(f"Cannot read image: {image}")
        else:
            img = image.copy()

        state = _SelectionState(img)
        cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
        cv2.setMouseCallback(window_name, state.mouse_callback)

        state.redraw()

        while True:
            cv2.imshow(window_name, state.display)
            key = cv2.waitKey(20) & 0xFF

            if key == 27:  # ESC — cancel
                cv2.destroyAllWindows()
                raise ValueError("Selection cancelled")

            elif key == 13 or key == 10:  # ENTER — confirm
                if state.roi.num_points < 3:
                    state.set_status("Need at least 3 points!", color=_RED)
                    state.redraw()
                    continue
                break

            elif key == ord("r"):  # Reset
                state.roi = PolygonROI()
                state.set_status("Reset — click to add points")
                state.redraw()

            elif key == ord("m"):  # Toggle move mode
                state.move_mode = not state.move_mode
                mode = "ON" if state.move_mode else "OFF"
                state.set_status(f"Move mode: {mode}")
                state.redraw()

            elif key == ord("c"):  # Copy coordinates
                coords = state.roi.to_string()
                _copy_to_clipboard(coords)
                state.set_status(f"Copied: {coords}", color=_GREEN)
                state.redraw()

        cv2.destroyAllWindows()

        logger.info(f"ROI selected: {state.roi.num_points} points — {state.roi.to_string()}")
        print(f"\nROI coordinates: {state.roi.to_string()}")
        return state.roi

    def preview(
        self,
        image: ImageArray,
        roi: PolygonROI,
        window_name: str = "ROI Preview",
    ) -> None:
        """Show ROI overlay and cropped region side by side."""
        display = image.copy()

        if roi.num_points >= 3:
            overlay = display.copy()
            cv2.fillPoly(overlay, [roi.as_numpy()], (*_OVERLAY_COLOR, 50))
            cv2.addWeighted(overlay, 0.3, display, 0.7, 0, display)
            cv2.polylines(display, [roi.as_numpy()], True, _GREEN, 2)

        for pt in roi.points:
            cv2.circle(display, pt, _POINT_RADIUS, _RED, -1)

        cv2.imshow(window_name, display)

        if roi.num_points >= 3:
            cropped = roi.crop(image)
            cv2.imshow("Cropped ROI", cropped)

        cv2.waitKey(0)
        cv2.destroyAllWindows()

    def apply(self, image: ImageArray, roi: PolygonROI) -> ImageArray:
        """Crop image using polygon ROI."""
        return roi.crop(image)

    def save_preset(self, name: str, roi: PolygonROI) -> None:
        """Save ROI as a named preset."""
        self._presets[name] = roi
        if self._presets_file:
            self._save_presets()
        logger.info(f"Saved ROI preset '{name}': {roi.to_string()}")

    def load_preset(self, name: str) -> PolygonROI:
        """Load a saved ROI preset by name."""
        if name not in self._presets:
            available = list(self._presets.keys())
            raise KeyError(f"ROI preset '{name}' not found. Available: {available}")
        return self._presets[name]

    def list_presets(self) -> dict[str, PolygonROI]:
        """List all saved ROI presets."""
        return dict(self._presets)

    def _save_presets(self) -> None:
        data = {name: roi.to_list() for name, roi in self._presets.items()}
        self._presets_file.parent.mkdir(parents=True, exist_ok=True)
        self._presets_file.write_text(json.dumps(data, indent=2))

    def _load_presets(self) -> None:
        data = json.loads(self._presets_file.read_text())
        self._presets = {
            name: PolygonROI([(p[0], p[1]) for p in pts])
            for name, pts in data.items()
        }


class _SelectionState:
    """Internal state for the interactive ROI selection window."""

    def __init__(self, image: ImageArray) -> None:
        self.original = image.copy()
        self.display = image.copy()
        self.roi = PolygonROI()
        self.move_mode = False
        self._dragging_idx: int | None = None
        self._status = "Click to add points | ENTER to confirm | ESC to cancel"
        self._status_color = _WHITE

    def set_status(self, text: str, color: tuple = _WHITE) -> None:
        self._status = text
        self._status_color = color

    def mouse_callback(self, event: int, x: int, y: int, flags: int, param: Any) -> None:
        if self.move_mode:
            self._handle_move(event, x, y)
        else:
            self._handle_draw(event, x, y)

    def _handle_draw(self, event: int, x: int, y: int) -> None:
        if event == cv2.EVENT_LBUTTONDOWN:
            self.roi.points.append((x, y))
            self.set_status(f"Point {self.roi.num_points} added at ({x}, {y})")
            self.redraw()

        elif event == cv2.EVENT_RBUTTONDOWN:
            if self.roi.points:
                removed = self.roi.points.pop()
                self.set_status(f"Removed point ({removed[0]}, {removed[1]})")
                self.redraw()

    def _handle_move(self, event: int, x: int, y: int) -> None:
        if event == cv2.EVENT_LBUTTONDOWN:
            self._dragging_idx = self._find_nearest_point(x, y, threshold=15)
            if self._dragging_idx is not None:
                self.set_status(f"Dragging point {self._dragging_idx + 1}")

        elif event == cv2.EVENT_MOUSEMOVE and self._dragging_idx is not None:
            self.roi.points[self._dragging_idx] = (x, y)
            self.redraw()

        elif event == cv2.EVENT_LBUTTONUP:
            if self._dragging_idx is not None:
                pt = self.roi.points[self._dragging_idx]
                self.set_status(f"Moved point {self._dragging_idx + 1} to ({pt[0]}, {pt[1]})")
                self._dragging_idx = None
                self.redraw()

    def _find_nearest_point(self, x: int, y: int, threshold: int = 15) -> int | None:
        """Find the index of the nearest point within threshold distance."""
        min_dist = float("inf")
        nearest = None
        for i, (px, py) in enumerate(self.roi.points):
            dist = ((px - x) ** 2 + (py - y) ** 2) ** 0.5
            if dist < min_dist and dist < threshold:
                min_dist = dist
                nearest = i
        return nearest

    def redraw(self) -> None:
        """Redraw the display with current polygon state."""
        self.display = self.original.copy()
        points = self.roi.points

        if not points:
            self._draw_help()
            self._draw_status_bar()
            return

        # Draw filled polygon overlay (semi-transparent)
        if len(points) >= 3:
            overlay = self.display.copy()
            cv2.fillPoly(overlay, [self.roi.as_numpy()], _OVERLAY_COLOR)
            cv2.addWeighted(overlay, 0.2, self.display, 0.8, 0, self.display)

        # Draw polygon outline
        if len(points) >= 2:
            for i in range(len(points) - 1):
                cv2.line(self.display, points[i], points[i + 1], _GREEN, _LINE_THICKNESS)
            if len(points) >= 3:
                # Close the polygon
                cv2.line(self.display, points[-1], points[0], _GREEN, _LINE_THICKNESS)

        # Draw points with index labels
        for i, (px, py) in enumerate(points):
            color = _YELLOW if self.move_mode and i == self._dragging_idx else _RED
            cv2.circle(self.display, (px, py), _POINT_RADIUS, color, -1)
            cv2.circle(self.display, (px, py), _POINT_RADIUS, _WHITE, 1)
            # Point label
            label = f"{i + 1}:({px},{py})"
            cv2.putText(self.display, label, (px + 10, py - 8), _FONT, _FONT_SCALE, _WHITE, 2)
            cv2.putText(self.display, label, (px + 10, py - 8), _FONT, _FONT_SCALE, _BLACK, 1)

        # Mode indicator
        if self.move_mode:
            cv2.putText(self.display, "MOVE MODE", (10, 25), _FONT, 0.6, _YELLOW, 2)

        self._draw_status_bar()

    def _draw_help(self) -> None:
        """Draw help text on empty canvas."""
        y = 30
        for line in _HELP_TEXT:
            cv2.putText(self.display, line, (10, y), _FONT, _FONT_SCALE, _WHITE, 1)
            y += 22

    def _draw_status_bar(self) -> None:
        """Draw status bar at bottom of image."""
        h, w = self.display.shape[:2]
        bar_h = 30
        cv2.rectangle(self.display, (0, h - bar_h), (w, h), _BLACK, -1)
        text = f"{self._status}  |  Points: {self.roi.num_points}"
        cv2.putText(
            self.display, text, (8, h - 9),
            _FONT, _FONT_SCALE, self._status_color, 1,
        )


def _copy_to_clipboard(text: str) -> None:
    """Copy text to system clipboard. Falls back to printing if unavailable."""
    import subprocess
    import shutil

    if shutil.which("xclip"):
        proc = subprocess.run(
            ["xclip", "-selection", "clipboard"],
            input=text.encode(), capture_output=True,
        )
        if proc.returncode == 0:
            return

    if shutil.which("xsel"):
        proc = subprocess.run(
            ["xsel", "--clipboard", "--input"],
            input=text.encode(), capture_output=True,
        )
        if proc.returncode == 0:
            return

    if shutil.which("wl-copy"):
        proc = subprocess.run(
            ["wl-copy"], input=text.encode(), capture_output=True,
        )
        if proc.returncode == 0:
            return

    if shutil.which("pbcopy"):
        proc = subprocess.run(
            ["pbcopy"], input=text.encode(), capture_output=True,
        )
        if proc.returncode == 0:
            return

    logger.warning("No clipboard tool found — printing coordinates instead")
    print(f"\nCoordinates (copy manually): {text}")
