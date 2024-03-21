# -*- coding: utf-8 -*-
#******************************************************************************
# ZYNTHIAN PROJECT: Zynthian Engine (zynthian_engine_jamulus)
#
# zynthian_engine implementation for jamulus
#
# Copyright (C) 2024 Brian Walton <riban@zynthian.org>
#
#******************************************************************************
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
#******************************************************************************

""" TODO:
    Save presets / servers
    Update control view with controllers when users connect/disconnect
    Send and display text messages
    Touch drag fader should be full width of channel, not just fader knob
    Default mute own channel (not mute self) is probably most common workflow
"""

import logging
import socket
from time import sleep
import threading
import json
import random, string
from subprocess import Popen, DEVNULL

from . import zynthian_engine
from zynconf import ServerPort
import zynautoconnect
from zyngine.zynthian_signal_manager import zynsigman
from zyngine import zynthian_processor

#------------------------------------------------------------------------------
# Jamulus Engine Class
#------------------------------------------------------------------------------

class zynthian_engine_jamulus(zynthian_engine):

    # ---------------------------------------------------------------------------
    # Config variables
    # ---------------------------------------------------------------------------
    RPC_PORT = ServerPort["jamulus_rpc"]
    RPC_SECRET_FILE = "/tmp/jamulus.secret"
    PRESET_FILE = "/zynthian/zynthian-my-data/presets/jamulus.json"
    STATE_DISCONNECTED = 0
    STATE_CONNECTING = 1
    STATE_CONNECTED = 2

    # ---------------------------------------------------------------------------
    # Initialization
    # ---------------------------------------------------------------------------

    def __init__(self, state_manager=None):
        super().__init__(state_manager)

        self._ctrls = [
            ["Connect", None, "On", ["Off","On"]],
            ["Mute Self", 100, "Off", ["Off", "On"]],
            ["Local Server", None, "Off", ["Off", "On"]]
        ]
        for i in range(1,9):
            self._ctrls += [
                [f"Fader {i}", i, 127, 127],
                [f"Pan {i}", i + 16, 64, 127],
                [f"Mute {i}", i + 32, "Off", ["Off","On"]],
                [f"Solo {i}", i + 48, "Off", ["Off","On"]]
            ]

        letters = string.ascii_lowercase + string.digits
        self.RPC_SECRET = ''.join(random.choice(letters) for i in range(16))
        self.custom_gui_fpath = "/zynthian/zynthian-ui/zyngui/zynthian_widget_jamulus.py"
        self.name = "Jamulus"
        self.nickname = "JA"
        self.jackname = "jamulus"
        self.type = "Audio Effect"
        self.user_name = socket.gethostname()
        self.clients = [] # List of connected client info
        self.levels = [] # List of each client's audio level (0..10)
        self.own_channel = None # Own channel or None if not connected
        self.server_proc = None # Process object for jamulus server running on this device
        self.monitors = {} # Populate with changed values
        self.update_ctrl_screen()

    def update_ctrl_screen(self):
        existing_names = []
        for scrn in self._ctrl_screens:
            existing_names.append(scrn[0])
        channels = range(1, len(self.clients) + 1)
        names = []
        self._ctrl_screens = [["Main", ["Connect", "Mute Self", "Local Server"]]]
        for i in channels:
            suffix = 1
            name = self.clients[i - 1]["name"]
            if not name:
                name = f"User {i}"
            else:
                while name in names:
                    name = self.clients[i - 1]["name"] + f" ({suffix})"
                    suffix += 1
            self._ctrl_screens += [[name, [f"Fader {i}", f"Pan {i}", f"Mute {i}", f"Solo {i}"]]]
            names.append(name)
        if self.processors:
            self.processors[0].init_ctrl_screens()
            zynsigman.send_queued(zynsigman.S_PROCESSOR, zynthian_processor.SS_ZCTRL_REFRESH, processor=self.processors[0])

    def start(self):
        if self.state_manager.get_jackd_samplerate() != 48000:
            raise Exception("Jamulus only supports 48000 samplerate")
        if self.proc:
            return
        logging.info(f"Starting Engine {self.name}")
        self.monitors["status"] = self.STATE_CONNECTING

        self.command = [
            "Jamulus",
            "--nojackconnect",
            "--clientname", self.jackname,
            "--jsonrpcport", str(self.RPC_PORT),
            "--jsonrpcsecretfile", self.RPC_SECRET_FILE,
            "--ctrlmidich", "'1;f1*16;p17*16;m33*16;s49*16;o100;o100'", # bug in jamulus r3.9 does not parse last parameter correctly so repeat ;o100
            "--inifile", f"{self.data_dir}/jamulus/Jamulus.ini",
            "--connect", self.preset[1]
        ]
        if not self.config_remote_display():
            self.command.append("--nogui")
        with open(self.RPC_SECRET_FILE, "w") as f:
            f.write(self.RPC_SECRET)
        self.rpc_id = 0
        self.clients = [] # List of connected client info
        self.levels = [] # List of each client's audio level (0..10)
        self.proc = Popen(self.command, env=self.command_env, cwd=self.command_cwd, stdout=DEVNULL, stderr=DEVNULL)
        # Wait for rpc-json server to be available indicating process is ready
        self.rpc_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.rpc_socket.settimeout(0.5)
        self.running=True
        success = False
        for i in range(10):
            try:
                self.rpc_socket.connect(("localhost", self.RPC_PORT))
                self.rpc_socket.send(bytes(f'{{"id":{self.rpc_id},"jsonrpc":"2.0","method":"jamulus/apiAuth","params":{{"secret":"{self.RPC_SECRET}"}}}}\r\n', "utf-8"))
                success = True
                self.rpc_id += 1
                break
            except Exception as e:
                sleep(0.2)
        if self.processors:
            self.processors[0].controllers_dict["Connect"].set_value("On", False)
        self.update_ctrl_screen()
        self.thread = threading.Thread(target=self.monitor)
        self.thread.start()
        self.set_name(self.user_name)

        zynautoconnect.request_midi_connect(True)
        zynautoconnect.request_audio_connect(True)

    def stop(self, term_server=True):
        if self.proc:
            self.running = False
            try:
                self.thread.join()
            except:
                pass # May be stopping before thread is started???
            self.rpc_socket.close()
            self.proc.terminate()
            for i in range(10):
                if self.proc.poll() is not None:
                    break
                sleep(0.2)
            self.proc = None
            self.clients = []
            self.monitors["status"] = self.STATE_DISCONNECTED
            self.update_ctrl_screen()
        if term_server and self.server_proc:
            self.server_proc.terminate()
            self.server_proc = None
            self.monitors["local_server_status"] = False

    def restart(self):
        self.stop(False)
        self.start()

    def monitor(self):
        while self.running:
            try:
                for jsn in self.rpc_socket.recv(4096).decode("utf-8").split("\n"):
                    if "method" in jsn:
                        msg = json.loads(jsn)
                        method = msg["method"]
                        update_zctrls = False
                        if method == "jamulusclient/channelLevelListReceived":
                            self.levels = msg["params"]["channelLevelList"]
                        elif method == "jamulusclient/clientListReceived":
                            self.clients = msg["params"]["clients"]
                            self.update_ctrl_screen()
                            self.monitors["clients"] = self.clients
                            self.monitors["status"] = self.STATE_CONNECTED
                            for zctrl in self.processors[0].controllers_dict.values():
                                if zctrl.midi_cc:
                                    zctrl.send_midi_cc(zctrl.value)
                        elif method == "jamulusclient/connected":
                            self.own_channel = msg["params"]["id"]
                            self.update_ctrl_screen()
                            self.monitors["status"] = self.STATE_CONNECTED
                        elif method == "jamulusclient/disconnected":
                            self.own_channel = None
                            self.processors[0].controllers_dict["Connect"].set_value("Off")
                            self.update_ctrl_screen()
                            self.monitors["status"] = self.STATE_DISCONNECTED
                            self.running = False
                            # Jamulus stops trying to reconnect 30s after last handshake but we want it to continue to reconnect
                            # May be influenced by https://github.com/jamulussoftware/jamulus/issues/2519
                            threading.Timer(0.5, self.restart).start()
                        elif method == "jamulusclient/chatTextReceived":
                            self.monitors["chatText"] = msg["params"]["chatText"]
            except TimeoutError:
                pass # We expect socket to timeout when no data available
            except OSError as e:
                logging.warning("Socket disconnected", e)
                break
            except Exception as e:
                logging.error(e)
            sleep(0.1)


    # ----------------------------------------------------------------------------
    # RPC-JSON Management
    # ----------------------------------------------------------------------------

    def set_name(self, name):
        try:
            self.rpc_socket.send(bytes(f'{{"id":{self.rpc_id},"jsonrpc":"2.0","method":"jamulusclient/setName","params":{{"name":"{name}"}}}}\r\n', "utf-8"))
            self.rpc_id += 1
        except:
            logging.warning("Failed to set name")

    def set_skill(self, skill):
        try:
            self.rpc_socket.send(bytes(f'{{"id":{self.rpc_id},"jsonrpc":"2.0","method":"jamulusclient/setSkillLevel","params":{{"skillLevel":"{skill}"}}}}\r\n', "utf-8"))
            self.rpc_id += 1
        except:
            logging.warning("Failed to set skll level")

    # ---------------------------------------------------------------------------
    # Bank Management
    # ---------------------------------------------------------------------------

    # No bank support for jamulus
    def get_bank_list(self, processor=None):
        return [("", None, "", None)]

    # ----------------------------------------------------------------------------
    # Preset Management
    # ----------------------------------------------------------------------------

    def get_preset_list(self, bank):
        """ Get list of presets (remote servers) in a bank
        
        bank - Name of bank (ignored)
        returns - list of preset config: [uri, url, name]
        """
        
        try:
            with open(self.PRESET_FILE, "r") as f:
                presets = json.load(f)
        except Exception as e:
            # Preset file missing or corrupt
            presets = [["DefaultLocalHost", "localhost", "Local Server"]]
        
        return presets

    def set_preset(self, processor, preset, preload=False):
        """ Connect to remote server
        processor - Processor object (not used - only one processor allowed for jamulus)
        preset - Preset config
        preload - True to allow preload (not used)
        """

        self.stop(False)
        self.preset = preset
        self.start()

    def is_preset_user(self, preset):
        return preset[0] != "DefaultLocalHost"

    def rename_preset(self, bank, preset, name):
        with open(self.PRESET_FILE, "r") as f:
            presets = json.load(f)
        for p in presets:
            if p[1] == preset[1]:
                p[2] = name
                with open(self.PRESET_FILE, 'w') as f:
                    json.dump(presets, f)
                return

    def delete_preset(self, bank, preset):
        with open(self.PRESET_FILE, "r") as f:
            presets = json.load(f)
        try:
            presets.pop(preset)
            with open(self.PRESET_FILE, 'w') as f:
                json.dump(presets, f)
        except Exception as e:
            logging.warning(e)

    #----------------------------------------------------------------------------
    # Controllers Management
    #----------------------------------------------------------------------------

    def send_controller_value(self, zctrl):
        if zctrl.symbol == "Local Server":
            if zctrl.value:
                # Start local server
                if self.server_proc is None:
                    cmd = ["Jamulus","--server", "--inifile", f"{self.data_dir}/jamulus/Jamulusserver.ini"]
                    if not self.config_remote_display():
                        cmd.append("--nogui")
                    self.server_proc = Popen(cmd, env=self.command_env, cwd=self.command_cwd, stdout=DEVNULL, stderr=DEVNULL)
                    self.monitors["local_server_status"] = True

            else:
                # Stop local server
                if self.server_proc:
                    self.server_proc.terminate()
                    self.server_proc = None
                    self.monitors["local_server_status"] = False
        elif zctrl.symbol == "Connect":
            if zctrl.value:
                self.start()
            else:
                self.stop(False)
        else:
            if zctrl.symbol.startswith("Fader"):
                if "fader" in self.monitors:
                    self.monitors["fader"].append((int(zctrl.symbol[6:]), zctrl.value))
                else:
                    self.monitors["fader"] = [(int(zctrl.symbol[6:]), zctrl.value)]
            elif zctrl.symbol.startswith("Pan"):
                if "pan" in self.monitors:
                    self.monitors["pan"].append((int(zctrl.symbol[4:]), zctrl.value))
                else:
                    self.monitors["pan"] = [(int(zctrl.symbol[4:]), zctrl.value)]
            elif zctrl.symbol.startswith("Mute"):
                if "mute" in self.monitors:
                    self.monitors["mute"].append((int(zctrl.symbol[5:]), zctrl.value))
                else:
                    self.monitors["mute"] = [(int(zctrl.symbol[5:]), zctrl.value)]
            elif zctrl.symbol.startswith("Solo"):
                if "solo" in self.monitors:
                    self.monitors["solo"].append((int(zctrl.symbol[5:]), zctrl.value))
                else:
                    self.monitors["solo"] = [(int(zctrl.symbol[5:]), zctrl.value)]
            elif zctrl.symbol == "Mute Self":
                self.monitors["muteSelf"] = zctrl.value
            raise("Use MIDI CC control")

    def get_monitors_dict(self):
        monitors = self.monitors.copy()
        self.monitors = {}
        return monitors

    # ---------------------------------------------------------------------------
    # API methods
    # ---------------------------------------------------------------------------

    @classmethod
    def zynapi_get_banks(cls):
        return [
            {
                "text": "Servers",
                "name": "Servers",
                "fullpath": "/zynthian/zynthian-my-data/presets/jamulus",
                "readonly": False
            }
        ]

    @classmethod
    def zynapi_get_presets(cls, bank):
        presets = []
        for preset in cls.get_preset_list(cls, bank):
            presets.append({
                    'text': preset[2],
                    'name': preset[2],
                    'fullpath': preset[0],
                    'raw': preset,
                    'readonly': True if preset[0] == 'DefaultLocalHost' else False
                })
        return presets

    @classmethod
    def zynapi_rename_preset(cls, preset_id, name):
        cls.rename_preset(preset_id, name)

    @classmethod
    def zynapi_download(cls, preset_id):
        presets = cls.get_preset_list(cls, None)
        for preset in presets:
            if preset[0] == preset_id:
                try:
                    filename = f'/tmp/{preset[0]}.jamulus'
                    with open(filename, 'w') as f:
                        f.write(f"uid={preset[0]}\n")
                        f.write(f"url={preset[1]}\n")
                        f.write(f"name={preset[2]}\n")
                    return filename
                except Exception as e:
                    logging.warning(e)
                break

    @classmethod
    def zynapi_get_formats(cls):
        return "jamulus"

    @classmethod
    def zynapi_install(cls, dpath, bank_path):
        with open(dpath, 'r') as f:
            lines = f.readlines()
        for line in lines:
            key, value = line.strip().split("=", 1)
            if key.lower() == "uid":
               uid = value
            elif key.lower() == "url":
               url = value
            elif key.lower() == "name":
               name = value
        try:
            new_preset = [uid, url, name]
        except:
            logging.warning("Bad jamulus preset file format")
            return
        presets = cls.get_preset_list(cls, None)
        update = False
        for i, preset in enumerate (presets):
            if preset[0] == new_preset[0]:
                presets[i] = new_preset
                update = True
                break
        if not update:
            presets.append(new_preset)
        with open(zynthian_engine_jamulus.PRESET_FILE, 'w') as f:
            json.dump(presets, f)

    @classmethod
    def zynapi_remove_preset(cls, preset_id):
        with open(zynthian_engine_jamulus.PRESET_FILE, "r") as f:
            presets = json.load(f)
        try:
            for i, preset in enumerate(presets):
                if preset[0] == preset_id:
                    presets.pop(i)
                    with open(zynthian_engine_jamulus.PRESET_FILE, 'w') as f:
                        json.dump(presets, f)
                    break
        except Exception as e:
            logging.warning(e)

    @classmethod
    def zynapi_get_description(cls):
        return "Low latency online audio collaboration."
