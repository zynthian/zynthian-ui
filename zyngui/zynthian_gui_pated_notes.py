#!/usr/bin/python3
# -*- coding: utf-8 -*-
# ******************************************************************************
# ZYNTHIAN PROJECT: Zynthian GUI
#
# Zynthian GUI Step-Sequencer Pattern Note Editor Class
#
# Copyright (C) 2015-2026 Fernando Moyano <jofemodo@zynthian.org>
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

import os
import json
import tkinter
import logging
from math import ceil
from queue import Queue
from xml.dom import minidom
import tkinter.font as tkfont

# Zynthian specific modules
from zynlibs.zynseq import zynseq
from zyngui import zynthian_gui_config
from zyngui.multitouch import MultitouchTypes
from zyngui.zynthian_gui_pated_base import *
from zyngui.zynthian_gui_base import zynthian_gui_base

# ------------------------------------------------------------------------------

# Event draw modes
EVENT_DRAW_NORMAL = 0       # Draw as normal event
EVENT_DRAW_CP = 1           # Draw as copied into the copy/paste buffer
EVENT_DRAW_SEL = 2          # Draw as selected event

EDIT_PARAM_DUR = 0          # Edit event duration
EDIT_PARAM_VEL = 1          # Edit event velocity
EDIT_PARAM_OFFSET = 2       # Edit event offset
EDIT_PARAM_STUT_SPD = 3     # Edit note stutter speed
EDIT_PARAM_STUT_VFX = 4     # Edit note stutter velocity FX (fade)
EDIT_PARAM_STUT_RMP = 5     # Edit note stutter speed ramp
EDIT_PARAM_PLAY_FREQ = 6    # Edit note play frequency
EDIT_PARAM_PLAY_CHANCE = 7  # Edit note play chance
EDIT_PARAM_STUT_FREQ = 8    # Edit note stutter frequency
EDIT_PARAM_STUT_CHANCE = 9  # Edit note stutter chance
EDIT_PARAM_LAST = 9         # Index of last parameter

STUT_VFX_OPTIONS = (
    "FLAT",
    "FADE-IN",
    "FADE-OUT"
)
STUT_RMP_OPTIONS = (
    "NONE",
    "SPEED-UP",
    "SPEED-DOWN"
)
PLAY_FREQ_OPTIONS = (
    "NEVER",
    "ALWAYS",
    "PLAY/2",
    "SKIP/2",
    "PLAY/3",
    "SKIP/3",
    "PLAY/4",
    "SKIP/4",
    "PLAY/5",
    "SKIP/5",
    "PLAY/6",
    "SKIP/6",
    "PLAY/7",
    "SKIP/7",
    "PLAY/8",
    "SKIP/8"
)
STUT_FREQ_OPTIONS = (
    "NEVER",
    "ALWAYS",
    "STUT/2",
    "SKIP/2",
    "STUT/3",
    "SKIP/3",
    "STUT/4",
    "SKIP/4",
    "STUT/5",
    "SKIP/5",
    "STUT/6",
    "SKIP/6",
    "STUT/7",
    "SKIP/7",
    "STUT/8",
    "SKIP/8"
)

NOTE_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
SCALES = {
    "major": [0, 2, 4, 5, 7, 9, 11, 12, 14, 16, 17, 19, 21, 23],
    "minor": [0, 2, 3, 5, 7, 8, 10, 12, 14, 15, 17, 19, 20, 22]
}

CHORD_MODES = [
    "Single note",
    "Chord",
    "Diatonic triads, major key",
    "Diatonic 7ths, major key",
    "Diatonic triads, minor key",
    "Diatonic 7ths, minor key"
]

CHORDS = [
    # Triads
    ["Major", [0, 4, 7]],
    ["Minor", [0, 3, 7]],
    ["Diminished", [0, 3, 6]],
    ["Augmented", [0, 4, 8]],
    # Seventh chords
    ["Major 7th", [0, 4, 7, 11]],  # (maj7)
    ["Minor 7th", [0, 3, 7, 10]],  # (m7)
    ["Dominant 7th", [0, 4, 7, 10]],  # (7)
    ["Half-Diminished 7th", [0, 3, 6, 10]],  # (m7♭5)
    ["Diminished 7th", [0, 3, 6, 9]],  # (dim7)
    ["Minor-Major 7th", [0, 3, 7, 11]],  # (m(maj7))
    ["Augmented Major 7th", [0, 4, 8, 11]],  # (+maj7)
    ["Augmented 7th", [0, 4, 8, 10]],  # (+7)
    # Extended chords
    ["Major 9th", [0, 4, 7, 11, 14]],  # (maj9)
    ["Dominant 9th", [0, 4, 7, 10, 14]],  # (9)
    ["Minor 9th", [0, 3, 7, 10, 14]],  # (m9)
    ["Minor-Major 9th", [0, 3, 7, 11, 14]],  # (m(maj9))
    ["Dominant 11th", [0, 4, 7, 10, 14, 17]],  # (11)
    ["Minor 11th", [0, 3, 7, 10, 14, 17]],  # (m11)
    ["Dominant 13th", [0, 4, 7, 10, 14, 17, 21]],  # (13)
    ["Minor 13th", [0, 3, 7, 10, 14, 17, 21]],  # (m13)
    # Suspended chords
    ["Suspended 2nd", [0, 2, 7]],  # (sus2)
    ["Suspended 4th", [0, 5, 7]],  # (sus4)
    ["7sus4", [0, 5, 7, 10]],
    # Add chords
    ["Add9", [0, 4, 7, 14]],
    ["Minor Add9", [0, 3, 7, 14]],  # (madd9)
    # 6th chords
    ["Major 6th", [0, 4, 7, 9]],  # (6)
    ["Minor 6th", [0, 3, 7, 9]],  # (m6)
    # Altered 7th chords
    ["Half-Diminished Dominant", [0, 4, 6, 10]]  # (7♭5)
]

# ------------------------------------------------------------------------------
# Zynthian Step-Sequencer Pattern Note Editor GUI Class
# ------------------------------------------------------------------------------


class zynthian_gui_pated_notes(zynthian_gui_pated_base):

    DEFAULT_VIEW_STEPS = 16
    DEFAULT_VIEW_ROWS = 16

    # Function to initialise class
    def __init__(self):
        self.edit_param = EDIT_PARAM_DUR  # Parameter to adjust in parameter edit mode

        # Note-entry values
        self.duration = 1.0
        self.velocity = 100
        self.offset = 0.0
        self.stut_speed = 0
        self.stut_velfx = 0
        self.stut_ramp = 0
        self.play_freq = 1
        self.play_chance = 1.0
        self.stut_freq = 1
        self.stut_chance = 1.0

        self.keymap = []  # Array of {"note":MIDI_NOTE_NUMBER, "name":"key name","colour":"key colour"} name and colour are optional
        self.keymap_offset = 60  # MIDI note number of bottom row in grid
        self.reload_keymap = False  # True when keymap needs reloading
        self.chord_mode = 0  # Chord entry mode. 0 for single note entry
        self.chord_type = 0  # Chord type. Index of CHORD
        self.diatonic_scale_tonic = 0  # Tonic of diatonic scale used for chords
        self.rows_pending = Queue()

        # Touch control variables
        self.drag_start_velocity = None  # Velocity value at start of drag
        self.drag_note = False  # True if dragging note in grid
        self.drag_velocity = False  # True indicates drag will adjust velocity
        self.drag_duration = False  # True indicates drag will adjust duration

        super().__init__()

    # Function to get name of this view
    def get_name(self):
        return "pated note"

    def get_title(self):
        title = super().get_title()
        if self.chord_mode:
            return f"{title}: Chords"
        else:
            return f"{title}: Notes"

    def get_evnum_from_row(self, row):
        try:
            return self.keymap[row]["note"]
        except:
            return None

    def get_row_from_evnum(self, num):
        for row in range(0, len(self.keymap)):
            if self.keymap[row]["note"] == num:
                return row
        return None

    get_note_from_row = get_evnum_from_row
    get_row_from_note = get_row_from_evnum

    def get_diatonic_chord(self, trigger_note):
        chord = []
        match self.chord_mode:
            case 2 | 3:
                scale_template = SCALES["major"]
            case 4 | 5:
                scale_template = SCALES["minor"]
            case _:
                return []
        if self.chord_mode in [3, 5]:
            chord_len = 4
        else:
            chord_len = 3
        scale_offset = trigger_note % 12 + self.diatonic_scale_tonic
        if scale_offset not in scale_template:
            return []  # Trigger note not in diatonic scale
        note_offset = scale_template.index(scale_offset)
        for i in range(chord_len):
            chord.append(scale_template[note_offset + 2 * i] - scale_template[note_offset])
        return chord

    def play_note(self, note):
        if self.zynseq.libseq.getPlayState(self.zynseq.scene, self.phrase, self.sequence) == zynseq.SEQ_STOPPED:
            self.zynseq.libseq.playNote(note, self.velocity, self.channel, int(200 * self.duration))

    # -------------------------------------------------------------------------
    # Pattern menu
    # -------------------------------------------------------------------------

    def get_menu_options(self):
        menu_options = super().get_menu_options()
        # Pattern Options
        options = {}
        options[f"Velocity Humanization ({int(self.zynseq.libseq.getHumanVelo())})"] = 'Velocity Humanization'
        options[f"Note Play Chance ({round(100 * self.zynseq.libseq.getPlayChance())}%)"] = 'Note Play Chance'
        scales = self.get_scales()
        options[f"Scale ({scales[self.zynseq.libseq.getScale()]})"] = 'Scale'
        options[f"Tonic ({NOTE_NAMES[self.zynseq.libseq.getTonic()]})"] = 'Tonic'
        menu_options['PATTERN'].update(options)
        # Pattern Edit
        options = {}
        note = self.zynseq.libseq.getInputRest()
        if note < 128:
            options[f"Rest-step note ({NOTE_NAMES[note % 12]}{note // 12 - 1})"] = 'Rest note'
        else:
            options["Rest note (None)"] = 'Rest note'
        options[f"Chord mode ({CHORD_MODES[self.chord_mode]})"] = 'Chord mode'
        if self.chord_mode == 1:
            options[f"Chord type ({CHORDS[self.chord_type][0]})"] = 'Chord type'
        elif self.chord_mode >= 2:
            options[f"Diatonic key ({NOTE_NAMES[self.diatonic_scale_tonic]})"] = 'Chord type'
        options['Transpose pattern'] = 'Transpose pattern'
        options.update(menu_options['EDIT'])
        options['Clear pattern notes'] = 'Clear pattern notes'
        menu_options['EDIT'] = options
        return menu_options

    def menu_cb(self, option, params):
        self.save_last_menu_option()
        match params:
            case 'Velocity Humanization':
                self.enable_param_editor(self, 'human_vel', {'name': 'Velocity Humanization', 'value_min': 0,
                                                              'value_max': 100, 'value_default': 0,
                                                              'value': int(self.zynseq.libseq.getHumanVelo())})

            case 'Note Play Chance':
                self.enable_param_editor(self, 'play_chance', {'name': 'Note Play Chance', 'value_min': 0,
                                                               'value_max': 100, 'value_default': 100,
                                                               'value': round(100.0 * self.zynseq.libseq.getPlayChance())})

            case 'Scale':
                self.enable_param_editor(self, 'scale', {'name': 'Scale', 'labels': self.get_scales(),
                                                         'value': self.zynseq.libseq.getScale()})
            case 'Tonic':
                self.enable_param_editor(self, 'tonic', {'name': 'Tonic', 'labels': NOTE_NAMES,
                                                         'value': self.zynseq.libseq.getTonic()})
            case 'Rest note':
                labels = ['None']
                for note in range(128):
                    labels.append("{}{}".format(NOTE_NAMES[note % 12], note // 12 - 1))
                value = self.zynseq.libseq.getInputRest() + 1
                if value > 128:
                    value = 0
                self.enable_param_editor(self, 'rest', {'name': 'Rest-step note', 'labels': labels, 'value': value})
            case 'Chord mode':
                self.enable_param_editor(self, 'chord_mode', {'name': 'Chord mode', 'labels': CHORD_MODES,
                                                              'value': self.chord_mode})
            case 'Chord type':
                if self.chord_mode == 1:
                    self.enable_param_editor(self, 'chord_type', {'name': 'Chord type',
                                                                  'labels': [item[0] for item in CHORDS],
                                                                  'value': self.chord_type})
                elif self.chord_mode >= 2:
                    self.enable_param_editor(self, 'diatonic_key', {'name': 'Diatonic key', 'labels': NOTE_NAMES,
                                                                    'value': self.diatonic_scale_tonic})
            case 'Transpose pattern':
                    self.enable_param_editor(self, 'transpose', {'name': 'Transpose', 'value_min': -1, 'value_max': 1,
                                                                 'labels': ['down', 'down/up', 'up'], 'value': 0})
            case 'Clear pattern notes':
                self.clear_pattern_notes()
            case _:
                super().menu_cb(option, params)

    def send_controller_value(self, zctrl):
        match zctrl.symbol:
            case 'human_vel':
                self.zynseq.libseq.setHumanVelo(1.0 * zctrl.value)
            case 'play_chance':
                self.zynseq.libseq.setPlayChance(zctrl.value / 100.0)
            case 'transpose':
                self.transpose(zctrl.value)
                zctrl.set_value(0)
            case 'scale':
                self.set_scale(zctrl.value)
            case 'tonic':
                self.set_tonic(zctrl.value)
            case 'rest':
                if zctrl.value == 0:
                    self.zynseq.libseq.setInputRest(128)
                else:
                    self.zynseq.libseq.setInputRest(zctrl.value - 1)
            case 'chord_mode':
                self.chord_mode = zctrl.value
            case 'chord_type':
                self.chord_type = zctrl.value
            case 'diatonic_key':
                self.diatonic_scale_tonic = zctrl.value
            case _:
                super().send_controller_value(zctrl)

    # Function to transpose pattern
    def transpose(self, offset):
        if offset != 0:
            self.save_pattern_snapshot(now=True, force=False)
            if self.zynseq.libseq.getScale():
                # Change to chromatic scale to transpose
                self.zynseq.libseq.setScale(0)
                self.load_keymap()
            self.zynseq.libseq.transpose(offset)
            self.save_pattern_snapshot(now=True, force=True)
            self.set_keymap_offset(self.keymap_offset + offset)
            self.selected_cell[1] += int(offset)
            self.redraw_pending = 3
            self.select_cell()

    # -------------------------------------------------------------------------
    # Pattern management
    # -------------------------------------------------------------------------

    # Function to load new pattern
    # index: Pattern index
    def load_pattern(self, index):
        # Load requested pattern
        self.zynseq.libseq.selectPattern(index)
        self.pattern = index
        self.selected_events = None
        self.block_copied = None
        n_steps = self.zynseq.libseq.getSteps()
        n_steps_beat = self.zynseq.libseq.getStepsPerBeat()
        keymap_len = len(self.keymap)
        self.load_keymap()
        if n_steps != self.n_steps or n_steps_beat != self.n_steps_beat or len(self.keymap) != keymap_len:
            self.n_steps = n_steps
            self.n_steps_beat = n_steps_beat
            self.step_offset = 0
            self.update_geometry()
            if self.duration > n_steps:
                self.duration = 1
            keymap_len = len(self.keymap)
            self.redraw_pending = 4
        else:
            self.redraw_pending = 3

        # Vertical position => keymap_offset
        if keymap_len > self.view_rows:
            self.keymap_offset = int(self.zynseq.libseq.getRefNote())
        else:
            self.keymap_offset = 0
            self.zynseq.libseq.setRefNote(0)
        self.set_keymap_offset()

        # Selected cell
        if self.selected_cell[0] >= n_steps:
            self.selected_cell[0] = int(n_steps) - 1
        self.selected_cell[1] = int(self.keymap_offset + self.view_rows / 2)

        # Draw grid and adjust zoom
        self.draw_grid()
        self.set_grid_zoom(self.zynseq.libseq.getPatternZoom())

        self.play_canvas.coords("playCursor", 1, 0, 1 + self.step_width, PLAYHEAD_HEIGHT)
        self.set_title()
        if not self.seq_info:
            # Populate editor sequence
            self.zynseq.libseq.clearSequence(self.zynseq.scene, self.phrase, self.sequence)
            self.zynseq.libseq.addPattern(self.zynseq.scene, self.phrase, self.sequence, 0, 0, index, True)
            self.zynseq.libseq.setChannel(self.zynseq.scene, self.phrase, self.sequence, 0, self.channel)

    # Function to clear Note events on pattern
    def clear_pattern_notes(self, params=None):
        self.zyngui.show_confirm(f"Clear notes in pattern {self.pattern}?", self.do_clear_pattern_notes)

    # Function to actually clear CC events
    def do_clear_pattern_notes(self, params=None):
        self.save_pattern_snapshot(now=True, force=False)
        self.zynseq.libseq.clearNotes()
        self.save_pattern_snapshot(now=True, force=True)
        self.select_cell()

    # -------------------------------------------------------------------------
    # Scales and keymap
    # -------------------------------------------------------------------------

    # Function to set musical scale
    #   scale: Index of scale to load
    #   Returns: name of scale
    def set_scale(self, scale):
        self.zynseq.libseq.setScale(scale)
        self.reload_keymap = True
        self.redraw_pending = 3

    # Function to set tonic (root note) of scale
    # tonic: Scale root note
    def set_tonic(self, tonic):
        self.zynseq.libseq.setTonic(tonic)
        self.reload_keymap = True
        self.redraw_pending = 3

    # Function to get list of scales
    # returns: List of available scales
    def get_scales(self):
        # Load scales
        data = []
        try:
            with open(CONFIG_ROOT + "/scales.json") as json_file:
                data = json.load(json_file)
        except:
            logging.warning("Unable to open scales.json")
        res = []
        # Look for a custom keymap, defaults to chromatic
        custom_keymap = self.get_custom_keymap()
        if custom_keymap:
            res.append(f"Custom - {custom_keymap[0]}")
        else:
            res.append(f"Custom - None")
        for scale in data:
            res.append(scale['name'])
        return res

    # Search for a custom map and return a tuple with [map_name, filepath / engine]
    def get_custom_keymap(self):
        synth_proc = self.zyngui.chain_manager.get_synth_processor(self.channel)
        if synth_proc:
            # Ask the synth processor for a keymap
            try:
                keymap_name = synth_proc.get_keymap_name()
            except:
                keymap_name = None
            if keymap_name:
                return [keymap_name, synth_proc]
            # else, try to find a midnam file
            else:
                map_name = None
                preset_path = synth_proc.get_presetpath()
                try:
                    with open(CONFIG_ROOT + "/keymaps.json") as json_file:
                        data = json.load(json_file)
                        for pat in data:
                            if pat in preset_path:
                                map_name = data[pat]
                                break
                    if map_name:
                        keymap_fpath = CONFIG_ROOT + f"/{map_name}.midnam"
                        if os.path.isfile(keymap_fpath):
                            return [map_name, keymap_fpath]
                        else:
                            logging.warning(f"Keymap file {keymap_fpath} doesn't exist.")
                except:
                    logging.warning("Unable to load keymaps.json")
        else:
            logging.info(f"MIDI channel {self.channel} has not synth processors.")

    # Function to populate keymap array
    # returns Name of scale / map
    def load_keymap(self):
        self.keymap = []

        scale = self.zynseq.libseq.getScale()
        tonic = self.zynseq.libseq.getTonic()

        # Try to load custom keymap
        if scale == 0:
            map_info = self.get_custom_keymap()
            if map_info:
                map_name = map_info[0]
                # map_info[1] is the filename of a midnam file
                if isinstance(map_info[1], str) and map_info[1].endswith(".midnam"):
                    keymap_fpath = map_info[1]
                    logging.info(f"Loading keymap {map_name} for MIDI channel {self.channel}...")
                    try:
                        xml = minidom.parse(keymap_fpath)
                        notes = xml.getElementsByTagName('Note')
                        for note in notes:
                            try:
                                colour = note.attributes['Colour'].value
                            except:
                                colour = "white"
                            self.keymap.append({'note': int(note.attributes['Number'].value),
                                                'name': note.attributes['Name'].value,
                                                'colour': colour})
                        return map_name
                    except Exception as e:
                        logging.error(f"Can't load '{keymap_fpath}' => {e}")
                # map[1] is an engine to ask for a custom keymap
                else:
                    try:
                        self.keymap = map_info[1].get_keymap()
                        return map_name
                    except:
                        pass

        # Not custom map loaded => Setup a scale keymap

        # Setup specific scale
        if scale > 1:
            try:
                with open(CONFIG_ROOT + "/scales.json") as json_file:
                    data = json.load(json_file)
                if scale <= len(data):
                    scale -= 1  # Offset by -1 because the 0 is used for custom keymap
                    for octave in range(0, 9):
                        for offset in data[scale]['scale']:
                            note = tonic + offset + octave * 12
                            if note > 127:
                                break
                            self.keymap.append({"note": note, "name": "{}{}".format(NOTE_NAMES[note % 12], note // 12 - 1)})
                    return data[scale]['name']
            except Exception as e:
                logging.error(f"Can't load 'scales.json' => {e}")

        # Setup chromatic scale
        for note in range(0, 128):
            new_entry = {"note": note}
            key = note % 12
            if key in (1, 3, 6, 8, 10):  # Black notes
                new_entry.update({"colour": "black"})
            else:
                new_entry.update({"colour": "white"})
            if key == 0:  # 'C'
                new_entry.update({"name": "C{}".format(note // 12 - 1)})
            self.keymap.append(new_entry)
        return "Chromatic"

    # -------------------------------------------------------------------------
    # Touch event management
    # -------------------------------------------------------------------------

    # Function to handle pianoroll drag motion
    def on_pianoroll_motion(self, event):
        offset = super().on_pianoroll_motion(event)
        self.set_keymap_offset(self.keymap_offset + offset)
        if self.selected_cell[1] < self.keymap_offset:
            self.selected_cell[1] = self.keymap_offset
        elif self.selected_cell[1] >= self.keymap_offset + int(self.view_rows):
            self.selected_cell[1] = self.keymap_offset + int(self.view_rows) - 1
        self.select_cell()
        return offset

    def on_pianoroll_release_action(self, event):
        # Play note if not drag action
        row = int((self.total_height - self.piano_roll.canvasy(event.y)) / self.row_height)
        if row < len(self.keymap):
            note = self.keymap[row]['note']
            self.play_note(note)
            self.pianoroll_note_on(note)
            zynthian_gui_config.top.after(200, self.pianoroll_note_off, note)


    # Function to handle mouse wheel over pianoroll
    def on_pianoroll_wheel(self, event):
        if event.num == 4:
            # Scroll up
            if self.keymap_offset + self.view_rows < len(self.keymap):
                self.set_keymap_offset(self.keymap_offset + 1)
                if self.selected_cell[1] < self.keymap_offset:
                    self.select_cell(self.selected_cell[0], self.keymap_offset)
        else:
            # Scroll down
            if self.keymap_offset > 0:
                self.set_keymap_offset(self.keymap_offset - 1)
                if self.selected_cell[1] >= self.keymap_offset + self.view_rows:
                    self.select_cell(self.selected_cell[0], self.keymap_offset + self.view_rows - 1)

    # Function to handle grid mouse down
    # event: Mouse event
    def on_grid_press(self, event):
        if self.param_editor_zctrl:
            self.disable_param_editor()

        # Select cell
        row = int((self.total_height - self.grid_canvas.canvasy(event.y)) / self.row_height)
        step = int(self.grid_canvas.canvasx(event.x) / self.step_width)
        try:
            note = self.keymap[row]['note']
        except:
            return
        start_step = self.zynseq.libseq.getNoteStart(step, note)
        if start_step >= 0:
            step = start_step
        if step < 0 or step >= self.n_steps:
            return
        self.select_cell(step, row)

        # Start drag state variables
        self.swiping = False
        self.grid_drag_start = event
        self.grid_drag_count = 0
        self.swipe_step_speed = 0
        self.swipe_row_speed = 0
        self.swipe_step_dir = 0
        self.swipe_row_dir = 0
        self.drag_note = False
        self.drag_velocity = False
        self.drag_duration = False
        self.drag_start_step = step
        self.drag_start_velocity = self.zynseq.libseq.getNoteVelocity(step, note)
        self.drag_start_duration = self.zynseq.libseq.getNoteDuration(step, note)

    # Function to handle grid mouse drag
    # event: Mouse event
    def on_grid_drag(self, event):
        if not self.grid_drag_start:
            return
        if self.grid_drag_count == 0 and abs(event.x - self.grid_drag_start.x) < 2 or \
                abs(event.y - self.grid_drag_start.y) < 2:
            # Avoid interpretting tap as drag (especially on V4 touchscreen)
            return
        self.grid_drag_count += 1

        if self.drag_note:
            step = self.selected_cell[0]
            row = self.selected_cell[1]
            note = self.keymap[row]['note']
            sel_duration = self.zynseq.libseq.getNoteDuration(step, note)
            sel_velocity = self.zynseq.libseq.getNoteVelocity(step, note)

            if self.drag_start_velocity:
                # Selected cell has a note, so we want to adjust its velocity or duration
                if not self.drag_velocity and not self.drag_duration and\
                        (event.x > (self.drag_start_step + 1) * self.step_width or
                         event.x < self.drag_start_step * self.step_width):
                    self.drag_duration = True
                if not self.drag_duration and not self.drag_velocity and\
                        (event.y > self.grid_drag_start.y + self.row_height / 2 or
                         event.y < self.grid_drag_start.y - self.row_height / 2):
                    self.drag_velocity = True
                if self.drag_velocity:
                    value = (self.grid_drag_start.y - event.y) / self.row_height
                    velocity = int(self.drag_start_velocity + value * self.height / 100)
                    if 1 <= velocity <= 127:
                        self.set_velocity_indicator(velocity)
                        if sel_duration and velocity != sel_velocity:
                            self.zynseq.libseq.setNoteVelocity(step, note, velocity)
                            self.draw_cell(step, row)
                if self.drag_duration:
                    duration = int(event.x / self.step_width) - self.drag_start_step
                    if duration > 0 and duration != sel_duration:
                        self.add_note_event(step, row, sel_velocity, duration)
                    else:
                        # self.duration = duration
                        pass
            else:
                # Clicked on empty cell so want to add a new note by dragging towards the desired cell
                # x pos of start of event
                x1 = self.selected_cell[0] * self.step_width
                x2 = x1 + self.step_width  # x pos right of event's first cell
                # y pos of bottom of selected row
                y1 = self.total_height - self.selected_cell[1] * self.row_height
                y2 = y1 - self.row_height  # y pos of top of selected row
                event_x = self.grid_canvas.canvasx(event.x)
                event_y = self.grid_canvas.canvasy(event.y)
                if event_x < x1:
                    self.select_cell(self.selected_cell[0] - 1, None)
                elif event_x > x2:
                    self.select_cell(self.selected_cell[0] + 1, None)
                elif event_y > y1:
                    self.select_cell(None, self.selected_cell[1] - 1)
                    self.play_note(self.keymap[self.selected_cell[1]]["note"])
                elif event_y < y2:
                    self.select_cell(None, self.selected_cell[1] + 1)
                    self.play_note(self.keymap[self.selected_cell[1]]["note"])
        else:
            step_offset = int(DRAG_SENSIBILITY * (self.grid_drag_start.x - event.x) / self.step_width)
            row_offset = int(DRAG_SENSIBILITY * (event.y - self.grid_drag_start.y) / self.row_height)
            if step_offset == 0 and row_offset == 0:
                if self.grid_drag_count < 2 and (event.time - self.grid_drag_start.time) > 800:
                    self.drag_note = True
                return
            self.swiping = True
            self.grid_drag_start = event
            if step_offset:
                self.swipe_step_dir = step_offset
                self.set_step_offset(self.step_offset + step_offset)
            if row_offset:
                self.swipe_row_dir = row_offset
                self.set_keymap_offset(self.keymap_offset + row_offset)
                if self.selected_cell[1] < self.keymap_offset:
                    self.selected_cell[1] = self.keymap_offset
                elif self.selected_cell[1] >= self.keymap_offset + int(self.view_rows):
                    self.selected_cell[1] = self.keymap_offset + int(self.view_rows) - 1
            self.select_cell()

    # Function to handle grid mouse release
    # event: Mouse event
    def on_grid_release(self, event):
        # No drag actions
        if self.grid_drag_start:
            dts = event.time - self.grid_drag_start.time
            if self.grid_drag_count == 0:
                # Bold click without drag
                if dts > 800:
                    if self.edit_mode == EDIT_MODE_NONE:
                        self.set_edit_mode(EDIT_MODE_SINGLE)
                    else:
                        self.set_edit_mode(EDIT_MODE_MULTI)
                # Short click without drag: Add/remove single note/chord
                else:
                    step = self.selected_cell[0]
                    row = self.selected_cell[1]
                    self.toggle_event(step, row)
            # End drag action
            elif self.drag_note:
                if not self.drag_start_velocity:
                    # Drag drop note
                    step = self.selected_cell[0]
                    row = self.selected_cell[1]
                    # note = self.keymap[row]['note']
                    self.toggle_event(step, row)
            # Swipe
            elif self.swiping:
                self.swipe_nudge(dts/1000)

        # Reset drag state variables
        self.grid_drag_start = None
        self.grid_drag_count = 0
        self.drag_note = False
        self.drag_velocity = False
        self.drag_duration = False
        self.drag_start_step = None
        self.drag_start_velocity = None
        self.drag_start_duration = None

    def on_gesture(self, gtype, value):
        if gtype == MultitouchTypes.GESTURE_H_DRAG:
            value = int(-0.1 * value)
            self.set_step_offset(self.step_offset + value)
            self.select_cell()
        elif gtype == MultitouchTypes.GESTURE_V_DRAG:
            value = int(0.1 * value)
            self.set_keymap_offset(self.keymap_offset + value)
            if self.selected_cell[1] < self.keymap_offset:
                self.selected_cell[1] = self.keymap_offset
            elif self.selected_cell[1] >= self.keymap_offset + int(self.view_rows):
                self.selected_cell[1] = self.keymap_offset + int(self.view_rows) - 1
            self.select_cell()
        elif gtype in (MultitouchTypes.GESTURE_H_PINCH, MultitouchTypes.GESTURE_V_PINCH):
            value = int(0.1 * value)
            self.set_grid_zoom(self.zoom + value)

    # Update swipe vertical scroll
    def swipe_vertical_action(self):
        self.keymap_offset += int(self.swipe_row_offset)
        self.swipe_row_offset -= int(self.swipe_row_offset)
        self.set_keymap_offset(self.keymap_offset)
        if self.selected_cell[1] < self.keymap_offset:
            self.selected_cell[1] = self.keymap_offset
        elif self.selected_cell[1] >= self.keymap_offset + int(self.view_rows):
            self.selected_cell[1] = self.keymap_offset + int(self.view_rows) - 1

    # -------------------------------------------------------------------------
    # Geometry management
    # -------------------------------------------------------------------------

    def calculate_geometry_limits(self):
        self.n_rows = len(self.keymap)
        super().calculate_geometry_limits()

    # Function to set kaymap offset and move grid view accordingly
    # offset: Keymap Offset (note at bottom row)
    def set_keymap_offset(self, offset=None):
        max_keymap_offset = max(0, len(self.keymap) - self.view_rows)
        if offset is not None:
            self.keymap_offset = int(offset)
        if self.keymap_offset > max_keymap_offset:
            self.keymap_offset = int(max_keymap_offset)
        elif self.keymap_offset < 0:
            self.keymap_offset = 0
        ypos = (self.scroll_height - self.keymap_offset * self.row_height) / self.total_height
        self.grid_canvas.yview_moveto(ypos)
        self.piano_roll.yview_moveto(ypos)
        self.zynseq.libseq.setRefNote(int(self.keymap_offset))
        #logging.debug(f"OFFSET: {self.keymap_offset} (keymap length: {len(self.keymap)})")
        #logging.debug(f"GRID Y-SCROLL: {ypos}\n\n")

    # Update grid position
    def update_grid_position(self, step_width_changed, row_height_changed):
        if step_width_changed:
            self.set_step_offset()
        if row_height_changed:
            self.set_keymap_offset()
        self.view_rows = self.grid_height // self.row_height
        self.view_steps = self.grid_width // self.step_width

    # Reset grid offset
    def reset_grid_offset(self):
        self.set_keymap_offset()
        self.set_step_offset()

    def set_grid_zoom(self, new_zoom=0):
        res = super().set_grid_zoom(new_zoom)
        self.zynseq.libseq.setPatternZoom(self.zoom)
        return res

    # -------------------------------------------------------------------------
    # Drawing functions
    # -------------------------------------------------------------------------

    # Function to adjust velocity indicator
    # velocity: Note velocity to indicate
    def set_velocity_indicator(self, velocity):
        self.velocity_canvas.coords("velocityIndicator", 0, 0, self.piano_roll_width * velocity / 127, PLAYHEAD_HEIGHT)

    # Draw all note events in pattern
    def draw_events(self):
        self.zynseq.libseq.isPatternModified()
        self.grid_canvas.delete("pat")
        evdata = zynseq.event_data()
        index = 0
        while True:
            res = self.zynseq.libseq.getEventDataAt(index, evdata)
            if res < 0:
                break
            #logging.debug(f"DRAWING EVENT AT {index} => {evdata.position}, {evdata.command}")
            if evdata.command == zynseq.MIDI_NOTE_ON:
                if self.selected_events and index in self.selected_events:
                    self.draw_event(evdata, EVENT_DRAW_SEL)
                else:
                    self.draw_event(evdata, EVENT_DRAW_NORMAL)
            index += 1

    # Draw all note events in the copy/paste buffer
    def draw_cp_events(self):
        self.grid_canvas.delete("cp")
        if self.block_copied:
            evdata = zynseq.event_data()
            index = 0
            while True:
                res = self.zynseq.libseq.getBufferEventDataAt(index, evdata)
                if res < 0:
                    break
                #logging.debug(f"DRAWING CP EVENT AT {index} => {evdata.position}, {evdata.command}")
                if evdata.command == zynseq.MIDI_NOTE_ON:
                    #evdata.position += self.block_dstep
                    evdata.val1_start += self.block_drow
                    #if 0 <= evdata.position < self.n_steps and 0 <= evdata.val1_start <= 127:
                    # Horizontal "circular" displaying
                    if 0 <= evdata.val1_start <= 127:
                        pos = evdata.position + self.block_dstep
                        if pos >= self.n_steps:
                            pos -= self.n_steps
                        elif pos < 0:
                            pos += self.n_steps
                        evdata.position = pos
                        self.draw_event(evdata, EVENT_DRAW_CP)
                index += 1

    # Draw an event
    # evdata: Event data
    # mode: draw mode => EVENT_DRAW_NORMAL, EVENT_DRAW_CP, EVENT_DRAW_SEL
    # row: row index (optimization parameter)
    def draw_event(self, evdata, mode=EVENT_DRAW_NORMAL, row=None):
        step = evdata.position
        # Calculate row if needed:
        if row is None:
            row = self.get_row_from_note(evdata.val1_start)
            # Nothing to plot is event's note hasn't a row
            if row is None:
                return

        #logging.debug(f"DRAWING EVENT AT CELL {step}, {row}")

        velocity_colour = evdata.val2_start + 70
        if mode == EVENT_DRAW_CP:
            cell_tag = f"cp_{step},{row}"
            cell_tags = (cell_tag, f"step{step}", "gridcell", "cp")
            fill_colour = f"#{velocity_colour//2:02x}{velocity_colour:02x}{velocity_colour//2:02x}"
        else:
            cell_tag = f"pat_{step},{row}"
            cell_tags = (cell_tag, f"step{step}", "gridcell", "pat")
            if mode == EVENT_DRAW_SEL:
                fill_colour = f"#{velocity_colour//2:02x}{velocity_colour//2:02x}{velocity_colour:02x}"
            else:
                fill_colour = f"#{velocity_colour:02x}{velocity_colour:02x}{velocity_colour:02x}"
        if evdata.play_freq == 0 or evdata.play_chance == 0:
            stipple = 'gray12'
        else:
            stipple = ''

        coord = self.get_cell(step, row, evdata.duration, evdata.offset)
        cells = self.grid_canvas.find_withtag(cell_tag)
        if cells:
            # Update existing cell
            self.grid_canvas.coords(cells[0], coord)
            self.grid_canvas.itemconfig(cells[0], fill=fill_colour, stipple=stipple, tags=cell_tags)
        else:
            # Create new cell
            self.grid_canvas.create_rectangle(coord, width=0, fill=fill_colour, stipple=stipple, tags=cell_tags)

        # Redraw cell decoration
        deco_tag = f"deco_{cell_tag}"
        self.grid_canvas.delete(deco_tag)
        deco_tags = cell_tags + (deco_tag,)
        self._draw_cell_deco(coord, fill_colour, evdata, deco_tags)

        if step + evdata.duration > self.n_steps:
            self.grid_canvas.itemconfig(f"lastnotetext{row}", text=f"+{evdata.duration - self.n_steps + step}", state="normal")

    def _draw_cell_deco(self, coord, fill_color, evdata, tags):
        # bright background - dark text
        #if (zynthian_gui_config.get_color_lux(fill_color) > 0.5):
        if (evdata.val2_start >= 58):
            deco_color = "#101010"
        # dark background - light text
        else:
            deco_color = "#E0E0E0"

        if evdata.stut_speed > 0:
            if evdata.stut_freq == 0 or evdata.stut_chance == 0:
                stipple = 'gray25'
            else:
                stipple = ''
            dx = self.step_width //  (2 * evdata.stut_speed)
            if dx < 2:
                dx = 2
            # Flat
            if evdata.stut_velfx == 0:
                w = self.row_height // 2
                y = coord[3] - w // 2
                self.grid_canvas.create_line(coord[0] + 1, y, coord[2] - 1, y,
                                             fill=deco_color, stipple=stipple, width=w, dash=(dx, dx), dashoffset=dx, tags=tags)
                label_anchor = tkinter.CENTER
                label_x = (coord[0] + coord[2]) // 2
            else:
                w = self.row_height - 1
                y = (coord[1] + coord[3]) // 2
                self.grid_canvas.create_line(coord[0] + 1, y, coord[2] - 1, y,
                                             fill=deco_color, stipple=stipple, width=w, dash=(dx, dx), dashoffset=dx, tags=tags)
                # Fade-in
                if evdata.stut_velfx == 1:
                    self.grid_canvas.create_polygon(coord[0], coord[1], coord[2], coord[1], coord[0], coord[3],
                                                    fill=fill_color, tags=tags)
                    label_anchor = tkinter.W
                    label_x = coord[0]
                # Fade-out
                elif evdata.stut_velfx == 2:
                    self.grid_canvas.create_polygon(coord[0], coord[1], coord[2], coord[3], coord[2], coord[1],
                                                    fill=fill_color, tags=tags)
                    label_anchor = tkinter.E
                    label_x = coord[2]
        else:
            label_anchor = tkinter.CENTER
            label_x = (coord[0] + coord[2]) // 2

        label_txt = None
        if evdata.play_freq > 1:
            label_txt = PLAY_FREQ_OPTIONS[evdata.play_freq]
        elif evdata.play_chance < 1.0:
            label_txt = f"{round(100 * evdata.play_chance)}%"
        elif evdata.stut_speed > 0:
            if evdata.stut_freq > 1:
                label_txt = STUT_FREQ_OPTIONS[evdata.stut_freq]
            elif evdata.stut_chance < 1.0:
                label_txt = f"{round(100 * evdata.stut_chance)}%"
        if label_txt:
            label_y = (coord[1] + coord[3]) // 2
            self.grid_canvas.create_text(label_x, label_y,
                                         fill=deco_color, text=label_txt, anchor=label_anchor, tags=tags)

    # Function to draw a grid row
    # row: Row number (keymap index)
    def draw_row(self, row):
        # Flush modified flag to avoid refresh redrawing whole grid => Is this OK?
        self.zynseq.libseq.isPatternModified()

        self.grid_canvas.itemconfig(f"lastnotetext{row}", state="hidden")
        for step in range(self.n_steps):
            self._draw_cell(step, row)

    def draw_cell(self, step, row):
        # Flush modified flag to avoid refresh redrawing whole grid => Is this OK?
        self.zynseq.libseq.isPatternModified()
        # Call _draw_cell
        self._draw_cell(step, row)

    # Function to draw a grid cell
    # step: Step (column) index
    # row: Index of row
    def _draw_cell(self, step, row):
        note = self.keymap[row]["note"]
        if self.block_copied:
            evdata = self.zynseq.get_note_data(step - self.block_dstep, note - self.block_drow, True)
        else:
            evdata = None
        if evdata:
            mode = EVENT_DRAW_CP
        else:
            index = self.zynseq.libseq.getNoteIndex(step, note)
            if index >= 0:
                evdata = zynseq.event_data()
                self.zynseq.libseq.getEventDataAt(index, evdata)
                if self.selected_events and index in self.selected_events:
                    mode = EVENT_DRAW_SEL
                else:
                    mode = EVENT_DRAW_NORMAL
            else:
                mode = EVENT_DRAW_NORMAL
                evdata = None
        if evdata:
            self.draw_event(evdata, mode, row)
        else:
            if mode == EVENT_DRAW_CP:
                self.grid_canvas.delete(f"cp_{step},{row}")
            else:
                self.grid_canvas.delete(f"pat_{step},{row}")

    def redraw_grid_pending(self):
        if self.grid_rows != len(self.keymap) or self.grid_steps != self.n_steps:
            self.grid_rows = len(self.keymap)
            self.grid_steps = self.n_steps
            self.grid_canvas.delete(tkinter.ALL)
            self.rect_selected_cell = None
            self.rect_selected_block = None
            self.draw_pianoroll()
            self.redraw_pending = 4
            self.play_canvas.coords("playCursor", 1 + self.playhead * self.step_width,
                                    0, 1 + self.step_width * (self.playhead + 1), PLAYHEAD_HEIGHT)

        super().redraw_grid_pending()

        if self.redraw_pending > 1:
            if self.redraw_pending > 3:
                self.piano_roll.delete("notename")
                self.grid_canvas.delete("gridhline")

            if self.redraw_pending > 2:
                row_min = 0
                row_max = len(self.keymap)
            else:
                row_min = self.selected_cell[1]
                row_max = self.selected_cell[1]

            for row in range(row_min, row_max):
                # Create last note labels in grid
                self.grid_canvas.create_text(self.total_width - self.select_thickness,
                                             int(self.row_height * (row - 0.5)),
                                             state=tkinter.HIDDEN, font=self.grid_font, anchor=tkinter.E,
                                             tags=(f"lastnotetext{row}", "lastnotetext", "gridcell"))
                if self.redraw_pending > 3:
                    self.pianoroll_set_row(row)
                    ypos = self.total_height - row * self.row_height
                    if self.keymap[row]['note'] % 12 == self.zynseq.libseq.getTonic():
                        self.grid_canvas.create_line(0, ypos, self.total_width, ypos, fill=GRID_LINE_STRONG, tags="gridhline")
                    else:
                        self.grid_canvas.create_line(0, ypos, self.total_width, ypos, fill=GRID_LINE_WEAK, tags="gridhline")

                # Draw row of note cells
                if self.redraw_pending <= 2:
                    self.draw_row(row)

            # Draw all notes
            if self.redraw_pending > 2:
                self.draw_events()

            # Set z-order to avoid vertical inlines overlapping note cells
            if self.redraw_pending > 2:
                self.grid_canvas.tag_lower("gridvline")

    # Function to draw pianoroll key outlines (does not fill key colour)
    def draw_pianoroll(self):
        self.piano_roll.delete(tkinter.ALL)
        for row in range(0, len(self.keymap)):
            x1 = 0
            y1 = self.total_height - (row + 1) * self.row_height + 1
            x2 = self.piano_roll_width
            y2 = y1 + self.row_height - 1
            tags = f"row{row}"
            self.piano_roll.create_rectangle(x1, y1, x2, y2, width=0, tags=tags)

    def pianoroll_set_row(self, row, color=None):
        row_id = f"row{row}"
        try:
            name = self.keymap[row]["name"]
        except:
            name = None
        if color is None:
            if "colour" in self.keymap[row]:
                color = self.keymap[row]["colour"]
            elif name and "#" in name:
                color = "black"
            else:
                color = "white"
            if color == "black":
                fill = "white"
            else:
                fill = CANVAS_BACKGROUND
        else:
            fill = CANVAS_BACKGROUND
        self.piano_roll.itemconfig(row_id, fill=color)
        # name = str(row)
        if name:
            tag = f"notename{row}"
            res = self.piano_roll.find_withtag(tag)
            if res:
                self.piano_roll.itemconfig(res[0], fill=fill)
            else:
                ypos = self.total_height - row * self.row_height
                self.piano_roll.create_text(2, ypos - 0.5 * self.row_height, text=name, font=self.grid_font,
                                            anchor="w", fill=fill, tags=(tag, "notename"))

    def pianoroll_note_on(self, note):
        # Highlight the note key
        row = self.get_row_from_note(note)
        if row is not None:
            self.pianoroll_set_row(row, "#40FF40")

        # Re-center vertically if note is off the view area
        if not self.keymap_offset <= row < self.keymap_offset + self.view_rows:
            self.set_keymap_offset(row - self.view_rows // 2 + 1)
            self.select_cell(None, row)

    def pianoroll_note_off(self, note):
        row = self.get_row_from_note(note)
        if row is not None:
            self.pianoroll_set_row(row)

    # Function to update selectedCell
    # step: Step (column) of selected cell (Optional - default to reselect current column)
    # row: Index of keymap to select (Optional - default to reselect current row).
    #      Maybe outside visible range to scroll display
    def select_cell(self, step=None, row=None):
        if not self.keymap:
            return
        # Check row boundaries
        if row is None:
            row = self.selected_cell[1]
        if row < 0:
            row = 0
        elif row >= len(self.keymap):
            row = len(self.keymap) - 1
        else:
            row = int(row)
        # Check keymap offset
        if row >= self.keymap_offset + self.view_rows:
            # Note is off top of view area
            self.set_keymap_offset(row - self.view_rows + 1)
        elif row <= self.keymap_offset:
            # Note is off bottom of view area
            self.set_keymap_offset(row)
        note = self.keymap[row]['note']

        # Check column boundaries
        if step is None:
            step = self.selected_cell[0]
        if step < 0:
            step = 0
        elif step >= self.n_steps:
            step = self.n_steps - 1
        else:
            step = int(step)
        # Skip hidden (overlapping) cells
        for previous in range(step - 1, -1, -1):
            prev_duration = ceil(self.zynseq.libseq.getNoteDuration(previous, note))
            if not prev_duration:
                continue
            if prev_duration > step - previous:
                if step > self.selected_cell[0]:
                    step = previous + prev_duration
                else:
                    step = previous
                break
        # Re-check column boundaries
        if step < 0:
            step = 0
        elif step >= self.n_steps:
            step = self.n_steps - 1
        # Check step offset
        if step >= self.step_offset + int(self.view_steps):
            # Step is off right of display
            self.set_step_offset(step - int(self.view_steps) + 1)
        elif step < self.step_offset:
            # Step is off left of display
            self.set_step_offset(step)
        self.selected_cell = [step, row]

        if self.edit_mode == EDIT_MODE_BLOCK:
            return

        # Duration & velocity
        evdata = self.zynseq.get_note_data(step, note)
        if evdata:
            duration = evdata.duration
            offset = evdata.offset
            velocity = evdata.val2_start
        else:
            duration = self.duration
            offset = 0.0
            velocity = self.velocity
        self.set_velocity_indicator(velocity)

        # Hide selected block and copy/paste notes
        self.grid_canvas.delete("cp")
        self.hide_selected_block()

        # Position selector cell-frame
        coord = self.get_cell(step, row, duration, offset)
        coord[0] -= 1
        coord[1] -= 1
        if not self.rect_selected_cell:
            self.rect_selected_cell = self.grid_canvas.create_rectangle(coord, fill="", outline=SELECT_BORDER,
                                                                   width=self.select_thickness, tags="selected_cell")
        else:
            self.grid_canvas.coords(self.rect_selected_cell, coord)
        self.grid_canvas.tag_raise(self.rect_selected_cell)

    # ---------------------------------------------------------------
    # Block edit functionality => Copy/paste block
    # ---------------------------------------------------------------

    def move_cell(self, cell, dstep, drow):
        inrange = True
        if dstep:
            cell[0] += dstep
            if cell[0] >= self.n_steps:
                cell[0] = self.n_steps - 1
                inrange = False
            elif cell[0] < 0:
                cell[0] = 0
                inrange = False
        if drow:
            cell[1] += drow
            if cell[1] >= len(self.keymap):
                cell[1] = len(self.keymap) - 1
                inrange = False
            elif cell[1] < 0:
                cell[1] = 0
                inrange = False
        return inrange

    # -------------------------------------------------------------------------
    # Event management
    # -------------------------------------------------------------------------

    # Function to toggle note event
    # step: step number (column)
    # row: keymap index
    # Returns: Note if note added else None
    def toggle_event(self, step, row):
        if step < 0 or step >= self.n_steps or row >= len(self.keymap):
            return
        note = self.keymap[row]['note']
        start_step = self.zynseq.libseq.getNoteStart(step, note)
        if start_step >= 0:
            self.remove_chord(start_step, row)
        else:
            self.add_chord(step, row, self.velocity, self.duration, self.offset)
        self.select_cell(None, row)

    # Function to remove an event
    # step: step number (column)
    # row: keymap index
    def remove_event(self, step, row):
        if row >= len(self.keymap):
            return
        self.save_pattern_snapshot(now=True, force=False)
        note = self.keymap[row]['note']
        self.zynseq.libseq.removeNote(step, note)
        # Silence note if sounding
        self.zynseq.libseq.playNote(note, 0, self.channel)
        self.save_pattern_snapshot(now=True, force=True)
        self.drawing = True
        self.draw_row(row)
        self.drawing = False
        self.select_cell(step, row)

    # Function to add a note or chord, depending on current chord mode
    # step: step number (column)
    # row: keymap index
    # vel: velocity (0-127)
    # dur: duration (in steps)
    # offset: offset of start of event (0..0.99)
    def add_chord(self, step, row, vel, dur, offset=0.0):
        note = self.keymap[row]["note"]
        match self.chord_mode:
            case 0:
                # Single note entry
                chord = [0]
            case 1:
                # Chord entry mode
                chord = CHORDS[self.chord_type][1]
            case _:
                # Diatonic chord entry mode
                chord = self.get_diatonic_chord(note)
        for note_offset in chord:
            if self.add_note_event(step, row + note_offset, vel, dur, offset):
                self.play_note(note + note_offset)

    # Function to remove a note or chord, depending on current chord mode
    # step: step number (column)
    # note: MIDI note (0-127)
    # vel: velocity (0-127)
    # dur: duration (in steps)
    # offset: offset of start of event (0..0.99)
    def remove_chord(self, step, row):
        match self.chord_mode:
            case 0:
                # Single note entry
                chord = [0]
            case 1:
                # Chord entry mode
                chord = CHORDS[self.chord_type][1]
            case _:
                # Diatonic chord entry mode
                note = self.keymap[row]["note"]
                chord = self.get_diatonic_chord(note)
        for offset in chord:
            self.remove_event(step, row + offset)


    def get_default_note_evdata(self):
        evdata = zynseq.event_data()
        evdata.set_values(0, self.offset, self.duration, 0x90, 0, self.velocity, 0, 0,
                          self.stut_speed, self.stut_velfx, self.stut_ramp,
                          self.play_freq, self.stut_freq, self.play_chance, self.stut_chance)
        return evdata

    # Function to add an event
    # step: step number (column)
    # row: keymap index
    # vel: velocity (0-127)
    # dur: duration (in steps)
    # offset: offset of start of event (0..0.99)
    def add_note_event(self, step, row, vel, dur, offset=0.0, new_note=True):
        self.save_pattern_snapshot(now=True, force=False)
        note = self.keymap[row]["note"]
        if note > 127:
            return False
        self.zynseq.libseq.addNote(step, note, vel, dur, offset)
        if new_note:
            self.zynseq.libseq.setNoteData(step, note, self.get_default_note_evdata())
        self.save_pattern_snapshot(now=True, force=True)
        self.drawing = True
        self.draw_row(row)
        self.drawing = False
        self.select_cell(step, row)
        return True

    # Function to refresh status
    def refresh_status(self):
        super().refresh_status()
        self.playstate = self.zynseq.libseq.getSequenceState(self.zynseq.scene, self.phrase, self.sequence) & 0xff
        step = self.zynseq.libseq.getPatternPlayhead()
        if self.playhead != step:
            self.playhead = step
            self.play_canvas.coords("playCursor",
                                    1 + self.playhead * self.step_width, 0,
                                    1 + self.step_width * (self.playhead + 1), PLAYHEAD_HEIGHT)
        if (self.zynseq.libseq.isPatternModified() or self.reload_keymap) and self.redraw_pending < 3:
            self.redraw_pending = 3
        if self.reload_keymap:
            self.load_keymap()
            self.reload_keymap = False
            self.set_keymap_offset()
        if self.redraw_pending:
            self.draw_grid()
        if not self.drawing:
            pending_rows = set()
            while not self.rows_pending.empty():
                pending_rows.add(self.rows_pending.get_nowait())
            while len(pending_rows):
                self.draw_row(pending_rows.pop())
        self.save_pattern_snapshot(now=False, force=False)

    # Function to handle MIDI notes (only used to refresh screen - actual MIDI input handled by lib)
    def midi_note_on(self, note):
        self.pianoroll_note_on(note)
        if self.zynseq.libseq.isMidiRecord():
            self.rows_pending.put_nowait(note)

    def midi_note_off(self, note):
        self.pianoroll_note_off(note)
        if self.zynseq.libseq.isMidiRecord():
            if self.playstate == zynseq.SEQ_STOPPED:
                self.save_pattern_snapshot(now=True, force=True)
            else:
                self.changed = True
            self.rows_pending.put_nowait(note)

    def set_edit_title(self):
        color_fg = zynthian_gui_config.color_header_bg
        color_bg = zynthian_gui_config.color_panel_tx
        step = self.selected_cell[0]
        note = self.get_note_from_row(self.selected_cell[1])
        delta = "1"
        zynpot = 2
        if self.edit_mode == EDIT_MODE_MULTI:
            if self.edit_param == EDIT_PARAM_DUR:
                delta = "0.1"
                zynpot = 1
                self.set_title("MULTI Duration ", color_fg, color_bg)
            elif self.edit_param == EDIT_PARAM_VEL:
                self.set_title("MULTI Velocity", color_fg, color_bg)
        else:
            evdata = self.zynseq.get_note_data(step, note)
            if self.edit_param == EDIT_PARAM_DUR:
                if evdata:
                    val = evdata.duration
                else:
                    val = self.duration
                self.set_title(f"Duration: {val:0.1f} steps", color_fg, color_bg)
                delta = "0.1"
                zynpot = 1
            elif self.edit_param == EDIT_PARAM_VEL:
                if evdata:
                    val = evdata.val2_start
                else:
                    val = self.velocity
                self.set_title(f"Velocity: {val}", color_fg, color_bg)
            elif self.edit_param == EDIT_PARAM_OFFSET:
                if evdata:
                    val = evdata.offset
                else:
                    val = self.offset
                val = round(100 * val)
                self.set_title(f"Offset: {val}%", color_fg, color_bg)
            elif self.edit_param == EDIT_PARAM_STUT_SPD:
                if evdata:
                    val = evdata.stut_speed
                else:
                    val = self.stut_speed
                self.set_title(f"Stutter speed: {val}", color_fg, color_bg)
            elif self.edit_param == EDIT_PARAM_STUT_VFX:
                if evdata:
                    val = evdata.stut_velfx
                else:
                    val = self.stut_velfx
                val = STUT_VFX_OPTIONS[val]
                self.set_title(f"Stutter velo: {val}", color_fg, color_bg)
            elif self.edit_param == EDIT_PARAM_STUT_RMP:
                if evdata:
                    val = evdata.stut_ramp
                else:
                    val = self.stut_ramp
                val = STUT_RMP_OPTIONS[val]
                self.set_title(f"Stutter ramp: {val}", color_fg, color_bg)
            elif self.edit_param == EDIT_PARAM_PLAY_CHANCE:
                if evdata:
                    val = evdata.play_chance
                else:
                    val = self.play_chance
                val = round(100 * val)
                self.set_title(f"Play chance: {val}%", color_fg, color_bg)
            elif self.edit_param == EDIT_PARAM_PLAY_FREQ:
                if evdata:
                    val = evdata.play_freq
                else:
                    val = self.play_freq
                val = PLAY_FREQ_OPTIONS[val]
                self.set_title(f"Play frequency: {val}", color_fg, color_bg)
            elif self.edit_param == EDIT_PARAM_STUT_CHANCE:
                if evdata:
                    val = evdata.stut_chance
                else:
                    val = self.stut_chance
                val = round(100 * val)
                self.set_title(f"Stutter chance: {val}%", color_fg, color_bg)
            elif self.edit_param == EDIT_PARAM_STUT_FREQ:
                if evdata:
                    val = evdata.stut_freq
                else:
                    val = self.stut_freq
                val = STUT_FREQ_OPTIONS[val]
                self.set_title(f"Stutter frequency: {val}", color_fg, color_bg)

    # Function to handle zynpots value change
    #   i: Zynpot index [0..n]
    #   dval: Current value of zyncoder
    def zynpot_cb(self, i, dval):
        if zynthian_gui_base.zynpot_cb(self, i, dval):
            return True

        if i == self.ctrl_order[1]:
            if self.edit_mode == EDIT_MODE_SINGLE:
                if self.edit_param == EDIT_PARAM_DUR:
                    step = self.selected_cell[0]
                    index = self.selected_cell[1]
                    note = self.keymap[index]['note']
                    evdata = self.zynseq.get_note_data(step, note)
                    if evdata:
                        duration = evdata.duration
                    else:
                        duration = self.duration
                    duration += 0.1 * dval
                    max_duration = self.n_steps
                    if duration > max_duration or duration < 0.05:
                        return
                    if evdata:
                        self.add_note_event(step, index, evdata.val2_start, duration, evdata.offset, new_note=False)
                        #self.add_chord(step, index, sel_velocity, duration, sel_offset)
                    else:
                        self.duration = duration
                        self.select_cell()
                self.set_edit_title()
                return True
            elif self.edit_mode == EDIT_MODE_MULTI:
                if self.edit_param == EDIT_PARAM_DUR:
                    if self.selected_events:
                        self.zynseq.libseq.changeDurationList(dval * 0.1, zynseq.event_indexes_buffer, len(self.selected_events))
                    else:
                        self.zynseq.libseq.changeDurationAll(dval * 0.1)
                    self.redraw_pending = 3
                    return True

        elif i == self.ctrl_order[2]:
            if self.edit_mode == EDIT_MODE_SINGLE:
                step = self.selected_cell[0]
                row = self.selected_cell[1]
                note = self.keymap[row]['note']
                evdata = self.zynseq.get_note_data(step, note)
                if self.edit_param == EDIT_PARAM_DUR:
                    if evdata:
                        val = evdata.duration
                    else:
                        val = self.duration
                    val += dval
                    if val > self.n_steps or val < 0.05:
                        return
                    if evdata:
                        self.add_note_event(step, row, evdata.val2_start, val, evdata.offset, new_note=False)
                    else:
                        self.duration = val
                        self.select_cell()
                elif self.edit_param == EDIT_PARAM_VEL:
                    if evdata:
                        val = evdata.val2_start
                    else:
                        val = self.velocity
                    val += dval
                    if val > 127 or val < 1:
                        return
                    self.set_velocity_indicator(val)
                    if evdata:
                        self.zynseq.libseq.setNoteVelocity(step, note, val)
                        self.draw_cell(step, row)
                    else:
                        self.velocity = val
                        self.select_cell()
                elif self.edit_param == EDIT_PARAM_OFFSET:
                    if evdata:
                        val = evdata.offset
                    else:
                        val = self.offset
                    val = round(100 * val) + dval
                    if val < 0 or val > 99:
                        return
                    if evdata:
                        self.zynseq.libseq.setNoteOffset(step, note, val/100)
                        self.draw_cell(step, row)
                    else:
                        self.offset = val/100
                        self.select_cell()
                elif self.edit_param == EDIT_PARAM_STUT_SPD:
                    if evdata:
                        val = evdata.stut_speed
                    else:
                        val = self.stut_speed
                    val += dval
                    if val < 0 or val > 32:
                        return
                    if evdata:
                        self.zynseq.libseq.setNoteStutterSpeed(step, note, val)
                        self.draw_cell(step, row)
                    else:
                        self.stut_speed = val
                        self.select_cell()
                elif self.edit_param == EDIT_PARAM_STUT_VFX:
                    if evdata:
                        val = evdata.stut_velfx
                    else:
                        val = self.stut_velfx
                    val += dval
                    if val < 0 or val >= len(STUT_VFX_OPTIONS):
                        return True
                    if evdata:
                        self.zynseq.libseq.setNoteStutterVelfx(step, note, val)
                        self.draw_cell(step, row)
                    else:
                        self.stut_velfx = val
                        self.select_cell()
                elif self.edit_param == EDIT_PARAM_STUT_RMP:
                    if evdata:
                        val = evdata.stut_ramp
                    else:
                        val = self.stut_ramp
                    val += dval
                    if val < 0 or val >= len(STUT_RMP_OPTIONS):
                        return True
                    if evdata:
                        self.zynseq.libseq.setNoteStutterRamp(step, note, val)
                        self.draw_cell(step, row)
                    else:
                        self.stut_ramp = val
                        self.select_cell()
                elif self.edit_param == EDIT_PARAM_PLAY_CHANCE:
                    if evdata:
                        val = evdata.play_chance
                    else:
                        val = self.play_chance
                    val = round(100 * val) + dval
                    if val < 0 or val > 100:
                        return True
                    if evdata:
                        self.zynseq.libseq.setNotePlayChance(step, note, val/100)
                        self.draw_cell(step, row)
                    else:
                        self.play_chance = val/100
                        self.select_cell()
                elif self.edit_param == EDIT_PARAM_PLAY_FREQ:
                    if evdata:
                        val = evdata.play_freq
                    else:
                        val = self.play_freq
                    val += dval
                    if val < 0 or val >= len(PLAY_FREQ_OPTIONS):
                        return True
                    if evdata:
                        self.zynseq.libseq.setNotePlayFreq(step, note, val)
                        self.draw_cell(step, row)
                    else:
                        self.play_freq = val
                        self.select_cell()
                elif self.edit_param == EDIT_PARAM_STUT_CHANCE:
                    if evdata:
                        val = evdata.stut_chance
                    else:
                        val = self.stut_chance
                    val = round(100 * val) + dval
                    if val < 0 or val > 100:
                        return True
                    if evdata:
                        self.zynseq.libseq.setNoteStutterChance(step, note, val/100)
                        self.draw_cell(step, row)
                    else:
                        self.stut_chance = val/100
                        self.select_cell()
                elif self.edit_param == EDIT_PARAM_STUT_FREQ:
                    if evdata:
                        val = evdata.stut_freq
                    else:
                        val = self.stut_freq
                    val += dval
                    if val < 0 or val >= len(STUT_FREQ_OPTIONS):
                        return True
                    if evdata:
                        self.zynseq.libseq.setNoteStutterFreq(step, note, val)
                        self.draw_cell(step, row)
                    else:
                        self.stut_freq = val
                        self.select_cell()
                self.set_edit_title()
                return True
            elif self.edit_mode == EDIT_MODE_MULTI:
                if self.edit_param == EDIT_PARAM_DUR:
                    if self.selected_events:
                        self.zynseq.libseq.changeDurationList(dval, zynseq.event_indexes_buffer, len(self.selected_events))
                    else:
                        self.zynseq.libseq.changeDurationAll(dval)
                    self.redraw_pending = 3
                elif self.edit_param == EDIT_PARAM_VEL:
                    if self.selected_events:
                        self.zynseq.libseq.changeVelocityList(dval, zynseq.event_indexes_buffer, len(self.selected_events))
                    else:
                        self.zynseq.libseq.changeVelocityAll(dval)
                    self.redraw_pending = 3
                return True

        elif i == self.ctrl_order[3]:
            if self.edit_mode in (EDIT_MODE_SINGLE, EDIT_MODE_MULTI):
                self.edit_param += dval
                if self.edit_param < 0:
                    self.edit_param = 0
                if self.edit_param > EDIT_PARAM_LAST:
                    self.edit_param = EDIT_PARAM_LAST
                self.set_edit_title()
                return True

        if super().zynpot_cb(i, dval):
            return True


# ------------------------------------------------------------------------------
