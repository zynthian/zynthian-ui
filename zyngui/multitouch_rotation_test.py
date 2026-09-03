#!/usr/bin/python3
# -*- coding: utf-8 -*-
# ******************************************************************************
# ZYNTHIAN PROJECT: Zynthian GUI
#
# Unit tests for MultiTouch coordinate rotation (90/270 deg touch support)
#
# ******************************************************************************
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License as
# published by the Free Software Foundation; either version 2 of
# the License, or any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# For a full copy of the GNU General Public License see the LICENSE.txt file.
#
# ******************************************************************************
"""Tests for MultiTouch.ROTATION_MAP and MultiTouch._transform_abs.

Runs standalone (``python3 zyngui/multitouch_rotation_test.py``) or under
pytest. multitouch.py imports tkinter / tkinterweb / evdev / zynthian_gui_config
at module load, so those are stubbed below to import the class with neither a
GUI, a display, nor touch hardware present.
"""

import os
import sys
from unittest.mock import MagicMock

# Make the repo root importable regardless of the current working directory.
_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

# Stub the heavy / hardware-bound deps pulled in at multitouch import time.
for _name in ("tkinter", "tkinterweb", "evdev"):
    sys.modules.setdefault(_name, MagicMock())
sys.modules.setdefault("zyngui.zynthian_gui_config", MagicMock())

from zyngui.multitouch import MultiTouch  # noqa: E402

# Reference panel: RPi Touch Display 2, native (unswapped) evdev ranges.
MAX_X, MAX_Y = 719, 1279
# Landscape screen after X11 Rotate "right": 1280 wide x 720 tall.
WIDTH, HEIGHT = MAX_Y + 1, MAX_X + 1

# Labeled corner touches captured with evtest on the reference unit, as raw
# panel (X, Y). These are the empirical oracle for the "Right" mapping.
CORNERS = {
    "top-left":     (704, 39),
    "top-right":    (649, 1218),
    "bottom-left":  (47, 98),
    "bottom-right": (67, 1197),
}


def map_xy(rotation, raw_x, raw_y, max_x=MAX_X, max_y=MAX_Y):
    """Full raw-panel -> screen mapping via the shipped map + transform.

    Feeds a raw X event and a raw Y event through MultiTouch._transform_abs
    exactly as the event loop does, then assembles (x_root, y_root).
    """
    swap, ix, iy = MultiTouch.ROTATION_MAP[rotation]
    dest_a, val_a = MultiTouch._transform_abs(
        True, raw_x, swap, ix, iy, max_x, max_y)
    dest_b, val_b = MultiTouch._transform_abs(
        False, raw_y, swap, ix, iy, max_x, max_y)
    coords = {dest_a: val_a, dest_b: val_b}
    return coords["x_root"], coords["y_root"]


def test_rotation_map_keys_and_legacy_values():
    # Exactly the four supported rotations, no more.
    assert set(MultiTouch.ROTATION_MAP) == {"None", "Right", "Inverted", "Left"}
    # Legacy behaviour must not drift:
    assert MultiTouch.ROTATION_MAP["None"] == (False, False, False)
    assert MultiTouch.ROTATION_MAP["Inverted"] == (False, True, True)


def test_none_is_identity():
    for raw_x, raw_y in CORNERS.values():
        assert map_xy("None", raw_x, raw_y) == (raw_x, raw_y)


def test_inverted_flips_both_axes():
    # Regression lock for the previous Inverted behaviour (invert both, no swap).
    for raw_x, raw_y in CORNERS.values():
        assert map_xy("Inverted", raw_x, raw_y) == (MAX_X - raw_x, MAX_Y - raw_y)


# --- Right: verified against hardware corner data ----------------------------

EXPECTED_RIGHT = {
    "top-left":     (39, 15),     # left,  top
    "top-right":    (1218, 70),   # right, top
    "bottom-left":  (98, 672),    # left,  bottom
    "bottom-right": (1197, 652),  # right, bottom
}


def test_right_exact_mapping():
    for name, (raw_x, raw_y) in CORNERS.items():
        assert map_xy("Right", raw_x, raw_y) == EXPECTED_RIGHT[name], name


def test_right_corners_land_in_correct_quadrant():
    # The "not mirrored" check: each labeled corner falls in its own quadrant.
    quadrant = {
        "top-left":     (lambda x: x < WIDTH / 2,  lambda y: y < HEIGHT / 2),
        "top-right":    (lambda x: x > WIDTH / 2,  lambda y: y < HEIGHT / 2),
        "bottom-left":  (lambda x: x < WIDTH / 2,  lambda y: y > HEIGHT / 2),
        "bottom-right": (lambda x: x > WIDTH / 2,  lambda y: y > HEIGHT / 2),
    }
    for name, (raw_x, raw_y) in CORNERS.items():
        sx, sy = map_xy("Right", raw_x, raw_y)
        chk_x, chk_y = quadrant[name]
        assert chk_x(sx) and chk_y(sy), f"{name} landed at ({sx},{sy})"


# --- Left: NOT hardware-verified; checked as the 180-deg mirror of Right -----

def test_left_is_180deg_mirror_of_right():
    # 270 deg must equal 90 deg with both screen axes flipped. Self-consistency
    # only: the Left mapping has not been confirmed on hardware.
    for raw_x, raw_y in CORNERS.values():
        rx, ry = map_xy("Right", raw_x, raw_y)
        lx, ly = map_xy("Left", raw_x, raw_y)
        assert (lx, ly) == (WIDTH - 1 - rx, HEIGHT - 1 - ry)


if __name__ == "__main__":
    _tests = [v for k, v in sorted(globals().items())
              if k.startswith("test_") and callable(v)]
    _failed = 0
    for _t in _tests:
        try:
            _t()
            print("PASS  %s" % _t.__name__)
        except AssertionError as e:
            _failed += 1
            print("FAIL  %s: %s" % (_t.__name__, e))
    print("\n%d/%d passed" % (len(_tests) - _failed, len(_tests)))
    sys.exit(1 if _failed else 0)
