# -*- coding: utf-8 -*-
# ******************************************************************************
# ZYNTHIAN PROJECT: Zynthian Engine (zynthian_engine_jalv)
#
# zynthian_engine implementation for Jalv Plugin Host
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
import re
import sys
import copy
import shutil
import logging
import traceback
from time import sleep
#from datetime import datetime
from threading import Thread
from subprocess import Popen, check_output, STDOUT, PIPE

from . import zynthian_lv2
from . import zynthian_engine
from . import zynthian_controller
from zyncoder.zyncore import lib_zyncore
from zyngine.ctrlinfo import *

# ------------------------------------------------------------------------------
# Jalv Engine Class => Engine for LV2 plugins
# ------------------------------------------------------------------------------


class zynthian_engine_jalv(zynthian_engine):

    # ------------------------------------------------------------------------------
    # Custom plugin info
    # ------------------------------------------------------------------------------

    if "Raspberry Pi 4" in os.environ.get('RBPI_VERSION'):
        rpi = "RPi4"
    elif "Raspberry Pi 3" in os.environ.get('RBPI_VERSION'):
        rpi = "RPi3"
    else:
        rpi = "RPi2"

    # Plugins that required different GUI toolkit to that advertised or cannot run native GUI on Zynthian
    broken_ui = {
        # 'http://calf.sourceforge.net/plugins/Monosynth': {"RPi4:":True, "RPi3": False, "RPi2": False },
        # 'http://calf.sourceforge.net/plugins/Organ': {"RPi4:":True, "RPi3": False, "RPi2": False },
        # 'http://nickbailey.co.nr/triceratops': {"RPi4:":True, "RPi3": False, "RPi2": False },
        # 'http://code.google.com/p/amsynth/amsynth': {"RPi4:":True, "RPi3": False, "RPi2": False },
        # Disable because CPU usage and widget implemented in main UI
        'http://gareus.org/oss/lv2/tuna#one': {"RPi5": False, "RPi4": False, "RPi3": False, "RPi2": False},
        # Disable because CPU usage and widget implemented in main UI
        'http://gareus.org/oss/lv2/tuna#mod': {"RPi5": False, "RPi4": False, "RPi3": False, "RPi2": False},
        # "http://tytel.org/helm": {"RPi5": False, "RPi4": False, "RPi3": True, "RPi2": False},				 # Better CPU with gtk but only qt4 works on RPi4
        'https://git.code.sf.net/p/qmidiarp/arp': {"RPi5": "X11UI", "RPi4": "X11UI", "RPi3": "X11UI", "RPi2": "X11UI"},
        'https://git.code.sf.net/p/qmidiarp/lfo': {"RPi5": "X11UI", "RPi4": "X11UI", "RPi3": "X11UI", "RPi2": "X11UI"},
        'https://git.code.sf.net/p/qmidiarp/seq': {"RPi5": "X11UI", "RPi4": "X11UI", "RPi3": "X11UI", "RPi2": "X11UI"},
        'http://distrho.sf.net/plugins/3BandEQ': {"RPi5": False, "RPi4": False, "RPi3": False, "RPi2": False}
    }

    plugins_custom_gui = {
        'http://gareus.org/oss/lv2/meters#spectr30mono': zynthian_engine.ui_dir + "/zyngui/zynthian_widget_spectr30.py",
        'http://gareus.org/oss/lv2/meters#spectr30stereo': zynthian_engine.ui_dir + "/zyngui/zynthian_widget_spectr30.py",
        'http://gareus.org/oss/lv2/tuna#one': zynthian_engine.ui_dir + "/zyngui/zynthian_widget_tunaone.py",
        'http://gareus.org/oss/lv2/tuna#mod': zynthian_engine.ui_dir + "/zyngui/zynthian_widget_tunaone.py",
        'http://looperlative.com/plugins/lp3-basic': zynthian_engine.ui_dir + "/zyngui/zynthian_widget_looper.py",
        'http://aidadsp.cc/plugins/aidadsp-bundle/rt-neural-loader': zynthian_engine.ui_dir + "/zyngui/zynthian_widget_aidax.py",
        'http://github.com/mikeoliphant/neural-amp-modeler-lv2': zynthian_engine.ui_dir + "/zyngui/zynthian_widget_nam.py"
    }

    # ------------------------------------------------------------------------------
    # Native formats configuration (used by zynapi_install, preset converter, etc.)
    # ------------------------------------------------------------------------------

    plugin2native_ext = {
        "Dexed": "syx",
        "synthv1": "synthv1",
        "padthv1": "padthv1",
        "Obxd": "fxb"
        # "Helm": "helm"
    }

    plugin2preset2lv2_format = {
        "Dexed": "dx7syx",
        "synthv1": "synthv1",
        "padthv1": "padthv1",
        "Obxd": "obxdfxb"
        # "Helm": "helm"
    }

    # ---------------------------------------------------------------------------
    # Custom controller pages
    # ---------------------------------------------------------------------------

    plugin_ctrl_info = {
        "ctrls": {
            'volume': [7, 98],
            'panning': [10, 64],
            'modulation wheel': [1, 0],
            'filter cutoff': [74, 64],
            'filter resonance': [71, 64]
        },
        "ctrl_screens": {
            '_default_synth': ['modulation wheel'],
            'Calf Monosynth': ['modulation wheel'],
            'Dexed': [],
            'Fabla': [],
            'Foo YC20 Organ': [],
            'Helm': [],
            'MDA DX10': ['volume', 'modulation wheel'],
            'MDA JX10': ['volume', 'modulation wheel'],
            'MDA ePiano': ['volume', 'modulation wheel'],
            'MDA Piano': ['volume', 'modulation wheel'],
            'Nekobi': [],
            'Noize Mak3r': [],
            'Obxd': ['modulation wheel'],
            'Pianoteq 7 Stage': [],
            'Raffo Synth': [],
            'Red Zeppelin 5': [],
            'reMID': ['volume'],
            'String machine': [],
            'synthv1': [],
            'Surge': ['modulation wheel'],
            'padthv1': [],
            'Vex': [],
            'amsynth': ['modulation wheel'],
            'JC303': [],
            'Novachord': []
        }
    }

    # ----------------------------------------------------------------------------
    # ZynAPI variables
    # ----------------------------------------------------------------------------

    zynapi_instance = None

    # ----------------------------------------------------------------------------
    # Initialization
    # ----------------------------------------------------------------------------

    def __init__(self, eng_code, state_manager, dryrun=False, jackname=None):
        super().__init__(state_manager)

        self.proc_poll_thread = None

        self.save_bank = None
        self.save_preset_uri = None

        if state_manager:
            self.eng_info = self.state_manager.chain_manager.engine_info[eng_code]
        else:
            self.eng_info = zynthian_lv2.get_engines()[eng_code]

        self.type = self.eng_info["TYPE"]
        self.name = "Jalv/" + self.eng_info["NAME"]
        self.nickname = eng_code
        self.plugin_name = self.eng_info["NAME"]
        self.plugin_url = self.eng_info['URL']

        # WARNING Show all controllers for Gareus Meters, as they seem to be wrongly marked with property "not_on_gui"
        if self.plugin_url.startswith("http://gareus.org/oss/lv2/meters"):
            self.ignore_not_on_gui = True
        else:
            self.ignore_not_on_gui = False

        self.native_gui = False
        if 'UI' in self.eng_info:
            if self.plugin_url in self.broken_ui:
                self.native_gui = self.broken_ui[self.plugin_url][self.rpi]
            else:
                self.native_gui = self.eng_info['UI']

        if not dryrun:
            if jackname:
                self.jackname = jackname
            else:
                self.jackname = self.state_manager.chain_manager.get_next_jackname(self.plugin_name)

            logging.debug("CREATING JALV ENGINE => {}".format(self.jackname))

            if self.config_remote_display() and self.native_gui:
                if self.native_gui == "Qt5UI":
                    jalv_bin = "jalv.qt5"
                elif self.native_gui == "Qt4UI":
                    # jalv_bin = "jalv.qt4"
                    jalv_bin = "jalv.gtk3"
                else:  # elif self.native_gui=="X11UI":
                    jalv_bin = "jalv.gtk3"
                self.command = [jalv_bin, "--jack-name", self.jackname, self.plugin_url]
            else:
                self.command = ["jalv", "-n", self.jackname, self.plugin_url]
                # Some plugins need a X11 display for running headless (QT5, QT6),
                # but some others can't run headless if there is a valid DISPLAY defined
                if not self.plugin_name.endswith("v1"):
                    self.command_env['DISPLAY'] = "X"

            # Use jalv's development version =>
            #self.command[0] = "/zynthian/zynthian-sw/jalv_asyncli/build/" + self.command[0]

            self.command_prompt = ">"

            # Jalv which uses PWD as the root for presets
            self.command_cwd = zynthian_engine.my_data_dir + "/presets/lv2"

            output = self.start()

            # Get Plugin & Jack names from Jalv starting text ...
            if output:
                for line in output.split("\n"):
                    if line[0:10] == "JACK Name:":
                        self.jackname = line[11:].strip()
                        logging.debug("Jack Name => {}".format(self.jackname))
                        break

            # Setup MIDI Controllers
            self._ctrls = []
            self._ctrl_screens = []

            # Search for a custom controller config for this plugin
            module_name = f"zyngine.ctrlinfo.ctrlinfo_{self.plugin_name}"
            if module_name in sys.modules:
                try:
                    self._ctrls = getattr(sys.modules[module_name], "ctrls", None)
                    self._ctrl_screens = getattr(sys.modules[module_name], "ctrl_screens", None)
                    logging.info("Using custom MIDI controllers file for '{}'.".format(self.plugin_name))
                except Exception as e:
                    logging.error(f"Wrong ctrlinfo module => {e}")

            # If not available or wrong, take from hardcoded controller configs
            if not self._ctrls or not self._ctrl_screens:
                self._ctrls = []
                self._ctrl_screens = []
                try:
                    if self.plugin_name in self.plugin_ctrl_info['ctrl_screens']:
                        logging.info("Using custom MIDI controllers for '{}'.".format(self.plugin_name))
                        ctrl_screens = self.plugin_ctrl_info['ctrl_screens'][self.plugin_name]
                    elif self.type == 'MIDI Synth':
                        logging.info("Using default MIDI controllers for '{}'.".format(self.plugin_name))
                        ctrl_screens = self.plugin_ctrl_info['ctrl_screens']['_default_synth']
                    else:
                        ctrl_screens = None
                    if ctrl_screens:
                        self._ctrl_screens = [['MIDI Controllers', copy.copy(ctrl_screens)]]
                        for ctrl_name in ctrl_screens:
                            self._ctrls.append([ctrl_name] + self.plugin_ctrl_info['ctrls'][ctrl_name])
                except Exception as e:
                    logging.error(f"Error setting MIDI controllers for '{self.plugin_name}' => {e}")

            #logging.debug(f"CTRLS => {self._ctrls}")
            #logging.debug(f"CTRL_SCREENS => {self._ctrl_screens}")

            # Generate LV2-Plugin Controllers
            self.lv2_monitors_dict = {}
            self.lv2_zctrl_dict = self.get_lv2_controllers_dict()
            self.generate_ctrl_screens(self.lv2_zctrl_dict)

            # Look for a custom GUI
            try:
                self.custom_gui_fpath = self.plugins_custom_gui[self.plugin_url]
            except:
                self.custom_gui_fpath = None

        # Get bank & presets info
        self.load_preset_info()

        self.reset()

    def load_preset_info(self):
        self.preset_info = zynthian_lv2.get_plugin_presets_cache(self.plugin_name)

    # ---------------------------------------------------------------------------
    # Subprocess Management & IPC
    # ---------------------------------------------------------------------------

    def start(self):
        if not self.proc:
            logging.info("Starting Engine {}".format(self.name))
            try:
                logging.debug("Command: {}".format(self.command))
                self.proc_exit = False
                # Turns out that environment's PWD is not set automatically
                # when cwd is specified for pexpect.spawn(), so do it here.
                if self.command_cwd:
                    self.command_env['PWD'] = self.command_cwd
                # Setting cwd is because we've set PWD above. Some engines doesn't
                # care about the process's cwd, but it is more consistent to set
                # cwd when PWD has been set.
                self.proc = Popen(self.command, env=self.command_env, cwd=self.command_cwd, shell=False,
                                  text=True, bufsize=1, stdout=PIPE, stderr=STDOUT, stdin=PIPE)
                output = self.proc_get_output()
                self.start_proc_poll_thread()
                return output

            except Exception as err:
                logging.error(
                    "Can't start engine {} => {}".format(self.name, err))

    def stop(self):
        if self.proc:
            try:
                logging.info("Stopping Engine " + self.name)
                self.proc_cmd("")
                self.proc_exit = True
                self.proc.terminate()
                try:
                    self.proc.wait(timeout=5)
                except:
                    self.proc.kill()
                self.proc = None
            except Exception as err:
                logging.error(f"Can't stop engine {self.name} => {err}")

    def proc_cmd(self, cmd):
        #a = datetime.now()
        self.proc.stdin.writelines([cmd + "\n"])
        #tdus = (datetime.now() - a).microseconds
        #logging.debug(f"COMMAND ({tdus}): {cmd}")

    def proc_get_output(self):
        res = ""
        while not self.proc_exit:
            line = self.proc.stdout.readline().strip()
            if line == self.command_prompt:
                break
            elif line:
                res += line
        return res

    def proc_poll_line(self):
        return self.proc.stdout.readline()

    def proc_poll_thread_task(self):
        while not self.proc_exit:
            line = self.proc.stdout.readline().strip()
            if line:
                self.proc_poll_parse_line(line)

    def proc_poll_parse_line(self, line):
        #logging.debug(f"{self.jackname} PARSE => " + line)
        match line[0:5]:
            case "#CTR>":
                self.proc_parse_ctrl_value(line[6:])
            case "#MON>":
                self.proc_parse_mon_value(line[6:])
            case "#PRS>":
                self.proc_parse_preset(line[6:])
            case _:
                if line == self.command_prompt:
                    logging.debug(f"PROMPT {self.jackname} >")
                elif line:
                    logging.debug(f"LOG {self.jackname} > " + line)

    def proc_parse_ctrl_value(self, line):
        parts = line.split("=")
        if len(parts) == 2:
            symparts = parts[0].split("#", maxsplit=1)
            #logging.debug(f"#CTR> {symparts[1]} ({symparts[0]}) = {val}")
            try:
                zctrl = self.lv2_zctrl_dict[symparts[1]]
                if zctrl.is_path:
                    val = parts[1]
                else:
                    try:
                        val = float(parts[1])
                    except Exception as e:
                        logging.warning(f"Wrong controller value when parsing jalv output => {line}")
                        return
                zctrl.set_value(val, False)
                if zctrl.graph_path is None:
                    try:
                        zctrl.graph_path = int(symparts[0])
                        #logging.debug(f"UPDATING JALV ZCTRL INDEX FOR '{symparts[1]}' => {zctrl.graph_path}")
                    except:
                        logging.warning(f"Cant't parse controller index from jalv output: {line}")
            except Exception as e:
                # TODO This shouldn't happen when property parameters are fully implemented
                logging.warning(f"Unknown controller when parsing jalv output => {line}")
        else:
            logging.warning(f"Wrong controller format when parsing jalv output => {line}")

    def proc_parse_mon_value(self, line):
        parts = line.split("=")
        if len(parts) == 2:
            try:
                val = float(parts[1])
            except Exception as e:
                logging.warning(f"Wrong monitor value when parsing jalv output => {line}")
                return
            symparts = parts[0].split("#", maxsplit=1)
            #logging.debug(f"#MON> {symparts[1]} ({symparts[0]}) = {val}")
            try:
                self.lv2_monitors_dict[symparts[1]] = val
            except Exception as e:
                # TODO This shouldn't happen when property parameters are fully implemented
                logging.warning(f"Unknown monitor when parsing jalv output => {line}")
        else:
            logging.warning(f"Wrong monitor format when parsing jalv output => {line}")

    def proc_parse_preset(self, line):
        parts = line.split(" ", maxsplit=1)
        if len(parts) == 2 and parts[1][0] == "(" and parts[1][-1] == ")":
            self.add_preset(parts[0], parts[1][1:-1])
            self.save_preset_uri = parts[0]
        else:
            logging.warning(f"Wrong preset format when parsing jalv output => {line}")

    def start_proc_poll_thread(self):
        self.proc_poll_thread = Thread(target=self.proc_poll_thread_task, args=())
        self.proc_poll_thread.name = f"proc_poll_{self.jackname}"
        self.proc_poll_thread.daemon = True  # thread dies with the program
        self.proc_poll_thread.start()

    # ---------------------------------------------------------------------------
    # Processor Management
    # ---------------------------------------------------------------------------

    def add_processor(self, processor):
        super().add_processor(processor)
        self.set_midi_chan(processor)

    def get_name(self, processor=None):
        return self.plugin_name

    def get_path(self, processor=None):
        return self.plugin_name

    # ---------------------------------------------------------------------------
    # MIDI Channel Management
    # ---------------------------------------------------------------------------

    def set_midi_chan(self, processor):
        processor.midi_chan_engine = processor.midi_chan
        if self.plugin_name == "Triceratops":
            self.lv2_zctrl_dict["midi_channel"].set_value(processor.midi_chan + 1.5)
        elif self.plugin_name.startswith("SO-"):
            self.lv2_zctrl_dict["channel"].set_value(processor.midi_chan)
        elif self.plugin_name in ("Osirus", "OsTIrus"):
            processor.midi_chan_engine = 0
            lib_zyncore.zmop_set_midi_chan_trans(processor.chain.zmop_index,
                                                 processor.midi_chan,
                                                 processor.midi_chan_engine)

    # ----------------------------------------------------------------------------
    # Bank Managament
    # ----------------------------------------------------------------------------

    def get_bank_list(self, processor=None):
        bank_list = []
        for bank_label, info in self.preset_info.items():
            if info['bank_url'] is None:
                bank_uri = ""
            else:
                bank_uri = str(info['bank_url'])
            bank_list.append((bank_uri, None, bank_label, None))
        if len(bank_list) == 0:
            bank_list.append(("", None, "None", None))
        return bank_list

    def set_bank(self, processor, bank):
        return True

    def get_user_bank_urid(self, bank_name):
        return "file://{}/presets/lv2/{}.presets.lv2/{}".format(self.my_data_dir,
                                                                zynthian_engine_jalv.sanitize_text(self.plugin_name),
                                                                zynthian_engine_jalv.sanitize_text(bank_name))

    def create_user_bank(self, bank_name):
        bundle_path = "{}/presets/lv2/{}.presets.lv2".format(
            self.my_data_dir, zynthian_engine_jalv.sanitize_text(self.plugin_name))
        fpath = bundle_path + "/manifest.ttl"

        bank_id = zynthian_engine_jalv.sanitize_text(bank_name)
        bank_ttl = "\n<{}>\n".format(bank_id)
        bank_ttl += "\ta pset:Bank ;\n"
        bank_ttl += "\tlv2:appliesTo <{}> ;\n".format(self.plugin_url)
        bank_ttl += "\trdfs:label \"{}\" .\n".format(bank_name)

        with open(fpath, 'a+') as f:
            f.write(bank_ttl)

        # Cache is updated when saving the preset

    def rename_user_bank(self, bank, new_bank_name):
        if self.is_preset_user(bank):
            try:
                # TODO: This changes position of bank in list - Suggest using bank URI as key in preset_info
                zynthian_engine_jalv.lv2_rename_bank(bank[0], new_bank_name)
            except Exception as e:
                logging.error(e)

            # Update cache
            try:
                self.preset_info[new_bank_name] = self.preset_info.pop(bank[2])
                zynthian_lv2.save_plugin_presets_cache(
                    self.plugin_name, self.preset_info)
            except Exception as e:
                logging.error(e)

    def remove_user_bank(self, bank):
        if self.is_preset_user(bank):
            try:
                zynthian_engine_jalv.lv2_remove_bank(bank)
            except Exception as e:
                logging.error(e)

            # Update cache
            if bank[2] in self.preset_info:
                try:
                    self.preset_info.pop(bank[2])
                    zynthian_lv2.save_plugin_presets_cache(
                        self.plugin_name, self.preset_info)
                except Exception as e:
                    logging.error(e)

    def delete_user_bank(self, bank):
        if self.is_preset_user(bank):
            try:
                for preset in list(self.preset_info[bank[2]]['presets']):
                    self.delete_preset(bank, preset['url'])
                self.remove_user_bank(bank)
                # TODO: self.zyngui.curprocessor.load_preset_list()
            except Exception as e:
                logging.error(e)

    # ----------------------------------------------------------------------------
    # Preset Managament
    # ----------------------------------------------------------------------------

    def get_preset_list(self, bank):
        preset_list = []
        try:
            for info in self.preset_info[bank[2]]['presets']:
                title = info['label'].replace("_", " ").strip()
                preset_list.append([info['url'], None, title, bank[0]])
        except:
            preset_list.append(("", None, "", None))

        return preset_list

    def set_preset(self, processor, preset, preload=False):
        if not preset[0]:
            return
        self.proc_cmd(f"preset {preset[0]}")
        return True

    def cmp_presets(self, preset1, preset2):
        try:
            if preset1[0] == preset2[0]:
                return True
            else:
                return False
        except:
            return False

    def is_preset_user(self, preset):
        return isinstance(preset[0], str) and preset[0].startswith(f"file://{self.my_data_dir}/presets/lv2/")

    def preset_exists(self, bank, preset_name):
        # TODO: This would be more robust using URI but that is created dynamically by save_preset()
        if not bank or bank[2] not in self.preset_info:
            return False
        try:
            for preset in self.preset_info[bank[2]]['presets']:
                if preset['label'] == preset_name:
                    return True
        except Exception as e:
            logging.error(e)
        return False

    def save_preset(self, bank, preset_name):
        if not bank:
            self.save_bank = ["", None, "None", None]
        else:
            self.save_bank = bank

        # Reset save_uri
        self.save_preset_uri = None
        # Send "save preset" command to jalv
        if self.save_bank[0]:
            cmd = f"save preset {self.save_bank[0]},{preset_name}"
        else:
            cmd = f"save preset {preset_name}"
        #logging.debug(f"SAVE PRESET COMMAND => {cmd}")
        self.proc_cmd(cmd)
        # Wait for save preset feedback
        i = 0
        while i < 20 and self.save_preset_uri == None:
            sleep(0.1)
            i += 1
        return self.save_preset_uri

    def add_preset(self, preset_uri, preset_name):
        logging.info(f"Add preset '{preset_name}' => {preset_uri}")
        # Add to cache
        try:
            # Add bank if needed
            if self.save_bank[2] not in self.preset_info:
                self.preset_info[self.save_bank[2]] = {
                    'bank_url': self.save_bank[0],
                    'presets': []
                }
            # Add preset
            if not self.preset_exists(self.save_bank, preset_name):
                self.preset_info[self.save_bank[2]]['presets'].append(
                    {'label': preset_name,
                     "url": preset_uri})
                # Save presets cache
                zynthian_lv2.save_plugin_presets_cache(self.plugin_name, self.preset_info)
                # If added, return true
                return True
        except Exception as e:
            logging.error(e)
        return False

    def delete_preset(self, bank, preset):
        if self.is_preset_user(preset):
            try:
                # Remove from LV2 ttl
                zynthian_engine_jalv.lv2_remove_preset(preset[0])
                # Remove from  cache
                for i, p in enumerate(self.preset_info[bank[2]]['presets']):
                    if p['url'] == preset[0]:
                        del self.preset_info[bank[2]]['presets'][i]
                        zynthian_lv2.save_plugin_presets_cache(self.plugin_name, self.preset_info)
                        break
            except Exception as e:
                logging.error(e)

        try:
            n = len(self.preset_info[bank[2]]['presets'])
            if n > 0:
                return n
        except Exception as e:
            pass
        zynthian_engine_jalv.lv2_remove_bank(bank)
        return 0

    def rename_preset(self, bank, preset, new_preset_name):
        if self.is_preset_user(preset):
            try:
                # Update LV2 ttl
                zynthian_engine_jalv.lv2_rename_preset(preset[0], new_preset_name)
                # Update cache
                for i, p in enumerate(self.preset_info[bank[2]]['presets']):
                    if p['url'] == preset[0]:
                        self.preset_info[bank[2]]['presets'][i]['label'] = new_preset_name
                        zynthian_lv2.save_plugin_presets_cache(self.plugin_name, self.preset_info)
                        break
            except Exception as e:
                logging.error(e)

    # ----------------------------------------------------------------------------
    # Controllers Managament
    # ----------------------------------------------------------------------------

    def get_lv2_controllers_dict(self):
        logging.info("Getting Controller List from LV2 Plugin ...")
        zctrls = {}
        for i, info in zynthian_lv2.get_plugin_ports(self.plugin_url).items():
            symbol = info['symbol']
            # logging.debug("Controller {} info =>\n{}!".format(symbol, info))
            try:
                display_priority = info['display_priority']
                if info['group_display_priority'] > 0:
                    display_priority += 1000000 * info['group_display_priority']
                # If there is points info ...
                if len(info['scale_points']) > 1:
                    labels = []
                    values = []
                    for p in info['scale_points']:
                        labels.append(p['label'])
                        values.append(p['value'])
                    zctrls[symbol] = zynthian_controller(self, symbol, {
                        'name': info['name'],
                        'group_symbol': info['group_symbol'],
                        'group_name': info['group_name'],
                        #'graph_path': info['index'],
                        'value': info['value'],
                        'labels': labels,
                        'ticks': values,
                        'value_default': info['value'],
                        'value_min': values[0],
                        'value_max': values[-1],
                        'is_toggle': info['is_toggled'],
                        'is_integer': info['is_integer'],
                        'is_logarithmic': False,
                        'is_path': False,
                        'path_file_types': None,
                        'not_on_gui': info['not_on_gui'],
                        'display_priority': display_priority
                    })

                # If it's a numeric controller ...
                elif info['is_integer']:
                    if info['is_toggled']:
                        if info['value'] == 0:
                            val = 'off'
                        else:
                            val = 'on'
                        zctrls[symbol] = zynthian_controller(self, symbol, {
                            'name': info['name'],
                            'group_symbol': info['group_symbol'],
                            'group_name': info['group_name'],
                            #'graph_path': info['index'],
                            'value': val,
                            'labels': ['off', 'on'],
                            'ticks': [int(info['range']['min']), int(info['range']['max'])],
                            'value_default': val,
                            'value_min': int(info['range']['min']),
                            'value_max': int(info['range']['max']),
                            'is_toggle': True,
                            'is_integer': True,
                            'is_logarithmic': False,
                            'is_path': False,
                            'path_file_types': None,
                            'not_on_gui': info['not_on_gui'],
                            'display_priority': display_priority
                        })
                    else:
                        zctrls[symbol] = zynthian_controller(self, symbol, {
                            'name': info['name'],
                            'group_symbol': info['group_symbol'],
                            'group_name': info['group_name'],
                            #'graph_path': info['index'],
                            'value': int(info['value']),
                            'value_default': int(info['value']),
                            'value_min': int(info['range']['min']),
                            'value_max': int(info['range']['max']),
                            'is_toggle': False,
                            'is_integer': True,
                            'is_logarithmic': info['is_logarithmic'],
                            'is_path': False,
                            'path_file_types': None,
                            'not_on_gui': info['not_on_gui'],
                            'display_priority': display_priority
                        })
                elif info['is_toggled']:
                    if info['value'] == 0:
                        val = 'off'
                    else:
                        val = 'on'
                    zctrls[symbol] = zynthian_controller(self, symbol, {
                        'name': info['name'],
                        'group_symbol': info['group_symbol'],
                        'group_name': info['group_name'],
                        #'graph_path': info['index'],
                        'value': val,
                        'labels': ['off', 'on'],
                        'ticks': [info['range']['min'], info['range']['max']],
                        'value_default': val,
                        'value_min': info['range']['min'],
                        'value_max': info['range']['max'],
                        'is_toggle': True,
                        'is_integer': False,
                        'is_logarithmic': False,
                        'is_path': False,
                        'path_file_types': None,
                        'not_on_gui': info['not_on_gui'],
                        'display_priority': display_priority
                    })
                elif info['is_path']:
                    zctrls[symbol] = zynthian_controller(self, symbol, {
                        'name': info['name'],
                        'group_symbol': info['group_symbol'],
                        'group_name': info['group_name'],
                        #'graph_path': info['index'],
                        'value': None,
                        'value_default': None,
                        'value_min': None,
                        'value_max': None,
                        'is_toggle': False,
                        'is_integer': False,
                        'is_logarithmic': False,
                        'is_path': True,
                        'path_file_types': info['path_file_types'],
                        'not_on_gui': info['not_on_gui'],
                        'display_priority': display_priority
                    })
                else:
                    zctrls[symbol] = zynthian_controller(self, symbol, {
                        'name': info['name'],
                        'group_symbol': info['group_symbol'],
                        'group_name': info['group_name'],
                        #'graph_path': info['index'],
                        'value': float(info['value']),
                        'value_default': float(info['value']),
                        'value_min': float(info['range']['min']),
                        'value_max': float(info['range']['max']),
                        'is_toggle': False,
                        'is_integer': False,
                        'is_logarithmic': info['is_logarithmic'],
                        'is_path': False,
                        'path_file_types': None,
                        'not_on_gui': info['not_on_gui'],
                        'display_priority': display_priority,
                        'envelope': info['envelope']
                    })

            # If control info is not OK
            except Exception as e:
                #logging.error(e)
                logging.exception(traceback.format_exc())

        # Sort by suggested display_priority => This is done in zynthian_engine!
        #new_index = sorted(zctrls, key=lambda x: zctrls[x].display_priority, reverse=True)
        #zctrls = {k: zctrls[k] for k in new_index}

        return zctrls

    def get_monitors_dict(self):
        self.proc_cmd("monitors")
        # Return current monitor values => No wait for the asynchronous response!
        return self.lv2_monitors_dict

    def get_controllers_dict(self, processor):
        # Get plugin static controllers
        zctrls = super().get_controllers_dict(processor)
        # Add plugin native controllers
        for zctrl in self.lv2_zctrl_dict.values():
            zctrl.set_options({"processor": processor})
        zctrls.update(self.lv2_zctrl_dict)
        return zctrls

    def send_controller_value(self, zctrl):
        if zctrl.midi_cc:
            try:
                lib_zyncore.zmop_send_ccontrol_change(zctrl.processor.chain.zmop_index,
                                                      zctrl.processor.midi_chan_engine,
                                                      zctrl.midi_cc,
                                                      zctrl.get_ctrl_midi_val())
            except Exception as e:
                logging.error(f"Can't send controller '{zctrl.symbol}' with CC{zctrl.midi_cc} to zmop {zctrl.processor.chain.zmop_index} => {e}")
        elif zctrl.graph_path is not None:
            if zctrl.is_path:
                #logging.debug("set %d %s" % (zctrl.graph_path, zctrl.value))
                self.proc_cmd("set %d %s" % (zctrl.graph_path, zctrl.value))
            else:
                self.proc_cmd("set %d %.6f" % (zctrl.graph_path, zctrl.value))
        else:
            if zctrl.is_path:
                #logging.debug("%s=%s" % (zctrl.symbol, zctrl.value))
                self.proc_cmd("%s=%s" % (zctrl.symbol, zctrl.value))
            else:
                self.proc_cmd("%s=%.6f" % (zctrl.symbol, zctrl.value))

    # ---------------------------------------------------------------------------
    # API methods
    # ---------------------------------------------------------------------------

    @classmethod
    def init_zynapi_instance(cls, eng_code):
        if cls.zynapi_instance and cls.zynapi_instance.nickname != eng_code:
            cls.zynapi_instance.stop()
            cls.zynapi_instance = None

        if not cls.zynapi_instance:
            cls.zynapi_instance = cls(eng_code, None, True)
        else:
            logging.debug(
                "\n\n********** REUSING INSTANCE for '{}'***********".format(eng_code))

    @classmethod
    def refresh_zynapi_instance(cls):
        if cls.zynapi_instance:
            zynthian_lv2.generate_presets_cache_workaround()
            zynthian_lv2.generate_plugin_presets_cache(
                cls.zynapi_instance.plugin_url)
            eng_code = cls.zynapi_instance.nickname
            cls.zynapi_instance.stop()
            cls.zynapi_instance = cls(eng_code, None, True)

    @classmethod
    def zynapi_get_banks(cls):
        banks = []
        for b in cls.zynapi_instance.get_bank_list():
            if b[2]:
                banks.append({
                    'text': b[2],
                    'name': b[2],
                    'fullpath': b[0],
                    'raw': b,
                    'readonly': False if not b[0] or b[0].startswith("file:///") else True
                })
        return banks

    @classmethod
    def zynapi_get_presets(cls, bank):
        presets = []
        for p in cls.zynapi_instance.get_preset_list(bank['raw']):
            if p[2]:
                presets.append({
                    'text': p[2],
                    'name': p[2],
                    'fullpath': p[0],
                    'raw': p,
                    'readonly': False if not p[0] or p[0].startswith("file:///") else True
                })
        return presets

    @classmethod
    def zynapi_rename_bank(cls, bank_path, new_bank_name):
        if bank_path.startswith("file:///"):
            cls.lv2_rename_bank(bank_path, new_bank_name)
            cls.refresh_zynapi_instance()
        else:
            raise Exception("Bank is read-only!")

    @classmethod
    def zynapi_remove_bank(cls, bank_path):
        if bank_path.startswith("file:///"):
            bundle_path, bank_name = os.path.split(bank_path)
            bundle_path = bundle_path[7:]
            shutil.rmtree(bundle_path)
            cls.refresh_zynapi_instance()
        else:
            raise Exception("Bank is read-only")

    @classmethod
    def zynapi_rename_preset(cls, preset_path, new_preset_name):
        if preset_path.startswith("file:///"):
            cls.lv2_rename_preset(preset_path, new_preset_name)
            cls.refresh_zynapi_instance()
        else:
            raise Exception("Preset is read-only!")

    @classmethod
    def zynapi_remove_preset(cls, preset_path):
        if preset_path.startswith("file:///"):
            cls.lv2_remove_preset(preset_path)
            cls.refresh_zynapi_instance()
        else:
            raise Exception("Preset is read-only")

    @classmethod
    def zynapi_download(cls, fullpath):
        if fullpath.startswith("file:///"):
            bundle_path, bank_name = os.path.split(fullpath)
            bundle_path = bundle_path[7:]
            return bundle_path
        else:
            raise Exception("Bank is not downloadable!")

    @classmethod
    def zynapi_install(cls, dpath, bank_path):
        fname, ext = os.path.splitext(dpath)
        native_ext = cls.zynapi_get_native_ext()

        # Try to copy LV2 bundles ...
        if os.path.isdir(dpath):
            # Find manifest.ttl
            manifest_files = check_output(f"find \"{dpath}\" -type f -iname manifest.ttl",
                                          shell=True).decode("utf-8").split("\n")
            # Copy LV2 bundle directories to destiny ...
            count = 0
            for f in manifest_files:
                bpath, fname = os.path.split(f)
                head, bname = os.path.split(bpath)
                if bname:
                    shutil.rmtree(zynthian_engine.my_data_dir +"/presets/lv2/" + bname, ignore_errors=True)
                    shutil.move(bpath, zynthian_engine.my_data_dir + "/presets/lv2/")
                    count += 1
            if count > 0:
                cls.refresh_zynapi_instance()
                return

        # Else, try to convert from native format ...
        if os.path.isdir(dpath) or ext[1:].lower() == native_ext:
            preset2lv2_cmd = "cd /tmp; preset2lv2 {} \"{}\"".format(
                cls.zynapi_get_preset2lv2_format(), dpath)
            try:
                res = check_output(preset2lv2_cmd, stderr=STDOUT, shell=True).decode("utf-8")
                for bname in re.compile("Bundle '(.*)' generated").findall(res):
                    bpath = "/tmp/" + bname
                    logging.debug("Copying LV2-Bundle '{}' ...".format(bpath))
                    shutil.rmtree(zynthian_engine.my_data_dir + "/presets/lv2/" + bname, ignore_errors=True)
                    shutil.move(bpath, zynthian_engine.my_data_dir + "/presets/lv2/")
                cls.refresh_zynapi_instance()
            except Exception as e:
                raise Exception(
                    "Conversion from {} to LV2 failed! => {}".format(native_ext, e))
        else:
            raise Exception("Unknown preset format: {}".format(native_ext))

    @classmethod
    def zynapi_get_formats(cls):
        formats = "zip,tgz,tar.gz,tar.bz2,tar.xz"
        fmt = cls.zynapi_get_native_ext()
        if fmt:
            formats = fmt + "," + formats
        return formats

    @classmethod
    def zynapi_martifact_formats(cls):
        fmt = cls.zynapi_get_native_ext()
        if fmt:
            return fmt
        else:
            return "lv2"

    @classmethod
    def zynapi_get_native_ext(cls):
        try:
            return cls.plugin2native_ext[cls.zynapi_instance.plugin_name]
        except:
            return None

    @classmethod
    def zynapi_get_preset2lv2_format(cls):
        try:
            return cls.plugin2preset2lv2_format[cls.zynapi_instance.plugin_name]
        except:
            return None

    # --------------------------------------------------------------------------
    # LV2 Bundle TTL file manipulations
    # --------------------------------------------------------------------------

    @staticmethod
    def ttl_read_parts(fpath):
        with open(fpath, 'r') as f:
            data = f.read()
            parts = data.split(".\n")
        return parts

    @staticmethod
    def ttl_write_parts(fpath, parts):
        with open(fpath, 'w') as f:
            data = ".\n".join(parts)
            f.write(data)
            # logging.debug(data)

    @staticmethod
    def lv2_rename_bank(bank_path, new_bank_name):
        bank_path = bank_path[7:]
        bundle_path, bank_dname = os.path.split(bank_path)

        man_fpath = bundle_path + "/manifest.ttl"
        parts = zynthian_engine_jalv.ttl_read_parts(man_fpath)

        bmre1 = re.compile(r"<{}>".format(bank_dname))
        bmre2 = re.compile(r"(.*)a pset:Bank ;")
        brre = re.compile(r"([\s]+rdfs:label[\s]+\").*(\" )")
        for i, p in enumerate(parts):
            if bmre1.search(p) and bmre2.search(p):
                new_bank_name = zynthian_engine_jalv.sanitize_text(new_bank_name)
                parts[i] = brre.sub(lambda m: m.group(1)+new_bank_name+m.group(2), p)
                zynthian_engine_jalv.ttl_write_parts(man_fpath, parts)
                return

        raise Exception("Format doesn't match!")

    @staticmethod
    def lv2_rename_preset(preset_path, new_preset_name):
        preset_path = preset_path[7:]
        bundle_path, preset_fname = os.path.split(preset_path)

        man_fpath = bundle_path + "/manifest.ttl"
        man_parts = zynthian_engine_jalv.ttl_read_parts(man_fpath)
        prs_parts = zynthian_engine_jalv.ttl_read_parts(preset_path)

        bmre1 = re.compile(r"<{}>".format(preset_fname))
        bmre2 = re.compile(r"(.*)a pset:Preset ;")
        brre = re.compile("([\s]+rdfs:label[\s]+\").*(\" )")

        renamed = False
        for i, p in enumerate(man_parts):
            if bmre1.search(p) and bmre2.search(p):
                new_preset_name = zynthian_engine_jalv.sanitize_text(new_preset_name)
                man_parts[i] = brre.sub(lambda m: m.group(1) + new_preset_name + m.group(2), p)
                zynthian_engine_jalv.ttl_write_parts(man_fpath, man_parts)
                renamed = True  # TODO: This overrides subsequent assertion in prs_parts
                break

        for i, p in enumerate(prs_parts):
            if bmre2.search(p):
                # new_preset_name = zynthian_engine_jalv.sanitize_text(new_preset_name)
                prs_parts[i] = brre.sub(lambda m: m.group(1) + new_preset_name + m.group(2), p)
                zynthian_engine_jalv.ttl_write_parts(preset_path, prs_parts)
                renamed = True
                break

        if not renamed:
            raise Exception("Format doesn't match!")

    @staticmethod
    def lv2_remove_preset(preset_path):
        logging.debug(f"Removing LV2 preset '{preset_path}'")
        preset_path = preset_path[7:]
        bundle_path, preset_fname = os.path.split(preset_path)

        man_fpath = bundle_path + "/manifest.ttl"
        parts = zynthian_engine_jalv.ttl_read_parts(man_fpath)

        bmre1 = re.compile(r"<{}>".format(preset_fname))
        bmre2 = re.compile(r"(.*)a pset:Preset ;")
        for i, p in enumerate(parts):
            if bmre1.search(p) and bmre2.search(p):
                del parts[i]
                zynthian_engine_jalv.ttl_write_parts(man_fpath, parts)
                os.remove(preset_path)
                return True
        return False

    @staticmethod
    #   Remove a preset bank
    #   bank: Bank object to remove
    #   Returns: True on success
    def lv2_remove_bank(bank):
        logging.debug(f"Removing LV2 bank '{bank[0]}'")
        try:
            path = bank[0][7:bank[0].rfind("/")]
        except Exception as e:
            return False

        try:
            with open("{}/manifest.ttl".format(path), "r") as manifest:
                lines = manifest.readlines()
        except Exception as e:
            return False

        bank_first_line = None
        bank_last_line = None
        for index, line in enumerate(lines):  # TODO: Use regexp to parse file
            if line.strip() == "<{}>".format(bank[2]):
                bank_first_line = index
            if bank_first_line is not None and line.strip()[-1:] == ".":
                bank_last_line = index
            if bank_last_line is not None:
                del lines[bank_first_line:bank_last_line + 1]
                break
        zynthian_engine.remove_double_spacing(lines)
        try:
            with open("{}/manifest.ttl".format(path), "w") as manifest:
                manifest.writelines(lines)
        except Exception as e:
            logging.error(e)

        # Remove bank reference from presets
        for file in os.listdir(path):
            if file[-4:] == ".ttl" and file != "manifest.ttl":
                bank_lines = []
                with open("{}/{}".format(path, file)) as ttl:
                    lines = ttl.readlines()
                for index, line in enumerate(lines):
                    if line.strip().startswith("pset:bank") and line.find("<{}>".format(bank[2])) > 0:
                        bank_lines.append(index)
                if len(bank_lines):
                    bank_lines.sort(reverse=True)
                    for line in bank_lines:
                        del lines[line]
                    zynthian_engine.remove_double_spacing(lines)
                    with open("{}/{}".format(path, file), "w") as ttl:
                        ttl.writelines(lines)

        return True

    @staticmethod
    def sanitize_text(text):
        # Remove bad chars
        bad_chars = ['.', ',', ';', ':', '!', '*', '+', '?', '@', '&', '$', '%', '=',
                     '"', '\'', '`', '/', '\\', '^', '<', '>', '[', ']', '(', ')', '{', '}']
        for i in bad_chars:
            text = text.replace(i, ' ')

        # Strip and replace (multi)spaces by single underscore
        text = '_'.join(text.split())
        text = '_'.join(filter(None, text.split('_')))

        return text

# ******************************************************************************
