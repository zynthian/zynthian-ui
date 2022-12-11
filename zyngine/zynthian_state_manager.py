# -*- coding: utf-8 -*-
# ****************************************************************************
# ZYNTHIAN PROJECT: Zynthian State Manager (zynthian_state_manager)
#
# zynthian state manager
#
# Copyright (C) 2015-2022 Fernando Moyano <jofemodo@zynthian.org>
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

import base64
import ctypes
from datetime import datetime
from glob import glob
import logging

# Zynthian specific modules
import zynconf
import zynautoconnect
from zyngine.zynthian_chain_manager import *
from zyngine.zynthian_processor import zynthian_processor 
from zyngui.zynthian_audio_recorder import zynthian_audio_recorder
from zyngine import zynthian_engine_audio_mixer
from zyngine import zynthian_gui_config
from zynlibs.zynseq import zynseq
from zyncoder.zyncore import *
from zyngine import zynthian_midi_filter
from zyncoder.zyncore import get_lib_zyncore
from zyngine import zynthian_controller

# ----------------------------------------------------------------------------
# Zynthian State Manager Class
# ----------------------------------------------------------------------------

SNAPSHOT_FORMAT_VERSION = 1

class zynthian_state_manager:

    def __init__(self):
        """ Create an instance of a state manager

        Manages full Zynthian state, i.e. snapshot
        """

        logging.warning("Creating state manager")
        self.chain_manager = zynthian_chain_manager(self)
        self.last_snapshot_fpath = ""
        self.last_snapshot_count = 0 # Increments each time a snapshot is loaded - modules may use to update if required
        self.reset_zs3()
        
        self.alsa_mixer_processor = zynthian_processor(("Mixer", "ALSA Mixer", "MIXER", None, zynthian_engine_alsa_mixer, True))
        self.alsa_mixer_processor.engine = zynthian_engine_alsa_mixer()
        self.alsa_mixer_processor.refresh_controllers()
        self.audio_recorder = zynthian_audio_recorder()
        self.zynmixer = zynthian_engine_audio_mixer.zynmixer()
        self.zynseq = zynseq.zynseq()

        self.midi_filter_script = None
        self.midi_learn_zctrl = None
        self.midi_learn_mode = 0 # 0:Disabled, 1:MIDI Learn, 2:ZS3 Learn
        self.zs3 = {} # Dictionary or zs3 configs indexed by "ch/pc"
        self.last_zs3 = 0
        self.status_info = {}

        # Initialize MIDI & Switches
        self.dtsw = []
        try:
            self.zynmidi = zynthian_zcmidi()
            self.zynswitches_init()
            self.zynswitches_midi_setup()
        except Exception as e:
            logging.error("ERROR initializing MIDI & Switches: {}".format(e))
            self.zynmidi = None

        # Init Auto-connector
        self.zynautoconnect_audio_flag = False
        self.zynautoconnect_midi_flag = False
        zynautoconnect.start(self)

    def reset(self):
        zynautoconnect.stop()
        self.last_snapshot_fpath = ""
        self.zynseq.load("")
        self.chain_manager.remove_all_chains(True)
        self.zynmixer.reset_state()
        self.zynseq.load("")
        self.reload_midi_config()
        zynautoconnect.start(self)

    #----------------------------------------------------------------------------
    # Snapshot Save & Load
    #----------------------------------------------------------------------------

    def get_state(self):
        """Get a dictionary describing the full state model"""

        self.save_zs3("zs3-0", "Last state")
        self.clean_zs3()
        state = {
            'format_version': SNAPSHOT_FORMAT_VERSION,
            'last_snapshot_fpath': self.last_snapshot_fpath, #TODO: Why is this required?
            'midi_profile_state': self.get_midi_profile_state(),
            'chains': self.chain_manager.get_state(),
            'zs3': self.zs3
        }

        state["engine_config"] = {}
        for engine in self.chain_manager.get_engines():
            for id, info in self.chain_manager.engine_info.items():
                if isinstance(engine, info[4]):
                    state["engine_config"][engine][id] = engine.get_extended_config()

        # Add ALSA-Mixer setting
        if zynthian_gui_config.snapshot_mixer_settings and self.alsa_mixer_processor:
            state['alsa_mixer'] = self.alsa_mixer_processor.get_state()

        # Audio Recorder Armed
        armed_state = []
        for midi_chan in [0,1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,256]:
            if self.audio_recorder.is_armed(midi_chan):
                armed_state.append(midi_chan)
        if armed_state:
            state['audio_recorder_armed'] = armed_state
        
        # Zynseq RIFF data
        binary_riff_data = self.zynseq.get_riff_data()
        b64_data = base64_encoded_data = base64.b64encode(binary_riff_data)
        state['zynseq_riff_b64'] = b64_data.decode('utf-8')

        return state

    def save_snapshot(self, fpath, extra_data=None):
        """Save current state model to file

        fpath : Full filename and path
        extra_data : Dictionary to add to snapshot, e.g. UI specific config
        Returns : True on success
        """

        try:
            # Get state
            state = self.get_state()
            if isinstance(extra_data, dict):
                state = {**state, **extra_data}

            # JSON Encode
            json = JSONEncoder().encode(state)
            logging.info("Saving snapshot %s => \n%s", fpath, json)

        except Exception as e:
            logging.error("Can't generate snapshot: %s" %e)
            return False

        try:
            with open(fpath,"w") as fh:
                logging.info("Saving snapshot %s => \n%s" % (fpath, json))
                fh.write(json)
                fh.flush()
                os.fsync(fh.fileno())

        except Exception as e:
            logging.error("Can't save snapshot file '%s': %s" % (fpath, e))
            return False

        self.last_snapshot_fpath = fpath
        return True


    def load_snapshot(self, fpath, load_chains=True, load_sequences=True):
        """Loads a snapshot from file
        
        fpath : Full path and filename of snapshot file
        load_chains : True to load chains
        load_sequences : True to load sequences into step sequencer
        Returns : State dictionary or None on failure
        """

        try:
            with open(fpath,"r") as fh:
                json = fh.read()
                logging.info("Loading snapshot %s => \n%s" % (fpath, json))
        except Exception as e:
            logging.error("Can't load snapshot '%s': %s" % (fpath, e))
            return None

        mute = self.zynmixer.get_mute(256)
        try:
            snapshot = JSONDecoder().decode(json)
            state = self.fix_snapshot(snapshot)

            if load_chains:
                # Mute output to avoid unwanted noises
                self.zynmixer.set_mute(256, True)
                if 'chains' in state:
                    self.chain_manager.set_state(state['chains'])
                self.chain_manager.stop_unused_engines()
                if 'active_chain' in state:
                    self.chain_manager.set_active_chain_by_id('active_chain')

            if load_sequences and 'zynseq_riff_b64' in state:
                b64_bytes = state['zynseq_riff_b64'].encode('utf-8')
                binary_riff_data = base64.decodebytes(b64_bytes)
                self.zynseq.restore_riff_data(binary_riff_data)

            if load_chains and load_sequences:
                if 'alsa_mixer' in state:
                    self.alsa_mixer_processor.set_state(state['alsa_mixer'])
                self.zynmixer.reset_state()
                if 'mixer' in state:
                    self.zynmixer.set_state(state['mixer'])
                if 'audio_recorder_armed' in state:
                    for midi_chan in [0,1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,256]:
                        if midi_chan in  state['audio_recorder_armed']:
                            self.audio_recorder.arm(midi_chan)
                        else:
                            self.audio_recorder.unarm(midi_chan)

                # Restore MIDI profile state
                if 'midi_profile_state' in state:
                    self.set_midi_profile_state(state['midi_profile_state'])

                if 'learned_zs3' in state:
                    self.learned_zs3 = state['learned_zs3']
                else:
                    #TODO: Move to legacy state handler
                    self.reset_zs3()
                    self.import_legacy_zs3s(state)

            if fpath == self.last_snapshot_fpath and "last_state_fpath" in state:
                self.last_snapshot_fpath = state['last_snapshot_fpath']
            else:
                self.last_snapshot_fpath = fpath

        except Exception as e:
            #TODO: self.zyngui.reset_loading()
            logging.exception("Invalid snapshot: %s" % e)
            return None

        self.zynautoconnect(True)

        # Restore mute state
        self.zynmixer.set_mute(255, mute)

        self.last_snapshot_count += 1
        return state

    def import_legacy_zs3s(self, state):
        """Load ZS3 state from legacy snapshot format state
        
        state : Dictionary containing state model
        TODO: Move to legacy snapshot handler
        """
        
        zs3_index = 0
        for midi_chan in range(0, 16):
            for prog_num in range(0, 128):
                lstates = [None] * len(state['layers'])
                note_range = [None] * 16
                root_layer_index = None
                for li, lss in enumerate(state['layers']):
                    if 'zs3_list' in lss and midi_chan == lss['midi_chan']:
                        lstate = lss['zs3_list'][prog_num]
                        if not lstate:
                            continue
                        try:
                            root_layer_index = self.root_layers.index(self.layers[li])
                        except:
                            pass
                        lstate['engine_name'] = lss['engine_name']
                        lstate['engine_nick'] = lss['engine_nick']
                        lstate['engine_jackname'] = self.layers[li].engine.jackname
                        lstate['midi_chan'] = midi_chan
                        lstate['show_fav_presets'] = lss['show_fav_presets']
                        if 'active_screen_index' in lstate:
                            lstate['current_screen_index'] = lstate['active_screen_index']
                            del lstate['active_screen_index']
                        if 'note_range' in lstate:
                            if lstate['note_range']:
                                note_range[midi_chan] = lstate['note_range']
                            del lstate['note_range']
                        lstates[li] = lstate

                if root_layer_index is not None:
                    zs3_new = {
                        'index': root_layer_index,
                        'layers': lstates,
                        'note_range': note_range,
                        'zs3_title': "Legacy ZS3 #{}".format(zs3_index + 1),
                        'midi_learn_chan': midi_chan,
                        'midi_learn_prognum': prog_num
                    }
                    self.learned_zs3.append(zs3_new)
                    #logging.debug("ADDED LEGACY ZS3 #{} => {}".format(zs3_index, zs3_new))
                    zs3_index += 1


    def restore_state_zs3(self, state):
        #TODO

        # Get restored active layer index
        if state['index']<len(self.root_layers):
            index = state['index']
            restore_midi_chan = self.root_layers[index].midi_chan
        else:
            index = None
            restore_midi_chan = None

        logging.debug("RESTORING ZS3 STATE (index={}) => {}".format(index, state))

        # Calculate the layers to restore, depending of mode OMNI/MULTI, etc
        layer2restore = []
        for i, lss in enumerate(state['layers']):
            l2r = False
            if lss:
                if zynthian_gui_config.midi_single_active_channel:
                    if restore_midi_chan is not None and lss['midi_chan'] == restore_midi_chan:
                        l2r = True
                else:
                    l2r = True
            layer2restore.append(l2r)

        # Restore layer state, step 1 => Restore Bank & Preset Status
        for i, lss in enumerate(state['layers']):
            if layer2restore[i]:
                self.layers[i].restore_state_1(lss)

        # Restore layer state, step 2 => Restore Controllers Status
        for i, lss in enumerate(state['layers']):
            if layer2restore[i]:
                self.layers[i].restore_state_2(lss)

        # Set Audio Capture
        if 'audio_capture' in state:
            self.set_audio_capture(state['audio_capture'])

        # Audio Recorder Armed
        if 'audio_recorder_armed' in state:
            for midi_chan in [0,1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,256]:
                if midi_chan in state['audio_recorder_armed']:
                    self.audio_recorder.arm(midi_chan)
                else:
                    self.audio_recorder.unarm(midi_chan)

        # Set Clone
        if 'clone' in state:
            self.set_clone(state['clone'])

        # Note-range & Tranpose
        if 'note_range' in state:
            self.set_note_range(state['note_range'])
        # BW compat.
        elif 'transpose' in state:
            self.reset_note_range()
            self.set_transpose(state['transpose'])

        # Mixer
        if 'mixer' in state:
            self.zynmixer.set_state(state['mixer'])

        # Restore ALSA-Mixer settings
        if self.alsa_mixer_processor and 'alsa_mixer' in state:
            self.alsa_mixer_processor.set_state(state['alsa_mixer'])

        # Set active layer
        if index is not None and index!=self.index:
            logging.info("Setting current_chain to {}".format(index))
            self.index = index
            self.chain_manager.set_active_chain_by_id("{:2d}".format(state['index']))

        # Autoconnect Audio => Not Needed!! It's called after action
        #self.zynautoconnect_audio(True)

    def convert_legacy_snapshot(self, snapshot):
        """Convert legacy (<2022-11-22) snapshot to current format"""

        #TODO: Implement legacy snapshot support

        state = snapshot

        if "index" in snapshot:
            state['active_chain'] = "{:02d}".format(snapshot["index"])
        
        if "layers" in snapshot:
            for layer in snapshot["layers"]:
                midi_chan = layer["midi_chan"]
                engine = layer["engine_nick"]
                if midi_chan == 256:
                    chain_id = "main"
                else:
                    chain_id = "{:02d}".format(midi_chan)

        if 'transpose' in state:
            self.reset_note_range()
            self.set_transpose(state['transpose'])

        state['format_version'] = SNAPSHOT_FORMAT_VERSION
        return snapshot

    def fix_snapshot(self, snapshot):
        """Apply fixes to snapshot based on format version"""
        if "format_version" not in snapshot:
            state = self.convert_legacy_snapshot(snapshot)
        else:
            state = snapshot
        if state["format_version"] < SNAPSHOT_FORMAT_VERSION:
            pass
        return state

    #----------------------------------------------------------------------------
    # ZS3 management
    #----------------------------------------------------------------------------

    def set_midi_prog_zs3(self, midi_chan, prog_num):
        """Recall ZS3 state from MIDI program change
        
        midi_chan : MIDI channel
        prog_num : MIDI program change number
        """
        
        try:
            if zynthian_gui_config.midi_single_active_channel:
                zs3_index = f"{get_lib_zyncore().get_midi_active_chan()}/{prog_num}"
            else:
                zs3_index = f"{midi_chan}/{prog_num}"
            return self.restore_zs3(self.zs3[zs3_index])
        except:
            logging.debug(f"Can't find a ZS3 for CH#{midi_chan}, PRG#{prog_num}")
            return False
 
    def save_midi_prog_zs3(self, midi_chan, prog_num):
        """Store current state as ZS3
        
        midi_chan : MIDI channel associated with ZS3
        prog_num : MIDI Program Change number
        """

        id = f"{midi_chan}/{prog_num}"
        next_id = 1
        for zs3 in self.zs3.values():
            if zs3["title"].startswith("New ZS3-"):
                try:
                    id = int (zs3["title"][8:])
                    if id > next_id:
                        next_id = id + 1
                except:
                    pass
        
        if id not in self.zs3:
            self.zs3[id] = {'title': f"New ZS3-{next_id}"}
        zs3[id]['active_chain'] = self.chain_manager.active_chain
        zs3[id]['processors'] = self.chain_manager.get_zs3_state()
        zs3[id]['mixer'] = self.zynmixer.get_state()
        self.last_zs3 = id

    def get_zs3_index_by_midich_prognum(self, midi_chan, prog_num):
        """Get index of a ZS3 from MIDI channel and program change number
        
        midi_chan : MIDI Channel
        prog_num : Program Change number
        """
        
        for zs3_index, zs3 in enumerate(self.learned_zs3):
            try:
                if zs3['midi_learn_chan'] == midi_chan and zs3['midi_learn_prognum'] == prog_num:
                    return zs3_index
            except:
                pass


    def get_zs3_index_by_prognum(self, prog_num):
        """Get index of a ZS3 from ist MIDI program number

        prog_num : MIDI Program Change number
        """
        for i, zs3 in enumerate(self.learned_zs3):
            try:
                if zs3['midi_learn_prognum'] == prog_num:
                    return i
            except:
                pass


    def get_last_zs3(self):
        """Get the index of the last ZS3 added"""
        return self.last_zs3


    def get_zs3_title(self, zs3_index):
        """Get ZS3 title
        
        zs3_index : Index of ZS3
        Returns : Title as string
        """
        if zs3_index is not None and zs3_index >= 0 and zs3_index < len(self.learned_zs3):
            return self.learned_zs3[zs3_index]['zs3_title']


    def set_zs3_title(self, i, title):
        if i is not None and i >= 0 and i < len(self.learned_zs3):
            self.learned_zs3[i]['zs3_title'] = title


    def restore_zs3(self, zs3_index):
        """Restore a ZS3
        
        zs3_index : Index of ZS3 to restore"""

        try:
            if zs3_index is not None and zs3_index >= 0 and zs3_index < len(self.learned_zs3):
                logging.info("Restoring ZS3#{}...".format(zs3_index))
                self.restore_state_zs3(self.learned_zs3[zs3_index])
                self.last_zs3 = zs3_index
                return True
            else:
                logging.debug("Can't find ZS3#{}".format(zs3_index))
        except Exception as e:
            logging.error("Can't restore ZS3 state => %s", e)

        return False


    def save_zs3(self, zs3_id, title):
        """Store current state as ZS3
        
        zs3_id : ID of zs3 to save / overwrite
        title : ZS3 title
        """

        # Initialise zs3
        self.zs3[zs3_id] = {
            "title": title,
            "active_chain": self.chain_manager.active_chain_id,
            "processors": {}
        }
        # Add processors
        for id, processor in self.chain_manager.processors.items():
            self.zs3[zs3_id]["processors"][id] = {
                "bank_info": processor.bank_info,
                "preset_info": processor.preset_info,
                "controllers": {}
            }
            # Add controllers that differ to their default (preset) values
            for symbol, zctrl in processor.controller_dict.items():
                ctrl_state = {}
                if zctrl.value != zctrl.value_default:
                    ctrl_state["value"] = zctrl.value
                if zctrl.midi_learn_chan:
                    ctrl_state["midi_learn_chan"] = zctrl.midi_learn_chan
                if zctrl.midi_learn_cc:
                    ctrl_state["midi_learn_cc"] = zctrl.midi_learn_cc
                if ctrl_state:
                    self.zs3[zs3_id]["processors"][id]["controllers"][symbol] = ctrl_state
        # Add mixer state
        self.zs3[zs3_id]["mixer"] = self.zynmixer.get_state(False)

    def delete_zs3(self, zs3_index):
        """Remove a ZS3
        
        zs3_index : Index of ZS3 to remove
        """
        try:
            del(self.zs3[zs3_index])
            if self.last_zs3 == zs3_index:
                self.last_zs3 = None
        except:
            logging.info("Tried to remove non-existant ZS3")

    def reset_zs3(self):
        """Remove all ZS3"""

        # ZS3 list (subsnapshots)
        self.zs3 = {}
        # Last selected ZS3 subsnapshot
        self.last_zs3 = None


    def clean_zs3(self):
        """Remove non-existant processors from ZS3 state"""
        
        for state in self.zs3:
            if state["active_chain"] not in self.chain_manager.chains:
                state["active_chain"] = self.chain_manager.active_chain_id
            for processor_id in list(state["processors"]):
                if processor_id not in self.chain_manager.processors:
                    del state["process"][processor_id]

    #------------------------------------------------------------------
    # Jackd Info
    #------------------------------------------------------------------

    def get_jackd_samplerate(self):
        """Get the samplerate that jackd is running"""
        return zynautoconnect.get_jackd_samplerate()


    def get_jackd_blocksize(self):
        """Get the block size used by jackd"""
        return zynautoconnect.get_jackd_blocksize()

    #------------------------------------------------------------------
    # MIDI learning
    #------------------------------------------------------------------

    def init_midi_learn_zctrl(self, zctrl):
        """Initialise a zcontroller midi learn
        
        zctrl : zcontroller object
        """
        
        self.midi_learn_zctrl = zctrl
        get_lib_zyncore().set_midi_learning_mode(1)
    
    def enter_midi_learn(self):
        """Enter MIDI learn mode"""

        if not self.midi_learn_mode:
            logging.debug("ENTER LEARN")
            self.midi_learn_mode = 1
            self.midi_learn_zctrl = None
            get_lib_zyncore().set_midi_learning_mode(1)

    def exit_midi_learn(self):
        """Exit MIDI learn mode"""

        if self.midi_learn_mode or self.midi_learn_zctrl:
            self.midi_learn_mode = 0
            self.midi_learn_zctrl = None
            get_lib_zyncore().set_midi_learning_mode(0)

    def toggle_midi_learn(self):
        """Toggle MIDI learn mode"""

        if self.midi_learn_mode:
            if zynthian_gui_config.midi_prog_change_zs3:
                self.midi_learn_mode = 2
                self.midi_learn_zctrl = None
            else:
                self.exit_midi_learn()
        else:
            self.enter_midi_learn()

    def clean_midi_learn(self, obj=None):
        """Clean MIDI learn from controls
        
        obj : Object to clean [chain_id, processor, zctrl] (Default: active chain)
        """

        if obj == None:
            obj = self.chain_manager.active_obj
        if isinstance(obj, str):
            for processor in self.chain_manager.get_processors(obj):
                processor.midi_unlearn()
        elif isinstance(obj, zynthian_processor):
            obj.midi_unlearn()
        elif isinstance(obj, zynthian_controller):
            obj.midi_unlearn()

    #------------------------------------------------------------------
    # Autoconnect
    #------------------------------------------------------------------

    def zynautoconnect(self, force=False):
        """Trigger jack graph connections
        
        force : True to force connections
        """
        if force:
            self.zynautoconnect_midi_flag = False
            zynautoconnect.midi_autoconnect(True)
            self.zynautoconnect_audio_flag = False
            zynautoconnect.audio_autoconnect(True)
        else:
            self.zynautoconnect_midi_flag = True
            self.zynautoconnect_audio_flag = True


    def zynautoconnect_midi(self, force=False):
        """Trigger jack MIDI graph connections
        
        force : True to force connections
        """
        if force:
            self.zynautoconnect_midi_flag = False
            zynautoconnect.midi_autoconnect(True)
        else:
            self.zynautoconnect_midi_flag = True


    def zynautoconnect_audio(self, force=False):
        """Trigger jack audio graph connections
        
        force : True to force connections
        """
        if force:
            self.zynautoconnect_audio_flag = False
            zynautoconnect.audio_autoconnect(True)
        else:
            self.zynautoconnect_audio_flag = True


    def zynautoconnect_do(self):
        """Trigger pending jack graph connections"""
        if zynautoconnect.is_running():
            if self.zynautoconnect_midi_flag:
                self.zynautoconnect_midi_flag = False
                zynautoconnect.midi_autoconnect(True)
            if self.zynautoconnect_audio_flag:
                self.zynautoconnect_audio_flag = False
                zynautoconnect.audio_autoconnect(True)


    def zynautoconnect_acquire_lock(self):
        """Request and wait for mutex lock"""
        zynautoconnect.acquire_lock()


    def zynautoconnect_release_lock(self):
        """Release mutex lock"""
        zynautoconnect.release_lock()

    # ---------------------------------------------------------------------------
    # MIDI Router Init & Config
    # ---------------------------------------------------------------------------

    def init_midi(self):
        """Initialise MIDI configuration"""
        try:
            #Set Global Tuning
            self.fine_tuning_freq = zynthian_gui_config.midi_fine_tuning
            get_lib_zyncore().set_midi_filter_tuning_freq(ctypes.c_double(self.fine_tuning_freq))
            #Set MIDI Master Channel
            get_lib_zyncore().set_midi_master_chan(zynthian_gui_config.master_midi_channel)
            #Set MIDI CC automode
            get_lib_zyncore().set_midi_filter_cc_automode(zynthian_gui_config.midi_cc_automode)
            #Set MIDI System Messages flag
            get_lib_zyncore().set_midi_filter_system_events(zynthian_gui_config.midi_sys_enabled)
            #Setup MIDI filter rules
            if self.midi_filter_script:
                self.midi_filter_script.clean()
            self.midi_filter_script = zynthian_midi_filter.MidiFilterScript(zynthian_gui_config.midi_filter_rules)

        except Exception as e:
            logging.error("ERROR initializing MIDI : {}".format(e))


    def reload_midi_config(self):
        """Reload MII configuration from saved state"""

        zynconf.load_config()
        midi_profile_fpath=zynconf.get_midi_config_fpath()
        if midi_profile_fpath:
            zynconf.load_config(True,midi_profile_fpath)
            zynthian_gui_config.set_midi_config()
            self.init_midi()
            self.init_midi_services()
            self.zynautoconnect()

    def init_midi_services(self):
        """Start/Stop MIDI aux. services"""

        self.default_rtpmidi()
        self.default_qmidinet()
        self.default_touchosc()
        self.default_aubionotes()

    # ---------------------------------------------------------------------------
    # Global Audio Player
    # ---------------------------------------------------------------------------

    def start_audio_player(self):
        """Start playback of global audio player"""

        filename = self.state_manager.audio_recorder.filename
        if not filename or not os.path.exists(filename):
            if os.path.ismount(self.state_manager.audio_recorder.capture_dir_usb):
                path = self.state_manager.audio_recorder.capture_dir_usb
            else:
                path = self.state_manager.audio_recorder.capture_dir_sdc
            files = glob('{}/*.wav'.format(path))
            if files:
                filename = max(files, key=os.path.getctime)
            else:
                return

        if not self.audio_player:
            try:
                self.audio_player = zynthian_processor("AP")
                self.audio_player.start_engine()
                zynautoconnect.audio_connect_aux(self.audio_player.engine.jackname)
            except Exception as e:
                self.stop_audio_player()
                return
        self.audio_player.engine.set_preset(self.audio_player, [filename])
        self.audio_player.engine.player.set_position(16, 0.0)
        self.audio_player.engine.player.start_playback(16)
        self.status_info['audio_player'] = 'PLAY'

    def stop_audio_player(self):
        """Stop playback of global audio player"""

        if self.audio_player:
            self.audio_player.engine.player.stop_playback(16)
            self.status_info['audio_player'] = ''

    # ---------------------------------------------------------------------------
    # Services
    # ---------------------------------------------------------------------------

    #Start/Stop RTP-MIDI depending on configuration
    def default_rtpmidi(self):
        if zynthian_gui_config.midi_rtpmidi_enabled:
            self.start_rtpmidi(False)
        else:
            self.stop_rtpmidi(False)

    def start_rtpmidi(self, save_config=True):
        logging.info("STARTING RTP-MIDI")
        try:
            check_output("systemctl start jackrtpmidid", shell=True)
            zynthian_gui_config.midi_rtpmidi_enabled = 1
            # Update MIDI profile
            if save_config:
                zynconf.update_midi_profile({ 
                    "ZYNTHIAN_MIDI_RTPMIDI_ENABLED": str(zynthian_gui_config.midi_rtpmidi_enabled)
                })
            # Call autoconnect after a little time
            sleep(0.5)
            self.zynautoconnect_midi()
        except Exception as e:
            logging.error(e)


    def stop_rtpmidi(self, save_config=True):
        logging.info("STOPPING RTP-MIDI")
        try:
            check_output("systemctl stop jackrtpmidid", shell=True)
            zynthian_gui_config.midi_rtpmidi_enabled = 0
            # Update MIDI profile
            if save_config:
                zynconf.update_midi_profile({ 
                    "ZYNTHIAN_MIDI_RTPMIDI_ENABLED": str(zynthian_gui_config.midi_rtpmidi_enabled)
                })

        except Exception as e:
            logging.error(e)

    def start_qmidinet(self, save_config=True):
        logging.info("STARTING QMIDINET")
        try:
            check_output("systemctl start qmidinet", shell=True)
            zynthian_gui_config.midi_network_enabled = 1
            # Update MIDI profile
            if save_config:
                zynconf.update_midi_profile({ 
                    "ZYNTHIAN_MIDI_NETWORK_ENABLED": str(zynthian_gui_config.midi_network_enabled)
                })
            # Call autoconnect after a little time
            sleep(0.5)
            self.zynautoconnect_midi()
        except Exception as e:
            logging.error(e)


    def stop_qmidinet(self, save_config=True):
        logging.info("STOPPING QMIDINET")
        try:
            check_output("systemctl stop qmidinet", shell=True)
            zynthian_gui_config.midi_network_enabled = 0
            # Update MIDI profile
            if save_config:
                zynconf.update_midi_profile({ 
                    "ZYNTHIAN_MIDI_NETWORK_ENABLED": str(zynthian_gui_config.midi_network_enabled)
                })
        except Exception as e:
            logging.error(e)

    #Start/Stop QMidiNet depending on configuration
    def default_qmidinet(self):
        if zynthian_gui_config.midi_network_enabled:
            self.start_qmidinet(False)
        else:
            self.stop_qmidinet(False)


    def start_touchosc2midi(self, save_config=True):
        logging.info("STARTING touchosc2midi")
        try:
            check_output("systemctl start touchosc2midi", shell=True)
            zynthian_gui_config.midi_touchosc_enabled = 1
            # Update MIDI profile
            if save_config:
                zynconf.update_midi_profile({ 
                    "ZYNTHIAN_MIDI_TOUCHOSC_ENABLED": str(zynthian_gui_config.midi_touchosc_enabled)
                })
            # Call autoconnect after a little time
            sleep(0.5)
            self.zynautoconnect_midi()
        except Exception as e:
            logging.error(e)

    def stop_touchosc2midi(self, save_config=True):
        logging.info("STOPPING touchosc2midi")
        try:
            check_output("systemctl stop touchosc2midi", shell=True)
            zynthian_gui_config.midi_touchosc_enabled = 0
            # Update MIDI profile
            if save_config:
                zynconf.update_midi_profile({ 
                    "ZYNTHIAN_MIDI_TOUCHOSC_ENABLED": str(zynthian_gui_config.midi_touchosc_enabled)
                })
        except Exception as e:
            logging.error(e)

    #Start/Stop TouchOSC depending on configuration
    def default_touchosc(self):
        if zynthian_gui_config.midi_touchosc_enabled:
            self.start_touchosc2midi(False)
        else:
            self.stop_touchosc2midi(False)

    def start_aubionotes(self, save_config=True):
        logging.info("STARTING aubionotes")
        try:
            check_output("systemctl start aubionotes", shell=True)
            zynthian_gui_config.midi_aubionotes_enabled = 1
            # Update MIDI profile
            if save_config:
                zynconf.update_midi_profile({ 
                    "ZYNTHIAN_MIDI_AUBIONOTES_ENABLED": str(zynthian_gui_config.midi_aubionotes_enabled)
                })
            # Call autoconnect after a little time
            sleep(0.5)
            self.zynautoconnect()
        except Exception as e:
            logging.error(e)

    def stop_aubionotes(self, save_config=True):
        logging.info("STOPPING aubionotes")
        try:
            check_output("systemctl stop aubionotes", shell=True)
            zynthian_gui_config.midi_aubionotes_enabled = 0
            # Update MIDI profile
            if save_config:
                zynconf.update_midi_profile({ 
                    "ZYNTHIAN_MIDI_AUBIONOTES_ENABLED": str(zynthian_gui_config.midi_aubionotes_enabled)
                })
        except Exception as e:
            logging.error(e)

    #Start/Stop AubioNotes depending on configuration
    def default_aubionotes(self):
        if zynthian_gui_config.midi_aubionotes_enabled:
            self.start_aubionotes(False)
        else:
            self.stop_aubionotes(False)


    # -------------------------------------------------------------------
    # Switches
    # -------------------------------------------------------------------

    # Init Standard Zynswitches
    def zynswitches_init(self):
        if not get_lib_zyncore(): return
        logging.info("INIT {} ZYNSWITCHES ...".format(zynthian_gui_config.num_zynswitches))
        ts = datetime.now()
        self.dtsw = [ts] * (zynthian_gui_config.num_zynswitches + 4)


    # Initialize custom switches, analog I/O, TOF sensors, etc.
    def zynswitches_midi_setup(self, current_chain_chan=None):
        if not get_lib_zyncore(): return
        logging.info("CUSTOM I/O SETUP...")

        # Configure Custom Switches
        for i, event in enumerate(zynthian_gui_config.custom_switch_midi_events):
            if event is not None:
                swi = 4 + i
                if event['chan'] is not None:
                    midi_chan = event['chan']
                else:
                    midi_chan = current_chain_chan

                if midi_chan is not None:
                    get_lib_zyncore().setup_zynswitch_midi(swi, event['type'], midi_chan, event['num'], event['val'])
                    logging.info("MIDI ZYNSWITCH {}: {} CH#{}, {}, {}".format(swi, event['type'], midi_chan, event['num'], event['val']))
                else:
                    get_lib_zyncore().setup_zynswitch_midi(swi, 0, 0, 0, 0)
                    logging.info("MIDI ZYNSWITCH {}: DISABLED!".format(swi))

        # Configure Zynaptik Analog Inputs (CV-IN)
        for i, event in enumerate(zynthian_gui_config.zynaptik_ad_midi_events):
            if event is not None:
                if event['chan'] is not None:
                    midi_chan = event['chan']
                else:
                    midi_chan = current_chain_chan

                if midi_chan is not None:
                    get_lib_zyncore().setup_zynaptik_cvin(i, event['type'], midi_chan, event['num'])
                    logging.info("ZYNAPTIK CV-IN {}: {} CH#{}, {}".format(i, event['type'], midi_chan, event['num']))
                else:
                    get_lib_zyncore().disable_zynaptik_cvin(i)
                    logging.info("ZYNAPTIK CV-IN {}: DISABLED!".format(i))

        # Configure Zynaptik Analog Outputs (CV-OUT)
        for i, event in enumerate(zynthian_gui_config.zynaptik_da_midi_events):
            if event is not None:
                if event['chan'] is not None:
                    midi_chan = event['chan']
                else:
                    midi_chan = current_chain_chan

                if midi_chan is not None:
                    get_lib_zyncore().setup_zynaptik_cvout(i, event['type'], midi_chan, event['num'])
                    logging.info("ZYNAPTIK CV-OUT {}: {} CH#{}, {}".format(i, event['type'], midi_chan, event['num']))
                else:
                    get_lib_zyncore().disable_zynaptik_cvout(i)
                    logging.info("ZYNAPTIK CV-OUT {}: DISABLED!".format(i))

        # Configure Zyntof Inputs (Distance Sensor)
        for i, event in enumerate(zynthian_gui_config.zyntof_midi_events):
            if event is not None:
                if event['chan'] is not None:
                    midi_chan = event['chan']
                else:
                    midi_chan = current_chain_chan

                if midi_chan is not None:
                    get_lib_zyncore().setup_zyntof(i, event['type'], midi_chan, event['num'])
                    logging.info("ZYNTOF {}: {} CH#{}, {}".format(i, event['type'], midi_chan, event['num']))
                else:
                    get_lib_zyncore().disable_zyntof(i)
                    logging.info("ZYNTOF {}: DISABLED!".format(i))

    def set_transpose(self, state):
        """Set transpose from state

        state : Transpose state model as dictionary
        TODO: Lose this function to legacy snapshot handler
        """

        for midi_chan in range(0, 16):
            lib_zyncore.set_midi_filter_halftone_trans(midi_chan, state[midi_chan])

    def get_midi_profile_state(self):
        """Get MIDI profile state as an ordered dictionary"""

        midi_profile_state = OrderedDict()
        for key in os.environ.keys():
            if key.startswith("ZYNTHIAN_MIDI_"):
                midi_profile_state[key[14:]] = os.environ[key]
        return midi_profile_state

    def set_midi_profile_state(self, state):
        """Set MIDI profile from state
        
        state : MIDI profile state dictionary
        """

        if state is not None:
            for key in state:
                os.environ["ZYNTHIAN_MIDI_" + key] = state[key]
            zynthian_gui_config.set_midi_config()
            self.init_midi()
            self.init_midi_services()
            self.zynautoconnect()
            return True

    def reset_midi_profile(self):
        """Clear MIDI profiles"""

        self.reload_midi_config()

