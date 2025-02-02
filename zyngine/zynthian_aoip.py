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

import zynautoconnect

# ----------------------------------------------------------------------------
# Zynthian AoIP Manager Class
# ----------------------------------------------------------------------------

class zynthian_aoip:

    DEST_MCAST_ADDR = "239.192.0.1" #TODO: Define in config
    SRC_MCAST_ADDR = "239.192.0.2"

    def __init__(self):
        """ struct of input dict:
        uri: {
            "Proc": popen_object,
            "ip": remote_address or None if not connected
            "chans": quantity of audio channels,
            "sr": samplerate
        }
        """
        self.inputs = {} # Map of aoip input config, indexed by uri "aoip_ip_port:idx"
        self.outputs = {} # Map of aoip output processes, indexed by uri "aoip_ip_port:idx"
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
                        config["chans"] = 0
                        config["sr"] = 0
                    elif line.startswith("From"):
                        a, ip, b, chans, c, sr, d = line.split()
                        logging.warning(f"Connection from {ip} with {chans} channels at {sr} {d}")
                        config["ip"] = ip
                        config["chans"] = int(chans)
                        config["sr"] = int(sr)
            sleep(0.1)

    def set_node(self, node):
        if node <= 250:
            self.node = node
            environ['ZYNTHIAN_AOIP_NODE'] = str(node)
            self.DEST_MCAST_ADDR = f"239.192.0.{node}"
            self.SRC_MCAST_ADDR = f"239.192.1.{node}"
        if node == 0:
            # Disable AoIP
            self.reset()

    def add_output(self):
        if self.node == 0:
            return False
        used_ports = []
        for uri in self.outputs:
            used_ports.append(int(uri.split("_")[-1]))
        port = 1
        while port in used_ports:
            port += 1
        uri = f"aoip_{self.DEST_MCAST_ADDR}_{port}"
        proc = Popen(
            [
                "stdbuf",
                "-oL",
                "zita-j2n",
                "--jname",
                uri,
                self.DEST_MCAST_ADDR,
                str(port),
                "eth0"
            ],
            text=True,
            bufsize=1,
            stdout=PIPE,
            stderr=STDOUT)
        if proc.poll() is None:
            self.outputs[uri] = proc
            set_blocking(proc.stdout.fileno(), False)
            sleep(0.1)
            zynautoconnect.update_aoip_aliases(uri, True)
            return True
        return False

    def remove_output(self, uri):
        if uri in self.outputs:
            self.outputs[uri].terminate()
            del self.outputs[uri]
            return True

    def add_input(self, node, output):
        if self.node == 0 or not 0 < node <= 250:
            return False
        addr = f"239.192.1.{node}"
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
                "chans": 0,
                "sr": 0
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
