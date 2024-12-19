# -*- coding: utf-8 -*-
# ******************************************************************************
# ZYNTHIAN PROJECT: Zynthian Engine (zynthian_engine_zynaddsubfx)
#
# zynthian_engine implementation for ZynAddSubFX Synthesizer
#
# Copyright (C) 2015-2023 Fernando Moyano <jofemodo@zynthian.org>
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
import shutil
import logging
from time import sleep
from string import Template
from os.path import isfile, join
from subprocess import check_output

from . import zynthian_engine
from zynconf import ServerPort
from zyncoder.zyncore import lib_zyncore

# ------------------------------------------------------------------------------
# ZynAddSubFX Engine Class
# ------------------------------------------------------------------------------


class zynthian_engine_zynaddsubfx(zynthian_engine):

    # ---------------------------------------------------------------------------
    # Controllers & Screens
    # ---------------------------------------------------------------------------

    bend_ticks = [[str(x) for x in range(-64, 64)],
                  [x for x in range(-6400, 6400, 100)]]

    # MIDI Controllers
    _ctrls = [
        #['volume', 7, 115],
        # ['panning', 10, 64],
        # ['expression', 11, 127],
        ['volume', '/part$i/Pvolume', 96, 127, {'midi_cc': 7}],
        ['panning', '/part$i/Ppanning', 64],
        ['filter cutoff', 74, 64],
        ['filter resonance', 71, 64],

        ['voice limit', '/part$i/Pvoicelimit', 0, 60],
        ['drum mode', '/part$i/Pdrummode', 'off', 'off|on'],
        ['sustain', 64, 'off', 'off|on'],
        ['assign mode', '/part$i/polyType', 'poly',
         [['poly', 'mono', 'legato', 'latch'], [0, 1, 2, 3]]],

        # ['portamento on/off', 65, 'off', 'off|on'],
        ['portamento enable', '/part$i/ctl/portamento.portamento', 'off', 'off|on'],
        ['portamento auto', '/part$i/ctl/portamento.automode', 'on', 'off|on'],
        ['portamento receive', '/part$i/ctl/portamento.receive', 'on', 'off|on'],

        ['portamento time', '/part$i/ctl/portamento.time', 64],
        ['portamento up/down', '/part$i/ctl/portamento.updowntimestretch', 64],
        ['threshold type', '/part$i/ctl/portamento.pitchthreshtype', '<=', ['<=', '>=']],
        ['threshold', '/part$i/ctl/portamento.pitchthresh', 3],

        ['portaprop on/off', '/part$i/ctl/portamento.proportional', 'off', 'off|on'],
        ['portaprop rate', '/part$i/ctl/portamento.propRate', 80],
        ['portaprop depth', '/part$i/ctl/portamento.propDepth', 90],

        ['modulation', 1, 0],
        ['modulation amplitude', 76, 127],
        ['modwheel depth', '/part$i/ctl/modwheel.depth', 80],
        ['modwheel exp', '/part$i/ctl/modwheel.exponential', 'off', 'off|on'],

        ['bendrange', '/part$i/ctl/pitchwheel.bendrange', '2', bend_ticks],
        ['bendrange split', '/part$i/ctl/pitchwheel.is_split', 'off', 'off|on'],
        ['bendrange down', '/part$i/ctl/pitchwheel.bendrange_down', 0, bend_ticks],

        ['resonance center', 77, 64],
        ['resonance bandwidth', 78, 64],
        ['rescenter depth', '/part$i/ctl/resonancecenter.depth', 64],
        ['resbw depth', '/part$i/ctl/resonancebandwidth.depth', 64],

        ['bandwidth', 75, 64],
        ['bandwidth depth', '/part$i/ctl/bandwidth.depth', 64],
        ['bandwidth exp', '/part$i/ctl/bandwidth.exponential', 'off', 'off|on'],

        ['panning depth', '/part$i/ctl/panning.depth', 64],
        ['filter.cutoff depth', '/part$i/ctl/filtercutoff.depth', 64],
        ['filter.Q depth', '/part$i/ctl/filterq.depth', 64],

        ['velocity sens.', '/part$i/Pvelsns', 64],
        ['velocity offs.', '/part$i/Pveloffs', 64]
    ]

    # Controller Screens
    _ctrl_screens = [
        ['main', ['volume', 'panning', 'filter cutoff', 'filter resonance']],
        ['mode', ['drum mode', 'sustain', 'assign mode', 'voice limit']],
        ['portamento', ['portamento enable', 'portamento auto', 'portamento receive']],
        ['portamento time', ['portamento time', 'portamento up/down', 'threshold', 'threshold type']],
        ['portamento prop', ['portaprop on/off', 'portaprop rate', 'portaprop depth']],
        ['modulation', ['modulation', 'modulation amplitude', 'modwheel depth', 'modwheel exp']],
        ['pitchwheel', ['bendrange split', 'bendrange down', 'bendrange']],
        ['resonance', ['resonance center', 'rescenter depth', 'resonance bandwidth', 'resbw depth']],
        ['bandwidth', ['bandwidth', 'bandwidth depth', 'bandwidth exp']],
        ['depth', ['panning depth', 'filter.cutoff depth', 'filter.Q depth']],
        ['velocity', ['velocity sens.', 'velocity offs.']]
    ]

    # ----------------------------------------------------------------------------
    # Config variables
    # ----------------------------------------------------------------------------

    preset_fexts = ['xiz', 'xmz', 'xsz', 'xlz']
    root_bank_dirs = [
        ('User', zynthian_engine.my_data_dir + "/presets/zynaddsubfx/banks"),
        ('System', zynthian_engine.data_dir + "/zynbanks")
    ]

    # ----------------------------------------------------------------------------
    # Initialization
    # ----------------------------------------------------------------------------

    def __init__(self, state_manager=None):
        super().__init__(state_manager)
        self.name = "ZynAddSubFX"
        self.nickname = "ZY"
        self.jackname = "zynaddsubfx"

        self.osc_target_port = ServerPort["zynaddsubfx_osc"]

        try:
            self.sr = int(self.state_manager.get_jackd_samplerate())
        except Exception as e:
            logging.error(e)
            self.sr = 44100

        try:
            self.bs = int(self.state_manager.get_jackd_blocksize())
        except Exception as e:
            logging.error(e)
            self.bs = 256

        if self.config_remote_display():
            self.command = "zynaddsubfx -r {} -b {} -O jack-multi -I jack -P {} -a".format(
                self.sr, self.bs, self.osc_target_port)
        else:
            self.command = "zynaddsubfx -r {} -b {} -O jack-multi -I jack -P {} -a -U".format(
                self.sr, self.bs, self.osc_target_port)

        # Zynaddsubfx which uses PWD as the root for presets, due to the fltk
        # toolkit used for the gui file browser.
        self.command_cwd = zynthian_engine.my_data_dir + "/presets"

        self.command_prompt = "\n\\[INFO] Main Loop..."

        self.osc_paths_data = []
        self.current_slot_zctrl = None
        self.slot_zctrls = {}

        self.start()
        self.reset()

    def reset(self):
        super().reset()
        self.disable_all_parts()

    # ---------------------------------------------------------------------------
    # Processor Management
    # ---------------------------------------------------------------------------

    def add_processor(self, processor):
        self.processors.append(processor)
        processor.part_i = self.get_free_parts()[0]
        processor.jackname = "{}:part{}/".format(self.jackname, processor.part_i)
        processor.refresh_controllers()
        self.enable_part(processor)
        processor.send_controller_values()
        logging.debug("ADD processor => Part {} ({})".format(processor.part_i, self.jackname))

    def remove_processor(self, processor):
        self.disable_part(processor.part_i)
        processor.part_i = None
        super().remove_processor(processor)

    # ---------------------------------------------------------------------------
    # MIDI Channel Management
    # ---------------------------------------------------------------------------

    def set_midi_chan(self, processor):
        if self.osc_server and processor.part_i is not None:
            lib_zyncore.zmop_set_midi_chan_trans(
                processor.chain.zmop_index,
                processor.get_midi_chan(),
                processor.part_i)

    # ----------------------------------------------------------------------------
    # Preset Managament
    # ----------------------------------------------------------------------------

    @staticmethod
    def _get_preset_list(bank):
        preset_list = []
        preset_dir = bank[0]
        index = 0
        logging.info("Getting Preset List for %s" % bank[2])
        for f in sorted(os.listdir(preset_dir)):
            preset_fpath = join(preset_dir, f)
            ext = f[-3:].lower()
            if isfile(preset_fpath) and (ext == 'xiz' or ext == 'xmz' or ext == 'xsz' or ext == 'xlz'):
                try:
                    index = int(f[0:4])-1
                    title = str.replace(f[5:-4], '_', ' ')
                except:
                    index += 1
                    title = str.replace(f[0:-4], '_', ' ')
                bank_lsb = int(index/128)
                bank_msb = bank[1]
                prg = index % 128
                preset_list.append([preset_fpath, [bank_msb, bank_lsb, prg], title, ext, f])
        return preset_list

    def get_preset_list(self, bank):
        return self._get_preset_list(bank)

    def set_preset(self, processor, preset, preload=False):
        if self.osc_server is None:
            return
        self.state_manager.start_busy("zynaddsubfx")
        if preset[3] == 'xiz':
            self.osc_server.send(self.osc_target, "/load-part", processor.part_i, preset[0])
            # logging.debug("OSC => /load-part %s, %s" % (processor.part_i,preset[0]))
        elif preset[3] == 'xmz':
            self.osc_server.send(self.osc_target, "/load_xmz", preset[0])
            logging.debug("OSC => /load_xmz %s" % preset[0])
        elif preset[3] == 'xsz':
            self.osc_server.send(self.osc_target, "/load_xsz", preset[0])
            logging.debug("OSC => /load_xsz %s" % preset[0])
        elif preset[3] == 'xlz':
            self.osc_server.send(self.osc_target, "/load_xlz", preset[0])
            logging.debug("OSC => /load_xlz %s" % preset[0])
        self.wait_busy()
        return True

    def cmp_presets(self, preset1, preset2):
        try:
            if preset1[0] == preset2[0]:
                return True
            else:
                return False
        except:
            return False

    # ----------------------------------------------------------------------------
    # Controller Managament
    # ----------------------------------------------------------------------------

    def get_ctrl_options(self, ctrl, processor):
        options = super().get_ctrl_options(ctrl, processor)

        # OSC control =>
        if isinstance(ctrl[1], str):
            # replace variables ...
            tpl = Template(ctrl[1])
            try:
                osc_path = tpl.safe_substitute(i=processor.part_i)
                options['osc_path'] = osc_path
                if self.osc_target_port > 0:
                    options['osc_port'] = self.osc_target_port
                #logging.debug(f"CONTROLLER {ctrl[0]} with OSC PATH => {osc_path}")
            except Exception as e:
                logging.error(f"Malformed OSC path => {ctrl[1]}")

        # Extra options => Pre-MIDI learning, etc.
        if len(ctrl) > 4 and isinstance(ctrl[4], dict):
            options.update(ctrl[4])

        return options

    def send_controller_value(self, zctrl):
        try:
            if self.osc_server and zctrl.osc_path:
                self.osc_server.send(self.osc_target, zctrl.osc_path, zctrl.get_ctrl_osc_val())
            else:
                izmop = zctrl.processor.chain.zmop_index
                if izmop is not None and izmop >= 0:
                    mchan = zctrl.processor.part_i
                    mval = zctrl.get_ctrl_midi_val()
                    lib_zyncore.zmop_send_ccontrol_change(izmop, mchan, zctrl.midi_cc, mval)
        except Exception as err:
            logging.error(err)

    # ---------------------------------------------------------------------------
    # Specific functions
    # ---------------------------------------------------------------------------

    def enable_part(self, processor):
        if self.osc_server and processor.part_i is not None:
            self.osc_server.send(self.osc_target, f"/part{processor.part_i}/Penabled", True)
            self.osc_server.send(self.osc_target, f"/part{processor.part_i}/Prcvchn", processor.part_i)
            lib_zyncore.zmop_set_midi_chan_trans(processor.chain.zmop_index,
                                                 processor.get_midi_chan(),
                                                 processor.part_i)

    def disable_part(self, i):
        if self.osc_server:
            self.osc_server.send(
                self.osc_target, "/part%d/Penabled" % i, False)

    def disable_all_parts(self):
        for i in range(0, 16):
            self.disable_part(i)

    def enable_processor_parts(self):
        for processor in self.processors:
            self.enable_part(processor)
        for i in self.get_free_parts():
            self.disable_part(i)

    # ----------------------------------------------------------------------------
    # OSC Managament
    # ----------------------------------------------------------------------------

    def cb_osc_all(self, path, args, types, src):
        try:
            # logging.debug("Rx OSC => {} {}".format(path, args))
            if path == '/volume':
                self.state_manager.end_busy("zynaddsubfx")
        except Exception as e:
            logging.warning(e)

    def wait_busy(self):
        self.osc_server.send(self.osc_target, "/volume")
        i = 0
        while self.state_manager.is_busy("zynaddsubfx"):
            sleep(0.1)
            if i > 100:
                self.state_manager.end_busy("zynaddsubfx")
                break
            else:
                i = i + 1

    # ---------------------------------------------------------------------------
    # API methods
    # ---------------------------------------------------------------------------

    @classmethod
    def zynapi_get_banks(cls):
        banks = []
        for b in cls.get_bank_dirlist(recursion=1, exclude_empty=False):
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
            presets.append({
                'text': p[4],
                'name': os.path.splitext(p[4])[0],
                'fullpath': p[0],
                'raw': p,
                'readonly': False
            })
        return presets

    @classmethod
    def zynapi_new_bank(cls, bank_name):
        os.mkdir(zynthian_engine.my_data_dir +
                 "/presets/zynaddsubfx/banks/" + bank_name)

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

    @classmethod
    def zynapi_download(cls, fullpath):
        return fullpath

    @classmethod
    def zynapi_install(cls, dpath, bank_path):

        if os.path.isdir(dpath):
            # Get list of directories (banks) containing xiz files ...
            xiz_files = check_output(
                "find \"{}\" -type f -iname *.xiz".format(dpath), shell=True).decode("utf-8").split("\n")

            # Copy xiz files to destiny, creating the bank if needed ...
            count = 0
            for f in xiz_files:
                head, xiz_fname = os.path.split(f)
                head, dbank = os.path.split(head)
                if dbank:
                    dest_dir = zynthian_engine.my_data_dir + "/presets/zynaddsubfx/banks/" + dbank
                    os.makedirs(dest_dir, exist_ok=True)
                    shutil.move(f, dest_dir + "/" + xiz_fname)
                    count += 1

            if count == 0:
                raise Exception("No XIZ files found!")

        else:
            fname, ext = os.path.splitext(dpath)
            if ext == '.xiz':
                shutil.move(dpath, bank_path)
            else:
                raise Exception("File doesn't look like a XIZ preset!")

    @classmethod
    def zynapi_get_formats(cls):
        return "xiz,zip,tgz,tar.gz,tar.bz2,tar.xz"

    @classmethod
    def zynapi_martifact_formats(cls):
        return "xiz"

# ******************************************************************************
