# -*- coding: utf-8 -*-
# *****************************************************************************
# ZYNTHIAN PROJECT: Zynthian Chain (zynthian_chain)
#
# zynthian chain
#
# Copyright (C) 2015-2024 Fernando Moyano <jofemodo@zynthian.org>
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

import ctypes
import logging

# Zynthian specific modules
import zynautoconnect
from zyncoder.zyncore import lib_zyncore

CHAIN_MODE_SERIES = 0
CHAIN_MODE_PARALLEL = 1


class zynthian_chain:

    # ------------------------------------------------------------------------
    # Initialization
    # ------------------------------------------------------------------------

    def __init__(self, chain_id, midi_chan=None, midi_thru=False, audio_thru=False):
        """ Create an instance of a chain

        A chain contains zero or more slots.
        Each slot may contain one or more processing processors.
        Processors receive audio/MIDI input from the previous slot.
        Processors in first slot use the chain's audio/MIDI input.
        An empty chain with audio input configured is pass-through.
        An empty chain with MIDI input configured is pass-through.
        Pass-through disabled by default.

        midi_chan : Optional MIDI channel for chain input / control
        midi_thru : True to enable MIDI thru for empty chain
        audio_thru : True to enable audio thru for empty chain
        """

        # Each slot contains a list of parallel processors
        self.midi_slots = []  # Midi subchain (list of lists of processors)
        # Synth/generator/special slots (should be single slot)
        self.synth_slots = []
        self.audio_slots = []  # Audio subchain (list of lists of processors)
        self.fader_pos = 0  # Position of fader in audio effects chain

        self.chain_id = chain_id  # Chain's ID
        # Chain's MIDI channel - None for purely audio chain, 0xffff for *All Chains*
        self.midi_chan = midi_chan
        self.mixer_chan = None
        self.zmop_index = None
        self.midi_thru = midi_thru  # True to pass MIDI if chain empty
        self.audio_thru = audio_thru  # True to pass audio if chain empty
        self.midi_in = []
        self.midi_out = []
        self.audio_in = []
        self.audio_out = []

        self.status = ""  # Arbitary status text
        self.current_processor = None  # Selected processor object
        self.title = None  # User defined title for chain
        self.midi_routes = {}  # Map of MIDI routes indexed by jackname
        self.audio_routes = {}  # Map of audio routes indexed by jackname
        self.reset()

    def reset(self):
        """ Resets chain, removing all processors

        types : list of processor types for pass-through
        stop_engines : True to stop unused engines
        Does not change midi/audio thru
        """

        if self.chain_id == 0:
            # Main mix bus
            self.title = "Main"
            self.audio_in = []
            # Default use first two physical audio outputs
            self.audio_out = ["system:playback_[1,2]$"]
            self.audio_thru = True
        else:
            self.title = ""
            self.audio_in = [1, 2]
            self.audio_out = [0]

        if self.is_midi():
            lib_zyncore.zmop_reset_note_range_transpose(self.zmop_index)

        self.free_zmop()
        self.midi_out = []

        self.current_processor = None
        self.remove_all_processors()

    def get_slots_by_type(self, type):
        """Get the list of slots

        type : Processor tye
        Returns : Slot list object
        """
        if type == "MIDI Tool":
            return self.midi_slots
        elif type == "Audio Effect":
            return self.audio_slots
        else:
            return self.synth_slots

    def get_type(self):
        if self.synth_slots:
            return "MIDI Synth"
        elif self.is_audio():
            return "Audio Effect"
        elif self.is_midi():
            return "MIDI Tool"
        else:
            return "Empty"

    # ----------------------------------------------------------------------------
    # Chain Management
    # ----------------------------------------------------------------------------

    def set_mixer_chan(self, chan):
        """Set chain mixer channel

        chan : Mixer channel 0..Max Channels or None
        """

        self.mixer_chan = chan
        self.rebuild_audio_graph()

    def set_zmop_options(self):
        if self.zmop_index is not None and len(self.synth_slots) > 0:
            # IMPORTANT!!! Synth chains drop CC & PC messages
            # logging.info(f"Dropping MIDI CC & PC from chain {self.chain_id}")
            lib_zyncore.zmop_set_flag_droppc(self.zmop_index, 1)
            lib_zyncore.zmop_set_flag_dropcc(self.zmop_index, 1)
        else:
            # Audio & MIDI chains doesn't drop CC & PC messages
            # logging.info(f"Routing MIDI CC & PC to chain {self.chain_id}")
            lib_zyncore.zmop_set_flag_droppc(self.zmop_index, 0)
            lib_zyncore.zmop_set_flag_dropcc(self.zmop_index, 0)

    def set_zmop_index(self, iz):
        """Set chain zmop index

        iz : 0...16 (TODO: get maximum number of chains from lib_zyncore!)
        """
        self.free_zmop()
        if iz is not None and iz >= 0:
            self.zmop_index = iz
            self.midi_in = [f"ZynMidiRouter:ch{iz}_out"]
            lib_zyncore.zmop_reset_cc_route(iz)
            if self.midi_chan is not None:
                if 0 <= self.midi_chan < 16:
                    lib_zyncore.zmop_set_midi_chan(iz, self.midi_chan)
                elif self.midi_chan == 0xffff:
                    lib_zyncore.zmop_set_midi_chan_all(iz)

    def free_zmop(self):
        """If already using a zmop, release and reset it
        """
        if self.zmop_index is not None and self.zmop_index >= 0:
            lib_zyncore.zmop_reset_midi_chans(self.zmop_index)
        self.zmop_index = None
        self.midi_in = []

    def set_midi_chan(self, chan):
        """Set chain (and its processors) MIDI channel

        chan : MIDI channel 0..15, 0xffff or None
        """

        self.midi_chan = chan
        if self.zmop_index is not None and self.zmop_index >= 0 and self.midi_chan is not None:
            if 0 <= self.midi_chan < 16:
                lib_zyncore.zmop_set_midi_chan(self.zmop_index, self.midi_chan)
            elif self.midi_chan == 0xffff:
                lib_zyncore.zmop_set_midi_chan_all(self.zmop_index)
        for processor in self.get_processors():
            processor.set_midi_chan(chan)

    def set_title(self, title):
        """ Set user defined title

        title : Chain title (None to use processor title
        """

        self.title = title

    def get_title(self):
        """Get chain title

        Returns : User defined chain title or processor title if not set
        """

        if self.title:
            return self.title
        else:
            return self.get_description_parts()[0]

    def get_description_parts(self, basepath=False, preset=False):
        """Get chain description parts, using synth or first processor

            - basepath: use engine's basepath or name
            - preset: include the selected preset
        """
        parts = []

        if self.title:
            parts.append(self.title)
        elif self.chain_id == 0:
            parts.append("Main")
        elif not self.synth_slots and self.audio_thru:
            parts.append("Audio Input " +
                         ','.join([str(i) for i in self.audio_in]))

        if self.synth_slots:
            proc = self.synth_slots[0][0]
        elif self.get_slot_count("Audio Effect"):
            proc = self.get_processors("Audio Effect")[0]
        elif self.get_slot_count("MIDI Tool"):
            proc = self.get_processors("MIDI Tool")[0]
        else:
            proc = None

        if proc:
            if basepath:
                parts.append(proc.get_basepath())
            else:
                name = proc.get_name()
                if name:
                    parts.append(name)
            if preset:
                preset_name = proc.get_preset_name()
                if preset_name:
                    parts.append(preset_name)

        if not parts:
            if self.is_audio():
                if self.is_midi():
                    chain_type = "Synth"
                else:
                    chain_type = "Audio"
            elif self.is_midi():
                chain_type = "MIDI"
            parts.append(f"{chain_type} Chain {self.chain_id}")

        return parts

    def get_description(self, n_lines=None):
        """Get chain description text

            n_lines: Max number of lines. None is "All"
        """
        parts = self.get_description_parts(basepath=False, preset=True)
        return "\n".join(parts[:n_lines])

    def get_name(self):
        """Get chain name (short title)

        Returns : User defined chain title or default processor name if not set
        """
        parts = self.get_description_parts(basepath=True, preset=False)
        if parts:
            return parts[0]
        else:
            return ""

    # ----------------------------------------------------------------------------
    # Routing Graph
    # ----------------------------------------------------------------------------

    def rebuild_audio_graph(self):
        """Build dictionary of lists of sources mapped by destination"""

        # TODO: This is called too frequently
        if not zynautoconnect.acquire_lock():
            return

        self.audio_routes = {}
        # Add effects chain routes
        for i, slot in enumerate(self.audio_slots):
            for processor in slot:
                sources = []
                if i < self.fader_pos:
                    if i == 0:
                        # First slot fed from synth or chain input
                        if self.synth_slots:
                            for proc in self.synth_slots[-1]:
                                sources.append(proc.get_jackname())
                        elif self.audio_thru:
                            sources = self.get_input_pairs()
                        self.audio_routes[processor.get_jackname()] = sources
                    else:
                        for prev_proc in self.audio_slots[i - 1]:
                            sources.append(prev_proc.get_jackname())
                        self.audio_routes[processor.get_jackname()] = sources
                else:
                    # Post fader
                    if i == self.fader_pos:
                        self.audio_routes[processor.get_jackname()] = [
                            f"zynmixer:output_{self.mixer_chan + 1:02d}"]
                    else:
                        for prev_proc in self.audio_slots[i - 1]:
                            sources.append(prev_proc.get_jackname())
                        self.audio_routes[processor.get_jackname()] = sources

        # Add special processor inputs
        if self.is_synth():
            processor = self.synth_slots[0][0]
            if processor.type == "Special":
                sources = self.get_input_pairs()
                self.audio_routes[processor.get_jackname()] = sources

        if self.mixer_chan is not None:
            mixer_source = []
            if self.fader_pos:
                # Routing from last audio processor
                for source in self.audio_slots[self.fader_pos - 1]:
                    mixer_source.append(source.get_jackname())
            elif self.synth_slots:
                # Routing from synth processor
                for proc in self.synth_slots[0]:
                    mixer_source.append(proc.get_jackname())
            elif self.audio_thru:
                # Routing from capture ports or main chain
                mixer_source = self.get_input_pairs()
            # Connect end of pre-fader chain
            self.audio_routes[f"zynmixer:input_{self.mixer_chan + 1:02d}"] = mixer_source

            # Connect end of post-fader chain
            if self.fader_pos < len(self.audio_slots):
                # Use end of post fader chain
                slot = self.audio_slots[-1]
                sources = []
                for processor in slot:
                    sources.append(processor.get_jackname())
            else:
                # Use mixer channel output
                # if self.mixer_chan < 16: #TODO: Get main mixbus channel from zynmixer
                #    sources = [] # Do not route - zynmixer will normalise outputs to main mix bus
                # else:
                sources = [f"zynmixer:output_{self.mixer_chan + 1:02d}"]
            for output in self.get_audio_out():
                self.audio_routes[output] = sources.copy()

        zynautoconnect.release_lock()

    def get_input_pairs(self):
        """Get jack regexp for pairs of system:capture ports

        Returns : List of regexps
        """

        if self.chain_id == 0:
            return self.audio_in.copy()
        sources = []
        for i in range(0, len(self.audio_in), 2):
            a = self.audio_in[i]
            if i < len(self.audio_in) - 1:
                b = self.audio_in[i + 1]
                sources.append(f"system:capture_({a}|{b})$")
            else:
                sources.append(f"system:capture_({a})$")
        return sources

    def rebuild_midi_graph(self):
        """Build dictionary of lists of sources mapped by destination"""

        if not zynautoconnect.acquire_lock():
            return

        self.midi_routes = {}
        for i, slot in enumerate(self.midi_slots):
            if i == 0:
                continue  # Chain inputs are handled by autoconnect
            for processor in slot:
                sources = []
                for prev_proc in self.midi_slots[i - 1]:
                    sources.append(prev_proc.get_jackname())
                self.midi_routes[processor.get_jackname()] = sources

        sources = []
        if len(self.midi_slots):
            for prev_proc in self.midi_slots[-1]:
                sources.append(prev_proc.get_jackname())
        if self.synth_slots:
            for proc in self.synth_slots[0]:
                # TODO: Should always use engine's get_jackname? => proc.get_jackname(True)
                dst_jackname = proc.engine.get_jackname()
                self.midi_routes[dst_jackname] = sources
                # Special Engines can generate MIDI output too!!
                if proc.type == "Special":
                    sources = [dst_jackname]
        elif len(self.midi_slots) == 0 and self.midi_thru:
            sources = self.midi_in
        for output in self.midi_out:
            self.midi_routes[output] = sources
        # Feed output of MIDI chain to all audio processors - ideally this should only feed processors with
        # MIDI inputs but it is probably as simple to let autoconnect deal with that.
        for slot in self.audio_slots:
            for proc in slot:
                self.midi_routes[proc.engine.jackname] = sources

        zynautoconnect.release_lock()

    def rebuild_graph(self):
        """Build dictionary of lists of destinations mapped by source"""

        self.rebuild_midi_graph()
        self.rebuild_audio_graph()

    def get_audio_out(self):
        """Get list of audio playback port names"""

        return self.audio_out.copy()
        audio_out = []
        for output in self.audio_out:
            if output == 0:
                if self.mixer_chan < 17:
                    audio_out.append("zynmixer:input_18")
                else:
                    audio_out.append("system:playback_[1,2]$")
            else:
                audio_out.append(output)
        return audio_out

    def toggle_audio_out(self, out):
        """Toggle chain audio output

        out : Jack port regex or chain id of destination to toggle
        """

        if out not in self.audio_out:
            self.audio_out.append(out)
        else:
            try:
                self.audio_out.remove(out)
            except:
                pass
        logging.debug(f"Toggling Audio Output: {out}")

        self.rebuild_audio_graph()
        zynautoconnect.request_audio_connect(True)

    def toggle_audio_in(self, input):
        """Toggle chain audio in (physcial capture port)

        input : Index of physical audio input (1-based)
        """

        if input in self.audio_in:
            self.audio_in.remove(input)
        else:
            self.audio_in.append(input)

        self.rebuild_audio_graph()
        zynautoconnect.request_audio_connect(True)

    def get_midi_out(self):
        return self.midi_out

    def toggle_midi_out(self, dest):
        """ Set/unset a MIDI output route
        dest : destination ID. A jack port name/alias (string) or a chain ID (integer)
        """

        if dest not in self.midi_out:
            self.midi_out.append(dest)
        else:
            self.midi_out.remove(dest)

        self.rebuild_midi_graph()
        zynautoconnect.request_midi_connect(True)

    def is_audio(self):
        """Returns True if chain is processes audio"""

        return self.mixer_chan is not None

    def is_midi(self):
        """Returns True if chain processes MIDI"""

        return self.zmop_index is not None

    def is_synth(self):
        """Returns True if chain contains synth processor"""

        return len(self.synth_slots) != 0

    # ---------------------------------------------------------------------------
    # Processor management
    # ---------------------------------------------------------------------------

    def get_slot_count(self, type=None):
        """Get quantity of slots in chain

        type : processor type ['MIDI Tool'|'Audio Effect', etc.] (Default: None=whole chain)
        Returns : Quantity of slots in chain (section)
        """

        if type is None:
            return len(self.midi_slots) + len(self.audio_slots) + len(self.synth_slots)
        elif type == "MIDI Tool":
            return len(self.midi_slots)
        elif type == "Audio Effect":
            return len(self.audio_slots)
        elif type == "Pre Fader":
            return self.fader_pos
        elif type == "Post Fader":
            return len(self.audio_slots) - self.fader_pos
        elif type == "MIDI Synth":
            return len(self.synth_slots)
        else:
            return 0

    def get_processor_count(self, type=None, slot=None):
        """Get quantity of processors in chain (slot)

        type : processor type to filter results (Default: whole chain)
        slot : Index of slot or None for whole chain (Default: whole chain)
        Returns : Quantity of processors in (sub)chain or slot
        """

        count = 0
        if type is None:
            if slot is None or slot < 0:
                for j in self.midi_slots + self.synth_slots + self.audio_slots:
                    count += len(j)
        else:
            slots = self.get_slots_by_type(type)

            if slot is None or slot < 0:
                for j in slots:
                    count += len(j)
            else:
                if slot < slots:
                    count = len(slots[slot])
        return count

    def get_processors(self, type=None, slot=None):
        """Get list of processor objects in chain

        type : processor type to filter result (Default: All processors)
        slot : Index of slot or None for whole chain
        Returns : List of processor objects
        """

        processors = []
        if type is None:
            if slot is None:
                for j in self.midi_slots + self.synth_slots + self.audio_slots:
                    processors += j
                return processors
            if slot < len(self.midi_slots):
                return self.midi_slots[slot]
            slot -= len(self.midi_slots)
            if slot < len(self.synth_slots):
                return self.synth_slots[slot]
            slot -= len(self.synth_slots)
            if slot < len(self.audio_slots):
                return self.audio_slots[slot]
        else:
            slots = self.get_slots_by_type(type)
            if slot is None or slot < 0:
                for j in slots:
                    processors += j
            else:
                if slot < len(slots):
                    processors = slots[slot]
        return processors

    def insert_processor(self, processor, parallel=False, slot=None):
        """Insert a processor in the chain

        processor : processor object to insert
        parallel : True to add in parallel (same slot) else create new slot (Default: series)
        slot : Position (slot) to insert within subchain (Default: End of chain)
        Returns : True if processor added to chain
        """

        slots = self.get_slots_by_type(processor.type)
        if len(slots) == 0:
            slots.append([processor])
        else:
            if slot is None or slot < 0 or slot > len(slots):
                slot = len(slots) - 1
            if parallel:
                slots[slot].append(processor)
            else:
                slots.insert(slot + 1, [processor])

        processor.set_chain(self)
        processor.set_midi_chan(self.midi_chan)

        self.set_zmop_options()
        self.current_processor = processor
        return True

    def replace_processor(self, old_processor, new_processor):
        """Replace a processor within a chain

        old_processor : processor object to replace
        new_processor : processor object to add to chain
        Returns : True if processor was replaced
        """

        slots = self.get_slots_by_type(old_processor.type)
        for i, slot in enumerate(slots):
            for j, processor in enumerate(slot):
                if processor == old_processor:
                    self.slots[i][j] = new_processor
                    self.remove_processor(old_processor)
                    new_processor.set_midi_chan(self.midi_chan)
                    # TODO: Should we rebuild graph?
                    zynautoconnect.request_audio_connect(True)
                    zynautoconnect.request_midi_connect(True)
                    if self.current_processor == old_processor:
                        self.current_processor = new_processor
                    return True
        return False

    def remove_processor(self, processor):
        """Remove a processor from chain

        processor : processor object to remove
        Returns : True on success
        """

        slot = self.get_slot(processor)
        if slot is None:
            logging.error("processor is not in chain!")
            return False

        logging.debug("Removing processor {}".format(processor.get_jackname()))

        slots = self.get_slots_by_type(processor.type)
        slots[slot].remove(processor)
        if len(slots[slot]) == 0:
            slots.pop(slot)
            if processor.type == "Audio Effect" and slot < self.fader_pos:
                self.fader_pos -= 1

        processor.set_chain(None)
        if processor.engine:
            processor.engine.remove_processor(processor)

        self.set_zmop_options()
        self.rebuild_graph()

        if processor == self.current_processor:
            if slots:
                self.current_processor = slots[0][0]
            elif self.synth_slots:
                self.current_processor = self.synth_slots[0][0]
            elif self.audio_slots:
                self.current_processor = self.audio_slots[0][0]
            elif self.midi_slots:
                self.current_processor = self.midi_slots[0][0]
            else:
                self.current_processor = None

        # del processor => I don't think this is needed nor right?? (Jofemodo)
        return True

    def remove_all_processors(self):
        """Remove all processors from chain

        stop_engines : True to stop the processors' worker engines
        """

        for processor in self.get_processors():
            self.remove_processor(processor)

    def nudge_processor(self, processor, up):
        try:
            slots = self.get_slots_by_type(processor.type)
            cur_slot = self.get_slot(processor)
            parallel = len(slots[cur_slot]) > 1
            is_audio = processor.type == "Audio Effect"
            if up:
                if parallel:
                    slots[cur_slot].remove(processor)
                    slots.insert(cur_slot, [processor])
                    if is_audio and cur_slot < self.fader_pos:
                        self.fader_pos += 1
                elif is_audio and cur_slot == self.fader_pos:
                    self.fader_pos += 1
                elif cur_slot > 0:
                    slots.pop(cur_slot)
                    slots[cur_slot - 1].append(processor)
                    if is_audio and cur_slot < self.fader_pos:
                        self.fader_pos -= 1
                else:
                    return False
            else:
                if parallel:
                    slots[cur_slot].remove(processor)
                    slots.insert(cur_slot + 1, [processor])
                    if is_audio and cur_slot < self.fader_pos:
                        self.fader_pos += 1
                elif is_audio and cur_slot + 1 == self.fader_pos:
                    self.fader_pos -= 1
                elif cur_slot + 1 < len(slots):
                    slots.pop(cur_slot)
                    slots[cur_slot].append(processor)
                    if is_audio and cur_slot < self.fader_pos:
                        self.fader_pos -= 1
                else:
                    return False

            self.rebuild_graph()
        except:
            logging.error("Failed to move processor")
        return True

    def swap_processors(self, processor1, processor2):
        """Swap two processors in chain

        processor1 : First processor object to swap
        processor2 : Second processor object to swap
        Returns : True on success
        """

        if processor1.type != processor2.type or processor1.type:
            logging.error(
                "Can only swap MIDI or AudioFX processors of same type")
            return False
        slot1 = slot2 = None
        par1 = par2 = None
        slots = self.get_slots_by_type(processor1.type)
        for s, slot in enumerate(slots):
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
        slots[slot1][par1] = processor2
        slots[slot2][par2] = processor1
        self.rebuild_graph()
        return True

    def get_slot(self, processor):
        """Returns the slot index which contains processor or None if processor is not in chain"""

        slots = self.get_slots_by_type(processor.type)
        for i, slot in enumerate(slots):
            for u in slot:
                if processor == u:
                    return i
        return None

    def set_current_processor(self, processor):
        if processor in self.get_processors():
            self.current_processor = processor

    # ------------------------------------------------------------------------
    # State Management
    # ------------------------------------------------------------------------

    def get_state(self):
        """List of slot states

        Each list entry is a list of processor states
        """

        slots_states = []
        for slot in self.midi_slots + self.synth_slots + self.audio_slots:
            slot_state = {}
            for processor in slot:
                slot_state[processor.id] = processor.eng_code
            if slot_state:
                slots_states.append(slot_state)

        # Get ZMOP CC route state
        cc_route_ct = (ctypes.c_uint8 * 128)()
        if self.zmop_index is not None and self.zmop_index >= 0:
            lib_zyncore.zmop_get_cc_route(self.zmop_index, cc_route_ct)
        cc_route = []
        for ccr in cc_route_ct:
            cc_route.append(ccr)

        state = {
            "title": self.title,
            "midi_chan": self.midi_chan,
            "midi_thru": self.midi_thru,
            "audio_thru": self.audio_thru,
            "mixer_chan": self.mixer_chan,
            "zmop_index": self.zmop_index,
            "cc_route": cc_route,
            "slots": slots_states,
            "fader_pos": self.fader_pos
        }

        return state
