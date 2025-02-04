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
from subprocess import check_output, Popen, STDOUT, PIPE, DEVNULL
from os import set_blocking, environ
from threading import Thread
import socket

import zynautoconnect
from zynconf import zynthian_config
from zyngine.zynthian_signal_manager import zynsigman

# ----------------------------------------------------------------------------
# Zynthian AoIP Manager Class
# ----------------------------------------------------------------------------

class zynthian_aoip:

    SS_AOIP_CONNECT = 1

    def __init__(self):
        """ struct of input dict:
        uri: {
            "Proc": popen_object,
            "ip": remote_address or None if not connected
            "name": remote name
            "chans": quantity of audio channels,
            "sr": samplerate
            "port": udp port
        }
        """
        self.inputs = {} # Map of aoip input config, indexed by uri "aoip_port:idx"
        self.outputs = {} # Map of aoip output config, indexed by uri "aoip_mac_port:idx"
        self.remote_hosts = {} # Map of remote host info, indexed by hostname
        self.exit_flag = False
        self.thread = Thread(target=self.thread_task)
        self.thread.name = "AoIP"
        self.thread.daemon = True  # thread dies with the program
        self.thread.start()

    def reset(self):
        for uri in list(self.outputs):
            self.remove_output(uri)
        for uri in list(self.inputs):
            self.remove_input(uri)

    def set_alias(self, uri, alias, input=False):
        ports = zynautoconnect.get_ports(uri, input)
        for i, port in enumerate(ports):
            aliases = port.aliases
            if aliases:
                port.unset_alias(aliases[0])
            port.set_alias(f"{alias} {'L' if i==0 else 'R'}")

    def thread_task(self):
        while not self.exit_flag:
            for uri, config in self.inputs.items():
                for line in config["proc"].stdout.readlines():
                    line = line.strip()
                    if line == "Waiting for info packet...":
                        logging.warning("Disconnected")
                        config["ip"] = None
                        config["name"] = "disconnected"
                        config["chans"] = 0
                        config["sr"] = 0
                        port = config["port"]
                        self.set_alias(uri, f"AoIP {port - 40190} {config['name']}")
                        zynsigman.send(zynsigman.S_AOIP, self.SS_AOIP_CONNECT, uri=uri, state=False)
                    elif line.startswith("From"):
                        a, ip, b, chans, c, sr, d = line.split()
                        config["ip"] = ip
                        config["name"] = socket.gethostbyaddr(ip)[0]
                        config["chans"] = int(chans)
                        config["sr"] = int(sr)
                        logging.warning(f"Connection from {ip} ({config['name']}) with {chans} channels at {sr} {d}")
                        port = config["port"]
                        self.set_alias(uri, f"AoIP {port - 40190} {config['name']}")
                        zynsigman.send(zynsigman.S_AOIP, self.SS_AOIP_CONNECT, uri=uri, state=True)
            sleep(0.1)

    def add_output(self, uri):
        try:
            a, hostname, port = uri.split("_")
            info = socket.gethostbyaddr(hostname)
            port = int(port)
        except:
            return False
        if info[0]:
            name = info[0]
        else:
            name = hostname
        proc = Popen(
            [
                "stdbuf",
                "-oL",
                "zita-j2n",
                "--jname",
                uri,
                hostname,
                str(port),
                "eth0"
            ],
            text=True,
            bufsize=1,
            stdout=PIPE,
            stderr=STDOUT)
        if proc.poll() is None:
            self.outputs[uri] = {"proc": proc, "port": port, "hostname": hostname, "name": name}
            set_blocking(proc.stdout.fileno(), False)
            sleep(0.1)
            self.set_alias(uri, f"AoIP {name}: {port - 40190} disconnected", True)
            return True
        return False

    def remove_output(self, uri):
        if uri in self.outputs:
            self.outputs[uri]["proc"].terminate()
            del self.outputs[uri]
            return True

    def add_input(self, port=None):
        if port:
            uri = f"aoip_{port}"
            if uri in self.inputs:
                return False
        else:
            for port in range(40191, 40201):
                uri = f"aoip_{port}"
                if uri not in self.inputs:
                    break
        if port > 40199:
            return False
        proc = Popen(
            [
                "stdbuf",
                "-oL",
                "zita-n2j",
                "--jname",
                uri,
                self.get_own_ip(),
                str(port)
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
                "port": port
            }
            set_blocking(proc.stdout.fileno(), False)
            sleep(0.1)
            self.set_alias(uri, f"AoIP {port - 40190} disconnected")
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
            sources.append(input["port"])
        for config in self.outputs.values():
            destinations.append([config["hostname"], config["port"]])
        return {"sources": sources, "destinations": destinations}

    def set_state(self, state):
        self.reset()
        if "sources" in state:
            for port in state["sources"]:
                self.add_input(port)
        if "destinations" in state:
            for uri in state["destinations"]:
                self.add_output(uri)

    def set_remote_inputs(self, hostname, inputs):
        if hostname == self.get_own_ip():
            return
        if hostname not in self.remote_hosts:
            self.remote_hosts[hostname] = {}
        self.remote_hosts[hostname]["inputs"] = inputs.split(",")

    def set_remote_name(self, hostname, name):
        if hostname not in self.remote_hosts:
            self.remote_hosts[hostname] = {}
        self.remote_hosts[hostname]["name"] = name

    def get_own_ip(self):
        for line in check_output(["ip", "-4", "addr", "show", "eth0"], encoding="utf-8").split("\n"):
            if "inet" in line:
                return line.split()[1].split("/")[0]
