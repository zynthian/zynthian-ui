# -*- coding: utf-8 -*-
# *****************************************************************************
# ZYNTHIAN PROJECT: Zynthian Chain (zynthian_chain)
#
# zynthian chain
#
# Copyright (C) 2015-2022 Fernando Moyano <jofemodo@zynthian.org>
#                         Brian Walton <riban@zynthian.org>
#
# *****************************************************************************
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
# *****************************************************************************

import collections
import logging
from collections import OrderedDict

# Zynthian specific modules
import zynautoconnect
from zyngine import zynthian_processor

CHAIN_MODE_SERIES = 0
CHAIN_MODE_PARALLEL = 1


class zynthian_chain:

    # ------------------------------------------------------------------------
    # Initialization
    # ------------------------------------------------------------------------

    def __init__(self, midi_chan=None,
        enable_midi_thru=False, enable_audio_thru=False):
        """ Create an instance of a chain

        A chain contains zero or more slots.
        Each slot may contain one or more processing processors.
        Processors receive audio/MIDI input from the previous slot.
        Processors in first slot use the chain's audio/MIDI input.
        An empty chain with audio input configured is pass-through.
        An empty chain with MIDI input configured is pass-through.
        Pass-through disabled by default.

        midi_chan - Optional MIDI channel for chain input / control
        enable_midi_thru - True to enable MIDI thru for empty chain
        enable_audio_thru - True to enable audio thru for empty chain
        """

        # Each slot contains a list of parallel processors
        self.midi_slots = []  # Midi subchain (list of lists of processors)
        self.audio_slots = []  # Audio subchain (list of lists of processors)
        self.synth_processor = None # Synth/generator/special slot
        # Helper map of chain type to chain slots
        self.slot_map = {"MIDI Tool": self.midi_slots,
                         "Audio Effect": self.audio_slots}
        self.processors_by_jackname = OrderedDict() # Processors mapped by jackname
        self.midi_chan = midi_chan  # Chain's MIDI channel - may be None for purly audio chain
        self.mixer_chan = midi_chan # Mixer channel to connect audio output
        self.midi_thru = enable_midi_thru # True to pass MIDI if chain empty
        self.audio_thru = enable_audio_thru # True to pass audio if chain empty
        # self.status = "" # Arbiatry status text TODO: Move to UI
        self.reset()

    def reset(self, types=[]):
        """ Resets chain, removing all processors
        
        types - list of processor types for pass-through
        Does not change midi/audio thru
        """

        if self.midi_chan is not None and self.midi_chan < 16:
            self.midi_in = ["ZynMidiRouter:ch{}_out".format(self.midi_chan)]
        else:
            self.midi_in = []
        self.midi_out = ["MIDI-OUT", "NET-OUT"]
        self.audio_in = ["system"]
        self.audio_out = ["mixer"]
        self.remove_all_processors()
        self.reset_clone()
        self.reset_note_range()
        self.rebuild_graph()

    # ----------------------------------------------------------------------------
    # Chain Management
    # ----------------------------------------------------------------------------

    def set_midi_chan(self, midi_chan):
        """Set chain (and its processors) MIDI channel
        
        midi_chan - MIDI channel 0..15 or None
        """
        self.midi_chan = midi_chan
        for processor in self.get_processors():
            processor.set_midi_chan(midi_chan)

    def get_title(self):
        if self.synth_processor:
            return "{}\n{}".format(self.synth_processor.engine.name, self.synth_processor.get_preset_name())
        elif self.get_slot_count("Audio Effect"):
            return self.get_processors("Audio Effect")[0].engine.name
        elif self.get_slot_count("MIDI Tool"):
            return self.get_processors("MIDI Tool")[0].engine.name
        else:
            return ""

    # ----------------------------------------------------------------------------
    # Routing Graph
    # ----------------------------------------------------------------------------

    def rebuild_audio_graph(self):
        """Build dictionary of lists of destinations mapped by destination"""

        try:
            zynautoconnect.acquire_lock()
        except:
            pass # May be before zynautoconnect started

        self.audio_routes = {}
        # Add effects chain routes
        for i, slot in enumerate(self.audio_slots):
            for processor in slot:
                sources = []
                if i == 0:
                    # First slot fed from synth or chain input
                    if self.synth_processor:
                        sources = self.synth_processor.get_jackname()
                    elif self.audio_thru:
                        sources = self.audio_in
                    self.audio_routes[processor.get_jackname()] = sources
                else:
                    for prev_proc in self.audio_slots[i - 1]:
                        sources.append(prev_proc.get_jackname())
                    self.audio_routes[processor.get_jackname()] = sources
        mixer_source = []
        if self.audio_slots:
            for source in self.audio_slots[-1]:
                mixer_source.append(source.get_jackname())
        elif self.synth_processor:
            mixer_source.append([self.synth_processor.get_jackname()])
        elif self.audio_thru:
            mixer_source = self.audio_in
        if self.mixer_chan is not None:
            self.audio_routes["zynmixer:input_{:02d}".format(self.mixer_chan + 1)] = mixer_source

        try:
            zynautoconnect.release_lock()
        except:
            pass # May be before zynautoconnect started

    def rebuild_midi_graph(self):
        """Build dictionary of lists of destinations mapped by source"""

        try:
            zynautoconnect.acquire_lock()
        except:
            pass # May be before zynautoconnect started
 
        self.midi_routes = {}
        for i, slot in enumerate(self.midi_slots):
            for processor in slot:
                sources = []
                if i == 0:
                    # First slot fed from chain input
                    sources = self.midi_in
                else:
                    for prev_proc in self.midi_slots[i - 1]:
                        sources.append(prev_proc.get_jackname())
                self.midi_routes[processor.get_jackname()] = sources

        if self.synth_processor:
            sources = []
            if len(self.midi_slots):
                for prev_proc in self.midi_slots[i - 1]:
                    sources.append(prev_proc.get_jackname())
            else:
                sources = self.midi_in
            self.midi_routes[self.synth_processor.get_jackname()] = sources
        elif len(self.midi_slots) == 0 and self.audio_thru:
            for output in self.midi_out:
                self.midi_routes[output] = self.midi_in

        try:
            zynautoconnect.release_lock()
        except:
            pass # May be before zynautoconnect started

    def rebuild_graph(self):
        """Build dictionary of lists of destinations mapped by source"""
        self.rebuild_midi_graph()
        self.rebuild_audio_graph()

    def get_audio_out(self):
        """Get list of audio playback ports"""

        return self.audio_out
        audio_out = []
        for output in self.audio_out:
            if output == "mixer":
                audio_out.append("zynmixer:in_{}a".format(self.chain.mixer_chan))
                audio_out.append("zynmixer:in_{}b".format(self.chain.mixer_chan))
            else:
                audio_out.append(output)
        return audio_out


    def toggle_audio_out(self, jackname):
        """Toggle processor audio output"""

        audio_out = self.get_audio_out()
        if jackname not in audio_out:
            audio_out.append(jackname)
        else:
            try:
                audio_out.remove(jackname)
            except:
                pass
        logging.debug("Toggling Audio Output: {}".format(jackname))

        self.rebuild_audio_graph()
        zynautoconnect.audio_autoconnect(True)

    def get_audio_in(self):
        """Get list of audio capture ports"""

        audio_in = []
        for input in self.audio_in:
            if input == "system":
                audio_in.append("system:capture_1")
                audio_in.append("system:capture_2")
            else:
                audio_in.append(input)
        return audio_in

    def toggle_audio_in(self, jackname):
        """Toggle processor audio in"""
        audio_in = self.get_audio_in()
        if jackname not in audio_in:
            audio_in.append(jackname)
        else:
            try:
                audio_in.remove(jackname)
            except:
                pass
        if len(audio_in) == 2 and "system:capture_1" in audio_in and "system:capture_2" in audio_in:
            self.audio_in = ["system"]
        else:
            self.audio_in = audio_in
        logging.debug("Toggling Audio Capture: {}".format(jackname))

        self.rebuild_audio_graph()
        zynautoconnect.audio_autoconnect(True)

    def toggle_midi_out(self, jackname):
        if isinstance(jackname, zynthian_processor):
            jackname=jackname.engine.jackname

        if jackname not in self.midi_out:
            self.midi_out.append(jackname)
        else:
            self.midi_out.remove(jackname)

        self.rebuild_midi_graph()
        zynautoconnect.midi_autoconnect(True)

    def is_audio(self):
        """Returns True if chain is processes audio"""
        return self.audio_thru or len(self.audio_slots) > 0 or self.synth_processor is not None

    def is_midi(self):
        """Returns True if chain processes MIDI"""
        return self.midi_thru or len(self.midi_slots) > 0

    # ---------------------------------------------------------------------------
    # Processor management
    # ---------------------------------------------------------------------------

    def generate_jackname_dict(self):
        self.processors_by_jackname = OrderedDict()
        if self.synth_processor:
            self.processors_by_jackname[self.synth_processor.get_jackname(
            )] = self.synth_processor
        for slot in self.midi_slots + self.audio_slots:
            for processor in slot:
                self.processors_by_jackname[processor.get_jackname()] = processor

    def get_slot_count(self, type=None):
        """Get quantity of slots in chain

        type - processor type ['MIDI Tool'|'Audio Effect', etc.] (Default: None=whole chain)
        Returns - Quantity of slots in chain (section)
        """

        slots = 0
        if type is None:
            slots = len(self.midi_slots) + len(self.audio_slots)
            if self.synth_processor:
                slots += 1
        elif type in self.slot_map:
            slots = len(self.slot_map[type])
        else:
            if self.synth_processor:
                slots = 1
        return slots

    def get_processor_count(self, type=None, slot=None):
        """Get quantity of processors in chain (slot)

        type - processor type to filter results (Default: whole chain)
        slot - Index of slot or None for whole chain (Default: whole chain)
        Returns - Quantity of processors in (sub)chain or slot
        """

        processors = 0
        if type is None:
            if slot is None:
                for j in self.midi_slots + self.audio_slots:
                    processors += len(j)
                if self.synth_processor:
                    processors += 1
        else:
            if type in self.slot_map:
                if slot is None:
                    for j in self.slot_map[type]:
                        processors += len(j)
                else:
                    if slot < len(self.slot_map[type]):
                        processors = len(self.slot_map[type][slot])
            elif slot == 0 and self.synth_processor:
                processors = 1
        return processors

    def get_processors(self, type=None, slot=None):
        """Get list of processor objects in chain

        type - processor type to filter result (Default: All processors)
        slot - Index of slot or None for whole chain
        Returns - List of processor objects
        """

        processors = []
        if type is None:
            for slot in self.midi_slots:
                processors += slot
            if self.synth_processor:
                processors.append(self.synth_processor)
            for j in self.audio_slots:
                processors += j
            if slot is not None:
                if len(processors) > slot:
                    return processors[slot]
                else:
                    return []
        else:
            if type in self.slot_map:
                if slot is None:
                    for j in self.slot_map[type]:
                        processors += j
                else:
                    if slot < len(self.slot_map[type]):
                        processors = self.slot_map[type][slot]
            elif slot == 0 and self.synth_processor:
                processors.append(self.synth_processor)
        return processors

    def get_processor_by_jackname(self, jackname):
        """Get processor object from its jackname"""

        if jackname in self.processors_by_jackname:
            return self.processors_by_jackname[jackname]
        return None

    def insert_processor(self, processor, chain_mode=CHAIN_MODE_SERIES, slot=None):
        """Insert a processor in the chain

        processor - processor object to insert
        chain_mode - CHAIN_MODE_SERIES|CHAIN_MODE_PARALLEL
        slot - Position (slot) to insert (Default: End of chain)
        Returns - True if processor added to chain
        """

        if processor.type in self.slot_map: # Common code for audio and midi fx
            if len(self.slot_map[processor.type]) == 0:
                self.slot_map[processor.type].append([processor])
            else:
                if slot is None or slot > len(self.slot_map[processor.type]):
                    slot = len(self.slot_map[processor.type])
                if chain_mode == CHAIN_MODE_SERIES:
                    self.slot_map[processor.type].insert(slot, [processor])
                else:
                    self.slot_map[processor.type][slot - 1].append(processor)
        else:
            if self.synth_processor:
                logging.error(
                    "Cannot insert processor - synth %s processor already exists", self.synth_processor.engine.name)
                return False
            self.synth_processor = processor

        processor.set_midi_chan(self.midi_chan)
        return True

    def replace_processor(self, old_processor, new_processor):
        """Replace a processor within a chain

        old_processor - processor object to replace
        new_processor - processor object to add to chain
        Returns - True if processor was replaced
        """

        if new_processor.type == "MIDI Tool":
            for i, slot in enumerate(self.midi_slots):
                for j, processor in enumerate(slot):
                    if processor == old_processor:
                        self.midi_slots[i][j] = new_processor
                        break
            return False
        elif new_processor.type == "Audio Effect":
            for i, slot in enumerate(self.audio_slots):
                for j, processor in enumerate(slot):
                    if processor == old_processor:
                        self.audio_slots[i][j] = new_processor
                        break
            return False
        else:
            if old_processor != self.synth_processor:
                return False
            self.synth_processor = new_processor

        # Remove old processor
        self.remove(old_processor)

        self.generate_jackname_dict()
        self.rebuild_graph()
        new_processor.set_midi_chan(self.midi_chan)
        zynautoconnect.autoconnect(True)
        return True

    def remove_processor(self, processor):
        """Remove a processor from chain

        processor - processor object to remove
        Returns - True on success
        """

        slot = self.get_slot(processor)
        if slot is None:
            logging.error("processor is not in chain!")
            return False

        logging.debug("Removing processor {}".format(processor.get_jackname()))

        if processor == self.synth_processor:
            self.synth_processor = None
        else:
            self.slot_map[processor.type][slot].remove(processor)
            if len(self.slot_map[processor.type][slot]) == 0:
                self.slot_map[processor.type].pop(slot)

        if processor.engine:
            processor.engine.stop()
            # TODO: Refactor engine to replace layer with processor
            processor.engine.del_layer(processor)

        self.generate_jackname_dict()
        self.rebuild_graph()
        del processor

        return True

    def remove_all_processors(self):
        """Remove all processors from chain"""

        for processor in self.get_processors():
            self.remove_processor(processor)
        self.rebuild_graph()

    def move_processor(self, processor, slot):
        """Move processor to different slot

        processor - Processor object
        slot - Index of slot to move process to
        Fails if slot does not exist
        """

        try:
            zynautoconnect.acquire_lock()
            slots = self.slot_map[processor.type]
            if slot < len(slots):
                cur_slot = self.get_slot(processor)
                if cur_slot != slot:
                    slots[cur_slot].pop(processor)
                    slots[slot].append(processor)
                    self.rebuild_graph()
                    zynautoconnect.autoconnect(True)
        except:
            logging.error("Failed to move processor")
        zynautoconnect.release_lock()

    def swap_processors(self, processor1, processor2):
        """Swap two processors in chain

        processor1 - First processor object to swap
        processor2 - Second processor object to swap
        Returns - True on success
        """

        if processor1.type != processor2.type or processor1.type not in self.slot_map:
            logging.error("Can only swap MIDI or AudioFX processors of same type")
            return False
        slot1 = slot2 = None
        par1 = par2 = None
        for s, slot in enumerate(self.slot_map[processor1.type]):
            for u, processor in enumerate(slot):
                if processor1 == processor:
                    slot1 = s
                    par1 = u
                if processor2 == processor:
                    slot2 = s
                    par2 = u

        if par1 == None or par2 == None or slot1 == None or slot2 == None:
            logging.error("processor not found")
            return False
        self.slot_map[processor1.type][slot1][par1] = processor2
        self.slot_map[processor1.type][slot2][par2] = processor1
        self.rebuild_graph()
        return True

    def get_slot(self, processor):
        """Returns the slot which contains processor or None if processor is not in chain"""
        if processor.type in self.slot_map:
            for i, slot in enumerate(self.slot_map[processor.type]):
                for u in slot:
                    if processor == u:
                        return i
        else:
            if processor == self.synth_processor:
                return 0
        return None

    def reset_clone(self):
        """Reset chain's MIDI clone configuration to default"""
        # TODO: Implement
        pass

    def reset_note_range(self):
        """Reset chain's note range configuration to default"""
        # TODO: Implement
        pass


    # ------------------------------------------------------------------------
    # State Management
    # ------------------------------------------------------------------------

    def get_state(self):
        """List of slot states
        
        Each list entry is a list of processor states
        """

        slots_states = []
        if self.synth_processor:
            slots_states.append([self.synth_processor.get_state()])
        for slot in self.midi_slots + self.audio_slots:
            slot_state = []
            for processor in slot:
                slot_state.append(processor.get_state())
            slots_states.append(slot_state)

        state = {
            "midi_chan": self.midi_chan,
            "midi_in": self.midi_in,
            "midi_out": self.midi_out,
            "midi_thru": self.midi_thru,
            "audio_in": self.audio_in,
            "audio_out": self.audio_out,
            "audio_thru": self. audio_thru,
            "slots": slots_states
        }
        return state

