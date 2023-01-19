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
from threading  import Thread
from json import JSONEncoder, JSONDecoder

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
from zyngine import zynthian_legacy_snapshot

# ----------------------------------------------------------------------------
# Zynthian State Manager Class
# ----------------------------------------------------------------------------

SNAPSHOT_SCHEMA_VERSION = 1

class zynthian_state_manager:

    def __init__(self):
        """ Create an instance of a state manager

        Manages full Zynthian state, i.e. snapshot
        """

        logging.warning("Creating state manager")
        self.chain_manager = zynthian_chain_manager(self)
        self.last_snapshot_count = 0 # Increments each time a snapshot is loaded - modules may use to update if required
        self.reset_zs3()
        
        self.alsa_mixer_processor = zynthian_processor("MX", ("Mixer", "ALSA Mixer", "MIXER", None, zynthian_engine_alsa_mixer, True))
        self.alsa_mixer_processor.engine = zynthian_engine_alsa_mixer()
        self.alsa_mixer_processor.refresh_controllers()
        self.audio_recorder = zynthian_audio_recorder()
        self.zynmixer = zynthian_engine_audio_mixer.zynmixer()
        self.zynseq = zynseq.zynseq()
        self.audio_player = None

        self.midi_filter_script = None
        self.midi_learn_zctrl = None # zctrl object currently listening for MIDI learn
        self.midi_learn_mode = 0 # 0:Disabled, 1:MIDI Learn, 2:ZS3 Learn
        self.zs3 = {} # Dictionary or zs3 configs indexed by "ch/pc"
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

        self.exit_flag = False
        #TODO: We may need this in future... self.start_thread()
        self.reset()

    def reset(self):
        zynautoconnect.stop()
        self.last_snapshot_fpath = ""
        self.zynseq.load("")
        self.chain_manager.remove_all_chains(True)
        self.zynmixer.reset_state()
        self.reload_midi_config()
        zynautoconnect.start(self)
        self.autoconnect(True)

    #------------------------------------------------------------------
    # Background task thread
    #------------------------------------------------------------------

    def start_thread(self):
        """Start a thread to run background tasks"""

        self.thread = Thread(target=self.thread_task, args=())
        self.thread.name = "Status Manager MIDI"
        self.thread.daemon = True # thread dies with the program
        self.thread.start()

    def thread_task(self):
        """Perform background tasks"""

        while not self.exit_flag:
            pass
            sleep(0.2)

    #----------------------------------------------------------------------------
    # Snapshot Save & Load
    #----------------------------------------------------------------------------

    def get_state(self):
        """Get a dictionary describing the full state model"""

        self.save_zs3("zs3-0", "Last state")
        self.clean_zs3()
        state = {
            'schema_version': SNAPSHOT_SCHEMA_VERSION,
            'last_snapshot_fpath': self.last_snapshot_fpath, #TODO: Why is this required?
            'midi_profile_state': self.get_midi_profile_state(),
            'chains': self.chain_manager.get_state(),
            'zs3': self.zs3
        }

        engine_states = {}
        for id, engine in self.chain_manager.zyngines.items():
            engine_state = engine.get_extended_config()
            if engine_state:
                engine_states[id] = engine_state
        if engine_states:
            state["engine_config"] = engine_states

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
            with open(fpath, "r") as fh:
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
                if "chains" in state:
                    self.chain_manager.set_state(state['chains'])
                self.chain_manager.stop_unused_engines()

            if "engine_config" in state:
                for id, engine_state in state["engine_config"].items():
                    try:
                        self.chain_manager.zyngines[id].set_extended_config(engine_state)
                    except Exception as e:
                        logging.info("Failed to set extended engine state for %s: %s", id, e)

            self.zs3 = state["zs3"]
            self.load_zs3("zs3-0")

            if load_sequences and "zynseq_riff_b64" in state:
                b64_bytes = state["zynseq_riff_b64"].encode("utf-8")
                binary_riff_data = base64.decodebytes(b64_bytes)
                self.zynseq.restore_riff_data(binary_riff_data)

            if load_chains and load_sequences:
                if "alsa_mixer" in state:
                    self.alsa_mixer_processor.set_state(state["alsa_mixer"])
                if "audio_recorder_armed" in state:
                    for midi_chan in [0,1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,256]:
                        if midi_chan in  state["audio_recorder_armed"]:
                            self.audio_recorder.arm(midi_chan)
                        else:
                            self.audio_recorder.unarm(midi_chan)

                # Restore MIDI profile state
                if "midi_profile_state" in state:
                    self.set_midi_profile_state(state["midi_profile_state"])

            if fpath == self.last_snapshot_fpath and "last_state_fpath" in state:
                self.last_snapshot_fpath = state["last_snapshot_fpath"]
            else:
                self.last_snapshot_fpath = fpath

        except Exception as e:
            #TODO: self.zyngui.reset_loading()
            logging.exception("Invalid snapshot: %s" % e)
            return None

        self.autoconnect(True)

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
                            #TODO: Move to ZS3
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

    def fix_snapshot(self, snapshot):
        """Apply fixes to snapshot based on format version"""

        if "schema_version" not in snapshot:
            converter = zynthian_legacy_snapshot.zynthian_legacy_snapshot()
            state = converter.convert_state(snapshot, self.chain_manager.engine_info)
        else:
            state = snapshot
            if state["schema_version"] < SNAPSHOT_SCHEMA_VERSION:
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
        return self.load_zs3(str(prog_num))
 
    def get_zs3_title(self, zs3_index):
        """Get ZS3 title
        
        zs3_index : Index of ZS3
        Returns : Title as string
        """
        if zs3_index in self.zs3:
            return self.zs3[zs3_index]["title"]
        return zs3_index


    def set_zs3_title(self, zs3_index, title):
        if zs3_index in self.zs3:
            self.zs3[zs3_index]["title"] = title


    def load_zs3(self, zs3_id):
        """Restore a ZS3
        
        zs3_id : ID of ZS3 to restore
        Returns : True on success
        """

        if zs3_id not in self.zs3:
            logging.info("Attepmted to load non-existant ZS3")
            return False

        zs3_state = self.zs3[zs3_id]
        if "chains" in zs3_state:
            for chain_id, chain_state in zs3_state["chains"].items():
                chain = self.chain_manager.get_chain(chain_id)
                if not chain:
                    continue
                if "note_low" in chain_state:
                    get_lib_zyncore().set_midi_filter_note_low(chain.midi_chan, chain_state["note_low"])
                else:
                    get_lib_zyncore().set_midi_filter_note_low(chain.midi_chan, 0)
                if "note_high" in chain_state:
                    get_lib_zyncore().set_midi_filter_note_high(chain.midi_chan, chain_state["note_high"])
                else:
                    get_lib_zyncore().set_midi_filter_note_high(chain.midi_chan, 127)
                if "transpose_octave" in chain_state:
                    get_lib_zyncore().set_midi_filter_transpose_octave(chain.midi_chan, chain_state["transpose_octave"])
                else:
                    get_lib_zyncore().set_midi_filter_transpose_octave(chain.midi_chan, 0)
                if "transpose_semitone" in chain_state:
                    get_lib_zyncore().set_midi_filter_transpose_semitone(chain.midi_chan, chain_state["transpose_semitone"])
                else:
                    get_lib_zyncore().set_midi_filter_transpose_semitone(chain.midi_chan, 0)

        if "midi_clone" in zs3_state:
            for src_chan in range(16):
                for dst_chan in range(16):
                    try:
                        self.enable_clone(src_chan, dst_chan, zs3_state["midi_clone"][str(src_chan)][str(dst_chan)]["enabled"])
                        self.set_clone_cc(src_chan, dst_chan, zs3_state["midi_clone"][str(src_chan)][str(dst_chan)]["cc"])
                    except:
                        self.enable_clone(src_chan, dst_chan, False)
                        get_lib_zyncore().reset_midi_filter_clone_cc(src_chan, dst_chan)

        if "processors" in zs3_state:
            for proc_id, proc_state in zs3_state["processors"].items():
                try:
                    processor = self.chain_manager.processors[int(proc_id)]
                    if zs3_id != "zs3-0" and zynthian_gui_config.midi_single_active_channel and self.chain_manager.get_chain_id_by_processor(processor) != self.chain_manager.active_chain_id:
                        continue
                    processor.set_state(proc_state)
                except:
                    pass

        if not zynthian_gui_config.midi_single_active_channel and "active_chain" in zs3_state:
            self.chain_manager.set_active_chain_by_id(zs3_state["active_chain"])

        if "mixer" in zs3_state:
            self.zynmixer.set_state(zs3_state["mixer"])

        return True

    def save_zs3(self, zs3_id=None, title=None):
        """Store current state as ZS3

        zs3_id : ID of zs3 to save / overwrite (Default: Create new id)
        title : ZS3 title (Default: Create new title)
        """

        # Get next id and name
        used_ids = []
        used_titles = []
        for id in self.zs3:
            if id.startswith("zs3-"):
                try:
                    used_ids.append(int(id.split('-')[1]))
                except:
                    pass
            if self.zs3[id]["title"].startswith("New ZS3 "):
                try:
                    used_titles.append(int(self.zs3[id]["title"][8:]))
                except:
                    pass
        used_ids.sort()
        used_titles.sort()

        if zs3_id is None:
            index = 0
            for offset, index in enumerate(used_ids):
                if offset and index - 1 != used_ids[offset] - 1:
                    break
            zs3_id = f"zs3-{index + 1}"

        if zs3_id in self.zs3:
            title = self.zs3[zs3_id]['title']

        if title is None:
            index = 0
            for offset, index in enumerate(used_titles):
                if offset and index - 1 != used_titles[offset] - 1:
                    break
            title = f"New ZS3 {index + 1}"

        # Initialise zs3
        self.zs3[zs3_id] = {
            "title": title,
            "active_chain": self.chain_manager.active_chain_id
        }
        chain_states = {}
        for chain_id, chain in self.chain_manager.chains.items():
            if isinstance(chain.midi_chan, int) and chain.midi_chan < 16:
                chain_state = {}
                #TODO: This is MIDI channel related, not chain specific
                note_low = get_lib_zyncore().get_midi_filter_note_low(chain.midi_chan)
                if note_low:
                    chain_state["note_low"] = note_low
                note_high = get_lib_zyncore().get_midi_filter_note_high(chain.midi_chan)
                if note_high != 127:
                    chain_state["note_high"] = note_high
                transpose_octave = get_lib_zyncore().get_midi_filter_transpose_octave(chain.midi_chan)
                if transpose_octave:
                    chain_state["transpose_octave"] = transpose_octave
                transpose_semitone = get_lib_zyncore().get_midi_filter_transpose_semitone(chain.midi_chan)
                if transpose_semitone:
                    chain_state["transpose_semitone"] = transpose_semitone
                if chain_state:
                    chain_states[chain_id] = chain_state
        if chain_states:
            self.zs3[zs3_id]["chains"] = chain_states

        clone_state = self.get_clone_state()
        if clone_state:
            self.zs3[zs3_id]["midi_clone"] = clone_state

        # Add processors
        processor_states = {}
        for id, processor in self.chain_manager.processors.items():
            processor_state = {
                "bank_info": processor.bank_info,
                "preset_info": processor.preset_info,
                "controllers": {}
            }
            # Add controllers that differ to their default (preset) values
            for symbol, zctrl in processor.controllers_dict.items():
                ctrl_state = {}
                if zctrl.value != zctrl.value_default:
                    ctrl_state["value"] = zctrl.value
                if zctrl.midi_learn_chan is not None:
                    ctrl_state["midi_learn_chan"] = zctrl.midi_learn_chan
                if zctrl.midi_learn_cc is not None:
                    ctrl_state["midi_learn_cc"] = zctrl.midi_learn_cc
                if ctrl_state:
                    processor_state["controllers"][symbol] = ctrl_state
            processor_states[id] = processor_state
        if processor_states:
            self.zs3[zs3_id]["processors"] = processor_states

        # Add mixer state
        mixer_state = self.zynmixer.get_state(False)
        if mixer_state:
            self.zs3[zs3_id]["mixer"] = mixer_state

    def delete_zs3(self, zs3_index):
        """Remove a ZS3
        
        zs3_index : Index of ZS3 to remove
        """
        try:
            del(self.zs3[zs3_index])
        except:
            logging.info("Tried to remove non-existant ZS3")

    def reset_zs3(self):
        """Remove all ZS3"""

        # ZS3 list (subsnapshots)
        self.zs3 = {}
        # Last selected ZS3 subsnapshot

    def clean_zs3(self):
        """Remove non-existant processors from ZS3 state"""
        
        for state in self.zs3:
            if self.zs3[state]["active_chain"] not in self.chain_manager.chains:
                self.zs3[state]["active_chain"] = self.chain_manager.active_chain_id
            if "processors" in self.zs3:
                for processor_id in list(self.zs3[state]["processors"]):
                    if processor_id not in self.chain_manager.processors:
                        del self.zs3[state]["process"][processor_id]

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

    def autoconnect(self, fast=False):
        """Trigger jack graph connections
        
        fast : True to force immediate connection (Default: connect on next 2s cycle)
        """
        self.autoconnect_midi(fast)
        self.autoconnect_audio(fast)

    #TODO: Can modules access zynautoconnect.request_midi_connect directyl?
    def autoconnect_midi(self, fast=False):
        """Trigger jack MIDI graph connections
        
        fast : True for immediate connection (Default: connect on next 2s cycle)
        """

        zynautoconnect.request_midi_connect(fast)

    def autoconnect_audio(self, fast=False):
        """Trigger jack audio graph connections
        
        fast : True to force immediate connection (Default: connect on next 2s cycle)
        """

        zynautoconnect.request_audio_connect(fast)

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
            self.autoconnect()

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

        filename = self.audio_recorder.filename
        if not filename or not os.path.exists(filename):
            if os.path.ismount(self.audio_recorder.capture_dir_usb):
                path = self.audio_recorder.capture_dir_usb
            else:
                path = self.audio_recorder.capture_dir_sdc
            files = glob('{}/*.wav'.format(path))
            if files:
                filename = max(files, key=os.path.getctime)
            else:
                return

        if not self.audio_player:
            try:
                self.audio_player = zynthian_processor("AP", self.chain_manager.engine_info["AP"])
                self.audio_player.midi_chan = 16
                self.chain_manager.start_engine(self.audio_player, "AP")
                self.autoconnect_audio(True)
            except Exception as e:
                self.stop_audio_player()
                self.autoconnect_audio()
                return
        self.audio_player.engine.set_preset(self.audio_player, [filename])
        self.audio_player.engine.player.set_position(16, 0.0)
        self.audio_player.engine.player.start_playback(16)
        self.status_info['audio_player'] = 'PLAY'

    def stop_audio_player(self):
        """Stop playback of global audio player"""

        if self.audio_player:
            self.audio_player.engine.player.stop_playback(16)
            self.audio_player.engine.del_layer(self.audio_player)
            self.audio_player = None
            try:
                self.status_info.pop('audio_player')
            except:
                pass

    def toggle_audio_player(self):
        """Toggle playback of global audio player"""

        if self.audio_player:
            self.stop_audio_player()
        else:
            self.start_audio_player()

    #----------------------------------------------------------------------------
    # Clone, Note Range & Transpose
    #----------------------------------------------------------------------------

    def get_clone_state(self):
        """Get MIDI clone state as list of dictionaries"""

        state = {}
        for src_chan in range(0,16):
            for dst_chan in range(0, 16):
                clone_info = {
                    "enabled": get_lib_zyncore().get_midi_filter_clone(src_chan, dst_chan),
                    "cc": list(map(int,get_lib_zyncore().get_midi_filter_clone_cc(src_chan, dst_chan).nonzero()[0]))
                }
                if clone_info["enabled"] or clone_info["cc"] != [1, 2, 64, 65, 66, 67, 68]:
                    if src_chan not in state:
                        state[src_chan] = {}
                    state[src_chan][dst_chan] = clone_info
        return state

    def enable_clone(self, src_chan, dst_chan, enable=True):
        """Enable/disbale MIDI clone for a source and destination

        src_chan : MIDI channel cloned from
        dst_chan : MIDI channe cloned to
        enable : True to enable or False to disable [Default: enable]
        """

        if src_chan < 0 or src_chan > 15 or dst_chan < 0 or dst_chan > 15:
            return
        if src_chan == dst_chan:
            get_lib_zyncore().set_midi_filter_clone(src_chan, dst_chan, 0)
        else:
            get_lib_zyncore().set_midi_filter_clone(src_chan, dst_chan, enable)

    def set_clone_cc(self, src_chan, dst_chan, cc):
        """Set MIDI clone

        src_chan : MIDI channel to clone from
        dst_chan : MIDI channel to clone to
        cc : List of MIDI CC numbers to clone or list of 128 flags, 1=CC enabled
        """

        cc_array = (c_ubyte * 128)()
        if len(cc) == 128:
            for cc_num in range(0, 128):
                cc_array[cc_num] = cc[cc_num]
        else:
            for cc_num in range(0, 128):
                if cc_num in cc:
                    cc_array[cc_num] = 1
                else:
                    cc_array[cc_num] = 0
        get_lib_zyncore().set_midi_filter_clone_cc(src_chan, dst_chan, cc_array)

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
            self.autoconnect_midi()
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
            self.autoconnect_midi()
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
            self.autoconnect_midi()
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
            self.autoconnect()
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
            self.autoconnect()
            return True

    def reset_midi_profile(self):
        """Clear MIDI profiles"""

        self.reload_midi_config()

