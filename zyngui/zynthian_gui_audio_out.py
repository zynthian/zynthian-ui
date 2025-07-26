#!/usr/bin/python3
# -*- coding: utf-8 -*-
# ******************************************************************************
# ZYNTHIAN PROJECT: Zynthian GUI
#
# Zynthian GUI Audio-Out Selector Class
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

import logging
from time import sleep

# Zynthian specific modules
import zynautoconnect
from zyngine.zynthian_signal_manager import zynsigman
from zyngui.zynthian_gui_selector_info import zynthian_gui_selector_info
from zyngine.zynthian_audio_recorder import zynthian_audio_recorder

# ------------------------------------------------------------------------------
# Zynthian Audio-Out Selection GUI Class
# ------------------------------------------------------------------------------


class zynthian_gui_audio_out(zynthian_gui_selector_info):

    def __init__(self):
        self.chain = None
        super().__init__('Audio Out')

    def build_view(self):
        self.check_ports = 0
        self.playback_ports = zynautoconnect.get_hw_audio_dst_ports()
        if super().build_view():
            zynsigman.register_queued(
                zynsigman.S_AUDIO_RECORDER, zynthian_audio_recorder.SS_AUDIO_RECORDER_STATE, self.update_rec)
            return True
        else:
            return False

    def hide(self):
        if self.shown:
            zynsigman.unregister(
                zynsigman.S_AUDIO_RECORDER, zynthian_audio_recorder.SS_AUDIO_RECORDER_STATE, self.update_rec)
            super().hide()

    def update_rec(self, state):
        # Lock multitrack record config when recorder is recording
        self.fill_list()

    def set_chain(self, chain):
        self.chain = chain

    def refresh_status(self):
        super().refresh_status()
        self.check_ports += 1
        if self.check_ports > 10:
            self.check_ports = 0
            ports = zynautoconnect.get_hw_audio_dst_ports()
            if self.playback_ports != ports:
                self.playback_ports = ports
                self.fill_list()

    def fill_list(self):
        self.list_data = []
        if self.chain.chain_id:
            # Normal chain so add mixer / chain targets
            port_names = [("Main mixbus", 0, ["Send audio from this chain to the main mixbus", "audio_output.png"])]
            self.list_data.append((None, None, "> Chain inputs"))
            for chain_id, chain in self.zyngui.chain_manager.chains.items():
                if chain_id != 0 and chain != self.chain and chain.audio_thru or chain.is_synth() and chain.synth_slots[0][0].type == "Special":
                    if self.zyngui.chain_manager.will_audio_howl(self.chain.chain_id, chain_id):
                        prefix = "∞ "
                    else:
                        prefix = ""
                    port_names.append((f"{prefix}{chain.get_name()}", chain_id, [f"Send audio from this chain to the input of chain {chain.get_name()}.", "audio_output.png"]))
                # Add side-chain targets
                for processor in chain.get_processors():
                    try:
                        for port_name in zynautoconnect.get_sidechain_portnames(processor.jackname):
                            port_names.append((f"↣ side {port_name}", port_name), [f"Send audio from this chain to the sidechain input of processor {port_name}.", "audio_output.png"])
                    except:
                        pass
            for title, processor, info in port_names:
                if processor in self.chain.audio_out:
                    self.list_data.append((processor, processor, "\u2612 " + title, info))
                else:
                    self.list_data.append((processor, processor, "\u2610 " + title, info))

        if self.chain.is_audio():
            port_names = []
            # Direct physical outputs
            self.list_data.append((None, None, "> Direct Outputs"))
            port_count = len(self.playback_ports)
            for i in range(0, port_count, 2):
                if self.playback_ports[i].aliases:
                    suffix = f" ({self.playback_ports[i].aliases[0]})"
                else:
                    suffix = ""
                port_names.append((f"Output {i + 1}{suffix}", f"^{self.playback_ports[i].name}$", [f"Send audio from this chain directly to physical audio output {i + 1} as mono.", "audio_output.png"]))
                if i < port_count:
                    if self.playback_ports[i + 1].aliases:
                        suffix = f" ({self.playback_ports[i + 1].aliases[0]})"
                    else:
                        suffix = ""
                    port_names.append((f"Output {i + 2}{suffix}", f"^{self.playback_ports[i + 1].name}$", [f"Send audio from this chain directly to physical audio output {i + 2} as mono.", "audio_output.png"]))
                    port_names.append((f"Outputs {i + 1}+{i + 2} (stereo)", f"^{self.playback_ports[i].name}$|^{self.playback_ports[i + 1].name}$", [f"Send audio from this chain directly to physical audio outputs {i + 1} & {i + 2} as stereo.", "audio_output.png"]))
            for title, processor, info in port_names:
                if processor in self.chain.audio_out:
                    self.list_data.append((processor, processor, "\u2612 " + title, info))
                else:
                    self.list_data.append((processor, processor, "\u2610 " + title, info))

        self.list_data.append((None, None, "> Audio Recorder"))
        armed = self.zyngui.state_manager.audio_recorder.is_armed(self.chain.mixer_chan)
        if self.zyngui.state_manager.audio_recorder.status:
            locked = None
        else:
            locked = "record"
        if armed:
            self.list_data.append((locked, 'record_disable', '\u2612 Record chain', [f"The chain will be recorded as a stereo track within a multitrack audio recording.", "audio_output.png"]))
        else:
            self.list_data.append((locked, 'record_enable', '\u2610 Record chain', [f"The chain will be not be recorded as a stereo track within a multitrack audio recording.", "audio_output.png"]))

        super().fill_list()

    def select_action(self, i, t='S'):
        if self.list_data[i][0] == 'record':
            if t == 'S':
                self.zyngui.state_manager.audio_recorder.toggle_arm(self.chain.mixer_chan)
                self.fill_list()
        elif t == 'S':
            self.chain.toggle_audio_out(self.list_data[i][0])
            self.fill_list()
        elif t == "B":
            if not self.list_data[i][1].startswith("^system:"):
                return
            self.zyngui.state_manager.start_busy("alsa_output", "Getting audio level parameters...")
            sleep(0.1)
            ctrl_list = []
            chans = []
            try:
                a = self.list_data[i][1].replace("$", "").replace("^", "")
                b = a.split("|")
                for c in b:
                    if c.startswith("system:"):
                        chans.append(int(c.split("_")[-1]) - 1)
                zctrls = self.zyngui.state_manager.alsa_mixer_processor.engine.get_controllers_dict()
                for symbol, zctrl in zctrls.items():
                    if zctrl.graph_path[4]:
                        chan = zctrl.graph_path[1]
                    else:
                        chan = zctrl.graph_path[2]
                    if chan in chans:
                        ctrl_list.append(symbol)
                    sleep(0.01)
            except:
                pass
            self.zyngui.state_manager.end_busy("alsa_output")
            if ctrl_list:
                self.zyngui.show_screen("alsa_mixer", params=ctrl_list)

    def set_select_path(self):
        self.select_path.set("Send Audio to ...")

# ------------------------------------------------------------------------------
