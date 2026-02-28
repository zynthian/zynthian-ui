# -*- coding: utf-8 -*-
# ******************************************************************************
# ZYNTHIAN PROJECT: Zynthian Engine (zynthian_engine_sfizz)
#
# zynthian_engine implementation for Sfizz
#
# Copyright (C) 2015-2026 Fernando Moyano <jofemodo@zynthian.org>
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
import glob
import shutil
import logging
from subprocess import check_output
import yaml
from pathlib import Path

from zyngine.zynthian_engine_sfz import zynthian_engine_sfz
SFIZZ_YAML_URL = "https://raw.githubusercontent.com/sfztools/sfztools.github.io/refs/heads/master/data/sfizz/support.yml"
SFIZZ_SUPPORTED = "/zynthian/config/sfizz_supported.yml"

# ------------------------------------------------------------------------------
# Sfizz Engine Class
# ------------------------------------------------------------------------------


class zynthian_engine_sfizz(zynthian_engine_sfz):

    # ---------------------------------------------------------------------------
    # Config variables
    # ---------------------------------------------------------------------------

    preset_fexts = ["sfz", "dspreset"]
    root_bank_dirs = [
        ('User', zynthian_engine_sfz.my_data_dir + "/soundfonts/sfz"),
        ('System', zynthian_engine_sfz.data_dir + "/soundfonts/sfz")
    ]

    # ---------------------------------------------------------------------------
    # Initialization
    # ---------------------------------------------------------------------------

    def __init__(self, state_manager=None, jackname=None):
        super().__init__(state_manager)
        self.name = "Sfizz"
        self.nickname = "SF"
        if jackname:
            self.jackname = jackname
        else:
            self.jackname = self.state_manager.chain_manager.get_next_jackname("sfizz")

        self.sfzpath = None

        pi_version = int(os.environ.get("RBPI_VERSION_NUMBER", "4"))
        if pi_version >= 5:
            self.num_voices = 64
            self.preload_size = 8192  # 8192, 16384, 32768, 65536
        elif pi_version == 4:
            self.num_voices = 48
            self.preload_size = 16384  # 8192, 16384, 32768, 65536
        else:
            self.num_voices = 32
            self.preload_size = 32768  # 8192, 16384, 32768, 65536


        self.command = f"sfizz_jack --client_name '{self.jackname}' --preload_size {self.preload_size} --num_voices {self.num_voices}"
        self.command_prompt = "> "

        self.reset()
        self.start()

    # ---------------------------------------------------------------------------
    # Subproccess Management & IPC
    # ---------------------------------------------------------------------------

    def stop(self):
        try:
            self.proc.sendline("quit")
            self.proc.expect("Closing...")
        except:
            super().stop()

    # ---------------------------------------------------------------------------
    # Bank Management
    # ---------------------------------------------------------------------------

    def get_bank_list(self, processor=None):
        return self.get_bank_dirlist(recursion=2)

    def set_bank(self, processor, bank):
        return True

    # ---------------------------------------------------------------------------
    # Preset Management
    # ---------------------------------------------------------------------------

    @classmethod
    def _get_preset_list(cls, bank):
        logging.info("Getting Preset List for %s" % bank[2])
        i = 0
        preset_list = []
        preset_dpath = bank[0]
        if os.path.isdir(preset_dpath):
            exclude_sfz = re.compile(r"[MOPRSTV][1-9]?l?\.sfz")
            for sd in glob.iglob(preset_dpath + "/*"):
                if os.path.isdir(sd):
                    flist = cls.find_all_preset_files(sd, cls.preset_fexts, recursion=0)
                    for f in flist:
                        filehead, filetail = os.path.split(f)
                        if not exclude_sfz.fullmatch(filetail):
                            filename, filext = os.path.splitext(f)
                            filename = filename[len(preset_dpath)+1:]
                            if len(flist) == 1:
                                dirname = filehead.split("/")[-1]
                                if dirname[-4:].lower() == ".sfz":
                                    dirname = dirname[:-4]
                                title = dirname.replace('_', ' ')
                            else:
                                title = filename.replace('_', ' ')
                            engine = filext[1:].lower()
                            preset_list.append([f, i, title, engine, "{}{}".format(filename, filext)])
                            i += 1
                else:
                    f = sd
                    filehead, filetail = os.path.split(f)
                    filename, filext = os.path.splitext(f)
                    if filext.lower() == ".sfz" and not exclude_sfz.fullmatch(filetail):
                        filename = filename[len(preset_dpath) + 1:]
                        title = filename.replace('_', ' ')
                        engine = filext[1:].lower()
                        preset_list.append([f, i, title, engine, "{}{}".format(filename, filext)])
                        i += 1

        preset_list.sort(key=lambda x:x[2].casefold())
        return preset_list

    def get_preset_list(self, bank, processor=None):
        return self._get_preset_list(bank)

    def set_preset(self, processor, preset, preload=False):
        try:
            self.sfzpath = preset[0]
            res = self.proc_cmd(f"load_instrument \"{self.sfzpath}\"")
            logging.debug(res)
            if "Instrument loaded" in res:
                self.load_sfz_config(self.sfzpath)
                processor.refresh_controllers()
                # processor.send_ctrl_midi_cc()
                return True
        except Exception as e:
            logging.error(e)
        return False

    def cmp_presets(self, preset1, preset2):
        try:
            if preset1[0] == preset2[0] and preset1[3] == preset2[3]:
                return True
            else:
                return False
        except:
            return False

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
        for p in cls._get_preset_list(bank['raw']):
            head, tail = os.path.split(p[2])
            presets.append({
                'text': p[4],
                'name': tail,
                'fullpath': p[0],
                'raw': p,
                'readonly': False
            })
        return presets

    @classmethod
    def zynapi_new_bank(cls, bank_name):
        if bank_name.lower().startswith("sfz/"):
            bank_type = "sfz"
            bank_name = bank_name[4:]
        else:
            bank_type = "sfz"
        os.mkdir(zynthian_engine.my_data_dir +
                 "/soundfonts/{}/{}".format(bank_type, bank_name))

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
        fname, ext = os.path.splitext(tail)
        new_preset_path = head + "/" + new_preset_name + ext
        os.rename(preset_path, new_preset_path)

    @classmethod
    def zynapi_remove_preset(cls, preset_path):
        os.remove(preset_path)
        # TODO => If last preset in SFZ dir, delete it too!

    @classmethod
    def zynapi_download(cls, fullpath):
        fname, ext = os.path.splitext(fullpath)
        if ext and ext[0] == '.':
            head, tail = os.path.split(fullpath)
            return head
        else:
            return fullpath

    @classmethod
    def zynapi_install(cls, dpath, bank_path):
        # TODO: Test that bank_path fits preset type (sfz)
        if not os.path.isdir(bank_path):
            raise Exception("Destiny is not a directory!")
        if os.path.isdir(dpath):
            # Locate sfz files and move all them to first level directory
            try:
                cmd = f"find \"{dpath}\" -type f -iname *.sfz"
                sfz_files = check_output(
                    cmd, shell=True).decode("utf-8").split("\n")
                # Find the "shallower" SFZ file
                shallower_sfz_file = sfz_files[0]
                shallower_sfz_deep = shallower_sfz_file.count('/')
                for f in sfz_files:
                    deep = f.count('/')
                    if f and deep < shallower_sfz_deep:
                        shallower_sfz_file = f
                        shallower_sfz_deep = deep
                head, tail = os.path.split(shallower_sfz_file)
                logging.debug(f"Shallower SFZ => {head} / {tail}")
                # Move SFZ stuff to the top level
                if head and head != dpath:
                    for f in glob.glob(head + "/*"):
                        shutil.move(f, dpath)
                    shutil.rmtree(head)
            except Exception as e:
                raise Exception(f"Directory doesn't contain any SFZ file")

            if "/sfz/" in bank_path:
                shutil.move(dpath, bank_path)
            else:
                raise Exception("Destiny is not a SFZ bank!")
        else:
            raise Exception("Doesn't look like a SFZ soundfont")

    @classmethod
    def zynapi_get_formats(cls):
        return "zip,tgz,tar.gz,tar.bz2,tar.xz,7z"

    @classmethod
    def zynapi_martifact_formats(cls):
        return "sfz"

    @classmethod
    def get_supported_opcode_patterns(cls, download=False):
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
    
    @classmethod
    def get_used_codes(cls, filename):
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

    @classmethod
    def get_all_sfz(cls, path):
        """ Get a list of all sfz files within a directory branch (recurssive)
        Args:
            path: Path of directory to search
        Returns: List of sfz files
        """

        return list(Path(path).rglob("*.sfz"))

    @classmethod
    def is_opcode_supported(cls, opcode, patterns):
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

    @classmethod
    def get_unsupported_opcodes(cls, filename, patterns):
        """ Get list of unsupported opcodes used by sfz
        Args:
            filename: Full path of sfz file
            patterns: List of regex patterns describing supported opcodes (see get_supported_opcode_patterns)
        Returns: List of unsupported opcodes
        """

        unsupported = []
        for opcode in zynthian_engine_sfizz.get_used_codes(filename)["opcodes"]:
            if not zynthian_engine_sfizz.is_opcode_supported(opcode, patterns):
                unsupported.append(opcode)
        return unsupported



# ******************************************************************************
