#!/usr/bin/python3
# -*- coding: utf-8 -*-
# ******************************************************************************
# ZYNTHIAN PROJECT: Zynthian Control Device Driver
#
# Zynthian Control Device Driver for to drive SooperLooper from MIDI CC
#
# Copyright (C) 2026 TK Conrad <tkconrad@gmail.com>
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
from zyngine.zynthian_signal_manager import zynsigman
from zyngine.ctrldev.zynthian_ctrldev_base import zynthian_ctrldev_base


# ──────────────────────────────────────────────────────────────────────────────
#  CONSTANTS — MIDI MAPPING CC -> SOOPERLOOPER
# ──────────────────────────────────────────────────────────────────────────────
#
# The MIDI controller (e.g. Behringer FCB1010) should send plain Control Change
# (CC) messages, one per pedal, with a value > 0 on press ("down") and 0 on
# release ("up"). All the logic below triggers on press (byte2 > 0) and ignores
# release (byte2 == 0), unless stated otherwise.
#
# Reminder of the requested mapping (loops are numbered 1 to 5 on the user
# side, and 0 to 4 on the SooperLooper engine / controllers_dict side):
#
#   CC 15 : Mute current loop (+ stop record) / Next loop / Record
#   CC 16 : Mute loops 3,4,5 / Trigger loop 2 from the start (quantized)
#   CC 17 : Mute loops 2,4,5 / Trigger loop 3 from the start (quantized)
#   CC 18 : Mute loops 2,3,5 / Trigger loop 4 from the start (quantized)
#   CC 19 : Mute loops 2,3,4 / Trigger loop 5 from the start (quantized)
#   CC 20 : Next loop
#   CC 21 : Mute current loop
#   CC 22 : Record current loop
#   CC 23 : Soft reset — mute all loops, stop any recording/overdub, reselect
#           loop 1, re-sync the driver's internal tracking, and re-apply the
#           quantize/sync engine settings. Does NOT erase recorded audio.

# Pedal CC numbers (1 to 10 on the FCB1010; only the ones listed are used here)
CC_CURRENT_MUTE_RECORD   = 15   # Mute current loop (+stop record) / Next loop / Record
CC_SOLO_LOOP2            = 16   # Mute 3,4,5 / Trigger 2 from start (quantized)
CC_SOLO_LOOP3            = 17   # Mute 2,4,5 / Trigger 3 from start (quantized)
CC_SOLO_LOOP4            = 18   # Mute 2,3,5 / Trigger 4 from start (quantized)
CC_SOLO_LOOP5            = 19   # Mute 2,3,4 / Trigger 5 from start (quantized)
CC_NEXT_LOOP             = 20   # Next loop
CC_MUTE_CURRENT          = 21   # Mute/unmute current loop (toggle)
CC_RECORD_CURRENT        = 22   # Record current loop
CC_SOFT_RESET            = 23   # Soft reset (mute all, stop recording, reselect loop 1, resync)

# List of all CC numbers handled by this driver (for quick membership tests)
HANDLED_CC = [
    CC_CURRENT_MUTE_RECORD,
    CC_SOLO_LOOP2,
    CC_SOLO_LOOP3,
    CC_SOLO_LOOP4,
    CC_SOLO_LOOP5,
    CC_NEXT_LOOP,
    CC_MUTE_CURRENT,
    CC_RECORD_CURRENT,
    CC_SOFT_RESET,
]

# Number of loops managed (loops 1 to 5 -> engine index 0 to 4)
NUM_LOOPS = 5
LOOP1_INDEX = 0  # loop 1 acts as the quantize/sync reference

# Global symbols exposed by Zynthian's SooperLooper processor
LOOP_SELECTED_SYMBOL  = "selected_loop_num"
SYNC_SOURCE_SYMBOL    = "sync_source"
QUANTIZE_SYMBOL       = "quantize"
MUTE_QUANTIZED_SYMBOL = "mute_quantized"
OVERDUB_QUANTIZED_SYMBOL = "overdub_quantized"
SELECTED_LOOP_CC_SYMBOL = "selected_loop_cc"

# Global parameter values, see SooperLooper OSC doc:
#   quantize : 0=off, 1=cycle, 2=8th, 3=loop
#   mute_quantized / overdub_quantized : 0=off, !=0 -> on
#   sync_source : -3=internal, -2=midi, -1=jack, 0=none, N>0 = loop N (1-indexed)
QUANTIZE_LOOP_VALUE   = 3   # quantize against the loop length ("loop")
QUANTIZED_ON_VALUE    = 1
SYNC_SOURCE_LOOP1     = 1   # 1-indexed on the OSC side -> loop 1


# ──────────────────────────────────────────────────────────────────────────────
#  MAIN DRIVER
# ──────────────────────────────────────────────────────────────────────────────

class zynthian_ctrldev_sooperlooper_ccx10(zynthian_ctrldev_base):

    # ── ALSA identification ───────────────────────────────────────────────────
    # Check with 'aconnect -l' and adapt the exact name if necessary.
    dev_ids = ["*"]
    driver_name = "SooperLooper CCx10"
    driver_description = "Integrates up to to 10 MIDI CC with SooperLooper. Tested with Behringer FCB1010."

    # The CC numbers handled here are consumed (return True); everything else
    # passes through freely for Zynthian's standard MIDI Learn.
    unroute_from_chains = False

    def __init__(self, state_manager, idev_in, idev_out):
        super().__init__(state_manager, idev_in, idev_out)

        # Subscribe to ZS3 / snapshot load signals
        zynsigman.register_queued(zynsigman.S_STATE_MAN, zynsigman.SS_LOAD_ZS3, self.on_zs3_loaded)
        zynsigman.register_queued(zynsigman.S_STATE_MAN, zynsigman.SS_LOAD_SNAPSHOT, self.on_snapshot_loaded)
        self.idev_out = idev_out

        self.chain = None
        self.processor = None

        # Fallback local mute state tracking (used only if engine state is unreadable)
        self.mute_state = [False] * NUM_LOOPS

        # Set to True the first time we successfully dump the monitors dict keys,
        # so we only spam the log once (helps confirm the real key naming on this
        # particular zynthian/SooperLooper version — see _get_monitors_dict()).
        self._monitors_keys_logged = False
        # Set once _get_loop_state() finds a working candidate key, purely so
        # we only log the "MATCHED" line once instead of on every call.
        self._matched_state_key = None

        return

    def end(self):
        zynsigman.unregister(zynsigman.S_STATE_MAN, zynsigman.SS_LOAD_ZS3, self.on_zs3_loaded)
        zynsigman.unregister(zynsigman.S_STATE_MAN, zynsigman.SS_LOAD_SNAPSHOT, self.on_snapshot_loaded)
        super().end()
        return

    def on_snapshot_loaded(self):
        self.refresh(force=True)
        return

    def on_zs3_loaded(self, zs3_id):
        self.refresh(force=True)
        return

    # ── Refresh — find the processor and configure quantize/sync ─────────────

    def refresh(self, force=False):
        cm = self.state_manager.chain_manager
        for chain_id, chain in cm.chains.items():
            logging.debug(f"FCB1010: scanning chain id={chain_id} name='{chain.get_name()}'")
            processors = chain.get_processors()
            for processor in processors:
                if processor.get_name() == "SooperLooper":
                    self.chain = chain
                    self.processor = processor

        if self.processor is None:
            logging.warning("FCB1010: refresh() found NO 'SooperLooper' processor in any chain.")
            return

        cdict = self.processor.controllers_dict

        # Reset local fallback sync
        for i in range(NUM_LOOPS):
            key = f"mute:{i}"
            if key in cdict:
                try:
                    self.mute_state[i] = bool(int(cdict[key].get_value()))
                except (TypeError, ValueError):
                    self.mute_state[i] = False

        # ── Quantize / Sync configuration, based on loop 1 ──────────────────
        if SYNC_SOURCE_SYMBOL in cdict:
            cdict[SYNC_SOURCE_SYMBOL].set_value(SYNC_SOURCE_LOOP1)
        if QUANTIZE_SYMBOL in cdict:
            cdict[QUANTIZE_SYMBOL].set_value(QUANTIZE_LOOP_VALUE)
        if MUTE_QUANTIZED_SYMBOL in cdict:
            cdict[MUTE_QUANTIZED_SYMBOL].set_value(QUANTIZED_ON_VALUE)
        if OVERDUB_QUANTIZED_SYMBOL in cdict:
            cdict[OVERDUB_QUANTIZED_SYMBOL].set_value(QUANTIZED_ON_VALUE)
        if SELECTED_LOOP_CC_SYMBOL in cdict:
            cdict[SELECTED_LOOP_CC_SYMBOL].set_value(0)

        return

    # ── SooperLooper ABSOLUTE Engine State Helpers ────────────────────────────

    def _get_monitors_dict(self):
        """
        Return the SooperLooper engine's monitors dict (read-only feedback
        values such as per-loop 'state', as opposed to controllers_dict,
        which only holds the settable controls: mute:N, record:N, trigger:N,
        etc.). Returns None if unavailable for any reason.
        """
        try:
            return self.processor.engine.get_monitors_dict()
        except AttributeError:
            return None

    def _get_loop_state(self, loop_index):
        """
        Returns the exact SooperLooper state integer for the given loop,
        or -1 if unavailable.
        Common States: 0=Off, 2=Record, 4=Play, 5=Overdub, 10=Muted, 20=OffMuted

        NOTE: loop state is a read-only *monitor* value reported by the
        SooperLooper engine, it does NOT live in controllers_dict (that dict
        only holds settable controls like mute:N / record:N / trigger:N).
        It has to be read from processor.engine.get_monitors_dict() instead.
        """
        mdict = self._get_monitors_dict()
        if not mdict:
            return -1

        if not self._monitors_keys_logged:
            logging.debug(f"FCB1010: monitors_dict keys available: {list(mdict.keys())}")
            self._monitors_keys_logged = True

        # Confirmed on ZynthianOS 2511 / current SooperLooper engine: the key
        # format is 'state_{loop_index}' (underscore), read straight from
        # monitors_dict as a plain float, e.g. mdict['state_1'] == 4.0
        key = f"state_{loop_index}"
        if key in mdict:
            try:
                value = int(mdict[key])
            except (TypeError, ValueError):
                try:
                    value = int(mdict[key].get_value())
                except (TypeError, ValueError, AttributeError):
                    return -1
            if not self._matched_state_key:
                logging.debug(f"FCB1010: loop state key MATCHED -> '{key}' (value={value})")
                self._matched_state_key = key
            return value

        return -1

    def _is_muted(self, loop_index):
        """
        Check actual engine state machine to determine if currently muted.
        This completely eliminates 'backwards toggling' desync issues.
        """
        state_val = self._get_loop_state(loop_index)
        if state_val != -1:
            # 10 = Muted, 20 = MutePlay (Wait to Play)
            if state_val in (10, 20):
                return True
            return False
            
        # Fallback to local tracker if absolute state is somehow missing
        return self.mute_state[loop_index]

    def _selected_loop_index(self):
        """Engine index (0-based) of the currently selected loop."""
        cdict = self.processor.controllers_dict
        if LOOP_SELECTED_SYMBOL not in cdict:
            return LOOP1_INDEX
        try:
            val = int(cdict[LOOP_SELECTED_SYMBOL].get_value())
            return val - 1 if val >= 1 else val
        except (TypeError, ValueError):
            return LOOP1_INDEX

    def _stop_recording_if_active(self, loop_index):
        """
        Safely ends recording/overdubbing by checking absolute state first.
        Prevents accidentally starting an overdub on a loop that is already just playing.
        """
        state_val = self._get_loop_state(loop_index)

        # 2 = Recording, 5 = Overdubbing, 6 = Multiplying, 7 = Inserting, 8 = Replacing
        # NOTE: 4 = Playing is a STABLE, non-recording state. Toggling the
        # 'record' control here does NOT stop anything -- it STARTS a brand
        # new recording on top of the loop's existing content, since
        # _record_loop() is a blind toggle. Including 4 in this set caused
        # loops that were simply playing (e.g. right after a prior stop) to
        # be re-armed for recording unintentionally.
        if state_val in (2, 5, 6, 7, 8):
            self._record_loop(loop_index)
            logging.debug(f"FCB1010: Loop {loop_index} was active (state {state_val}), stopped it.")
        else:
            logging.debug(f"FCB1010: Loop {loop_index} is stable (state {state_val}), skipped record toggle.")

    def _set_mute(self, loop_index, muted):
        """
        Ensure the given loop ends up muted/unmuted by verifying absolute state.
        Only sends the blind toggle if the loop is verified to be in the wrong state.
        """
        cdict = self.processor.controllers_dict
        key = f"mute:{loop_index}"
        if key not in cdict:
            return

        # Use absolute engine state as the source of truth
        is_currently_muted = self._is_muted(loop_index)

        if is_currently_muted == bool(muted):
            logging.debug(f"FCB1010: _set_mute SKIP -> loop {loop_index} is already muted={muted}")
            self.mute_state[loop_index] = bool(muted) # keep fallback tracker synced
            return

        zctrl = cdict[key]
        zctrl.set_value(1)
        zctrl.send_value(True)
        self.mute_state[loop_index] = bool(muted)
        logging.debug(f"FCB1010: _set_mute OK -> toggled {key} to reach state muted={muted}")

    def _mute_only(self, loops_to_mute, loop_to_unmute):
        """Mute every loop in `loops_to_mute` and unmute `loop_to_unmute`."""
        logging.debug(f"FCB1010: _mute_only called -> mute={loops_to_mute} unmute={loop_to_unmute}")
        for idx in loops_to_mute:
            self._set_mute(idx, True)
        self._set_mute(loop_to_unmute, False)

    def _trigger_loop(self, loop_index):
        """
        Trigger playback of `loop_index` from the very beginning (loop start),
        instead of simply unmuting it wherever its playhead happens to be.
        Because `quantize` is set to QUANTIZE_LOOP_VALUE and `sync_source` is
        loop 1 (see refresh()), this trigger is quantized against loop 1's
        cycle, the same as the mute actions fired alongside it.
        """
        cdict = self.processor.controllers_dict
        key = f"trigger:{loop_index}"
        if key in cdict:
            cdict[key].set_value(1)
            cdict[key].set_value(0)
            self.mute_state[loop_index] = False  # update fallback tracker
            logging.debug(f"FCB1010: _trigger_loop OK -> triggered {key}")
        else:
            logging.warning(
                f"FCB1010: _trigger_loop FAILED -> '{key}' not found in "
                f"controllers_dict, falling back to plain unmute."
            )
            self._set_mute(loop_index, False)

    def _solo_trigger(self, loops_to_mute, loop_to_trigger):
        """
        Mute every loop in `loops_to_mute` and (re)trigger `loop_to_trigger`
        from the beginning. All actions are quantized against loop 1's cycle,
        so they land together at the same loop boundary.
        """
        logging.debug(
            f"FCB1010: _solo_trigger called -> mute={loops_to_mute} trigger={loop_to_trigger}"
        )
        for idx in loops_to_mute:
            self._set_mute(idx, True)
        self._trigger_loop(loop_to_trigger)

    def _record_loop(self, loop_index):
        """Trigger record/overdub (down+up) on the given loop."""
        cdict = self.processor.controllers_dict
        key = f"record:{loop_index}"
        if key in cdict:
            cdict[key].set_value(1)
            cdict[key].set_value(0)
            self.mute_state[loop_index] = False # update fallback tracker
            logging.debug(f"FCB1010: _record_loop OK -> toggled {key}")

    def _select_next_loop(self):
        """Explicitly calculate and select the next loop, wrapping around Loop 1."""
        current = self._selected_loop_index()
        next_idx = current + 1
        if next_idx >= NUM_LOOPS:
            next_idx = LOOP1_INDEX + 1  
            
        cdict = self.processor.controllers_dict
        if LOOP_SELECTED_SYMBOL in cdict:
            zctrl = cdict[LOOP_SELECTED_SYMBOL]
            zctrl.set_value(next_idx + 1)
            zctrl.send_value(True) 
            logging.debug(f"FCB1010: _select_next_loop OK -> selected loop {next_idx + 1}")
            
        return next_idx

    def _full_reset(self):
        """
        Soft reset triggered by CC 23:
          - Stop any active recording/overdub on every loop.
          - Mute every loop.
          - Reselect loop 1.
          - Re-sync the driver's internal tracking with the engine.
          - Re-apply the quantize/sync engine settings.
        Recorded audio content is left untouched.
        """
        logging.debug("FCB1010: CC_SOFT_RESET -> starting full soft reset")

        # Re-discover the processor and re-apply quantize/sync/mute_quantized
        # settings first, so the state read below is accurate.
        self.chain = None
        self.processor = None
        self.refresh(force=True)

        if self.processor is None:
            logging.warning("FCB1010: CC_SOFT_RESET aborted -> no SooperLooper processor found.")
            return

        # Stop any recording/overdub in progress, then mute, on every loop.
        for idx in range(NUM_LOOPS):
            self._stop_recording_if_active(idx)
            self._set_mute(idx, True)

        # Reselect loop 1.
        cdict = self.processor.controllers_dict
        if LOOP_SELECTED_SYMBOL in cdict:
            zctrl = cdict[LOOP_SELECTED_SYMBOL]
            zctrl.set_value(LOOP1_INDEX + 1)
            zctrl.send_value(True)

        # Reset the local fallback mute tracker to match reality (all muted).
        self.mute_state = [True] * NUM_LOOPS

        logging.debug("FCB1010: CC_SOFT_RESET -> completed full soft reset")
        return

    # ── MIDI event processing ─────────────────────────────────────────────────

    def midi_event(self, ev):
        """
        Dispatch MIDI events received from the FCB1010.
        Returns True  -> event consumed here.
        Returns False -> event passed through normally into Zynthian.
        """
        evtype  = (ev[0] >> 4) & 0x0F
        channel = ev[0] & 0x0F
        byte1   = ev[1] & 0x7F
        byte2   = ev[2] & 0x7F

        if evtype != 0xB or byte1 not in HANDLED_CC:
            return False

        if self.processor is None:
            return False

        if byte2 == 0:
            return True  # consume release event

        # ── CC 15 : Mute current loop (+ stop record) / Next loop / Record
        if byte1 == CC_CURRENT_MUTE_RECORD:
            loop_to_finish = self._selected_loop_index()

            if loop_to_finish == LOOP1_INDEX:
                # Loop 1: Check absolute state and only end recording if it's actually recording.
                # Bypasses the mute completely. 
                self._stop_recording_if_active(loop_to_finish)
                logging.debug("FCB1010: CC_CURRENT_MUTE_RECORD on Loop 1 -> ended recording, bypassing mute.")
            else:
                # Loops 2-5: Stop recording and mute. 
                self._stop_recording_if_active(loop_to_finish)
                self._set_mute(loop_to_finish, True)

            new_loop = self._select_next_loop()
            self._record_loop(new_loop)
            
            return True

        # ── CC 16 : Mute loops 3,4,5 / Trigger loop 2 from the beginning (quantized)
        if byte1 == CC_SOLO_LOOP2:
            self._solo_trigger(loops_to_mute=[2, 3, 4], loop_to_trigger=1)
            return True

        # ── CC 17 : Mute loops 2,4,5 / Trigger loop 3 from the beginning (quantized)
        if byte1 == CC_SOLO_LOOP3:
            self._solo_trigger(loops_to_mute=[1, 3, 4], loop_to_trigger=2)
            return True

        # ── CC 18 : Mute loops 2,3,5 / Trigger loop 4 from the beginning (quantized)
        if byte1 == CC_SOLO_LOOP4:
            self._solo_trigger(loops_to_mute=[1, 2, 4], loop_to_trigger=3)
            return True

        # ── CC 19 : Mute loops 2,3,4 / Trigger loop 5 from the beginning (quantized)
        if byte1 == CC_SOLO_LOOP5:
            self._solo_trigger(loops_to_mute=[1, 2, 3], loop_to_trigger=4)
            return True

        # ── CC 20 : Next loop
        if byte1 == CC_NEXT_LOOP:
            self._select_next_loop()
            return True

        # ── CC 21 : Mute/unmute current loop (toggle)
        if byte1 == CC_MUTE_CURRENT:
            current = self._selected_loop_index()
            currently_muted = self._is_muted(current)
            self._set_mute(current, not currently_muted)
            return True

        # ── CC 22 : Record current loop
        if byte1 == CC_RECORD_CURRENT:
            current = self._selected_loop_index()
            self._record_loop(current)
            return True

        # ── CC 23 : Soft reset — mute all, stop recording, reselect loop 1, resync
        if byte1 == CC_SOFT_RESET:
            self._full_reset()
            return True

        return False
