# -*- coding: utf-8 -*-
# ****************************************************************************
# ZYNTHIAN PROJECT: Zynthian Chain Manager (zynthian_chain_manager)
#
# zynthian chain manager
#
# Copyright (C) 2015-2026 Fernando Moyano <jofemodo@zynthian.org>
#                         Brian Walton <riban@zynthian.org>
#
# ****************************************************************************
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
# ****************************************************************************

import logging

# Zynthian specific modules
import zynautoconnect
from zyncoder.zyncore import lib_zyncore

from zyngine import *
from zyngine import zynthian_lv2
from zyngine.zynthian_chain import *
from zyngine.zynthian_engine_jalv import *
from zyngine.zynthian_engine_pianoteq import *
from zyngine.zynthian_signal_manager import zynsigman
from zyngine.zynthian_processor import zynthian_processor
from zyngine import zynthian_state_manager
from zyngui import zynthian_gui_config

# ----------------------------------------------------------------------------
# Some variables & definitions
# ----------------------------------------------------------------------------

MAX_NUM_MIDI_CHANS = 32

# Get ZynMidiRouter parameters and limits from lib_zyncore
NUM_ZMOP_CHAINS = lib_zyncore.zmop_get_num_chains()
MAX_NUM_ZMOPS = NUM_ZMOP_CHAINS - 1
NUM_MIDI_DEVS_IN = lib_zyncore.zmip_get_num_devs() + 3  #TODO: Use a constant for this extra capacity
NUM_MIDI_DEVS_OUT = lib_zyncore.zmop_get_num_devs()
MAX_NUM_MIDI_DEVS = min(NUM_MIDI_DEVS_IN, NUM_MIDI_DEVS_OUT)
ZMIP_SEQ_INDEX = lib_zyncore.zmip_get_seq_index()
ZMIP_STEP_INDEX = lib_zyncore.zmip_get_step_index()
ZMIP_INT_INDEX = lib_zyncore.zmip_get_int_index()
ZMIP_CTRL_INDEX = lib_zyncore.zmip_get_ctrl_index()
ZMOP_MOD_INDEX = lib_zyncore.zmop_get_mod_index()
ZMOP_STEP_INDEX = lib_zyncore.zmop_get_step_index()

engine2class = {
    "ZY": zynthian_engine_zynaddsubfx,
    "FS": zynthian_engine_fluidsynth,
    "SF": zynthian_engine_sfizz,
    "LS": zynthian_engine_linuxsampler,
    "BF": zynthian_engine_setbfree,
    'JV': zynthian_engine_jalv,
    "AE": zynthian_engine_aeolus,
    "PT": zynthian_engine_pianoteq,
    "AP": zynthian_engine_audioplayer,
    "SL": zynthian_engine_sooperlooper,
    "SX": zynthian_engine_sysex,
    "MC": zynthian_engine_midi_control,
    "PD": zynthian_engine_puredata,
    "MD": zynthian_engine_modui,
    "IR": zynthian_engine_inet_radio,
    "MI": zynthian_engine_audio_mixer,
    "MR": zynthian_engine_audio_mixer,
    "MX": zynthian_engine_alsa_mixer,
    "TP": zynthian_engine_tempo,
    'CL': zynthian_engine_clippy
}

# ----------------------------------------------------------------------------
# Zynthian Chain Manager Class
# ----------------------------------------------------------------------------


class zynthian_chain_manager:

    engine_info = None
    single_processor_engines = ["BF", "MD", "PT", "AE", "SL", "IR"]

    def __init__(self, state_manager):
        """ Create an instance of a chain manager

        Manages chains of audio and MIDI processors.
        Each chain consists of zero or more slots.
        Each slot may contain one or more processors.

        state_manager : State manager object
        """

        logging.info("Creating chain manager")

        self.state_manager = state_manager

        self.chains = {}  # Map of chain objects indexed by chain id
        self.zyngine_counter = 0  # Appended to engine names for uniqueness
        self.zyngines = {}  # Map of instantiated engines, indexed by engine code
        self.processors = {}  # Dictionary of processor objects indexed by UID
        self.active_chain = None  # Active chain object => This should NEVER be None!!!
        self.active_midi_chain = None # Chain currently receiving active MIDI input
        self._pinned_chains = 1 # Quantity of pinned chains (shown pinned to right edge of mixer in UI)

        # Map of list of zctrls indexed by 24-bit ZMOP,CHAN,CC
        self.absolute_midi_cc_binding = {}
        # Map of list of zctrls indexed by 24-bit CHAIN,CHAN,CC
        self.chain_midi_cc_binding = {}
        self.rebuild_optimisation_cache()

    # ------------------------------------------------------------------------
    # Engine Management
    # ------------------------------------------------------------------------

    @classmethod
    def get_engine_info(cls):
        """Get engine config from file and add extra info"""

        # Get engines info from file, including standalone engines.
        # Yes, names aren't good. They should be refactored!
        eng_info = zynthian_lv2.get_engines()

        # Don't recalculate if info not changed
        if eng_info == cls.engine_info:
            return cls.engine_info

        cls.engine_info = eng_info
        cls.engine_info["MI"] = {"ID":"0", "NAME":"Mixer_Channel_Strip", "TITLE": "Mixer Channel Strip", "TYPE": "Audio Effect", "CAT": "Other", "ENABLED": False, "INDEX": 0, "URL": "", "UI": "", "DESCR": "Audio mixer channel strip", "QUALITY": 5, "COMPLEX": 5, "EDIT": 0}
        cls.engine_info["MR"] = {"ID":"1", "NAME":"Mixer_Return_Strip", "TITLE": "Mixer Effect Return Strip", "TYPE": "Audio Effect", "CAT": "Other", "ENABLED": False, "INDEX": 1, "URL": "", "UI": "", "DESCR": "Audio mixer effect return strip", "QUALITY": 5, "COMPLEX": 5, "EDIT": 0}
        cls.engine_info["MX"] = {"NAME": "Alsa_Mixer", "TITLE": "ALSA Mixer", "TYPE": "Global", "CAT": None, "ENGINE": zynthian_engine_alsa_mixer, "ENABLED": False}
        cls.engine_info["TP"] = {"NAME": "Tempo", "TITLE": "Tempo", "TYPE": "Global", "CAT": None, "ENGINE": zynthian_engine_tempo, "ENABLED": False}
        # Look for an engine class for each one
        for key, info in cls.engine_info.items():
            try:
                info['ENGINE'] = engine2class[key[0:2]]
                # logging.debug(f"Found engine class for {key}")
            except:
                logging.error(
                    f"Engine {key} has been disabled. Can't find an engine class for it.")
                info['ENGINE'] = None
                info['ENABLED'] = False

        # Complete Pianoteq config
        pt_info = get_pianoteq_binary_info()
        if pt_info and pt_info['api']:
            cls.engine_info['PT']['TITLE'] = pt_info['name']
        else:
            cls.engine_info['PT']['ENGINE'] = None
            cls.engine_info['PT']['ENABLED'] = False

        return cls.engine_info

    @classmethod
    def save_engine_info(cls):
        """Save the engine config to file"""

        zynthian_lv2.save_engines()

    # ------------------------------------------------------------------------
    # Chain Management
    # ------------------------------------------------------------------------

    def add_chain(self, chain_id, midi_chan=None, midi_thru=False, audio_thru=False, zmop_index=None,
                  title="", chain_pos=None, fast_refresh=True):
        """Add a chain

        chain_id: UID of chain (None to get next available)
        midi_chan : MIDI channel associated with chain
        midi_thru : True to enable MIDI thru for empty chain (Default: False)
        audio_thru : True to enable audio thru for empty chain (Default: False)
        zmop_index : MIDI router output (Default: None)
        title : Chain title (Default: None)
        chain_pos : Position to insert chain (Default: End)
        fast_refresh : False to trigger slow autoconnect (Default: Fast autoconnect)
        Returns : Chain ID or None if chain could not be created
        """

        self.state_manager.start_busy("add_chain", "Adding Chain")

        # If not chain ID has been specified, create new unique chain ID
        if chain_id is None:
            chain_id = 1
            while chain_id in self.chains:
                chain_id += 1
        chain_id = int(chain_id)

        if chain_pos is None:
            chain_pos = len(self.chains) - 1

        # If Main chain ...
        if chain_id == 0:  # main
            midi_thru = False
            audio_thru = True

        # If the chain already exists, update and return
        if chain_id in self.chains:
            self.chains[chain_id].midi_thru = midi_thru
            self.chains[chain_id].audio_thru = audio_thru
            self.state_manager.end_busy("add_chain")
            return chain_id

        # Enable sequencer channel
        if midi_chan is not None:
            self.state_manager.zynseq.enable_channel(midi_chan, True)

        """
        # Enable launcher sequences if not used by other chain
        if midi_chan is not None:
            enable_sequences = True
            for chain in self.chains.values():
                if chain.midi_chan == midi_chan:
                    enable_sequences = False
                    break
            if enable_sequences:
                self.state_manager.zynseq.enable_channel(midi_chan, True)
        """

        # Create chain instance
        chain = zynthian_chain(chain_id, midi_chan, midi_thru, audio_thru)
        if not chain:
            return None

        # Insert chain into dict
        items = list(self.chains.items())
        items.insert(chain_pos, (chain_id, chain))
        self.chains = dict(items)
        self.chains[chain_id] = chain
        # Update pinned chains
        if self._pinned_chains > 1 and chain_pos >= self.get_pinned_pos():
            self._pinned_chains += 1

        # Setup chain
        chain.set_title(title)

        # Set MIDI channel
        self.set_midi_chan(chain_id, midi_chan)

        # Setup MIDI routing
        if isinstance(midi_chan, int) and (0 <= midi_chan < 16 or midi_chan == 0xffff):
            # Restore zmop_index if it's free for assignment
            if zmop_index is None or not self.is_free_zmop_index(zmop_index):
                zmop_index = self.get_next_free_zmop_index()
            chain.set_zmop_index(zmop_index)
            # Enable all MIDI input devices by default => TODO: Should we allow user to define default routing?
            for zmip in range(MAX_NUM_MIDI_DEVS):
                lib_zyncore.zmop_set_route_from(chain.zmop_index, zmip, True)
            # Enable StepSeq MIDI intput
            lib_zyncore.zmop_set_route_from(chain.zmop_index, ZMIP_STEP_INDEX, True)
            # Enable SMF sequencer MIDI intput
            lib_zyncore.zmop_set_route_from(chain.zmop_index, ZMIP_SEQ_INDEX, True)
            # Enable CV/Gate MIDI input (fake port zmip)
            lib_zyncore.zmop_set_route_from(chain.zmop_index, ZMIP_INT_INDEX, True)
            # Enable default native CC handling of pedals
            cc_route_ct = (ctypes.c_uint8 * 128)()
            for ccnum in (64, 66, 67, 69):
                cc_route_ct[ccnum] = 1
            lib_zyncore.zmop_set_cc_route(zmop_index, cc_route_ct)

        chain.rebuild_graph()
        zynautoconnect.request_audio_connect(fast_refresh)
        zynautoconnect.request_midi_connect(fast_refresh)

        logging.debug(f"ADDED CHAIN {chain_id} => midi_chan={chain.midi_chan}, zmop_index={chain.zmop_index}")

        self.set_active_chain_by_id(chain_id)
        if fast_refresh:
            zynsigman.send_queued(zynsigman.S_CHAIN_MAN, zynsigman.SS_ADD_CHAIN)
        else:
            self.rebuild_optimisation_cache()
        self.state_manager.end_busy("add_chain")
        return chain_id

    def add_chain_from_state(self, chain_id, chain_state):
        if 'title' in chain_state:
            title = chain_state['title']
        else:
            title = ""
        if 'midi_chan' in chain_state:
            midi_chan = chain_state['midi_chan']
        else:
            midi_chan = None
        if 'midi_thru' in chain_state:
            midi_thru = chain_state['midi_thru']
        else:
            midi_thru = False
        if 'audio_thru' in chain_state:
            audio_thru = chain_state['audio_thru']
        else:
            audio_thru = False
        if 'zmop_index' in chain_state:
            zmop_index = chain_state['zmop_index']
        else:
            zmop_index = None

        chain_id = self.add_chain(chain_id, midi_chan=midi_chan, midi_thru=midi_thru, audio_thru=audio_thru,
                       zmop_index=zmop_index, title=title, fast_refresh=False)

        # Set CC route state
        zmop_index = self.chains[chain_id].zmop_index
        if 'cc_route' in chain_state and zmop_index is not None and zmop_index >= 0:
            cc_route_ct = (ctypes.c_uint8 * 128)()
            for ccnum in chain_state['cc_route']:
                cc_route_ct[ccnum] = 1
            lib_zyncore.zmop_set_cc_route(zmop_index, cc_route_ct)
        return chain_id

    def remove_chain(self, chain_id, stop_engines=True, fast_refresh=True):
        """Removes a chain or resets main chain

        chain_id : ID of chain to remove
        stop_engines : True to stop unused engines
        fast_refresh : False to trigger slow autoconnect (Default: Fast autoconnect)
        Returns : True on success
        """

        if chain_id not in self.chains:
            return False
        self.state_manager.start_busy("remove_chain", "Removing Chain")
        chain_pos = self.get_chain_index(chain_id)
        # List of associated chains that shold be removed simultaneously
        chains_to_remove = [chain_id]
        chain = self.chains[chain_id]
        midi_chan = chain.midi_chan
        if chain.synth_slots:
            if chain.synth_slots[0][0].eng_code in ["BF", "AE"]:
                # TODO: We remove all setBfree and Aeolus chains but maybe we should allow chain manipulation
                for id, ch in self.chains.items():
                    if ch != chain and ch.synth_slots and ch.synth_slots[0][0].eng_code == chain.synth_slots[0][0].eng_code:
                        chains_to_remove.append(id)

        for chain_id in chains_to_remove:
            chain = self.chains[chain_id]
            if chain == self.active_midi_chain:
                self.active_midi_chain = None
            if isinstance(chain.midi_chan, int):
                if chain.midi_chan < MAX_NUM_MIDI_CHANS:
                    lib_zyncore.ui_send_ccontrol_change(chain.midi_chan, 120, 0)
                elif chain.midi_chan == 0xffff:
                    for mc in range(16):
                        lib_zyncore.ui_send_ccontrol_change(mc, 120, 0)
            if self._pinned_chains > 1 and chain_pos >= self.get_pinned_pos():
                self._pinned_chains -= 1

            update_fxreturns = False
            if chain.zynmixer_proc:
                chain.zynmixer_proc.zynmixer.set_mute(chain.zynmixer_proc.mixer_chan, True) # Mute chain whilst removing
                sleep(self.state_manager.jack_period)
                if chain.zynmixer_proc.eng_code == "MR" and chain.chain_id:
                    update_fxreturns = True

            for processor in chain.get_processors():
                self.remove_processor(chain_id, processor, False)
            chain.reset()
            if chain_id == 0:
                chain.zynmixer_proc.zynmixer.set_mute(chain.zynmixer_proc.mixer_chan, False) # Unmute main chain
            else:
                self.chains.pop(chain_id)
                del chain

        self.rebuild_optimisation_cache()

        zynautoconnect.request_audio_connect(fast_refresh)
        zynautoconnect.request_midi_connect(fast_refresh)
        if stop_engines:
            self.stop_unused_engines()
        if self.active_chain not in self.chains.values():
            if chain_pos + 1 >= len(self.chains):
                chain_pos -= 1
            self.set_active_chain_by_index(chain_pos)

        # Disable launcher sequences if not used by other chain
        if midi_chan is not None:
            disable_sequences = True
            for chain in self.chains.values():
                if chain.midi_chan == midi_chan:
                    disable_sequences = False
                    break
            if disable_sequences:
                self.state_manager.zynseq.enable_channel(midi_chan, False)

        self.state_manager.purge_zs3()

        if update_fxreturns:
            i = 1
            for chain_id in self.chains:
                chain = self.chains[chain_id]
                if chain.title.startswith("Effect Return "):
                    chain.title = f"Effect Return {i}"
                    i += 1
        if fast_refresh:
            zynsigman.send_queued(zynsigman.S_CHAIN_MAN, zynsigman.SS_REMOVE_CHAIN)

        self.state_manager.end_busy("remove_chain")
        return True

    def remove_all_chains(self, stop_engines=True):
        """Remove all chains

        stop_engines : True to stop orphaned engines
        Returns : True if all chains removed
        Note: Main chain is retained but reset
        """

        success = True
        for chain_id in list(self.chains.keys()):
            success &= self.remove_chain(chain_id, stop_engines, fast_refresh=False)
        self._pinned_chains = 1
        zynsigman.send_queued(zynsigman.S_CHAIN_MAN, zynsigman.SS_REMOVE_ALL_CHAINS)
        return success

    def set_chain_title(self, chain_id, title):
        try:
            chain = self.chains[chain_id]
            if chain.get_title() == title:
                return
            chain.set_title(title)
            if chain.chain_id and chain.zynmixer_proc and chain.zynmixer_proc.eng_code == "MR":
                self.refresh_mixbus_sends()
            zynsigman.send_queued(zynsigman.S_CHAIN_MAN, zynsigman.SS_RENAME_CHAIN, chain_id=chain_id, title=title)
        except:
            pass

    def nudge_chain(self, offset):
        """Move active chain's position relative to current position

        offset - Position to move to relative to current position (+/-)
        Returns - New position of chain
        """

        try:
            pos = list(self.chains).index(self.active_chain.chain_id) + offset
        except:
            return None
        return self.move_chain(self.active_chain.chain_id, pos)

    def move_chain(self, chain_id, pos):
        """Move a chain's position

        chain_id - Chain id
        pos - Position to move to
        Returns - New position of chain or None on failure
        """

        if chain_id is None:
            chain_id = self.active_chain.chain_id
        if not chain_id or chain_id not in self.chains:
            return None
        index = list(self.chains).index(chain_id)
        div = self.get_pinned_pos()
        if index < div and pos >= div:
            self._pinned_chains += 1
            pos -= 1
        elif index >= div and pos < div:
            if self._pinned_chains > 1:
                self._pinned_chains -= 1
            pos += 1
        pos = min(pos, len(self.chains) - 2)
        pos = max(pos, 0)

        if pos == index:
            return pos

        value = self.chains.pop(chain_id)
        items = list(self.chains.items())
        items.insert(pos, (chain_id, value))
        self.chains = dict(items)

        chain = self.chains[chain_id]
        if chain.zynmixer_proc and chain.zynmixer_proc.eng_code == "MR":
            # Moved a mixbus (effects return) so update sends and default mixbus names
            send = 1
            for chain in self.chains.values():
                parts = chain.title.split("Aux Mixbus ")
                if len(parts) > 1:
                    try:
                        parts = parts[1].split(" ")
                        parts[0] = str(send)
                        chain.title = f"Aux Mixbus {' '.join(parts)}"
                    except:
                        pass
                    send += 1
        self.refresh_mixbus_sends()
        self.rebuild_optimisation_cache()
        zynsigman.send(zynsigman.S_CHAIN_MAN, zynsigman.SS_MOVE_CHAIN)
        return pos

    # --- Chain getter functions ---

    def get_active_chain(self):
        """Get the active chain object or None if no active chain

        Returns: Chain object or None on failure
        """

        return self.active_chain

    def get_active_chain_index(self):
        """Get the active chain object or None if no active chain

        Returns: Chain object or None on failure
        """

        return self.get_chain_index(self.active_chain.chain_id)

    def get_chain_index(self, chain_id):
        """ Get the index of a chain from its displayed order
        Args:
            chain_id: Chain id
            Returns: Index of chain or last chain if chain_id not found
        """

        if chain_id in self.chains:
            return list(self.chains).index(chain_id)
        return len(self.chains) - 1

    def get_chain_count(self, audio=True, midi=True, synth=True):
        """ Get the quantity of chains
        Args:
            audio : True to include audio chains
            midi : True to include MIDI chains
            synth : True to include synth chains
        Returns: Quantity of chains
        """

        if audio and midi and synth:
            return len(self.chains)

        count = 0
        for chain in self.chains.values():
            if chain.is_midi() == midi or chain.is_audio() == audio or chain.is_synth() == synth:
                count += 1
        return count

    def get_chain(self, chain_id):
        """ Get a chain object by its id
        Args:
            chain_id: Chain identifier (int)
        Returns: Chain object or None on failure
        """

        try:
            return self.chains[chain_id]
        except KeyError:
            return None

    def get_chain_id_by_index(self, index):
        """ Get a chain ID by its display index
        Args:
            index: Display position
        Returns: Chain identifier (int) or None on failure
        Note: You may use negative index to count back from end, e.g. index=-1 for last chain (which is always the main mixbus)
        """

        try:
            return list(self.chains)[index]
        except IndexError:
            return None

    def get_chain_by_index(self, index):
        """ Get a chain object by its display index
        Args:
            index: Display position
        Returns: Chain object or None on failure
        Note: You may use negative index to count back from end, e.g. index=-1 for last chain (which is always the main mixbus)
        """

        try:
            return self.chains[self.get_chain_id_by_index(index)]
        except KeyError:
            return None

    def get_chain_by_position(self, pos, audio=True, midi=True, synth=True):
        """ Get a chain by its (display) position with option to filter
        Args:
            pos : Display position (0..no of chains)
            audio : True to include audio chains
            midi : True to include MIDI chains
            synth : True to include synth chains
        Returns : Chain object or None if not found
        """

        if audio and midi and synth:
            return self.get_chain_by_index(pos)

        for chain in self.chains.values():
            if chain.is_midi() == midi or chain.is_audio() == audio or chain.is_synth() == synth:
                if pos == 0:
                    return chain
                pos -= 1

        return None

    def get_chain_ids_filtered(self, filter=None):
        """ Get chain list filtered and ordered in display order
        Args:
            filter : A list of chain types to filter => ["audio", "midi", "synth", "generator", "audio_out", "audio_in", "mixbus"]
        Returns : List of chain identifiers
        """

        if not filter:
            return list(self.chains)

        chain_ids_filtered = []
        for chain_id, chain in self.chains.items():
            for type in filter:
                try:
                    if getattr(chain, f"is_{type}")():
                        chain_ids_filtered.append(chain_id)
                except:
                    pass
        return chain_ids_filtered

    def get_chain_id_by_mixer_chan(self, chan, mixbus=False):
        """ Get a chain by the mixer channel
        Args:
            chan: Mixer channel index
            mixbus: True to look for mixbus channels
        Returns: Chain identifier or None on failure
        """

        try:
            pos = self._mixer_chan_2_pos[mixbus][chan]
            return list(self.chains)[pos]
        except:
            return None

        #if mixbus:
        #    eng_code = "MR"
        #else:
        #    eng_code = "MI"
        #for chain_id, chain in self.chains.items():
        #    if chain.zynmixer_proc and chain.zynmixer_proc.mixer_chan == chan and chain.zynmixer_proc.eng_code == eng_code:
        #        return chain_id
        #return None

    def get_pos_by_mixer_chan(self, chan, mixbus=False):
        """ Get display position of a chain by the mixer channel
        Args:
            chan: Mixer channel index
            mixbus: True to look for mixbus channels
        Returns: Chain position or None on failure
        """

        try:
            return self._mixer_chan_2_pos[mixbus][chan]
        except:
            return None

    def get_pos_by_midi_chan(self, chan):
        """ Get a list of display positions (columns) for chains with specified MIDI channel

        Args:
            chan: MIDI channel
        Returns: List of display positions (columns). May be empty list.
        """

        try:
            return self._midi_chan_2_pos[chan]
        except IndexError:
            return []

    def get_chain_ids_by_midi_chan(self, chan):
        """ Get a list of chain identifiers for chains with specified MIDI channel

        Args:
            chan: MIDI channel
        Returns: List of chain identifiers. May be empty list.
        """

        try:
            return self._midi_chan_2_chain_ids[chan]
        except IndexError:
            return []

    def get_send_id(self, idx):
        """ Get chain identifier for an effects send/return mixbus

        Args:
            idx: Index of the effect send/return/mixbus
        Returns:
            Chain identifier or None on failure.
        """
        try:
            return self._sends[idx]
        except IndexError:
            return None

    def rebuild_optimisation_cache(self):
        self._midi_chan_2_chain_ids = [list() for _ in range(MAX_NUM_MIDI_CHANS)] # List of lists of chain ids, indexed by midi channel.
        self._midi_chan_2_pos = [list() for _ in range(MAX_NUM_MIDI_CHANS)] # List of lists of chain positions, indexed by midi channel.
        self._mixer_chan_2_pos = [{},{}] # Map of chain positions, indexed by mixer chan. First map is for chains. Second map is for mixbuses.
        self._sends = [] # List of FX send/return mixbus chain_ids
        for pos, chain in enumerate(self.chains.values()):
            try:
                self._midi_chan_2_chain_ids[chain.midi_chan].append(chain.chain_id)
                self._midi_chan_2_pos[chain.midi_chan].append(pos)
            except:
                pass
            if chain.zynmixer_proc:
                self._mixer_chan_2_pos[chain.zynmixer_proc.eng_code == "MR"][chain.zynmixer_proc.mixer_chan] = pos
                if chain.zynmixer_proc.eng_code == "MR":
                    self._mixer_chan_2_pos[1][chain.zynmixer_proc.mixer_chan] = pos
                    if chain.chain_id:
                        self._sends.append(chain.chain_id)

    # --- Pinned chain managment---
    def set_pinned(self, count):
        """ Set the quantity of pinned chains
        Args:
            count: Quantity of chains to pin to right hand edge of UI
        Note: Includes main mixbus which must always be pinned, so minimum count is 1
        """

        if count:
            self._pinned_chains = count

    def get_pinned_count(self):
        """ Get the quantity of pinned chains
        Returns: Quantity of pinned chains
        """
        return self._pinned_chains

    def get_pinned_pos(self):
        """ Get the index of the first pinned chain
        Returns:
            Position of first pinned chain
        """

        return max(0, len(self.chains) - self._pinned_chains)

    # ------------------------------------------------------------------------
    # Chain Input/Output and Routing Management
    # ------------------------------------------------------------------------

    def get_chain_audio_inputs(self, chain_id):
        """Get list of audio inputs for a chain"""

        if chain_id in self.chains:
            return self.chains[chain_id].audio_in
        return []

    def set_chain_audio_inputs(self, chain_id, inputs):
        """Set chain's audio inputs

        chain_id : Chain id
        inputs : List of jack sources or aliases (None to reset)
        """
        if chain_id in self.chains:
            if inputs:
                self.chains[chain_id].audio_in = inputs
            else:
                self.chains[chain_id].audio_in = ["SYSTEM"]
            self.chains[chain_id].rebuild_audio_graph()

    def get_chain_audio_ouputs(self, chain_id):
        """Get list of audio outputs for a chain"""

        if chain_id in self.chains:
            return self.chains[chain_id].audio_out
        return []

    def set_chain_audio_outputs(self, chain_id, outputs):
        """Set chain's audio outputs

        chain_id : Chain id
        outputs : List of jack destinations or aliases (None to reset)
        """
        if chain_id in self.chains:
            if outputs:
                self.chains[chain_id].audio_out = outputs
            else:
                self.chains[chain_id].audio_out = [0]
            self.chains[chain_id].rebuild_audio_graph()

    def enable_chain_audio_thru(self, chain_id, enable=True):
        """Enable/disable audio pass-through

        enable : True to pass chain's audio input to output when chain is empty
        """
        if chain_id in self.chains and self.chains[chain_id].audio_thru != enable:
            self.chains[chain_id].audio_thru = enable
            self.chains[chain_id].rebuild_audio_graph()

    def get_chain_audio_routing(self, chain_id):
        """Get dictionary of lists of destinations mapped by source"""

        if chain_id in self.chains:
            return self.chains[chain_id].audio_routes
        return {}

    def get_chain_midi_inputs(self, chain_id):
        """Get list of MIDI inputs for a chain"""

        if chain_id in self.chains:
            return self.chains[chain_id].midi_in
        return []

    def set_chain_midi_inputs(self, chain_id, inputs):
        """Set chain's MIDI inputs

        chain_id : Chain id
        inputs : List of jack sources or aliases (None to reset)
        """
        if chain_id in self.chains:
            if inputs:
                self.chains[chain_id].midi_in = inputs
            else:
                self.chains[chain_id].midi_in = ["MIDI-IN"]
            self.chains[chain_id].rebuild_midi_graph()

    def get_chain_midi_ouputs(self, chain_id):
        """Get list of MIDI outputs for a chain"""

        if chain_id in self.chains:
            return self.chains[chain_id].midi_out
        return []

    def set_chain_midi_outputs(self, chain_id, outputs):
        """Set chain's MIDI outputs

        chain_id : Chain id
        outputs : List of jack destinations or aliases (None to reset)
        """
        if chain_id in self.chains:
            if outputs:
                self.chains[chain_id].midi_out = outputs
            else:
                self.chains[chain_id].midi_out = ["MIDI-OUT", "NET-OUT"]
            self.chains[chain_id].rebuild_midi_graph()

    def enable_chain_midi_thru(self, chain_id, enable=True):
        """Enable/disable MIDI pass-through

        enable : True to pass chain's MIDI input to output when chain is empty
        """
        if chain_id in self.chains and self.chains[chain_id].midi_thru != enable:
            self.chains[chain_id].midi_thru = enable
            self.chains[chain_id].rebuild_midi_graph()

    def get_chain_midi_routing(self, chain_id):
        """Get dictionary of lists of destinations mapped by source"""

        if chain_id in self.chains:
            return self.chains[chain_id].midi_routes
        return {}

    def will_midi_howl(self, src_id, dst_id, node_list=None):
        """Checks if adding a connection will cause a MIDI howl-round loop

        src_id : Chain ID of the source chain
        dst_id : Chain ID of the destination chain
        node_list : Do not use - internal function parameter
        Returns : True if adding the route will cause howl-round feedback loop
        """

        if dst_id not in self.chains:
            return False
        if src_id is not None:
            # src_id only provided on first call (not re-entrant cycles)
            if src_id not in self.chains:
                return False
            node_list = [src_id]  # Init node_list on first call
        if dst_id in node_list:
            return True
        node_list.append(dst_id)
        for chain_id in self.chains[dst_id].midi_out:
            if chain_id in self.chains:
                if self.will_midi_howl(None, chain_id, node_list):
                    return True
                node_list.append(chain_id)
        return False

    def will_audio_howl(self, src_id, dst_id, node_list=None):
        """Checks if adding a connection will cause an audio howl-round loop

        src_id : Chain ID of the source chain
        dst_id : Chain ID of the destination chain
        node_list : Do not use - internal function parameter
        Returns : True if adding the route will cause howl-round feedback loop
        """

        if dst_id not in self.chains:
            return False
        if src_id is not None:
            # src_id only provided on first call (not re-entrant cycles)
            if src_id not in self.chains:
                return False
            node_list = [src_id]  # Init node_list on first call
        if dst_id in node_list:
            return True
        node_list.append(dst_id)
        for chain_id in self.chains[dst_id].audio_out:
            if chain_id in self.chains:
                if self.will_audio_howl(None, chain_id, node_list):
                    return True
                node_list.append(chain_id)
        return False

    # ------------------------------------------------------------------------
    # Chain Selection
    # ------------------------------------------------------------------------

    def set_active_chain_by_id(self, chain_id=None):
        """Select the active chain

        chain_id : ID of chain (Default: Reassert current active channel)
        Returns : ID of active chain
        """

        if chain_id is None:
            chain = self.active_chain
        else:
            try:
                chain = self.chains[chain_id]
            except:
                chain = None

        #zynthian_gui_config.logging_call_stack()

        # If no better candidate, set active the first chain (Main)
        if chain is None:
            chain = next(iter(self.chains.values()))

        if self.active_chain != chain:
            self.active_chain = chain
            if chain and chain.midi_chan is not None and chain.midi_chan < 16:
                self.active_midi_chain = chain
            self.state_manager.zynseq.chan = chain.midi_chan
            zynsigman.send_queued(zynsigman.S_CHAIN_MAN, zynsigman.SS_SET_ACTIVE_CHAIN, active_chain_id=self.active_chain.chain_id)
            # If chain receives MIDI, set the active chain in ZynMidiRouter (lib_zyncore)
            if isinstance(chain.zmop_index, int):
                try:
                    lib_zyncore.set_active_chain(chain.zmop_index)
                except Exception as e:
                    logging.error(e)

        return self.active_chain.chain_id

    def set_active_chain_by_object(self, chain_object):
        """Select the active chain

        chain_object : Chain object
        Returns : ID of active chain
        """

        for id in self.chains:
            if self.chains[id] == chain_object:
                self.set_active_chain_by_id(id)
                break
        return self.active_chain.chain_id

    def set_active_chain_by_index(self, index):
        """Select the active chain by display index

        index : Index of chain in display order
        Returns : ID of active chain
        """

        if 0 <= index < len(self.chains):
            return self.set_active_chain_by_id(self.get_chain_id_by_index(index))
        else:
            return self.set_active_chain_by_id(0)

    def next_chain(self, nudge=1):
        """Set active the next chain from the ordered list

        nudge : Quantity of chains to step (may be negative, default: 1)
        Returns : Chain ID
        """

        index = self.get_chain_index(self.active_chain.chain_id)
        index += nudge
        index = max(index, 0)
        index = min(index, len(self.chains) - 1)
        return self.set_active_chain_by_index(index)

    def previous_chain(self, nudge=1):
        """Set active the previous chain from the ordered list

        nudge : Quantity of chains to step (may be negative, default: 1)
        Returns : Chain ID
        """

        return self.next_chain(-nudge)

    def rotate_chain(self):
        if self.active_chain.chain_id > 0:
            return self.next_chain()
        else:
            return self.set_active_chain_by_index(0)

    # ------------------------------------------------------------------------
    # Processor Management
    # ------------------------------------------------------------------------

    def get_available_processor_id(self):
        """Get the next available processor ID"""

        proc_ids = list(self.processors)
        proc_ids.sort()
        id = 0
        while id in proc_ids:
            id += 1
        return id

    def add_processor(self, chain_id, eng_code, slot=None, proc_id=None, fast_refresh=True, eng_config=None, midi_autolearn=True):
        """Add a processor to a chain

        chain : Chain ID
        eng_code : Engine's code
        slot : Slot (position) within subchain (0..last slot, Default: last slot)
        proc_id : Processor UID (Default: Use next available ID)
        eng_config: Extended configuration for the engine (optional)
        midi_autolearn: True to auto-learn MIDI-CC based controllers (i.e. False when creating from state)
        Returns : processor object or None on failure
        """

        if chain_id is not None and chain_id not in self.chains:
            logging.error(f"Chain '{chain_id}' doesn't exist!")
            return None

        if eng_code not in self.engine_info:
            if eng_code != 'None':
                logging.error(f"Engine '{eng_code}' not found!")
            return None
        if proc_id is None:
            proc_id = self.get_available_processor_id()
            send_signal = True
        elif proc_id in self.processors:
            logging.error(f"Processor '{proc_id}' already exists!")
            return None
        else:
            send_signal = False

        if self.state_manager.is_busy():
            self.state_manager.start_busy("add_processor", None, f"adding {eng_code} to chain {chain_id}")
        else:
            self.state_manager.start_busy("add_processor", "Adding Processor", f"adding {eng_code} to chain {chain_id}")

        logging.debug(f"Adding processor '{eng_code}' with ID '{proc_id}'")
        processor = zynthian_processor(eng_code, self.engine_info[eng_code], proc_id)
        processor.set_midi_autolearn(midi_autolearn)
        # Add proc early to allow engines to add more as required, e.g. Aeolus
        self.processors[proc_id] = processor

        if chain_id is not None:
            chain = self.chains[chain_id]
            if processor.type == "MIDI Synth" and chain.synth_slots:
                self.remove_processor(chain_id, chain.synth_slots[0][0])
                pass # Cannot have multiple synth engines
            chain.insert_processor(processor, slot)
            # Update when adding new (proc_id = None)
            if send_signal:
                chain.current_processor = processor

        engine = self.start_engine(processor, eng_code, eng_config)
        if not engine:
            # Failed!! => Remove processor from list
            del self.processors[proc_id]
            self.state_manager.end_busy("add_processor")
            return None

        if chain_id is None:
            # Global processors not in any chain
            self.state_manager.end_busy("add_processor")
            return processor

        if eng_code in ("MI", "MR"):
            chain.zynmixer_proc = processor
            # Add FX sends to existing chains
            self.refresh_mixbus_sends()

        # Update group chains
        for src_chain in self.chains.values():
            if chain_id in src_chain.audio_out:
                src_chain.rebuild_graph()
        chain.rebuild_graph()
        # Signal processor creation, except when creating from state (loading snapshot)
        if send_signal:
            zynsigman.send_queued(zynsigman.S_CHAIN_MAN, zynsigman.SS_ADD_PROCESSOR)
        self.state_manager.end_busy("add_processor")
        # Success!! => Return processor
        return processor

    def can_move_processor(self, processor):
        """ Can processor be moved?
        Args:
            Processor: Processor object
        Returns: True if processor can be moved within chain or to another chain
        """

        if not processor or processor.type in ("MIDI Synth", "Audio Generator"):
            return False
        if processor.type == "Audio Effect" and processor.eng_code not in ["MI", "MR"] and self.get_chain_count(True, False, True) > 1:
            return True
        elif processor.type == "MIDI Tool" and self.get_chain_count(False, True, True) > 1:
            return True
        slots = processor.chain.get_slots_by_type(processor.type)
        if len(slots) > 1 or len(slots) and len(slots[0]) > 1:
            return True
        return False

    def nudge_processor(self, chain_id, processor, up):
        if chain_id not in self.chains:
            return False
        chain = self.chains[chain_id]
        if not chain.nudge_processor(processor, up):
            return False
        for src_chain in self.chains.values():
            if chain_id in src_chain.audio_out:
                src_chain.rebuild_graph()

        if chain.is_audio():
            # Audio chain so mute main output whilst making change (blunt but effective)
            mute = self.state_manager.zynmixer_bus.get_mute(0)
            self.state_manager.mute()
            zynautoconnect.request_audio_connect(True)
            self.state_manager.mute(mute)
        zynautoconnect.request_midi_connect(True)
        return True

    def remove_processor(self, chain_id, processor, stop_engine=True):
        """Remove a processor from a chain

        chain : Chain id
        processor : Instance of processor
        stop_engine : True to stop unused engine
        Returns : True on success
        """

        if chain_id not in self.chains:
            logging.error(f"Chain {chain_id} doesn't exist!")
            return False

        if not isinstance(processor, zynthian_processor):
            logging.error(f"Invalid processor instance '{processor}' can't be removed from chain {chain_id}!")
            return False

        if self.state_manager.is_busy():
            self.state_manager.start_busy("remove_processor", None, f"removing {processor.get_basepath()} from chain {chain_id}")
        else:
            self.state_manager.start_busy(
                "remove_processor", "Removing Processor", f"removing {processor.get_basepath()} from chain {chain_id}")

        for symbol in processor.controllers_dict:
            self.remove_midi_learn(processor, symbol)

        id = None
        for i, p in self.processors.items():
            if processor == p:
                id = i
                break

        if chain_id is None:
            success = True
        else:
            success = self.chains[chain_id].remove_processor(processor)
        if success:
            try:
                self.processors.pop(id)
            except:
                pass
            if stop_engine:
                self.stop_unused_engines()

            if processor.eng_code == "MR":
                self.chains[chain_id].zynmixer_proc = None
                # Remove FX sends from existing chains
                self.refresh_mixbus_sends()

            # Update chain routing (may have effected lots of chains)
            for chain in self.chains.values():
                chain.rebuild_graph()
            zynsigman.send_queued(zynsigman.S_CHAIN_MAN, zynsigman.SS_REMOVE_PROCESSOR)

        self.state_manager.end_busy("remove_processor")
        return success

    def refresh_mixbus_sends(self):
        mixbus_chain_ids = self.get_chain_ids_filtered(["mixbus"])
        for processor in self.processors.values():
            if processor.eng_code != "MI":
                continue

            # Remove send controller pages
            for page in list(processor.ctrl_screens_dict):
                if page.startswith("send "):
                    processor.ctrl_screens_dict.pop(page)
            # Create each send page
            for send_idx, send_chain_id in enumerate(mixbus_chain_ids):
                if send_chain_id == 0:  # Exclude main mixbus
                    continue
                send_chain = self.chains[send_chain_id]
                level_symbol = f"send_{send_chain_id}_level"
                mode_symbol = f"send_{send_chain_id}_mode"
                name_prefix = f"send {send_idx + 1}"
                # Generate a decent title for the ctrl_screen
                ctrl_screen_title = name_prefix
                if send_chain.title:
                    send_chain_name = send_chain.title
                else:
                    send_chain_name = send_chain.get_processors("Audio Effect")[0].get_name()
                if send_chain_name:
                    ctrl_screen_title += f" - {send_chain_name}"
                # Create or update send controllers
                if level_symbol in processor.controllers_dict:
                    processor.controllers_dict[level_symbol].name = f"{name_prefix} level"
                    processor.controllers_dict[level_symbol].short_name = f"{name_prefix} level"
                    processor.controllers_dict[mode_symbol].name = f"{name_prefix} mode"
                    processor.controllers_dict[mode_symbol].short_name = f"{name_prefix} mode"
                else:
                    send = send_chain.zynmixer_proc.mixer_chan - 2 # FX returns start at 2, after main and aux
                    processor.controllers_dict[level_symbol] = zynthian_controller(processor.engine, level_symbol, {
                        'name': f'{name_prefix} level',
                        'value_max': 1.0,
                        'value_default': 0.0,
                        'value': processor.zynmixer.get_send_level(processor.mixer_chan, send),
                        'processor': processor,
                        'graph_path': ["send_level", send]
                    })
                    processor.controllers_dict[mode_symbol] = zynthian_controller(processor.engine, mode_symbol, {
                        'name': f'{name_prefix} mode',
                        'value_max': 1,
                        'value_default': 0,
                        'value': processor.zynmixer.get_send_mode(processor.mixer_chan, send),
                        'labels': ['post fader', 'pre fader'],
                        'processor': processor,
                        'graph_path': ["send_mode", send]
                    })
                # Add the control screen
                processor.ctrl_screens_dict[ctrl_screen_title] = [processor.controllers_dict[level_symbol], processor.controllers_dict[mode_symbol]]
            # Remove send controllers that doesn't exist anymore
            for symbol in list(processor.controllers_dict):
                if not symbol.startswith("send_"):
                    continue
                s, c, t = symbol.split("_")
                if int(c) not in mixbus_chain_ids:
                    del processor.controllers_dict[symbol]

    def get_slot_count(self, chain_id, type=None):
        """Get the quantity of slots in a chain

        id : Chain id
        type : Processor type to filter result (Default: all types)
        Returns : Quantity of slots in chain or subchain
        """

        if chain_id not in self.chains:
            return 0
        return self.chains[chain_id].get_slot_count(type)

    def get_processor_count(self, chain_id=None, type=None, slot=None):
        """Get the quantity of processors in a slot

        chain_id : Chain id (Default: all processors in all chains)
        type : Processor type to filter result (Default: all types)
        slot : Index of slot or None for whole chain (Default: whole chain)
        Returns : Quantity of processors in (sub)chain or slot
        """

        if chain_id is None:
            count = 0
            for chain in self.chains:
                count += self.chains[chain].get_processor_count(type, slot)
                return count
        if chain_id not in self.chains:
            return 0
        return self.chains[chain_id].get_processor_count(type, slot)

    def get_processor_id(self, processor):
        """Get processor uid from processor object

        processor : Processor object
        Returns : Processor UID or None if not found
        """

        for uid, proc in self.processors.items():
            if proc == processor:
                return uid
        return None

    def get_processors(self, chain_id=None, type=None, slot=None):
        """Get a list of processors in (sub)chain (slot)

        chain_id : Chain id (Default: all processors)
        type : Processor type to filter result (Default: all types)
        slot : Index of slot or None for whole chain (Default: whole chain)
        Returns : List of processor objects
        """

        if chain_id is None:
            processors = []
            for chain in self.chains:
                processors += (self.chains[chain].get_processors(type, slot))
            return processors
        if chain_id not in self.chains:
            return []
        return self.chains[chain_id].get_processors(type, slot)

    # ------------------------------------------------------------------------
    # Engine Management
    # ------------------------------------------------------------------------

    def start_engine(self, processor, eng_code, eng_config=None):
        """Starts or reuse an existing engine

        processor : processor owning engine
        eng_code : Engine short code
        eng_config: Extended configuration (optional)
        Returns : engine object
        """

        if eng_code not in self.engine_info:
            logging.error(f"Engine '{eng_code}' not found!")
            return None

        if eng_code in self.zyngines:
            # Engine already started
            zyngine = self.zyngines[eng_code]
        else:
            # Start new engine instance
            info = self.engine_info[eng_code]
            zynthian_engine_class = info["ENGINE"]
            if eng_code[0:3] == "JV/":
                eng_key = f"JV/{self.zyngine_counter}"
                zyngine = zynthian_engine_class(eng_code, self.state_manager, False)
            elif eng_code in ("SF", "PD"):
                eng_key = f"{eng_code}/{self.zyngine_counter}"
                zyngine = zynthian_engine_class(self.state_manager)
            else:
                eng_key = eng_code
                zyngine = zynthian_engine_class(self.state_manager)

            self.zyngines[eng_key] = zyngine
            self.zyngine_counter += 1
            # Force Jack Tempo to update
            self.state_manager.zynseq.libseq.updateJackPosition()

        # Set extended configuration (optional)
        if eng_config:
            zyngine.set_extended_config(eng_config)

        processor.set_engine(zyngine)
        return zyngine

    def stop_unused_engines(self):
        """Stop engines that are not used by any processors"""
        for eng_key in list(self.zyngines.keys()):
            if not self.zyngines[eng_key].processors:
                logging.debug(f"Stopping Unused Engine '{eng_key}' ...")
                self.state_manager.set_busy_details(f"stopping engine {self.zyngines[eng_key].get_name()}")
                self.zyngines[eng_key].stop()
                del self.zyngines[eng_key]

    def stop_unused_jalv_engines(self):
        """Stop JALV engines that are not used by any processors"""
        for eng_key in list(self.zyngines.keys()):
            if len(self.zyngines[eng_key].processors) == 0 and eng_key[0:3] == "JV/":
                logging.debug(f"Stopping Unused Jalv Engine '{eng_key}'...")
                self.state_manager.set_busy_details(f"stopping engine {self.zyngines[eng_key].get_name()}")
                self.zyngines[eng_key].stop()
                del self.zyngines[eng_key]

    def filtered_engines_by_cat(self, etype, all=False):
        """Get dictionary of engine info filtered by type and indexed by catagory
            etype: type of engine
            all: include "disabled" engine too
        """
        result = {}
        if etype in zynthian_lv2.engines_by_type:
            # Add categories in right order
            for eng_cat in zynthian_lv2.engine_categories[etype]:
                result[eng_cat] = {}
            # Add engines to each category
            for eng_code, info in zynthian_lv2.engines_by_type[etype].items():
                eng_cat = info["CAT"]
                if eng_cat in result:
                    hide_if_single_proc = eng_code not in self.single_processor_engines or eng_code not in self.zyngines
                    if (info["ENABLED"] or all) and hide_if_single_proc:
                        result[eng_cat][eng_code] = info
                else:
                    logging.error(f"Engine '{eng_code}' has invalid category '{eng_cat}'!")
            # Remove empty categories
            for eng_cat in list(result.keys()):
                if not result[eng_cat]:
                    del result[eng_cat]
        return result

    def get_next_jackname(self, jackname, sanitize=True):
        """Get the next available jackname

        jackname : stub of jackname
        """

        try:
            # Jack, when listing ports, accepts regular expressions as the jack name.
            # So, for avoiding problems, jack names shouldn't contain regex characters.
            if sanitize:
                jackname = re.sub("[\_]{2,}", "_", re.sub("[\s\'\*\(\)\[\]]", "_", jackname))
            names = set()
            for processor in self.get_processors():
                jn = processor.get_jackname()
                if jn is not None and jn.startswith(jackname):
                    names.add(jn)
            i = 1
            while f"{jackname}-{i:02}" in names:
                i += 1
            return f"{jackname}-{i:02}"
        except Exception as e:
            logging.error(e)
            return f"{jackname}-00"

    def reload_engine_preset_info(self, eng_code):
        """Reload preset info for an engine

        eng_code : engine code
        """

        self.state_manager.start_busy("reload_engine_preset_info", "Scanning for banks & presets")
        if eng_code.startswith("JV/"):
            try:
                plugin_uri = self.engine_info[eng_code]['URL']
                #zynthian_lv2.generate_presets_cache_workaround()
                zynthian_lv2.generate_plugin_presets_cache(plugin_uri, True)
            except Exception as e:
                logging.error(e)

        for proc in self.processors.values():
            if eng_code and proc.eng_code.startswith(eng_code):
                try:
                    proc.engine.load_preset_info()
                except:
                    pass
        self.state_manager.end_busy("reload_engine_preset_info")

    # ------------------------------------------------------------------------
    # State Management
    # ------------------------------------------------------------------------

    def get_state(self):
        """Get dictionary of chain slot states indexed by chain id"""

        state = {}
        for chain_id in self.chains:
            state[chain_id] = self.chains[chain_id].get_state()
        return state

    def set_state(self, state, engine_config, merge=False):
        """Create chains from state

        state : List of chain states
        engine_config: Extended engine config
        Returns : True on success
        """

        self.state_manager.start_busy("set_chain_state", None, "loading chains")

        # Clean all chains but don't stop unused engines
        if not merge:
            self.remove_all_chains(False)

            # Reusing Jalv engine instances raise problems (audio routing & jack names, etc..),
            # so we stop Jalv engines!
            self.stop_unused_jalv_engines()  # TODO: Can we factor this out? => Not yet!!

        for chain_id, chain_state in state.items():
            if merge:
                chain_id = None
            chain_id = self.add_chain_from_state(chain_id, chain_state)
            if "slots" in chain_state:
                slot = 0
                for slot_state in chain_state["slots"]:
                    # slot_state is a dict of proc_id:proc_type for procs in this slot
                    for proc_id, eng_code in slot_state.items():
                        if proc_id == str(zynthian_state_manager.MAIN_MIXBUS_ID):
                            continue  # Do not replace main mixbus audio mixer processor
                        try:
                            eng_config = engine_config[eng_code]
                        except:
                            eng_config = None
                        # TODO: insert in correct slot, accounting for slot being relative to subchain type
                        # Use index to identify first proc in slot (add in series)
                        processor = self.add_processor(chain_id, eng_code, slot, proc_id=int(proc_id), eng_config=eng_config, midi_autolearn=False)
                        if processor:
                            slot = self.chains[chain_id].get_slot(processor)
                    slot += 1
            if "zctrls" in chain_state:
                self.chains[chain_id].set_zctrls_state(chain_state["zctrls"])
        self.rebuild_optimisation_cache()
        self.state_manager.end_busy("set_chain_state")

    def restore_presets(self):
        """Restore presets in active chain"""

        for processor in self.get_processors(self.active_chain.chain_id):
            processor.restore_preset()

    # ----------------------------------------------------------------------------
    # MIDI CC
    # ----------------------------------------------------------------------------

    def print_midi_learn(self):
        print(f"\n\n*********** CHAIN MIDI LEARN TABLE ***********")
        for key, zctrls in self.chain_midi_cc_binding.items():
            key = int(key)
            chain_id = (key >> 16) & 0xFF
            midi_chan = (key >> 8) & 0xFF
            midi_cc = key & 0x7F
            print(f"CHAIN={chain_id}, CHAN={midi_chan}, CC={midi_cc} =>")
            for zctrl in zctrls:
                print(f"     {zctrl.symbol}")
        print(f"*********** ABSOLUTE MIDI LEARN TABLE ***********")
        for key, zctrls in self.absolute_midi_cc_binding.items():
            key = int(key)
            zmip = (key >> 16) & 0xFF
            midi_chan = (key >> 8) & 0xFF
            midi_cc = key & 0x7F
            print(f"ZMIP={zmip}, CHAN={midi_chan}, CC={midi_cc} =>")
            for zctrl in zctrls:
                print(f"     {zctrl.symbol}")
        print(f"**************************************************\n\n")

    def add_midi_learn(self, midi_chan, midi_cc, zctrl, zmip=None):
        """Adds a midi learn configuration

        midi_chan : MIDI channel to bind (None / 0xFF to not bind to MIDI channel)
        midi_cc : CC number of CC message
        zctrl : Controller object
        zmip : ZMIP of absolute learn device (Optional: Default - do not learn absolute)
        """

        if zctrl is None:
            return

        # Remove previous mappings with extra care
        if zmip is None or zmip != ZMIP_STEP_INDEX:
            # When mapping chain or absolute, remove previous mappings, except custom ZynStep mappings
            map_zynstep = not self.is_custom_zynstep_mapping(zctrl)
            self.remove_midi_learn_from_zctrl(zctrl, chain=True, abs=True, zynstep=map_zynstep)
        else:
            # When explicitly mapping ZynStep, don't remove previous chain/absolute mappings
            map_zynstep = True
            self.remove_midi_learn_from_zctrl(zctrl, chain=False, abs=False, zynstep=True)

        if midi_chan is None:
            midi_chan = 0xff
        logging.debug(f"(chan={midi_chan}, midi_cc={midi_cc}, zctrl={zctrl.symbol}, zmip={zmip})")

        # Chain learning for external devices => All chain types
        if zmip is None:
            if zctrl.processor and zctrl.processor.chain_id is not None:
                key = (zctrl.processor.chain_id << 16) | (midi_chan << 8) | midi_cc
                if key in self.chain_midi_cc_binding:
                    if zctrl not in self.chain_midi_cc_binding[key]:
                        self.chain_midi_cc_binding[key].append(zctrl)
                else:
                    self.chain_midi_cc_binding[key] = [zctrl]

        # Absolute learning for external devices
        elif zmip != ZMIP_STEP_INDEX:
            key = (zmip << 16) | (midi_chan << 8) | midi_cc
            if key in self.absolute_midi_cc_binding:
                if zctrl not in self.absolute_midi_cc_binding[key]:
                    self.absolute_midi_cc_binding[key].append(zctrl)
            else:
                self.absolute_midi_cc_binding[key] = [zctrl]

        # ZynStep mapping => MIDI chains only
        if map_zynstep and zctrl.processor and zctrl.processor.midi_chan is not None:
            key = (ZMIP_STEP_INDEX << 16) | (zctrl.processor.midi_chan << 8) | midi_cc
            if key in self.absolute_midi_cc_binding:
                if zctrl not in self.absolute_midi_cc_binding[key]:
                    self.absolute_midi_cc_binding[key].append(zctrl)
            else:
                self.absolute_midi_cc_binding[key] = [zctrl]

        #self.print_midi_learn()

    def add_zynstep_midi_learn(self, midi_cc, zctrl):
        """Adds a midi learn configuration for zynstep

        midi_cc : CC number of CC message
        zctrl : Controller object
        """

        self.add_midi_learn(None, midi_cc, zctrl, ZMIP_STEP_INDEX)

    def remove_midi_learn(self, proc, symbol, chain=True, abs=True, zynstep=None):
        """Remove a midi learn configuration

        proc : Processor object
        symbol : Control symbol
        chain : remove chain MIDI learn
        abs : remove absolute MIDI learn
        zynstep : remove zynstep MIDI learn. None for auto-delete (delete if it matches chain/abs MIDI learn).
        """

        try:
            zctrl = proc.controllers_dict[symbol]
        except:
            return
        self.remove_midi_learn_from_zctrl(zctrl, chain=chain, abs=abs, zynstep=zynstep)

    def remove_midi_learn_from_zctrl(self, zctrl, chain=True, abs=True, zynstep=None):
        """Remove a midi learn configuration

        zctrl : zctrl object
        chain : remove chain MIDI learn
        abs : remove absolute MIDI learn
        zynstep : remove zynstep MIDI learn. None for auto-delete (delete if it matches chain/abs MIDI learn).
        """

        # processor.id may not exist! logging.debug(f"(proccessor={zctrl.processor.id}, symbol={zctrl.symbol})")

        if zynstep is None:
            zynstep = not self.is_custom_zynstep_mapping(zctrl)

        if chain:
            for key in list(self.chain_midi_cc_binding):
                zctrls = self.chain_midi_cc_binding[key]
                try:
                    zctrls.remove(zctrl)
                except:
                    pass
                if not zctrls:
                    self.chain_midi_cc_binding.pop(key)
        if abs:
            for key in list(self.absolute_midi_cc_binding):
                if (key >> 16) & 0xff == ZMIP_STEP_INDEX:
                    continue
                zctrls = self.absolute_midi_cc_binding[key]
                try:
                    zctrls.remove(zctrl)
                except:
                    pass
                if not zctrls:
                    self.absolute_midi_cc_binding.pop(key)

        if zynstep:
            for key in list(self.absolute_midi_cc_binding):
                if (key >> 16) & 0xff != ZMIP_STEP_INDEX:
                    continue
                zctrls = self.absolute_midi_cc_binding[key]
                try:
                    zctrls.remove(zctrl)
                except:
                    pass
                if not zctrls:
                    self.absolute_midi_cc_binding.pop(key)

    def get_midi_learn_from_zctrl(self, zctrl, chain=True, abs=True, zynstep=True):
        if chain:
            for key, zctrls in self.chain_midi_cc_binding.items():
                if zctrl in zctrls:
                    return [key, "chain"]
        if abs:
            for key, zctrls in self.absolute_midi_cc_binding.items():
                if (key >> 16) & 0xff == ZMIP_STEP_INDEX:
                    continue
                if zctrl in zctrls:
                    return [key, "abs"]
        if zynstep:
            for key, zctrls in self.absolute_midi_cc_binding.items():
                if (key >> 16) & 0xff != ZMIP_STEP_INDEX:
                    continue
                if zctrl in zctrls:
                    return [key, "zynstep"]

    def is_custom_zynstep_mapping(self, zctrl):
        # Look for a non-zynstep mapping (absolute or chain)
        try:
            key = self. get_midi_learn_from_zctrl(zctrl, chain=True, abs=True, zynstep=False)[0]
            midi_cc = key & 0x7f
        except:
            midi_cc = None
        # Look for a zynstep mapping
        for key, zctrls in self.absolute_midi_cc_binding.items():
            if ZMIP_STEP_INDEX == (key >> 16) & 0xff and zctrl in zctrls:
                # Check if it's custom mapping => It's different to non-zynstep mapping (not auto-mapped!)
                if midi_cc is None or midi_cc != key & 0x7f:
                    return True
                else:
                    return False
        return False

    def get_zynstep_mapped_zctrl(self, midi_chan, cc_num):
        try:
            key = (ZMIP_STEP_INDEX << 16) | (midi_chan << 8) | cc_num
            return self.absolute_midi_cc_binding[key][0]
        except:
            return None

    def midi_control_change(self, zmip, midi_chan, cc_num, cc_val):
        """Send MIDI CC message to relevant chain

        zmip : Index of MIDI input device
        midi_chan : MIDI channel
        cc_num : CC number
        cc_val : CC value
        """
        # Handle bank change (CC0/32)
        # TODO: Validate and optimise bank change code
        if zynthian_gui_config.midi_bank_change:
            for chain_id in self._midi_chan_2_chain_ids[midi_chan]:
                chain = self.chains[chain_id]
                if cc_num == 0:
                    for processor in chain.get_processors():
                        processor.midi_bank_msb(cc_val)
                        break
                    return
                elif cc_num == 32:
                    for processor in chain.get_processors():
                        processor.midi_bank_lsb(cc_val)
                        break
                    return

        key_low = (midi_chan << 8) | cc_num

        # Handle controller feedback from setBfree engine => setBfree sends feedback in assigned MIDI channels
        # Each engine sending feedback should use a separated zmip, currently only setBfree does.
        if zmip == ZMIP_CTRL_INDEX:
            #logging.debug(f"MIDI CONTROL FEEDBACK {midi_chan}, {cc_num} => {cc_val}")
            for proc in zynautoconnect.ctrl_fb_procs:
                try:
                    if proc.part_i == midi_chan:
                        for symbol, zctrl in proc.controllers_dict.items():
                            if zctrl.midi_cc == cc_num:
                                #logging.debug(f"CONTROLLER FEEDBACK {proc.id}:{symbol} ({midi_chan}:{cc_num}) => {cc_val}")
                                #zctrl.midi_control_change(cc_val, send=False)
                                zctrl.set_value(cc_val, send=False)
                                return
                except Exception as e:
                    logging.warning(f"Can't manage control feedback for CH{midi_chan}:CC{cc_num} => {e}")
            return

        # Handle absolute CC binding
        try:
            key = (zmip << 16) | key_low
            zctrls = self.absolute_midi_cc_binding[key]
            for zctrl in zctrls:
                zctrl.midi_control_change(cc_val)
                #logging.debug(f"ABSOLUTE LEARNED ZCTRL {zctrl.symbol} ...")
        except:
            pass
        if zmip == ZMIP_STEP_INDEX:
            #logging.debug(f"MIDI CC FROM ZYNSTEP:  {midi_chan}#{cc_num} => {cc_val}")
            return

        # Handle active chain CC binding
        try:
            # Channel-bond
            try:
                key = (self.active_chain.chain_id << 16) | key_low
                zctrls1 = self.chain_midi_cc_binding[key]
            except:
                zctrls1 = []
            # Channel-unbond
            try:
                key = (self.active_chain.chain_id << 16) | (0xff << 8) | cc_num
                zctrls2 = self.chain_midi_cc_binding[key]
            except:
                zctrls2 = []
            # Change controllers values
            for zctrl in zctrls1 + zctrls2:
                zctrl.midi_control_change(cc_val)
        except:
            pass

    def clean_midi_learn(self, obj):
        """Clean MIDI learn from controls

        obj : Object to clean [chain_id | processor | zctrl] (Default: active chain)
        """

        if obj == None:
            obj = self.active_chain.chain_id
        if obj == None:
            return

        if isinstance(obj, zynthian_controller):
            self.remove_midi_learn(obj.processor, obj.symbol)

        elif isinstance(obj, zynthian_processor):
            for symbol in obj.controllers_dict:
                self.remove_midi_learn(obj, symbol)

        elif isinstance(obj, int):
            for proc in self.get_processors(obj):
                for symbol in proc.controllers_dict:
                    self.remove_midi_learn(proc, symbol)

    # ----------------------------------------------------------------------------
    # MIDI Program Change (when ZS3 is disabled!)
    # ----------------------------------------------------------------------------

    def set_midi_prog_preset(self, midi_chan, midi_prog):
        """Send MIDI PC message to relevant chain

        midi_chan : MIDI channel
        midi_prog : Program change value
        """

        changed = False
        for processor in self.get_processors(type="MIDI Synth"):
            try:
                mch = processor.midi_chan
                if mch is None or mch == midi_chan:
                    # TODO This is really DIRTY!!
                    # Fluidsynth engine => ignore Program Change on channel 10
                    if processor.engine.nickname == "FS" and mch == 9:
                        continue
                    changed |= processor.set_preset(midi_prog, True)
            except Exception as e:
                logging.error(f"Can't set preset for CH#{midi_chan}:PC#{midi_prog} => {e}")
        return changed

    def set_midi_chan(self, chain_id, midi_chan):
        """Set chain MIDI channel

        chain_id : Chain ID
        midi_chan : MIDI channel
        """

        if chain_id not in self.chains:
            return
        chain = self.chains[chain_id]

        # Remove current midi_chan(s) from dictionary
        if isinstance(chain.midi_chan, int):
            midi_chans = []
            # Single MIDI channel
            if 0 <= chain.midi_chan < MAX_NUM_MIDI_CHANS:
                midi_chans = [chain.midi_chan]
            # ALL MIDI channels
            elif chain.midi_chan == 0xffff:
                midi_chans = list(range(MAX_NUM_MIDI_CHANS))

        chain.set_midi_chan(midi_chan)
        for mc in range(16):
            if not self._midi_chan_2_chain_ids[mc]:
                self.state_manager.zynseq.enable_channel(mc, False)
        self.state_manager.zynseq.enable_channel(midi_chan, True, True)

        # Add new midi_chan(s) to dictionary
        if isinstance(midi_chan, int):
            midi_chans = []
            # Single MIDI channel
            if 0 <= midi_chan < MAX_NUM_MIDI_CHANS:
                midi_chans = [midi_chan]
            # ALL MIDI channels
            elif midi_chan == 0xffff:
                midi_chans = list(range(MAX_NUM_MIDI_CHANS))
        self.rebuild_optimisation_cache()

    def get_free_midi_chans(self):
        """Get list of unused MIDI channels"""

        free_chans = list(range(MAX_NUM_MIDI_CHANS))
        try:
            free_chans.remove(zynthian_gui_config.master_midi_channel)
        except:
            pass
        for chain_id in self.chains:
            try:
                free_chans.remove(self.chains[chain_id].midi_chan)
            except:
                pass
        return free_chans

    def get_next_free_midi_chan(self, chan=0):
        """Get next unused MIDI channel

        chan : MIDI channel to search from (Default: 0)
        """

        free_chans = self.get_free_midi_chans()
        if chan is None:
            chan = 0
        for i in range(chan, MAX_NUM_MIDI_CHANS):
            if i in free_chans:
                return i
        for i in range(chan):
            if i in free_chans:
                return i
        raise Exception("No available free MIDI channels!")

    def get_num_chains_midi_chan(self, chan):
        """Get num of chains with MIDI channel

        chan : MIDI channel to search
        """

        try:
            return len(self._midi_chan_2_chain_ids[chan])
        except:
            return 0

    def is_free_zmop_index(self, zmop_index):
        """Get next unused zmop index
        """

        for chain in self.chains.values():
            if chain.zmop_index is not None and chain.zmop_index == zmop_index:
                return False
        return True

    def get_next_free_zmop_index(self):
        """Get next unused zmop index
        """

        busy_zmops = [0] * MAX_NUM_ZMOPS
        for chain_id in self.chains:
            try:
                busy_zmops[self.chains[chain_id].zmop_index] = 1
            except:
                pass
        for i in range(0, MAX_NUM_ZMOPS):
            if not busy_zmops[i]:
                return i
        return None

    def get_synth_chain(self, midi_chan):
        """Get a chain in a given MIDI channel, preferably, a synth chain.
           If several synth chains in the same MIDI channel, take the first one.

        chan : MIDI channel
        Returns : Chain ID or None if not found
        """
        # Try to find a Synth processor in the specified MIDI channel ...
        for chain_id in self._midi_chan_2_chain_ids[midi_chan]:
            processors = self.get_processors(chain_id, "MIDI Synth")
            if len(processors) > 0:
                return self.chains[chain_id]
        # If not synth processors, return first chain in the MIDI channel
        for chain_id in self._midi_chan_2_chain_ids[midi_chan]:
            return self.chains[chain_id]
        return None

    def get_synth_processor(self, midi_chan):
        """Get a synth processor on MIDI channel
           If several synth chains in the same MIDI channel, take the first one.
           if not synth processors, try other processor types.

        chan : MIDI channel
        Returns : Processor or None on failure
        """
        # Try to find a Synth processor in the specified MIDI channel ...
        for chain_id in self._midi_chan_2_chain_ids[midi_chan]:
            processors = self.get_processors(chain_id, "MIDI Synth")
            if len(processors) > 0:
                return processors[0]
        # If not synth processors, try other processor types...
        for chain_id in self._midi_chan_2_chain_ids[midi_chan]:
            processors = self.get_processors(chain_id)
            if len(processors) > 0:
                return processors[0]
        return None

    def get_synth_preset_name(self, midi_chan):
        """Get the preset name for a synth on MIDI channel
           If several synth chains in the same MIDI channel, take the first one.
           if not synth processors, try other processor types.

        chan : MIDI channel
        Returns : Preset name or None on failure
        """
        proc = self.get_synth_processor(midi_chan)
        if proc:
            res = proc.get_preset_name()
            if not res:
                res = proc.get_bank_name()
            if not res:
                res = proc.get_name()
            if res:
                return res.replace("_", " ")
        return ""

    # ---------------------------------------------------------------------------
    # Extended Config
    # ---------------------------------------------------------------------------

    def get_zyngines_state(self):
        """Get state model for engines extended configuration as a dictionary"""

        # TODO: Although this relates to zyngine it may be advantageous to move to processor state
        state = {}
        for zyngine in self.zyngines.values():
            state[zyngine.nickname] = zyngine.get_extended_config()
        return state

# -----------------------------------------------------------------------------


# Call class method to get engine info into the "engine_info" class variable
zynthian_chain_manager.get_engine_info()

# -----------------------------------------------------------------------------
