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
    Send and display text messages
    Touch drag fader should be full width of channel, not just fader knob
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

    directories = [
        {
            "name": "Any Genre 1",
            "address": "anygenre1.jamulus.io:22124",
            "servers": []
        },
        {
            "name": "Any Genre 2",
            "address": "anygenre2.jamulus.io:22224",
            "servers": []
        },
        {
            "name": "Any Genre 3",
            "address": "anygenre3.jamulus.io:22624",
            "servers": []
        },
        {
            "name": "Rock",
            "address": "rock.jamulus.io:22424",
            "servers": []
        },
        {
            "name": "Jazz",
            "address": "jazz.jamulus.io:22324",
            "servers": []
        },
        {
            "name": "Classical/Folk",
            "address": "classical.jamulus.io:22524",
            "servers": []
        },
        {
            "name": "Choral/Barbershop",
            "address": "choral.jamulus.io:22724",
            "servers": []
        }
    ]

    # ---------------------------------------------------------------------------
    # Initialization
    # ---------------------------------------------------------------------------

    def __init__(self, state_manager=None):
        super().__init__(state_manager)

        self._ctrls = [
            ["Connect", None, "On", ["Off","On"]],
            ["Mute Self", 100, "On", ["Off", "On"]],
            ["Local Server", None, "Off", ["Off", "On"]]
        ]
        for i in range(1,9):
            self._ctrls += [
                [f"Fader {i}", i, 127, 127],
                [f"Pan {i}", i + 16, 64, 127],
                [f"Mute {i}", i + 32, "Off", ["Off","On"]],
                [f"Solo {i}", i + 48, "Off", ["Off","On"]]
            ]

        self.directory_index = 0
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
        self.preset = ["localhost", False, "Local Server"]
        self.server_info = {} # List of [pingTime, numClients]for each server, indexed by server socket address
        #self.update_ctrl_screen()
        self.start()

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

        self.command = [
            "jamulus",
            "--nojackconnect",
            "--clientname", self.jackname,
            "--jsonrpcport", str(self.RPC_PORT),
            "--jsonrpcsecretfile", self.RPC_SECRET_FILE,
            "--ctrlmidich", "'1;f1*16;p17*16;m33*16;s49*16;o100;o100'", # bug in jamulus (r3.10) does not parse last parameter correctly so repeat ;o100
            "--inifile", f"{self.data_dir}/jamulus/Jamulus.ini",
            "--mutestream"
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
        for i in range(10):
            try:
                self.rpc_socket.connect(("localhost", self.RPC_PORT))
                self.rpc_socket.send(bytes(f'{{"id":{self.rpc_id},"jsonrpc":"2.0","method":"jamulus/apiAuth","params":{{"secret":"{self.RPC_SECRET}"}}}}\r\n', "utf-8"))
                self.rpc_id += 1
                success = True
                break
            except Exception as e:
                sleep(0.2)
        self.update_ctrl_screen()
        self.thread = threading.Thread(target=self.monitor)
        self.thread.start()
        self.set_name(self.user_name)

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
            self.monitors["connectionState"] = self.STATE_DISCONNECTED
            self.update_ctrl_screen()
        if term_server and self.server_proc:
            self.server_proc.terminate()
            self.server_proc = None
            self.monitors["localServerState"] = False

    def restart(self):
        self.stop(False)
        self.start()

    def monitor(self):
        while self.running:
            if self.parse_rpc():
                break
            sleep(0.1)

    def parse_rpc(self):
            try:
                for jsn in self.rpc_socket.recv(65507).decode("utf-8").split("\n"):
                    if "method" in jsn:
                        msg = json.loads(jsn)
                        method = msg["method"]
                        #logging.debug(method)
                        if method == "jamulusclient/channelLevelListReceived":
                            self.levels = msg["params"]["channelLevelList"]
                        elif method == "jamulusclient/clientListReceived":
                            self.clients = msg["params"]["clients"]
                            self.update_ctrl_screen()
                            self.monitors["clients"] = self.clients
                            self.monitors["connectionState"] = self.STATE_CONNECTED
                            for zctrl in self.processors[0].controllers_dict.values():
                                if zctrl.midi_cc:
                                    zctrl.send_midi_cc(zctrl.value)
                        elif method == "jamulusclient/connected":
                            self.own_channel = msg["params"]["id"]
                            self.update_ctrl_screen()
                            self.monitors["connectionState"] = self.STATE_CONNECTED
                        elif method == "jamulusclient/disconnected":
                            self.own_channel = None
                            self.processors[0].controllers_dict["Connect"].set_value("Off")
                            self.update_ctrl_screen()
                            self.monitors["connectionState"] = self.STATE_DISCONNECTED
                            self.running = False
                            # Jamulus stops trying to reconnect 30s after last handshake but we want it to continue to reconnect
                            # May be influenced by https://github.com/jamulussoftware/jamulus/issues/2519
                            threading.Timer(0.5, self.restart).start()
                        elif method == "jamulusclient/chatTextReceived":
                            self.monitors["chatText"] = msg["params"]["chatText"]
                        elif method == "jamulusclient/serverListReceived":
                            self.directories[self.directory_index]["servers"] += msg["params"]["servers"]
                        elif method == "jamulusclient/serverInfoReceived":
                            self.server_info[msg["params"]["address"]] = (msg["params"]["pingTime"], msg["params"]["numClients"])
                        elif method == "jamulusclient/recorderState":
                            self.monitors["recorderState"] = msg["params"]["state"]
            except TimeoutError:
                pass # We expect socket to timeout when no data available
            except OSError as e:
                logging.warning("Socket disconnected", e)
                return True
            except Exception as e:
                logging.error(e)


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

    def connect(self, address):
        self.disconnect()
        try:
            self.rpc_socket.send(bytes(f'{{"id":{self.rpc_id},"jsonrpc":"2.0","method":"jamulusclient/connect","params":{{"address":"{address}"}}}}\r\n', "utf-8"))
            self.rpc_id += 1
            self.monitors["connectionState"] = self.STATE_CONNECTING
            if self.processors:
                self.processors[0].controllers_dict["Connect"].set_value("On", False)

        except:
            logging.warning("Failed to connect")

    def disconnect(self):
        try:
            self.rpc_socket.send(bytes(f'{{"id":{self.rpc_id},"jsonrpc":"2.0","method":"jamulusclient/disconnect","params":{{}}}}\r\n', "utf-8"))
            self.rpc_id += 1
            self.monitors["connectionState"] = self.STATE_DISCONNECTED
            self.update_ctrl_screen()
        except:
            logging.warning("Failed to disconnect")

    # ---------------------------------------------------------------------------
    # Bank Management
    # ---------------------------------------------------------------------------

    def get_bank_list(self, processor=None):
        """ Get list of banks

        processor - Not used
        returns - List of banks [uid (str), index (int) or None if user bank, name (str)]
        """

        try:
            with open(self.PRESET_FILE, "r") as f:
                user_presets = json.load(f)
        except:
            # Preset file missing or corrupt
            user_presets = {"Default": {"localhost": "Local Server"}}
            with open(self.PRESET_FILE, "w") as f:
                json.dump(user_presets, f)

        if user_presets:
            banks = [(None, None, "User Banks", None)]
            for i, bank in enumerate(user_presets):
                banks.append((bank, None, bank))
        else:
            banks = []

        try:
            if self.proc:
                banks.append((None, None, "Public Directories", None))
                for i, directory in enumerate(self.directories):
                    banks += [(directory["address"], i, directory["name"])]
        except:
            pass # api cannot return public servers because jamulus client is required which may not be running
        return banks

    def rename_user_bank(self, bank, new_bank_name):
        self.zynapi_rename_bank(bank[0], new_bank_name)

    def delete_user_bank(self, bank):
        self.zynapi_remove_bank(bank[0])

    # ----------------------------------------------------------------------------
    # Preset Management
    # ----------------------------------------------------------------------------

    def get_preset_list(self, bank):
        """ Get list of presets (remote servers) in a bank
        
        bank - Bank config list [uid (str), index (int) or None if user bank, name (str)]
        returns - list of preset config: [server socket address (str), is user preset (bool), name (str)]
        """

        presets = []
        if bank[1] is None:
            try:
                with open(self.PRESET_FILE, "r") as f:
                    user_presets = json.load(f)
                for server, name in user_presets[bank[0]].items():
                    presets.append([server, None, name])
            except Exception as e:
                pass
        else:
            try:
                self.directory_index = bank[1]
                self.directories[self.directory_index]["servers"] = []
                self.server_info = {}
                self.rpc_socket.send(bytes(f'{{"id":{self.rpc_id},"jsonrpc":"2.0","method":"jamulusclient/pollServerList","params":{{"directory":"{self.directories[self.directory_index]["address"]}"}}}}\r\n', "utf-8"))
                self.rpc_id += 1
                sleep(1) # Wait for response (handled by background task)
            except Exception as e:
                logging.warning("Failed to get directory listing", e)

            preset_dict = {}
            for server in self.directories[self.directory_index]['servers']:
                if server["address"] != "0.0.0.0:0" and server["name"] and server["address"]:
                    preset_dict[server["address"]] = server
            max_ping_time = 0
            for addr, info in sorted(self.server_info.items(), key=lambda x:(x[1][0],-x[1][1])):
                try:
                    server = preset_dict[addr]
                    ping_time = info[0]
                    if ping_time > max_ping_time:
                        presets.append((None, None, f"Latency {max_ping_time - 0} - {max_ping_time + 40} ms"))
                        max_ping_time += 40
                    title = f"[{ping_time}ms {info[1]}] {server['name']}".strip()
                    if server['city']:
                        title += f" ({server['city']}"
                        if server['country']:
                            country = server['country']
                            parts = server['country'].split()
                            if len(parts) > 1:
                                country = '.'.join(t[0] for t in parts)
                            title += f",{country}"
                        title += ")"
                    else:
                        if server['country']:
                            title += f"({server['country']})"
                    presets.append([server["address"], False, title])
                except Exception as e:
                    #logging.debug(e)
                    pass # May reach here if servers unavailable - that's fine!

        return presets

    def set_preset(self, processor, preset, preload=False):
        """ Connect to remote server
        processor - Processor object (not used - only one processor allowed for jamulus)
        preset - Preset config is list [server socket address (str), is user preset (bool), name (str)]
        preload - True to allow preload (not used)
        """

        self.preset = preset
        if self.processors and self.processors[0].controllers_dict["Connect"].value:
            self.connect(self.preset[0])

    def is_preset_user(self, preset):
        return preset[1] is None

    def rename_preset(self, bank, preset, name):
        try:
            with open(self.PRESET_FILE, "r") as f:
                presets = json.load(f)
            presets[bank[0]][preset[0]] = name
            with open(self.PRESET_FILE, 'w') as f:
                json.dump(presets, f)
        except:
            pass

    def delete_preset(self, bank, preset):
        try:
            with open(self.PRESET_FILE, "r") as f:
                presets = json.load(f)
            presets[bank[0]].pop(preset[0])
            with open(self.PRESET_FILE, 'w') as f:
                json.dump(presets, f)
        except Exception as e:
            logging.warning(e)

    def toggle_preset_fav(self, processor, preset):
        if self.preset_favs is None:
            self.load_preset_favs()
        try:
            del self.preset_favs[str(preset[0])]
            fav_status = False
        except:
            self.preset_favs[str(preset[0])] = [processor.bank_info, preset]
            if ']' in self.preset_favs[str(preset[0])][1][2]:
                self.preset_favs[str(preset[0])][1][2] = self.preset_favs[str(preset[0])][1][2].split('] ', 1)[1]
            fav_status = True

        try:
            with open(self.preset_favs_fpath, 'w') as f:
                json.dump(self.preset_favs, f)
        except Exception as e:
            logging.error("Can't save preset favorites! => {}".format(e))

        return fav_status

    #----------------------------------------------------------------------------
    # Controllers Management
    #----------------------------------------------------------------------------

    def send_controller_value(self, zctrl):
        if zctrl.symbol == "Local Server":
            if zctrl.value:
                # Start local server
                if self.server_proc is None:
                    cmd = [
                        "jamulus",
                        "--server",
                        "--inifile", f"{self.data_dir}/jamulus/Jamulusserver.ini"
                    ]
                    if not self.config_remote_display():
                        cmd.append("--nogui")
                    self.server_proc = Popen(cmd, env=self.command_env, cwd=self.command_cwd, stdout=DEVNULL, stderr=DEVNULL)
                    self.monitors["localServerState"] = True

            else:
                # Stop local server
                if self.server_proc:
                    self.server_proc.terminate()
                    self.server_proc = None
                    self.monitors["localServerState"] = False
        elif zctrl.symbol == "Connect":
            if zctrl.value:
                self.connect(self.preset[0])
            else:
                self.disconnect()
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
        banks = []
        for b in cls.get_bank_list(cls):
            if b[2]:
                banks.append({
                    'text': b[2],
                    'name': b[2],
                    'fullpath': b[0],
                    'raw': b,
                    'readonly': False
                })
        return banks

    @classmethod
    def zynapi_get_presets(cls, bank):
        presets = []
        try:
            with open(cls.PRESET_FILE, "r") as f:
                user_presets = json.load(f)
            for server, name in user_presets[bank["name"]].items():
                presets.append({
                    'text': name,
                    'name': name,
                    'fullpath': f'{bank["name"]}/{server}',
                    'raw': [bank["name"], server, name],
                    'readonly': False
                })
        except Exception as e:
            logging.warning(e)
        return presets

    @classmethod
    def zynapi_new_bank(cls, bank_name):
        try:
            with open(cls.PRESET_FILE, "r") as f:
                user_presets = json.load(f)
            if bank_name in user_presets:
                return
            user_presets[bank_name] = {}
        except:
            user_presets = {bank_name:{}}
        with open(cls.PRESET_FILE, 'w') as f:
            json.dump(user_presets, f)

    @classmethod
    def zynapi_rename_bank(cls, bank_name, new_bank_name):
        try:
            with open(cls.PRESET_FILE, "r") as f:
                user_presets = json.load(f)
            if bank_name in user_presets:
                user_presets[new_bank_name] = user_presets.pop(bank_name)
            with open(cls.PRESET_FILE, 'w') as f:
                json.dump(user_presets, f)
        except:
            pass

    @classmethod
    def zynapi_remove_bank(cls, bank_name):
        try:
            with open(cls.PRESET_FILE, "r") as f:
                user_presets = json.load(f)
            if bank_name in user_presets:
                user_presets.pop(bank_name)
            with open(cls.PRESET_FILE, 'w') as f:
                json.dump(user_presets, f)
        except:
            pass

    @classmethod
    def zynapi_rename_preset(cls, preset_id, name):
        bank, server = preset_id.split('/', 1)
        cls.rename_preset(cls, [bank], [server], name)

    @classmethod
    def zynapi_download(cls, preset_id):
        bank, server = preset_id.split('/', 1)
        try:
            with open(cls.PRESET_FILE, "r") as f:
                user_presets = json.load(f)
            name = user_presets[bank][server]
            filename = f'/tmp/{name}.jamulus'
            with open(filename, 'w') as f:
                f.write(f"server={server}\n")
                f.write(f"name={name}\n")
            return filename
        except Exception as e:
            logging.warning(e)

    @classmethod
    def zynapi_get_formats(cls):
        return "jamulus"

    @classmethod
    def zynapi_install(cls, dpath, bank_name):
        with open(dpath, 'r') as f:
            lines = f.readlines()
        for line in lines:
            key, value = line.strip().split("=", 1)
            if key.lower() == "server":
               server = value
            elif key.lower() == "name":
               name = value
        try:
            new_preset = [server, True, name]
        except:
            logging.warning("Bad jamulus preset file format")
            return

        try:
            with open(cls.PRESET_FILE, "r") as f:
                user_presets = json.load(f)
        except Exception as e:
            user_presets = {}
        if not bank_name:
            try:
                bank_name = list(user_presets)[0]
            except:
                bank_name = "Default"
        if bank_name not in user_presets:
            user_presets[bank_name] = {}
        user_presets[bank_name][new_preset[0]] = new_preset[2]
        with open(zynthian_engine_jamulus.PRESET_FILE, 'w') as f:
            json.dump(user_presets, f)

    @classmethod
    def zynapi_remove_preset(cls, preset_id):
        try:
            bank, server = preset_id.split('/', 1)
            cls.delete_preset(cls, [bank], [server])
        except Exception as e:
            logging.warning(e)

    @classmethod
    def zynapi_get_description(cls):
        return "Low latency online audio collaboration."
