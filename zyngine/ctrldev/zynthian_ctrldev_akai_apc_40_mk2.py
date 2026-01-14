#!/usr/bin/python3
# -*- coding: utf-8 -*-
# ******************************************************************************
# ZYNTHIAN PROJECT: Zynthian Control Device Driver
#
# Zynthian Control Device Driver for "Akai APC 40 mk2"
#
# Copyright (C) 2025 Brian Walton <riban@zynthian.org>
# API: https://cdn.inmusicbrands.com/akai/attachments/apc40II/APC40Mk2_Communications_Protocol_v1.2.pdf
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
from time import monotonic, sleep

# Zynthian specific modules
from zyngine.ctrldev.zynthian_ctrldev_base import *
from zyncoder.zyncore import lib_zyncore
from zynlibs.zynseq import zynseq
from zyngui import zynthian_gui_config
from zyngine.zynthian_chain_manager import MAX_NUM_MIDI_CHANS
from zyngine.zynthian_signal_manager import zynsigman
from zyngine.zynthian_audio_recorder import zynthian_audio_recorder
from zyngine.zynthian_engine_audioplayer import zynthian_engine_audioplayer

BOLD_PRESS_TIME = 0.4

ENC_MODE_PAN    = 0
ENC_MODE_SENDS  = 1
ENC_MODE_USER   = 2

LED_CLIP_LAUNCH     = 0x00  # First clip launcher RGB LED (0x00-0x27)
LED_RECORD_ARM      = 0x30  # Record arm LED (Tracks: MIDI channel 0-7. 0=off, 1-127=Rred)
LED_SOLO            = 0x31  # Solo LED (Tracks: MIDI channel 0-7. 0=off, 1-127=blue)
LED_ACTIVATOR       = 0x32  # Activator LED (Tracks: MIDI channel 0-7. 0=off, 1-127=orange)
LED_TRACK_SEL       = 0x33  # Track select LED (Tracks: MIDI channel 0-7. 0=off, 1-127=orange)
LED_CLIP_STOP       = 0x34  # Clip stop LED (Tracks: MIDI channel 0-7. 0=off, 1=on, 2=flashing, 3-127=on)
LED_DEVICE_LEFT     = 0x3A  # Device left LED (Tracks: MIDI channel 0-8. 0=off, 1-127=on)
LED_DEVICE_RIGHT    = 0x3B  # Device right LED (Tracks: MIDI channel 0-8. 0=off, 1-127=on)
LED_BANK_LEFT       = 0x3C  # Bank left LED (Tracks: MIDI channel 0-8. 0=off, 1-127=on)
LED_BANK_RIGHT      = 0x3D  # Bank right LED (Tracks: MIDI channel 0-8. 0=off, 1-127=on)
LED_DEVICE_ON       = 0x3E  # Device on/off LED (Tracks: MIDI channel 0-8. 0=off, 1-127=on)
LED_DEVICE_LOCK     = 0x3F  # Device lock LED (Tracks: MIDI channel 0-8. 0=off, 1-127=on)
LED_DEVICE_VIEW     = 0x40  # Clip/dev. view LED (Tracks: MIDI channel 0-8. 0=off, 1-127=on)
LED_DETAIL_VIEW     = 0x41  # Detail view LED (Tracks: MIDI channel 0-8. 0=off, 1-127=on)
LED_CROSSOVER_AB    = 0x42  # (Track: MIDI channel 0-7. 0=off, 1=Yellow, 2-127=Orange) NO LED ON DEVICE!
LED_MASTER          = 0x50  # Master LED (0=off, 1-127=on)
LED_SCENE_LAUNCH_1  = 0x52  # Launch scene 1 RGB LED
LED_SCENE_LAUNCH_2  = 0x53  # Launch scene 2 RGB LED
LED_SCENE_LAUNCH_3  = 0x54  # Launch scene 3 RGB LED
LED_SCENE_LAUNCH_4  = 0x55  # Launch scene 4 RGB LED
LED_SCENE_LAUNCH_5  = 0x56  # Launch scene 5 RGB LED
LED_PAN             = 0x57  # Pan LED (0=off, 1-127=on)
LED_SENDS           = 0x58  # Sends LED (0=off, 1-127=on)
LED_USER            = 0x59  # User LED (0=off, 1-127=on)
LED_METRONOME       = 0x5A  # Metronome LED (0=off, 1-127=on)
LED_PLAY            = 0x5B  # Play LED (0=off, 1-127=on)
LED_STOP            = 0x5C  # STOP LED (0=off, 1-127=on)
LED_RECORD          = 0x5D  # Record LED (0=off, 1-127=on)

BTN_STOP_ALL_CLIPS  = 0x51  # Stop all clips
BTN_UP              = 0x5E  # Up button
BTN_DOWN            = 0x5F  # Down button
BTN_RIGHT           = 0x60  # Right button
BTN_LEFT            = 0x61  # Left button
BTN_SHIFT           = 0x62  # Shift button
BTN_TAP_TEMPO       = 0x63  # Tap tempo button
BTN_NUDGE_DOWN      = 0x64  # Nudge - button
BTN_NUDGE_UP        = 0x65  # Nudge + button
BTN_SESSION         = 0x66  # Session record button
BTN_BANK            = 0x67  # Bank button

CC_FADER            = 0x07  # Fader slider (Tracks: MIDI channel 0-7)
CC_TEMPO            = 0x0D  # Tempo knob (Relative)
CC_MAIN_FADER       = 0x0E  # Main fader slider
CC_CROSS_FADER      = 0x0F  # A/B cross fader
CC_DEVICE_1         = 0x10  # Device control knob (Tracks: MIDI channel 0-7)
CC_DEVICE_2         = 0x11  # Device control knob (Tracks: MIDI channel 0-7)
CC_DEVICE_3         = 0x12  # Device control knob (Tracks: MIDI channel 0-7)
CC_DEVICE_4         = 0x13  # Device control knob (Tracks: MIDI channel 0-7)
CC_DEVICE_5         = 0x14  # Device control knob (Tracks: MIDI channel 0-7)
CC_DEVICE_6         = 0x15  # Device control knob (Tracks: MIDI channel 0-7)
CC_DEVICE_7         = 0x16  # Device control knob (Tracks: MIDI channel 0-7)
CC_DEVICE_8         = 0x17  # Device control knob (Tracks: MIDI channel 0-7)
CC_LED_RING_1       = 0x18  # LED ring type (Tracks: MIDI channel 0-7)
CC_LED_RING_2       = 0x19  # LED ring type (Tracks: MIDI channel 0-7)
CC_LED_RING_3       = 0x1A  # LED ring type (Tracks: MIDI channel 0-7)
CC_LED_RING_4       = 0x1B  # LED ring type (Tracks: MIDI channel 0-7)
CC_LED_RING_5       = 0x1C  # LED ring type (Tracks: MIDI channel 0-7)
CC_LED_RING_6       = 0x1D  # LED ring type (Tracks: MIDI channel 0-7)
CC_LED_RING_7       = 0x1E  # LED ring type (Tracks: MIDI channel 0-7)
CC_LED_RING_8       = 0x1F  # LED ring type (Tracks: MIDI channel 0-7)
CC_CUE_LEVEL        = 0x2F  # Cue level knob
CC_TRACK_1          = 0x30  # Track encoder knob
CC_TRACK_2          = 0x31  # Track encoder knob
CC_TRACK_3          = 0x32  # Track encoder knob
CC_TRACK_4          = 0x33  # Track encoder knob
CC_TRACK_5          = 0x34  # Track encoder knob
CC_TRACK_6          = 0x35  # Track encoder knob
CC_TRACK_7          = 0x36  # Track encoder knob
CC_TRACK_8          = 0x37  # Track encoder knob
CC_TRACK_LED_RING_1 = 0x38  # Track encoder LED ring type
CC_TRACK_LED_RING_2 = 0x39  # Track encoder LED ring type
CC_TRACK_LED_RING_3 = 0x3A  # Track encoder LED ring type
CC_TRACK_LED_RING_4 = 0x3B  # Track encoder LED ring type
CC_TRACK_LED_RING_5 = 0x3C  # Track encoder LED ring type
CC_TRACK_LED_RING_6 = 0x3D  # Track encoder LED ring type
CC_TRACK_LED_RING_7 = 0x3E  # Track encoder LED ring type
CC_TRACK_LED_RING_8 = 0x3F  # Track encoder LED ring type
CC_FOOTSWITCH       = 0x40  # External foot switch

# MIDI channels set mode of RGB buttons
RGB_MODE_PRIMARY    = 0x00  # Show RGB LED primary colour
RGB_MODE_ONE_SHOT_24= 0x01 # Show RGB LED secondary colour - oneshot 1/24
RGB_MODE_ONE_SHOT_16= 0x02 # Show RGB LED secondary colour - oneshot 1/16
RGB_MODE_ONE_SHOT_8 = 0x03  # Show RGB LED secondary colour - oneshot 1/8
RGB_MODE_ONE_SHOT_4 = 0x04  # Show RGB LED secondary colour - oneshot 1/4
RGB_MODE_ONE_SHOT_2 = 0x05  # Show RGB LED secondary colour - oneshot 1/2
RGB_MODE_PULSE_24   = 0x06  # Show RGB LED secondary colour - pulsing 1/24
RGB_MODE_PULSE_16   = 0x07  # Show RGB LED secondary colour - pulsing 1/24
RGB_MODE_PULSE_8    = 0x08  # Show RGB LED secondary colour - pulsing 1/24
RGB_MODE_PULSE_4    = 0x09  # Show RGB LED secondary colour - pulsing 1/24
RGB_MODE_PULSE_2    = 0x0A  # Show RGB LED secondary colour - pulsing 1/24
RGB_MODE_BLINK_24   = 0x0B  # Show RGB LED secondary colour - blinking 1/24
RGB_MODE_BLINK_16   = 0x0C  # Show RGB LED secondary colour - blinking 1/24
RGB_MODE_BLINK_8    = 0x0D  # Show RGB LED secondary colour - blinking 1/24
RGB_MODE_BLINK_4    = 0x0E  # Show RGB LED secondary colour - blinking 1/24
RGB_MODE_BLINK_2    = 0x0F  # Show RGB LED secondary colour - blinking 1/24

# LED ring types
LED_RING_TYPE_OFF   = 0x00  # Off
LED_RING_TYPE_SINGLE= 0x01  # Single ring
LED_RING_TYPE_VOLUME= 0x02  # Volume style
LED_RING_TYPE_PAN   = 0x03  # Pan style


class zynthian_ctrldev_akai_apc_40_mk2(zynthian_ctrldev_zynpad, zynthian_ctrldev_zynmixer):

    dev_ids = ["APC40 mkII IN 1"]
    driver_name = "APC40 mk2"
    driver_description = "Interface Akai APC40 with mixer, launcher and more..."

    # Function to initialise class
    def __init__(self, state_manager, idev_in, idev_out=None):
        super().__init__(state_manager, idev_in, idev_out)
        self.cols = 8
        self.rows = 5

        self.sysex_manufacturer_id = None
        self.sysex_product_model_id = None
        self.sysex_dev_id = None
        self._shift = False  # True whilst shift button is pressed
        self._send = False  # True whilst send button is pressed
        self.send = 0  # Index of send to adjust
        self._user = False  # True whilst user button is pressed
        self.user = 0  # Index of (fav) chain controller to adjust
        self.enc_mode = ENC_MODE_PAN  # Chain encoder mode
        self.last_cc_send = 0  # Time of last sent feedback CC - used to avoid feedback interference
        self.mixer_toggle = False
        self.last_press = None
        self.ccnum2zctrls = {}

    # Send the SysEx universal device enquiry
    def send_sysex_universal_device_enquiry(self, chan=0):
        self.sysex_dev_id = None
        msg = bytes.fromhex(f"F0 7E {chan:02x} 06 01 F7")
        logging.debug("SYSEX UNIVERSAL DEVICE ENQUIRY: " + msg.hex(" "))
        lib_zyncore.dev_send_midi_event(self.idev_out, msg, len(msg))

    def send_sysex(self, msg_id, data):
        if self.idev_out is not None and self.sysex_dev_id is not None:
            size = len(data)
            header_data = bytes([self.sysex_manufacturer_id, self.sysex_dev_id, self.sysex_product_model_id, msg_id])
            msg = bytes.fromhex(f"F0 {header_data.hex(' ')} {size//0xFF:02x} {size%0xFF:02x} {data.hex(' ')} F7")
            logging.debug("SYSEX MESSAGE: " + msg.hex(" "))
            lib_zyncore.dev_send_midi_event(self.idev_out, msg, len(msg))

    def send_sysex_set_mode(self, mode):
        self.send_sysex(0x60, bytes([mode, 1, 1, 1]))

    def init(self):
        self.send_sysex_universal_device_enquiry(0)
        sleep(0.05)
        self.last_press = None  # Time of last button press used for (simple single-button) bold press detection
        self.mixer_toggle = False
        self.set_scroll_mode(SCROLL_MODE_GUI_SEL)
        self.refresh()
        self.on_active_chain()
        self.set_enc_mode()
        super().init()
        zynsigman.register_queued(zynsigman.S_AUDIO_RECORDER, zynthian_audio_recorder.SS_AUDIO_RECORDER_STATE, self.on_audio_rec)
        zynsigman.register_queued(zynsigman.S_AUDIO_PLAYER, zynthian_engine_audioplayer.SS_AUDIO_PLAYER_STATE, self.on_audio_play)
        zynsigman.register_queued(zynsigman.S_STEPSEQ, zynseq.SS_SEQ_METRO, self.on_metronome)
        zynsigman.register_queued(zynsigman.S_GUI, zynsigman.SS_GUI_SHOW_SCREEN, self.on_gui_show_screen)

    def end(self):
        super().end()
        zynsigman.unregister(zynsigman.S_AUDIO_RECORDER, zynthian_audio_recorder.SS_AUDIO_RECORDER_STATE, self.on_audio_rec)
        zynsigman.unregister(zynsigman.S_AUDIO_PLAYER, zynthian_engine_audioplayer.SS_AUDIO_PLAYER_STATE, self.on_audio_play)
        zynsigman.unregister(zynsigman.S_STEPSEQ, zynseq.SS_SEQ_METRO, self.on_metronome)
        zynsigman.unregister(zynsigman.S_GUI, zynsigman.SS_GUI_SHOW_SCREEN, self.on_gui_show_screen)

    def light_off(self):
        for led in range(0x28):
            lib_zyncore.dev_send_note_off(self.idev_out, 0, led, 0)

    def on_gui_show_screen(self, screen):
        lib_zyncore.dev_send_ccontrol_change(self.idev_out, 0, BTN_SESSION, 0x0)
        lib_zyncore.dev_send_ccontrol_change(self.idev_out, 0, BTN_BANK, 0x0)
        match screen:
            case "launcher":
                lib_zyncore.dev_send_ccontrol_change(self.idev_out, 0, BTN_SESSION, 0x1)
            case "presets":
                lib_zyncore.dev_send_ccontrol_change(self.idev_out, 0, BTN_BANK, 0x1)
            case "banks":
                lib_zyncore.dev_send_ccontrol_change(self.idev_out, 0, BTN_BANK, 0x1)

    def update_mixer_strip(self, chan, symbol, value, mixbus=False):
        if symbol == "balance" and self.enc_mode == ENC_MODE_PAN:
            if mixbus and chan == 0:
                # Main chain
                pass
            else:
                try:
                    now = monotonic()
                    if now < self.last_cc_send + 0.1:
                        return
                    pos = self.chain_manager.get_pos_by_mixer_chan(chan, mixbus)
                    lib_zyncore.dev_send_ccontrol_change(self.idev_out, 0, pos + 48, int((value + 1.0) * 63))
                except:
                    pass
        elif symbol == "solo":
            if mixbus and chan == 0:
                return  # No control for main mixbus
            try:
                pos = self.chain_manager.get_chain_id_by_mixer_chan(chan, mixbus) - self.scroll_h
                if 0 <= pos < self.cols:
                    lib_zyncore.dev_send_note_on(self.idev_out, pos, LED_SOLO, value)
            except TypeError:
                pass
        elif symbol == "mute":
            if mixbus and chan == 0:
                return  # No control for main mixbus
            try:
                pos = self.chain_manager.get_chain_id_by_mixer_chan(chan, mixbus) - self.scroll_h
                if 0 <= pos < self.cols:
                    lib_zyncore.dev_send_note_on(self.idev_out, pos, LED_ACTIVATOR, value)
            except TypeError:
                pass
        elif symbol == "record":
            if mixbus and chan == 0:
                return  # No control for main mixbus
            try:
                pos = self.chain_manager.get_chain_id_by_mixer_chan(chan, mixbus) - self.scroll_h
                if 0 <= pos < self.cols:
                    lib_zyncore.dev_send_note_on(self.idev_out, pos, LED_RECORD_ARM, value)
            except TypeError:
                pass

    def on_active_chain(self, active_chain_id=None):
        if active_chain_id is None:
            active_chain_id = self.chain_manager.active_chain.chain_id
        super().on_active_chain(active_chain_id)
        for pos in range(self.cols):
            lib_zyncore.dev_send_note_on(self.idev_out, pos, LED_TRACK_SEL, 0)
        if active_chain_id == 0:
            lib_zyncore.dev_send_note_on(self.idev_out, 0, LED_MASTER, 1)
            self.update_device_encoders()
            return
        pos = self.chain_manager.get_chain_index(active_chain_id)
        if pos is None:
            return
        pos = max(0, pos - self.scroll_h)
        lib_zyncore.dev_send_note_on(self.idev_out, 0, LED_MASTER, 0)
        lib_zyncore.dev_send_note_on(self.idev_out, pos, LED_TRACK_SEL, 1)
        self.update_device_encoders()

    def refresh(self):
        super().refresh()
        for col in range(min(self.cols, len(self.chain_ids_filtered))):
            pos = self.scroll_h + col
            chain_id = self.chain_ids_filtered[pos]
            if chain_id == 0:
                continue
            proc = self.chain_manager.chains[chain_id].zynmixer_proc
            if proc:
                for symbol in ("mute", "solo", "record"):
                    mixbus = proc.eng_code == "MR"
                    value = proc.controllers_dict[symbol].value
                    self.update_mixer_strip(pos, symbol, value, mixbus)
            else:
                lib_zyncore.dev_send_note_on(self.idev_out, col, LED_SOLO, 0)
                lib_zyncore.dev_send_note_on(self.idev_out, col, LED_ACTIVATOR, 0)
                lib_zyncore.dev_send_note_on(self.idev_out, col, LED_RECORD_ARM, 0)
        #self.set_enc_mode(self.enc_mode)

    def on_audio_rec(self, state):
        lib_zyncore.dev_send_note_on(self.idev_out, 0, LED_RECORD, state)

    def on_audio_play(self, handle, state):
        try:
            if handle == self.state_manager.audio_player.handle:
                lib_zyncore.dev_send_note_on(self.idev_out, 0, LED_PLAY, int(state))
        except:
            pass

    def on_metronome(self, enable, volume):
        lib_zyncore.dev_send_note_on(self.idev_out, 0, LED_METRONOME, enable)

    def set_enc_mode(self, mode=None):
        if mode is not None and mode <= ENC_MODE_USER:
            self.enc_mode = mode
        lib_zyncore.dev_send_note_on(self.idev_out, 0, LED_PAN, self.enc_mode == ENC_MODE_PAN)
        lib_zyncore.dev_send_note_on(self.idev_out, 0, LED_SENDS, self.enc_mode == ENC_MODE_SENDS)
        lib_zyncore.dev_send_note_on(self.idev_out, 0, LED_USER, self.enc_mode == ENC_MODE_USER)
        self.update_track_encoders()
        # Update device button leds
        for led in range(LED_DEVICE_LEFT, LED_DEVICE_VIEW + 1):
            lib_zyncore.dev_send_note_off(self.idev_out, 0, led, 0)
        if self.enc_mode == ENC_MODE_SENDS:
            lib_zyncore.dev_send_note_on(self.idev_out, 0, LED_DEVICE_LEFT + self.send, 1)
        elif self.enc_mode == ENC_MODE_USER:
            lib_zyncore.dev_send_note_on(self.idev_out, 0, LED_DEVICE_LEFT + self.user, 1)

    # Send track knob values
    def update_track_encoders(self):
        if self.enc_mode == ENC_MODE_PAN:
            for i in range(8):
                pos = self.scroll_h + i
                cc = CC_TRACK_1 + i
                val = int((self.get_mixer_param("balance", pos) + 1) * 64)
                lib_zyncore.dev_send_ccontrol_change(self.idev_out, 0, cc, val)
                try:
                    self.ccnum2zctrls[cc].reset_send_value_cb()
                    del self.ccnum2zctrls[cc]
                except:
                    pass
        elif self.enc_mode == ENC_MODE_SENDS:
            for i in range(8):
                pos = self.scroll_h + i
                cc = CC_TRACK_1 + i
                send_id = self.chain_manager.get_send_id(self.send)
                if send_id is not None:
                    val = int(self.get_mixer_param(f"send_{send_id}_level", pos) * 127)
                else:
                    val = 0
                lib_zyncore.dev_send_ccontrol_change(self.idev_out, 0, cc, val)
                try:
                    self.ccnum2zctrls[cc].reset_send_value_cb()
                    del self.ccnum2zctrls[cc]
                except:
                    pass
        elif self.enc_mode == ENC_MODE_USER:
            for i in range(8):
                pos = self.scroll_h + i
                cc = CC_TRACK_1 + i
                # Use first chain zctrl (favorite)
                try:
                    self.ccnum2zctrls[cc] = self.get_filtered_chain_by_index(pos).zctrls[self.user]
                    self.ccnum2zctrls[cc].set_send_value_cb(self.send_encoder_feedback)
                    val = self.ccnum2zctrls[cc].get_ctrl_midi_val()
                except:
                    val = 0
                lib_zyncore.dev_send_ccontrol_change(self.idev_out, 0, cc, val)

    # Send device knob values
    def update_device_encoders(self):
        # Reset zctrl callbacks
        for cc in list(self.ccnum2zctrls.keys()):
            self.ccnum2zctrls[cc].reset_send_value_cb()
            del self.ccnum2zctrls[cc]

        # Get absolute MIDI learned zctrls
        key_base = self.idev << 16
        for key in list(self.chain_manager.absolute_midi_cc_binding):
            if key_base == (key & 0xFFFF00):
                cc = key & 0x7F
                #logging.debug(f"FOUND ABSOLUTE ZCTRL {key:06x} == {key_base:06x}")
                self.ccnum2zctrls[cc] = self.chain_manager.absolute_midi_cc_binding[key][0]
        # Get chain MIDI learned zctrls
        key_base = self.chain_manager.active_chain.chain_id << 16
        for key in list(self.chain_manager.chain_midi_cc_binding):
            cc = key & 0x7F
            if key_base == (key & 0xFFFF00) and cc not in self.ccnum2zctrls:
                #logging.debug(f"FOUND CHAIN ZCTRL {key:06x} == {key_base:06x}")
                self.ccnum2zctrls[cc] = self.chain_manager.chain_midi_cc_binding[key][0]
        # Send update to the 8 device knobs
        for i in range(8):
            cc = CC_DEVICE_1 + i
            try:
                self.ccnum2zctrls[cc].set_send_value_cb(self.send_encoder_feedback)
                val = self.ccnum2zctrls[cc].get_ctrl_midi_val()
            except:
                val = 0
            lib_zyncore.dev_send_ccontrol_change(self.idev_out, 0, cc, val)

    def send_encoder_feedback(self, zctrl):
        for cc, _zctrl in self.ccnum2zctrls.items():
            if _zctrl == zctrl:
                val = zctrl.get_ctrl_midi_val()
                lib_zyncore.dev_send_ccontrol_change(self.idev_out, 0, cc, val)

    def midi_event(self, ev):
        def relative_to_signed(v):
            return v if v < 64 else v - 128

        # SysEx
        if ev[0] == 0xF0:
            logging.info(f"Received SysEx => {ev.hex(' ')}")
            if ev[3] == 0x6 and ev[4] == 0x2:
                self.sysex_manufacturer_id = ev[5]
                self.sysex_product_model_id = ev[6]
                self.sysex_dev_id = ev[13]
                # Set Mode 1
                self.send_sysex_set_mode(0x41)
            return True

        if self.state_manager.power_save_mode:
            return True

        evtype = (ev[0] >> 4) & 0x0F
        chan = ev[0] & 0x0f
        now = monotonic()
        if evtype == 0xb:
            cc = ev[1]
            val = ev[2]
            if cc == CC_MAIN_FADER:
                self.set_mixer_param("level", -1, val / 127.0)
            elif cc == CC_FADER:
                pos = self.scroll_h + chan
                self.set_mixer_param("level", pos, val / 127.0)
            elif cc == CC_CUE_LEVEL:
                dval = relative_to_signed(val)
                self.nudge_mixer_param("balance", -1, dval)
            elif cc == CC_TEMPO:
                dval = relative_to_signed(val)
                if self._shift:
                    self.zynseq.zctrl_metro_volume.nudge(dval**3)
                else:
                    self.zynseq.nudge_tempo(dval)
            elif CC_TRACK_1 <= cc <= CC_TRACK_8:
                pos = self.scroll_h + cc - CC_TRACK_1
                if self.enc_mode == ENC_MODE_PAN:
                    self.set_mixer_param("balance", pos, val / 64.0 - 1.0)
                    self.last_cc_send = now
                elif self.enc_mode == ENC_MODE_SENDS:
                    send_id = self.chain_manager.get_send_id(self.send)
                    if send_id is not None:
                        self.set_mixer_param(f"send_{send_id}_level", pos, val / 127.0)
                elif self.enc_mode == ENC_MODE_USER:
                    # Use first chain zctrl (favorite)
                    try:
                        user_zctrl = self.get_filtered_chain_by_index(pos).zctrls[self.user]
                        user_zctrl.midi_control_change(val)
                    except:
                        pass
            # Send CC to chains and midi_learn subsystem
            elif CC_DEVICE_1 <= cc <= CC_DEVICE_8:
                #logging.debug(f"DEVICE CC => cc={cc}, val={val}")
                if not self.state_manager.midi_learn_zctrl:
                    self.chain_manager.midi_control_change(self.idev, 0, cc, val)
                zynsigman.send_queued(zynsigman.S_MIDI, zynsigman.SS_MIDI_CC,
                                      izmip=self.idev, chan=0, num=cc, val=val)

        elif evtype == 8:
            # Note off
            note = ev[1]
            not_enc_mode = not (self._send or self._user)
            if note == BTN_SHIFT:
                self._shift = False
                if self.enc_mode == ENC_MODE_SENDS:
                    self.update_track_encoders()
            elif note == LED_SENDS:
                self._send = False
            elif note == LED_USER:
                self._user = False
            elif note == BTN_STOP_ALL_CLIPS:
                if self.last_press and now > self.last_press + BOLD_PRESS_TIME:
                    # PANIC!
                    self.state_manager.all_notes_off()
                else:
                    for midi_chan in range(MAX_NUM_MIDI_CHANS + 1):
                        for phrase in range(self.zynseq.phrases):
                            self.zynseq.libseq.setPlayState(self.zynseq.scene, phrase, midi_chan, zynseq.SEQ_STOPPED)
                self.last_press = None

            # Navigation CUIAs: Arrows, BACK, SELECT, etc.
            elif note == LED_DEVICE_ON and not_enc_mode:
                #self.state_manager.send_cuia("ZYNSWITCH", (1, "R"))
                pass
            elif note == LED_DEVICE_LOCK and not_enc_mode:
                self.state_manager.send_cuia("ZYNSWITCH", (3, "R"))
            elif note == LED_DEVICE_VIEW:
                pass
            elif note == LED_DETAIL_VIEW:
                pass

        elif evtype == 9:
            # Note on
            note = ev[1]
            # Clip launcher pads
            if note < 0x30:
                # Launcher pad => sel.scroll_h = self.scroll_h
                pos = self.scroll_h + note % 8
                row = note // 8
                midi_chan = self.get_filtered_midi_chan_by_index(pos)
                if midi_chan is None:
                    return
                phrase = self.rows - 1 - row + self.scroll_v
                self.zynseq.libseq.togglePlayState(self.zynseq.scene, phrase, midi_chan)
            # Scene buttons => Phrase launcher
            elif LED_SCENE_LAUNCH_1 <= note <= LED_SCENE_LAUNCH_5:
                phrase = note - LED_SCENE_LAUNCH_1
                self.zynseq.libseq.togglePlayState(self.zynseq.scene, phrase, 32)
            # Track select button => Chain select
            elif note == LED_TRACK_SEL:
                try:
                    id = self.chain_ids_filtered[self.scroll_h + chan]
                    self.chain_manager.set_active_chain_by_id(id)
                except:
                    pass
            elif note == LED_MASTER:
                self.chain_manager.set_active_chain_by_id(0)
            # Track flag buttons
            elif note == LED_SOLO:
                pos = self.scroll_h + chan
                self.toggle_mixer_param("solo", pos)
            elif note == LED_ACTIVATOR:
                pos = self.scroll_h + chan
                self.toggle_mixer_param("mute", pos)
            elif note == LED_RECORD_ARM:
                pos = self.scroll_h + chan
                self.toggle_mixer_param("record", pos)
            elif note == LED_CLIP_STOP:
                pos = self.scroll_h + chan
                midi_chan = self.get_filtered_midi_chan_by_index(pos)
                for phrase in range(self.zynseq.phrases):
                    self.zynseq.libseq.setPlayState(self.zynseq.scene, phrase, midi_chan, zynseq.SEQ_STOPPING)
            # Global buttons
            elif note == BTN_STOP_ALL_CLIPS:
                self.last_press = now
            elif note == LED_PAN:
                self.set_enc_mode(ENC_MODE_PAN)
            elif note == LED_SENDS:
                self.set_enc_mode(ENC_MODE_SENDS)
                self._send = True
            elif note == LED_USER:
                self.set_enc_mode(ENC_MODE_USER)
                self._user = True
            elif note == BTN_SHIFT:
                self._shift = True
            elif note == BTN_TAP_TEMPO:
                self.state_manager.send_cuia("TAP_TEMPO")
            elif note == LED_PLAY:
                self.state_manager.toggle_audio_player()
            elif note == LED_RECORD:
                self.state_manager.audio_recorder.toggle_recording()
            elif note == LED_METRONOME:
                if self._shift:
                    self.state_manager.send_cuia("TOGGLE_SCREEN", ("tempo",))
                else:
                    self.zynseq.zctrl_metro_enable.toggle()
            elif note == BTN_NUDGE_DOWN:
                self.zynseq.nudge_tempo(-0.1)
            elif note == BTN_NUDGE_UP:
                self.zynseq.nudge_tempo(+0.1)

            # Navigation CUIAs: Arrows, BACK, SELECT, etc.
            elif note == BTN_UP:
                self.state_manager.send_cuia("ARROW_UP")
            elif note == BTN_DOWN:
                self.state_manager.send_cuia("ARROW_DOWN")
            elif note == BTN_LEFT:
                self.state_manager.send_cuia("ARROW_LEFT")
            elif note == BTN_RIGHT:
                self.state_manager.send_cuia("ARROW_RIGHT")
            elif LED_DEVICE_LEFT <= note <= LED_DETAIL_VIEW:
                idx = note - LED_DEVICE_LEFT
                if self._send:
                    self.send = idx
                    self.set_enc_mode(ENC_MODE_SENDS)
                elif self._user:
                    self.user = idx
                    self.set_enc_mode(ENC_MODE_USER)
                elif note == LED_DEVICE_ON:
                    self.state_manager.send_cuia("BACK")
                    #self.state_manager.send_cuia("ZYNSWITCH", (1, "P"))
                elif note == LED_DEVICE_LOCK:
                    self.state_manager.send_cuia("ZYNSWITCH", (3, "P"))
            elif note == LED_DETAIL_VIEW:
                if self._send:
                    self.send = 7
                    self.set_enc_mode(ENC_MODE_SENDS)
                else:
                    pass
            elif note == BTN_SESSION:
                if zynthian_gui_config.zyngui.screens["mixer"].launcher_mode:
                    self.state_manager.send_cuia("SCREEN_MIXER")
                else:
                    self.state_manager.send_cuia("SCREEN_LAUNCHER")
            elif note == BTN_BANK:
                self.state_manager.send_cuia("BANK_PRESET")
            else:
                logging.debug(f"UNCATCHED NOTE-ON => {note:02x}")

        return True

    def update_pad(self, row, col, pad_info):
        if col < self.cols:
            note = (4 - row) * 8 + col
        elif col == self.phrase_launcher_col:
            note = row + LED_SCENE_LAUNCH_1
        else:
            return
        led_mode = RGB_MODE_PRIMARY
        led_colour = 0
        group = 32
        try:
            group = pad_info["group"]
        except:
            pass
        try:
            state = pad_info["state"]
            repeat = pad_info["repeat"]
            led_colour = zynthian_gui_config.LAUNCHER_COLOUR[group]["apc"]
            if repeat == 0:
                led_colour = 0 # Off
                led_mode = RGB_MODE_PRIMARY
            elif state == zynseq.SEQ_STOPPED:
                led_colour = zynthian_gui_config.LAUNCHER_COLOUR[group]["apc"]
                led_mode = RGB_MODE_PRIMARY
            elif state == zynseq.SEQ_PLAYING:
                led_colour = zynthian_gui_config.LAUNCHER_PLAYING_COLOUR["apc"]
                led_mode = RGB_MODE_PULSE_2
            elif state in [zynseq.SEQ_STOPPING, zynseq.SEQ_STOPPING_SYNC]:
                lib_zyncore.dev_send_note_on(self.idev_out, RGB_MODE_PRIMARY, note, led_colour)
                led_colour = zynthian_gui_config.LAUNCHER_STOPPING_COLOUR["apc"]
                led_mode = RGB_MODE_BLINK_4
            elif state == zynseq.SEQ_STARTING:
                lib_zyncore.dev_send_note_on(self.idev_out, RGB_MODE_PRIMARY, note, led_colour)
                led_colour = zynthian_gui_config.LAUNCHER_STARTING_COLOUR["apc"]
                led_mode = RGB_MODE_BLINK_8
            elif state == zynseq.SEQ_CHILD_PLAYING:
                led_colour = zynthian_gui_config.LAUNCHER_PLAYING_COLOUR["apc"]
                led_mode = RGB_MODE_PULSE_2
            elif state == zynseq.SEQ_CHILD_STOPPING:
                lib_zyncore.dev_send_note_on(self.idev_out, RGB_MODE_PRIMARY, note, led_colour)
                led_colour = zynthian_gui_config.LAUNCHER_STOPPING_COLOUR["apc"]
                led_mode = RGB_MODE_BLINK_4
        except:
            pass
        lib_zyncore.dev_send_note_on(self.idev_out, led_mode, note, led_colour)
