# -*- coding: utf-8 -*-
#*****************************************************************************
# ZYNTHIAN PROJECT: Zynthian processor (zynthian_processor)
#
# zynthian processor
#
# Copyright (C) 2015-2022 Fernando Moyano <jofemodo@zynthian.org>
#						  Brian Walton <riban@zynthian.org>
#
#*****************************************************************************
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
#*****************************************************************************

from collections import OrderedDict
import copy
import logging
from time import sleep
import os

# Zynthian specific modules
from zyncoder.zyncore import get_lib_zyncore


class zynthian_processor:

    # ---------------------------------------------------------------------------
    # Data dirs
    # ---------------------------------------------------------------------------

    data_dir = os.environ.get('ZYNTHIAN_DATA_DIR',"/zynthian/zynthian-data")
    my_data_dir = os.environ.get('ZYNTHIAN_MY_DATA_DIR',"/zynthian/zynthian-my-data")
    ex_data_dir = os.environ.get('ZYNTHIAN_EX_DATA_DIR',"/media/usb0")

    # ------------------------------------------------------------------------
    # Initialization
    # ------------------------------------------------------------------------

    def __init__(self, type_info, id=None):
        """ Create an instance of a processor

        A processor represents a block within a chain.
        It provides access to a worker engine
        type_info : List of type info [short name, name, type, None, engine class, Bool]
        id : UID for processor (Default: None)
        """

        self.id = id
        self.type = type_info[2]
        self.engine = None
        self.name = type_info[0]
        self.midi_chan = None
        self.jackname = None

        self.bank_list = []
        self.bank_index = 0
        self.bank_name = None
        self.bank_info = None
        self.bank_msb = 0
        self.bank_msb_info = [[0,0], [0,0], [0,0]] # system, user, external => [offset, n]

        self.show_fav_presets = False
        self.preset_list = []
        self.preset_index = 0
        self.preset_name = None
        self.preset_info = None
        self.preset_bank_index = None
        self.preset_loaded = None

        self.preload_index = None
        self.preload_name = None
        self.preload_info = None

        self.controllers_dict = {}
        self.ctrl_screens_dict = {}
        self.current_screen_index = -1
        self.refresh_flag = False

    def reset(self):
        """ Reset processor to inital state, removing engine, etc."""

        # MIDI-unlearn all controllers
        self.midi_unlearn()
        # Delete layer from engine
        self.engine.del_layer(self) #TODO: Is this done elsewhere?
        # Clear refresh flag
        self.refresh_flag=False

    def get_jackname(self):
        """ Get the jackname for the processor's engine"""

        if self.jackname:
            return self.jackname
        if self.engine:
            return self.engine.jackname
        return ''

    def set_engine(self, engine):
        """Set engine that this processor uses"""
        
        self.engine = engine
        self.engine.add_layer(self) # TODO: Refactor engine to replace layer with processor
        self.refresh_controllers() #TODO: What is this?

    def get_name(self):
        """Get name of processor"""

        if self.engine:
            return self.engine.get_name(self)

    # ---------------------------------------------------------------------------
    # MIDI Channel Management
    # ---------------------------------------------------------------------------

    def set_midi_chan(self, midi_chan):
        """Set processor (and its engines) MIDI channel
        
        midi_chan - MIDI channel 0..15 or None
        """

        self.midi_chan = midi_chan
        if self.engine:
            self.engine.set_midi_chan(self)
            for zctrl in self.controllers_dict.values():
                zctrl.set_midi_chan(midi_chan)
            self.engine.refresh_midi_learn()
            self.send_ctrlfb_midi_cc()
    
    def get_midi_chan(self):
        """Get MIDI channel (0..15 or None)
        
        TODO: Processors inherit MIDI channel from chain
        """
        return self.midi_chan

    # ---------------------------------------------------------------------------
    # Bank Management
    # ---------------------------------------------------------------------------

    def load_bank_list(self):
        """Load bank list for processor"""

        self.bank_list = self.engine.get_bank_list(self)

        # Calculate info for bank_msb
        i = 0
        self.bank_msb_info = [[0,0], [0,0], [0,0]] # system, user, external => [offset, n]
        for bank in self.bank_list:
            if bank[0].startswith(self.ex_data_dir):
                self.bank_msb_info[0][0] += 1
                self.bank_msb_info[1][0] += 1
                self.bank_msb_info[2][1] += 1
                i += 1
            elif bank[0].startswith(self.my_data_dir):
                self.bank_msb_info[0][0] += 1
                self.bank_msb_info[1][1] += 1
                i += 1
            else:
                break
        self.bank_msb_info[0][1] = len(self.bank_list) - i

        # Add favourites virtual bank if there is some preset marked as favourite
        if self.engine.show_favs_bank and len(self.engine.get_preset_favs(self))>0:
            self.bank_list = [["*FAVS*",0,"*** Favorites ***"]] + self.bank_list
            for i in range(3):
                self.bank_msb_info[i][0] += 1

        logging.debug("BANK LIST => \n%s" % str(self.bank_list))
        logging.debug("BANK MSB INFO => \n{}".format(self.bank_msb_info))


    def reset_bank(self):
        """Reset bank to default (empty)"""
        self.bank_index=0
        self.bank_name=None
        self.bank_info=None


    def set_bank(self, i, set_engine=True):
        """Set processor's engine bank by index

        i - Index of the bank to select
        set_engine - True to set engine's bank
        Returns - True if bank selected, None if more bank selection steps required or False on failure
        """

        if i < len(self.bank_list):
            bank_name = self.bank_list[i][2]

            if bank_name is None:
                return False

            if i != self.bank_index or self.bank_name != bank_name:
                set_engine_needed = True
                logging.info("Bank selected: %s (%d)" % (self.bank_name, i))
            else:
                set_engine_needed = False
                logging.info("Bank already selected: %s (%d)" % (self.bank_name, i))

            last_bank_index = self.bank_index
            last_bank_name = self.bank_name
            self.bank_index = i
            self.bank_name = bank_name
            self.bank_info = copy.deepcopy(self.bank_list[i])

            if set_engine and set_engine_needed:
                return self.engine.set_bank(self, self.bank_info)

        return False


    def set_bank_by_name(self, bank_name, set_engine=True):
        """Set processor's engine bank by name
        
        bank_name - Name of bank to select
        set_engine - True to set engine's bank
        Returns - True on success
        #TODO Optimize search!!
        """
        
        for i in range(len(self.bank_list)):
            if bank_name == self.bank_list[i][2]:
                return self.set_bank(i, set_engine)
        return False


    #TODO Optimize search!!
    def set_bank_by_id(self, bank_id, set_engine=True):
        """Set processor's engine bank by id

        bank_id - ID of the bank to select
        set_engine - True to set engine's bank
        Returns - True if bank selected, None if more bank selection steps required or False on failure
        """

        for i in range(len(self.bank_list)):
            if bank_id == self.bank_list[i][0]:
                return self.set_bank(i, set_engine)
        return False


    def get_bank_name(self):
        """Get current bank name"""
        return self.bank_name


    def get_bank_index(self):
        """Get current bank index"""
        return self.bank_index


    # ---------------------------------------------------------------------------
    # Preset Management
    # ---------------------------------------------------------------------------

    def load_preset_list(self):
        """Load bank list for processor"""

        preset_list = []

        if self.show_fav_presets:
            for v in self.get_preset_favs().values():
                preset_list.append(v[1])
        elif self.bank_info:
            for preset in self.engine.get_preset_list(self.bank_info):
                if self.engine.is_preset_fav(preset):
                    preset[2] = "❤" + preset[2]
                preset_list.append(preset)
        else:
            return
        self.preset_list = preset_list
        logging.debug("PRESET LIST => \n%s" % str(self.preset_list))


    def reset_preset(self):
        """Reset preset to default (empty)"""
        logging.debug("PRESET RESET!")
        self.preset_index=0
        self.preset_name=None
        self.preset_info=None


    def set_preset(self, preset_index, set_engine=True, force_set_engine=True):
        """Set the processor's engine preset
        
        preset_index - Index of preset
        set_engine - True to set the engine preset???
        force_set_engine - True to force engine set???
        Returns - True on success
        """
        
        if preset_index < len(self.preset_list):
            preset_id = str(self.preset_list[preset_index][0])
            preset_name = self.preset_list[preset_index][2]
            preset_info = copy.deepcopy(self.preset_list[preset_index])

            if not preset_name:
                return False

            # Remove favorite marker char
            if preset_name[0]=='❤':
                preset_name=preset_name[1:]

            # Check if preset is in favorites pseudo-bank and set real bank if needed
            if preset_id in self.engine.preset_favs:
                bank_name = self.engine.preset_favs[preset_id][0][2]
                if bank_name!=self.bank_name:
                    self.set_bank_by_name(bank_name)

            # Check if force set engine
            if force_set_engine:
                set_engine_needed = True
            # Check if preset is already loaded
            elif self.engine.cmp_presets(preset_info, self.preset_info):
                set_engine_needed = False
                logging.info("Preset already selected: %s (%d)" % (preset_name, preset_index))
                # Check if some other preset is preloaded
                if self.preload_info and not self.engine.cmp_presets(self.preload_info,self.preset_info):
                    set_engine_needed = True
            else:
                set_engine_needed = True
                logging.info("Preset selected: %s (%d)" % (preset_name, preset_index))

            last_preset_index = self.preset_index #TODO: Not used
            last_preset_name = self.preset_name #TODO: Not used
            self.preset_index = preset_index
            self.preset_name = preset_name
            self.preset_info = preset_info
            self.preset_bank_index = self.bank_index

            # Clean preload info
            self.preload_index = None
            self.preload_name = None
            self.preload_info = None

            if set_engine:
                if set_engine_needed:
                    #self.load_ctrl_config()
                    return self.engine.set_preset(self, self.preset_info)
                else:
                    return False

            return True
        return False


    def set_preset_by_name(self, preset_name, set_engine=True, force_set_engine=True):
        """Set processor's engine preset by name
        
        preset_name - Name of preset to select
        set_engine - True to set engine's preset???
        force_set_engine - True to force setting engine's preset???
        TODO:Optimize search!!
        """
        for i in range(len(self.preset_list)):
            name_i = self.preset_list[i][2]
            try:
                if name_i[0]=='❤':
                    name_i=name_i[1:]
                if preset_name == name_i:
                    return self.set_preset(i, set_engine, force_set_engine)
            except:
                pass

        return False


    #TODO Optimize search!!
    def set_preset_by_id(self, preset_id, set_engine=True, force_set_engine=True):
        """Set processor's engine preset by ID
        
        preset_id - ID of preset to select
        set_engine - True to set engine's preset???
        force_set_engine - True to force setting engine's preset???
        TODO: Optimize search!!
        """

        for i in range(len(self.preset_list)):
            if preset_id==self.preset_list[i][0]:
                return self.set_preset(i, set_engine, force_set_engine)
        return False


    def preload_preset(self, preset_index):
        """Preload processor's engine preset by index
        
        preset_index - Index of preset
        Preloading request engine to temporarily load a preset
        """
        # Avoid preload on engines that take excessive time to load presets
        if self.engine.nickname in ['PD','MD']:
            return True
        if preset_index < len(self.preset_list):
            if (not self.preload_info and not self.engine.cmp_presets(self.preset_list[preset_index], self.preset_info)) or (self.preload_info and not self.engine.cmp_presets(self.preset_list[preset_index], self.preload_info)):
                self.preload_index = preset_index
                self.preload_name = self.preset_list[preset_index][2]
                self.preload_info = copy.deepcopy(self.preset_list[preset_index])
                logging.info("Preset Preloaded: %s (%d)" % (self.preload_name, preset_index))
                self.engine.set_preset(self,self.preload_info,True)
                return True
        return False


    def restore_preset(self):
        """Restore preset after temporary preload"""

        if self.preset_name is not None and self.preload_info is not None and not self.engine.cmp_presets(self.preload_info,self.preset_info):
            if self.preset_bank_index is not None and self.bank_index != self.preset_bank_index:
                self.set_bank(self.preset_bank_index, False)
            self.preload_index = None
            self.preload_name = None
            self.preload_info = None
            logging.info("Restore Preset: %s (%d)" % (self.preset_name, self.preset_index))
            self.engine.set_preset(self, self.preset_info)
            return True
        return False


    def get_preset_name(self):
        """Get current preset name"""
        return self.preset_name


    def get_preset_index(self):
        """Get index of current preset"""
        return self.preset_index


    def get_preset_bank_index(self):
        """Get current preset's bank index"""
        return self.preset_bank_index


    def get_preset_bank_name(self):
        """Get current preset's bank name"""
        try:
            return self.bank_list[self.preset_bank_index][2]
        except:
            return None


    def toggle_preset_fav(self, preset):
        """Toggle preset's favourite state
        
        preset - Preset info (list)
        """
        
        self.engine.toggle_preset_fav(self, preset)
        if self.show_fav_presets and not len(self.get_preset_favs()):
            self.set_show_fav_presets(False)


    def remove_preset_fav(self, preset):
        """Remove preset from favourites

        preset - Preset info (list)
        """

        self.engine.remove_preset_fav(preset)
        if self.show_fav_presets and not len(self.get_preset_favs()):
            self.set_show_fav_presets(False)


    def get_preset_favs(self):
        """Get list of favourite preset info structures"""

        return self.engine.get_preset_favs(self)


    def set_show_fav_presets(self, flag=True):
        """Set/reset flag indicating whether to show preset favourites
        
        flag - True to enable show favourites
        TODO: Should this be in UI?
        """
        
        if flag and len(self.engine.get_preset_favs(self)):
            self.show_fav_presets = True
            #self.reset_preset()
        else:
            self.show_fav_presets = False


    def get_show_fav_presets(self):
        """Get the flag indicating whether to show preset favourites"""
        return self.show_fav_presets


    def toggle_show_fav_presets(self):
        """Toggle flag indicating whether to show preset favourites"""

        if self.show_fav_presets:
            self.set_show_fav_presets(False)
        else:
            self.set_show_fav_presets(True)
        return self.show_fav_presets

    # ---------------------------------------------------------------------------
    # Controllers Management
    # ---------------------------------------------------------------------------

    def refresh_controllers(self):
        """Refresh processor controllers configuration"""

        self.init_controllers()
        self.init_ctrl_screens()


    def init_controllers(self):
        """Initialise processor controllers"""

        self.controllers_dict = self.engine.get_controllers_dict(self)


    def init_ctrl_screens(self):
        """Create controller screens from zynthian controller keys
        
        TODO: This should be in UI
        """

        #Build control screens ...
        self.ctrl_screens_dict = OrderedDict()
        for cscr in self.engine._ctrl_screens:
            self.ctrl_screens_dict[cscr[0]]=self.build_ctrl_screen(cscr[1])

        #Set active the first screen
        if len(self.ctrl_screens_dict) > 0:
            if self.current_screen_index == -1:
                self.current_screen_index = 0
        else:
            self.current_screen_index = -1


    def get_ctrl_screens(self):
        """Get processor controller screens
        
        TODO: This should be in UI
        Returns - Dictionary of controller screen structures
        """
        
        return self.ctrl_screens_dict


    def get_ctrl_screen(self, key):
        """Get processor controller screen

        key - Screen key
        Returns - Controller screen structure
        TODO: This should be in UI
        """

        try:
            return self.ctrl_screens_dict[key]
        except:
            return None


    def get_current_screen_index(self):
        """Get index of last selected controller screen
        
        Returns - Index of screen
        TODO: This should be in UI
        """
        
        return self.current_screen_index


    def set_current_screen_index(self, screen_index):
        """Set index of last selected controller screen
        
        screen_index - Index of screen
        TODO: This should be in UI
        """
        self.current_screen_index = screen_index


    def build_ctrl_screen(self, ctrl_keys):
        """Build array of zynthian_controllers from list of keys

        ctrl_keys - List of controller keys (symbols)
        TODO: This should be in UI
        """

        zctrls=[]
        for k in ctrl_keys:
            if k:
                try:
                    zctrls.append(self.controllers_dict[k])
                except:
                    logging.error("Controller %s is not defined" % k)
        return zctrls


    def send_ctrl_midi_cc(self):
        """Send MIDI CC for all controllers
        
        TODO: When is this required?
        """

        for k, zctrl in self.controllers_dict.items():
            if zctrl.midi_cc:
                get_lib_zyncore().ui_send_ccontrol_change(zctrl.midi_chan, zctrl.midi_cc, int(zctrl.value))
                logging.debug("Sending MIDI CH{}#CC{}={} for {}".format(zctrl.midi_chan, zctrl.midi_cc, int(zctrl.value), k))
        self.send_ctrlfb_midi_cc()


    def send_ctrlfb_midi_cc(self):
        """Send MIDI CC for all feeback controllers
        
        TODO: When is this required?
        """

        for k, zctrl in self.controllers_dict.items():
            if zctrl.midi_learn_cc:
                get_lib_zyncore().ctrlfb_send_ccontrol_change(zctrl.midi_learn_chan, zctrl.midi_learn_cc, int(zctrl.value))
                logging.debug("Sending MIDI FB CH{}#CC{}={} for {}".format(zctrl.midi_learn_chan, zctrl.midi_learn_cc, int(zctrl.value), k))
            elif zctrl.midi_cc:
                get_lib_zyncore().ctrlfb_send_ccontrol_change(zctrl.midi_chan, zctrl.midi_cc, int(zctrl.value))
                logging.debug("Sending MIDI FB CH{}#CC{}={} for {}".format(zctrl.midi_chan, zctrl.midi_cc, int(zctrl.value), k))


    def midi_unlearn(self, unused=None):
        """Clear all mapping of MIDI CC to controllers"""

        for k, zctrl in self.controllers_dict.items():
            zctrl.midi_unlearn()


    #----------------------------------------------------------------------------
    # MIDI processing
    #----------------------------------------------------------------------------

    def midi_control_change(self, chan, ccnum, ccval):
        """Handle MIDI CC message
        
        chan - MIDI channel
        ccnum - CC number
        ccval - CC value
        """
        
        if self.engine:
            #logging.debug("Receving MIDI CH{}#CC{}={}".format(chan, ccnum, ccval))
            try:
                self.engine.midi_control_change(chan, ccnum, ccval)
            except:
                pass


    def midi_bank_msb(self, bank_msb):
        """Handle MIDI bank MSB message
        
        bank_msb - Bank MSB
        """
        logging.debug("Received Bank MSB for CH#{}: {}".format(self.midi_chan, bank_msb))
        if bank_msb >= 0 and bank_msb <= 2:
            self.bank_msb = bank_msb


    def midi_bank_lsb(self, bank_lsb):
        """Handle MIDI bank MSB message
        
        bank_lsb - Bank LSB
        """
        info = self.bank_msb_info[self.bank_msb]
        logging.debug("Received Bank LSB for CH#{}: {} => {}".format(self.midi_chan, bank_lsb, info))
        if bank_lsb < info[1]:
            logging.debug("MSB offset for CH#{}: {}".format(self.midi_chan, info[0]))
            self.set_show_fav_presets(False)
            self.set_bank(info[0] + bank_lsb)
            self.load_preset_list()
        else:
            logging.warning("Bank index {} doesn't exist for MSB {} on CH#{}".format(bank_lsb, self.bank_msb, self.midi_chan))


    # ---------------------------------------------------------------------------
    # State Management
    # ---------------------------------------------------------------------------

    def get_state(self):
        """Get dictionary describing processor"""

        state = {
            'processor_type': self.engine.nickname,
            'bank_info': self.bank_info,
            'preset_info': self.preset_info,
            'show_fav_presets': self.show_fav_presets, #TODO: GUI
            'controllers_dict': {},
            'current_screen_index': self.current_screen_index #TODO: GUI
        }
        # Get controller values
        for symbol in self.controllers_dict:
            state['controllers_dict'][symbol] = self.controllers_dict[symbol].get_state()
        return state

    def set_state(self, state):
        """Configure processor from state model dictionary

        state - Processor state
        """

        self.load_bank_list()
        if state["bank_info"]:
            self.set_bank_by_id(state["bank_info"][0])
        self.load_preset_list()
        if state["preset_info"]:
            self.set_preset_by_id(state["preset_info"][0])
        # Set controller values
        for symbol in state['controllers_dict']:
            try:
                self.controllers_dict[symbol].restore_state(state['controllers_dict'][symbol])
            except Exception as e:
                logging.warning("Invalid Controller on layer {}: {}".format(self.get_basepath(), e))

    def restore_state_legacy(self, state):
        """Restore legacy states from state
        
        TODO: Move this to snapshot handler
        """
        
        #Set legacy Note Range (BW compatibility)
        if self.midi_chan is not None and self.midi_chan >= 0 and 'note_range' in state:
            nr = state['note_range']
            get_lib_zyncore().set_midi_filter_note_range(self.midi_chan, nr['note_low'], nr['note_high'], nr['octave_trans'], nr['halftone_trans'])


    def wait_stop_loading(self):
        """Wait until engine has finished loading or timed out"""

        while self.engine.loading > 0:
            logging.debug("WAITING FOR STOP LOADING ({}) ... => {}".format(self.engine.name, self.engine.loading))
            sleep(0.1)


    # ---------------------------------------------------------------------------
    # Path/Breadcrumb Strings
    # ---------------------------------------------------------------------------

    def get_path(self):
        """Get path (breadcrumb) string"""

        #TODO: UI
        if self.preset_name:
            bank_name = self.get_preset_bank_name()
            if not bank_name:
                bank_name = "???"
            path = bank_name + "/" + self.preset_name
        else:
            path = self.bank_name
        return path


    def get_basepath(self):
        """Get base path string"""
        #TODO: UI

        path = self.engine.get_path(self)
        if self.midi_chan is not None:
            if self.midi_chan < 16:
                path = "{}#{}".format(self.midi_chan+1, path)
            elif self.midi_chan == 256:
                path = "Main#{}".format(path)
        return path


    def get_bankpath(self):
        """Get bank path string"""

        #TODO: UI
        path = self.get_basepath()
        if self.bank_name and self.bank_name!="None":
            path += " > " + self.bank_name
        return path


    def get_presetpath(self):
        """Get preset path string"""

        #TODO: UI
        path = self.get_basepath()

        subpath = None
        bank_name = self.get_preset_bank_name()
        if bank_name and bank_name!="None":
            subpath = bank_name
            if self.preset_name:
                subpath += "/" + self.preset_name
        elif self.preset_name:
            subpath = self.preset_name

        if subpath:
            path += " > " + subpath

        return path

#-----------------------------------------------------------------------------