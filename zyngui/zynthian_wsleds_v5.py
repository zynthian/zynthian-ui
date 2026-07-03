#!/usr/bin/python3
# -*- coding: utf-8 -*-
# ******************************************************************************
# ZYNTHIAN PROJECT: Zynthian GUI
#
# Zynthian WSLeds Class for V5
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

# ---------------------------------------------------------------------------
# Zynthian WSLeds class for V5
# ---------------------------------------------------------------------------


class zynthian_wsleds_v5(zynthian_wsleds_base):

    def __init__(self, zyngui):
        super().__init__(zyngui)
        self.num_leds = 20

        # Per-screen customizable LEDs (14 LEDs):
        # + ALT => 7
        # + transport => 8, 9, 10
        # + arrow => 14, 16, 17, 18
        # + BACK/SEL => 15, 13
        # + F1-F4 => 4, 11, 12, 19
        # + CTRL => 2
        self.custom_wsleds = [7, 8, 9, 10, 14,
                              16, 17, 18, 15, 13,
                              4, 11, 12, 19, None,
                              2]

    def update_wsleds(self):
        curscreen = self.zyngui.get_current_screen()
        workflow = self.zyngui.get_current_workflow()
        alt_mode = self.zyngui.get_alt_mode()

        # Menu / Admin
        if workflow == "admin":
            self.wsleds[0] = self.wscolor_active2
        elif workflow in ("menu", "chain_manager"):
            self.wsleds[0] = self.wscolor_active
        else:
            self.wsleds[0] = self.wscolor_default

        # Audio Mixer / ALSA Mixer
        if workflow == "alsa_mixer":
            self.wsleds[1] = self.wscolor_active2
        elif curscreen == "mixer":
            self.wsleds[1] = self.wscolor_active
        else:
            self.wsleds[1] = self.wscolor_default

        # Control / Preset Screen:
        if workflow == "bank_preset":
            self.wsleds[2] = self.wscolor_active2
        elif workflow in ("chain_control", "audio_player"):
            self.wsleds[2] = self.wscolor_active
        else:
            self.wsleds[2] = self.wscolor_default

        # ZS3 / Snapshot:
        if workflow == "snapshot":
            self.wsleds[3] = self.wscolor_active2
        elif workflow == "zs3":
            self.wsleds[3] = self.wscolor_active
        else:
            self.wsleds[3] = self.wscolor_default

        # Zynseq: Launcher /Pattern Editor
        if workflow == "pated":
            self.wsleds[5] = self.wscolor_active2
        elif curscreen == "launcher":
            self.wsleds[5] = self.wscolor_active
        else:
            self.wsleds[5] = self.wscolor_default

        # Tempo Screen
        if workflow == "tempo":
            self.wsleds[6] = self.wscolor_active
        elif self.zyngui.state_manager.zynseq.libseq.getMetronomeMode() > 0:
            self.blink(6, self.wscolor_active)
        else:
            self.wsleds[6] = self.wscolor_default

        # ALT button:
        if alt_mode:
            self.wsleds[7] = self.wscolor_alt
        else:
            self.wsleds[7] = self.wscolor_default

        if alt_mode and curscreen != "midi_recorder":
            self.zyngui.screens["midi_recorder"].update_wsleds(self.custom_wsleds)
        else:
            # REC Button
            if self.zyngui.state_manager.audio_recorder.rec_proc:
                self.wsleds[8] = self.wscolor_red
            else:
                self.wsleds[8] = self.wscolor_default
            # STOP button
            self.wsleds[9] = self.wscolor_default
            # PLAY button:
            if self.zyngui.state_manager.status_audio_player:
                self.wsleds[10] = self.wscolor_green
            else:
                self.wsleds[10] = self.wscolor_default

        # Select/Yes button
        self.wsleds[13] = self.wscolor_green

        # Back/No button
        self.wsleds[15] = self.wscolor_red

        # Arrow buttons (Up, Left, Bottom, Right)
        self.wsleds[14] = self.wscolor_yellow
        self.wsleds[16] = self.wscolor_yellow
        self.wsleds[17] = self.wscolor_yellow
        self.wsleds[18] = self.wscolor_yellow

        # F1-F4 buttons
        if alt_mode:
            wscolor_fx = self.wscolor_alt
        else:
            wscolor_fx = self.wscolor_default
        self.wsleds[4] = wscolor_fx
        self.wsleds[11] = wscolor_fx
        self.wsleds[12] = wscolor_fx
        self.wsleds[19] = wscolor_fx

        curscreen_obj = self.zyngui.get_current_screen_obj()
        if curscreen_obj:
            # Call current screen's update_wsleds() function to update the customizable LEDs
            update_wsleds_func = getattr(curscreen_obj, "update_wsleds", None)
            if callable(update_wsleds_func):
                update_wsleds_func(self.custom_wsleds)

# ------------------------------------------------------------------------------
