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
import os.path
import logging
import oyaml as yaml

from zyncoder.zyncore import lib_zyncore
from zyngine.zynthian_engine import zynthian_engine

#SFIZZ_YAML_URL = "https://raw.githubusercontent.com/sfztools/sfztools.github.io/refs/heads/master/data/sfizz/support.yml"
#SFIZZ_SUPPORTED = "/zynthian/config/sfizz_supported.yml"

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
        #['breath', 2, 127],

        #['expression', 11, 127],
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
        #['portamento', ['portamento on/off', 'portamento time-coarse', 'portamento time-fine']],
        #['envelope/filter', ['env. attack', 'env. release', 'filter cutoff', 'filter resonance']]
    ]

    # ---------------------------------------------------------------------------
    # Initialization
    # ---------------------------------------------------------------------------

    def __init__(self, state_manager=None):
       super().__init__(state_manager)
       self.keymap = None
       self.custom_ctrls = []
       self.custom_ctrl_screens = []

    # ---------------------------------------------------------------------------
    # Preset preload
    # ---------------------------------------------------------------------------

    def allow_timer_preload(self, preset_data):
        # TODO Calculate the size of the soundfont to determine how to preload
        return False

    # ---------------------------------------------------------------------------
    # Controllers Management
    # ---------------------------------------------------------------------------

    def get_controllers_dict(self, processor):
        logging.debug(f"Custom Controllers => \n{self.custom_ctrls}")
        logging.debug(f"Custom Controller Screens => \n{self.custom_ctrl_screens}")
        # Generate default controller list, removing CCs redefined in custom controllers
        self._ctrls = []
        ctrl_names = []
        for ctrl in self.default_ctrls:
            include = True
            for cctrl in self.custom_ctrls:
                if isinstance(cctrl[1], int) and ctrl[1] == cctrl[1]:
                    include = False
                    break
                elif isinstance(cctrl[1], dict):
                    try:
                        if ctrl[1] == cctrl[1]["midi_cc"]:
                            include = False
                            break
                    except:
                        pass
            if include:
                self._ctrls.append(ctrl)
                ctrl_names.append(ctrl[0])
        self._ctrl_screens = []
        # Generate default screen list, removing CCs redefined in custom screens
        for scr in self.default_ctrl_screens:
            ctrl_group = []
            for cname in scr[1]:
                if cname in ctrl_names:
                    ctrl_group.append(cname)
            if ctrl_group:
                self._ctrl_screens.append([scr[0], ctrl_group])
        # Join controllers & screens in a single list
        self._ctrls += self.custom_ctrls
        self._ctrl_screens += self.custom_ctrl_screens
        return super().get_controllers_dict(processor)

    def parse_sfz_controllers(self, sfzpath):
        self.custom_ctrls = []
        self.custom_ctrl_screens = []

        try:
            with open(sfzpath, "r") as fh:
                sfz_text = fh.read()
                # logging.debug(f"Loaded SFZ file {sfzpath} =>\n{sfz}")
        except Exception as e:
            logging.error(f"Can't load SFZ file '{sfzpath}' => {e}")
            return False

        # Compile all regex patterns (Case-Insensitive)
        label_pattern = re.compile(r'\blabel_cc(\d{1,3})\s*=\s*([^=\r\n]+)', re.I)
        value_pattern = re.compile(r'\bset_(hd)?cc(\d{1,3})\s*=\s*(-?\d+(?:\.\d+)?)', re.I)
        dynamic_pattern = re.compile(r'\b[a-zA-Z0-9_]+_(?:hd)?cc(\d{1,3})\s*=', re.I)

        # Internal tracking storage
        cc_labels = {}
        cc_values = {}
        all_discovered_ccs = set()

        # Pass 1: Parse explicit labels, values, and harvest initial CCs
        for match in label_pattern.finditer(sfz_text):
            cc_num = int(match.group(1))
            if 0 <= cc_num <= 127:
                cc_labels[cc_num] = match.group(2).strip()
                all_discovered_ccs.add(cc_num)

        for match in value_pattern.finditer(sfz_text):
            cc_num = int(match.group(2))
            if 0 <= cc_num <= 127:
                # Parse as float if a decimal point is present, otherwise integer
                val_str = match.group(3)
                cc_values[cc_num] = float(val_str) if '.' in val_str else int(val_str)
                all_discovered_ccs.add(cc_num)

        # Pass 2: Harvest CC numbers hidden inside dynamic control opcodes
        for match in dynamic_pattern.finditer(sfz_text):
            cc_num = int(match.group(1))
            if 0 <= cc_num <= 127:
                all_discovered_ccs.add(cc_num)

        # Construct the final dictionary output ordered by CC number
        cc_config = {}
        for cc in sorted(list(all_discovered_ccs)):
            # 1. Fetch raw label or apply the default fallback rule
            title = cc_labels.get(cc, None)

            if title:
                # Title Sanitization: Clean up comments and erratic spacing
                # Cut off the string if there is an inline comment (// or #)
                # Strip trailing/leading spaces, tabs, and newlines
                title = re.split(r'//|#', title)[0].strip()
            else:
                title = f"cc {cc}"

            # Apply value fallback rule
            value = cc_values.get(cc, 0)
            cc_config[cc] = (title, value)

        #logging.debug(f"Parsed CCs => \n{cc_config}")

        ctrl_group = []
        for num, conf in cc_config.items():
            name = conf[0]
            if name:
                try:
                    val = int(conf[1])
                except:
                    val = 0
                self.custom_ctrls.append([name, int(num), val])
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
        # Try to load YAML config files ...
        res = self.load_controllers_config(sfzpath[:-3] + "yml")
        # If not, try to parse controllers from SFZ file
        if not res:
            res = self.parse_sfz_controllers(sfzpath)
        return res

    def load_controllers_config(self, fpath):
        self.custom_ctrls = []
        self.custom_ctrl_screens = []

        # Load SFZ specific config
        config = self.load_yaml_config(fpath)
        # Load SFZ common config
        cconfig = self.load_yaml_config(os.path.dirname(fpath) + "/common.yml")
        if not config:
            config = cconfig
        elif cconfig:
            # Merge common config into specific config without duplicating elements
            for scr_name, scr_data in cconfig["controllers"].items():
                if scr_name in config["controllers"]:
                    for ctrl_name, ctrl_data in scr_data.items():
                        if ctrl_name not in config["controllers"][scr_name]:
                            config["controllers"][scr_name][ctrl_name] = ctrl_data
                else:
                    config["controllers"][scr_name] = scr_data
            # Keymap config
            if "keymap" not in config and "keymap" in cconfig:
                config["keymap"] = cconfig["keymap"]

        if not config:
            return False

        # Get keymap config
        try:
            self.keymap = config["keymap"]
        except:
            self.keymap = None

        # Generate controller & screen list
        try:
            for screen_title, ctrls in config["controllers"].items():
                for ctrl_name, ctrl_options in ctrls.items():
                    self.custom_ctrls.append([ctrl_name, ctrl_options])
                self.custom_ctrl_screens.append([screen_title, list(ctrls.keys())])
        except Exception as e:
            logging.error(f"Wrong config data in yaml file '{fpath}' => {e}")
            return False

        return True

    def load_yaml_config(self, fpath):
        try:
            fh = open(fpath, "r")
        except:
            logging.debug(f"Yaml config file '{fpath}' not found")
            return {}
        try:
            data = fh.read()
            #logging.debug(f"Loading yaml config file '{fpath}' =>\n{data}")
            return yaml.load(data, Loader=yaml.SafeLoader)
        except Exception as e:
            logging.error(f"Bad formatted yaml in config file '{fpath}' => {e}")
            return {}

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

    #-------------------------------------------------------------------------
    # Opcode parsing and support detection
    #-------------------------------------------------------------------------

    ''' Not used currently!

    @staticmethod
    def get_supported_opcode_patterns(download=False):
        """ Get list of regex patterns describing sfizz supported sfz codes
        Args:
            download: True to download latest support yaml file
        Returns: List of regex patterns describing supported opcodes
        """

        patterns = []
        if download and os.system(f"wget -N -O {SFIZZ_SUPPORTED} {SFIZZ_YAML_URL} > /dev/null 2>&1") != 0:
            return patterns

        try:
            with open(SFIZZ_SUPPORTED, "r") as f:
                data = yaml.safe_load(f)
        except:
            return patterns
        if not data:
            return patterns

        opcodes = data.get("opcodes", [])
        for cat in data['categories']:
            opcodes += cat.get('opcodes', [])
        for op in opcodes:
            if "support" in op:
                continue
            name = op.get("name")
            if not name:
                continue
            escaped = re.escape(name)
            escaped = re.sub(r"[A-Z]", r"\\d+", escaped)
            patterns.append(re.compile(f"^{escaped}$"))
        return patterns

    @staticmethod
    def get_used_codes(filename):
        """Extract headers and opcodes from a .sfz file
        Args:
            filename: Full path of sfz file
        Returns: Dict of headers and opcodes used by sfz
        """

        used = {"headers": set(), "opcodes": set()}
        with open(filename, "r", encoding="utf-8") as f:
            for line in f:
                line = re.sub(r"//.*", "", line)
                line = re.sub(r"/\*.*?\*/", "", line)
                headers = re.findall(r"<[^>]+>", line)
                used["headers"].update(headers)
                matches = re.findall(r"([A-Za-z0-9_]+)\s*=", line)
                used["opcodes"].update(matches)
        return used

    @staticmethod
    def get_all_sfz(path):
        """ Get a list of all sfz files within a directory branch (recurssive)
        Args:
            path: Path of directory to search
        Returns: List of sfz files
        """

        return list(Path(path).rglob("*.sfz"))

    @staticmethod
    def is_opcode_supported(opcode, patterns):
        """ Check if opcode matches any supported pattern
        Args:
            opcode: Opcode to validate
            patterns: List of regexp patterns used to validate
        Returns: True if valid opcode
        """

        for pattern in patterns:
            if pattern.match(opcode):
                return True
        return False

    @staticmethod
    def get_unsupported_opcodes(filename, patterns):
        """ Get list of unsupported opcodes used by sfz
        Args:
            filename: Full path of sfz file
            patterns: List of regex patterns describing supported opcodes (see get_supported_opcode_patterns)
        Returns: List of unsupported opcodes
        """

        unsupported = []
        for opcode in zynthian_engine_sfz.get_used_codes(filename)["opcodes"]:
            if not zynthian_engine_sfz.is_opcode_supported(opcode, patterns):
                unsupported.append(opcode)
        return unsupported

    '''

# ******************************************************************************
