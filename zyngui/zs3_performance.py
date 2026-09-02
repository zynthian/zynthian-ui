#!/usr/bin/python3
# -*- coding: utf-8 -*-
# ******************************************************************************
# ZYNTHIAN PROJECT: Zynthian GUI
#
# ZS3 performance view => decision functions
#
# Copyright (C) 2026 Charlie Wakely <ccwakely@gmail.com>
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

# This module imports nothing. Everything here answers "given this ZS3 dict and
# this id, what should the screen say"; zynthian_gui_zs3 does the drawing and
# none of the deciding. Keeping it import-free is what makes it testable
# without a Tkinter display or hardware attached.

DEFAULT_ZS3_ID = "zs3-0"
ELLIPSIS = "…"


def parse_zs3_id(zs3_id):
    """Split a ZS3 id into its parts

    Four id forms exist:

      "zs3-N"  saved with no program change  (state_manager.save_zs3)
      "*/P"    any channel, program P        (gui_zs3_options.py:242)
      "C/P"    channel C, program P          (gui_zs3_options.py:244)
      "P"      bare number, left behind when a program change is *removed*
               from a "C/P" or "*/P" id, because gui_zs3_options.py:238
               splits on "/" and keeps only the last part

    C is stored 0-based and returned 1-based, matching what the ZS3 list shows
    (gui_zs3.py:106 renders CH#{int(parts[0]) + 1}).

    Returns : dict of
      kind       "unnumbered" | "any_channel" | "channel" | "orphan" | "default"
      midi_chan  1-based channel, or None for any-channel / unnumbered
      prog       program change number as displayed, or None
    """

    if zs3_id == DEFAULT_ZS3_ID:
        return {"kind": "default", "midi_chan": None, "prog": None}

    if not isinstance(zs3_id, str) or not zs3_id:
        return {"kind": "unnumbered", "midi_chan": None, "prog": None}

    if "/" in zs3_id:
        chan_part, _, prog_part = zs3_id.partition("/")
        prog = _as_int(prog_part)
        if prog is None:
            return {"kind": "unnumbered", "midi_chan": None, "prog": None}
        if chan_part == "*":
            return {"kind": "any_channel", "midi_chan": None, "prog": prog}
        chan = _as_int(chan_part)
        if chan is None:
            return {"kind": "any_channel", "midi_chan": None, "prog": prog}
        return {"kind": "channel", "midi_chan": chan + 1, "prog": prog}

    prog = _as_int(zs3_id)
    if prog is not None:
        return {"kind": "orphan", "midi_chan": None, "prog": prog}

    return {"kind": "unnumbered", "midi_chan": None, "prog": None}


def format_pc_label(zs3_id):
    """Build the program change label, or "" when the ZS3 has no number

    Formatted as the ZS3 list screen formats it (gui_zs3.py:104-106) so the two
    faces of this screen cannot disagree about the same ZS3.

    Returns : String
    """

    parts = parse_zs3_id(zs3_id)
    if parts["prog"] is None:
        return ""
    if parts["midi_chan"] is None:
        return "PRG#{}".format(parts["prog"])
    return "CH#{}:PRG#{}".format(parts["midi_chan"], parts["prog"])


def cue_ids(zs3):
    """Get the ZS3 ids in the order stepping walks them

    Dict insertion order, excluding "zs3-0" => the same list
    state_manager.get_zs3_ids() builds, so the position shown here cannot
    disagree with where ZS3_NEXT / ZS3_PREV will go.

    Returns : List of ZS3 ids
    """

    return [key for key in zs3 if key != DEFAULT_ZS3_ID]


def first_cue_id(zs3):
    """Get the first ZS3 in stepping order, or None if there are none

    Named on the "no ZS3 loaded" face so it can say which ZS3 comes first
    rather than only that none is loaded.

    Returns : ZS3 id or None
    """

    cues = cue_ids(zs3 or {})
    return cues[0] if cues else None


def cue_position(zs3, zs3_id):
    """Get the position of a ZS3 in stepping order, 1-based, and the total

    position is 0 when the id is not in the stepping order: nothing loaded, the
    default state, or an id absent from this snapshot.

    Returns : (position, total)
    """

    cues = cue_ids(zs3)
    try:
        return cues.index(zs3_id) + 1, len(cues)
    except ValueError:
        return 0, len(cues)


def ellipsize(text, limit):
    """Shorten text to limit characters, ending in an ellipsis

    Never clip: a title running off the edge of the screen reads as a different
    title, so seeing that a name has been shortened matters more than seeing
    the end of it.

    Returns : String
    """

    if text is None:
        return ""
    text = str(text)
    if limit is None or limit <= 0:
        return ""
    if len(text) <= limit:
        return text
    if limit == 1:
        return ELLIPSIS
    return text[:limit - 1].rstrip() + ELLIPSIS


def performance_state(zs3, zs3_id):
    """Build everything the performance face draws

    zs3     : The state manager's zs3 dict
    zs3_id  : The current ZS3 id, as carried by SS_LOAD_ZS3, or None

    Titles are returned whole. How much of one fits on screen depends on the
    font and the panel, which this module deliberately cannot see, so the
    screen measures and calls ellipsize() itself.

    For the default state SS_LOAD_ZS3 carries "zs3-0" while last_zs3_id is set
    to None, so the two disagree; both are accepted here and render the same.

    Never raises: an unknown id, an empty snapshot and None are all states this
    screen has to survive mid-performance.

    Returns : dict of title, pc_label, position, total, position_label,
              is_default, is_loaded, is_known
    """

    zs3 = zs3 or {}
    is_default = zs3_id == DEFAULT_ZS3_ID
    is_loaded = bool(zs3_id) and not is_default
    entry = zs3.get(zs3_id) if isinstance(zs3, dict) else None

    if not is_loaded:
        title = "No cue" if zs3_id is None else "Default state"
    elif entry is None:
        # get_zs3_title() falls back to the raw id; do the same rather than
        # invent a placeholder.
        title = str(zs3_id)
    else:
        title = entry.get("title") or str(zs3_id)

    position, total = cue_position(zs3, zs3_id)

    return {
        "title": title,
        "pc_label": format_pc_label(zs3_id) if is_loaded else "",
        "position": position,
        "total": total,
        "position_label": "{} / {}".format(position, total) if position else "- / {}".format(total),
        "is_default": is_default,
        "is_loaded": is_loaded,
        "is_known": entry is not None,
    }


def _as_int(text):
    try:
        return int(text)
    except (TypeError, ValueError):
        return None

# ------------------------------------------------------------------------------
