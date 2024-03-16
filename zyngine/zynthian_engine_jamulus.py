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

import logging
import socket
from time import sleep
import threading
import json
import random, string
from subprocess import Popen, PIPE

from . import zynthian_engine
from . import zynthian_controller
from zynconf import ServerPort
import zynautoconnect

#------------------------------------------------------------------------------
# Jamulus Engine Class
#------------------------------------------------------------------------------

class zynthian_engine_jamulus(zynthian_engine):

    # ---------------------------------------------------------------------------
    # Config variables
    # ---------------------------------------------------------------------------
    RPC_PORT = ServerPort["jamulus_rpc"]
    RPC_SECRET_FILE = "/tmp/jamulus.secret"

    # ---------------------------------------------------------------------------
    # Initialization
    # ---------------------------------------------------------------------------

    def __init__(self, state_manager=None):
        super().__init__(state_manager)
        letters = string.ascii_lowercase + string.digits
        self.RPC_SECRET = ''.join(random.choice(letters) for i in range(16))
        self.custom_gui_fpath = "/zynthian/zynthian-ui/zyngui/zynthian_widget_jamulus.py"
        self.name = "Jamulus"
        self.nickname = "JA"
        self.jackname = "jamulus"
        self.type = "Audio Effect"
        self.user_name = socket.gethostname() # TODO: Get from global Zynthian user name
        self.clients = [] # List of connected client info
        self.levels = [] # List of each client's audio level (0..10)
        self.own_channel = None # Own channel or None if not connected
        self.server_proc = None # Process object for jamulus server running on this device
        self.monitors = {} # Populate with changed values
        self.build_ctrls()
        # List: [uid, url, name, None]
        self.presets = [
            ["Local", "localhost", "Local"]
        ]
        try:
            with open(self.my_data_dir + "/presets/jamulus/presets.json", "r") as f:
                self.presets += json.load(f)
        except Exception as e:
            # Preset file missing or corrupt
            logging.error(e)

    def build_ctrls(self):
        if self.server_proc is None:
            local_server = "Off"
        else:
            local_server = "On"
        self._ctrls = [
            ["Mute Self", 100, "Off", ["Off","On"]],
            ["Local Server", None, local_server, ["Off", "On"]]
        ]
        self._ctrl_screens = [
            ["Local", ["Mute Self", "Local Server"]]
        ]
        channels = range(1, len(self.clients) + 1)
        names = []
        for i in channels:
            suffix = 1
            self._ctrls += [[f"Fader {i}", i, 127, 127]]
            self._ctrls += [[f"Pan {i}", i + 16, 64, 127]]
            self._ctrls += [[f"Mute {i}", i + 32, "Off", ["Off","On"]]]
            self._ctrls += [[f"Solo {i}", i + 48, "Off", ["Off","On"]]]
            name = self.clients[i - 1]["name"]
            if not name:
                name = f"User {i}"
            else:
                while name in names:
                    name = self.clients[i - 1]["name"] + f" ({suffix})"
                    suffix += 1
            if self.own_channel == i - 1:
                name += " (me)"
            self._ctrl_screens += [[name, [f"Fader {i}", f"Pan {i}", f"Mute {i}", f"Solo {i}"]]]
            names.append(name)


    def start(self):
        if self.state_manager.get_jackd_samplerate() != 48000:
            raise Exception("Jamulus only supports 48000 samplerate")
        if self.proc:
            return
        logging.info(f"Starting Engine {self.name}")

        self.command = [
            "/usr/bin/jamulus",
            "--nojackconnect",
            "--clientname", self.jackname,
            "--jsonrpcport", str(self.RPC_PORT),
            "--jsonrpcsecretfile", self.RPC_SECRET_FILE,
            "--ctrlmidich", "'1;f1*16;p17*16;m33*16;s49*16;o100'",
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
        self.own_channel = None # Own channel or None if not connected

        self.proc = Popen(self.command, env=self.command_env, cwd=self.command_cwd)
        #super().start() #TODO: Use lightwieght Popen - last attempt stopped RPC working
        # Wait for rpc-json server to be available indicating process is ready
        self.rpc_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.rpc_socket.settimeout(0.5)
        success = False
        for i in range(10):
            try:
                self.rpc_socket.connect(("localhost", self.RPC_PORT))
                self.rpc_socket.send(bytes(f'{{"id":{self.rpc_id},"jsonrpc":"2.0","method":"jamulus/apiAuth","params":{{"secret":"{self.RPC_SECRET}"}}}}\r\n', "utf-8"))
                success = True
                self.rpc_id += 1
                break
            except Exception as e:
                sleep(0.5)
        self.thread = threading.Thread(target=self.monitor)
        self.running = True
        self.thread.start()
        self.set_name(self.user_name)

    def stop(self, term_server=True):
        if self.proc:
            self.running = False
            self.rpc_socket.close()
            self.thread.join()
            self.proc.terminate()
            self.proc = None
        if term_server and self.server_proc:
            self.server_proc.terminate()
            self.server_proc = None

    def monitor(self):
        while self.running:
            try:
                for jsn in self.rpc_socket.recv(4096).decode("utf-8").split("\n"):
                    if "method" in jsn:
                        msg = json.loads(jsn)
                        method = msg["method"]
                        if method == "jamulusclient/channelLevelListReceived":
                            self.levels = msg["params"]["channelLevelList"]
                        elif method == "jamulusclient/clientListReceived":
                            self.clients = msg["params"]["clients"]
                            self.build_ctrls()
                            self.processors[0].refresh_controllers()
                            self.monitors["clients"] = self.clients
                            self.monitors["connected"] = True
                        elif method == "jamulusclient/connected":
                            self.own_channel = msg["params"]["id"]
                            self.build_ctrls()
                            self.processors[0].refresh_controllers()
                            self.monitors["connected"] = True
                        elif method == "jamulusclient/disconnected":
                            self.own_channel = None
                            self.build_ctrls()
                            self.processors[0].refresh_controllers()
                            self.monitors["connected"] = False
            except TimeoutError:
                pass # We expect socket to timeout when no data available
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
        """
        
        return self.presets

    def set_preset(self, processor, preset, preload=False):
        """ Connect to remote server
        processor - Processor object (only one processor allowed for jamulus)
        preset - Preset config
        preload - True to allow preload (not used)
        """

        self.stop(False)
        self.preset = preset
        self.start()
        zynautoconnect.request_midi_connect(True)
        zynautoconnect.request_audio_connect(True)


    #----------------------------------------------------------------------------
    # Controllers Management
    #----------------------------------------------------------------------------

    def send_controller_value(self, zctrl):
        if zctrl.symbol == "Local Server":
            if zctrl.value:
                # Start local server
                if self.server_proc is None:
                    cmd = ["/usr/bin/jamulus","--server", "--inifile", f"{self.data_dir}/jamulus/Jamulusserver.ini"]
                    if not self.config_remote_display():
                        cmd.append("--nogui")
                    self.server_proc = Popen(cmd, env=self.command_env, cwd=self.command_cwd, stdout=PIPE, stderr=PIPE, stdin=PIPE)
            else:
                # Stop local server
                if self.server_proc:
                    self.server_proc.terminate()
                    self.server_proc = None
        else:
            if zctrl.symbol.startswith("Fader"):
                if "fader" in self.monitors:
                    self.monitors["fader"].append((int(zctrl.symbol[6:]), zctrl.value))
                else:
                    self.monitors["fader"] = [(int(zctrl.symbol[6:]), zctrl.value)]
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
            raise("Use MIDI CC control")

    def get_monitors_dict(self):
        monitors = self.monitors.copy()
        self.monitors = {}
        return monitors