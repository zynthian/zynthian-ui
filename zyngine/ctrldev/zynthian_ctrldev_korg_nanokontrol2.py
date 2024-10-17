#!/usr/bin/python3
# -*- coding: utf-8 -*-
# ******************************************************************************
# ZYNTHIAN PROJECT: Zynthian Control Device Driver
#
# Zynthian Control Device Driver for "Korg nanoKontrol-2"
#
# Copyright (C) 2024 Fernando Moyano <jofemodo@zynthian.org>
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
from zyncoder.zyncore import lib_zyncore
from zyngine.zynthian_signal_manager import zynsigman
from zyngine.ctrldev.zynthian_ctrldev_base import zynthian_ctrldev_zynmixer

# --------------------------------------------------------------------------
# Korg nanoKontrol-2 Integration
# --------------------------------------------------------------------------


class zynthian_ctrldev_korg_nanokontrol2(zynthian_ctrldev_zynmixer):

    dev_ids = ["nanoKONTROL2 IN 1"]

    midi_chan = 0x0
    sysex_answer_cb = None

    rec_mode = 0
    shift = False

    cycle_ccnum = 46
    track_left_ccnum = 58
    track_right_ccnum = 59
    marker_set_ccnum = 60
    marker_left_ccnum = 61
    marker_right_ccnum = 62
    transport_frwd_ccnum = 43
    transport_ffwd_ccnum = 44
    transport_stop_ccnum = 42
    transport_play_ccnum = 41
    transport_rec_ccnum = 45

    solo_ccnums = [32, 33, 34, 35, 36, 37, 38, 39]
    mute_ccnums = [48, 49, 50, 51, 52, 53, 54, 55]
    rec_ccnums = [64, 65, 66, 67, 68, 69, 70, 71]
    knobs_ccnum = [16, 17, 18, 19, 20, 21, 22, 23]
    faders_ccnum = [0, 1, 2, 3, 4, 5, 6, 7]

    # Function to initialise class
    def __init__(self, state_manager, idev_in, idev_out=None):
        self.midimix_bank = 0
        super().__init__(state_manager, idev_in, idev_out)

    def send_sysex(self, data):
        if self.idev_out is not None:
            msg = bytes.fromhex(
                f"F0 42 4{hex(self.midi_chan)[2:]} 00 01 13 00 {data} F7")
            lib_zyncore.dev_send_midi_event(self.idev_out, msg, len(msg))

    def korg_sysex_midi2data(self, midi):
        data = bytearray()
        pos = 0
        while True:
            bitsbyte = midi[pos]
            for i in range(0, 7):
                b7 = (bitsbyte >> i) & 0x1
                byte = midi[pos + 1 + i] | (b7 << 7)
                data.append(byte)
            pos += 8
            if pos > len(midi) - 7:
                break
        while len(data) < 339:
            data.append(0)
        return data

    def korg_sysex_data2midi(self, data):
        midi = bytearray()
        pos = 0
        while True:
            bitsbyte = 0x0
            for i in range(0, 7):
                bitsbyte |= (data[pos + i] >> 7) << i
            midi.append(bitsbyte)
            for i in range(0, 7):
                midi.append(data[pos + i] & 0x7F)
            pos += 7
            if pos > len(data) - 6:
                break
        while len(midi) < 388:
            midi.append(0)
        return midi

    def set_mode_led_external(self):
        # Send Scene Data Dump Request
        self.sysex_answer_cb = self.cb_set_mode_led_external
        self.send_sysex("1F 10 00")

    def cb_set_mode_led_external(self, sysex_answer):
        self.sysex_answer_cb = None
        # Toggle led mode in Scene data
        scene_data = self.korg_sysex_midi2data(sysex_answer[13:-1])
        scene_data[2] = 0x1
        logging.debug(f"SCENE DATA MODIFIED: {scene_data.hex(' ')}")
        # Send back modified scene data
        midi_data = self.korg_sysex_data2midi(scene_data)
        self.sysex_answer_cb = self.cb_sysex_ack
        self.send_sysex(f"7F 7F 02 03 05 40 {midi_data.hex(' ')}")

    def cb_sysex_ack(self, sysex_answer):
        self.sysex_answer_cb = None
        if sysex_answer[8] == 0x23:
            logging.debug("Received SysEx ACK. Data Load operation success.")
        elif sysex_answer[8] == 0x24:
            logging.error("Received SysEx NAK. Data Load operation failed.")
        else:
            logging.error(f"Unknown SysEx response => {sysex_answer.hex(' ')}")

    def init(self):
        # Enable LED control
        self.set_mode_led_external()
        # Register signals
        zynsigman.register_queued(
            zynsigman.S_AUDIO_PLAYER, self.state_manager.SS_AUDIO_PLAYER_STATE, self.refresh_audio_transport)
        zynsigman.register_queued(
            zynsigman.S_AUDIO_RECORDER, self.state_manager.SS_AUDIO_RECORDER_STATE, self.refresh_audio_transport)
        zynsigman.register_queued(
            zynsigman.S_STATE_MAN, self.state_manager.SS_MIDI_PLAYER_STATE, self.refresh_midi_transport)
        zynsigman.register_queued(
            zynsigman.S_STATE_MAN, self.state_manager.SS_MIDI_RECORDER_STATE, self.refresh_midi_transport)
        super().init()

    def end(self):
        super().end()
        # Unregister signals
        zynsigman.unregister(zynsigman.S_AUDIO_PLAYER,
                             self.state_manager.SS_AUDIO_PLAYER_STATE, self.refresh_audio_transport)
        zynsigman.unregister(zynsigman.S_AUDIO_RECORDER,
                             self.state_manager.SS_AUDIO_RECORDER_STATE, self.refresh_audio_transport)
        zynsigman.unregister(
            zynsigman.S_STATE_MAN, self.state_manager.SS_MIDI_PLAYER_STATE, self.refresh_midi_transport)
        zynsigman.unregister(
            zynsigman.S_STATE_MAN, self.state_manager.SS_MIDI_RECORDER_STATE, self.refresh_midi_transport)

    def refresh_audio_transport(self, **kwargs):
        if self.shift:
            return
        # REC Button
        if self.state_manager.audio_recorder.rec_proc:
            lib_zyncore.dev_send_ccontrol_change(
                self.idev_out, self.midi_chan, self.transport_rec_ccnum, 0x7F)
        else:
            lib_zyncore.dev_send_ccontrol_change(
                self.idev_out, self.midi_chan, self.transport_rec_ccnum, 0)
        # STOP button
        lib_zyncore.dev_send_ccontrol_change(
            self.idev_out, self.midi_chan, self.transport_stop_ccnum, 0)
        # PLAY button:
        if self.state_manager.status_audio_player:
            lib_zyncore.dev_send_ccontrol_change(
                self.idev_out, self.midi_chan, self.transport_play_ccnum, 0x7F)
        else:
            lib_zyncore.dev_send_ccontrol_change(
                self.idev_out, self.midi_chan, self.transport_play_ccnum, 0)

    def refresh_midi_transport(self, **kwargs):
        if not self.shift:
            return
        # REC Button
        if self.state_manager.status_midi_recorder:
            lib_zyncore.dev_send_ccontrol_change(
                self.idev_out, self.midi_chan, self.transport_rec_ccnum, 0x7F)
        else:
            lib_zyncore.dev_send_ccontrol_change(
                self.idev_out, self.midi_chan, self.transport_rec_ccnum, 0)
        # STOP button
        lib_zyncore.dev_send_ccontrol_change(
            self.idev_out, self.midi_chan, self.transport_stop_ccnum, 0)
        # PLAY button:
        if self.state_manager.status_midi_player:
            lib_zyncore.dev_send_ccontrol_change(
                self.idev_out, self.midi_chan, self.transport_play_ccnum, 0x7F)
        else:
            lib_zyncore.dev_send_ccontrol_change(
                self.idev_out, self.midi_chan, self.transport_play_ccnum, 0)

    # Update LED status for a single strip
    def update_mixer_strip(self, chan, symbol, value):
        if self.idev_out is None:
            return
        chain_id = self.chain_manager.get_chain_id_by_mixer_chan(chan)
        if chain_id:
            col = self.chain_manager.get_chain_index(chain_id)
            if self.midimix_bank:
                col -= 8
            if 0 <= col < 8:
                if symbol == "mute":
                    lib_zyncore.dev_send_ccontrol_change(
                        self.idev_out, self.midi_chan, self.mute_ccnums[col], value * 0x7F)
                elif symbol == "solo":
                    lib_zyncore.dev_send_ccontrol_change(
                        self.idev_out, self.midi_chan, self.solo_ccnums[col], value * 0x7F)
                elif symbol == "rec" and self.rec_mode:
                    lib_zyncore.dev_send_ccontrol_change(
                        self.idev_out, self.midi_chan, self.rec_ccnums[col], value * 0x7F)

    # Update LED status for active chain
    def update_mixer_active_chain(self, active_chain):
        if self.rec_mode:
            return
        if self.midimix_bank:
            col0 = 8
        else:
            col0 = 0
        for i in range(0, 8):
            chain_id = self.chain_manager.get_chain_id_by_index(col0 + i)
            if chain_id and chain_id == active_chain:
                rec = 0x7F
            else:
                rec = 0
            lib_zyncore.dev_send_ccontrol_change(
                self.idev_out, self.midi_chan, self.rec_ccnums[i], rec)

    # Update full LED status
    def refresh(self):
        if self.idev_out is None:
            return

        # Bank selection LED
        if self.midimix_bank:
            col0 = 8
            lib_zyncore.dev_send_ccontrol_change(
                self.idev_out, self.midi_chan, self.transport_frwd_ccnum, 0)
            lib_zyncore.dev_send_ccontrol_change(
                self.idev_out, self.midi_chan, self.transport_ffwd_ccnum, 0x7F)
        else:
            col0 = 0
            lib_zyncore.dev_send_ccontrol_change(
                self.idev_out, self.midi_chan, self.transport_frwd_ccnum, 0x7F)
            lib_zyncore.dev_send_ccontrol_change(
                self.idev_out, self.midi_chan, self.transport_ffwd_ccnum, 0)

        if self.shift:
            lib_zyncore.dev_send_ccontrol_change(
                self.idev_out, self.midi_chan, self.cycle_ccnum, 0x7F)
            self.refresh_midi_transport()
        else:
            lib_zyncore.dev_send_ccontrol_change(
                self.idev_out, self.midi_chan, self.cycle_ccnum, 0)
            self.refresh_audio_transport()

        # Strips Leds
        for i in range(0, 8):
            chain = self.chain_manager.get_chain_by_index(col0 + i)

            if chain and chain.mixer_chan is not None:
                mute = self.zynmixer.get_mute(chain.mixer_chan) * 0x7F
                solo = self.zynmixer.get_solo(chain.mixer_chan) * 0x7F
            else:
                chain = None
                mute = 0
                solo = 0

            if not self.rec_mode:
                if chain and chain == self.chain_manager.get_active_chain():
                    rec = 0x7F
                else:
                    rec = 0
            else:
                if chain and chain.mixer_chan is not None:
                    rec = self.state_manager.audio_recorder.is_armed(
                        chain.mixer_chan) * 0x7F
                else:
                    rec = 0

            lib_zyncore.dev_send_ccontrol_change(
                self.idev_out, self.midi_chan, self.mute_ccnums[i], mute)
            lib_zyncore.dev_send_ccontrol_change(
                self.idev_out, self.midi_chan, self.solo_ccnums[i], solo)
            lib_zyncore.dev_send_ccontrol_change(
                self.idev_out, self.midi_chan, self.rec_ccnums[i], rec)

    def get_mixer_chan_from_device_col(self, col):
        if self.midimix_bank:
            col += 8
        chain = self.chain_manager.get_chain_by_index(col)
        if chain:
            return chain.mixer_chan
        else:
            return None

    def midi_event(self, ev):
        evtype = (ev[0] >> 4) & 0x0F
        if evtype == 0xB:
            ccnum = ev[1] & 0x7F
            ccval = ev[2] & 0x7F

            if ccnum == self.track_left_ccnum:
                if ccval > 0:
                    self.state_manager.send_cuia("ARROW_LEFT")
                    self.refresh()
                return True
            elif ccnum == self.track_right_ccnum:
                if ccval > 0:
                    self.state_manager.send_cuia("ARROW_RIGHT")
                    self.refresh()
                return True
            elif ccnum == self.cycle_ccnum:
                if ccval > 0:
                    self.shift = not self.shift
                    self.rec_mode = self.shift
                    self.refresh()
                return True
            elif ccnum == self.marker_left_ccnum:
                if ccval > 0:
                    self.state_manager.send_cuia("ARROW_UP")
                    self.refresh()
                return True
            elif ccnum == self.marker_right_ccnum:
                if ccval > 0:
                    self.state_manager.send_cuia("ARROW_DOWN")
                    self.refresh()
                return True
            elif ccnum == self.marker_set_ccnum:
                if ccval > 0:
                    self.state_manager.send_cuia("ZYNSWITCH", [3, "P"])
                else:
                    self.state_manager.send_cuia("ZYNSWITCH", [3, "R"])
                self.refresh()
                return True
            elif ccnum == self.transport_frwd_ccnum:
                if ccval > 0:
                    if self.midimix_bank == 0:
                        self.state_manager.send_cuia("BACK")
                    else:
                        self.midimix_bank = 0
                    self.refresh()
                return True
            elif ccnum == self.transport_ffwd_ccnum:
                if ccval > 0:
                    self.midimix_bank = 1
                    self.refresh()
                return True
            elif ccnum == self.transport_play_ccnum:
                if ccval > 0:
                    if self.shift:
                        self.state_manager.send_cuia("TOGGLE_MIDI_PLAY")
                    else:
                        self.state_manager.send_cuia("TOGGLE_AUDIO_PLAY")
                return True
            elif ccnum == self.transport_rec_ccnum:
                if ccval > 0:
                    if self.shift:
                        self.state_manager.send_cuia("TOGGLE_MIDI_RECORD")
                    else:
                        self.state_manager.send_cuia("TOGGLE_AUDIO_RECORD")
                return True
            elif ccnum == self.transport_stop_ccnum:
                if ccval > 0:
                    if self.shift:
                        self.state_manager.send_cuia("STOP_MIDI_PLAY")
                    else:
                        self.state_manager.send_cuia("STOP_AUDIO_PLAY")
                return True
            elif ccnum in self.mute_ccnums:
                if ccval > 0:
                    col = self.mute_ccnums.index(ccnum)
                    if self.shift and col == 7:
                        mixer_chan = 255
                    else:
                        mixer_chan = self.get_mixer_chan_from_device_col(col)
                    if mixer_chan is not None:
                        if self.zynmixer.get_mute(mixer_chan):
                            val = 0
                        else:
                            val = 1
                        self.zynmixer.set_mute(mixer_chan, val, True)
                        # Send LED feedback
                        if self.idev_out is not None:
                            lib_zyncore.dev_send_ccontrol_change(
                                self.idev_out, self.midi_chan, ccnum, val * 0x7F)
                    elif self.idev_out is not None:
                        # If not associated mixer channel, turn-off the led
                        lib_zyncore.dev_send_ccontrol_change(
                            self.idev_out, self.midi_chan, ccnum, 0)
                return True
            elif ccnum in self.solo_ccnums:
                if ccval > 0:
                    col = self.solo_ccnums.index(ccnum)
                    if self.shift and col == 7:
                        mixer_chan = 255
                    else:
                        mixer_chan = self.get_mixer_chan_from_device_col(col)
                    if mixer_chan is not None:
                        if self.zynmixer.get_solo(mixer_chan):
                            val = 0
                        else:
                            val = 1
                        self.zynmixer.set_solo(mixer_chan, val, True)
                        # Send LED feedback
                        if self.idev_out is not None:
                            lib_zyncore.dev_send_ccontrol_change(
                                self.idev_out, self.midi_chan, ccnum, val * 0x7F)
                    elif self.idev_out is not None:
                        # If not associated mixer channel, turn-off the led
                        lib_zyncore.dev_send_ccontrol_change(
                            self.idev_out, self.midi_chan, ccnum, 0)
                return True
            elif ccnum in self.rec_ccnums:
                if ccval > 0:
                    col = self.rec_ccnums.index(ccnum)
                    if not self.rec_mode:
                        if self.midimix_bank:
                            col += 8
                        self.chain_manager.set_active_chain_by_index(col)
                        self.refresh()
                    else:
                        mixer_chan = self.get_mixer_chan_from_device_col(col)
                        if mixer_chan is not None:
                            self.state_manager.audio_recorder.toggle_arm(
                                mixer_chan)
                            # Send LED feedback
                            if self.idev_out is not None:
                                val = self.state_manager.audio_recorder.is_armed(
                                    mixer_chan) * 0x7F
                                lib_zyncore.dev_send_ccontrol_change(
                                    self.idev_out, self.midi_chan, ccnum, val)
                        elif self.idev_out is not None:
                            # If not associated mixer channel, turn-off the led
                            lib_zyncore.dev_send_ccontrol_change(
                                self.idev_out, self.midi_chan, ccnum, 0)
                return True
            # elif ccnum == self.master_ccnum:
            # self.zynmixer.set_level(255, ccval / 127.0)
            # return True
            elif ccnum in self.faders_ccnum:
                col = self.faders_ccnum.index(ccnum)
                # With "shift" ...
                if self.shift and col == 7:
                    # use last fader to control Main volume (right)
                    self.zynmixer.set_level(255, ccval / 127.0)
                # else, use faders to control chain's volume
                else:
                    mixer_chan = self.get_mixer_chan_from_device_col(col)
                    if mixer_chan is not None:
                        self.zynmixer.set_level(
                            mixer_chan, ccval / 127.0, True)
                return True
            elif ccnum in self.knobs_ccnum:
                col = self.knobs_ccnum.index(ccnum)
                # With "shift" ...
                if self.shift:
                    # use last knob to control Main balance
                    if col == 7:
                        self.zynmixer.set_balance(
                            255, 2.0 * ccval / 127.0 - 1.0)
                    # pass rest of knob's CC to engine control (MIDI-learn)
                    else:
                        return False
                # else, use knobs to control chain's balance
                else:
                    mixer_chan = self.get_mixer_chan_from_device_col(col)
                    if mixer_chan is not None:
                        self.zynmixer.set_balance(
                            mixer_chan, 2.0 * ccval/127.0 - 1.0)
                return True
        # SysEx
        elif ev[0] == 0xF0:
            if callable(self.sysex_answer_cb):
                self.sysex_answer_cb(ev)
            else:
                logging.debug(f"Received SysEx (unprocessed) => {ev.hex(' ')}")
            return True

    # Light-Off all LEDs
    def light_off(self):
        if self.idev_out is None:
            return

        for ccnum in self.mute_ccnums:
            lib_zyncore.dev_send_ccontrol_change(
                self.idev_out, self.midi_chan, ccnum, 0)
        for ccnum in self.solo_ccnums:
            lib_zyncore.dev_send_ccontrol_change(
                self.idev_out, self.midi_chan, ccnum, 0)
        for ccnum in self.rec_ccnums:
            lib_zyncore.dev_send_ccontrol_change(
                self.idev_out, self.midi_chan, ccnum, 0)
        for ccnum in [41, 42, 43, 44, 45, 46, 58, 59, 60, 61, 62]:
            lib_zyncore.dev_send_ccontrol_change(
                self.idev_out, self.midi_chan, ccnum, 0)

# ------------------------------------------------------------------------------
