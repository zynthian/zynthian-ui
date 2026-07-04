#!/usr/bin/python3
# -*- coding: utf-8 -*-
# ******************************************************************************
# ZYNTHIAN PROJECT: Zynthian Control Device Driver
#
# Zynthian Control Device Driver for "Novation Launchkey MK3 88"
# Vangelis branch
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

# Zynthian specific modules
from zyngine.ctrldev.zynthian_ctrldev_base import zynthian_ctrldev_zynpad, zynthian_ctrldev_zynmixer
from zyncoder.zyncore import lib_zyncore
from zynlibs.zynseq import zynseq
from zyngui import zynthian_gui_config
from zyngine.zynthian_chain_manager import MAX_NUM_MIDI_CHANS
from zyngine.zynthian_signal_manager import zynsigman

# ------------------------------------------------------------------------------------------------------------------
# Novation Launchkey MK3 88
# ------------------------------------------------------------------------------------------------------------------


class zynthian_ctrldev_launchkey_mk3_88(zynthian_ctrldev_zynpad, zynthian_ctrldev_zynmixer):

    dev_ids = ["Launchkey MK3 88 IN 2"]
    driver_name = "Launchkey MK3 88"
    driver_description = "Interface Novation Launchkey MK3 88 with zynpad and mixer"
    unroute_from_chains = True

    # MIDI CC Numbers — pokrętła i suwaki (kanał 0)
    CC_KNOBS   = [21, 22, 23, 24, 25, 26, 27, 28]
    CC_SLIDERS = [53, 54, 55, 56, 57, 58, 59, 60]
    CC_MASTER  = 61

    # CC przyciski pod suwakami chain (kanał 0)
    CC_CHAIN_BUTTONS = [37, 38, 39, 40, 41, 42, 43, 44]
    CC_MASTER_BUTTON = 45   # Zmiana trybu Select/Mute/Solo

    # CC przycisków transportowych i nawigacyjnych (kanał 15 / 0xF w trybie DAW)
    CC_TRACK_RIGHT = 0x66   # 102
    CC_TRACK_LEFT  = 0x67   # 103
    CC_PLAY        = 0x73   # 115
    CC_RECORD      = 0x75   # 117
    CC_LOOP        = 0x76   # 118 (Capture MIDI)
    CC_SCENE_UP    = 0x68   # 104
    CC_SCENE_DOWN  = 0x69   # 105
    CC_CLICK       = 0x4C   # 76  (Metronom)
    CC_DEVICE_SEL  = 0x33   # 51
    CC_SHIFT       = 0x6C   # 108

    # Tryby świecenia LED (kanały MIDI note-on do padów)
    CHAN_STEADY = 0
    CHAN_FLASH  = 1
    CHAN_PULSE  = 2

    # Kolory LEDów przycisków chain
    LED_OFF           = 0
    COLOR_WHITE_FULL  = 3
    COLOR_RED_DIM     = 7
    COLOR_RED_FULL    = 5
    COLOR_YELLOW_DIM  = 15
    COLOR_YELLOW_FULL = 13

    def __init__(self, state_manager, idev_in, idev_out=None):
        self.shift = False
        self.buttons_mode = 0   # 0=Select, 1=Mute, 2=Solo
        super().__init__(state_manager, idev_in, idev_out)
        self.cols = 8
        self.rows = 2

    # ------------------------------------------------------------------
    # Inicjalizacja i zakończenie
    # ------------------------------------------------------------------

    def init(self):
        # Wejście w tryb DAW
        lib_zyncore.dev_send_note_on(self.idev_out, 15, 12, 127)
        # Tryb pokręteł: 1 = Volume
        lib_zyncore.dev_send_ccontrol_change(self.idev_out, 15, 9, 1)
        super().init()
        # Dodatkowe sygnały dla LEDów przycisków chain
        zynsigman.register_queued(zynsigman.S_CHAIN_MAN, zynsigman.SS_SET_ACTIVE_CHAIN, self._refresh_chain_leds)
        zynsigman.register_queued(zynsigman.S_GUI, zynsigman.SS_GUI_SHOW_SCREEN, self._refresh_chain_leds)
        self._refresh_chain_leds()

    def end(self):
        zynsigman.unregister(zynsigman.S_CHAIN_MAN, zynsigman.SS_SET_ACTIVE_CHAIN, self._refresh_chain_leds)
        zynsigman.unregister(zynsigman.S_GUI, zynsigman.SS_GUI_SHOW_SCREEN, self._refresh_chain_leds)
        super().end()
        lib_zyncore.dev_send_note_on(self.idev_out, 15, 12, 0)

    # ------------------------------------------------------------------
    # ZynPad — pady
    # ------------------------------------------------------------------

    def update_pad(self, row, col, pad_info):
        """Koloruje pada na kontrolerze wg stanu sekwencji."""
        if col >= self.cols:    # Phrase launcher col — nie implementujemy
            return
        note = 96 + row * 16 + col
        chan = self.CHAN_STEADY
        vel = 0
        try:
            state  = pad_info["state"]
            repeat = pad_info["repeat"]
            group  = pad_info["group"]
            if repeat == 0 or group >= MAX_NUM_MIDI_CHANS:
                pass  # vel=0 → LED off
            elif state == zynseq.SEQ_STOPPED:
                vel = zynthian_gui_config.LAUNCHER_COLOUR[group]["launchpad"]
                chan = self.CHAN_STEADY
            elif state == zynseq.SEQ_PLAYING:
                vel  = zynthian_gui_config.LAUNCHER_COLOUR[group]["launchpad"]
                chan = self.CHAN_PULSE
            elif state in (zynseq.SEQ_STOPPING, zynseq.SEQ_STOPPING_SYNC):
                vel  = zynthian_gui_config.LAUNCHER_STOPPING_COLOUR["launchpad"]
                chan = self.CHAN_FLASH
            elif state == zynseq.SEQ_STARTING:
                # Błysk kolorem grupy, potem flash kolor startowy
                vel = zynthian_gui_config.LAUNCHER_COLOUR[group]["launchpad"]
                lib_zyncore.dev_send_note_on(self.idev_out, self.CHAN_STEADY, note, vel)
                vel  = zynthian_gui_config.LAUNCHER_STARTING_COLOUR["launchpad"]
                chan = self.CHAN_FLASH
        except Exception:
            pass
        lib_zyncore.dev_send_note_on(self.idev_out, chan, note, vel)

    def pad_off(self, col, row):
        note = 96 + row * 16 + col
        lib_zyncore.dev_send_note_on(self.idev_out, 0, note, 0)

    def light_off(self):
        for row in range(self.rows):
            for col in range(self.cols):
                self.pad_off(col, row)

    # ------------------------------------------------------------------
    # Zynmixer — LEDy przycisków chain
    # ------------------------------------------------------------------

    def update_mixer_strip(self, chan, symbol, value, mixbus=False):
        """Wywoływane przez bazę zynmixer przy każdej zmianie wartości miksera."""
        self._refresh_chain_leds()

    def _refresh_chain_leds(self, *args, **kwargs):
        """
        Aktualizuje LEDy 8 przycisków chain i przycisku Master.
        Indeks i+1 pomija chain 0 (Main) — identycznie jak set_mixer_param z idx+1.
        """
        if self.idev_out is None:
            return
        try:
            active_chain_id = None
            active_chain = self.chain_manager.get_active_chain()
            if active_chain:
                active_chain_id = active_chain.chain_id

            master_col = self.COLOR_YELLOW_FULL if self.buttons_mode == 2 else self.COLOR_RED_FULL
            lib_zyncore.dev_send_ccontrol_change(self.idev_out, self.CHAN_STEADY, self.CC_MASTER_BUTTON, master_col)

            for i, cc_num in enumerate(self.CC_CHAIN_BUTTONS):
                idx = i + self.scroll_h  # +1 pomija chain 0 (Main)
                chain = self.get_filtered_chain_by_index(idx)
                if chain is None:
                    color = self.LED_OFF
                elif self.buttons_mode == 0:   # SELECT
                    color = self.COLOR_RED_FULL if chain.chain_id == active_chain_id else self.COLOR_WHITE_FULL
                elif self.buttons_mode == 1:   # MUTE
                    color = self.COLOR_RED_FULL if self.get_mixer_param("mute", idx) else self.COLOR_RED_DIM
                else:                          # SOLO
                    color = self.COLOR_YELLOW_FULL if self.get_mixer_param("solo", idx) else self.COLOR_YELLOW_DIM
                lib_zyncore.dev_send_ccontrol_change(self.idev_out, self.CHAN_STEADY, cc_num, color)
        except Exception as e:
            logging.warning(f"LaunchkeyMK3 88 _refresh_chain_leds: {e}")

    # ------------------------------------------------------------------
    # Obsługa MIDI
    # ------------------------------------------------------------------

    def midi_event(self, ev):
        if self.state_manager.power_save_mode:
            return True

        evtype = (ev[0] >> 4) & 0x0F
        chan   = ev[0] & 0x0F

        # ----- NOTE ON — pady ZynPad -----
        if evtype == 0x9:
            note = ev[1] & 0x7F
            # Potwierdzenie trybu DAW od kontrolera — ignoruj
            if ev == b'\x9f\x0c\x7f':
                return True
            vel = ev[2] & 0x7F
            if vel > 0 and 96 <= note <= 127:
                try:
                    col = (note - 96) % 16
                    row = (note - 96) // 16
                    midi_chan = self.get_filtered_midi_chan_by_index(col)
                    if midi_chan is not None:
                        phrase = row + self.scroll_v
                        self.zynseq.libseq.togglePlayState(self.zynseq.scene, phrase, midi_chan)
                except Exception:
                    pass
            return True

        # ----- CC -----
        elif evtype == 0xB:
            ccnum = ev[1] & 0x7F
            ccval = ev[2] & 0x7F

            # === Kanał 15 (0xF) — wszystkie kontrolki w trybie DAW ===
            if chan == 0xF:
                if ccval == 0:
                    return True  # Ignoruj zwolnienie przycisków

                # Transport
                if ccnum == self.CC_PLAY:
                    self.state_manager.send_cuia("TOGGLE_MIDI_PLAY" if self.shift else "TOGGLE_PLAY")

                elif ccnum == self.CC_RECORD:
                    self.state_manager.send_cuia("TOGGLE_MIDI_RECORD" if self.shift else "TOGGLE_RECORD")

                elif ccnum == self.CC_LOOP:
                    self.state_manager.send_cuia("ZYNSWITCH", [3, 'S'])

                elif ccnum == self.CC_TRACK_RIGHT:
                    if self.shift:
                        self.state_manager.send_cuia("ARROW_RIGHT")
                    else:
                        self.zynseq.select_scene(self.zynseq.scene + 1)
                        self.refresh()

                elif ccnum == self.CC_TRACK_LEFT:
                    if self.shift:
                        self.state_manager.send_cuia("ARROW_LEFT")
                    else:
                        self.zynseq.select_scene(max(0, self.zynseq.scene - 1))
                        self.refresh()

                elif ccnum == self.CC_SCENE_UP:
                    if self.shift:
                        self.zynseq.select_phrase(self.zynseq.phrase - 1)
                        self.refresh()
                    else:
                        self.zynseq.libseq.togglePlayState(
                            self.zynseq.scene, self.zynseq.phrase, zynseq.PHRASE_CHANNEL)

                elif ccnum == self.CC_SCENE_DOWN:
                    if self.shift:
                        self.zynseq.select_phrase(self.zynseq.phrase + 1)
                        self.refresh()
                    else:
                        self.state_manager.send_cuia("BACK")

                elif ccnum == self.CC_CLICK:
                    self.state_manager.send_cuia("TEMPO")

                elif ccnum == self.CC_DEVICE_SEL:
                    self.state_manager.send_cuia("SCREEN_ZYNPAD")

                # Suwaki — poziom głośności chainów
                elif ccnum in self.CC_SLIDERS:
                    idx = self.CC_SLIDERS.index(ccnum)
                    self.set_mixer_param("level", idx + self.scroll_h, ccval / 127.0)

                # Master suwak — głośność Main (chain 0)
                elif ccnum == self.CC_MASTER:
                    self.set_mixer_param("level", -1, ccval / 127.0)

                # Pokrętła — panorama chainów
                elif ccnum in self.CC_KNOBS:
                    idx = self.CC_KNOBS.index(ccnum)
                    self.set_mixer_param("balance", idx + self.scroll_h, 2 * ccval / 127.0 - 1)

                # Master button — zmiana trybu Select/Mute/Solo
                elif ccnum == self.CC_MASTER_BUTTON:
                    self.buttons_mode = (self.buttons_mode + 1) % 3
                    self._refresh_chain_leds()

                # Przyciski chain (Select / Mute / Solo)
                elif ccnum in self.CC_CHAIN_BUTTONS:
                    idx = self.CC_CHAIN_BUTTONS.index(ccnum)
                    filt_idx = idx + self.scroll_h
                    chain = self.get_filtered_chain_by_index(filt_idx)
                    if chain is not None:
                        if self.buttons_mode == 0:   # SELECT
                            self.chain_manager.set_active_chain_by_id(chain.chain_id)
                        elif self.buttons_mode == 1:  # MUTE
                            self.toggle_mixer_param("mute", filt_idx)
                        else:                         # SOLO
                            self.toggle_mixer_param("record", filt_idx)
                        self._refresh_chain_leds()

                return True

            # === Kanał 0 — tylko Shift (przesyłany poza trybem DAW) ===
            if ccnum == self.CC_SHIFT:
                self.shift = (ccval != 0)
                return True

        return True

# ------------------------------------------------------------------------------
