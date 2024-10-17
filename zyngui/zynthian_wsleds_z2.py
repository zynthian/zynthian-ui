#!/usr/bin/python3
# -*- coding: utf-8 -*-
# ******************************************************************************
# ZYNTHIAN PROJECT: Zynthian GUI
#
# Zynthian WSLeds Class for Z2
#
# Copyright (C) 2015-2023 Fernando Moyano <jofemodo@zynthian.org>
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

# Zynthian specific modules
from zyngui.zynthian_wsleds_base import zynthian_wsleds_base
from zyngui import zynthian_gui_config

# ---------------------------------------------------------------------------
# Zynthian WSLeds class for Z2
# ---------------------------------------------------------------------------


class zynthian_wsleds_z2(zynthian_wsleds_base):

    def __init__(self, zyngui):
        super().__init__(zyngui)
        self.num_leds = 25
        # Per-screen customizable LEDs (15 LEDs):
        # + ALT => 13
        # + transport => 14, 17, 15
        # + arrow => 19, 21, 22, 23
        # + BACK/SEL => 18, 20
        # + F1-F5 => 8, 9, 10, 11, 12 (display's bottom buttons)
        self.custom_wsleds = [13, 14, 17, 15, 19,
                              21, 22, 23, 18, 20, 8, 9, 10, 11, 12]

    def update_wsleds(self):
        curscreen = self.zyngui.current_screen
        curscreen_obj = self.zyngui.get_current_screen_obj()

        # Menu
        if self.zyngui.is_current_screen_menu():
            self.wsleds[0] = self.wscolor_active
        elif self.zyngui.is_current_screen_admin():
            self.wsleds[0] = self.wscolor_active2
        else:
            self.wsleds[0] = self.wscolor_default

        # Active Chain
        if self.zyngui.alt_mode:
            wscolor_light = self.wscolor_alt
        else:
            wscolor_light = self.wscolor_default

        # => Light non-empty chains
        for i, chain_id in enumerate([1, 2, 3, 4, 5, 0]):
            if self.zyngui.chain_manager.get_chain(chain_id) is None:
                self.wsleds[i + 1] = self.wscolor_off
            else:
                if self.zyngui.chain_manager.active_chain_id == chain_id:
                    # => Light active chain
                    if curscreen == "control":
                        self.wsleds[i + 1] = self.wscolor_active
                    else:
                        if self.zyngui.chain_manager.get_processor_count(chain_id):
                            self.blink(i + 1, self.wscolor_active)
                        else:
                            self.blink(i + 1, self.wscolor_active2)
                else:
                    self.wsleds[i + 1] = wscolor_light

        # MODE button => MIDI LEARN
        if self.zyngui.state_manager.get_midi_learn_zctrl() or curscreen == "zs3":
            self.wsleds[7] = self.wscolor_yellow
        elif self.zyngui.state_manager.midi_learn_zctrl:
            self.wsleds[7] = self.wscolor_active
        else:
            self.wsleds[7] = self.wscolor_default

        # Zynpad screen:
        if curscreen == "zynpad":
            self.wsleds[8] = self.wscolor_active
        else:
            self.wsleds[8] = self.wscolor_default

        # Pattern Editor/Arranger screen:
        if curscreen == "pattern_editor":
            self.wsleds[9] = self.wscolor_active
        elif curscreen == "arranger":
            self.wsleds[9] = self.wscolor_active2
        else:
            self.wsleds[9] = self.wscolor_default

        # Control / Preset Screen:
        if curscreen in ("control", "audio_player"):
            self.wsleds[10] = self.wscolor_active
        elif curscreen in ("preset", "bank"):
            if self.zyngui.current_processor.get_show_fav_presets():
                self.blink(10, self.wscolor_active2)
            else:
                self.wsleds[10] = self.wscolor_active2
        else:
            self.wsleds[10] = self.wscolor_default

        # ZS3/Snapshot screen:
        if curscreen == "zs3":
            self.wsleds[11] = self.wscolor_active
        elif curscreen == "snapshot":
            self.wsleds[11] = self.wscolor_active2
        else:
            self.wsleds[11] = self.wscolor_default

        # ???:
        self.wsleds[12] = self.wscolor_default

        # ALT button:
        if self.zyngui.alt_mode:
            self.wsleds[13] = self.wscolor_alt
        else:
            self.wsleds[13] = self.wscolor_default

        if self.zyngui.alt_mode and curscreen != "midi_recorder":
            self.zyngui.screens["midi_recorder"].update_wsleds(wsleds)
        else:
            # REC Button
            if self.zyngui.state_manager.audio_recorder.rec_proc:
                self.wsleds[14] = self.wscolor_red
            else:
                self.wsleds[14] = self.wscolor_default
            # STOP button
            self.wsleds[17] = self.wscolor_default
            # PLAY button:
            if self.zyngui.state_manager.status_audio_player:
                self.wsleds[15] = self.wscolor_green
            else:
                self.wsleds[15] = self.wscolor_default

        # Tempo Screen
        if curscreen == "tempo":
            self.wsleds[16] = self.wscolor_active
        elif self.zyngui.state_manager.zynseq.libseq.isMetronomeEnabled():
            self.blink(16, self.wscolor_active)
        else:
            self.wsleds[16] = self.wscolor_default

        # Select/Yes button
        self.wsleds[20] = self.wscolor_green

        # Back/No button
        self.wsleds[18] = self.wscolor_red

        # Arrow buttons (Up, Left, Bottom, Right)
        self.wsleds[19] = self.wscolor_yellow
        self.wsleds[21] = self.wscolor_yellow
        self.wsleds[22] = self.wscolor_yellow
        self.wsleds[23] = self.wscolor_yellow

        # Audio Mixer / ALSA Mixer
        if curscreen == "audio_mixer":
            self.wsleds[24] = self.wscolor_active
        elif curscreen == "alsa_mixer":
            self.wsleds[24] = self.wscolor_active2
        else:
            self.wsleds[24] = self.wscolor_default

        # Call current screen's update_wsleds() function to update the customizable LEDs
        update_wsleds_func = getattr(curscreen_obj, "update_wsleds", None)
        if callable(update_wsleds_func):
            update_wsleds_func(self.custom_wsleds)

        try:
            self.zyngui.screens[curscreen].update_wsleds()
        except:
            pass

# ------------------------------------------------------------------------------
