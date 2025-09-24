#!/usr/bin/python3
# -*- coding: utf-8 -*-
# ******************************************************************************
# ZYNTHIAN PROJECT: Zynthian Control Device Driver
#
# Zynthian Control Device Driver for "Novation Launchpad Mini MK3"
#
# Copyright (C) 2015-2025 Fernando Moyano <jofemodo@zynthian.org>
#                         Brian Walton <brian@riban.co.uk>
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
from time import sleep

# Zynthian specific modules
import zynautoconnect
from zynlibs.zynseq import zynseq
from zyncoder.zyncore import lib_zyncore
from zyngine.ctrldev.zynthian_ctrldev_base import zynthian_ctrldev_zynpad
from zyngui import zynthian_gui_config


# ------------------------------------------------------------------------------------------------------------------
# Novation Launchpad Mini MK3
# ------------------------------------------------------------------------------------------------------------------


class zynthian_ctrldev_launchpad_mini_mk3(zynthian_ctrldev_zynpad):

    dev_ids = ["Launchpad Mini MK3 IN 1"]

    STARTING_COLOUR = 21
    STOPPING_COLOUR = 5
    SELECTED_BANK_COLOUR = 29
    STOP_ALL_COLOUR = 5

    def send_sysex(self, data):
        if self.idev_out is not None:
            msg = bytes.fromhex(f"F0 00 20 29 02 0D {data} F7")
            lib_zyncore.dev_send_midi_event(self.idev_out, msg, len(msg))
            sleep(0.05)

    def get_note_xy(self, note):
        row = 8 - (note // 10)
        col = (note % 10) - 1
        return col, row

    def init(self):
        # Awake
        self.sleep_off()
        # self.send_sysex_universal_inquiry()
        # Enter DAW session mode
        self.send_sysex("10 01")
        # Select session layout (session = 0x00, faders = 0x0D)
        self.send_sysex("00 00")
        super().init()

    def end(self):
        super().end()
        # Exit DAW session mode
        self.send_sysex("10 00")
        # Select Keys layout (drums = 0x04, keys = 0x05, user = 0x06, prog = 0x7F)
        self.send_sysex("00 05")

    def update_pad_state(self, scene, chan, state=None, mode=None):
        if self.idev_out is None or scene > self.rows or (chan > self.cols and chan != zynseq.SCENE_CHANNEL):
            return
        try:
            info = self.zynseq.launcher_info[scene][chan]
        except:
            info = None
        try:
            if info:
                try:
                    empty = info["empty"]
                except:
                    empty = 1
                if state is None or mode is None:
                    state = info["state"]
                    mode = info["mode"]
            else:
                empty = 1
            #logging.debug(f"Scene {scene}, Slot {chan} => state={state}, mode={mode}, empty={empty}")
            if info is None or (chan < zynseq.SCENE_CHANNEL and (empty or mode == 0)):
                midi_chan = 0
                color = 0
            elif state == zynseq.SEQ_STOPPED:
                midi_chan = 0
                if chan == zynseq.SCENE_CHANNEL:
                    color = 0
                else:
                    color = zynthian_gui_config.LAUNCHER_COLOUR[chan]["launchpad"]
            elif state in (zynseq.SEQ_PLAYING, zynseq.SEQ_CHILD_PLAYING):
                if chan == zynseq.SCENE_CHANNEL:
                    midi_chan = 0
                    color = zynthian_gui_config.LAUNCHER_STARTING_COLOUR["launchpad"]
                else:
                    midi_chan = 2
                    color = zynthian_gui_config.LAUNCHER_COLOUR[chan]["launchpad"]
            elif state in (zynseq.SEQ_STOPPING, zynseq.SEQ_STOPPING_SYNC, zynseq.SEQ_FORCED_STOP, zynseq.SEQ_CHILD_STOPPING):
                midi_chan = 1
                color = zynthian_gui_config.LAUNCHER_STOPPING_COLOUR["launchpad"]
            elif state == zynseq.SEQ_STARTING:
                midi_chan = 1
                color = zynthian_gui_config.LAUNCHER_STARTING_COLOUR["launchpad"]
            else:
                midi_chan = 0
                color = 0
        except Exception as e:
            logging.error(e)
            midi_chan = 0
            color = 0
        # Send MIDI event to controller
        if chan < zynseq.SCENE_CHANNEL:
            note = 10 * (8 - scene) + chan + 1
            lib_zyncore.dev_send_note_on(self.idev_out, midi_chan, note, color)
        elif chan == zynseq.SCENE_CHANNEL:
            ccnum = 89 - 10 * scene
            lib_zyncore.dev_send_ccontrol_change(self.idev_out, max(midi_chan, 1), ccnum, color)

    # Light-Off the pad specified with chan & scene (column & row)
    def pad_off(self, col, row):
        if col < zynseq.SCENE_CHANNEL:
            note = 10 * (8 - row) + col + 1
            lib_zyncore.dev_send_note_on(self.idev_out, 0, note, 0)
        elif col == zynseq.SCENE_CHANNEL:
            ccnum = 89 - 10 * row
            lib_zyncore.dev_send_ccontrol_change(self.idev_out, 0, ccnum, 0)

    def midi_event(self, ev):
        # logging.debug(f"Launchpad MINI MK3 MIDI handler => {ev}")
        evtype = (ev[0] >> 4) & 0x0F
        # Note ON => launch/stop sequence
        if evtype == 0x9:
            note = ev[1] & 0x7F
            vel = ev[2] & 0x7F
            if vel > 0:
                col, row = self.get_note_xy(note)       #  scene=row
                try:
                    info = self.zynseq.launcher_info[row][col]
                    if info:
                        logging.debug(f"PAD ({row}, {col}) INFO => {info}")
                        self.zynseq.libseq.togglePlayState(row, col)
                except:
                    pass
            return True
        # CC => arrows, scene change, stop all
        elif evtype == 0xB:
            ccnum = ev[1] & 0x7F
            ccval = ev[2] & 0x7F
            if ccval > 0:
                if ccnum == 0x5B:
                    self.state_manager.send_cuia("ARROW_UP")
                elif ccnum == 0x5C:
                    self.state_manager.send_cuia("ARROW_DOWN")
                elif ccnum == 0x5D:
                    self.state_manager.send_cuia("ARROW_LEFT")
                elif ccnum == 0x5E:
                    self.state_manager.send_cuia("ARROW_RIGHT")
                else:
                    col, row = self.get_note_xy(ccnum)
                    if col == 8:
                        info = self.zynseq.launcher_info[row][zynseq.SCENE_CHANNEL]
                        logging.debug(f"SCENE PAD ({row})!!")
                        if info:
                            logging.debug(f"SCENE ({row}) INFO => {info}")
                            self.zynseq.libseq.togglePlayState(row, zynseq.SCENE_CHANNEL)
            return True
        # SysEx
        elif ev[0] == 0xF0:
            logging.info(f"Received SysEx => {ev.hex(' ')}")
            return True

    # Light-Off LEDs
    def light_off(self):
        # logging.debug("Lighting Off LEDs Launchpad MINI MK3")
        # Clean state of notes & CCs
        self.send_sysex("12 01 00 01")

    # Sleep On
    def sleep_on(self):
        # Sleep Mode (0 = sleep, 1 = awake)
        self.send_sysex("09 00")

    # Sleep On
    def sleep_off(self):
        # Sleep Mode (0 = sleep, 1 = awake)
        self.send_sysex("09 01")

# ------------------------------------------------------------------------------
