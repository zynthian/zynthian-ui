# -*- coding: utf-8 -*-
# ******************************************************************************
# ZYNTHIAN PROJECT: Zynthian Engine (zynthian_engine_carla)
#
# zynthian_engine implementation for the Carla Plugin Host
#
# One headless Carla instance (zynthian_carla_host.py, JACK "multiple clients" mode)
# is shared by all the processors using this engine. Every processor loads one Carla
# plugin, that gets its own JACK client, so it can be routed like any other
# processor. This is the same model used by zynthian_engine_zynaddsubfx, where
# several processors (parts) live in the same engine instance.
#
# Feature set (mirrors zynthian_engine_jalv):
#   - controllers and controller screens generated from the plugin parameters
#   - native / jack-routing bypass for audio effects
#   - parameter feedback from the plugin and output parameter monitors
#   - banks and presets: plugin programs, MIDI programs and user presets
#     (save, rename, delete, user banks), favorites
#   - optional native plugin GUI (remote display)
#   - crash recovery of the host process
#   - plugin state stored in snapshots (extended config)
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
# ******************************************************************************

import os
import re
import sys
import json
import zlib
import time
import base64
import shutil
import socket
import logging
import tempfile
import traceback
from threading import Thread, Event, Lock, Timer
from subprocess import Popen, PIPE

import zynautoconnect
from zyncoder.zyncore import lib_zyncore
from zyngine.zynthian_engine import zynthian_engine
from zyngine.zynthian_controller import zynthian_controller

# ------------------------------------------------------------------------------
# Constants
# ------------------------------------------------------------------------------

# Carla parameter hints and types (see CarlaBackend.h)
PARAMETER_IS_BOOLEAN = 0x001
PARAMETER_IS_INTEGER = 0x002
PARAMETER_IS_LOGARITHMIC = 0x004
PARAMETER_IS_ENABLED = 0x010
PARAMETER_IS_READ_ONLY = 0x040
PARAMETER_INPUT = 1
PARAMETER_OUTPUT = 2

PLUGIN_OPTION_USE_CHUNKS = 0x008

CARLA_HOST_SCRIPT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "zynthian_carla_host.py")

PRESET_EXT = ".carxs"
LAYOUT_DIR = os.environ.get("ZYNTHIAN_CONFIG_DIR", "/zynthian/config") + "/carla/layouts"
CONTROL_SOCKET = os.environ.get("ZYNTHIAN_CARLA_SOCKET", "/tmp/zynthian-carla.sock")
HOST_CALL_TIMEOUT = 15
HOST_LOAD_TIMEOUT = 180
DETACH_GRACE_TIME = 3.0

STATELESS_TYPES = ("LADSPA", "DSSI", "INTERNAL")



def lv2_node_uri(node):
    try:
        if node.is_uri():
            return str(node.as_uri())
    except Exception:
        pass
    return str(node).strip("<>")


def sanitize_text(text):
    bad_chars = ['.', ',', ';', ':', '!', '*', '+', '?', '@', '&', '$', '%', '=',
                 '"', '\'', '`', '/', '\\', '^', '<', '>', '[', ']', '(', ')', '{', '}']
    for i in bad_chars:
        text = text.replace(i, ' ')
    text = '_'.join(text.split())
    text = '_'.join(filter(None, text.split('_')))
    return text


# ------------------------------------------------------------------------------
# Per-plugin data
# ------------------------------------------------------------------------------

class carla_plugin:

    def __init__(self, engine, processor):
        self.engine = engine
        self.processor = processor
        self.eng_code = processor.eng_code
        self.eng_info = processor.eng_info
        self.carla = self.eng_info.get("CARLA", {})
        self.title = self.eng_info["NAME"]
        self.key = sanitize_text(self.eng_code[3:] if self.eng_code.startswith("CA/") else self.eng_code)
        self.plugin_dir = f"{engine.presets_root}/{self.key}"

        self.h = None                # Handle of the plugin in the host process
        self.jackname = None
        self.loaded = False
        self.detached = False
        self.unload_timer = None
        self.desc = {}
        self.has_ui = False
        self.stateful = False

        self.params = {}
        self.zctrls = {}
        self.path_zctrls = []
        self.path_props = {}
        self.index2symbol = {}
        self.monitors = {}
        self.monitor_symbols = {}
        self.programs = []
        self.midi_programs = []

        self.midi_ctrls = []
        self.midi_ctrl_screens = []
        self._ctrl_screens = []
        self.bypass_zctrl = None
        self.custom_gui_fpath = None
        self.gui_shown = False
        self.gui_pos = None

        self.proxy = carla_processor_engine(engine, self)

    # ---------------------------------------------------------------------------
    # Engine interface used by the zynthian core (through the proxy)
    # ---------------------------------------------------------------------------

    @property
    def name(self):
        return self.title

    def get_jackname(self):
        return self.jackname

    def get_monitors_dict(self):
        if self.loaded and self.monitor_symbols and self.h is not None:
            self.engine.host_request("monitors", self._cb_monitors, h=self.h)
        return self.monitors

    def _cb_monitors(self, resp):
        if resp.get("ok"):
            for sidx, val in resp["res"]["values"].items():
                symbol = self.monitor_symbols.get(int(sidx))
                if symbol:
                    self.monitors[symbol] = val

    # ---------------------------------------------------------------------------
    # Native GUI
    # ---------------------------------------------------------------------------

    def can_show_gui(self):
        return self.loaded and self.has_ui and self.engine.remote_display

    def show_gui(self, show=True):
        # Show or hide the plugin's native GUI window
        if self.can_show_gui():
            self.engine.host_send("show_ui", h=self.h, show=bool(show), pos=self.gui_pos)
            self.set_gui_state(show)

    def toggle_gui(self):
        self.show_gui(not self.gui_shown)

    def set_gui_state(self, shown):
        # Called when the host reports the window was shown/hidden, e.g. manually closed
        self.gui_shown = bool(shown)

    def get_preset_options(self, preset):
        options = {}
        if self.can_show_gui():
            if self.gui_shown:
                options["Hide plugin GUI"] = [False, ["Hide the native plugin GUI", "info.png"]]
            else:
                options["Show plugin GUI"] = [True, ["Show the native plugin GUI", "info.png"]]
        return options

    def preset_options_cb(self, option, preset):
        if option.endswith("plugin GUI"):
            self.show_gui(option.startswith("Show"))

    # ---------------------------------------------------------------------------
    # User banks and presets (files saved with the plugin's state)
    # ---------------------------------------------------------------------------

    def get_user_bank_urid(self, bank_name):
        return f"{self.plugin_dir}/{sanitize_text(bank_name)}"

    def create_user_bank(self, bank_name):
        os.makedirs(self.get_user_bank_urid(bank_name), exist_ok=True)

    def rename_user_bank(self, bank, new_bank_name):
        if self.engine.is_preset_user(bank):
            try:
                new_path = self.get_user_bank_urid(new_bank_name)
                if new_path != bank[0]:
                    os.rename(bank[0], new_path)
            except Exception as e:
                logging.error(e)

    def delete_user_bank(self, bank):
        if self.engine.is_preset_user(bank):
            try:
                shutil.rmtree(bank[0])
            except Exception as e:
                logging.error(e)

    def _bank_dir(self, bank):
        try:
            if bank and bank[0] and self.engine.is_preset_user(bank):
                return bank[0]
            if bank and bank[0] == self.plugin_dir:
                return self.plugin_dir
        except Exception:
            pass
        return self.plugin_dir

    def preset_exists(self, bank, preset_name):
        return os.path.isfile(f"{self._bank_dir(bank)}/{sanitize_text(preset_name)}{PRESET_EXT}")

    def save_preset(self, bank, preset_name):
        if not self.loaded:
            return None
        dpath = self._bank_dir(bank)
        os.makedirs(dpath, exist_ok=True)
        fpath = f"{dpath}/{sanitize_text(preset_name)}{PRESET_EXT}"
        try:
            self.engine.host_call("save_state", h=self.h, path=fpath)
        except Exception as e:
            logging.error(f"Can't save preset '{preset_name}' => {e}")
            return None
        return fpath

    def rename_preset(self, bank, preset, new_preset_name):
        if self.engine.is_preset_user(preset):
            try:
                new_path = f"{os.path.dirname(preset[0])}/{sanitize_text(new_preset_name)}{PRESET_EXT}"
                if new_path != preset[0]:
                    os.rename(preset[0], new_path)
            except Exception as e:
                logging.error(e)

    def delete_preset(self, bank, preset):
        dpath = os.path.dirname(preset[0]) if self.engine.is_preset_user(preset) else None
        if dpath:
            try:
                os.remove(preset[0])
            except Exception as e:
                logging.error(e)
            n = len([f for f in os.listdir(dpath) if f.endswith(PRESET_EXT)])
            if n == 0 and dpath != self.plugin_dir:
                try:
                    shutil.rmtree(dpath)
                except Exception as e:
                    logging.error(e)
            return n
        return 0


# ------------------------------------------------------------------------------
# Per-processor view of the engine
# ------------------------------------------------------------------------------

class carla_processor_engine:

    _per_plugin = ("name", "jackname", "get_jackname", "bypass_zctrl", "_ctrl_screens", "custom_gui_fpath",
                   "get_monitors_dict", "get_preset_options", "preset_options_cb",
                   "get_user_bank_urid", "create_user_bank", "rename_user_bank", "delete_user_bank",
                   "preset_exists", "save_preset", "rename_preset", "delete_preset")

    def __init__(self, engine, plugin):
        object.__setattr__(self, "_engine", engine)
        object.__setattr__(self, "_plugin", plugin)

    def __getattr__(self, name):
        if name in carla_processor_engine._per_plugin:
            return getattr(self._plugin, name)
        return getattr(self._engine, name)


# ------------------------------------------------------------------------------
# Carla Engine Class
# ------------------------------------------------------------------------------

class zynthian_engine_carla(zynthian_engine):

    # ---------------------------------------------------------------------------
    # Config variables
    # ---------------------------------------------------------------------------

    presets_root = zynthian_engine.my_data_dir + "/presets/carla"

    default_synth_ctrls = [['modulation wheel', 1, 0]]
    default_synth_ctrl_screens = [['MIDI Controllers', ['modulation wheel']]]

    # ----------------------------------------------------------------------------
    # ZynAPI variables
    # ----------------------------------------------------------------------------

    zynapi_instance = None
    zynapi_eng_code = None

    # ----------------------------------------------------------------------------
    # Initialization
    # ----------------------------------------------------------------------------

    _instance = None
    _instance_lock = Lock()

    def __new__(cls, state_manager=None, *args, **kwargs):
        with cls._instance_lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
            return cls._instance

    def __init__(self, state_manager=None):
        if self.__dict__.get("_initialized"):
            return
        self._initialized = True
        super().__init__(state_manager)

        self.name = "Carla"
        self.nickname = "CA"
        self.jackname = "zynthian-carla"
        self.type = "Special"

        self.plugins = {}
        self.plugins_by_handle = {}
        self.saved_states = {}

        self.proc = None
        self.proc_exit = False
        self.proc_poll_thread = None
        self.proc_err_thread = None
        self.host_ready = Event()
        self.host_error = None
        self.host_sample_rate = None
        self.host_buffer_size = None
        self.restart_times = []
        self.restart_lock = Lock()
        self.control_sock = None
        self.control_thread = None

        self.pending_calls = {}
        self.next_call_id = 0
        self.call_lock = Lock()
        self.write_lock = Lock()

        forced_display = os.environ.get("ZYNTHIAN_CARLA_DISPLAY")
        self.remote_display = self.config_remote_display()
        if forced_display:
            self.remote_display = forced_display
            self.command_env['DISPLAY'] = forced_display
        elif not self.remote_display and os.environ.get("DISPLAY"):
            self.remote_display = os.environ["DISPLAY"]
            self.command_env['DISPLAY'] = self.remote_display
        if not self.remote_display:
            # Some plugins need a display variable to start headless, so give them a fake one
            self.command_env['DISPLAY'] = "X"

        self.command = [sys.executable or "python3", CARLA_HOST_SCRIPT, "--name", self.jackname]
        self.command_cwd = zynthian_engine.my_data_dir + "/presets"

        logging.debug("CREATING CARLA ENGINE")
        try:
            self.start()
        except Exception as e:
            logging.error(f"Can't start Carla host => {e}")
        self.reset()

    # ---------------------------------------------------------------------------
    # Host process management & IPC
    # ---------------------------------------------------------------------------

    def start(self):
        if self.proc:
            return
        logging.info("Starting Engine {}".format(self.name))
        logging.debug("Command: {}".format(self.command))
        self.proc_exit = False
        self.host_ready.clear()
        self.host_error = None
        self.proc = Popen(self.command, env=self.command_env, cwd=self.command_cwd, shell=False,
                          text=True, bufsize=1, stdin=PIPE, stdout=PIPE, stderr=PIPE)
        self.proc_poll_thread = Thread(target=self.proc_poll_thread_task, args=(self.proc,),
                                       name="proc_poll_carla", daemon=True)
        self.proc_poll_thread.start()
        self.proc_err_thread = Thread(target=self.proc_err_thread_task, args=(self.proc,),
                                      name="proc_err_carla", daemon=True)
        self.proc_err_thread.start()
        if not self.host_ready.wait(30) or self.host_error:
            err = self.host_error or "timeout waiting for the Carla host"
            self.kill_host()
            raise RuntimeError(err)
        self.start_control_server()

    def stop(self):
        with self._instance_lock:
            if zynthian_engine_carla._instance is self:
                zynthian_engine_carla._instance = None
        self.proc_exit = True
        self.stop_control_server()
        for plugin in list(self.plugins.values()):
            if plugin.unload_timer:
                plugin.unload_timer.cancel()
        if self.proc:
            logging.info("Stopping Engine " + self.name)
            proc = self.proc
            try:
                self.host_send("quit")
                proc.wait(timeout=8)
            except Exception as e:
                logging.warning(f"Carla host can't be stopped gracefully. Killing it! => {e}")
                self.kill_host()
            self.proc = None
        self.plugins_by_handle = {}
        self.fail_pending_calls("engine stopped")

    def kill_host(self):
        proc = self.proc
        self.proc = None
        if proc:
            try:
                proc.kill()
                proc.wait(timeout=3)
            except Exception:
                pass

    # ---------------------------------------------------------------------------
    # Desktop control socket: lets an external app (zynthian_carla_gui.py) list the hosted
    # plugins and show/hide their native GUIs.
    # ---------------------------------------------------------------------------

    def start_control_server(self):
        if self.control_sock:
            return
        path = CONTROL_SOCKET
        try:
            if os.path.exists(path):
                os.unlink(path)
            sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            sock.bind(path)
            os.chmod(path, 0o600)
            sock.listen(4)
        except Exception as e:
            logging.error(f"Can't create the Carla control socket {path} => {e}")
            return
        self.control_sock = sock
        self.control_thread = Thread(target=self.control_thread_task, args=(sock,),
                                     name="carla_control", daemon=True)
        self.control_thread.start()

    def stop_control_server(self):
        sock = self.control_sock
        self.control_sock = None
        if sock:
            try:
                sock.close()
            except Exception:
                pass
            try:
                os.unlink(CONTROL_SOCKET)
            except Exception:
                pass

    def control_thread_task(self, sock):
        while self.control_sock is sock:
            try:
                conn, _ = sock.accept()
            except Exception:
                break
            Thread(target=self.control_client_task, args=(conn,), name="carla_control_client",
                   daemon=True).start()

    def control_client_task(self, conn):
        try:
            conn.settimeout(60)
            with conn, conn.makefile("rw") as f:
                for line in f:
                    try:
                        resp = {"ok": True, "res": self.control_command(json.loads(line))}
                    except Exception as e:
                        resp = {"ok": False, "err": str(e)}
                    f.write(json.dumps(resp) + "\n")
                    f.flush()
        except Exception as e:
            logging.debug(f"Carla control client closed => {e}")

    def control_list(self):
        res = []
        for processor, plugin in list(self.plugins.items()):
            if plugin.detached or not plugin.loaded:
                continue
            res.append({
                "id": processor.id,
                "name": plugin.title,
                "jackname": plugin.jackname,
                "has_gui": bool(plugin.can_show_gui()),
                "shown": bool(plugin.gui_shown)
            })
        return sorted(res, key=lambda x: x["id"])

    def control_command(self, msg):
        cmd = msg.get("cmd")
        if cmd == "list":
            return self.control_list()
        if cmd == "layout":
            for processor, plugin in list(self.plugins.items()):
                if processor.id == msg.get("id") and plugin.loaded:
                    return {"key": plugin.key, "file": f"{LAYOUT_DIR}/{plugin.key}.json",
                            "layout": self.get_layout_template(plugin)}
            raise RuntimeError("Unknown plugin id")
        if cmd in ("show", "hide", "toggle"):
            for processor, plugin in list(self.plugins.items()):
                if processor.id == msg.get("id"):
                    if not plugin.can_show_gui():
                        raise RuntimeError("The plugin has no native GUI or there is no display")
                    plugin.show_gui(not plugin.gui_shown if cmd == "toggle" else cmd == "show")
                    return {"shown": plugin.gui_shown}
            raise RuntimeError("Unknown plugin id")
        raise RuntimeError(f"Unknown command '{cmd}'")

    def host_write(self, obj):
        line = json.dumps(obj, separators=(",", ":")) + "\n"
        with self.write_lock:
            self.proc.stdin.write(line)
            self.proc.stdin.flush()

    def host_send(self, cmd, **args):
        # Fire and forget (no response)
        if not self.proc:
            return
        try:
            self.host_write({"cmd": cmd, **args})
        except Exception as e:
            logging.debug(f"Can't send '{cmd}' to the Carla host => {e}")

    def host_request(self, cmd, callback, **args):
        # Asynchronous request. The callback is executed in the polling thread
        if not self.proc:
            return
        with self.call_lock:
            self.next_call_id += 1
            call_id = self.next_call_id
            self.pending_calls[call_id] = {"cb": callback}
        try:
            self.host_write({"id": call_id, "cmd": cmd, **args})
        except Exception as e:
            self.pending_calls.pop(call_id, None)
            logging.debug(f"Can't send '{cmd}' to the Carla host => {e}")

    def host_call(self, cmd, timeout=HOST_CALL_TIMEOUT, **args):
        # Synchronous request. Never call this from the polling thread!
        if not self.proc:
            raise RuntimeError("Carla host is not running")
        slot = {"ev": Event()}
        with self.call_lock:
            self.next_call_id += 1
            call_id = self.next_call_id
            self.pending_calls[call_id] = slot
        try:
            self.host_write({"id": call_id, "cmd": cmd, **args})
            if not slot["ev"].wait(timeout):
                raise TimeoutError(f"Carla host didn't respond to '{cmd}'")
        finally:
            self.pending_calls.pop(call_id, None)
        resp = slot["resp"]
        if not resp.get("ok"):
            raise RuntimeError(resp.get("err", "unknown error"))
        return resp.get("res")

    def fail_pending_calls(self, err):
        for call_id, slot in list(self.pending_calls.items()):
            resp = {"ok": False, "err": err}
            slot["resp"] = resp
            if "ev" in slot:
                slot["ev"].set()
            elif "cb" in slot:
                try:
                    slot["cb"](resp)
                except Exception:
                    pass
        self.pending_calls.clear()

    def proc_err_thread_task(self, proc):
        try:
            for line in proc.stderr:
                line = line.rstrip()
                if line:
                    logging.debug(f"CARLA > {line}")
        except Exception:
            pass

    def proc_poll_thread_task(self, proc):
        try:
            for line in proc.stdout:
                line = line.strip()
                if line:
                    try:
                        self.proc_poll_parse_line(line)
                    except Exception:
                        logging.error(f"Error parsing Carla host output '{line[:200]}' => {traceback.format_exc()}")
        except Exception as e:
            logging.debug(f"Carla host output closed => {e}")
        if proc is self.proc and not self.proc_exit:
            logging.error("Carla host process has died!")
            self.host_error = self.host_error or "Carla host process has died"
            self.host_ready.set()
            self.fail_pending_calls("Carla host process has died")
            Thread(target=self.restart_host, name="carla_restart", daemon=True).start()

    def proc_poll_parse_line(self, line):
        msg = json.loads(line)
        if "id" in msg:
            slot = self.pending_calls.pop(msg["id"], None)
            if slot:
                slot["resp"] = msg
                if "ev" in slot:
                    slot["ev"].set()
                else:
                    try:
                        slot["cb"](msg)
                    except Exception:
                        logging.error(traceback.format_exc())
            return

        evt = msg.get("evt")
        if evt == "params":
            plugin = self.plugins_by_handle.get(msg["h"])
            if plugin:
                self.update_zctrls(plugin, msg["v"])
        elif evt == "ready":
            self.host_sample_rate = msg.get("sample_rate")
            self.host_buffer_size = msg.get("buffer_size")
            self.host_ready.set()
        elif evt == "fatal":
            logging.error(f"Carla host failed => {msg.get('msg')}")
            self.host_error = msg.get("msg")
            self.host_ready.set()
        elif evt == "log":
            level = {"error": logging.ERROR, "warning": logging.WARNING}.get(msg.get("level"), logging.DEBUG)
            logging.log(level, f"CARLA > {msg.get('msg')}")
        elif evt == "ui":
            plugin = self.plugins_by_handle.get(msg["h"])
            if plugin:
                plugin.set_gui_state(msg.get("state") == 1)
        elif evt == "ui_pos":
            plugin = self.plugins_by_handle.get(msg["h"])
            if plugin:
                plugin.gui_pos = [msg["x"], msg["y"]]
        elif evt == "reload":
            plugin = self.plugins_by_handle.get(msg["h"])
            if plugin:
                Thread(target=self.reload_plugin, args=(plugin,), name="carla_reload", daemon=True).start()
        elif evt == "unavailable":
            logging.error(f"Carla plugin is not available => {msg.get('msg')}")
        elif evt in ("program", "midi_program", "engine_stopped"):
            logging.debug(f"CARLA EVENT => {msg}")

    def restart_host(self):
        # Recover from a crash of the host, e.g. a misbehaving plugin
        with self.restart_lock:
            now = time.monotonic()
            self.restart_times = [t for t in self.restart_times if now - t < 120]
            if len(self.restart_times) >= 3:
                logging.error("Carla host is crashing too often. Not restarting it!")
                return
            self.restart_times.append(now)
            logging.warning("Restarting Carla host ...")

            self.kill_host()
            self.plugins_by_handle = {}
            plugins = [p for p in self.plugins.values() if p.loaded and not p.detached]
            states = {}
            for plugin in plugins:
                try:
                    states[plugin] = plugin.processor.get_state()
                except Exception as e:
                    logging.error(e)
                plugin.loaded = False
                plugin.h = None
            try:
                self.start()
            except Exception as e:
                logging.error(f"Can't restart Carla host => {e}")
                return
            for plugin in plugins:
                try:
                    if self.load_plugin(plugin, rebuild=False):
                        if plugin in states:
                            plugin.processor.set_state(states[plugin])
                except Exception:
                    logging.error(traceback.format_exc())
            zynautoconnect.request_audio_connect()
            zynautoconnect.request_midi_connect()

    # ---------------------------------------------------------------------------
    # Processor Management
    # ---------------------------------------------------------------------------

    def add_processor(self, processor):
        plugin = self.plugins.get(processor)
        if plugin:
            if plugin.unload_timer:
                plugin.unload_timer.cancel()
                plugin.unload_timer = None
            plugin.detached = False
            if processor not in self.processors:
                self.processors.append(processor)
            processor.jackname = plugin.jackname
            processor.engine = plugin.proxy
            self.set_midi_chan(processor)
            zynautoconnect.add_sidechain_ports(plugin.jackname)
            return

        plugin = carla_plugin(self, processor)
        self.plugins[processor] = plugin
        processor.engine = plugin.proxy
        self.set_midi_chan(processor)
        self.processors.append(processor)

        if self.load_plugin(plugin):
            processor.jackname = plugin.jackname
            zynautoconnect.add_sidechain_ports(plugin.jackname)
            self.set_midi_chan(processor)
        else:
            logging.error(f"Carla plugin '{plugin.title}' couldn't be loaded!")
            processor.jackname = None
            processor.refresh_controllers()

    def remove_processor(self, processor):
        plugin = self.plugins.get(processor)
        try:
            self.processors.remove(processor)
        except ValueError:
            logging.error(f"Processor {processor.get_name()} not found in engine's processors list")
        if not plugin:
            return
        zynautoconnect.remove_sidechain_ports(plugin.jackname)
        processor.jackname = None
        plugin.detached = True
        plugin.unload_timer = Timer(DETACH_GRACE_TIME, self.unload_detached_plugin, args=(processor,))
        plugin.unload_timer.daemon = True
        plugin.unload_timer.start()

    def unload_detached_plugin(self, processor):
        plugin = self.plugins.get(processor)
        if not plugin or not plugin.detached:
            return
        logging.debug(f"Unloading Carla plugin {plugin.jackname}")
        if plugin.loaded and plugin.h is not None:
            self.plugins_by_handle.pop(plugin.h, None)
            try:
                self.host_call("remove_plugin", h=plugin.h)
            except Exception as e:
                logging.error(f"Can't remove Carla plugin {plugin.jackname} => {e}")
        plugin.loaded = False
        self.plugins.pop(processor, None)

    def get_name(self, processor=None):
        try:
            return self.plugins[processor].title
        except Exception:
            return self.name

    def get_path(self, processor=None):
        return self.get_name(processor)

    # ---------------------------------------------------------------------------
    # Plugin loading
    # ---------------------------------------------------------------------------

    def get_plugin_jackname(self, plugin):
        if plugin.jackname:
            return plugin.jackname
        base = re.sub(r'[^A-Za-z0-9_\-]', '_', plugin.title)
        base = re.sub(r'_{2,}', '_', base).strip('_')[:40] or "Carla_Plugin"
        return self.chain_manager.get_next_jackname(base)

    def load_plugin(self, plugin, rebuild=True):
        carla = plugin.carla
        if not carla:
            logging.error(f"Engine '{plugin.eng_code}' has no Carla plugin info!")
            return False
        if not self.proc:
            try:
                self.start()
            except Exception as e:
                logging.error(f"Can't start Carla host => {e}")
                return False
        jackname = self.get_plugin_jackname(plugin)
        try:
            desc = self.host_call("add_plugin", timeout=HOST_LOAD_TIMEOUT,
                                  type=carla.get("type"), filename=carla.get("filename"),
                                  label=carla.get("label"), uid=carla.get("uid", 0),
                                  build=carla.get("build"), name=jackname)
        except Exception as e:
            logging.error(f"Can't load Carla plugin '{plugin.title}' => {e}")
            return False

        plugin.h = desc["h"]
        plugin.desc = desc
        plugin.jackname = desc.get("name") or jackname
        plugin.has_ui = bool(desc.get("has_ui"))
        plugin.programs = desc.get("programs", [])
        plugin.midi_programs = desc.get("midi_programs", [])
        plugin.stateful = str(carla.get("type", "")).upper() not in STATELESS_TYPES or \
            bool(desc.get("options_enabled", 0) & PLUGIN_OPTION_USE_CHUNKS)
        plugin.loaded = True
        plugin.detached = False
        logging.info(f"Loaded Carla plugin '{plugin.title}' => JACK client '{plugin.jackname}'")

        if rebuild:
            self.setup_plugin_controllers(plugin)
        else:
            self.map_plugin_params(plugin, desc)
        self.plugins_by_handle[plugin.h] = plugin

        if rebuild:
            plugin.processor.refresh_controllers()
        self.set_midi_chan(plugin.processor)
        return True

    def reload_plugin(self, plugin):
        try:
            desc = self.host_call("get_info", h=plugin.h)
            plugin.desc = desc
            plugin.programs = desc.get("programs", [])
            plugin.midi_programs = desc.get("midi_programs", [])
            self.setup_plugin_controllers(plugin)
            plugin.processor.refresh_controllers()
            plugin.processor.init_ctrl_screens(force_refresh=True)
        except Exception as e:
            logging.error(f"Can't reload Carla plugin '{plugin.title}' => {e}")

    # ---------------------------------------------------------------------------
    # MIDI Channel Management
    # ---------------------------------------------------------------------------

    def has_midi_out(self, processor):
        plugin = self.plugins.get(processor)
        return bool(plugin and plugin.loaded and plugin.desc.get("midi_outs"))

    def set_midi_chan(self, processor):
        processor.midi_chan_engine = processor.midi_chan
        plugin = self.plugins.get(processor)
        if plugin and plugin.loaded and isinstance(processor.midi_chan, int) and 0 <= processor.midi_chan < 16:
            self.host_send("set_ctrl_channel", h=plugin.h, chan=processor.midi_chan)

    # ----------------------------------------------------------------------------
    # Bank Management
    # ----------------------------------------------------------------------------

    def get_bank_list(self, processor=None):
        plugin = self.plugins.get(processor)
        if not plugin:
            return [("", None, "None", None)]
        bank_list = []

        try:
            if any(n.endswith(PRESET_EXT) for n in os.listdir(plugin.plugin_dir)):
                bank_list.append((plugin.plugin_dir, None, "User", None))
            for name in sorted(os.listdir(plugin.plugin_dir), key=str.casefold):
                dpath = f"{plugin.plugin_dir}/{name}"
                if os.path.isdir(dpath):
                    bank_list.append((dpath, None, name.replace("_", " "), None))
        except FileNotFoundError:
            pass
        except Exception as e:
            logging.error(e)

        if plugin.programs:
            bank_list.append((f"carla:{plugin.key}:prog", None, "Programs", None))
        if plugin.carla.get("type") != "LV2":
            for bank in sorted({b for b, p, n in plugin.midi_programs}):
                names = [n for b, p, n in plugin.midi_programs if b == bank]
                if plugin.programs and names == list(plugin.programs):
                    continue
                bank_list.append((f"carla:{plugin.key}:midibank:{bank}", None, f"MIDI Bank {bank}", None))
        if not bank_list:
            bank_list.append(("", None, "None", None))
        return bank_list

    def set_bank(self, processor, bank):
        return True

    def is_preset_user(self, preset):
        try:
            path = preset[0]
            if not isinstance(path, str) or not path.startswith(self.presets_root + "/"):
                return False
            parts = os.path.relpath(path, self.presets_root).split(os.sep)
            if path.endswith(PRESET_EXT):
                return True
            return len(parts) == 2
        except Exception:
            return False

    # ----------------------------------------------------------------------------
    # Preset Management
    # ----------------------------------------------------------------------------

    def get_preset_list(self, bank, processor=None):
        preset_list = []
        plugin = self.plugins.get(processor)
        try:
            bank_id = bank[0]
            if plugin and bank_id == f"carla:{plugin.key}:prog":
                for i, name in enumerate(plugin.programs):
                    preset_list.append([f"carla:{plugin.key}:prog:{i}", None, name or f"Program {i + 1}", bank_id])
            elif plugin and bank_id.startswith(f"carla:{plugin.key}:midibank:"):
                mbank = int(bank_id.rsplit(":", 1)[1])
                for b, p, name in plugin.midi_programs:
                    if b == mbank:
                        preset_list.append([f"carla:{plugin.key}:midi:{b}:{p}", None, name or f"Program {p + 1}", bank_id])
            elif bank_id and os.path.isdir(bank_id):
                for fname in sorted(os.listdir(bank_id), key=str.casefold):
                    if fname.endswith(PRESET_EXT):
                        title = fname[:-len(PRESET_EXT)].replace("_", " ").strip()
                        preset_list.append([f"{bank_id}/{fname}", None, title, bank_id])
        except Exception as e:
            logging.error(e)
        if not preset_list:
            preset_list.append(("", None, "", None))
        return preset_list

    def set_preset(self, processor, preset, preload=False):
        plugin = self.plugins.get(processor)
        if not plugin or not plugin.loaded or not preset[0]:
            return False
        preset_id = preset[0]
        try:
            if preset_id.startswith(f"carla:{plugin.key}:prog:"):
                res = self.host_call("program", h=plugin.h, index=int(preset_id.rsplit(":", 1)[1]))
            elif preset_id.startswith(f"carla:{plugin.key}:midi:"):
                parts = preset_id.split(":")
                bank, prog = int(parts[-2]), int(parts[-1])
                index = None
                for i, (b, p, name) in enumerate(plugin.midi_programs):
                    if b == bank and p == prog:
                        index = i
                        break
                if index is None:
                    raise ValueError(f"MIDI program {bank}:{prog} not found")
                res = self.host_call("midi_program", h=plugin.h, index=index)
            elif preset_id.endswith(PRESET_EXT):
                res = self.host_call("load_state", timeout=HOST_LOAD_TIMEOUT, h=plugin.h, path=preset_id)
            else:
                return False
        except Exception as e:
            logging.error(f"Can't set preset '{preset[2]}' => {e}")
            return False
        self.update_zctrls(plugin, res.get("values", {}), check_ignore=False)
        return True

    def cmp_presets(self, preset1, preset2):
        try:
            return preset1[0] == preset2[0]
        except Exception:
            return False

    def get_preset_favs(self, processor):
        favs = super().get_preset_favs(processor)
        plugin = self.plugins.get(processor)
        if not plugin:
            return favs
        prefix_a = f"carla:{plugin.key}:"
        prefix_b = plugin.plugin_dir + "/"
        return {k: v for k, v in favs.items() if k.startswith(prefix_a) or k.startswith(prefix_b)}

    # ----------------------------------------------------------------------------
    # Controllers Managament
    # ----------------------------------------------------------------------------

    def get_midi_ctrl_info(self, plugin):
        ctrls = []
        screens = []
        module_name = f"zyngine.ctrlinfo.ctrlinfo_{plugin.title}"
        if module_name in sys.modules:
            try:
                ctrls = list(getattr(sys.modules[module_name], "ctrls", None) or [])
                screens = list(getattr(sys.modules[module_name], "ctrl_screens", None) or [])
                logging.info(f"Using custom MIDI controllers file for '{plugin.title}'.")
            except Exception as e:
                logging.error(f"Wrong ctrlinfo module => {e}")
        if not ctrls or not screens:
            ctrls = []
            screens = []
            if plugin.eng_info.get("TYPE") == "MIDI Synth":
                ctrls = [list(c) for c in self.default_synth_ctrls]
                screens = [[s[0], list(s[1])] for s in self.default_synth_ctrl_screens]
        return ctrls, screens

    def unique_symbol(self, p, used):
        symbol = p["symbol"] or sanitize_text(p["name"]) or f"param{p['index']}"
        if symbol in used:
            symbol = f"{symbol}_{p['index']}"
        used.add(symbol)
        return symbol

    def load_layout(self, plugin):
        fpath = f"{LAYOUT_DIR}/{plugin.key}.json"
        try:
            with open(fpath) as f:
                return json.load(f)
        except FileNotFoundError:
            return None
        except Exception as e:
            logging.error(f"Can't read the controller layout {fpath} => {e}")
            return None

    def apply_layout(self, plugin, layout):
        refs = {}
        for p in plugin.desc.get("params", []):
            symbol = plugin.index2symbol.get(p["index"])
            if symbol is None:
                continue
            for key in (p["symbol"], p["name"], symbol):
                if key:
                    refs.setdefault(str(key).casefold(), symbol)
        for symbol, prop in plugin.path_props.items():
            zctrl = plugin.zctrls.get(symbol)
            for key in (prop["uri"], zctrl.name if zctrl else None, symbol):
                if key:
                    refs.setdefault(str(key).casefold(), symbol)

        def find(ref):
            if isinstance(ref, int):
                return plugin.index2symbol.get(ref)
            return refs.get(str(ref).casefold())

        used = set()
        for page in layout.get("pages", []):
            symbols = []
            for ref in page.get("params", []):
                symbol = find(ref)
                if symbol is None:
                    logging.warning(f"Layout of {plugin.title}: parameter '{ref}' not found")
                elif symbol not in used:
                    symbols.append(symbol)
                    used.add(symbol)
            name = page.get("name") or "Params"
            for n in range(0, len(symbols), 4):
                suffix = f" {n // 4 + 1}" if len(symbols) > 4 else ""
                self._ctrl_screens.append([name + suffix, symbols[n:n + 4]])
        for ref in layout.get("hide", []):
            symbol = find(ref)
            if symbol:
                used.add(symbol)
        rest = {k: v for k, v in plugin.zctrls.items() if k not in used}
        if rest and not layout.get("hide_unlisted", False):
            self.generate_ctrl_screens(rest)

    def get_layout_template(self, plugin):
        params = []
        for p in plugin.desc.get("params", []):
            if p["index"] in plugin.index2symbol:
                params.append(p["name"] or p["symbol"] or p["index"])
        return {"pages": [{"name": "Params", "params": params}]}

    def map_plugin_params(self, plugin, desc):
        plugin.params = {p["index"]: p for p in desc.get("params", [])}

    def setup_plugin_controllers(self, plugin):
        desc = plugin.desc
        processor = plugin.processor
        etype = plugin.eng_info.get("TYPE")
        self.map_plugin_params(plugin, desc)

        plugin.midi_ctrls, plugin.midi_ctrl_screens = self.get_midi_ctrl_info(plugin)
        plugin.zctrls = {}
        plugin.index2symbol = {}
        plugin.monitors = {}
        plugin.monitor_symbols = {}
        plugin.bypass_zctrl = None
        plugin.path_zctrls = []
        plugin.path_props = {}

        lv2_ports = self.get_lv2_ports(plugin)
        path_props = self.get_lv2_path_params(plugin, lv2_ports)

        used = set()
        for p in desc.get("params", []):
            if not p["hints"] & PARAMETER_IS_ENABLED:
                continue
            symbol = self.unique_symbol(p, used)
            if p["type"] == PARAMETER_OUTPUT or p["hints"] & PARAMETER_IS_READ_ONLY:
                plugin.monitor_symbols[p["index"]] = symbol
                plugin.monitors[symbol] = p["value"]
                continue
            if p["type"] != PARAMETER_INPUT:
                continue
            try:
                zctrl = self.create_zctrl(plugin, p, symbol)
            except Exception:
                logging.error(f"Can't create controller for parameter '{p['name']}' => {traceback.format_exc()}")
                continue
            lv2_info = lv2_ports.get(p["symbol"])
            if lv2_info:
                self.apply_lv2_port_info(zctrl, lv2_info)
            plugin.zctrls[symbol] = zctrl
            plugin.index2symbol[p["index"]] = symbol

            if etype == "Audio Effect" and plugin.bypass_zctrl is None:
                if lv2_info and lv2_info.get("is_bypass"):
                    zctrl.set_options({"is_bypass": True, "bypass_value": lv2_info["bypass_value"]})
                    plugin.bypass_zctrl = zctrl
                elif symbol.lower() in ("bypass", "enable") or p["name"].lower() in ("bypass", "enable"):
                    zctrl.set_options({"is_bypass": True, "bypass_value": int(not p["value"])})
                    plugin.bypass_zctrl = zctrl

        for n, prop in enumerate(path_props):
            self.add_path_zctrl(plugin, prop, n == 0, used)

        if plugin.bypass_zctrl:
            bz = plugin.bypass_zctrl
            bz.set_options({"short_name": "bypass",
                            "labels": ["inline", "bypass"],
                            "ticks": [int(not bz.bypass_value), bz.bypass_value],
                            "display_priority": 0})
        elif etype == "Audio Effect":
            # No native bypass
            plugin.bypass_zctrl = plugin.zctrls["bypass"] = zynthian_controller(self, 'bypass', {
                'name': "bypass",
                'is_toggle': True,
                'is_bypass': True,
                'bypass_value': 1,
                'value_max': 1,
                'value_default': 0,
                'value': 0,
                'processor': processor,
                'labels': ['inline', 'bypass'],
                'ticks': [0, 1],
                'display_priority': 0
            })

        plugin.gui_shown = False
        plugin.custom_gui_fpath = self.get_custom_gui(plugin)

        self._ctrl_screens = [[s[0], list(s[1])] for s in plugin.midi_ctrl_screens]
        layout = self.load_layout(plugin)
        if layout:
            self.apply_layout(plugin, layout)
        else:
            self.generate_ctrl_screens(plugin.zctrls)
        plugin._ctrl_screens = self._ctrl_screens
        self._ctrl_screens = []

    def get_custom_gui(self, plugin):
        fpath = f"{self.ui_dir}/zyngui/widgets_user/zynthian_widget_{plugin.title.lower().replace(' ', '_')}.py"
        if os.path.isfile(fpath):
            return fpath
        if str(plugin.carla.get("type", "")).upper() == "LV2":
            from zyngine.zynthian_engine_jalv import zynthian_engine_jalv
            return zynthian_engine_jalv.plugins_custom_gui.get(plugin.carla.get("label"))
        return None

    def get_lv2_ports(self, plugin):
        if str(plugin.carla.get("type", "")).upper() != "LV2" or not plugin.carla.get("label"):
            return {}
        try:
            from zyngine import zynthian_lv2
            if getattr(zynthian_lv2, "world", None) is None:
                zynthian_lv2.init_lilv()
            return {info["symbol"]: info for info in zynthian_lv2.get_plugin_ports(plugin.carla["label"])}
        except Exception:
            logging.warning(f"Can't get the LV2 description of <{plugin.carla.get('label')}> => "
                            f"{traceback.format_exc()}")
            return {}

    def apply_lv2_port_info(self, zctrl, info):
        display_priority = info["display_priority"]
        if info.get("group_display_priority", 0) > 0:
            display_priority += 1000000 * info["group_display_priority"]
        opts = {"display_priority": display_priority, "not_on_gui": info["not_on_gui"],
                "envelope": info.get("envelope"), "filter": info.get("filter")}
        if info.get("group_symbol") is not None or info.get("group_name") is not None:
            opts["group_symbol"] = info["group_symbol"]
            opts["group_name"] = info["group_name"]
        zctrl.set_options(opts)

    def get_lv2_path_params(self, plugin, lv2_ports):
        infos = {symbol: info for symbol, info in lv2_ports.items() if info.get("is_path")}
        if not infos:
            return []
        res = []
        try:
            from zyngine import zynthian_lv2
            world = zynthian_lv2.world
            lv2_plugin = world.get_all_plugins()[plugin.carla["label"]]
            for node in world.find_nodes(lv2_plugin.get_uri(), world.ns.patch.writable, None):
                symbol = world.get_symbol(node)
                if symbol in infos:
                    res.append({"uri": lv2_node_uri(node), "symbol": symbol, "info": infos[symbol]})
        except Exception:
            logging.warning(f"Can't get the path properties of <{plugin.carla.get('label')}> => "
                            f"{traceback.format_exc()}")
            return []
        return sorted(res, key=lambda i: i["uri"].encode())

    def add_path_zctrl(self, plugin, prop, primary, used):
        info = prop["info"]
        base = sanitize_text(prop["symbol"]) or "path"
        symbol = base
        i = 1
        while symbol in used:
            symbol = f"{base}_path{i}"
            i += 1
        display_priority = info['display_priority']
        if info.get('group_display_priority', 0) > 0:
            display_priority += 1000000 * info['group_display_priority']
        try:
            zctrl = zynthian_controller(self, symbol, {
                'processor': plugin.processor,
                'name': info['name'],
                'group_symbol': info['group_symbol'],
                'group_name': info['group_name'],
                'value': None,
                'value_default': None,
                'value_min': None,
                'value_max': None,
                'is_toggle': False,
                'is_trigger': False,
                'is_integer': False,
                'is_logarithmic': False,
                'is_path': True,
                'path_file_types': info['path_file_types'],
                'path_preload': info['path_preload'],
                'not_on_gui': info['not_on_gui'],
                'display_priority': display_priority
            })
        except Exception:
            logging.error(f"Can't create controller for path property '{info['name']}' => {traceback.format_exc()}")
            return None
        used.add(symbol)
        plugin.zctrls[symbol] = zctrl
        plugin.path_zctrls.append(zctrl)
        plugin.path_props[symbol] = {"uri": prop["uri"], "primary": primary}
        return symbol

    def create_zctrl(self, plugin, p, symbol):
        hints = p["hints"]
        vmin, vmax, vdef, val = p["min"], p["max"], p["def"], p["value"]
        if vmax <= vmin:
            vmax = vmin + 1.0
        is_integer = bool(hints & PARAMETER_IS_INTEGER)
        is_toggle = bool(hints & PARAMETER_IS_BOOLEAN)
        is_log = bool(hints & PARAMETER_IS_LOGARITHMIC) and vmin > 0
        group = p["group"] or None
        group_name = group
        if group:
            m = re.match(r"^([^\s:]+):(.+)$", group)
            if m:
                group, group_name = m.group(1), m.group(2).strip()
        opts = {
            'processor': plugin.processor,
            'name': p["name"] or symbol,
            'group_symbol': group,
            'group_name': group_name,
            'graph_path': p["index"],
            'is_trigger': False,
            'is_path': False,
            'path_file_types': None,
            'is_bypass': False,
            'bypass_value': 0,
            'not_on_gui': False,
            'display_priority': 0
        }
        sps = sorted(p["scale_points"], key=lambda s: s[0])

        if len(sps) > 1:
            labels = []
            for sp in sps:
                label = sp[1]
                if len(label) > 9:
                    label = camel_split_re.sub(' ', label)
                labels.append(label)
            ticks = [sp[0] for sp in sps]
            opts.update({'value': val, 'labels': labels, 'ticks': ticks, 'value_default': vdef,
                         'value_min': ticks[0], 'value_max': ticks[-1],
                         'is_toggle': is_toggle, 'is_integer': is_integer, 'is_logarithmic': False})
        elif is_toggle:
            sval = 'off' if val == 0 else 'on'
            opts.update({'value': sval, 'labels': ['off', 'on'], 'ticks': [vmin, vmax],
                         'value_default': 'off' if vdef == 0 else 'on',
                         'value_min': vmin, 'value_max': vmax,
                         'is_toggle': True, 'is_integer': is_integer, 'is_logarithmic': False})
        elif is_integer:
            opts.update({'value': int(val), 'value_default': int(vdef),
                         'value_min': int(vmin), 'value_max': int(vmax),
                         'is_toggle': False, 'is_integer': True, 'is_logarithmic': is_log})
        else:
            opts.update({'value': float(val), 'value_default': float(vdef),
                         'value_min': float(vmin), 'value_max': float(vmax),
                         'is_toggle': False, 'is_integer': False, 'is_logarithmic': is_log})
        return zynthian_controller(self, symbol, opts)

    # Get zynthian controllers dictionary.
    # Updates existing processor dictionary.
    def get_controllers_dict(self, processor):
        plugin = self.plugins.get(processor)
        self._ctrls = plugin.midi_ctrls if plugin else []
        zctrls = super().get_controllers_dict(processor)
        self._ctrls = []
        if plugin:
            for zctrl in plugin.zctrls.values():
                zctrl.set_options({"processor": processor})
            zctrls.update(plugin.zctrls)
        return zctrls

    def update_zctrls(self, plugin, values, check_ignore=True):
        # Feedback from the plugin. Keys are Carla parameter indexes (as strings)
        for sidx, val in values.items():
            try:
                idx = int(sidx)
            except ValueError:
                continue
            symbol = plugin.index2symbol.get(idx)
            if symbol is None:
                if idx in plugin.monitor_symbols:
                    plugin.monitors[plugin.monitor_symbols[idx]] = val
                continue
            zctrl = plugin.zctrls.get(symbol)
            if not zctrl:
                continue
            if zctrl.is_path or (check_ignore and zctrl.get_ignore_engine_fb()):
                continue
            try:
                zctrl.set_value(val, False)
            except Exception as e:
                logging.warning(f"Wrong feedback value for controller {symbol} => {val} ({e})")

    def send_controller_value(self, zctrl):
        plugin = self.plugins.get(zctrl.processor)
        if zctrl.midi_cc:
            try:
                lib_zyncore.zmop_send_ccontrol_change(zctrl.processor.chain.zmop_index,
                                                      zctrl.processor.midi_chan_engine,
                                                      zctrl.midi_cc,
                                                      zctrl.get_ctrl_midi_val())
            except Exception as e:
                logging.error(f"Can't send controller '{zctrl.symbol}' with CC{zctrl.midi_cc} => {e}")
        elif plugin and plugin.loaded and zctrl.is_path:
            prop = plugin.path_props.get(zctrl.symbol)
            if zctrl.value and prop:
                self.host_send("set_path", h=plugin.h, uri=prop["uri"], primary=prop["primary"],
                               value=str(zctrl.value))
        elif plugin and plugin.loaded and zctrl.graph_path is not None:
            self.host_send("set_param", h=plugin.h, index=zctrl.graph_path, value=float(zctrl.value))

    # ---------------------------------------------------------------------------
    # State management
    # ---------------------------------------------------------------------------

    def get_extended_config(self):
        # Save plugin internal state (where parameter values is insufficient)
        states = {}
        for processor, plugin in list(self.plugins.items()):
            if not plugin.loaded or plugin.detached or not plugin.stateful or processor.id is None:
                continue
            fd, tmp = tempfile.mkstemp(suffix=PRESET_EXT)
            os.close(fd)
            try:
                self.host_call("save_state", h=plugin.h, path=tmp)
                with open(tmp, "rb") as f:
                    states[str(processor.id)] = base64.b64encode(zlib.compress(f.read(), 6)).decode()
            except Exception as e:
                logging.error(f"Can't get state of Carla plugin '{plugin.title}' => {e}")
            finally:
                try:
                    os.remove(tmp)
                except Exception:
                    pass
        if states:
            return {"version": 1, "plugins": states}
        return None

    def set_extended_config(self, xconfig):
        try:
            self.saved_states.update(xconfig.get("plugins", {}))
        except Exception as e:
            logging.error(f"Wrong Carla extended config => {e}")

    def set_state_post(self, processor):
        # Called after the preset and the controllers have been restored
        data = self.saved_states.pop(str(processor.id), None)
        plugin = self.plugins.get(processor)
        if not data or not plugin or not plugin.loaded:
            return
        fd, tmp = tempfile.mkstemp(suffix=PRESET_EXT)
        try:
            with os.fdopen(fd, "wb") as f:
                f.write(zlib.decompress(base64.b64decode(data)))
            res = self.host_call("load_state", timeout=HOST_LOAD_TIMEOUT, h=plugin.h, path=tmp)
            self.update_zctrls(plugin, res.get("values", {}), check_ignore=False)
        except Exception as e:
            logging.error(f"Can't restore state of Carla plugin '{plugin.title}' => {e}")
        finally:
            try:
                os.remove(tmp)
            except Exception:
                pass

    # ---------------------------------------------------------------------------
    # API methods
    # ---------------------------------------------------------------------------

    # Only user presets (state files) can be managed from the web UI. There are no instances here: the plugin is identified by its engine code.

    class zynapi_plugin_stub:
        def __init__(self, eng_code):
            self.nickname = eng_code
            self.plugin_name = eng_code[3:] if eng_code.startswith("CA/") else eng_code

    @classmethod
    def init_zynapi_instance(cls, eng_code):
        cls.zynapi_eng_code = eng_code
        cls.zynapi_instance = cls.zynapi_plugin_stub(eng_code)

    @classmethod
    def refresh_zynapi_instance(cls):
        pass

    @classmethod
    def zynapi_plugin_dir(cls):
        eng_code = cls.zynapi_eng_code
        return f"{cls.presets_root}/{sanitize_text(eng_code[3:] if eng_code.startswith('CA/') else eng_code)}"

    @classmethod
    def zynapi_get_banks(cls):
        banks = []
        pdir = cls.zynapi_plugin_dir()
        banks.append({'text': "User", 'name': "User", 'fullpath': pdir, 'raw': [pdir, None, "User", None], 'readonly': False})
        try:
            for name in sorted(os.listdir(pdir), key=str.casefold):
                dpath = f"{pdir}/{name}"
                if os.path.isdir(dpath):
                    title = name.replace("_", " ")
                    banks.append({'text': title, 'name': title, 'fullpath': dpath,
                                  'raw': [dpath, None, title, None], 'readonly': False})
        except FileNotFoundError:
            pass
        return banks

    @classmethod
    def zynapi_get_presets(cls, bank):
        presets = []
        dpath = bank['fullpath']
        try:
            for fname in sorted(os.listdir(dpath), key=str.casefold):
                if fname.endswith(PRESET_EXT):
                    title = fname[:-len(PRESET_EXT)].replace("_", " ")
                    presets.append({'text': title, 'name': title, 'fullpath': f"{dpath}/{fname}",
                                    'raw': [f"{dpath}/{fname}", None, title, dpath], 'readonly': False})
        except FileNotFoundError:
            pass
        return presets

    @classmethod
    def zynapi_new_bank(cls, bank_name):
        os.makedirs(f"{cls.zynapi_plugin_dir()}/{sanitize_text(bank_name)}", exist_ok=True)

    @classmethod
    def zynapi_rename_bank(cls, bank_path, new_bank_name):
        if bank_path == cls.zynapi_plugin_dir():
            raise Exception("The root bank can't be renamed!")
        os.rename(bank_path, f"{os.path.dirname(bank_path)}/{sanitize_text(new_bank_name)}")

    @classmethod
    def zynapi_remove_bank(cls, bank_path):
        if bank_path == cls.zynapi_plugin_dir():
            raise Exception("The root bank can't be removed!")
        shutil.rmtree(bank_path)

    @classmethod
    def zynapi_rename_preset(cls, preset_path, new_preset_name):
        os.rename(preset_path, f"{os.path.dirname(preset_path)}/{sanitize_text(new_preset_name)}{PRESET_EXT}")

    @classmethod
    def zynapi_remove_preset(cls, preset_path):
        os.remove(preset_path)

    @classmethod
    def zynapi_download(cls, fullpath):
        return fullpath

    @classmethod
    def zynapi_install(cls, dpath, bank_path):
        dest = bank_path if bank_path else cls.zynapi_plugin_dir()
        if os.path.isdir(dpath):
            count = 0
            for root, dirs, files in os.walk(dpath):
                for fname in files:
                    if fname.endswith(PRESET_EXT):
                        bname = os.path.basename(root)
                        ddir = dest if root == dpath else f"{cls.zynapi_plugin_dir()}/{sanitize_text(bname)}"
                        os.makedirs(ddir, exist_ok=True)
                        shutil.move(os.path.join(root, fname), f"{ddir}/{fname}")
                        count += 1
            if count == 0:
                raise Exception(f"No {PRESET_EXT} files found!")
        elif dpath.endswith(PRESET_EXT):
            os.makedirs(dest, exist_ok=True)
            shutil.move(dpath, dest)
        else:
            raise Exception(f"File doesn't look like a Carla preset ({PRESET_EXT})!")

    @classmethod
    def zynapi_get_formats(cls):
        return "carxs,zip,tgz,tar.gz,tar.bz2,tar.xz"

    @classmethod
    def zynapi_martifact_formats(cls):
        return "carxs"


# Splits CamelCase labels
camel_split_re = re.compile(r'(?<=[a-z0-9])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])|(?<=[A-Za-z])(?=[0-9])|(?<=[0-9])(?=[A-Za-z])')

# ******************************************************************************