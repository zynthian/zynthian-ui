#!/usr/bin/python3
# -*- coding: utf-8 -*-
# ******************************************************************************
# ZYNTHIAN PROJECT: Zynthian Control Device Driver
#
# Zynthian Control Device Driver for "Akai APC Key 25 mk2", with support for
# SooperLooper functions
#
# Copyright (C) 2025 Niels Giesen
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

import logging
import time
import random
import functools
from os import listdir, mkdir
from os.path import isdir, isfile, join
from dataclasses import dataclass, field
from threading import Timer
from typing import Dict, Any, Callable, List
from itertools import chain, islice

import liblo

from zyncoder.zyncore import lib_zyncore
from zyngine.zynthian_engine_sooperlooper import (
    zynthian_engine_sooperlooper,
    SL_STATE_UNKNOWN,
    SL_STATE_OFF,
    SL_STATE_REC_STARTING,
    SL_STATE_RECORDING,
    SL_STATE_REC_STOPPING,
    SL_STATE_PLAYING,
    SL_STATE_OVERDUBBING,
    SL_STATE_MULTIPLYING,
    SL_STATE_INSERTING,
    SL_STATE_REPLACING,
    SL_STATE_DELAYING,
    SL_STATE_MUTED,
    SL_STATE_SCRATCHING,
    SL_STATE_PLAYING_ONCE,
    SL_STATE_SUBSTITUTING,
    SL_STATE_PAUSED,
    SL_STATE_UNDO_ALL,
    SL_STATE_TRIGGER_PLAY,
    SL_STATE_UNDO,
    SL_STATE_REDO,
    SL_STATE_REDO_ALL,
    SL_STATE_OFF_MUTED,
)
from zyngine.ctrldev.zynthian_ctrldev_base_ui import ModeHandlerBase
from zyngine.ctrldev.zynthian_ctrldev_base_extended import KnobSpeedControl
from zyngine.ctrldev.zynthian_ctrldev_akai_apc_key25_mk2 import \
    zynthian_ctrldev_akai_apc_key25_mk2, FeedbackLEDs


class BRIGHTS:
    LED_OFF = 0x80
    LED_BRIGHT_10 = 0x90
    LED_BRIGHT_25 = 0x91
    LED_BRIGHT_50 = 0x92
    LED_BRIGHT_65 = 0x93
    LED_BRIGHT_75 = 0x94
    LED_BRIGHT_90 = 0x95
    LED_BRIGHT_100 = 0x96
    LED_PULSING_16 = 0x97
    LED_PULSING_8 = 0x98
    LED_PULSING_4 = 0x99
    LED_PULSING_2 = 0x9A
    LED_BLINKING_24 = 0x9B
    LED_BLINKING_16 = 0x9C
    LED_BLINKING_8 = 0x9D
    LED_BLINKING_4 = 0x9E
    LED_BLINKING_2 = 0x9F


LED_BRIGHTS = [
    BRIGHTS.LED_BRIGHT_10,
    BRIGHTS.LED_BRIGHT_25,
    BRIGHTS.LED_BRIGHT_50,
    BRIGHTS.LED_BRIGHT_65,
    BRIGHTS.LED_BRIGHT_75,
    BRIGHTS.LED_BRIGHT_90,
    BRIGHTS.LED_BRIGHT_100,
]


class BUTTONS:
    BTN_SHIFT = 0x62
    BTN_STOP_ALL_CLIPS = 0x51
    BTN_PLAY = 0x5B
    BTN_RECORD = 0x5D

    BTN_TRACK_1 = BTN_UP = 0x40
    BTN_TRACK_2 = BTN_DOWN = 0x41
    BTN_TRACK_3 = BTN_LEFT = BTN_UNDO = 0x42
    BTN_TRACK_4 = BTN_RIGHT = BTN_REDO = 0x43
    BTN_TRACK_5 = BTN_KNOB_CTRL_VOLUME = 0x44
    BTN_TRACK_6 = BTN_KNOB_CTRL_PAN = 0x45
    BTN_TRACK_7 = BTN_KNOB_CTRL_SEND = 0x46
    BTN_TRACK_8 = BTN_KNOB_CTRL_DEVICE = 0x47

    BTN_SOFT_KEY_START = 0x52
    BTN_SOFT_KEY_END = 0x56
    BTN_SOFT_KEY_CLIP_STOP = BTN_KNOB_1 = 0x52
    BTN_SOFT_KEY_SOLO = BTN_KNOB_2 = 0x53
    BTN_SOFT_KEY_MUTE = BTN_KNOB_3 = 0x54
    BTN_SOFT_KEY_REC_ARM = BTN_KNOB_4 = 0x55
    BTN_SOFT_KEY_SELECT = 0x56

    BTN_PAD_START = 0x00
    BTN_PAD_END = 0x27
    BTN_PAD_29 = BTN_ALT = 0x1C
    BTN_PAD_30 = BTN_METRONOME = 0x1D
    BTN_PAD_31 = BTN_PAD_STEP = 0x1E
    BTN_PAD_37 = BTN_OPT_ADMIN = 0x24
    BTN_PAD_38 = BTN_MIX_LEVEL = 0x25
    BTN_PAD_39 = BTN_CTRL_PRESET = 0x26
    BTN_PAD_40 = BTN_ZS3_SHOT = 0x27
    BTN_PAD_5 = BTN_PAD_LEFT = 0x04
    BTN_PAD_6 = BTN_PAD_DOWN = 0x05
    BTN_PAD_7 = BTN_PAD_RIGHT = 0x06
    BTN_PAD_8 = BTN_F4 = 0x07
    BTN_PAD_13 = BTN_BACK_NO = 0x0C
    BTN_PAD_14 = BTN_PAD_UP = 0x0D
    BTN_PAD_15 = BTN_SEL_YES = 0x0E
    BTN_PAD_16 = BTN_F3 = 0x0F
    BTN_PAD_21 = BTN_PAD_RECORD = 0x14
    BTN_PAD_23 = BTN_PAD_PLAY = 0x16
    BTN_PAD_24 = BTN_F2 = 0x17
    BTN_PAD_32 = BTN_F1 = 0x1F


class COLORS:
    COLOR_BLACK = 0x00
    COLOR_DARK_GREY = 0x01
    COLOR_RED = 0x05
    COLOR_GREEN = 0x15
    COLOR_BLUE = 0x25
    COLOR_AQUA = 0x21
    COLOR_BLUE_DARK = 0x2D
    COLOR_BLUE_LIGHT = 0x24
    COLOR_WHITE = 0x03
    COLOR_EGYPT = 0x6C
    COLOR_ORANGE = 0x09
    COLOR_ORANGE_LIGHT = 0x08
    COLOR_AMBER = 0x54
    COLOR_RUSSET = 0x3D
    COLOR_PURPLE = 0x51
    COLOR_PINK = 0x39
    COLOR_PINK_LIGHT = 0x52
    COLOR_PINK_WARM = 0x38
    COLOR_YELLOW = 0x0D
    COLOR_LIME = 0x4B
    COLOR_LIME_DARK = 0x11
    COLOR_DARK_GREEN = 0x41
    COLOR_GREEN_YELLOW = 0x4A
    COLOR_BROWNISH_RED = 0x0A
    COLOR_BROWN_LIGHT = 0x7E
    SOFT_OFF = 0x00
    SOFT_ON = 0x01
    SOFT_BLINK = 0x02


COLS = 8
ROWS = 5
KNOBS_PER_ROW = 4

# LED states
LED_ON = 1
EV_NOTE_ON = 0x09
EV_NOTE_OFF = 0x08
EV_CC = 0x0B

PAD_ENABLE_SL = 0x07


class zynthian_ctrldev_akai_apc_key25_mk2_sooperlooper(zynthian_ctrldev_akai_apc_key25_mk2):

    driver_name = 'AKAI APC Key25 MK2 + SL'

    def __init__(self, state_manager, idev_in, idev_out=None):
        super().__init__(state_manager, idev_in, idev_out)
        self._sooperlooper_handler = looper_handler(
            state_manager, self._leds, idev_in, idev_out, self)

    def _on_midi_event(self, ev):
        evtype = (ev[0] >> 4) & 0x0F

        if evtype == EV_NOTE_ON:
            note = ev[1] & 0x7F

            if self._is_shifted:
                old_handler = self._current_handler

                if note == PAD_ENABLE_SL:
                    self._current_handler = self._sooperlooper_handler

                if old_handler != self._current_handler:
                    old_handler.set_active(False)
                    self._current_handler.set_active(True)

        return super()._on_midi_event(ev)


TRACK_COMMANDS = [
    SL_STATE_RECORDING,
    SL_STATE_MULTIPLYING,
    SL_STATE_INSERTING,
    SL_STATE_REPLACING,
    SL_STATE_SUBSTITUTING,
    SL_STATE_PLAYING_ONCE,
    SL_STATE_TRIGGER_PLAY,
    SL_STATE_PAUSED,
]
TRACK_LEVELS = [
    "in_peak_meter",
    "rec_thresh",
    "input_gain",
    "wet",
    "dry",
    "feedback",
    "pitch_shift",
    "none",
]
LEVEL_COLORS = [
    COLORS.COLOR_RED,
    COLORS.COLOR_RED,
    COLORS.COLOR_LIME,COLORS.COLOR_BLUE,
    COLORS.COLOR_DARK_GREY,
    COLORS.COLOR_PURPLE,
    COLORS.COLOR_WHITE,
    COLORS.COLOR_WHITE,
]
LEVEL_BOUNDS = {
    "in_peak_meter": (0, 1),
    "rec_thresh": (0, 1),
    "input_gain": (0, 1),
    "wet" : (0, 1),
    "dry": (0, 1),
    "feedback": (0, 1),
    "pitch_shift": (-12, 12),
    "none": (0, 1),
}
SYNC_SOURCE_CHARS = {
    # -3 = internal, -2 = midi, -1 = jack, 0 = none, # > 0 = loop number (1 indexed)
    -3: 'I',
    -2: 'M',
    -1: 'J',
     0:  '-'
}

def syncSourceChar(source):
    if source > 0:
        return source
    return SYNC_SOURCE_CHARS.get(source, '')

# @todo factor out this from here and zynthian_engine_sooperlooper?
# ------------------------------------------------------------------------------
# Sooper Looper State Codes
# ------------------------------------------------------------------------------

# From sooperlooper engine

SL_STATES = {
    SL_STATE_UNKNOWN: {
        "name": "unknown",
        "color": COLORS.COLOR_BLACK,
        "ledmode": BRIGHTS.LED_OFF,
    },
    SL_STATE_OFF: {
        "name": "off",
        "color": COLORS.COLOR_WHITE,
        "ledmode": BRIGHTS.LED_BRIGHT_100,
    },
    SL_STATE_REC_STARTING: {
        "name": "waitstart",
        "color": COLORS.COLOR_RED,
        "ledmode": BRIGHTS.LED_PULSING_16,
    },
    SL_STATE_RECORDING: {
        "name": "record",
        "color": COLORS.COLOR_RED,
        "ledmode": BRIGHTS.LED_BRIGHT_100,
    },
    SL_STATE_REC_STOPPING: {
        "name": "waitstop",
        "color": COLORS.COLOR_RED,
        "ledmode": BRIGHTS.LED_PULSING_8,
    },
    SL_STATE_PLAYING: {
        "name": "play",
        "color": COLORS.COLOR_GREEN,
        "ledmode": BRIGHTS.LED_BRIGHT_100,
    },
    SL_STATE_OVERDUBBING: {
        "name": "overdub",
        "color": COLORS.COLOR_PURPLE,
        "ledmode": BRIGHTS.LED_BRIGHT_100,
    },
    SL_STATE_MULTIPLYING: {
        "name": "multiply",
        "color": COLORS.COLOR_AMBER,
        "ledmode": BRIGHTS.LED_BRIGHT_100,
    },
    SL_STATE_INSERTING: {
        "name": "insert",
        "color": COLORS.COLOR_PINK_WARM,
        "ledmode": BRIGHTS.LED_BRIGHT_100,
    },
    SL_STATE_REPLACING: {
        "name": "replace",
        "color": COLORS.COLOR_PINK_LIGHT,
        "ledmode": BRIGHTS.LED_BRIGHT_100,
    },
    SL_STATE_SUBSTITUTING: {
        "name": "substitute",
        "color": COLORS.COLOR_PINK,
        "ledmode": BRIGHTS.LED_BRIGHT_100,
    },
    SL_STATE_DELAYING: {
        "name": "delay",
        "color": COLORS.COLOR_RED,
        "ledmode": BRIGHTS.LED_BRIGHT_10,
    },
    SL_STATE_MUTED: {
        "name": "mute",
        "color": COLORS.COLOR_DARK_GREEN,
        "ledmode": BRIGHTS.LED_BRIGHT_100,
    },
    SL_STATE_SCRATCHING: {
        "name": "scratch",
        "color": COLORS.COLOR_BLUE,
        "ledmode": BRIGHTS.LED_BRIGHT_100,
    },
    SL_STATE_PLAYING_ONCE: {
        "name": "oneshot",
        "color": COLORS.COLOR_LIME_DARK,
        "ledmode": BRIGHTS.LED_PULSING_8,
    },
    SL_STATE_PAUSED: {
        "name": "pause",
        "color": COLORS.COLOR_GREEN_YELLOW,
        "ledmode": BRIGHTS.LED_BRIGHT_100,
    },
    SL_STATE_UNDO_ALL: {
        "name": "undo_all",
        "color": COLORS.COLOR_DARK_GREY,
        "ledmode": BRIGHTS.LED_BRIGHT_100,
    },
    SL_STATE_UNDO: {
        "name": "undo_all",
        "color": COLORS.COLOR_DARK_GREY,
        "ledmode": BRIGHTS.LED_BRIGHT_50,
    },
    SL_STATE_REDO: {
        "name": "redo",
        "color": COLORS.COLOR_DARK_GREY,
        "ledmode": BRIGHTS.LED_BRIGHT_50,
    },
    SL_STATE_REDO_ALL: {
        "name": "redo_all",
        "color": COLORS.COLOR_DARK_GREY,
        "ledmode": BRIGHTS.LED_BRIGHT_100,
    },
    SL_STATE_OFF_MUTED: {
        "name": "offmute",
        "color": COLORS.COLOR_RED,
        "ledmode": BRIGHTS.LED_BRIGHT_100,
    },  # undocumented
    SL_STATE_TRIGGER_PLAY: {
        "name": "trigger_play",
        "color": COLORS.COLOR_GREEN,
        "ledmode": BRIGHTS.LED_BRIGHT_100,
    },
}

SETTINGS = [
    "sync",
    "relative_sync",
    "playback_sync",
    "mute_quantized",
    "overdub_quantized",
    "replace_quantized",
    None,
    None,  # "quantize",
]

SETTINGCOLORS = [
    COLORS.COLOR_BLUE,
    COLORS.COLOR_LIME,
    COLORS.COLOR_GREEN,
    COLORS.COLOR_DARK_GREEN,
    COLORS.COLOR_PURPLE,
    COLORS.COLOR_PINK_LIGHT,
    # -3 = internal,  -2 = midi, -1 = jack, 0 = none, # > 0 = loop number (1 indexed)
    [
        COLORS.COLOR_WHITE,
        COLORS.COLOR_ORANGE,
        COLORS.COLOR_RED,
        COLORS.COLOR_DARK_GREY,
        COLORS.COLOR_BLUE,
        COLORS.COLOR_BLUE_DARK,
    ],
    [
        COLORS.COLOR_WHITE,
        COLORS.COLOR_ORANGE,
        COLORS.COLOR_BROWNISH_RED,
        COLORS.COLOR_BLUE,
    ],
]
PATH_LOOP_OFFSET = ["device", "loopoffset"]
CHARS = {
    1: ["_._", ".._", "_._", "_._", "..."],
    2: ["_._", "._.", "__.", "_._", "..."],
    3: ["...", "__.", "_._", "__.", ".._"],
    4: [".__", "._.", "...", "__.", "__."],
    5: ["...", ".__", "...", "__.", "..."],
    6: ["_._", ".__", "...", "._.", "..."],
    7: ["...", "__.", "_._", "_._", ".__"],
    8: ["...", "._.", "...", "._.", "..."],
    9: ["_._", "._.", "...", "__.", "..."],
    0: ["_._", "._.", "._.", "._.", "_._"],
   'J': ["...", "__.", "__.", "._.", "_._"],
   'M': ["._.", "...", "._.", "._.", "._."],
   'I': ["...", "_._", "_._", "_._", "..."],
   '': ["___", "___", "___", "___", "___"],
   '-': ["___", "___", "...", "___", "___"],
}
matrixPadLedmode = {".": BRIGHTS.LED_BRIGHT_100, "_": BRIGHTS.LED_BRIGHT_10}
matrixPadColor = {".": COLORS.COLOR_WHITE, "_": COLORS.COLOR_DARK_GREY}

def toggle_value(value, lst):
    if value in lst:
        lst.remove(value)  # Remove the value if it's already in the list
    else:
        lst.append(value)
    return lst

# Some 'functional' code (well, not really)
def path(keys, obj):
    """Retrieve the value at the specified path in a nested dictionary."""
    for key in keys:
        if isinstance(obj, dict) and key in obj:
            obj = obj[key]
        else:
            return None  # Return None if the key does not exist
    return obj


def assoc_path(state, path, value):
    """Associates a value at a given path in a dictionary."""
    d = state
    for key in path[:-1]:
        d = d.setdefault(key, {})
    d[path[-1]] = value
    return state


def split_every(n, iterable):
    """Split an iterable into chunks of size n."""
    it = iter(iterable)
    while chunk := list(islice(it, n)):
        yield chunk

# Calculate the difference
def generator_difference(gen_a, gen_b_set):
    for item in gen_a:
        if item not in gen_b_set:
            yield item

def overlay(*arrays):
    # logging.debug(f"arrays {arrays}")

    # Step 1: Split each array into chunks of 3
    split_arrays = [list(split_every(3, array)) for array in arrays]
    # logging.debug(f"split {split_arrays}")

    # Step 2: Concatenate all the arrays into a single list
    concatenated = list(chain.from_iterable(split_arrays))
    # logging.debug(f"concatenated {concatenated}")

    # Step 3: Remove duplicates based on the second element
    # unique = {tuple(item): item for item in concatenated}.values()
    # unique = {tuple(map(tuple, item)): item for item in concatenated}.values()
    unique = []
    seen = set()
    for item in concatenated:
        second_item = item[1]
        if second_item not in seen:
            unique.append(item)
            seen.add(second_item)

    # logging.debug(f"unique {unique}")
    # Step 4: Sort by the second element
    sorted_unique = sorted(unique, key=lambda x: x[1])

    # Step 5: Flatten the list (if needed)
    flattened = list(chain.from_iterable(sorted_unique))

    return flattened


def list_get(lst, index, default=None):
    """Return the element at the specified index, or default if the index is out of range."""
    try:
        if 0 <= index < len(lst):
            return lst[index]
        return default
    except KeyError:
        return default


def cycle(from_val, to, cur):
    return (cur - from_val + 1) % (to - from_val + 1) + from_val


# PAD FUNCTIONS


def rowStartPad(y):
    return (ROWS - 1 - y) * COLS


def rowPads(track):
    padoffset = rowStartPad(track)
    return map(lambda n: n + padoffset, range(0, COLS))


def padRow(pad):
    return range(ROWS - 1, -1, -1).index((pad / COLS) // 1)

def confirmrow(pad, cols):
    row = int(pad / cols) - 1
    if pad < cols:              # Last row
        row = 1
    return row

def confirmcols(pad, cols):
    numpad = (pad % cols)
    if numpad == 0: # First pad
        return [0,1]
    if numpad == cols - 1: # Last pad
        return [cols - 2, cols - 1]
    return [numpad - 1, numpad + 1]

def get_pad(cols, col, row):
    return (row * cols) + col

def confirmers(pad, cols):
    row = confirmrow(pad, cols)
    [no, yes] = confirmcols(pad, cols)
    return [get_pad(cols, no, row), get_pad(cols, yes, row)]

def shiftedTrack(track, offset):
    return track - offset


def makeSessionNumberReducer(color, last):
    def sessionNumberReducer(acc, cur):
        try:
            pad = int(cur[:-7])
            return acc + [
                BRIGHTS.LED_PULSING_8 if pad == last else BRIGHTS.LED_BRIGHT_100,
                pad,
                color,
            ]
        except ValueError:
            return acc

    return sessionNumberReducer


# Pad coloring
def padBrightnessForLevel(num, level, ctrl):
    min, max = LEVEL_BOUNDS.get(ctrl)
    scale = max - min
    level = (level - min) / scale
    pos = num * level
    # logging.debug(f"{pos}--{num}--{level}")
    roundedpos = pos // 1
    index = (num - 1) * (pos - roundedpos) // 1
    last = LED_BRIGHTS[int(index)]
    return (
        lambda x: BRIGHTS.LED_BRIGHT_100
        if x < roundedpos
        else last
        if x == roundedpos
        else BRIGHTS.LED_BRIGHT_10
    )


def panPads(value):
    pos = 2 * (COLS - 1) * value
    roundedpos = pos // 1
    extrapad = roundedpos % 2
    firstpad = (roundedpos / 2) // 1
    # Step 3: Remove duplicates based on the second element
    if firstpad == extrapad + firstpad:
        return [firstpad]
    return [firstpad, firstpad + extrapad]
    # unique = {tuple(item): item for item in [firstpad, firstpad + extrapad]}.values()
    # return unique


def get_cell_led_mode_fn(state: Dict[str, Any]) -> Callable:
    submode = getDeviceSetting("submode", state)

    def cond_fn(track, y):
        # Check for device pan
        if submode == looper_handler.MODE_PAN:
            channels = track.get("channel_count")
            if channels is None:
                return lambda x: BRIGHTS.LED_OFF
            if channels == 2:
                pads_left = panPads(track.get("pan_1", 0))
                pads_right = panPads(track.get("pan_2", 1))
                both = set(pads_left) & set(pads_right)
                any_pads = set(pads_left) | set(pads_right)

                return lambda x: (
                    BRIGHTS.LED_BRIGHT_100
                    if x in both
                    else BRIGHTS.LED_BRIGHT_75
                    if x in any_pads
                    else BRIGHTS.LED_BRIGHT_25
                )
            pads = panPads(track.get("pan_1", 0.5))
            return (
                lambda x: BRIGHTS.LED_BRIGHT_100 if x in pads else BRIGHTS.LED_BRIGHT_25
            )

        # Check for device levels
        if submode == looper_handler.MODE_LEVEL1:
            if y == 0:
                return lambda x: padBrightnessForLevel(
                    COLS, state.get("glob", {}).get("wet", 0),"wet"

                )(x)
            return lambda x: padBrightnessForLevel(COLS, track.get("wet", 0), "wet")(x)

        # Check for track levels
        if submode == looper_handler.MODE_LEVEL2:
            tracknum = getGlob("selected_loop_num", state)
            theTrack = (
                state.get("glob")
                if tracknum == -1
                else path(["tracks", tracknum], state) or {}
            )
            # level = theTrack[key]

            def track_level_fn(track, i):
                return lambda xpad: (
                    padBrightnessForLevel(ROWS, theTrack.get(TRACK_LEVELS[xpad], 0), TRACK_LEVELS[xpad])(
                        ROWS - 1 - i
                    )
                )

            return track_level_fn(None, y)  # NO Example index

        # Default case
        state_value = track.get("state", SL_STATE_UNKNOWN)
        if state_value == SL_STATE_UNKNOWN:
            return lambda x: 0x80
        pos = (
            0
            if track.get("loop_len", 0) == 0
            else 8 * (track.get("loop_pos", 0) / track.get("loop_len", 1))
        )

        rounded_pos = int(pos)
        # last = LED_BRIGHTS[
        #     min(3, int(7 * (pos - rounded_pos)))
        # ]  # Ensure index is within bounds
        led_mode = SL_STATES[state_value]["ledmode"]

        return lambda x: (
            BRIGHTS.LED_BRIGHT_100
            if led_mode == BRIGHTS.LED_BRIGHT_100 and x <= rounded_pos
            else BRIGHTS.LED_BRIGHT_25
            if led_mode == BRIGHTS.LED_BRIGHT_100
            else led_mode
        )

    return cond_fn


def get_cell_color_fn(state: Dict[str, Any]) -> Callable:
    submode = getDeviceSetting("submode", state)

    def cond_fn(track, y):
        # Check for device pan
        if submode == looper_handler.MODE_PAN:
            channels = track.get("channel_count")
            track_state = track.get("state", SL_STATE_UNKNOWN)
            if channels is None:
                return lambda x: SL_STATES[track_state]["color"]
            if channels == 2:
                pads_left = panPads(track.get("pan_1", 0))
                pads_right = panPads(track.get("pan_2", 1))
                both = set(pads_left) & set(pads_right)
                # any_pads = set(pads_left) | set(pads_right)

                return lambda x: (
                    COLORS.COLOR_PURPLE
                    if x in both
                    else COLORS.COLOR_RED
                    if x in pads_left
                    else COLORS.COLOR_BLUE
                    if x in pads_right
                    else SL_STATES[track_state]["color"]
                )
            return lambda x: SL_STATES[track_state]["color"]

        # Check for wet for loops in view
        if submode == looper_handler.MODE_LEVEL1:
            state_value = track.get("state", SL_STATE_UNKNOWN)
            if y == 0:
                return lambda x: COLORS.COLOR_BLUE_DARK
            if state_value == SL_STATE_UNKNOWN:
                return lambda x: SL_STATES[state_value]["color"]
            if state_value == SL_STATE_OFF:
                return lambda x: COLORS.COLOR_BLUE_LIGHT
            return lambda x: COLORS.COLOR_BLUE

        # Check for selected loop levels
        if submode == looper_handler.MODE_LEVEL2:

            def track_level_fn(track, i):
                return lambda xpad: LEVEL_COLORS[xpad]  # Example implementation

            return track_level_fn(track, 0)  # Example index

        # Default case
        state_value = track.get("state", SL_STATE_UNKNOWN)
        statespec = SL_STATES[state_value]
        statecolor = statespec["color"]
        return lambda x: statecolor

    return cond_fn


def make_loopnum_overlay(char, col=0):
    spec = CHARS.get(char)
    if not spec:
        return []

    overlay = []
    for rownum, charSpec in enumerate(spec):
        startPad = rowStartPad(rownum) + col
        for i, boolish in enumerate(charSpec):
            pad = startPad + i
            overlay.extend([matrixPadLedmode[boolish], pad, matrixPadColor[boolish]])

    return overlay


def matrix_function(toprow, loopoffset, tracks, storeState, set_syncs):
    matrix = []
    trackLedModeFn = get_cell_led_mode_fn(storeState)
    trackColorFn = get_cell_color_fn(storeState)

    for y in range(ROWS):  # Equivalent to [0, 1, 2, 3, 4]
        tracknum = y - loopoffset
        track = list_get(tracks, tracknum, {}) if tracknum < getGlob('loopcount', storeState) else {}
        cellLedModeFn = trackLedModeFn(track, y)
        cellColorFn = trackColorFn(track, y)

        # state = track.get("state", SL_STATE_UNKNOWN)
        # next_state = track.get("next_state")
        # loop_len = track.get("loop_len")
        # loop_pos = track.get("loop_pos")
        # wet = track.get("wet")
        # sync = track.get("sync")
        # relative_sync = track.get("relative_sync")

        if len(toprow) > 0 and y == 0:
            matrix.extend(toprow)
            # logging.debug(f"matrci with top row {matrix}")
            continue
        if set_syncs and y == 0:
            padnums = range(32, 38)  # rowPads(y)
            pads = []
            for x, pad in enumerate(padnums):
                pads.extend([BRIGHTS.LED_BRIGHT_50, pad, SETTINGCOLORS[x]])

            track1 = tracks.get(0, {})
            synccolor = SETTINGCOLORS[6][
                int(min((getGlob("sync_source", storeState) or 0) + 3, 5))
            ]

            matrix.extend(
                [
                    BRIGHTS.LED_BRIGHT_100,
                    38,
                    synccolor,
                    BRIGHTS.LED_BRIGHT_100
                    if track1.get("quantize", 0)
                    else BRIGHTS.LED_BRIGHT_10,
                    39,
                    list_get(
                        SETTINGCOLORS[7],
                        int(track1.get("quantize", 0)),
                        SETTINGCOLORS[7][0],
                    ),
                    *pads,
                ]
            )
            continue

        try:
            if set_syncs:
                pads = [
                    [
                        BRIGHTS.LED_OFF
                        if track == {}
                        else
                        BRIGHTS.LED_BRIGHT_100
                        if track.get(SETTINGS[x])
                        else BRIGHTS.LED_BRIGHT_10,
                        pad,
                        SETTINGCOLORS[x][int(track.get(SETTINGS[x], 0))]
                        if isinstance(SETTINGCOLORS[x], list)
                        else SETTINGCOLORS[x],
                    ]
                    for x, pad in enumerate(rowPads(y))
                ]

                matrix.extend(
                    [
                        BRIGHTS.LED_BRIGHT_75,
                        30,
                        COLORS.COLOR_BROWN_LIGHT,
                        BRIGHTS.LED_BRIGHT_75,
                        22,
                        COLORS.COLOR_BROWN_LIGHT,
                    ]
                )
                for pad in pads:
                    matrix.extend(pad)
                continue

            for x, pad in enumerate(rowPads(y)):
                cell = [cellLedModeFn(x), pad, cellColorFn(x)]
                matrix.extend(cell)

        except Exception as e:
            logging.debug("Caught an exception:", e)
            raise
            return []

    return matrix


def get_soft_keys(loopoffset, storeState):
    soft_keys = []

    for y in range(5):  # Equivalent to [0, 1, 2, 3, 4]
        tracknum = -1 if y == 0 else y - loopoffset
        selected_loop_num = getGlob("selected_loop_num", storeState)

        soft_keys.extend(
            [
                0x90,
                0x52 + y,
                COLORS.SOFT_BLINK
                if tracknum == selected_loop_num and doLevelsOfSelectedMode(storeState)
                else (COLORS.SOFT_ON if tracknum == selected_loop_num else COLORS.SOFT_OFF),
            ]
        )

    return soft_keys


def get_eighths(storeState):
    if getDeviceSetting("show8ths", storeState):
        eighths = [
            item
            for pad in range(getGlob("eighth_per_cycle", storeState))
            for item in [BRIGHTS.LED_BRIGHT_100, pad, COLORS.COLOR_BROWNISH_RED]
        ]
    else:
        eighths = []

    return eighths


# ACTION HELPERS


def globAction(setting, value):
    return {"type": "glob", "setting": setting, "value": value}


def deviceAction(setting, value):
    return {"type": "device", "setting": setting, "value": value}

def assocAction(setting, value):
    return {"type": "assoc", "setting": setting, "value": value}

def batchAction(actions):
    return {"type": "batch", "value": actions}


def trackAction(track, ctrl, value):
    return {
        "type": "track",
        "track": track,
        "ctrl": ctrl,
        "value": value,
    }


# STATE HELPERS
def getDeviceSetting(setting, state):
    return path(["device", setting], state)

def getAny(setting, state):
    return path(setting, state)

def getGlob(setting, state):
    return path(["glob", setting], state)


def getLoopoffset(state):
    offset = path(PATH_LOOP_OFFSET, state)
    return 1 if offset is None else offset


def doLevelsOfSelectedMode(state):
    submode = getDeviceSetting("submode", state)
    return submode == looper_handler.MODE_LEVEL2


def doSyncMode(state):
    submode = getDeviceSetting("submode", state)
    return submode == looper_handler.MODE_SYNC


# Reduce function
def on_update_track(action, state):
    track = action.get("track")
    ctrl = action.get("ctrl")
    value = action.get("value")
    return assoc_path(state, ["tracks", track, ctrl], value)


# Create the FULL MIDI LED LAYOUT
def createAllPads(state):
    loopoffset = getLoopoffset(state)
    submode = getDeviceSetting("submode", state) or looper_handler.MODE_DEFAULT
    set_syncs = submode == looper_handler.MODE_SYNC

    def ctrl_btn(btn):
        if btn == BUTTONS.BTN_KNOB_CTRL_VOLUME:
            return [
                0x90,
                btn,
                1
                if submode == looper_handler.MODE_LEVEL1
                else 2
                if submode == looper_handler.MODE_LEVEL2
                else 0,
            ]
        if btn == BUTTONS.BTN_KNOB_CTRL_PAN:
            return [
                0x90,
                btn,
                1 if submode == looper_handler.MODE_PAN
                else 0,
            ]  # @check Used to have to convert this to num
        if btn == BUTTONS.BTN_KNOB_CTRL_SEND:
            return [0x90, btn, 1 if set_syncs else 0]
        if btn == BUTTONS.BTN_KNOB_CTRL_DEVICE:
            return [
                0x90,
                btn,
                1
                if submode == looper_handler.MODE_SESSION_SAVE
                else 2
                if submode == looper_handler.MODE_SESSION_LOAD
                else 0,
            ]
        return []

    ctrl_keys = functools.reduce(
        lambda acc, btn: acc + ctrl_btn(btn), range(0x40, 0x48), []
    )

    if submode in [looper_handler.MODE_SESSION_LOAD, looper_handler.MODE_SESSION_SAVE]:
        color = (
            COLORS.COLOR_DARK_GREEN
            if submode == looper_handler.MODE_SESSION_LOAD
            else COLORS.COLOR_ORANGE
        )
        sessions = getDeviceSetting("sessions", state) or []
        sessionnums = functools.reduce(
            makeSessionNumberReducer(color, getDeviceSetting("sessions-last", state)),
            sessions,
            [],
        )

        def emptycellreducer(acc, cur):
            return acc + [BRIGHTS.LED_BRIGHT_25, cur, color]

        def emptyrowreducer(acc, cur):
            return acc + functools.reduce(emptycellreducer, rowPads(cur), [])

        emptycells = functools.reduce(emptyrowreducer, range(0, ROWS), [])

        confirmpad = getDeviceSetting("confirm-save", state)

        confirmation_pads = []
        if (confirmpad is not None):
            [no, yes] = confirmers(confirmpad, COLS)
            confirmation_pads = [BRIGHTS.LED_BRIGHT_100, no, COLORS.COLOR_RED, BRIGHTS.LED_BRIGHT_100, yes, COLORS.COLOR_GREEN]

        return overlay(confirmation_pads, sessionnums, emptycells) + ctrl_keys

    tracks = state.get("tracks", {})
    toprow = (
        [
            [BRIGHTS.LED_BRIGHT_90, pad, SL_STATES[TRACK_COMMANDS[i]]["color"]]
            for i, pad in enumerate(rowPads(0))
        ]
        if submode in [looper_handler.MODE_DEFAULT]
        else []
    )
    toprow = list(chain.from_iterable(toprow))
    matrix = matrix_function(toprow, loopoffset, tracks, state, set_syncs)
    # mlen = len(matrix) / 3
    # logging.debug(f"{mlen}")
    # return matrix
    soft_keys = get_soft_keys(loopoffset, state)
    eighths = get_eighths(state)
    # logging.debug(f"softkeys{soft_keys}")
    # logging.debug(f"ctrl_keys{ctrl_keys}")
    # logging.debug(f"matrix{matrix}")
    pads = matrix + overlay(soft_keys, ctrl_keys)
    if len(pads):
        # Don't show it because we wanna track the crazy pan behaviour
        if submode != looper_handler.MODE_PAN and getDeviceSetting("shifted", state):
            firstLoop = 2 - loopoffset
            if firstLoop > 9 and firstLoop < 100:
                return overlay(
                    make_loopnum_overlay((firstLoop / 10) // 1, 2),
                    make_loopnum_overlay(firstLoop % 10, 5),
                    pads,
                )
            else:
                return overlay(make_loopnum_overlay(firstLoop, 5), pads)
        elif getDeviceSetting("showsource", state):
            return overlay(make_loopnum_overlay(syncSourceChar(getGlob('sync_source', state)), 1), pads)
        elif getDeviceSetting("group-selecting", state):
            groupnum = getDeviceSetting("group-selected", state)
            loops = getAny(["device", "groups", groupnum, "loops"], state) or []
            for i in range(len(pads) - 2, 0, -3):
                pad = pads[i]
                if pad == BUTTONS.BTN_SOFT_KEY_SELECT:
                    pads[i-1] = 0x90
                    pads[i+1] = COLORS.SOFT_BLINK
                elif pad < 32:
                    row = padRow(pad)
                    loopoffset = getLoopoffset(state)
                    loopnum = -1 if row == 0 else shiftedTrack(row, loopoffset)
                    pads[i-1] = BRIGHTS.LED_BRIGHT_100 if loopnum in loops else BRIGHTS.LED_BRIGHT_10
                elif pad < (32 + 5):
                    pads[i-1] = BRIGHTS.LED_PULSING_8 if groupnum == (pad % COLS) else BRIGHTS.LED_BRIGHT_50
                    # pads[i+1] = SL_STATES[TRACK_COMMANDS[pad % COLS]]["color"]
            return pads

        elif submode == looper_handler.MODE_DEFAULT:
            for i in range(len(pads) - 2, 0, -3):
                pad = pads[i]
                if (pad > 31) and (pad < 37):
                    pads[i-1] = BRIGHTS.LED_BLINKING_4 if getDeviceSetting('group-solo', state) == pad % COLS else BRIGHTS.LED_BRIGHT_100
            return pads
        else:
            return overlay(eighths, pads)

@dataclass
class EventArgs:
    pad: int = None
    row: int = None
    loopoffset: int = None
    numpad: int = None
    track: int = None
    stateTrack: Dict[str, Any] = field(default_factory=dict)
    tracks: List[Dict[str, Any]] = field(default_factory=list)
    evtype: int = None

class ButtonAutoLatch:
    PT_BOLD_TIME = 0.3 * 1000

    def __init__(self):
        self._hits = {}

    def performance_now(self):
        # Implement a method  to return the current time in milliseconds
        import time

        return time.time() * 1000

    def feed(self, note, evtype):
        last = self._hits.get(note)
        now = (
            self.performance_now()
        )  # Assuming you have a method to get the current time

        # If note_on, return true
        if evtype == EV_NOTE_ON:
            if last:
                del self._hits[note]
                return False
            # Turn on
            self._hits[note] = now
            return True

        if evtype == EV_NOTE_OFF:
            if note not in self._hits:
                return False
            else:
                if now - last < self.PT_BOLD_TIME:
                    return True
                    # leave on
                else:
                    del self._hits[note]
                    return False
                    # turn off

        raise ValueError("ButtonAutoLatch only meant for NOTE_ON and NOTE_OFF events")


# zynthian_ctrldev_akai_apc_key25_mk2_sl
class looper_handler(
    ModeHandlerBase  # zynthian_ctrldev_zynmixer, zynthian_ctrldev_zynpad
):
    """Looper Handler for Zynthian Controller Device: Akai APC Key 25"""

    ctrls = [
        "channel_count",  # undocumented
        "wet",
        "dry",
        "pan_1",
        "pan_2",
        "pan_3",
        "pan_4",
        "feedback",
        "input_gain",
        "rec_thresh",
        "sync",
        "relative_sync",
        "quantize",
        "playback_sync",
        "mute_quantized",
        "overdub_quantized",
        "replace_quantized",
        "reverse",
        "pitch_shift",
    ]
    auto_ctrls = [
        "state",
        "next_state",
        "loop_pos",
        "loop_len",
    ]
    globs = [
        "sync_source",
        "selected_loop_num",
        "eighth_per_cycle",
        "wet",
        "dry",
        "input_gain",
    ]

    MODE_DEFAULT = 0
    MODE_LEVEL1 = 1
    MODE_LEVEL2 = 2
    MODE_PAN = 4
    MODE_SYNC = 7
    MODE_SESSION_SAVE = 10
    MODE_SESSION_LOAD = 11

    MODE_NUMS = [
        MODE_DEFAULT,
        MODE_LEVEL1,
        MODE_LEVEL2,
        MODE_PAN,
        MODE_SYNC,
        MODE_SESSION_SAVE,
        MODE_SESSION_LOAD,
    ]

    @classmethod
    def get_autoload_flag(cls):
        return True

    SL_PORT = zynthian_engine_sooperlooper.SL_PORT
    # OSC_SL_PORT = ServerPort["sooperlooper_osc"] # 9951
    # OSC_SL_HOST = "127.0.0.1"; # Unnecessary

    SL_SESSION_PATH = "/zynthian/zynthian-my-data/presets/sooperlooper/"

    def __init__(self, state_manager, leds: FeedbackLEDs, idev_in=None, idev_out=None, parent=None):
        """Initialize the controller with required parameters"""
        logging.debug(
            "\n================================================================="
        )
        logging.debug("APC Key 25 mk2 SL __init__ starting...")
        logging.debug(f"state_manager: {state_manager}")
        logging.debug(f"idev_in: {idev_in}, type: {type(idev_in)}")
        logging.debug(f"idev_out: {idev_out}, type: {type(idev_out)}")

        logging.debug("Calling parent class __init__...")
        # Call parent class initializer explicitly
        #        zynthian_ctrldev_base.__init__(self, state_manager, idev_in, idev_out)
        super().__init__(state_manager)

        logging.debug("Parent class __init__ completed")
        # logging.debug(f"self.idev_out after parent init: {self.idev_out}")
        logging.debug("APC Key 25 mk2 SL __init__ completed")
        logging.debug(
            "=================================================================\n"
        )
        self.parent = parent
        self.state = {}
        self.loopcount = 0
        self._knobs_ease = KnobSpeedControl()
        self._auto_latch = ButtonAutoLatch()
        self._state_manager = state_manager
        self._default_handler = SubModeDefaultWithGroups(
            self, state_manager, leds, idev_in, idev_out
        )
        self._levels1_handler = SubModeLevels1(
            self, state_manager, leds, idev_in, idev_out
        )
        self._levels2_handler = SubModeLevels2(
            self, state_manager, leds, idev_in, idev_out
        )
        self._pan_handler = SubModePan(self, state_manager, leds, idev_in, idev_out)
        self._sync_handler = SubModeSync(self, state_manager, leds, idev_in, idev_out)
        self._save_handler = SubModeSessionsSave(
            self, state_manager, leds, idev_in, idev_out
        )
        self._load_handler = SubModeSessionsLoad(
            self, state_manager, leds, idev_in, idev_out
        )
        self._handlers = {
            self.MODE_DEFAULT: self._default_handler,
            self.MODE_LEVEL1: self._levels1_handler,
            self.MODE_LEVEL2: self._levels2_handler,
            self.MODE_PAN: self._pan_handler,
            self.MODE_SYNC: self._sync_handler,
            self.MODE_SESSION_SAVE: self._save_handler,
            self.MODE_SESSION_LOAD: self._load_handler,
        }
        self._current_handler = None
        self.activateSubmode(self.MODE_DEFAULT)
        self._init_complete = False
        self._shutting_down = False
        self.osc_server = None
        self.osc_target = None
        self._loop_states = {}
        self._init_time = 0
        self.last_notes = []
        self.idev_in = idev_in
        self.idev_out = idev_out

        self._leds = leds
        self._leds.all_off()
        self.init()
        # Light up first button in each row
        # self._leds.led_state(82, LED_ON)  # First snapshot
        # self._leds.led_state(64, LED_ON)  # First zs3

        # if self._leds is None:
        #     logging.debug("Initializing LED controller...")
        #     self._leds = FeedbackLEDs(idev_out)
        #     logging.debug("LED controller initialized")

    @property
    def loopcount(self):
        return getGlob('loopcount', self.state) or 0

    @loopcount.setter
    def loopcount(self, value):
        return self.dispatch(globAction('loopcount', value))

    @loopcount.deleter
    def loopcount(self):
        return self.dispatch(globAction('loopcount', 0))

    def set_active(self, active):
        super().set_active(active)
        self._leds.all_off()
        self.last_notes = [];
        if active:
            self.render()
            self.reconnect()

    # def sub_mode(self):
    #     if getDeviceSetting("levels", self.state) == 1:
    #         return self.MODE_LEVEL1
    #     if showTrackLevels(self.state):
    #         return self.MODE_LEVEL2
    #     if getDeviceSetting("pan", self.state):
    #         return self.MODE_PAN
    #     if getDeviceSetting("sync", self.state):
    #         return self.MODE_SYNC
    #     if self._current_handler == self._save_handler:
    #         return self.MODE_SESSION_SAVE
    #     if self._current_handler == self._load_handler:
    #         return self.MODE_SESSION_LOAD
    #     return self.MODE_DEFAULT

    def refresh(self):
        """Refresh device state"""
        pass
        # self.update_loop_states()

    def init(self):
        logging.debug("Starting APC Key 25 mk2 sl init sequence")
        """Initialize the device"""
        if self._shutting_down:
            logging.debug("Skipping initialization - device is shutting down")
            return

        self._init_complete = False
        # super().init()

        if not self._shutting_down:
            logging.debug("Initializing zynthian_ctrldev_akai_apc_key25...")

            # Initialize LED controller
            if self._leds is None:
                logging.debug("Initializing LED controller...")
                self._leds = FeedbackLEDs(self.idev_out)
                logging.debug("LED controller initialized")

            # Initialize OSC server
            try:
                logging.debug("Creating OSC server...")
                self.osc_server = liblo.ServerThread()
                self.osc_server_port = self.osc_server.get_port()
                self.osc_server_url = f"osc.udp://localhost:{self.osc_server_port}"
                logging.debug(f"OSC server initialized on port {self.osc_server_port}")

                # Register OSC methods
                logging.debug("Registering OSC methods...")
                self.osc_server.add_method("/error", "s", self._cb_osc_error)
                self.osc_server.add_method("/pong", "ssi", self._cb_osc_pong)
                self.osc_server.add_method("/info", "ssi", self._cb_osc_info)
                self.osc_server.add_method("/update", "isf", self._cb_osc_update)
                self.osc_server.add_method("/glob", "isf", self._cb_osc_glob)
                # self.osc_server.add_method("/sessions", "sf", self._cb_osc_sessions)
                self.osc_server.add_method(None, None, self._cb_osc_fallback)

                # Start the OSC server
                logging.debug("Starting OSC server...")
                self.osc_server.start()
                logging.debug("OSC server started successfully")

                logging.debug("Attempting to connect to SooperLooper...")
                # Start connection attempt timer
                self._init_time = time.time()
                self._try_connect_to_sooperlooper()

            except liblo.ServerError as err:
                logging.debug(f"Error initializing OSC: {err}")
                self.osc_server = None

    def end(self):
        super().end()

    def increase(self, delta, ctrl, track, loopnum):
        curval = track.get(ctrl)
        if curval is None:
            return
        # Calculate the new value, ensuring it stays within the range [0, 1]
        if ctrl == "pitch_shift":
            new_value = max(-12, min(12, curval + delta))
        else:
            new_value = max(0, min(1, curval + delta * 0.1))
        self.just_send(f"/sl/{loopnum}/set", ("s", ctrl), ("f", new_value))

    def note_on(self, note, velocity, shifted_override=None):
        self._on_shifted_override(shifted_override)
        if (shifted_override and note == 7):
            return
        return self.note_event(EV_NOTE_ON, note)

    def note_off(self, note, shifted_override=None):
        if (shifted_override and note == 7):
            return
        return self.note_event(EV_NOTE_OFF, note)

    def on_shift_changed(self, val):
        self.dispatch(deviceAction("shifted", val))

    def note_event(self, evtype, button):
        if BUTTONS.BTN_PAD_START <= button <= BUTTONS.BTN_PAD_END:
            return self.pad_event(evtype, button)
        if BUTTONS.BTN_KNOB_CTRL_VOLUME <= button <= BUTTONS.BTN_KNOB_CTRL_DEVICE:
            return self.handle_mode_buttons(button, evtype)
        if (
            getDeviceSetting("shifted", self.state)
            and BUTTONS.BTN_SOFT_KEY_CLIP_STOP <= button <= BUTTONS.BTN_SOFT_KEY_SELECT
        ):
            return self.select_loop_for_button(button)
        self.handle_rest_of_buttons(button, evtype)

    def cc_change(self, ccnum, ccval):
        delta = self._knobs_ease.feed(
            ccnum, ccval, getDeviceSetting("shifted", self.state)
        )  # @todo: use self._is_shifted (or not at all?)
        if delta is None:
            return
        knobnum = ccnum - 48
        if doLevelsOfSelectedMode(self.state):
            if knobnum == 0:
                return
            level = TRACK_LEVELS[knobnum]
            if not level:
                return
            loopnum = getGlob("selected_loop_num", self.state)
            if loopnum == -1:
                return
            self.increase(delta, level, self.state["tracks"][loopnum], loopnum)
            return
        loopoffset = getLoopoffset(self.state)
        loopnum = (knobnum % KNOBS_PER_ROW) - (loopoffset - 1)
        tracks = self.state["tracks"]
        track = tracks.get(loopnum)
        if track is None:  # Check if track is None
            return None  # Or handle as needed
        funnum = knobnum // KNOBS_PER_ROW
        # todo: this could be larger than 1?
        funs = ["wet", "pan"]
        fun = funs[funnum]
        if fun == "pan":
            channel_count = int(track.get("channel_count", 0))
            for c in range(
                1, channel_count + 1
            ):  # Loop from 1 to channel_count inclusive
                ctrl = f"pan_{c}"
                if getDeviceSetting("shifted", self.state):
                    if c == 2 and channel_count == 2:
                        self.increase(-delta, ctrl, track, loopnum)
                    else:
                        self.increase(delta, ctrl, track, loopnum)
                else:
                    if channel_count == 2:
                        if c == 1:
                            if delta < 0 or track.get("pan_2", 0) == 1:
                                self.increase(delta, ctrl, track, loopnum)
                        if c == 2:
                            if delta > 0 or track.get("pan_1", 0) == 0:
                                self.increase(delta, ctrl, track, loopnum)
                    else:
                        self.increase(delta, ctrl, track, loopnum)
        else:
            self.increase(delta, fun, track, loopnum)
        pass

    def pad_event(self, evtype, pad):
        submode = getDeviceSetting("submode", self.state)
        # if submode == self.MODE_PAN:
        #     return
        row = padRow(pad)
        numpad = pad % COLS
        loopoffset = getLoopoffset(self.state)
        track = -1 if row == 0 else shiftedTrack(row, loopoffset)
        tracks = self.state.get("tracks", {})
        # Let loop 0 be the source of truth for all (sync/quant; rec_or_overdub is special-cased on loop -1 anyway)
        stateTrack = (
            path(["tracks", 0], self.state)
            if track == -1
            else {}
            if track >= self.loopcount
            else path(["tracks", track], self.state)
        )
        common_args = EventArgs(numpad=numpad,
                                pad=pad,
                                row=row,
                                loopoffset=loopoffset,
                                track=track,
                                stateTrack=stateTrack,
                                tracks=tracks,
                                evtype=evtype)
        if (hasattr(self._current_handler, 'on_pad') and callable(getattr(self._current_handler, 'on_pad'))):
            return self._current_handler.on_pad(common_args);
        pass

    def activateSubmode(self, modenum):
        handler = self._handlers[modenum]
        current_handler = self._current_handler
        self._current_handler = handler
        handler.set_active(True)
        if current_handler:
            current_handler.set_active(False)
        self.dispatch(deviceAction("submode", modenum))

    def nextModeNum(self, button):
        submode = getDeviceSetting("submode", self.state)
        index = 3 * (button - BUTTONS.BTN_KNOB_CTRL_VOLUME)
        if submode == self.MODE_DEFAULT:
            # 0, 3, 6, 9 => 1 , 4, 7, 10
            return index + 1
        if submode == index + 1:
            # Is 1st submode of this button
            index = submode + 1
            if index not in self.MODE_NUMS:
                return self.MODE_DEFAULT
            return index
        if submode == index + 2:
            # Is 2nd submode of this button
            return self.MODE_DEFAULT
        # Special case for default state
        if (index == (self.MODE_SESSION_SAVE - 1)):
            return self.MODE_DEFAULT
        return index + 1

    def handle_mode_buttons(self, button, evtype):
        if evtype == EV_NOTE_ON:
            next = self.nextModeNum(button)
            self.activateSubmode(next)
        return

    # @todo: only on note on
    def select_loop_for_button(self, button):
        row = button - 0x52
        track = (
            -1 if row == 0 else shiftedTrack(row, getLoopoffset(self.state))
        )  # Assuming shifted_track is a method of self

        if track < self.loopcount:
            self.dispatch(globAction("selected_loop_num", track))
            self.just_send("/set", ("s", "selected_loop_num"), ("f", track))
        return

    def handle_rest_of_buttons(self, button, evtype):
        shifted = getDeviceSetting("shifted", self.state)
        if hasattr(self._current_handler, 'on_button') and callable(getattr(self._current_handler, 'on_button')) and self._current_handler.on_button(button, evtype, shifted):
            return

        if button == BUTTONS.BTN_STOP_ALL_CLIPS:
            if evtype == EV_NOTE_ON:
                if getDeviceSetting("shifted", self.state):
                    self.just_send("/sl/-1/hit", ("s", "mute_off"))
                else:
                    self.just_send("/sl/-1/hit", ("s", "mute_on"))
            else:
                # self.render_all_pads(state)  # Assuming render_all_pads is a method of self
                # @todo: simply turn all leds off
                self.request_feedback(
                    "/ping", "/pong"
                )  # Assuming request_feedback is a method of self
            return

        if button == BUTTONS.BTN_SHIFT:
            self.dispatch(deviceAction("shifted", evtype == EV_NOTE_ON))
            return

        if button == BUTTONS.BTN_TRACK_1:
            if evtype == EV_NOTE_ON and (getDeviceSetting("shifted", self.state)):
                self.shift_up()  # Assuming shift_up is a method of self
            return

        if button == BUTTONS.BTN_TRACK_2:
            if evtype == EV_NOTE_ON and (getDeviceSetting("shifted", self.state)):
                self.shift_down()
            return

        return

    def get_sessions(self):
        mypath = self.SL_SESSION_PATH
        if (not isdir(mypath)):
            mkdir(mypath)
        onlyfiles = [
            f
            for f in listdir(mypath)
            if isfile(join(mypath, f)) and f.endswith(".slsess")
        ]
        self.dispatch(deviceAction("sessions", onlyfiles))

    def request_feedback(self, address, path, *args):
        try:
            self.osc_server.send(self.osc_target, address, *args, self.osc_server_url, path)
        except:
            pass

    def just_send(self, address, *args):
        self.osc_server.send(self.osc_target, address, *args)

    def range(self, start=0):
        return f"[{start}-{self.loopcount - 1}]"

    def _cb_osc_fallback(self, path, args, types, src):
        """Fallback callback for unhandled OSC messages"""
        logging.debug(f"Received unhandled OSC message: {path} {args}")

    def _cb_osc_error(self, path, args):
        """Error callback for errors on loading or saving sessions"""
        logging.debug(f"Error: {path} {args}")

    def _cb_osc_pong(self, path, args):
        """Callback for info messages from SooperLooper"""
        self._init_complete = True
        self.request_feedback("/register", "/info")
        self.handleInfo(args)
        self.register_update(self.range(0))
        self.just_send("/set", "smart_eighths", 0)

    def shift_down(self):
        self.dispatch({"type": "offsetDown"})

    def shift_up(self):
        self.dispatch({"type": "offsetUp"})

    def _cb_osc_info(self, path, args):
        """Callback for info messages from SooperLooper"""
        old_count = int(self.loopcount)
        self.handleInfo(args)

        logging.debug(f"{old_count} => {self.loopcount}")
        if self.loopcount > old_count:
            for loop in range(old_count, self.loopcount):
                self.register_update(loop)
                self.just_send(f"/sl/{loop}/set", "sync", 1)
        if self.loopcount < old_count:
            for loop in range(self.loopcount, old_count):
                self.dispatch({"type": "empty-track", "value": loop})

    def _cb_osc_update(self, path, args, types, src):
        [track, ctrl, val] = args[:3]
        if ctrl == "in_peak_meter":
            self.dispatch(
                {
                    "type": "track",
                    "track": getGlob("selected_loop_num", self.state),
                    "ctrl": ctrl,
                    "value": val * 2,
                },
            )
        else:
            self.dispatch({"type": "track", "track": track, "ctrl": ctrl, "value": val})

    def _cb_osc_glob(self, path, args):
        [_, ctrl, value] = args[:3]
        if ctrl == "selected_loop_num":
            self.dispatch(globAction(ctrl, int(value)))
        elif ctrl == "sync_source":
            self.dispatch(globAction(ctrl, int(value)))
        elif ctrl == "eighth_per_cycle":
            self.dispatch(globAction(ctrl, int(value)))
        else:
            self.dispatch(globAction(ctrl, value))

    def _cb_osc_sessions(self, path, args):
        self.dispatch(deviceAction("sessions", args))

    def reducer(self, state=None, action=None):
        if state is None:
            state = {"tracks": {}}

        if action is None:
            return state

        if action["type"] == "track":
            # logging.debug(f"action {action}")
            return on_update_track(action, state)
        elif action["type"] == "empty-track":
            return assoc_path(state, ["tracks", action["value"]], {})
        elif action["type"] == "device":
            return assoc_path(state, ["device", action["setting"]], action["value"])
        elif action["type"] == "assoc":
            return assoc_path(state, action["setting"], action["value"])
        elif action["type"] == "offsetUp":
            max_offset = 1  # ==> -1, which is all!
            cur_offset = getLoopoffset(state)
            return assoc_path(state, PATH_LOOP_OFFSET, min(cur_offset + 1, max_offset))
        elif action["type"] == "offsetDown":
            min_offset = min(
                0, (ROWS - 1) - self.loopcount
            )  # Leave last (fifth) row for new loops
            cur_offset = getLoopoffset(state)
            return assoc_path(state, PATH_LOOP_OFFSET, max(cur_offset - 1, min_offset))
        elif action["type"] == "glob":
            return assoc_path(state, ["glob", action["setting"]], action["value"])
        elif action["type"] == "batch":
            for batch_action in action["value"]:
                state = self.reducer(state, batch_action)
            return state
        else:
            return state

    def render(self):
        pads = createAllPads(self.state)
        notes = split_every(3, pads)
        these = generator_difference(notes, self.last_notes)
        self.last_notes = these;
        sendable = []
        for pad in these:
            if pad[0] == 0x80:
                # For some reason simply sending a note off does not work.
                # lib_zyncore.dev_send_midi_event(self.idev_out, bytes(pad), 3)
                # The following does work, but something tells me to stay with they ctrldev_base way
                # lib_zyncore.dev_send_note_on(self.idev, 0, pad[1], 0)
                self._leds.led_off(pad[1], False)
            else:
                sendable.extend(pad)

        # logging.debug(pads, len(pads))
        if (len(sendable) > 0):
            msg = bytes(sendable)
            lib_zyncore.dev_send_midi_event(self.idev_out, msg, len(msg))
        # NOW RENDER

    def dispatch(self, action):
        # logging.debug(f"type {type}; action {action}")
        self.state = self.reducer(self.state, action)
        if not (self._is_active):
            return
        self.render()

    def register_update(self, range):
        for ctrl in self.ctrls:
            self.request_feedback(f"/sl/{range}/register_update", "/update", ctrl)

        for ctrl in self.auto_ctrls:
            self.request_feedback(
                f"/sl/{range}/register_auto_update", "/update", ctrl, 100
            )

        for ctrl in self.globs:
            self.request_feedback("/register_update", "/glob", ctrl)

        # Ensure to get initial state after a delay
        Timer(2.0, self.get_initial_state, args=(range,)).start()

    def register_selected(self, ctrls):
        for ctrl in ctrls:
            self.request_feedback(
                "/sl/-3/register_auto_update", "/update", ("s", ctrl), ("i", 100)
            )

    def unregister_selected(self, ctrls):
        for ctrl in ctrls:
            self.request_feedback(
                "/sl/-3/unregister_auto_update", "/update", ("s", ctrl)
            )

    def get_initial_state(self, range):
        for ctrl in self.ctrls + self.auto_ctrls:
            self.request_feedback(f"/sl/{range}/get", "/update", ctrl)

        for ctrl in self.globs:
            self.request_feedback("/get", "/glob", ctrl)

    def handleInfo(self, args):
        try:
            if len(args) >= 3:
                hosturl, version, loopcount = args[:3]
                self.loopcount = int(loopcount)
        except Exception as e:
            logging.error(f"Error in info callback: {e}")

        # @todo: from zynthian_ctrldev_akai_apc_key25.py: factor out, use in zynthian_engine_sooperlooper too?

    def reconnect(self):
        # self._init_complete = False
        self.request_feedback("/ping", "/pong")
        # self._try_connect_to_sooperlooper()

    def _try_connect_to_sooperlooper(self):
        """Attempt to connect to SooperLooper via OSC after initial delay"""
        if self._init_complete:
            return True

        # Check if enough time has passed since initialization
        elapsed = time.time() - self._init_time
        if elapsed < 10:
            logging.debug(f"Waiting for sooperlooper to start... ({elapsed:.1f}s)")
            # Schedule next attempt
            Timer(1.0, self._try_connect_to_sooperlooper).start()
            return False

        if self.osc_server is None:
            logging.debug("OSC server not initialized")
            return False

        try:
            logging.debug(
                f"Attempting to connect to SooperLooper on port {self.SL_PORT}..."
            )
            self.osc_target = liblo.Address(self.SL_PORT)
            # logging.debug("Successfully connected to SooperLooper via OSC")
            logging.debug(
                "Pinging SL.                                                                                                                                                                                                                                    ..."
            )
            self.request_feedback("/ping", "/pong")
            # self._init_complete = True
            Timer(2.0, self._try_connect_to_sooperlooper).start()
            return True

        except Exception as e:
            logging.debug(f"Failed to connect to SooperLooper: {e}")
            # Retry after delay if still within reasonable time
            # if elapsed < 300:  # Try for up to 300 seconds
            #     logging.debug("Scheduling retry...")
            # Just keep on trying
            Timer(2.0, self._try_connect_to_sooperlooper).start()
            return False


class SubModeDefault(ModeHandlerBase):
    """Submode for controlling loops in view"""

    MODENAME = "default"

    def __init__(
        self, parent: looper_handler, state_manager, leds: FeedbackLEDs, idev_in=None, idev_out=None
    ):
        super().__init__(state_manager)
        self.parent = parent
        # NOTE: we're still using parent's toggles for this
        self.dosolo = False
        self.domute = False
        self.undoing = False
        self.redoing = False
        self.alt = False

    def set_active(self, active):
        super().set_active(active)

    def handle_loop_operations(self, numpad):
        if numpad <= 3:
            self.parent.just_send(
                "/loop_add",
                ("i", (numpad + 1) % 4),  # mono - 4 channels, repeating
                ("f", 40),
            )
            return True

        elif numpad >= 4:
            self.parent.just_send(
                "/loop_del",
                ("i", -1),  # Last loop -- the only supported one
            )
            return True

    def on_button(self, button, evtype, shifted):
        if button == BUTTONS.BTN_UNDO:
            self.undoing = evtype == EV_NOTE_ON
            return True

        if button == BUTTONS.BTN_REDO:
            self.redoing = evtype == EV_NOTE_ON
            return True

        if button == BUTTONS.BTN_TRACK_1:
            if shifted:
                return False
            self.alt = evtype == EV_NOTE_ON
            return True

        if button == BUTTONS.BTN_SOFT_KEY_SOLO:
            self.dosolo = evtype == EV_NOTE_ON
            return True

        if button == BUTTONS.BTN_SOFT_KEY_MUTE:
            self.domute = evtype == EV_NOTE_ON
            return True


        if button == BUTTONS.BTN_UNDO:
            self.undoing = evtype == EV_NOTE_ON
            return True

        if button == BUTTONS.BTN_REDO:
            self.redoing = evtype == EV_NOTE_ON
            return True

        pass


    def on_pad(self, args: EventArgs):
        track = args.track
        evtype = args.evtype
        numpad = args.numpad
        stateTrack = args.stateTrack
        if evtype == EV_NOTE_ON:
            if track >= self.parent.loopcount:
                return self.handle_loop_operations(numpad)
            if self.dosolo:
                return self.parent.just_send(f"/sl/{track}/hit", ("s", "solo"))
            if self.domute:
                return self.parent.just_send(f"/sl/{track}/hit", ("s", "mute"))
            if self.undoing and numpad <= 1:
                return self.parent.just_send(f"/sl/{track}/hit", ("s", "undo_all"))
            if self.redoing and numpad >= 4:
                return self.parent.just_send(f"/sl/{track}/hit", ("s", "redo_all"))
        if not self.undoing or self.redoing:
            if numpad == 0:
                return self.handle_rec_or_overdub(track, stateTrack, evtype)
        if numpad < 8:
            return self.handle_loop_actions(numpad, track, evtype)
        pass

    def handle_rec_or_overdub(self, track, stateTrack, evtype):
        sus = "down" if evtype == EV_NOTE_ON else "up"
        if track == -1:
            self.parent.just_send(f"/sl/{track}/{sus}", ("s", "record_or_overdub"))
            return
        if stateTrack is None:
            return
        state = stateTrack.get("state", SL_STATE_UNKNOWN)
        if (
            state < SL_STATE_RECORDING
            or (not self.alt and state == SL_STATE_RECORDING)
            or (self.alt and state != SL_STATE_RECORDING)
        ):
            self.parent.just_send(f"/sl/{track}/{sus}", ("s", "record"))
        else:
            self.parent.just_send(f"/sl/{track}/{sus}", ("s", "overdub"))

    def handle_loop_actions(self, numpad, track, evtype):
        sus = "down" if evtype == EV_NOTE_ON else "up"
        if numpad == 1:
            self.parent.just_send(f"/sl/{track}/{sus}", ("s", "multiply"))
            return

        if numpad == 2:
            if self.undoing:
                self.parent.just_send(f"/sl/{track}/{sus}", ("s", "undo"))
            elif self.alt:
                self.parent.just_send(f"/sl/{track}/{sus}", ("s", "reverse"))
            else:
                self.parent.just_send(f"/sl/{track}/{sus}", ("s", "insert"))
            return

        if numpad == 3:
            if self.redoing:
                self.parent.just_send(f"/sl/{track}/{sus}", ("s", "redo"))
            elif self.alt:
                if evtype == EV_NOTE_ON:
                    self.parent.just_send(
                        f"/sl/{track}/set",
                        ("s", "delay_trigger"),
                        ("f", random.random()),
                    )
                else:
                    pass
            else:
                self.parent.just_send(f"/sl/{track}/{sus}", ("s", "replace"))
            return

        if numpad == 4:
            self.parent.just_send(f"/sl/{track}/{sus}", ("s", "substitute"))
            return

        if numpad == 5:
            self.parent.just_send(f"/sl/{track}/{sus}", ("s", "oneshot"))

        if numpad == 6:
            self.parent.just_send(f"/sl/{track}/{sus}", ("s", "trigger"))

        if numpad == 7:
            self.parent.just_send(f"/sl/{track}/{sus}", ("s", "pause"))

class SubModeLevels1(ModeHandlerBase):
    """Submode for handling levels for loops in view"""

    MODENAME = "levels1"

    def __init__(
        self, parent: looper_handler, state_manager, leds: FeedbackLEDs, idev_in=None, idev_out=None
    ):
        super().__init__(state_manager)
        self.parent = parent

    def set_active(self, active):
        super().set_active(active)

    def on_pad(self, args: EventArgs):
        if args.evtype == EV_NOTE_OFF:
            return
        if args.track >= self.parent.loopcount:
            return SubModeDefault.handle_loop_operations(self, args.numpad)
        if args.pad < ((ROWS - 1) * COLS):
            return self.handle_all_wet(args)
        else:
            return self.handle_glob_wet(args.numpad)

    def compute_value_within_axis(self, numpad, storedValue):
        value = (numpad + 1) / COLS
        if storedValue == value:
            value -= 1 / (COLS * 2)

        if storedValue == 1 / (COLS * 2) and numpad == 0:
            value = 0

        return value

    def handle_all_wet(self, args: EventArgs):
        stateTrack = args.stateTrack
        if not stateTrack:
            return

        storedValue = stateTrack.get("wet")

        if storedValue is None:
            return

        value = self.compute_value_within_axis(args.numpad, storedValue)
        tracl = args.track
        self.parent.dispatch(trackAction(args.track, "wet", value))
        self.parent.just_send(f"/sl/{args.track}/set", ("s", "wet"), ("f", value))

    def handle_glob_wet(self, numpad):
        setting = "wet"
        storedValue = getGlob(setting, self.parent.state)

        value = self.compute_value_within_axis(numpad, storedValue)

        self.parent.dispatch(globAction(setting, value))
        self.parent.just_send("/set", ("s", "wet"), ("f", value))

class SubModeLevels2(ModeHandlerBase):
    """Submode for handling levels for selected loop"""

    MODENAME = "levels2"

    def __init__(
        self, parent: looper_handler, state_manager, leds: FeedbackLEDs, idev_in=None, idev_out=None
    ):
        super().__init__(state_manager)
        self.parent = parent

    def set_active(self, active):
        super().set_active(active)
        if active:
            self.parent.register_selected(["in_peak_meter"])
        else:
            self.parent.unregister_selected(["in_peak_meter"])

    def on_pad(self, args: EventArgs):
        if (args.evtype == EV_NOTE_OFF):
            return
        return self.handle_selected_loop_levels(args.numpad, args.row, args.tracks)

    def handle_selected_loop_levels(self, numpad, row, tracks):
        value = (ROWS - row) / ROWS
        trackno = getGlob("selected_loop_num", self.parent.state)
        isglob = trackno == -1

        if isglob and (numpad < 2 or numpad > 4):
            return

        levelTrack = self.parent.state["glob"] if isglob else tracks.get(trackno)
        if levelTrack is None:
            return

        ctrl = TRACK_LEVELS[numpad]
        storedValue = levelTrack.get(ctrl, 0)

        if ctrl == "pitch_shift":
            value = [12, None, 0, NotImplemented, -12][row]
            if row == 1:
                value = storedValue + 1
            if row == 3:
                value = storedValue - 1
            self.parent.dispatch(trackAction(trackno, ctrl, value))
            self.parent.just_send(f"/sl/{trackno}/set", ("s", ctrl), ("f", value))
            return

        if round(storedValue * ROWS) == round(value * ROWS):
            value -= 1 / 10

        if round(storedValue * 100) == 10 and row == ROWS - 1:
            value = 0

        if isglob:
            self.parent.dispatch(globAction(ctrl, value))
            self.parent.just_send("/set", ("s", ctrl), ("f", value))
        else:
            self.parent.dispatch(trackAction(trackno, ctrl, value))
            self.parent.just_send(f"/sl/{trackno}/set", ("s", ctrl), ("f", value))


class SubModePan(ModeHandlerBase):
    """Submode for handling pan for loops in view"""

    MODENAME = "pan"

    def __init__(
        self, parent: looper_handler, state_manager, leds: FeedbackLEDs, idev_in=None, idev_out=None
    ):
        super().__init__(state_manager)
        self.parent = parent

    def set_active(self, active):
        super().set_active(active)

    def on_pad(self, args: EventArgs):
        if (args.evtype == EV_NOTE_OFF):
            return
        if args.track >= self.parent.loopcount:
            return SubModeDefault.handle_loop_operations(self, args.numpad)
        return

class SubModeGroups(ModeHandlerBase):
    """Submode to handle groups of loops"""

    MODENAME = "groups"

    @property
    def activegroupnum(self):
        return getDeviceSetting("group-selected", self.parent.state)

    @property
    def isselecting(self):
        return getDeviceSetting("group-selecting", self.parent.state)

    @property
    def activegroup(self):
        return self.getgroup(self.activegroupnum)

    @property
    def sologroup(self):
        return getDeviceSetting("group-solo", self.parent.state)

    def getgroup(self, group: int):
        return path([group], getDeviceSetting("groups", self.parent.state)) or {"num": group, "loops": []}

    def setselecting(self, mode):
        self.parent.dispatch(deviceAction("group-selecting", mode))

    def setactivegroup(self, group):
        self.parent.dispatch(deviceAction("group-selected", group))


    def set_active(self, active):
        super().set_active(active)
        if not active:
            self.setselecting(False)
        else:
            self.setactivegroup(0)

    def toggle_into_active_group(self, row):
        group = self.activegroup
        num = group.get('num')
        loops = group.get('loops')
        loopoffset = getLoopoffset(self.parent.state)
        loopnum = row - (loopoffset - 1) - 1
        loops = toggle_value(loopnum, loops)
        self.parent.dispatch( assocAction(["device", "groups", num],  { "num" : num, "loops": loops, "soloed":  group.get('soloed', None)}))

    def toggle_group(self, num):
        group = self.getgroup(num)
        loops = group.get('loops', [])
        if len(loops) == 0:
            return
        soloed = self.sologroup == num
        current_loop_selection = []
        tracks = path(["tracks"], self.parent.state)
        previous_loop_selection = getDeviceSetting('prev-loop-selection', self.parent.state) or range(0, len(tracks))
        for i in range(0, len(tracks)):
            if tracks.get(i) is not None:
                if tracks.get(i).get('state') != SL_STATE_MUTED:
                    current_loop_selection.append(i)
        is_effectively_active = set(current_loop_selection) == set(loops)
        # print(f"active: {is_effectively_active}")
        # print(current_loop_selection, loops)
        if is_effectively_active:
            for i in range(0, len(tracks)):
                if tracks.get(i) is not None:
                    if i in previous_loop_selection:
                        if tracks.get(i).get('state') == SL_STATE_PAUSED:
                           self.parent.just_send(f"/sl/{i}/hit", ("s", "pause"))
                        else:
                            self.parent.just_send(f"/sl/{i}/hit", ("s", "mute_off"))
                    else:
                        self.parent.just_send(f"/sl/{i}/hit", ("s", "mute_on"))
            self.parent.dispatch(deviceAction("group-solo", None))
        else:
            for i in range(0, len(tracks)):
                if tracks.get(i) is not None:
                    if i in loops:
                        if tracks.get(i).get('state') == SL_STATE_PAUSED:
                           self.parent.just_send(f"/sl/{i}/hit", ("s", "pause"))
                        else:
                            self.parent.just_send(f"/sl/{i}/hit", ("s", "mute_off"))
                    else:
                        self.parent.just_send(f"/sl/{i}/hit", ("s", "mute_on"))
            self.parent.dispatch(deviceAction("prev-loop-selection", current_loop_selection))
            self.parent.dispatch(deviceAction("group-solo", num))

    def on_button(self, button, evtype, shifted):
        if shifted:
            pass
        if evtype == EV_NOTE_ON:
            if button == BUTTONS.BTN_SOFT_KEY_SELECT:
                self.setselecting(not self.isselecting)
                return True

    def on_pad(self, common_args: EventArgs):
        if common_args.evtype == EV_NOTE_ON:
            if common_args.row == 0:
                if common_args.numpad < 5:
                    if self.isselecting:
                        self.setactivegroup(common_args.numpad)
                        return True
                    else:
                        if self.undoing or self.redoing:
                            pass
                        else:
                            self.toggle_group(common_args.numpad)
                            return True
            if self.isselecting:
                self.toggle_into_active_group(common_args.row)
                return True
        pass

class SubModeDefaultWithGroups(SubModeDefault, SubModeGroups):
    """Submode for controlling loops in view, with groups"""

    MODENAME = "groups"

    def __init__( self, parent: looper_handler, state_manager, leds: FeedbackLEDs, idev_in=None, idev_out=None):
        SubModeDefault.__init__(self, parent, state_manager, leds, idev_in, idev_out)

    def set_active(self, active):
        SubModeGroups.set_active(self, active)

    def on_button(self, button, evtype, shifted):
        handled = SubModeDefault.on_button(self, button, evtype, shifted)
        if (not handled):
            return SubModeGroups.on_button(self, button, evtype, shifted)
        return handled

    def on_pad(self, common_args: EventArgs):
        if SubModeGroups.on_pad(self, common_args):
            return True
        return SubModeDefault.on_pad(self, common_args)

class SubModeSync(ModeHandlerBase):
    """Submode for setting sync/quantize settings for loops in view"""

    MODENAME = "sync"

    def __init__(
        self, parent, state_manager, leds: FeedbackLEDs, idev_in=None, idev_out=None
    ):
        super().__init__(state_manager)
        self.parent = parent

    def set_active(self, active):
        super().set_active(active)
        self.parent.dispatch(deviceAction("showsource", None))

    def on_pad(self, args: EventArgs):
        # @todo: numpad 6 and row 2 and 3 would be better to get multiples of 8
        row = args.row
        numpad = args.numpad
        pad = args.pad
        evtype = args.evtype
        if (row == 1 or row == 2) and numpad == 6:
            show8ths = evtype == EV_NOTE_ON
            self.parent.dispatch(deviceAction("show8ths", show8ths))
            if show8ths:
                setting = "eighth_per_cycle"
                oldvalue = getGlob(setting, self.parent.state) or 16
                value = max(2, oldvalue - 1) if row == 2 else oldvalue + 1
                self.parent.just_send("/set", ("s", setting), ("f", value))
                self.parent.dispatch(globAction(setting, value))
            return

        # Set 8ths directly
        if getDeviceSetting("show8ths", self.parent.state):
            setting = "eighth_per_cycle"
            value = pad + 1
            self.parent.just_send("/set", ("s", setting), ("f", value))
            self.parent.dispatch(globAction(setting, value))
            return
        track = args.track
        stateTrack = args.stateTrack
        tracks = args.tracks
        if stateTrack == {}:
            if args.evtype == EV_NOTE_ON:
                return SubModeDefault.handle_loop_operations(self, args.numpad)
        else:
            return self.handle_syncs(numpad, track, stateTrack, tracks, evtype)

    def handle_syncs(self, numpad: int, track: int, stateTrack: Dict[str, Any], tracks, evtype):
        if evtype == EV_NOTE_OFF:
            if track == -1 and numpad == 6:
                self.parent.dispatch(deviceAction('showsource', None))
            return
        if numpad < 6:
            if stateTrack is None:
                return
            setting = SETTINGS[numpad]
            self.parent.just_send(
                f"/sl/{track}/set",
                setting,
                int(not stateTrack.get(setting, False)),  # Convert boolean to int
            )

        if track == -1 and numpad == 7:
            # NOTE: it seems just loop 1's setting is used for all
            quant = int(tracks.get(0).get("quantize", -1))  # Default to -1 if not found
            if quant is None:  # Check for NaN equivalent
                quant = -1
            self.parent.just_send(f"/sl/{track}/set", "quantize", (quant + 1) % 4)

        if track == -1 and numpad == 6:
            # -3 = internal, -2 = midi, -1 = jack, 0 = none, # > 0 = loop number (1 indexed)
            setting = "sync_source"
            oldvalue = self.parent.state.get("glob", {}).get(
                setting, -3
            )  # Default to -3 if not found
            if oldvalue is None:  # Check for NaN equivalent
                oldvalue = -4

            value = cycle(
                -3, self.parent.loopcount, oldvalue
            )  # Assuming cycle is defined elsewhere
            self.parent.just_send("/set", setting, value)
            self.parent.dispatch(batchAction([globAction(setting, value), deviceAction('showsource', True)]))
        return

class SubModeSessionsSave(ModeHandlerBase):
    """Submode for saving sessions"""

    MODENAME = "sessionsave"

    def __init__(
        self, parent: looper_handler, state_manager, leds: FeedbackLEDs, idev_in=None, idev_out=None
    ):
        super().__init__(state_manager)
        self.parent = parent

    def set_active(self, active):
        super().set_active(active)
        if active:
            self.parent.get_sessions()
        else:
            self.parent.dispatch(deviceAction("confirm-save", None))

    def on_pad(self, args: EventArgs):
        if args.evtype == EV_NOTE_OFF:
            return
        pad = args.pad;
        # @todo: check whether there is already a session
        confirmpad = getDeviceSetting("confirm-save", self.parent.state)
        if (confirmpad is not None):
            [no, yes] = confirmers(confirmpad, COLS)
            # print(f"Check whether pad is one of no or yes")
            if no == pad:
                # print(f"If no -> unset confirm-save")
                self.parent.dispatch(deviceAction("confirm-save", None))
            if yes == pad:
                # print(f"If yes -> save, and unset confirm-save")
                self.parent.dispatch(deviceAction("confirm-save", None))
                self.save_session(confirmpad)
            return
        sessions = getDeviceSetting("sessions", self.parent.state) or []
        for session in sessions:
            if session[:-7] == "{:02}".format(pad):
                # print(f"Need to confirm {pad}")
                self.parent.dispatch(deviceAction("confirm-save", pad))
                return

        self.save_session(pad)

    def save_session(self, pad):
        # Create the filepath
        file_path = f"{self.parent.SL_SESSION_PATH}{str(pad).zfill(2)}.slsess"

        self.parent.dispatch(deviceAction("sessions-last", pad))
        # Send the session load request
        self.parent.just_send("/save_session", file_path, self.parent.osc_server_url, "/error", 1)

        # Use time.sleep to mimic setTimeout
        time.sleep(1)  # Wait for 1 second
        self.parent.get_sessions()

class SubModeSessionsLoad(ModeHandlerBase):
    """Submode for loading sessions"""

    MODENAME = "sessionload"

    def __init__(
        self, parent: looper_handler, state_manager, leds: FeedbackLEDs, idev_in=None, idev_out=None
    ):
        super().__init__(state_manager)
        self.parent = parent

    def set_active(self, active):
        super().set_active(active)

    def on_pad(self, args: EventArgs):
        if (args.evtype == EV_NOTE_OFF):
            return
        return self.load_session(args.pad)

    def load_session(self, pad):
        # Create the URI
        file_path = f"{self.parent.SL_SESSION_PATH}{str(pad).zfill(2)}.slsess"

        self.parent.dispatch(deviceAction("sessions-last", pad))
        # Send the session load request
        self.parent.just_send("/load_session", file_path, self.parent.osc_server_url, "/error")

        # Use time.sleep to mimic setTimeout
        time.sleep(1)  # Wait for 1 second
        self.parent.request_feedback("/ping", "/pong")
