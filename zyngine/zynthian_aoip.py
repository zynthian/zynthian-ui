# -*- coding: utf-8 -*-
# ****************************************************************************
# ZYNTHIAN PROJECT: Zynthian AoIP Manager (zynthian_aoip)
#
# Copyright (C) 2025 Fernando Moyano <jofemodo@zynthian.org>
#                    Brian Walton <riban@zynthian.org>
#
# ****************************************************************************
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
# ****************************************************************************

import logging
from time import sleep
from subprocess import Popen, STDOUT, PIPE, DEVNULL
from os import set_blocking, environ
from threading import Thread
import socket

import zynautoconnect
from zynconf import zynthian_config

# ----------------------------------------------------------------------------
# Zynthian AoIP Manager Class
# ----------------------------------------------------------------------------

class zynthian_aoip:

    def __init__(self):
        """ struct of input dict:
        uri: {
            "Proc": popen_object,
            "ip": remote_address or None if not connected
            "name": remote name
            "chans": quantity of audio channels,
            "sr": samplerate
            "state": [node, output]
        }
        """
        self.inputs = {} # Map of aoip input config, indexed by uri "aoip_ip_port:idx"
        self.outputs = {} # Map of aoip output config, indexed by uri "aoip_ip_port:idx"
        self.exit_flag = False
        self.set_node(int(environ.get('ZYNTHIAN_AOIP_NODE', 0)))
        self.thread = Thread(target=self.thread_task)
        self.thread.name = "AoIP"
        self.thread.daemon = True  # thread dies with the program
        self.thread.start()

    def reset(self):
        for uri in list(self.outputs):
            self.remove_output(uri)
        for uri in list(self.inputs):
            self.remove_input(uri)

    def thread_task(self):
        while not self.exit_flag:
            for uri, config in self.inputs.items():
                for line in config["proc"].stdout.readlines():
                    line = line.strip()
                    if line == "Waiting for info packet...":
                        logging.warning("Disconnected")
                        config["ip"] = None
                        config["name"] = ""
                        config["chans"] = 0
                        config["sr"] = 0
                    elif line.startswith("From"):
                        a, ip, b, chans, c, sr, d = line.split()
                        logging.warning(f"Connection from {ip} with {chans} channels at {sr} {d}")
                        config["ip"] = ip
                        config["name"] = socket.gethostbyaddr(ip)
                        config["chans"] = int(chans)
                        config["sr"] = int(sr)
            sleep(0.1)

    def set_node(self, node):
        if node <= 250:
            self.node = node
            self.DEST_MCAST_ADDR = f"239.192.0.{node}"
            zynthian_config.save_config({'ZYNTHIAN_AOIP_NODE':  str(node)})
        if node == 0:
            # Disable AoIP
            self.reset()

    def add_output(self, output=None):
        if self.node == 0:
            return False
        used_ports = []
        for config in self.outputs.values():
            used_ports.append(config["output"])
        if output in used_ports:
            return False
        if output == None:
            output = 1
            while output in used_ports:
                output += 1
        if output > 250:
            return False
        uri = f"aoip_{self.DEST_MCAST_ADDR}_{output}"
        proc = Popen(
            [
                "stdbuf",
                "-oL",
                "zita-j2n",
                "--jname",
                uri,
                self.DEST_MCAST_ADDR,
                str(output),
                "eth0"
            ],
            text=True,
            bufsize=1,
            stdout=PIPE,
            stderr=STDOUT)
        if proc.poll() is None:
            self.outputs[uri] = {"proc": proc, "output": output}
            set_blocking(proc.stdout.fileno(), False)
            sleep(0.1)
            zynautoconnect.update_aoip_aliases(uri, True)
            return True
        return False

    def remove_output(self, uri):
        if uri in self.outputs:
            self.outputs[uri]["proc"].terminate()
            del self.outputs[uri]
            return True

    def add_input(self, node, output):
        if self.node == 0 or not 0 < node <= 250:
            return False
        addr = f"239.192.0.{node}"
        uri = f"aoip_{addr}_{output}"
        proc = Popen(
            [
                "stdbuf",
                "-oL",
                "zita-n2j",
                "--jname",
                uri,
                addr,
                str(output),
                "eth0"
            ],
            text=True,
            bufsize=1,
            stdout=PIPE,
            stderr=STDOUT)
        if proc.poll() is None:
            self.inputs[uri] = {
                "proc": proc,
                "ip": None,
                "name": "",
                "chans": 0,
                "sr": 0,
                "state": [node, output]
            }
            set_blocking(proc.stdout.fileno(), False)
            sleep(0.1)
            zynautoconnect.update_aoip_aliases(uri, False)
            return True
        return False

    def remove_input(self, uri):
        if uri in self.inputs:
            self.inputs[uri]["proc"].terminate()
            del self.inputs[uri]
            return True

    def get_state(self):
        sources = []
        destinations = []
        for input in self.inputs.values():
            sources.append(input["state"])
        for config in self.outputs.values():
            destinations.append(config["output"])
        return {"sources": sources, "destinations": destinations}

    def set_state(self, state):
        self.reset()
        if "sources" in state:
            for source in state["sources"]:
                self.add_input(*source)
        if "destinations" in state:
            for destination in state["destinations"]:
                self.add_output(destination)
