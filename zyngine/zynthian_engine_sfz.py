# -*- coding: utf-8 -*-
# ******************************************************************************
# ZYNTHIAN PROJECT: Zynthian Engine extensions for SFZ management
#
# zynthian_engine extensions for SFZ nanagement
#
# Copyright (C) 2015-2025 Fernando Moyano <jofemodo@zynthian.org>
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

import re
import logging
import oyaml as yaml

from zyncoder.zyncore import lib_zyncore
from . import zynthian_engine

# ------------------------------------------------------------------------------
# SFZ extensions class
# ------------------------------------------------------------------------------


class zynthian_engine_sfz(zynthian_engine):

    # ---------------------------------------------------------------------------
    # Controllers & Screens
    # ---------------------------------------------------------------------------

    # SFZ Default MIDI Controllers (modulators)
    default_ctrls = [
        ['volume', 7, 96],
        ['pan', 10, 64],
        #['modulation wheel', 1, 0],
        # ['breath', 2, 127],

        ['sustain', 64, 'off', ['off', 'on']],
        ['sostenuto', 66, 'off', ['off', 'on']],
        ['expression', 11, 127],
        #['legato', 68, 'off', ['off', 'on']],

        #['portamento on/off', 65, 'off', ['off', 'on']],
        #['portamento time-coarse', 5, 0],
        #['portamento time-fine', 37, 0],

        # ['expr. pedal', 4, 127],
        #['filter cutoff', 74, 64],
        #['filter resonance', 71, 64],
        #['env. attack', {'value': 64, 'midi_cc': 73, 'envelope': 'attack'}],
        #['env. release', {'value': 64, 'midi_cc': 72, 'envelope': 'release'}]
    ]

    # Controller Screens
    default_ctrl_screens = [
        ['main', ['volume', 'pan']],
        ['pedals', ['sostenuto', 'sustain', 'expression']],
        #['portamento', ['portamento on/off', 'portamento time-coarse', 'portamento time-fine']],
        #['envelope/filter', ['env. attack', 'env. release', 'filter cutoff', 'filter resonance']]
    ]

    # ---------------------------------------------------------------------------
    # Initialization
    # ---------------------------------------------------------------------------

    def __init__(self, state_manager=None):
       super().__init__(state_manager)
       self.custom_ctrls = []
       self.custom_ctrl_screens = []

    # ---------------------------------------------------------------------------
    # Controllers Management
    # ---------------------------------------------------------------------------

    def get_controllers_dict(self, processor):
        self._ctrls = self.default_ctrls + self.custom_ctrls
        self._ctrl_screens = self.default_ctrl_screens + self.custom_ctrl_screens
        return super().get_controllers_dict(processor)

    def parse_sfz_controllers(self, sfzpath):
        self.custom_ctrls = []
        self.custom_ctrl_screens = []

        try:
            with open(sfzpath, "r") as fh:
                sfz = fh.read()
                # logging.debug(f"Loaded SFZ file {sfzpath} =>\n{sfz}")
        except Exception as e:
            logging.error(f"Can't load SFZ file '{sfzpath}' => {e}")
            return False

        cc_config = {}
        pat1 = re.compile("^set_cc(\d+)=(\d+)", re.MULTILINE)
        pat2 = re.compile("^label_cc(\d+)=(\w+)", re.MULTILINE)
        for m in pat1.finditer(sfz):
            try:
                cc_config[int(m[1])] = ["", int(m[2])]
            except:
                pass
        for m in pat2.finditer(sfz):
            try:
                cc_config[int(m[1])][0] = m[2]
            except:
                cc_config[m[1]] = [m[2], None]
        logging.debug(f"CC Config => \n{cc_config}")

        ctrl_group = []
        for num, conf in cc_config.items():
            name = conf[0]
            if name:
                try:
                    val = int(conf[1])
                except:
                    val = 0
                self.custom_ctrls.append([name, num, val])
                ctrl_group.append(name)
                if len(ctrl_group) == 4:
                    screen_title = f"custom #{len(self.custom_ctrl_screens) + 1}"
                    self.custom_ctrl_screens.append([screen_title, ctrl_group])
                    ctrl_group = []
        if len(ctrl_group) > 0:
            screen_title = f"custom #{len(self.custom_ctrl_screens) + 1}"
            self.custom_ctrl_screens.append([screen_title, ctrl_group])
        return True

    def load_sfz_config(self, sfzpath):
        # Try to load YAML config file ...
        res = self.load_controllers_config(sfzpath[:-3] + "yml")
        # If not, try to parse controllers from SFZ file
        if not res:
            res = self.parse_sfz_controllers(sfzpath)
        return res

    def load_controllers_config(self, fpath):
        self.custom_ctrls = []
        self.custom_ctrl_screens = []

        try:
            fh = open(fpath, "r")
        except:
            logging.info(f"Can't open yaml config file '{fpath}'")
            return False
        try:
            data = fh.read()
            logging.info(f"Loading yaml config file '{fpath}' =>\n{data}")
            config = yaml.load(data, Loader=yaml.SafeLoader)
        except Exception as e:
            logging.error(f"Bad formatted yaml in config file '{fpath}' => {e}")
            return False

        try:
            for screen_title, ctrls in config["controllers"].items():
                for ctrl_name, ctrl_options in ctrls.items():
                    self.custom_ctrls.append([ctrl_name, ctrl_options])
                self.custom_ctrl_screens.append([screen_title, list(ctrls.keys())])
        except Exception as e:
            logging.error(f"Wrong config data in yaml file '{fpath}' => {e}")

        return True

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
            if zctrl.graph_path == "note_on":
                try:
                    lib_zyncore.zmop_send_note_on(zctrl.processor.chain.zmop_index,
                                                  zctrl.processor.midi_chan_engine,
                                                  zctrl.value, 1)
                except Exception as e:
                    logging.error(f"Can't send note-on '{zctrl.value}' from keyswitch controller '{zctrl.symbol}' to zmop {zctrl.processor.chain.zmop_index} => {e}")


# ******************************************************************************
