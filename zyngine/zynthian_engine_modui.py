# -*- coding: utf-8 -*-
# ******************************************************************************
# ZYNTHIAN PROJECT: Zynthian Engine (zynthian_engine_modui)
#
# zynthian_engine implementation for MOD-UI (LV2 plugin host)
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
import copy
import shutil
import logging
import requests
import websocket
import traceback
from time import sleep
from subprocess import check_output
from threading import Thread
from collections import OrderedDict

# Zynthian specific modules
from . import zynthian_engine
from . import zynthian_controller

# ------------------------------------------------------------------------------
# MOD-UI Engine Class
# ------------------------------------------------------------------------------


class zynthian_engine_modui(zynthian_engine):

    # ---------------------------------------------------------------------------
    # Config variables
    # ---------------------------------------------------------------------------

    base_api_url = 'http://localhost:8888'
    websocket_url = 'ws://localhost:8888/websocket'

    bank_dirs = [
        ('EX', zynthian_engine.ex_data_dir + "/presets/mod-ui/pedalboards"),
        # this is a symlink to zynthian_engine.my_data_dir + "/presets/mod-ui/pedalboards"
        ('_', os.path.expanduser("~/.pedalboards/"))
    ]

    # ---------------------------------------------------------------------------
    # Initialization
    # ---------------------------------------------------------------------------

    def __init__(self, state_manager=None):
        super().__init__(state_manager)

        self.type = "Special"
        self.name = "MOD-UI"
        self.nickname = "MD"
        self.jackname = "mod-monitor"

        self.websocket = None
        self.ws_thread = None
        self.ws_preset_loaded = False
        self.ws_bundle_loaded = False
        self.hw_ports = {}
        self.midi_dev_info = None

        self.reset()
        self.start()

    def reset(self):
        super().reset()
        self.graph = {}
        self.plugin_info = OrderedDict()
        self.plugin_zctrls = OrderedDict()
        self.pedal_presets = OrderedDict()
        self.pedal_preset_noun = 'snapshot'

    def get_jackname(self):
        return "mod-host"

    def start(self):
        self.ws_bundle_loaded = False
        if not self.is_service_active("mod-ui"):
            logging.info("STARTING MOD-HOST & MOD-UI services...")
            check_output(("systemctl start mod-ui"), shell=True)

    def stop(self):
        # self.stop_websocket()
        if self.is_service_active("mod-ui"):
            logging.info("STOPPING MOD-HOST & MOD-UI services...")
            # check_output(("systemctl stop mod-host && systemctl stop browsepy && systemctl stop mod-ui"), shell=True)
            check_output(
                ("systemctl stop browsepy && systemctl stop mod-ui"), shell=True)
        self.ws_bundle_loaded = False

    def is_service_active(self, service="mod-ui"):
        cmd = "systemctl is-active "+str(service)
        try:
            result = check_output(cmd, shell=True).decode('utf-8', 'ignore')
        except Exception as e:
            result = "ERROR: "+str(e)
        if result.strip() == 'active':
            return True
        else:
            return False

    # ---------------------------------------------------------------------------
    # Processor Management
    # ---------------------------------------------------------------------------

    def add_processor(self, processor):
        super().add_processor(processor)
        self.set_midi_chan(processor)
        if not self.ws_thread:
            self.start_websocket()

    def remove_processor(self, processor):
        self.graph_reset()
        super().remove_processor(processor)

    # ----------------------------------------------------------------------------
    # Bank Managament
    # ----------------------------------------------------------------------------

    def get_bank_list(self, processor=None):
        return self.get_dirlist(self.bank_dirs)

    def set_bank(self, processor, bank):
        self.load_bundle(bank[0])
        return True

    def load_bundle(self, path):
        self.graph_reset()
        self.ws_bundle_loaded = False
        logging.debug(f"Loading bundle '{path}'...")
        res = self.api_post_request(
            "/pedalboard/load_bundle/", data={'bundlepath': path})
        if not res or not res['ok']:
            logging.error(f"Can't load bundle {path}")
        else:
            i = 0
            while not self.ws_bundle_loaded and i < 101:
                logging.debug(f"Waiting for bundle to load ...")
                sleep(0.1)
                i += 2
            logging.debug(f"Bundle {path} is loaded!!")
            return res['name']

    # ----------------------------------------------------------------------------
    # Preset Managament
    # ----------------------------------------------------------------------------

    def get_preset_list(self, bank):
        self.pedal_presets.clear()

        # Get Pedalboard Presets ...
        presets = self.api_get_request('/%s/list' % self.pedal_preset_noun)
        if presets is None:
            # switch to old mod-ui API which uses 'pedalpreset' instead of 'snapshot'
            self.pedal_preset_noun = 'pedalpreset'
            presets = self.api_get_request('/%s/list' % self.pedal_preset_noun)

        if not presets:
            self.api_post_request('/%s/enable' % self.pedal_preset_noun)
            presets = self.api_get_request('/%s/list' % self.pedal_preset_noun)

        preset_list = []
        if presets:
            preset_list.append((None, 0, "> Pedalboard Snapshots"))
            for pid in sorted(presets):
                title = presets[pid]
                # logging.debug("Add pedalboard preset " + title)
                preset_entry = [pid, [0, 0, 0], title, '']
                self.pedal_presets[pid] = preset_entry
            preset_list += list(self.pedal_presets.values())

        # Get Plugins Presets ...
        for pgraph in self.plugin_info:
            if len(self.plugin_info[pgraph]['presets']) > 0:
                preset_dict = {}
                preset_list.append(
                    (None, 0, "> {}".format(self.plugin_info[pgraph]['name'])))
                for prs in self.plugin_info[pgraph]['presets']:
                    title = prs['label']
                    # logging.debug("Add effect preset " + title)
                    preset_dict[prs['uri']] = len(preset_list)
                    preset_list.append([prs['uri'], [0, 0, 0], title, pgraph])
                self.plugin_info[pgraph]['presets_dict'] = preset_dict

        return preset_list

    def set_preset(self, processor, preset, preload=False):
        if preset[3]:
            self.load_effect_preset(preset[3], preset[0])
        else:
            self.load_pedalboard_preset(preset[0])
        return True

    def load_effect_preset(self, plugin, preset):
        self.ws_preset_loaded = False
        res = self.api_get_request(
            "/effect/preset/load/"+plugin, data={'uri': preset})
        i = 0
        while not self.ws_preset_loaded and i < 100:
            sleep(0.1)
            i = i+1

    def load_pedalboard_preset(self, preset):
        self.ws_preset_loaded = False
        res = self.api_get_request("/%s/load" %
                                   self.pedal_preset_noun, data={'id': preset})
        i = 0
        while not self.ws_preset_loaded and i < 100:
            sleep(0.1)
            i = i+1

    def cmp_presets(self, preset1, preset2):
        try:
            if preset1[3] == preset2[3] and preset1[0] == preset2[0]:
                return True
            else:
                return False
        except:
            return False

    def get_preset_favs(self, processor):
        if self.preset_favs is None:
            self.load_preset_favs()

        result = OrderedDict()
        for k, v in self.preset_favs.items():
            if v[1][0] in [p[0] for p in processor.preset_list]:
                result[k] = v

        return result

    # ----------------------------------------------------------------------------
    # Controllers Managament
    # ----------------------------------------------------------------------------

    def get_controllers_dict(self, processor):
        processor.controllers_dict = {}
        self._ctrl_screens = []
        try:
            for pgraph in sorted(self.plugin_info, key=lambda k: self.plugin_info[k]['posx']):
                logging.debug(
                    f"Plugin {pgraph} => X={self.plugin_info[pgraph]['posx']}")
                c = 1
                ctrl_set = []

                pgname = self.plugin_info[pgraph]['name']
                parts = pgraph.split("_")
                if len(parts) > 1:
                    try:
                        pgi = int(parts[-1])
                        pgname = pgname + "/" + str(pgi)
                    except:
                        pass
                logging.debug(f"Pgraph name => {pgname}")

                for param in self.plugin_info[pgraph]['ports']['control']['input']:
                    try:
                        zctrl = param['ctrl']
                        logging.debug(
                            f"Plugin {pgraph}, controller {zctrl.symbol} => {zctrl.name}")
                        zctrl.set_options({"processor": processor})
                        processor.controllers_dict[zctrl.symbol] = zctrl
                        ctrl_set.append(zctrl.symbol)
                        if len(ctrl_set) >= 4:
                            logging.debug(f"Adding control screen #{c}")
                            self._ctrl_screens.append(
                                [pgname+'#'+str(c), ctrl_set])
                            ctrl_set = []
                            c = c+1
                    except Exception as err:
                        logging.error(
                            f"Generating control screens for plugin {pgraph} => {err}")
                if len(ctrl_set) >= 1:
                    logging.debug(f"Adding control screen #{c}")
                    self._ctrl_screens.append([pgname+'#'+str(c), ctrl_set])
        except Exception as err:
            logging.error(f"Generating controller list => {err}")
        return processor.controllers_dict

    def send_controller_value(self, zctrl):
        self.websocket.send("param_set %s %.6f" % (zctrl.symbol, zctrl.value))
        logging.debug("WS << param_set %s %.6f" % (zctrl.symbol, zctrl.value))

    # ----------------------------------------------------------------------------
    # Websocket & MOD-UI API Management
    # ----------------------------------------------------------------------------

    def start_websocket(self):
        logging.info("Connecting to MOD-UI websocket...")

        i = 0
        while i < 100:
            try:
                self.websocket = websocket.create_connection(
                    self.websocket_url)
                break
            except:
                i += 1
                sleep(0.5)

        if i < 100:
            self.ws_thread = Thread(target=self.task_websocket, args=())
            self.ws_thread.name = "modui"
            self.ws_thread.daemon = True  # thread dies with the program
            self.ws_thread.start()

            j = 0
            while j < 100:
                if self.ws_bundle_loaded:
                    break
                j += 1
                sleep(0.1)

            if j < 100:
                return True
            else:
                self.stop_websocket()
                return False

        else:
            return False

    def stop_websocket(self):
        logging.info("Closing MOD-UI websocket...")
        if self.websocket:
            self.websocket.close()

    def task_websocket(self):
        error_counter = 0
        self.enable_midi_devices()
        while True:
            try:
                received = self.websocket.recv()
                logging.debug("WS >> %s" % received)
                try:
                    args = received.split()
                    command = args[0]
                except:
                    logging.error(
                        f"Wrong packet received from websocket => {received}")
                    continue

                if command == "ping":
                    self.enable_midi_devices()
                    self.websocket.send("pong")
                    logging.debug("WS << pong")

                elif command == "add_hw_port":
                    if args[3] == '1':
                        pdir = "output"
                    else:
                        pdir = "input"
                    self.add_hw_port_cb(
                        args[2], pdir, args[1], args[4], args[5])

                elif command == "add":
                    if args[2][0:4] == "http":
                        logging.info("ADD PLUGIN: "+args[1]+" => "+args[2])
                        self.add_plugin_cb(args[1], args[2], args[3], args[4])

                elif command == "remove":
                    if args[1] == ":all":
                        logging.info("REMOVE ALL PLUGINS")
                        self.remove_all_plugins_cb()
                    elif args[1]:
                        logging.info("REMOVE PLUGIN: "+args[1])
                        self.remove_plugin_cb(args[1])

                elif command == "connect":
                    self.graph_connect_cb(args[1], args[2])

                elif command == "disconnect":
                    self.graph_disconnect_cb(args[1], args[2])

                elif command == "preset":
                    self.preset_cb(args[1], args[2])

                elif command == "pedal_snapshot":
                    self.pedal_preset_cb(args[1])

                elif command == "param_set":
                    self.set_param_cb(args[1], args[2], args[3])

                elif command == "midi_map":
                    self.midi_map_cb(args[1], args[2], args[3], args[4])

                elif command == "loading_start":
                    logging.info("LOADING START")
                    self.state_manager.start_busy("mod-ui")

                elif command == "loading_end":
                    logging.info("LOADING END")
                    self.graph_autoconnect_midi_input()
                    self.state_manager.end_busy("mod-ui")
                    self.ws_bundle_loaded = True

                elif command == "bundlepath":
                    logging.info("BUNDLEPATH %s" % args[1])
                    self.bundlepath_cb(args[1])

                elif command == "stop":
                    logging.error("Restarting MOD services ...")
                    self.state_manager.start_busy("mod-ui")
                    self.stop()
                    self.start()
                    self.state_manager.end_busy("mod-ui")

            except websocket._exceptions.WebSocketConnectionClosedException:
                self.state_manager.start_busy("mod-ui")

                if self.is_service_active("mod-ui"):
                    try:
                        logging.error(
                            "Connection Closed. Retrying to connect ...")
                        self.websocket = websocket.create_connection(
                            self.websocket_url)
                        error_counter = 0
                    except:
                        if error_counter > 100:
                            logging.error(
                                "Re-connection failed. Restarting MOD services ...")
                            self.stop()
                            self.start()
                            self.set_bank(
                                self.processors[0], self.processors[0].bank_info)
                            error_counter = 0
                        else:
                            error_counter += 1
                            sleep(1)
                else:
                    logging.error(
                        "Connection Closed & MOD-UI stopped. Finishing...")
                    self.ws_thread = None
                    self.state_manager.start_busy("mod-ui")
                    return

                self.state_manager.end_busy("mod-ui")

            except Exception as e:
                # logging.error("task_websocket() => %s (%s)" % (e, type(e)))
                logging.exception(traceback.format_exc())
                self.state_manager.start_busy("mod-ui")
                sleep(1)
                self.state_manager.end_busy("mod-ui")

    def api_get_request(self, path, data=None, json=None):
        try:
            res = requests.get(self.base_api_url + path,
                               data=data, json=json, timeout=2)
        except Exception as e:
            logging.error(f"MOD-UI API {self.base_api_url}{path} => {e}")
            return
        if res.status_code != 200:
            logging.error(
                f"MOD-UI API {self.base_api_url}{path} => returned {res.status_code}")
        else:
            return res.json()

    def api_post_request(self, path, data=None, json=None):
        try:
            res = requests.post(self.base_api_url + path, data=data, json=json)
        except Exception as e:
            logging.error(e)
            return

        if res.status_code != 200:
            logging.error("POST call to MOD-UI API: " +
                          str(res.status_code) + " => " + self.base_api_url + path)
        else:
            return res.json()

    def bundlepath_cb(self, bpath):
        bdirname = bpath.split('/')[-1]
        # Find bundle_path in bank list ...
        processor = self.processors[0]
        bank_list = processor.get_bank_list()
        for i in range(len(bank_list)):
            # logging.debug("BUNDLE PATH SEARCH => %s <=> %s" % (bank_list[i][0].split('/')[-1], bdirname))
            if bank_list[i][0].split('/')[-1] == bdirname:
                bank_name = bank_list[i][2]
                # Set Bank in GUI, processor and engine without reloading the bundle
                logging.info('Bank Selected from Bundlepath: ' +
                             bank_name + ' (' + str(i)+')')
                processor.set_bank(i, False)
                self.state_manager.send_cuia("refresh_screen", ["control"])
                break

    def add_hw_port_cb(self, ptype, pdir, pgraph, pname, pnum):
        if ptype not in self.hw_ports:
            self.hw_ports[ptype] = {}
        if pdir not in self.hw_ports[ptype]:
            self.hw_ports[ptype][pdir] = {}
        self.hw_ports[ptype][pdir][pgraph] = {'name': pname, 'num': pnum}
        self.graph_autoconnect_midi_input()
        logging.debug("ADD_HW_PORT => "+pgraph+", "+ptype+", "+pdir)

    def add_plugin_cb(self, pgraph, puri, posx, posy):
        self.state_manager.start_busy("mod-ui")
        pinfo = self.api_get_request("/effect/get", data={'uri': puri})
        if pinfo:
            self.plugin_zctrls[pgraph] = {}
            # Add parameters to dictionary
            for param in pinfo['ports']['control']['input']:
                # Skip ports with the folowing designations (like MOD-UI)
                if param['designation'] in ["http://lv2plug.in/ns/lv2core#enabled",
                                            "http://lv2plug.in/ns/lv2core#freeWheeling",
                                            "http://lv2plug.in/ns/ext/time#beatsPerBar",
                                            "http://lv2plug.in/ns/ext/time#beatsPerMinute",
                                            "http://lv2plug.in/ns/ext/time#speed"]:
                    continue

                try:
                    ctrl_symbol = pgraph+'/'+param['symbol']
                    # If there is range info (should be!!) ...
                    if param['valid'] and param['ranges'] and len(param['ranges']) > 2:

                        if param['properties'] and 'integer' in param['properties']:
                            is_integer = True
                        else:
                            is_integer = False

                        # If there is Scale Points info ...
                        if param['scalePoints'] and len(param['scalePoints']) > 1:
                            labels = []
                            values = []
                            for p in param['scalePoints']:
                                if p['valid']:
                                    labels.append(p['label'])
                                    values.append(p['value'])
                            try:
                                val = param['ranges']['default']
                            except:
                                val = values[0]

                            param['ctrl'] = zynthian_controller(self, ctrl_symbol, {
                                'name': param['shortName'],
                                'graph_path': param['symbol'],
                                'value': val,
                                'labels': labels,
                                'ticks': values,
                                'value_min': 0,
                                'value_max': len(values)-1,
                                'is_toggle': False,
                                'is_integer': is_integer
                            })

                        # If it's a normal controller ...
                        else:
                            pranges = param['ranges']
                            r = pranges['maximum']-pranges['minimum']
                            if is_integer:
                                if r == 1:
                                    val = pranges['default']
                                    param['ctrl'] = zynthian_controller(self, ctrl_symbol, {
                                        'name': param['shortName'],
                                        'graph_path': param['symbol'],
                                        'value': val,
                                        'labels': ['off', 'on'],
                                        'ticks': [0, 1],
                                        'value_min': 0,
                                        'value_max': 1,
                                        'is_toggle': True,
                                        'is_integer': True
                                    })
                                else:
                                    param['ctrl'] = zynthian_controller(self, ctrl_symbol, {
                                        'name': param['shortName'],
                                        'graph_path': param['symbol'],
                                        'value': int(pranges['default']),
                                        'value_default': int(pranges['default']),
                                        'value_min': int(pranges['minimum']),
                                        'value_max': int(pranges['maximum']),
                                        'is_toggle': False,
                                        'is_integer': True
                                    })
                            else:
                                param['ctrl'] = zynthian_controller(self, ctrl_symbol, {
                                    'name': param['shortName'],
                                    'graph_path': param['symbol'],
                                    'value': pranges['default'],
                                    'value_default': pranges['default'],
                                    'value_min': pranges['minimum'],
                                    'value_max': pranges['maximum'],
                                    'is_toggle': False,
                                    'is_integer': False
                                })

                    # If there is no range info (should be!!) => Default MIDI CC controller with 0-127 range
                    else:
                        param['ctrl'] = zynthian_controller(self, ctrl_symbol, {
                            'name': param['shortName'],
                            'graph_path': param['symbol'],
                            'value': 0,
                            'value_default': 0,
                            'value_min': 0,
                            'value_max': 127,
                            'is_toggle': False,
                            'is_integer': True
                        })

                    # Add ZController to plugin_zctrl dictionary
                    self.plugin_zctrls[pgraph][param['symbol']] = param['ctrl']

                except Exception as err:
                    logging.error("Configuring Controllers: " +
                                  pgraph+" => "+str(err))

            # Add bypass Zcontroller
            bypass_zctrl = zynthian_controller(self, pgraph+'/:bypass', {
                'name': 'bypass',
                'graph_path': 'bypass',
                'value': 0,
                'labels': ['off', 'on'],
                'values': [0, 1],
                'value_min': 0,
                'value_max': 1,
                'is_toggle': True,
                'is_integer': True
            })

            self.plugin_zctrls[pgraph][':bypass'] = bypass_zctrl
            pinfo['ports']['control']['input'].insert(
                0, {'symbol': pgraph + '/:bypass', 'ctrl': bypass_zctrl})
            # Add position info
            pinfo['posx'] = int(round(float(posx)))
            pinfo['posy'] = int(round(float(posy)))
            # Add to info array
            self.plugin_info[pgraph] = pinfo
            # Refresh controllers
            self.processors[0].refresh_controllers()
            self.state_manager.send_cuia("refresh_screen", ["control"])
            self.state_manager.end_busy("mod-ui")

    def remove_plugin_cb(self, pgraph):
        self.state_manager.start_busy("mod-ui")
        if pgraph in self.graph:
            del self.graph[pgraph]
        if pgraph in self.plugin_zctrls:
            del self.plugin_zctrls[pgraph]
        if pgraph in self.plugin_info:
            del self.plugin_info[pgraph]
        # Refresh controllers
        self.processors[0].refresh_controllers()
        self.state_manager.send_cuia("refresh_screen", ["control"])
        self.state_manager.end_busy("mod-ui")

    def remove_all_plugins_cb(self):
        self.state_manager.start_busy("mod-ui")
        self.reset()
        self.processors[0].refresh_controllers()
        self.state_manager.send_cuia("refresh_screen", ["control"])
        self.state_manager.end_busy("mod-ui")

    def graph_connect_cb(self, src, dest):
        if src not in self.graph:
            self.graph[src] = []
        self.graph[src].append(dest)

    def graph_disconnect_cb(self, src, dest):
        if src in self.graph:
            if dest in self.graph[src]:
                self.graph[src].remove(dest)

    def graph_reset(self):
        logging.debug("Graph Reset...")
        graph = copy.deepcopy(self.graph)
        for src in graph:
            for dest in graph[src]:
                # logging.debug(f"MOD-UI API: /effect/disconnect/{src},{dest}")
                self.api_get_request(f"/effect/disconnect/{src},{dest}")
        # logging.debug("MOD-UI API: /reset")
        self.api_get_request("/reset")

    # If not already connected, try to connect zynthian MIDI send to the "input plugins" ...
    def graph_autoconnect_midi_input(self):
        midi_zynthian = "/graph/zynthian_midi_out"
        midi_in = "/graph/serial_midi_in"
        if midi_zynthian not in self.graph:
            if midi_in in self.graph:
                for dest in self.graph[midi_in]:
                    self.api_get_request(
                        "/effect/connect/{},{}".format(midi_zynthian, dest))

    def enable_midi_devices(self, aggregated_mode=False):
        self.midi_dev_info = self.api_get_request("/jack/get_midi_devices")

        # detect whether to use the old or new data format for set_midi_devices
        # based on the reponse for get_midi_devices
        old_set_midi_devices = 'midiAggregatedMode' not in self.midi_dev_info
        # logging.debug("API /jack/get_midi_devices => {}".format(self.midi_dev_info))
        if 'devList' in self.midi_dev_info:
            devs = []
            for dev in self.midi_dev_info['devList']:
                # if dev not in res['devsInUse']:
                devs.append(dev)
            if old_set_midi_devices:
                data = devs
            else:
                data = {
                    "devs": devs,
                    "midiAggregatedMode": aggregated_mode,
                    "midiLoopback": False
                }
            if len(data) > 0:
                res = self.api_post_request(
                    "/jack/set_midi_devices", json=data)
                # logging.debug("API /jack/set_midi_devices => {}".format(data))
                # logging.debug("RES => {}".format(res))

    def set_param_cb(self, pgraph, symbol, val):
        try:
            zctrl = self.plugin_zctrls[pgraph][symbol]
            zctrl.set_value(float(val), False)
        except Exception as err:
            logging.error("Parameter Not Found: "+pgraph +
                          "/"+symbol+" => "+str(err))
            # TODO: catch different types of exception

    def preset_cb(self, pgraph, uri):
        try:
            self.processors[0].set_preset_by_id(uri, False)
            self.state_manager.send_cuia("refresh_screen", ["control"])
        except Exception as e:
            logging.error(
                "Preset Not Found: {}/{} => {}".format(pgraph, uri, e))
        self.ws_preset_loaded = True

    def pedal_preset_cb(self, preset):
        try:
            pid = self.pedal_presets[preset][0]
            self.processors[0].set_preset_by_id(pid, False)
            self.state_manager.send_cuia("refresh_screen", ["control"])
        except Exception as e:
            logging.error("Preset Not Found: {}".format(preset))
        self.ws_preset_loaded = True

    # ----------------------------------------------------------------------------
    # MIDI learning
    # ----------------------------------------------------------------------------

    # These MOD-UI native functions are not used!

    def init_midi_learn(self, zctrl):
        logging.info("Learning '{}' ...".format(zctrl.symbol))
        res = self.api_post_request("/effect/parameter/address/"+zctrl.symbol,
                                    json=self.get_parameter_address_data(zctrl, "/midi-learn"))

    def midi_unlearn(self, zctrl):
        logging.info("Unlearning '{}' ...".format(zctrl.symbol))
        try:
            pad = self.get_parameter_address_data(zctrl, "null")
            return self.api_post_request("/effect/parameter/address/"+zctrl.symbol, json=pad)
        except Exception as e:
            logging.warning("Can't unlearn => {}".format(e))

    def set_midi_learn(self, zctrl, chan, cc):
        try:
            if zctrl.symbol and chan is not None and cc is not None:
                logging.info("Set MIDI map '{}' => {}, {}".format(
                    zctrl.symbol, chan, cc))
                uri = "/midi-custom_Ch.{}_CC#{}".format(chan+1, cc)
                pad = self.get_parameter_address_data(zctrl, uri)
                return self.api_post_request("/effect/parameter/address/"+zctrl.symbol, json=pad)
        except Exception as e:
            logging.warning("Can't learn => {}".format(e))

    def midi_map_cb(self, pgraph, symbol, chan, cc):
        logging.info("MIDI Map: {} {} => {}, {}".format(
            pgraph, symbol, chan, cc))
        try:
            self.plugin_zctrls[pgraph][symbol]._cb_midi_learn(
                int(chan), int(cc))
        except Exception as err:
            logging.error(
                "Parameter Not Found: {}/{} => {}".format(pgraph, symbol, err))

    def get_parameter_address_data(self, zctrl, uri):
        if isinstance(zctrl.labels, list):
            steps = len(zctrl.labels)
        else:
            steps = 127
        data = {
            "uri": uri,
            "label": zctrl.short_name,
            "minimum": str(zctrl.value_min),
            "maximum": str(zctrl.value_max),
            "value": str(zctrl.value),
            "steps": str(steps)
        }
        # {"uri":"/midi-learn","label":"Record","minimum":"0","maximum":"1","value":0,"steps":"1"}
        # {"uri":"/midi-learn","label":"SooperLooper","minimum":0,"maximum":1,"value":0}
        # {"uri":"/midi-learn","label":"Reset","minimum":"0","maximum":"1","value":0,"steps":"1"}
        logging.debug("Parameter Address Data => {}".format(data))
        return data

    # ---------------------------------------------------------------------------
    # API methods
    # ---------------------------------------------------------------------------

    @classmethod
    def zynapi_get_banks(cls):
        banks = []
        for b in cls.get_dirlist(cls.bank_dirs):
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
        return []

    @classmethod
    def zynapi_rename_bank(cls, bank_path, new_bank_name):
        head, tail = os.path.split(bank_path)
        new_bank_path = head + "/" + new_bank_name
        os.rename(bank_path, new_bank_path)

    @classmethod
    def zynapi_remove_bank(cls, bank_path):
        shutil.rmtree(bank_path)

    @classmethod
    def zynapi_download(cls, fullpath):
        return fullpath

    @classmethod
    def zynapi_install(cls, dpath, bank_path):
        if os.path.isdir(dpath):
            shutil.move(dpath, zynthian_engine.my_data_dir +
                        "/presets/mod-ui/pedalboards")
            # TODO Test if it's a MOD-UI pedalboard
        else:
            raise Exception("File doesn't look like a MOD-UI pedalboard!")

    @classmethod
    def zynapi_get_formats(cls):
        return "zip,tgz,tar.gz,tar.bz2,tar.xz"

# ******************************************************************************
