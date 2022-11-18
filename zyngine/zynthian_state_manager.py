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
from glob import glob
import logging

# Zynthian specific modules
import zynconf
import zynautoconnect
from zyngine.zynthian_chain_manager import *
from zyngui.zynthian_audio_recorder import zynthian_audio_recorder
from zyngine import zynthian_engine_audio_mixer
from zyngine import zyngine_config
from zynlibs.zynseq import zynseq
from zyncoder.zyncore import *
from zyngine import zynthian_midi_filter

# ----------------------------------------------------------------------------
# Zynthian State Manager Class
# ----------------------------------------------------------------------------

class zynthian_state_manager():

    def __init__(self):
        """ Create an instance of a state manager

        Manages full Zynthian state, i.e. snapshot
        """

        logging.warning("Creating state manager")
        self.chain_manager = zynthian_chain_manager(self)
        self.last_snapshot_fpath = None
        self.last_snapshot_count = 0 # Increments each time a snapshot is loaded - modules may use to update if required
        self.reset_zs3()
        
        self.create_amixer_chain()

        self.audio_recorder = zynthian_audio_recorder()
        self.zynmixer = zynthian_engine_audio_mixer.zynmixer()
        self.zynseq = zynseq.zynseq()

        self.midi_filter_script = None
        self.midi_learn_zctrl = None
        self.midi_learn_mode = 0 # 0:Disabled, 1:MIDI Learn, 2:ZS3 Learn
        self.learned_zs3 = []
        self.last_zs3_index = 0
        self.status_info = {}


        # Init Auto-connector
        self.zynautoconnect_audio_flag = False
        self.zynautoconnect_midi_flag = False
        zynautoconnect.start(self)

    def reset(self):
        zynautoconnect.stop()
        self.last_snapshot_fpath = None
        #TODO: self.chain_manager.reset_clone()
        #TODO: self.chain_manager.reset_note_range()
        self.chain_manager.remove_all_chains(True)
        self.reset_midi_profile()

    def create_amixer_chain(self):
        self.amixer_chain  = zynthian_chain()
        self.chain_manager.add_processor("amixer", 'MX')
        self.alsa_processor = zynthian_processor.zynthian_processor(self.chain_manager.engine_info["MX"])
        self.amixer_chain.insert_processor(self.alsa_processor)

    #----------------------------------------------------------------------------
    # Snapshot Save & Load
    #----------------------------------------------------------------------------

    def get_state(self):
        state = {
            'index':self.index,
            'mixer':[],
            'clone':[],
            'note_range':[],
            'audio_capture': self.get_audio_capture(),
            'last_snapshot_fpath': self.last_snapshot_fpath
        }

        # Chains info
        state['chains'] = self.chain_manager.get_state()

        # Add ALSA-Mixer setting as a layer
        if zyngine_config.snapshot_mixer_settings and self.amixer_chain:
            state['chains'].append(self.amixer_chain.get_state())

        # Clone info
        for i in range(0,16):
            state['clone'].append([])
            for j in range(0,16):
                clone_info = {
                    'enabled': lib_zyncore.get_midi_filter_clone(i,j),
                    'cc': list(map(int,lib_zyncore.get_midi_filter_clone_cc(i,j).nonzero()[0]))
                }
                state['clone'][i].append(clone_info)

        # Note-range info
        for i in range(0,16):
            info = {
                'note_low': lib_zyncore.get_midi_filter_note_low(i),
                'note_high': lib_zyncore.get_midi_filter_note_high(i),
                'octave_trans': lib_zyncore.get_midi_filter_octave_trans(i),
                'halftone_trans': lib_zyncore.get_midi_filter_halftone_trans(i)
            }
            state['note_range'].append(info)

        # Mixer
        try:
            state['mixer'] = self.zynmixer.get_state()
        except Exception as e:
            pass

        # Audio Recorder Armed
        state['audio_recorder_armed'] = []
        for midi_chan in [0,1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,256]:
            if self.audio_recorder.is_armed(midi_chan):
                state['audio_recorder_armed'].append(midi_chan)

        logging.debug("STATE index => {}".format(state['index']))

        return state


    def restore_state_snapshot(self, state):
        # Restore MIDI profile state
        if 'midi_profile_state' in state:
            self.set_midi_profile_state(state['midi_profile_state'])

        # Set MIDI Routing
        if 'midi_routing' in state:
            self.set_midi_routing(state['midi_routing'])
        else:
            self.reset_midi_routing()

        # Calculate root_layers
        self.root_layers = self.get_fxchain_roots()

        # Autoconnect MIDI
        self.zyngui.zynautoconnect_midi(True)

        # Set extended config and load bank list => when loading snapshots, not zs3!
        if 'extended_config' in state:
            # Extended settings (i.e. setBfree tonewheel model, aeolus tuning, etc.)
            self.set_extended_config(state['extended_config'])

        # Restore layer state, step 0 => bank list
        for i, lss in enumerate(state['layers']):
            self.layers[i].restore_state_0(lss)

        # Restore layer state, step 1 => Restore Bank & Preset Status
        for i, lss in enumerate(state['layers']):
            self.layers[i].restore_state_1(lss)

        # Restore layer state, step 2 => Restore Controllers Status
        for i, lss in enumerate(state['layers']):
            self.layers[i].restore_state_2(lss)

        # Set Audio Routing
        if 'audio_routing' in state:
            self.set_audio_routing(state['audio_routing'])
        else:
            self.reset_audio_routing()

        # Set Audio Capture
        if 'audio_capture' in state:
            self.set_audio_capture(state['audio_capture'])
        else:
            self.reset_audio_capture()

        self.fix_audio_inputs()

        # Audio Recorder Primed
        if 'audio_recorder_armed' not in state:
            state['audio_recorder_armed'] = []
        for midi_chan in [0,1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,256]:
            if midi_chan in state['audio_recorder_armed']:
                self.audio_recorder.arm(midi_chan)
            else:
                self.audio_recorder.unarm(midi_chan)

        # Set Clone
        if 'clone' in state:
            self.set_clone(state['clone'])
        else:
            self.reset_clone()

        # Note-range & Tranpose
        if 'note_range' in state:
            self.set_note_range(state['note_range'])
        # BW compat.
        elif 'transpose' in state:
            self.reset_note_range()
            self.set_transpose(state['transpose'])
        else:
            self.reset_note_range()

        # Mixer
        self.zynmixer.reset_state()
        if 'mixer' in state:
            self.zynmixer.set_state(state['mixer'])

        # Restore ALSA-Mixer settings
        if self.amixer_chain and 'amixer_chain' in state:
            self.amixer_chain.restore_state_1(state['amixer_chain'])
            self.amixer_chain.restore_state_2(state['amixer_chain'])

        # Set active layer
        self.chain_manager.set_active_chain_by_id(str(state['index']))

        # Autoconnect Audio
        self.zyngui.zynautoconnect_audio(True)

        # Restore Learned ZS3s (SubSnapShots)
        if 'learned_zs3' in state:
            self.learned_zs3 = state['learned_zs3']
        else:
            self.reset_zs3()
            self.import_legacy_zs3s(state)


    def import_legacy_zs3s(self, state):
        zs3_index = 0
        for midi_chan in range(0, 16):
            for prognum in range(0, 128):
                lstates = [None] * len(state['layers'])
                note_range = [None] * 16
                root_layer_index = None
                for li, lss in enumerate(state['layers']):
                    if 'zs3_list' in lss and midi_chan == lss['midi_chan']:
                        lstate = lss['zs3_list'][prognum]
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
                        'midi_learn_prognum': prognum
                    }
                    self.learned_zs3.append(zs3_new)
                    #logging.debug("ADDED LEGACY ZS3 #{} => {}".format(zs3_index, zs3_new))
                    zs3_index += 1


    def restore_state_zs3(self, state):

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
                if zyngine_config.midi_single_active_channel:
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
        if self.amixer_chain and 'amixer_chain' in state:
            self.amixer_chain.restore_state_1(state['amixer_chain'])
            self.amixer_chain.restore_state_2(state['amixer_chain'])

        # Set active layer
        if index is not None and index!=self.index:
            logging.info("Setting current_chain to {}".format(index))
            self.index = index
            self.chain_manager.set_active_chain_by_id(str(state['index']))

        # Autoconnect Audio => Not Needed!! It's called after action
        #self.zyngui.zynautoconnect_audio(True)


    def save_snapshot(self, fpath):
        try:
            # Get state
            state = self.get_state()

            # Extra engine state
            state['extended_config'] = self.get_extended_config()

            # MIDI profile
            state['midi_profile_state'] = self.get_midi_profile_state()

            # Audio & MIDI routing
            state['audio_routing'] = self.get_audio_routing()
            state['midi_routing'] = self.get_midi_routing()

            # Subsnapshots
            state['learned_zs3'] = self.learned_zs3

            # Zynseq RIFF data
            binary_riff_data = self.zynseq.get_riff_data()
            b64_data = base64_encoded_data = base64.b64encode(binary_riff_data)
            state['zynseq_riff_b64'] = b64_data.decode('utf-8')

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
            logging.error("Can't save snapshot '%s': %s" % (fpath, e))
            return False

        self.last_snapshot_fpath = fpath
        return True


    def load_snapshot(self, fpath, load_sequences=True):
        try:
            with open(fpath,"r") as fh:
                json=fh.read()
                logging.info("Loading snapshot %s => \n%s" % (fpath,json))
        except Exception as e:
            logging.error("Can't load snapshot '%s': %s" % (fpath,e))
            return False

        try:
            snapshot=JSONDecoder().decode(json)
            # Layers
            self._load_snapshot_layers(snapshot)
            # Sequences
            if load_sequences:
                self._load_snapshot_sequences(snapshot)

            if fpath == self.last_state_snapshot_fpath and "last_snapshot_fpath" in snapshot:
                self.last_snapshot_fpath = snapshot['last_snapshot_fpath']
            else:
                self.last_snapshot_fpath = fpath

        except Exception as e:
            #TODO: self.zyngui.reset_loading()
            logging.exception("Invalid snapshot: %s" % e)
            return False

        self.last_snapshot_count += 1
        return True


    def load_snapshot_layers(self, fpath):
        return self.load_snapshot(fpath, False)


    def load_snapshot_sequences(self, fpath):
        try:
            with open(fpath,"r") as fh:
                json=fh.read()
                logging.info("Loading snapshot %s => \n%s" % (fpath,json))
        except Exception as e:
            logging.error("Can't load snapshot '%s': %s" % (fpath,e))
            return False

        try:
            snapshot=JSONDecoder().decode(json)
            self._load_snapshot_sequences(snapshot)
        except Exception as e:
            #TODO: self.zyngui.reset_loading()
            logging.exception("Invalid snapshot: %s" % e)
            return False

        #self.last_snapshot_fpath = fpath
        return True


    def _load_snapshot_layers(self, snapshot):
        # Mute output to avoid unwanted noises
        mute = self.zynmixer.get_mute(256)
        self.zynmixer.set_mute(256, True)

        # Clean all layers, but don't stop unused engines
        self.chain_manager.remove_all_chains(False)

        # Reusing Jalv engine instances raise problems (audio routing & jack names, etc..),
        # so we stop Jalv engines!
        self.chain_manager.stop_unused_jalv_engines()

        #Create new layers, starting engines when needed
        for i, lss in enumerate(snapshot['layers']):
            if lss['engine_nick'] == "MX":
                if zyngine_config.snapshot_mixer_settings:
                    snapshot['amixer_chain'] = lss
                del snapshot['layers'][i]
            else:
                if 'engine_jackname' in lss:
                    jackname = lss['engine_jackname']
                else:
                    jackname = None
                engine = self.zyngui.screens['engine'].start_engine(lss['engine_nick'], jackname)
                #TODO: self.layers.append(zynthian_layer(engine, lss['midi_chan'], self.zyngui))

        # Finally, stop all unused engines
        self.zyngui.screens['engine'].stop_unused_engines()

        self.restore_state_snapshot(snapshot)

        # Restore mute state
        self.zynmixer.set_mute(255, mute)


    def _load_snapshot_sequences(self, snapshot):
        #Zynseq RIFF data
        if 'zynseq_riff_b64' in snapshot:
            b64_bytes = snapshot['zynseq_riff_b64'].encode('utf-8')
            binary_riff_data = base64.decodebytes(b64_bytes)
            self.zyngui.zynseq.restore_riff_data(binary_riff_data)


    def get_midi_profile_state(self):
        # Get MIDI profile state from environment
        midi_profile_state = OrderedDict()
        for key in os.environ.keys():
            if key.startswith("ZYNTHIAN_MIDI_"):
                midi_profile_state[key[14:]] = os.environ[key]
        return midi_profile_state


    def set_midi_profile_state(self, mps):
        # Load MIDI profile from saved state
        if mps is not None:
            for key in mps:
                os.environ["ZYNTHIAN_MIDI_" + key] = mps[key]
            zyngine_config.set_midi_config()
            self.init_midi()
            self.init_midi_services()
            self.zynautoconnect()
            return True


    def reset_midi_profile(self):
        self.zyngui.reload_midi_config()


    def set_select_path(self):
        self.select_path.set("Layers")


    #----------------------------------------------------------------------------
    # ZS3 management
    #----------------------------------------------------------------------------

    def set_midi_prog_zs3(self, midich, prognum):
        if zyngine_config.midi_single_active_channel:
            i = self.get_zs3_index_by_prognum(prognum)
        else:
            i = self.get_zs3_index_by_midich_prognum(midich, prognum)

        if i is not None:
            return self.restore_zs3(i)
        else:
            logging.debug("Can't find a ZS3 for CH#{}, PRG#{}".format(midich, prognum))
            return False


    def save_midi_prog_zs3(self, midich, prognum):
        # Look for a matching zs3 
        if midich is not None and prognum is not None:
            if zyngine_config.midi_single_active_channel:
                i = self.get_zs3_index_by_prognum(prognum)
            else:
                i = self.get_zs3_index_by_midich_prognum(midich, prognum)
        else:
            i = None
        
        # Get state and add MIDI-learn info
        state = self.get_state()
        state['zs3_title'] = "New ZS3"
        state['midi_learn_chan'] = midich
        state['midi_learn_prognum'] = prognum

        # Save in ZS3 list, overwriting if already used
        if i is None or i < 0 or i >= len(self.learned_zs3):
            self.learned_zs3.append(state)
            i = len(self.learned_zs3) - 1
        else:
            self.learned_zs3[i] = state

        self.last_zs3_index = i
        logging.info("Saved ZS3#{} => CH#{}:PRG#{}".format(i, midich, prognum))

        return i


    def get_zs3_index_by_midich_prognum(self, midich, prognum):
        for i, zs3 in enumerate(self.learned_zs3):
            try:
                if zs3['midi_learn_chan'] == midich and zs3['midi_learn_prognum'] == prognum:
                    return i
            except:
                pass


    def get_zs3_index_by_prognum(self, prognum):
        for i, zs3 in enumerate(self.learned_zs3):
            try:
                if zs3['midi_learn_prognum'] == prognum:
                    return i
            except:
                pass


    def get_last_zs3_index(self):
        return self.last_zs3_index


    def get_zs3_title(self, i):
        if i is not None and i >= 0 and i < len(self.learned_zs3):
            return self.learned_zs3[i]['zs3_title']


    def set_zs3_title(self, i, title):
        if i is not None and i >= 0 and i < len(self.learned_zs3):
            self.learned_zs3[i]['zs3_title'] = title


    def restore_zs3(self, i):
        try:
            if i is not None and i >= 0 and i < len(self.learned_zs3):
                logging.info("Restoring ZS3#{}...".format(i))
                self.restore_state_zs3(self.learned_zs3[i])
                self.last_zs3_index = i
                return True
            else:
                logging.debug("Can't find ZS3#{}".format(i))
        except Exception as e:
            logging.error("Can't restore ZS3 state => %s", e)

        return False


    def save_zs3(self, i=None):
        # Get state and add MIDI-learn info
        state = self.get_state()

        # Save in ZS3 list, overwriting if already used
        if i is None or i < 0 or i >= len(self.learned_zs3):
            state['zs3_title'] = "New ZS3"
            state['midi_learn_chan'] = None
            state['midi_learn_prognum'] = None
            self.learned_zs3.append(state)
            i = len(self.learned_zs3) - 1
        else:
            state['zs3_title'] = self.learned_zs3[i]['zs3_title']
            state['midi_learn_chan'] = self.learned_zs3[i]['midi_learn_chan']
            state['midi_learn_prognum'] = self.learned_zs3[i]['midi_learn_prognum']
            self.learned_zs3[i] = state

        logging.info("Saved ZS3#{}".format(i))
        self.last_zs3_index = i
        return i


    def delete_zs3(self, i):
        del(self.learned_zs3[i])
        if self.last_zs3_index == i:
            self.last_zs3_index = None


    def reset_zs3(self):
        # ZS3 list (subsnapshots)
        self.learned_zs3 = []
        # Last selected ZS3 subsnapshot
        self.last_zs3_index = None


    def delete_layer_state_from_zs3(self, j):
        for state in self.learned_zs3:
            try:
                del state['layers'][j]
            except:
                pass


    def clean_layer_state_from_zs3(self, j):
        for state in self.learned_zs3:
            try:
                state['layers'][j] = None
            except:
                pass

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
        
        zctrl - zcontroller object
        """
        
        self.midi_learn_zctrl = zctrl
        lib_zyncore.set_midi_learning_mode(1)
    
    def enter_midi_learn(self):
        """Enter MIDI learn mode"""

        if not self.midi_learn_mode:
            logging.debug("ENTER LEARN")
            self.midi_learn_mode = 1
            self.midi_learn_zctrl = None
            lib_zyncore.set_midi_learning_mode(1)


    def exit_midi_learn(self):
        """Exit MIDI learn mode"""

        if self.midi_learn_mode or self.midi_learn_zctrl:
            self.midi_learn_mode = 0
            self.midi_learn_zctrl = None
            lib_zyncore.set_midi_learning_mode(0)

    def toggle_midi_learn(self):
        """Toggle MIDI learn mode"""

        if self.midi_learn_mode:
            if zyngine_config.midi_prog_change_zs3:
                self.midi_learn_mode = 2
                self.midi_learn_zctrl = None
            else:
                self.exit_midi_learn()
        else:
            self.enter_midi_learn()

    #------------------------------------------------------------------
    # Autoconnect
    #------------------------------------------------------------------

    def zynautoconnect(self, force=False):
        """Trigger jack graph connections
        
        force - True to force connections
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
        
        force - True to force connections
        """
        if force:
            self.zynautoconnect_midi_flag = False
            zynautoconnect.midi_autoconnect(True)
        else:
            self.zynautoconnect_midi_flag = True


    def zynautoconnect_audio(self, force=False):
        """Trigger jack audio graph connections
        
        force - True to force connections
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
        try:
            #Set Global Tuning
            self.fine_tuning_freq = zyngine_config.midi_fine_tuning
            lib_zyncore.set_midi_filter_tuning_freq(ctypes.c_double(self.fine_tuning_freq))
            #Set MIDI Master Channel
            lib_zyncore.set_midi_master_chan(zyngine_config.master_midi_channel)
            #Set MIDI CC automode
            lib_zyncore.set_midi_filter_cc_automode(zyngine_config.midi_cc_automode)
            #Set MIDI System Messages flag
            lib_zyncore.set_midi_filter_system_events(zyngine_config.midi_sys_enabled)
            #Setup MIDI filter rules
            if self.midi_filter_script:
                self.midi_filter_script.clean()
            self.midi_filter_script = zynthian_midi_filter.MidiFilterScript(zyngine_config.midi_filter_rules)

        except Exception as e:
            logging.error("ERROR initializing MIDI : {}".format(e))


    def reload_midi_config(self):
        zynconf.load_config()
        midi_profile_fpath=zynconf.get_midi_config_fpath()
        if midi_profile_fpath:
            zynconf.load_config(True,midi_profile_fpath)
            zyngine_config.set_midi_config()
            self.init_midi()
            self.init_midi_services()
            self.zynautoconnect()

    def init_midi_services(self):
        #Start/Stop MIDI aux. services
        self.default_rtpmidi()
        self.default_qmidinet()
        self.default_touchosc()
        self.default_aubionotes()

    # ---------------------------------------------------------------------------
    # Global Audio Player
    # ---------------------------------------------------------------------------

    def start_audio_player(self):
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
                self.chain_manager.add_chain('aux') #TODO: Prob don't want chain
                self.audio_player = self.chain_manager.add_processor("aux", "AP", CHAIN_MODE_PARALLEL)
                zynautoconnect.audio_connect_aux(self.audio_player.jackname)
            except Exception as e:
                self.stop_audio_player()
                return
        self.audio_player.engine.set_preset(self.audio_player, [filename])
        self.audio_player.engine.player.set_position(16, 0.0)
        self.audio_player.engine.player.start_playback(16)
        #TODO: self.status_info['audio_player'] = 'PLAY'

    def stop_audio_player(self):
        if self.audio_player:
            self.audio_player.engine.player.stop_playback(16)

    # ---------------------------------------------------------------------------
    # Services
    # ---------------------------------------------------------------------------

    #Start/Stop RTP-MIDI depending on configuration
    def default_rtpmidi(self):
        if zyngine_config.midi_rtpmidi_enabled:
            self.start_rtpmidi(False)
        else:
            self.stop_rtpmidi(False)

    def start_rtpmidi(self, save_config=True):
        logging.info("STARTING RTP-MIDI")
        try:
            check_output("systemctl start jackrtpmidid", shell=True)
            zyngine_config.midi_rtpmidi_enabled = 1
            # Update MIDI profile
            if save_config:
                zynconf.update_midi_profile({ 
                    "ZYNTHIAN_MIDI_RTPMIDI_ENABLED": str(zyngine_config.midi_rtpmidi_enabled)
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
            zyngine_config.midi_rtpmidi_enabled = 0
            # Update MIDI profile
            if save_config:
                zynconf.update_midi_profile({ 
                    "ZYNTHIAN_MIDI_RTPMIDI_ENABLED": str(zyngine_config.midi_rtpmidi_enabled)
                })

        except Exception as e:
            logging.error(e)

    def start_qmidinet(self, save_config=True):
        logging.info("STARTING QMIDINET")
        try:
            check_output("systemctl start qmidinet", shell=True)
            zyngine_config.midi_network_enabled = 1
            # Update MIDI profile
            if save_config:
                zynconf.update_midi_profile({ 
                    "ZYNTHIAN_MIDI_NETWORK_ENABLED": str(zyngine_config.midi_network_enabled)
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
            zyngine_config.midi_network_enabled = 0
            # Update MIDI profile
            if save_config:
                zynconf.update_midi_profile({ 
                    "ZYNTHIAN_MIDI_NETWORK_ENABLED": str(zyngine_config.midi_network_enabled)
                })
        except Exception as e:
            logging.error(e)

    #Start/Stop QMidiNet depending on configuration
    def default_qmidinet(self):
        if zyngine_config.midi_network_enabled:
            self.start_qmidinet(False)
        else:
            self.stop_qmidinet(False)


    def start_touchosc2midi(self, save_config=True):
        logging.info("STARTING touchosc2midi")
        try:
            check_output("systemctl start touchosc2midi", shell=True)
            zyngine_config.midi_touchosc_enabled = 1
            # Update MIDI profile
            if save_config:
                zynconf.update_midi_profile({ 
                    "ZYNTHIAN_MIDI_TOUCHOSC_ENABLED": str(zyngine_config.midi_touchosc_enabled)
                })
            # Call autoconnect after a little time
            sleep(0.5)
            self.zyngui.zynautoconnect_midi()
        except Exception as e:
            logging.error(e)

    def stop_touchosc2midi(self, save_config=True):
        logging.info("STOPPING touchosc2midi")
        try:
            check_output("systemctl stop touchosc2midi", shell=True)
            zyngine_config.midi_touchosc_enabled = 0
            # Update MIDI profile
            if save_config:
                zynconf.update_midi_profile({ 
                    "ZYNTHIAN_MIDI_TOUCHOSC_ENABLED": str(zyngine_config.midi_touchosc_enabled)
                })
        except Exception as e:
            logging.error(e)

    #Start/Stop TouchOSC depending on configuration
    def default_touchosc(self):
        if zyngine_config.midi_touchosc_enabled:
            self.start_touchosc2midi(False)
        else:
            self.stop_touchosc2midi(False)

    def start_aubionotes(self, save_config=True):
        logging.info("STARTING aubionotes")
        try:
            check_output("systemctl start aubionotes", shell=True)
            zyngine_config.midi_aubionotes_enabled = 1
            # Update MIDI profile
            if save_config:
                zynconf.update_midi_profile({ 
                    "ZYNTHIAN_MIDI_AUBIONOTES_ENABLED": str(zyngine_config.midi_aubionotes_enabled)
                })
            # Call autoconnect after a little time
            sleep(0.5)
            self.zyngui.zynautoconnect()
        except Exception as e:
            logging.error(e)

    def stop_aubionotes(self, save_config=True):
        logging.info("STOPPING aubionotes")
        try:
            check_output("systemctl stop aubionotes", shell=True)
            zyngine_config.midi_aubionotes_enabled = 0
            # Update MIDI profile
            if save_config:
                zynconf.update_midi_profile({ 
                    "ZYNTHIAN_MIDI_AUBIONOTES_ENABLED": str(zyngine_config.midi_aubionotes_enabled)
                })
        except Exception as e:
            logging.error(e)

    #Start/Stop AubioNotes depending on configuration
    def default_aubionotes(self):
        if zyngine_config.midi_aubionotes_enabled:
            self.start_aubionotes(False)
        else:
            self.stop_aubionotes(False)

