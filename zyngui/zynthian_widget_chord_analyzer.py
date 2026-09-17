#!/usr/bin/python3
# -*- coding: utf-8 -*-
# ******************************************************************************
# ZYNTHIAN PROJECT: Zynthian GUI
#
# Zynthian Widget Class for NAM (Neural Amp Modeler) plugin
#
# Copyright (C) 2015-2025 Jofemodo <fernando@zynthian.org>
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

import os
import logging
import tkinter

# Zynthian specific modules
from zyngui import zynthian_gui_config
from zyngui import zynthian_widget_base

# ------------------------------------------------------------------------------
# Zynthian Widget Class for chord_analyzer_headless plugin
# ------------------------------------------------------------------------------


class zynthian_widget_chord_analyzer(zynthian_widget_base.zynthian_widget_base):

    root_labels = ["-", "C", "C#/Db", "D", "D#/Eb", "E", "F", "F#/Gb", "G", "G#/Ab", "A", "A#/Bb", "B"]
    quality_labels = ["-", "maj", "m", "dim", "aug", "7", "maj7", "m7", "mMaj7", "dim7", "m7b5", "aug7",
                        "augMaj7", "sus2", "sus4", "7sus4", "add9", "add11", "6", "m6", "maj9", "m9", "9",
                        "maj11", "m11", "11", "maj13", "m13", "13", "5", "7b5", "7#5", "7b9", "7#9"]
    inversion_labels = ["-", "Root", "1st", "2nd", "3rd", "4th", "5th", "6th", "Slash"]
    bass_labels = ["-", "C", "C#/Db", "D", "D#/Eb", "E", "F", "F#/Gb", "G", "G#/Ab", "A", "A#/Bb", "B"]

    def __init__(self, parent):
        super().__init__(parent)

        self.widget_canvas = tkinter.Canvas(self,
                                            highlightthickness=0,
                                            relief='flat',
                                            bg=zynthian_gui_config.color_bg)
        self.widget_canvas.grid(sticky='news')

        # Create custom GUI elements (position and size set when canvas is grid and size applied)
        self.chord_label = self.widget_canvas.create_text(
            0, 0,
            fill=zynthian_gui_config.color_ml,
            text='',
            anchor="w"
        )
        self.chord_line = self.widget_canvas.create_line(
            0, 0, 0, 0,
            width=1,
            fill=zynthian_gui_config.color_tx_off
        )
        self.bass_label = self.widget_canvas.create_text(
            0, 0,
            fill=zynthian_gui_config.color_tx,
            text='',
            width=0,
            anchor="nw"
        )

    def on_size(self, event):
        if event.width == self.width and event.height == self.height:
            return
        super().on_size(event)

        content_width = round(0.9 * self.width)
        content_height = round(0.2 * self.height)
        x0 = round(0.05 * self.width)
        y0 = round(0.5 * self.height)
        fs_chord = content_height // 3
        fs_bass = content_height // 3

        self.widget_canvas.coords(self.chord_label, x0, y0)
        self.widget_canvas.itemconfig(self.chord_label, font=(zynthian_gui_config.font_family, fs_chord))
        self.widget_canvas.coords(self.chord_line, x0, y0 + content_height // 2, x0 + content_width, y0 + content_height // 2)
        self.widget_canvas.coords(self.bass_label, x0, y0 + int(0.8 * content_height))
        self.widget_canvas.itemconfig(self.bass_label, font=(zynthian_gui_config.font_family, fs_bass), width=content_width)

        self.widget_canvas.grid(row=0, column=0, sticky='news')

    def refresh_gui(self):
        #logging.debug(self.monitors)
        if "detected_root" in self.monitors:
            root_index = int(self.monitors["detected_root"])
            quality_index = int(self.monitors["detected_quality"])
            inversion_index = int(self.monitors["detected_inversion"])
            bass_index = int(self.monitors["detected_bass"])
        elif "chord_analyzer_detectedRoot" in self.monitors:
            root_index = int(self.monitors["chord_analyzer_detectedRoot"])
            quality_index = int(self.monitors["chord_analyzer_detectedQuality"])
            inversion_index = int(self.monitors["chord_analyzer_detectedInversion"])
            bass_index = int(self.monitors["chord_analyzer_detectedBass"])
        elif "chord_analyzer_midi_detectedRoot" in self.monitors:
            root_index = int(self.monitors["chord_analyzer_midi_detectedRoot"])
            quality_index = int(self.monitors["chord_analyzer_midi_detectedQuality"])
            inversion_index = int(self.monitors["chord_analyzer_midi_detectedInversion"])
            bass_index = int(self.monitors["chord_analyzer_midi_detectedBass"])
        else:
            return
        try:
            chord_text = self.root_labels[root_index] + " " + self.quality_labels[quality_index] + "   (" + self.inversion_labels[inversion_index] + ")"
            self.widget_canvas.itemconfig(self.chord_label, text=chord_text)
            bass_text = "Bass " + self.bass_labels[bass_index]
            self.widget_canvas.itemconfig(self.bass_label, text=bass_text)
        except Exception as e:
            logging.error(f"Can't render result: {root_index}, {quality_index}, {bass_index}, {inversion_index} => {e}")

# ------------------------------------------------------------------------------
