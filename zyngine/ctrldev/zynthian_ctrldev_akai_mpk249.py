#!/usr/bin/python3
# -*- coding: utf-8 -*-
# ******************************************************************************
# ZYNTHIAN PROJECT: Zynthian Control Device Driver
#
# Zynthian Control Device Driver for "Akai MPK249"
#
# Copyright (C) 2015-2026 Fernando Moyano <jofemodo@zynthian.org>
#                         Brian Walton <brian@riban.co.uk>
#
# Copyright (C) 2026 MPK249 driver contributions
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
import threading

from zyncoder.zyncore import lib_zyncore
from zynlibs.zynseq import zynseq
from zyngine.zynthian_signal_manager import zynsigman
from zyngine.ctrldev.zynthian_ctrldev_base import (
    zynthian_ctrldev_base,
    zynthian_ctrldev_zynmixer,
    zynthian_ctrldev_zynpad,
)

# ------------------------------------------------------------------------------
# MIDI routing
# ------------------------------------------------------------------------------
# Leave False so note/CC data still reaches chains unless this handler consumes
# the message (returns True). Keys on one channel and pads on another is the
# usual factory layout.
#
# If your MPK preset puts drums on channel 10 and the keybed on channel 1, you
# are fine. If everything shares one channel, either reprogram the MPK or set
# a narrow unroute mask (see zynthian_ctrldev_base.unroute_from_chains).
# ------------------------------------------------------------------------------

# Wire-format channel nibble (0 = MIDI ch 1, 9 = MIDI ch 10).
CTRL_MIDI_CH = 0
CTRL_BANK_B_MIDI_CH = 1
CTRL_BANK_C_MIDI_CH = 2
PAD_MIDI_CH = 9
# How pad banks are distinguished:
# - "channel": banks A–D use different MIDI channels (legacy Preset 1–style).
#   Bank index comes from the channel nibble; PAD_NOTE_BANK is one 4×4 grid shared
#   by all banks (same notes on different channels).
# - "single_channel": all pads use PAD_MIDI_CH; each physical pad/bank combination
#   must have a unique MIDI note (factory Generic / MIDI Out–style). Bank index is
#   derived from the note; PAD_NOTE_BANKS lists one 4×4 grid per bank A–D.
PAD_BANK_MODE = "single_channel"
# Some MPK presets send pads on a different channel than expected. When True,
# mapped pad notes are accepted on any channel as a fallback.
PAD_ACCEPT_MAPPED_NOTES_ANY_CH = True
# Optional bank-by-channel mapping for presets where pad banks A/B/C/D reuse
# notes but transmit on different channels (PAD_BANK_MODE == "channel" only).
# Wire-format channels: MIDI ch2..5 => 1..4
PAD_BANK_CH_FIRST = 1
PAD_BANK_CH_COUNT = 4
PAD_BANK_COL_STRIDE = 4
PAD_BANK_ROW_STRIDE = 4
# Bank layout over an 8x8 logical matrix (bank order A,B,C,D):
#   Top row:    A, C
#   Bottom row: B, D
#   A: cols 1-4, rows 1-4
#   B: cols 1-4, rows 5-8
#   C: cols 5-8, rows 1-4
#   D: cols 5-8, rows 5-8
PAD_BANK_LAYOUT_COLS = 2
# Pad LED feedback: either MPK2 RAM writes (SysEx) or note-on velocity (preset-dependent).
# SysEx layout from community reverse-engineering (MPK261); MPK249 uses product id 0x24
# instead of 0x25. See https://practicalusage.com/akai-mpk261-one-more-thing/
PAD_LED_USE_SYSEX = True
# Mirror note-based LED updates to all banks even when SysEx is enabled.
# Some MPK presets keep per-bank pad LED state only when receiving note-on
# feedback on each bank channel.
PAD_LED_MIRROR_NOTES_ALL_BANKS = False
MPK249_SYSEX_PRODUCT_ID = 0x24
# MPK261_SYSEX_PRODUCT_ID = 0x25
# Palette indices 0x00–0x0B (not RGB); tune to taste / firmware.
PAD_SYSEX_COLOR_OFF = 0x00
# Idle = has pattern but not playing; keep well separated from ACTIVE on the hardware.
PAD_SYSEX_COLOR_IDLE = 0x03
PAD_SYSEX_COLOR_ACTIVE = 0x06
PAD_SYSEX_COLOR_STARTING = 0x05
PAD_SYSEX_COLOR_STOPPING = 0x04
# Note-on LED feedback for pad banks B–C–D (and optional mirror on bank A).
# Many MPK presets map note-on to a small palette; keep idle distinct from active.
PAD_LED_OFF_VEL = 0
PAD_LED_IDLE_VEL = 16
PAD_LED_ACTIVE_VEL = 127
PAD_LED_STARTING_VEL = 96
PAD_LED_STOPPING_VEL = 48
# For banks B/C/D (note-feedback), choose how "playing" is shown:
# - "blink": pulse active pads (best distinction on limited note palettes)
# - "steady": keep active pads steady (no blinking)
PAD_NON_A_PLAY_MODE = "blink"
PAD_LED_BLINK_PERIOD_S = 1.0
# Bank B send feedback mode:
# - none: no UI focus/refresh side effects (parameter change only)
# - active_chain: update active chain only, no screen switch (least intrusive)
# - control_screen: jump to SCREEN_CONTROL for explicit send-page visibility
CTRL_BANK_B_FEEDBACK_MODE = "none"
CTRL_BANK_B_AUTOFOCUS_COOLDOWN_S = 0.5
# Verbose bank/LED routing (uses logging.warning so it shows at default log level).
PAD_BANK_DEBUG_LOG = False

# ------------------------------------------------------------------------------
# Control Bank A — faders & pan knobs (VERIFY with Webconf → MIDI log)
# ------------------------------------------------------------------------------
# None: use Generic layout when PAD_BANK_MODE == "single_channel", else Preset 1.
# "generic": faders CC 18, 21–27 (MPK2 Generic / MIDI Out style, see alanschrank/MPK249);
#            knobs in observed order [3, 9, 14, 15, 16, 17, 20, 19].
#            All eight faders → chain levels.
# "preset1": faders CC 12–19, last fader = main mix; knobs CC 22–29.
CTRL_MIXER_LAYOUT = None

def _mpk249_use_generic_mixer_layout():
    if CTRL_MIXER_LAYOUT == "generic":
        return True
    if CTRL_MIXER_LAYOUT == "preset1":
        return False
    return PAD_BANK_MODE == "single_channel"


if _mpk249_use_generic_mixer_layout():
    FADER_CCS = [18, 21, 22, 23, 24, 25, 26, 27]
    # Keep fader 8 as main mix, consistent with Preset 1 behavior.
    MASTER_FADER_INDEX = 7
    # Knobs 1..8 in physical order.
    KNOB_PAN_CCS = [3, 9, 14, 15, 16, 17, 20, 19]
    # Generic encoders behave more reliably as delta from successive absolute-style
    # values (prevents first-contact jumps from stale internal encoder position).
    # This preset appears to emit absolute-like values that do not represent a
    # real hardware pickup point after bank/preset load. "absolute_delta" treats
    # each message as movement since prior message from that knob CC.
    # If feel is too fast/slow, tune KNOB_PAN_REL_STEP below.
    KNOB_PAN_VALUE_MODE = "absolute_delta"
else:
    FADER_CCS = [12, 13, 14, 15, 16, 17, 18, 19]
    MASTER_FADER_INDEX = 7
    KNOB_PAN_CCS = [22, 23, 24, 25, 26, 27, 28, 29]
    KNOB_PAN_VALUE_MODE = "absolute"

CHAIN_PAN_KNOB_COUNT = 7
KNOB_PAN_MASTER_INDEX = 7
# Balance increment per relative encoder "step".
KNOB_PAN_REL_STEP = 0.02
# Snap to exact edges when boundary CC values are reached in matching direction.
KNOB_PAN_EDGE_SNAP = True
# In absolute mode, ignore the first event for each pan knob to avoid initial
# pickup jumps from stale hardware encoder state.
KNOB_PAN_IGNORE_FIRST_ABS = True
MASTER_CC = None
MASTER_CC_BY_CTRL_BANK = {
    CTRL_MIDI_CH: MASTER_CC,
    CTRL_BANK_B_MIDI_CH: None,
    CTRL_BANK_C_MIDI_CH: None,
}
CTRL_BANK_B_SEND_CHAIN_TITLE = "Reverb"

# Pan/balance on CTRL_MIDI_CH follows KNOB_PAN_CCS in physical knob order:
# indices 0..6 map to visible chains; index KNOB_PAN_MASTER_INDEX maps to main balance.
# Absolute 0–127 ↔ balance −1..+1 via cc/64−1.
# Do not send pan CC back in update_mixer_strip: many controllers echo or move
# encoders, which causes wrong LEDs and “snap left” on first touch.

# Pad grid for bank A only (row-major, top row first). Each value is the MIDI
# note number emitted by that pad. Used when PAD_BANK_MODE == "channel"
# (same 16 notes on each pad channel). Rebuild from the MIDI log if launching fails.
PAD_NOTE_BANK = [
    [81, 83, 84, 86],
    [74, 76, 77, 79],
    [67, 69, 71, 72],
    [60, 62, 64, 65],
]

# One 4×4 grid per hardware pad bank A–D when PAD_BANK_MODE == "single_channel".
# Rows are top-to-bottom on the hardware (row 0 = top row of pads); columns left-to-right.
# Factory-style chromatic layout (Pad 1 = bottom-left = C2, Pad 16 = top-right = D#3,
# then each bank continues upward by semitones): Bank A 36–51, B 52–67, C 68–83, D 84–99.
# If your preset differs, confirm with Admin → Webconf → MIDI log.
PAD_NOTE_BANKS = (
    [
        [48, 49, 50, 51],
        [44, 45, 46, 47],
        [40, 41, 42, 43],
        [36, 37, 38, 39],
    ],
    [
        [64, 65, 66, 67],
        [60, 61, 62, 63],
        [56, 57, 58, 59],
        [52, 53, 54, 55],
    ],
    [
        [80, 81, 82, 83],
        [76, 77, 78, 79],
        [72, 73, 74, 75],
        [68, 69, 70, 71],
    ],
    [
        [96, 97, 98, 99],
        [92, 93, 94, 95],
        [88, 89, 90, 91],
        [84, 85, 86, 87],
    ],
)

# Optional transport (CC, must be on CTRL_MIDI_CH). Value > 0 triggers once.
# REW/FF default to navigation actions that are broadly useful in arranger/editor.
TRANSPORT_PLAY_CC = 118
TRANSPORT_STOP_CC = 117
TRANSPORT_REC_CC = 119
TRANSPORT_REW_CC = 115
TRANSPORT_FF_CC = 116
TRANSPORT_LOOP_CC = 114
TRANSPORT_REW_CUIA = "ARROW_LEFT"
TRANSPORT_FF_CUIA = "ARROW_RIGHT"
# No global "TOGGLE_LOOP" CUIA is defined across all contexts; choose one that
# matches your workflow (e.g. a screen navigation action) or leave None.
TRANSPORT_LOOP_CUIA = "TOGGLE_PATTERN_EDITOR_ZYNPAD"


class zynthian_ctrldev_akai_mpk249(zynthian_ctrldev_zynpad, zynthian_ctrldev_zynmixer):

    dev_ids = [
        "MPK249 IN 1",
        "MPK249 IN 2",
        "MPK249 IN 3",
        "MPK249 IN 4",
        "MPK249 IN3",
    ]
    driver_name = "Akai MPK249"
    driver_description = "MPK249 — mixer, pan, zynpad; keys pass through"
    unroute_from_chains = False

    def __init__(self, state_manager, idev_in, idev_out=None):
        self._pad_note_to_rc = {}
        self._pad_note_to_brc = {}
        self._pan_abs_seen_ccs = set()
        self._pan_last_cc_val = {}
        self._pan_last_step_by_cc = {}
        self._current_screen = None
        self._loop_pending_editor = False
        self._blink_timer = None
        self._blink_stop = threading.Event()
        self._blink_phase = False
        self._blink_notes_by_bank = {b: set() for b in range(PAD_BANK_CH_COUNT)}
        self._last_ctrl_bank_b_focus_ts = 0.0
        super().__init__(state_manager, idev_in, idev_out)
        self._active_pad_bank = 0
        self.cols = 4
        self.rows = 4
        self.phrase_launcher_col = self.cols
        self._build_pad_map()

    def _dbg(self, msg):
        # Use WARNING so lines appear with default ZYNTHIAN_LOG_LEVEL (WARNING).
        if PAD_BANK_DEBUG_LOG:
            logging.warning(f"MPK249 DBG: {msg}")

    def init(self):
        super().init()
        logging.info(
            "MPK249 PAD_BANK_MODE=%s (set single_channel + PAD_NOTE_BANKS for Generic/MIDI Out)",
            PAD_BANK_MODE,
        )
        logging.info(
            "MPK249 CTRL_MIXER_LAYOUT=%s generic=%s FADER_CCS=%s KNOB_PAN_CCS=%s "
            "KNOB_PAN_VALUE_MODE=%s MASTER_FADER_INDEX=%s",
            CTRL_MIXER_LAYOUT,
            _mpk249_use_generic_mixer_layout(),
            FADER_CCS,
            KNOB_PAN_CCS,
            KNOB_PAN_VALUE_MODE,
            MASTER_FADER_INDEX,
        )
        self._start_blink_timer()
        zynsigman.register_queued(
            zynsigman.S_GUI,
            zynsigman.SS_GUI_SHOW_SCREEN,
            self.on_gui_show_screen,
        )

    def end(self):
        self._stop_blink_timer()
        zynsigman.unregister(
            zynsigman.S_GUI,
            zynsigman.SS_GUI_SHOW_SCREEN,
            self.on_gui_show_screen,
        )
        super().end()

    def _start_blink_timer(self):
        if PAD_NON_A_PLAY_MODE != "blink":
            return
        self._blink_stop.clear()
        self._schedule_blink_tick()

    def _stop_blink_timer(self):
        self._blink_stop.set()
        if self._blink_timer is not None:
            self._blink_timer.cancel()
            self._blink_timer = None

    def _schedule_blink_tick(self):
        if self._blink_stop.is_set():
            return
        self._blink_timer = threading.Timer(
            max(0.2, PAD_LED_BLINK_PERIOD_S * 0.5), self._blink_tick
        )
        self._blink_timer.daemon = True
        self._blink_timer.start()

    def _blink_tick(self):
        try:
            # Bank A uses SysEx color states and should remain steady.
            if (
                self.idev_out is not None
                and PAD_NON_A_PLAY_MODE == "blink"
                and self._active_pad_bank != 0
            ):
                self._blink_phase = not self._blink_phase
                vel = PAD_LED_ACTIVE_VEL if self._blink_phase else PAD_LED_OFF_VEL
                ch = self._pad_led_out_channel()
                notes = tuple(self._blink_notes_by_bank.get(self._active_pad_bank, ()))
                for note in notes:
                    lib_zyncore.dev_send_note_on(self.idev_out, ch, note, vel)
        except Exception as ex:
            logging.warning(f"MPK249 blink tick: {ex}")
        finally:
            self._schedule_blink_tick()

    def on_gui_show_screen(self, screen):
        self._current_screen = screen

    def refresh(self):
        """Rebuild pad LEDs for the *active* MPK bank's quadrant of the zynpad.

        The base zynpad refresh walks phrases ``scroll_v .. scroll_v+rows-1``, which
        is only correct for a full 8×8 (or scrolled) view. Each MPK pad bank (A–D)
        maps to a 4×4 quadrant: row offset ``bank_row * 4`` and column offset
        ``bank_col * 4`` — same as :meth:`_handle_pad_note`.
        """

        zynthian_ctrldev_base.refresh(self)
        if self.idev_out is None:
            return
        self.light_off()
        bank_row = self._active_pad_bank % PAD_BANK_LAYOUT_COLS
        bank_col = self._active_pad_bank // PAD_BANK_LAYOUT_COLS
        for row in range(self.rows):
            phrase = row + self.scroll_v + bank_row * PAD_BANK_ROW_STRIDE
            for chan in range(32):
                self.update_seq_state(phrase, chan)
            self.update_seq_state(phrase, zynseq.PHRASE_CHANNEL)

    def update_seq_state(self, phrase, chan):
        """Map global phrase / chain index to the 4×4 grid for the active bank."""

        if chan is None or self.idev_out is None:
            return

        bank_row = self._active_pad_bank % PAD_BANK_LAYOUT_COLS
        bank_col = self._active_pad_bank // PAD_BANK_LAYOUT_COLS
        row = phrase - self.scroll_v - bank_row * PAD_BANK_ROW_STRIDE
        if row < 0 or row >= self.rows:
            return

        if chan == zynseq.PHRASE_CHANNEL:
            col = self.phrase_launcher_col
            try:
                pad_info = self.zynseq.state["scenes"][self.zynseq.scene]["phrases"][phrase]
                pad_info["empty"] = False
            except Exception:
                pad_info = None
            self.update_pad(row, col, pad_info)
            return

        try:
            pad_info = self.zynseq.state["scenes"][self.zynseq.scene]["phrases"][phrase]["sequences"][chan]
            if pad_info["group"] < 16:
                try:
                    pattern = pad_info["tracks"][0]["patns"]["0"]
                    pad_info["empty"] = len(self.zynseq.state["patns"][str(pattern)]["events"]) == 0
                except Exception:
                    pad_info["empty"] = True
            else:
                try:
                    chain_id = self.chain_manager.get_chain_ids_by_midi_chan(chan)[0]
                    chain = self.chain_manager.chains[chain_id]
                    clippy_proc = chain.get_clippy_processor()
                    if clippy_proc.controllers_dict[f"file {phrase + 1}"].get_value():
                        pad_info["empty"] = False
                    else:
                        pad_info["empty"] = True
                except Exception:
                    pad_info["empty"] = True
        except IndexError:
            pad_info = None

        for idx in self.chain_manager.get_pos_by_midi_chan(chan):
            col = idx - self.scroll_h - bank_col * PAD_BANK_COL_STRIDE
            if 0 <= col < self.cols:
                self.update_pad(row, col, pad_info)

    def _pad_note_for_cell(self, bank, row, col):
        """MIDI note used for LED feedback for this logical bank/cell."""

        if PAD_BANK_MODE == "single_channel":
            return PAD_NOTE_BANKS[bank][row][col]
        return PAD_NOTE_BANK[row][col]

    def _pad_led_out_channel(self):
        """Wire-format channel nibble for pad LED note-on feedback."""

        if PAD_BANK_MODE == "single_channel":
            return PAD_MIDI_CH
        return PAD_BANK_CH_FIRST + self._active_pad_bank

    def _build_pad_map(self):
        self._pad_note_to_rc.clear()
        self._pad_note_to_brc.clear()
        if PAD_BANK_MODE == "single_channel":
            if len(PAD_NOTE_BANKS) != PAD_BANK_CH_COUNT:
                logging.warning(
                    "MPK249 PAD_NOTE_BANKS must have %s banks (got %s)",
                    PAD_BANK_CH_COUNT,
                    len(PAD_NOTE_BANKS),
                )
            seen = {}
            for bank, grid in enumerate(PAD_NOTE_BANKS):
                for r, row in enumerate(grid):
                    for c, note in enumerate(row):
                        if note in seen:
                            logging.warning(
                                "MPK249 PAD_NOTE_BANKS: duplicate note %s at "
                                "bank %s cell %s,%s and %s",
                                note,
                                bank,
                                r,
                                c,
                                seen[note],
                            )
                        seen[note] = (bank, r, c)
                        self._pad_note_to_brc[note] = (bank, r, c)
            return
        for r, row in enumerate(PAD_NOTE_BANK):
            for c, note in enumerate(row):
                self._pad_note_to_rc[note] = (r, c)

    @staticmethod
    def _mpk249_pad_ram_bytes(row, col):
        """Return two address bytes (each ≤0x7F) for pad RAM color slot.

        Community docs list SysEx pad RAM from the bottom row of the hardware
        (0x0A7C–0x0A7F) then upward through 0x0B00–0x0B0B.  PAD_NOTE_BANK uses
        row 0 as the top row (highest MIDI notes).  Map logical rows without
        flipping column order.
        """

        if not (0 <= row <= 3 and 0 <= col <= 3):
            raise ValueError(f"bad pad cell {row},{col}")
        ram_row = 3 - row
        if ram_row == 0:
            return (0x0A, 0x7C + col)
        return (0x0B, (ram_row - 1) * 4 + col)

    def _send_pad_led_sysex(self, row, col, color):
        if self.idev_out is None:
            return
        ah, al = self._mpk249_pad_ram_bytes(row, col)
        color &= 0x7F
        msg = bytes(
            [
                0xF0,
                0x47,
                0x00,
                MPK249_SYSEX_PRODUCT_ID,
                0x31,
                0x00,
                0x04,
                0x01,
                ah,
                al,
                color,
                0xF7,
            ]
        )
        try:
            lib_zyncore.dev_send_midi_event(self.idev_out, msg, len(msg))
        except Exception as ex:
            logging.warning(f"MPK249 pad SysEx: {ex}")

    @staticmethod
    def _cc_to_balance(ccval):
        """Map MIDI CC 0–127 to zynmixer balance −1..+1 (MIDI Mix style)."""

        return max(-1.0, min(1.0, ccval / 64.0 - 1.0))

    @staticmethod
    def _clamp_balance(val):
        return max(-1.0, min(1.0, float(val)))

    @staticmethod
    def _cc_to_relative_steps(ccval):
        """Decode common relative encoder CC encodings into signed steps."""

        v = int(ccval) & 0x7F
        if KNOB_PAN_VALUE_MODE == "relative_binary_offset":
            # 64 = no move; >64 clockwise; <64 counter-clockwise.
            return v - 64
        if KNOB_PAN_VALUE_MODE == "relative_signed_bit":
            # 1..63 clockwise, 65..127 counter-clockwise, 64 = no move.
            if v == 64:
                return 0
            if v < 64:
                return v
            return -(v - 64)
        # Default relative_twos_complement: 1 = +1, 127 = -1, 0 = 0.
        if v == 0:
            return 0
        return v if v < 64 else v - 128

    def _absolute_cc_delta_steps(self, ccnum, ccval):
        """Delta from successive 0..127 values with wrap handling."""

        v = int(ccval) & 0x7F
        prev = self._pan_last_cc_val.get(ccnum)
        self._pan_last_cc_val[ccnum] = v
        if prev is None:
            return 0
        d = v - prev
        if d > 64:
            d -= 128
        elif d < -64:
            d += 128
        if d != 0:
            self._pan_last_step_by_cc[ccnum] = 1 if d > 0 else -1
            return d
        # Some presets clamp encoder value at boundaries but still emit repeated
        # 0/127 while turning. Continue in the last known direction so pan can
        # still reach exact -100/+100 without a forced reverse turn.
        last_dir = self._pan_last_step_by_cc.get(ccnum, 0)
        if v == 127 and last_dir > 0:
            return 1
        if v == 0 and last_dir < 0:
            return -1
        return d

    def _set_strip_balance_from_cc(self, pos, ccval, ccnum=None):
        """Apply pan to a chain strip mixer; always drive zynmixer (not only on zctrl delta)."""

        chain = self.get_filtered_chain_by_index(pos)
        if not chain or not chain.zynmixer_proc:
            return
        proc = chain.zynmixer_proc
        try:
            if KNOB_PAN_VALUE_MODE == "absolute":
                val = self._cc_to_balance(ccval)
            elif KNOB_PAN_VALUE_MODE == "absolute_delta":
                current = proc.zynmixer.get_balance(proc.mixer_chan)
                steps = self._absolute_cc_delta_steps(ccnum, ccval)
                if KNOB_PAN_EDGE_SNAP and ccval == 127 and steps > 0:
                    val = 1.0
                elif KNOB_PAN_EDGE_SNAP and ccval == 0 and steps < 0:
                    val = -1.0
                elif steps == 0:
                    return
                else:
                    val = self._clamp_balance(current + steps * KNOB_PAN_REL_STEP)
            else:
                current = proc.zynmixer.get_balance(proc.mixer_chan)
                steps = self._cc_to_relative_steps(ccval)
                val = self._clamp_balance(current + steps * KNOB_PAN_REL_STEP)
            proc.zynmixer.set_balance(proc.mixer_chan, val)
            zc = proc.controllers_dict.get("balance")
            if zc is not None:
                zc.set_value(val, send=False)
        except Exception as ex:
            logging.warning(f"MPK249 chain balance: {ex}")

    def _set_main_balance_from_cc(self, ccval, ccnum=None):
        mp = self.state_manager.main_mixbus_proc
        if not mp:
            return
        try:
            if KNOB_PAN_VALUE_MODE == "absolute":
                val = self._cc_to_balance(ccval)
            elif KNOB_PAN_VALUE_MODE == "absolute_delta":
                current = mp.zynmixer.get_balance(mp.mixer_chan)
                steps = self._absolute_cc_delta_steps(ccnum, ccval)
                if KNOB_PAN_EDGE_SNAP and ccval == 127 and steps > 0:
                    val = 1.0
                elif KNOB_PAN_EDGE_SNAP and ccval == 0 and steps < 0:
                    val = -1.0
                elif steps == 0:
                    return
                else:
                    val = self._clamp_balance(current + steps * KNOB_PAN_REL_STEP)
            else:
                current = mp.zynmixer.get_balance(mp.mixer_chan)
                steps = self._cc_to_relative_steps(ccval)
                val = self._clamp_balance(current + steps * KNOB_PAN_REL_STEP)
            mp.zynmixer.set_balance(mp.mixer_chan, val)
            zc = mp.controllers_dict.get("balance")
            if zc is not None:
                zc.set_value(val, send=False)
        except Exception as ex:
            logging.warning(f"MPK249 main balance: {ex}")

    def _should_ignore_first_absolute_pan(self, ccnum):
        if KNOB_PAN_VALUE_MODE != "absolute" or not KNOB_PAN_IGNORE_FIRST_ABS:
            return False
        if ccnum in self._pan_abs_seen_ccs:
            return False
        self._pan_abs_seen_ccs.add(ccnum)
        self._dbg(f"pan_pickup_ignore_first cc={ccnum}")
        return True

    @staticmethod
    def _control_bank_name_from_channel(ch):
        return {
            CTRL_MIDI_CH: "A",
            CTRL_BANK_B_MIDI_CH: "B",
            CTRL_BANK_C_MIDI_CH: "C",
        }.get(ch, "?")

    def update_mixer_strip(self, chan, symbol, value, mixbus=False):
        """Mirror mixer changes onto MPK faders (best-effort; faders are not motorized)."""

        if self.idev_out is None or symbol != "level":
            return
        try:
            if mixbus:
                mp = self.state_manager.main_mixbus_proc
                if not mp or chan != mp.mixer_chan:
                    return
                if MASTER_FADER_INDEX is not None:
                    ccval = min(127, max(0, int(round(float(value) * 127.0))))
                    lib_zyncore.dev_send_ccontrol_change(
                        self.idev_out,
                        CTRL_MIDI_CH,
                        FADER_CCS[MASTER_FADER_INDEX],
                        ccval,
                    )
                return
            pos = self.chain_manager.get_pos_by_mixer_chan(chan, mixbus)
            if pos is None:
                return
            col = pos - self.scroll_h
            max_chain_fader = (
                MASTER_FADER_INDEX
                if MASTER_FADER_INDEX is not None
                else len(FADER_CCS)
            )
            if 0 <= col < max_chain_fader:
                ccval = min(127, max(0, int(round(float(value) * 127.0))))
                lib_zyncore.dev_send_ccontrol_change(
                    self.idev_out, CTRL_MIDI_CH, FADER_CCS[col], ccval
                )
        except Exception as ex:
            logging.warning(f"MPK249 mixer feedback: {ex}")

    def _handle_control_bank_a_cc(self, ccnum, ccval):
        """Default BANK A mapping: current mixer/pan/transport behavior."""

        master_cc = MASTER_CC_BY_CTRL_BANK.get(CTRL_MIDI_CH, MASTER_CC)
        if master_cc is not None and ccnum == master_cc:
            self.set_mixer_param("level", -1, ccval / 127.0)
            return True

        if ccnum in FADER_CCS:
            col = FADER_CCS.index(ccnum)
            if MASTER_FADER_INDEX is not None and col == MASTER_FADER_INDEX:
                # Main mixbus lives on zynmixer_bus (not zynmixer_chan); use the
                # chain-0 MR processor so level updates route correctly.
                mp = self.state_manager.main_mixbus_proc
                if mp and "level" in mp.controllers_dict:
                    val = ccval / 127.0
                    zc = mp.controllers_dict["level"]
                    if zc.value != val:
                        zc.set_value(val)
                return True
            pos = self.scroll_h + col
            self.set_mixer_param("level", pos, ccval / 127.0)
            return True

        if ccnum in KNOB_PAN_CCS:
            if self._should_ignore_first_absolute_pan(ccnum):
                return True
            idx = KNOB_PAN_CCS.index(ccnum)
            if idx == KNOB_PAN_MASTER_INDEX:
                self._set_main_balance_from_cc(ccval, ccnum)
                return True
            if 0 <= idx < CHAIN_PAN_KNOB_COUNT:
                pos = self.scroll_h + idx
                self._set_strip_balance_from_cc(pos, ccval, ccnum)
                return True

        if TRANSPORT_PLAY_CC is not None and ccnum == TRANSPORT_PLAY_CC and ccval > 0:
            self.state_manager.send_cuia("TOGGLE_PLAY")
            return True
        if TRANSPORT_STOP_CC is not None and ccnum == TRANSPORT_STOP_CC and ccval > 0:
            self.state_manager.send_cuia("STOP")
            return True
        if TRANSPORT_REC_CC is not None and ccnum == TRANSPORT_REC_CC and ccval > 0:
            self.state_manager.send_cuia("TOGGLE_RECORD")
            return True
        if TRANSPORT_REW_CC is not None and ccnum == TRANSPORT_REW_CC and ccval > 0:
            if TRANSPORT_REW_CUIA:
                self.state_manager.send_cuia(TRANSPORT_REW_CUIA)
            return True
        if TRANSPORT_FF_CC is not None and ccnum == TRANSPORT_FF_CC and ccval > 0:
            if TRANSPORT_FF_CUIA:
                self.state_manager.send_cuia(TRANSPORT_FF_CUIA)
            return True
        if TRANSPORT_LOOP_CC is not None and ccnum == TRANSPORT_LOOP_CC and ccval > 0:
            if TRANSPORT_LOOP_CUIA == "TOGGLE_PATTERN_EDITOR_ZYNPAD":
                if self._current_screen == "pattern_editor":
                    self._loop_pending_editor = False
                    self.state_manager.send_cuia("SCREEN_ZYNPAD")
                else:
                    # Deterministic two-step toggle:
                    # 1) Normalize to ZynPad from any non-editor screen.
                    # 2) Next press enters Pattern Editor.
                    if self._loop_pending_editor:
                        self._loop_pending_editor = False
                        self.state_manager.send_cuia("SCREEN_PATTERN_EDITOR")
                    elif self._current_screen in ("zynpad", "arranger", "launcher"):
                        self.state_manager.send_cuia("SCREEN_PATTERN_EDITOR")
                    else:
                        self._loop_pending_editor = True
                        self.state_manager.send_cuia("SCREEN_ZYNPAD")
            elif TRANSPORT_LOOP_CUIA:
                self.state_manager.send_cuia(TRANSPORT_LOOP_CUIA)
            return True

        return False

    def _handle_control_bank_b_cc(self, ccnum, ccval):
        """CONTROL BANK B mapping hook (MIDI channel 2 / nibble 1).

        Mapping:
        - Knobs 1..7  => send level to mixbus named CTRL_BANK_B_SEND_CHAIN_TITLE
        - Knob 8      => return level of that mixbus chain
        - Transport   => mirrored from BANK A
        """

        def _get_mixbus_chain_by_title(title):
            title_l = (title or "").strip().lower()
            if not title_l:
                return None
            for chain in self.chain_manager.chains.values():
                try:
                    if not chain.is_mixbus():
                        continue
                    if (chain.get_title() or "").strip().lower() == title_l:
                        return chain
                except Exception:
                    continue
            return None

        def _focus_control_for_chain(chain_id):
            if CTRL_BANK_B_FEEDBACK_MODE not in ("active_chain", "control_screen"):
                return
            now = time.monotonic()
            if now - self._last_ctrl_bank_b_focus_ts < CTRL_BANK_B_AUTOFOCUS_COOLDOWN_S:
                return
            try:
                self.chain_manager.set_active_chain_by_id(chain_id)
                if CTRL_BANK_B_FEEDBACK_MODE == "control_screen":
                    self.state_manager.send_cuia("SCREEN_CONTROL")
                    self.state_manager.send_cuia("refresh_screen", ["control"])
                else:
                    # No screen switch: hint UI to refresh overlays/widgets.
                    self.state_manager.send_cuia("refresh_screen", ["control"])
                    self.state_manager.send_cuia("refresh_screen", ["audio_mixer"])
            except Exception as ex:
                logging.warning(f"MPK249 BANK B control focus: {ex}")
            self._last_ctrl_bank_b_focus_ts = now

        # Knobs 1..8 (in KNOB_PAN_CCS order) map to reverb sends/return.
        if ccnum in KNOB_PAN_CCS:
            if self._should_ignore_first_absolute_pan(ccnum):
                return True
            send_chain = _get_mixbus_chain_by_title(CTRL_BANK_B_SEND_CHAIN_TITLE)
            if not send_chain or not send_chain.zynmixer_proc:
                return False

            val = ccval / 127.0
            knob_idx = KNOB_PAN_CCS.index(ccnum)
            # Knob 8 controls reverb return level.
            if knob_idx == KNOB_PAN_MASTER_INDEX:
                _focus_control_for_chain(send_chain.chain_id)
                try:
                    zc = send_chain.zynmixer_proc.controllers_dict.get("level")
                    if zc is not None and zc.value != val:
                        zc.set_value(val)
                        return True
                except Exception as ex:
                    logging.warning(f"MPK249 BANK B reverb return: {ex}")
                return False

            # Knobs 1..7 control visible chain sends to reverb mixbus.
            pos = self.scroll_h + knob_idx
            chain = self.get_filtered_chain_by_index(pos)
            if not chain or not chain.zynmixer_proc:
                return False
            _focus_control_for_chain(chain.chain_id)
            send_symbol = f"send_{send_chain.chain_id}_level"
            try:
                zc = chain.zynmixer_proc.controllers_dict.get(send_symbol)
                if zc is None:
                    return False
                if zc.value != val:
                    zc.set_value(val)
                return True
            except Exception as ex:
                logging.warning(f"MPK249 BANK B send '{send_symbol}': {ex}")
                return False

        if TRANSPORT_PLAY_CC is not None and ccnum == TRANSPORT_PLAY_CC and ccval > 0:
            self.state_manager.send_cuia("TOGGLE_PLAY")
            return True
        if TRANSPORT_STOP_CC is not None and ccnum == TRANSPORT_STOP_CC and ccval > 0:
            self.state_manager.send_cuia("STOP")
            return True
        if TRANSPORT_REC_CC is not None and ccnum == TRANSPORT_REC_CC and ccval > 0:
            self.state_manager.send_cuia("TOGGLE_RECORD")
            return True
        return False

    def _handle_control_bank_c_cc(self, ccnum, ccval):
        """CONTROL BANK C mapping hook (MIDI channel 3 / nibble 2).

        Default: no CC assignments. Add mappings here as desired.
        """

        return False

    @staticmethod
    def _pad_led_feedback(pad_info):
        """Return (note_velocity, sysex_color) for pad_info from zynpad."""

        vel = PAD_LED_OFF_VEL
        syx = PAD_SYSEX_COLOR_OFF
        try:
            state = pad_info["state"]
            if state == zynseq.SEQ_PLAYING:
                vel = PAD_LED_ACTIVE_VEL
                syx = PAD_SYSEX_COLOR_ACTIVE
            elif state in (
                zynseq.SEQ_STARTING,
                zynseq.SEQ_STOPPING,
                zynseq.SEQ_STOPPING_SYNC,
            ):
                if state == zynseq.SEQ_STARTING:
                    vel = PAD_LED_STARTING_VEL
                    syx = PAD_SYSEX_COLOR_STARTING
                else:
                    vel = PAD_LED_STOPPING_VEL
                    syx = PAD_SYSEX_COLOR_STOPPING
            elif state == zynseq.SEQ_STOPPED and not pad_info.get("empty", True):
                vel = PAD_LED_IDLE_VEL
                syx = PAD_SYSEX_COLOR_IDLE
        except Exception:
            pass
        return vel, syx

    def update_pad(self, row, col, pad_info):
        if self.idev_out is None or col == self.cols:
            return
        try:
            note = self._pad_note_for_cell(self._active_pad_bank, row, col)
        except Exception:
            return

        vel, syx = self._pad_led_feedback(pad_info)
        state = None if pad_info is None else pad_info.get("state")
        empty = None if pad_info is None else pad_info.get("empty")
        self._dbg(
            f"update_pad row={row} col={col} bank={self._active_pad_bank} "
            f"note={note} state={state} empty={empty} vel={vel} syx={syx}"
        )

        # SysEx RAM writes are reliable for Bank A but unstable across B/C/D on
        # some MPK firmware presets (can blank/ghost Bank A). Keep SysEx on A.
        if PAD_LED_USE_SYSEX and self._active_pad_bank == 0:
            self._send_pad_led_sysex(row, col, syx)
            if not PAD_LED_MIRROR_NOTES_ALL_BANKS:
                return

        # Track which pads are PLAYING so we can blink them without repainting
        # the whole bank (avoids "everything red flickers" effect).
        if PAD_NON_A_PLAY_MODE == "blink" and self._active_pad_bank != 0:
            notes = self._blink_notes_by_bank.setdefault(self._active_pad_bank, set())
            if state == zynseq.SEQ_PLAYING:
                notes.add(note)
            else:
                notes.discard(note)

        ch = self._pad_led_out_channel()
        self._dbg(f"send_note_led ch={ch} note={note} vel={vel}")
        lib_zyncore.dev_send_note_on(self.idev_out, ch, note, vel)

    def light_off(self):
        if self.idev_out is None:
            return
        self._dbg(f"light_off bank={self._active_pad_bank}")
        # Only clear SysEx pad RAM while Bank A is active. Clearing RAM during
        # B/C/D refresh can blank Bank A's physical colors until A refreshes.
        if PAD_LED_USE_SYSEX and self._active_pad_bank == 0:
            for row in range(len(PAD_NOTE_BANK)):
                for col in range(len(PAD_NOTE_BANK[row])):
                    self._send_pad_led_sysex(row, col, PAD_SYSEX_COLOR_OFF)
        # Wipe note-feedback: multi-channel presets use one channel per bank; single-channel
        # presets use PAD_MIDI_CH with distinct notes per bank/cell.
        if PAD_BANK_MODE == "single_channel":
            ch = PAD_MIDI_CH
            for bank in range(PAD_BANK_CH_COUNT):
                for row in range(len(PAD_NOTE_BANKS[bank])):
                    for col in range(len(PAD_NOTE_BANKS[bank][row])):
                        note = PAD_NOTE_BANKS[bank][row][col]
                        self._dbg(
                            f"send_note_off ch={ch} note={note} vel={PAD_LED_OFF_VEL}"
                        )
                        lib_zyncore.dev_send_note_on(
                            self.idev_out, ch, note, PAD_LED_OFF_VEL
                        )
        else:
            for bank in range(PAD_BANK_CH_COUNT):
                ch = PAD_BANK_CH_FIRST + bank
                for row in range(len(PAD_NOTE_BANK)):
                    for col in range(len(PAD_NOTE_BANK[row])):
                        note = PAD_NOTE_BANK[row][col]
                        self._dbg(
                            f"send_note_off ch={ch} note={note} vel={PAD_LED_OFF_VEL}"
                        )
                        lib_zyncore.dev_send_note_on(
                            self.idev_out, ch, note, PAD_LED_OFF_VEL
                        )

    def _get_pad_bank_from_channel(self, ch):
        """Return pad bank index from wire-format MIDI channel nibble."""

        bank = ch - PAD_BANK_CH_FIRST
        if 0 <= bank < PAD_BANK_CH_COUNT:
            return bank
        return 0

    def _handle_pad_note(self, note, ch):
        if PAD_BANK_MODE == "single_channel":
            brc = self._pad_note_to_brc.get(note)
            if not brc:
                return False
            bank, row, col = brc
            self._dbg(
                f"pad_note_in ch={ch} note={note} -> bank={bank} (single_ch map)"
            )
        else:
            pos = self._pad_note_to_rc.get(note)
            if not pos:
                return False
            row, col = pos
            bank = self._get_pad_bank_from_channel(ch)
            self._dbg(f"pad_note_in ch={ch} note={note} -> bank={bank}")
        if bank != self._active_pad_bank:
            # Stop blink state from leaking across banks.
            self._blink_notes_by_bank = {b: set() for b in range(PAD_BANK_CH_COUNT)}
            self._active_pad_bank = bank
            # Reload persisted LED state for the newly active hardware bank.
            self._dbg(f"bank_switch active_bank={self._active_pad_bank}; refresh()")
            self.refresh()
        bank_col = bank // PAD_BANK_LAYOUT_COLS
        bank_row = bank % PAD_BANK_LAYOUT_COLS
        phrase = self.scroll_v + row + bank_row * PAD_BANK_ROW_STRIDE
        chain_col = self.scroll_h + col + bank_col * PAD_BANK_COL_STRIDE
        midi_chan = self.get_filtered_midi_chan_by_index(chain_col)
        if midi_chan is None:
            return True
        try:
            self._dbg(
                f"toggle_play scene={self.zynseq.scene} phrase={phrase} midi_chan={midi_chan} "
                f"(row={row} col={col} bank={bank})"
            )
            self.zynseq.libseq.togglePlayState(self.zynseq.scene, phrase, midi_chan)
        except Exception as ex:
            logging.warning(f"MPK249 pad toggle => {ex}")
        return True

    def midi_event(self, ev):
        evtype = (ev[0] >> 4) & 0x0F
        ch = ev[0] & 0x0F

        if evtype == 0xB:
            ccnum = ev[1] & 0x7F
            ccval = ev[2] & 0x7F
            if ch == CTRL_MIDI_CH:
                return self._handle_control_bank_a_cc(ccnum, ccval)
            if ch == CTRL_BANK_B_MIDI_CH:
                return self._handle_control_bank_b_cc(ccnum, ccval)
            if ch == CTRL_BANK_C_MIDI_CH:
                return self._handle_control_bank_c_cc(ccnum, ccval)
            return False

        if evtype == 0x9:
            vel = ev[2] & 0x7F
            note = ev[1] & 0x7F
            if PAD_BANK_MODE == "single_channel":
                is_mapped_pad_note = note in self._pad_note_to_brc
            else:
                is_mapped_pad_note = note in self._pad_note_to_rc
            is_pad_input = ch == PAD_MIDI_CH or (
                PAD_ACCEPT_MAPPED_NOTES_ANY_CH and is_mapped_pad_note
            )
            if is_pad_input:
                self._dbg(f"midi_note_on ch={ch} note={note} vel={vel} pad_input={is_pad_input}")
                # Always consume pad-channel note events so they don't leak to
                # other subsystems (e.g. pattern editor keymap handlers).
                if vel > 0:
                    self._handle_pad_note(note, ch)
                return True
            return False

        if evtype == 0x8:
            note = ev[1] & 0x7F
            if PAD_BANK_MODE == "single_channel":
                is_mapped_pad_note = note in self._pad_note_to_brc
            else:
                is_mapped_pad_note = note in self._pad_note_to_rc
            if ch == PAD_MIDI_CH or (PAD_ACCEPT_MAPPED_NOTES_ANY_CH and is_mapped_pad_note):
                return True
            return False

        return False

# ------------------------------------------------------------------------------
