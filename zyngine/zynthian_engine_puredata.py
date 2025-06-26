# -*- coding: utf-8 -*-
# ******************************************************************************
# ZYNTHIAN PROJECT: Zynthian Engine (zynthian_engine_puredata)
#
# zynthian_engine implementation for PureData
#
# Copyright (C) 2015-2024 Fernando Moyano <jofemodo@zynthian.org>
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
import liblo
import queue
import shutil
import logging
import oyaml as yaml
from time import sleep
from os.path import isfile, join

import zynautoconnect
from . import zynthian_engine
from . import zynthian_basic_engine
from . import zynthian_controller

# ------------------------------------------------------------------------------
# Puredata Engine Class
# ------------------------------------------------------------------------------


class zynthian_engine_puredata(zynthian_engine):

    # ---------------------------------------------------------------------------
    # Controllers & Screens
    # ---------------------------------------------------------------------------

    default_organelle_zctrl_config = {
        'Knobs': {
            'knob1': {
                'midi_cc': 74,
                'value': 63
            },
            'knob2': {
                'midi_cc': 71,
                'value': 63
            },
            'knob3': {
                'midi_cc': 76,
                'value': 63
            },
            'knob4': {
                'midi_cc': 77,
                'value': 63
            }
        },
        'Master': {
            'volume': {
                'midi_cc': 7,
                'value': 90
            }
        }
    }

    _ctrls = [
    ]

    _ctrl_screens = [
    ]

    # ----------------------------------------------------------------------------
    # Config variables
    # ----------------------------------------------------------------------------

    startup_patch = zynthian_engine.data_dir + "/presets/puredata/zynthian_startup.pd"

    preset_fexts = ["pd"]
    root_bank_dirs = [
        ('User', zynthian_engine.my_data_dir + "/presets/puredata"),
        ('System', zynthian_engine.data_dir + "/presets/puredata")
    ]

    # ----------------------------------------------------------------------------
    # Initialization
    # ----------------------------------------------------------------------------

    def __init__(self, state_manager=None):
        super().__init__(state_manager)

        self.type = "Special"
        self.name = "PureData"
        self.nickname = "PD"
        self.jackname = self.state_manager.chain_manager.get_next_jackname(self.name)
        self.jackname_midi = ""

        # Initialize custom GUI path as None - will be set conditionally when loading presets
        self.custom_gui_fpath = None

        # Specific OSC stuff
        self.osc_zctrls = {}
        self.osc_child_handlers = []
        self.osc_unhandle_messages = queue.Queue(100)

        self.preset = ""
        self.preset_config = None
        self.zctrl_config = None

        if self.config_remote_display():
            self.base_command = f"pd -jack -nojackconnect -jackname \"{self.jackname}\" -rt -alsamidi -mididev 1"
        else:
            self.base_command = f"pd -nogui -jack -nojackconnect -jackname \"{self.jackname}\" -rt -alsamidi -mididev 1"

        self.reset()

    def get_jackname(self):
        return self.jackname_midi

    # ---------------------------------------------------------------------------
    # OSC Management
    # ---------------------------------------------------------------------------

    def osc_init(self):
        self.osc_drop_unhandle_messages()

        # Initialize OSC client.
        if not self.osc_target:
            try:
                self.osc_target = liblo.Address("localhost", self.osc_target_port, self.osc_proto)
                logging.info("OSC target in port {}".format(self.osc_target_port))
            except liblo.AddressError as err:
                self.osc_target = None
                logging.error(f"OSC client initialization error: {err}")

        # Start OSC server
        if not self.osc_server:
            try:
                self.osc_server = liblo.ServerThread(self.osc_server_port)
                self.osc_server.add_method(None, None, self.osc_handle_all)
                self.osc_server.start()
                logging.info("OSC server running in port {}".format(self.osc_server_port))
            except Exception as err:
                self.osc_server = None
                logging.error(f"OSC Server can't be started ({err}). Running without OSC feedback.")

    def osc_handle_all(self, path, args):
        try:
            self.osc_zctrls[path].set_value(args[0], send=False)
        except:
            if self.osc_child_handlers:
                for handler in self.osc_child_handlers:
                    if handler(path, args):
                        return
            else:
                #if self.osc_unhandle_messages.full():
                #    self.osc_unhandle_messages.get()
                try:
                    self.osc_unhandle_messages.put([path, args])
                except queue.Full:
                    pass
                    #logging.info(f"UNHANDLE OSC MESSAGE: {path}")

    def osc_add_child_handler(self, child_handler):
        self.osc_child_handlers.append(child_handler)

    def osc_reset_child_handlers(self):
        self.osc_child_handlers = []

    def osc_flush_unhandle_messages(self):
        while not self.osc_unhandle_messages.empty():
            path, args = self.osc_unhandle_messages.get()
            self.osc_handle_all(path, args)

    def osc_drop_unhandle_messages(self):
        while not self.osc_unhandle_messages.empty():
            self.osc_unhandle_messages.get()

    # ---------------------------------------------------------------------------
    # Processor Management
    # ---------------------------------------------------------------------------

    # ---------------------------------------------------------------------------
    # MIDI Channel Management
    # ---------------------------------------------------------------------------

    # ----------------------------------------------------------------------------
    # Bank Managament
    # ----------------------------------------------------------------------------

    def get_bank_list(self, processor=None):
        return self.get_bank_dirlist(recursion=2)

    def set_bank(self, processor, bank):
        return True

    # ----------------------------------------------------------------------------
    # Preset Managament
    # ----------------------------------------------------------------------------

    def get_preset_list(self, bank):
        return self.get_dirlist(bank[0])

    def set_preset(self, processor, preset, preload=False):
        self.load_preset_config(preset)
    
        # Set custom GUI path based on two conditions:
        # 1. Organelle is in the preset path, OR
        # 2. Preset config has an 'use_organelle_widget' flag set to True
        preset_path = preset[0]

        # Use Organelle widget for Organelle patches or when flag is set
        if "organelle" in preset_path.lower() or self.preset_config and self.preset_config.get('use_organelle_widget'):
            self.custom_gui_fpath = self.ui_dir + "/zyngui/zynthian_widget_organelle.py"
            if not self.zctrl_config:
                self.zctrl_config = self.default_organelle_zctrl_config
        elif self.preset_config and self.preset_config.get('use_euclidseq_widget', False):
            # Use EuclidSeq widget when flag is set
            self.custom_gui_fpath = "/zynthian/zynthian-ui/zyngui/zynthian_widget_euclidseq.py"
        else:
            # Don't use custom widget for other pd patches
            self.custom_gui_fpath = None

        try:
            self.command = self.base_command
            if self.custom_gui_fpath or (self.preset_config and self.preset_config.get('osc_zctrls', False)):
                self.osc_target_port = 3000 + 10 * processor.id
                self.osc_server_port = 3000 + 10 * processor.id + 1
                self.command += f" -send \";osc_receive_port {self.osc_target_port}; osc_send_port {self.osc_server_port}\""
            else:
                self.osc_target_port = None
                self.osc_server_port = None
            self.command += f" -open \"{self.startup_patch}\" \"{self.get_preset_filepath(preset)}\""
            self.preset = preset[0]
            self.stop()
            amidi_ports = self.get_amidi_clients()
            self.start()
            for symbol in processor.controllers_dict:
                self.state_manager.chain_manager.remove_midi_learn(processor, symbol)
            processor.refresh_controllers()
            sleep(2.0)
            amidi_ports = list(set(self.get_amidi_clients()) - set(amidi_ports))
            if len(amidi_ports) > 0:
                self.jackname_midi = f"Pure Data \\[{amidi_ports[0]}\\]"
                logging.debug(f"MIDI jackname => \"{self.jackname_midi}\"")
            else:
                self.jackname_midi = f"Pure Data"
                logging.error(f"Can't get MIDI jackname!")
        except Exception as err:
            logging.error(err)

        # Need to all autoconnect because restart of process
        try:
            self.state_manager.chain_manager.chains[processor.chain_id].rebuild_graph()
        except:
            pass
        zynautoconnect.request_audio_connect(True)
        zynautoconnect.request_midi_connect(True)
        processor.send_ctrl_midi_cc()
        return True

    def load_preset_config(self, preset):
        config_fpath = preset[0] + "/zynconfig.yml"
        try:
            with open(config_fpath, "r") as fh:
                yml = fh.read()
                logging.info(f"Loading preset config file {config_fpath} => \n{yml}")
                self.preset_config = yaml.load(yml, Loader=yaml.SafeLoader)
                self.zctrl_config = {}
                if self.preset_config:
                    for ctrl_group, ctrl_dict in self.preset_config.items():
                        if isinstance(ctrl_dict, dict):
                            self.zctrl_config[ctrl_group] = ctrl_dict
                    return True
                else:
                    logging.error(f"Preset config file '{config_fpath}' is empty.")
                    return False
        except Exception as e:
            logging.error(f"Can't load preset config file '{config_fpath}': {e}")
            return False

    def get_preset_filepath(self, preset):
        if self.preset_config:
            preset_fpath = preset[0] + "/" + self.preset_config['main_file']
            if isfile(preset_fpath):
                return preset_fpath

        preset_fpath = preset[0] + "/main.pd"
        if isfile(preset_fpath):
            return preset_fpath

        preset_fpath = preset[0] + "/" + os.path.basename(preset[0]) + ".pd"
        if isfile(preset_fpath):
            return preset_fpath

        preset_fpath = join(preset[0], os.listdir(preset[0])[0])
        return preset_fpath

    def cmp_presets(self, preset1, preset2):
        try:
            if preset1[0] == preset2[0] and preset1[2] == preset2[2]:
                return True
            else:
                return False
        except:
            return False

    # ----------------------------------------------------------------------------
    # Controllers Managament
    # ----------------------------------------------------------------------------

    def get_controllers_dict(self, processor):
        zctrls = {}
        self._ctrl_screens = []
        self.osc_zctrls = {}
        if self.zctrl_config:
            for ctrl_group, ctrl_dict in self.zctrl_config.items():
                logging.debug(f"Preset Config '{ctrl_group}' ...")
                c = 1
                ctrl_set = []
                if ctrl_group == 'midi_controllers':
                    ctrl_group = 'Controllers'
                logging.debug(f"Generating Controller Screens for '{ctrl_group}' => {ctrl_dict}")
                try:
                    for name, options in ctrl_dict.items():
                        try:
                            if len(ctrl_set) >= 4:
                                screen_title = f"{ctrl_group}#{c}"
                                logging.debug(f"Adding Controller Screen {screen_title}")
                                self._ctrl_screens.append([screen_title, ctrl_set])
                                ctrl_set = []
                                c += 1
                            if isinstance(options, int):
                                options = {'midi_cc': options}
                            if 'midi_chan' not in options:
                                options['midi_chan'] = processor.midi_chan
                            logging.debug(f"CTRL {name} => {options}")
                            options['name'] = str.replace(name, '_', ' ')
                            options['processor'] = processor
                            zctrl = zynthian_controller(self, name, options)
                            zctrls[name] = zctrl
                            ctrl_set.append(name)
                            if 'osc_path' in options:
                                self.osc_zctrls[options['osc_path']] = zctrl
                        except Exception as err:
                            logging.error(f"Generating Controller Screens: {err}")
                    if len(ctrl_set) >= 1:
                        if c > 1:
                            screen_title = f"{ctrl_group}#{c}"
                        else:
                            screen_title = ctrl_group
                        logging.debug(f"Adding Controller Screen {screen_title}")
                        self._ctrl_screens.append([screen_title, ctrl_set])
                except Exception as err:
                    logging.error(err)

        if len(zctrls) == 0:
            zctrls = super().get_controllers_dict(processor)
        else:
            processor.controllers_dict = zctrls

        return zctrls

    # --------------------------------------------------------------------------
    # Special
    # --------------------------------------------------------------------------

    @staticmethod
    def get_amidi_clients():
        res = []
        try:
            with open("/proc/asound/seq/clients", "r") as f:
                for line in f.readlines():
                    if line.startswith("Client") and "\"Pure Data\" [User Legacy]" in line:
                        try:
                            res.append(int(line[7:10]))
                        except Exception as e:
                            logging.error(f"Can't parse ALSA MIDI client port for {line} => {e}")
            #logging.debug(f"ALSA MIDI CLIENTS => {res}")
        except Exception as e:
            logging.error(f"Can't get ALSA MIDI client list => {e}")
        return res

    # ---------------------------------------------------------------------------
    # API methods
    # ---------------------------------------------------------------------------

    @classmethod
    def zynapi_get_banks(cls):
        banks = []
        for b in cls.get_bank_dirlist(recursion=2, exclude_empty=False):
            banks.append({
                'text': b[2],
                'name': b[4],
                'fullpath': b[0],
                'raw': b,
                'readonly': False
            })
        return banks

    @classmethod
    def zynapi_get_presets(cls, bank):
        presets = []
        for p in cls.get_dirlist(bank['fullpath']):
            presets.append({
                'text': p[4],
                'name': p[2],
                'fullpath': p[0],
                'raw': p,
                'readonly': False
            })
        return presets

    @classmethod
    def zynapi_new_bank(cls, bank_name):
        os.mkdir(zynthian_engine.my_data_dir + "/presets/puredata/" + bank_name)

    @classmethod
    def zynapi_rename_bank(cls, bank_path, new_bank_name):
        head, tail = os.path.split(bank_path)
        new_bank_path = head + "/" + new_bank_name
        os.rename(bank_path, new_bank_path)

    @classmethod
    def zynapi_remove_bank(cls, bank_path):
        shutil.rmtree(bank_path)

    @classmethod
    def zynapi_rename_preset(cls, preset_path, new_preset_name):
        head, tail = os.path.split(preset_path)
        new_preset_path = head + "/" + new_preset_name
        os.rename(preset_path, new_preset_path)

    @classmethod
    def zynapi_remove_preset(cls, preset_path):
        shutil.rmtree(preset_path)

    @classmethod
    def zynapi_download(cls, fullpath):
        return fullpath

    @classmethod
    def zynapi_install(cls, dpath, bank_path):
        if not bank_path:
            raise Exception("You must select a destiny bank folder!")
        if os.path.isdir(dpath):
            shutil.move(dpath, bank_path)
            # TODO Test if it's a PD bundle
        else:
            fname, ext = os.path.splitext(dpath)
            if ext == '.pd':
                bank_path += "/" + fname
                os.mkdir(bank_path)
                shutil.move(dpath, bank_path)
            else:
                raise Exception("File doesn't look like a PD patch!")

    @classmethod
    def zynapi_get_formats(cls):
        return "pd,zip,tgz,tar.gz,tar.bz2"

# ******************************************************************************