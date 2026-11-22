# ******************************************************************************
# ZYNTHIAN PROJECT: Zynthian Control Device Driver
#
# Zynthian Control Device Driver for Behringer FCB1010 running riban firmware
#
# Copyright (C) 2026 Brian Walton <riban@zynthian.org>
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
#
# Behringer FCB1010 footpedal with riban firmware.
#
# Autoloaded by the pedal's SysEx identity
#
# ------------------------------------------------------------------------------

import logging

# Zynthian specific modules
from zyngine.ctrldev.zynthian_ctrldev_base import zynthian_ctrldev_base
from zyncoder.zyncore import lib_zyncore
from zyngine.zynthian_signal_manager import zynsigman

SYSEX_ID_MANUFACTURER = 0x7D
SYSEX_ID_FAMILY_MEMBER = bytes.fromhex("46 43 31 30")  # ASCII "FC10"
SYSEX_ID = bytes([SYSEX_ID_MANUFACTURER]) + SYSEX_ID_FAMILY_MEMBER

# ------------------------------------------------------------------------------
# Behringer FCB1010 (riban firmware)
# ------------------------------------------------------------------------------


class zynthian_ctrldev_behringer_fcb1010_riban(zynthian_ctrldev_base):

    sysex_ids = [SYSEX_ID]
    driver_name = "FCB1010 riban"
    driver_description = "Behringer FCB1010 with riban firmware"
    autoload_flag = False
    unroute_from_chains = False

    def __init__(self, state_manager, idev_in, idev_out=None):
        super().__init__(state_manager, idev_in, idev_out)
        self.channel = None     # MIDI channel (0-15) discovered from identity
        self.version = None     # Tuple containing 4 version octets from identity (not used)
        self.skip_identity = False  # True to ignore the next identity (the one this driver was autoloaded by)

    def init(self):
        """ Called when driver is loaded """
        super().init()
        self.chain_manager.cc_feedback.register(self.idev, self.on_feedback)
        identity_reply = self.state_manager.ctrldev_manager.get_identity_reply(self.idev)
        # If autoloaded by the pedal's identity, that identity also reaches on_sysex next
        self.skip_identity = self.parse_identity(identity_reply)
        self.chain_manager.cc_feedback.resend(self.idev)
        zynsigman.register_queued(zynsigman.S_MIDI, zynsigman.SS_MIDI_SYSEX, self.on_sysex)

    def end(self):
        """ Called when driver is unloaded """
        zynsigman.unregister(zynsigman.S_MIDI, zynsigman.SS_MIDI_SYSEX, self.on_sysex)
        self.chain_manager.cc_feedback.unregister(self.idev)
        super().end()

    def parse_identity(self, ev):
        """ Parse an SysEx identity reply and update device info

        Args:
            ev: MIDI event as list of butes
        Returns: True if it is the pedal's identity (device info updated)
        """

        if ev is None or len(ev) < 15 or ev[0] != 0xF0 or ev[1] != 0x7E or ev[3] != 0x06 or ev[4] != 0x02:
            return False
        if ev[5:10] not in self.sysex_ids:
            return False
        self.version = tuple(ev[10:14])
        self.channel = ev[2]
        return True

    def on_feedback(self, zctrl, chan, cc):
        """Handle CC feedback from broker

        Args:
            zctrl: Controller object
            chan: MIDI binding CC channel (0xFF for all channels)
            cc: MIDI binding CC number
        """

        if chan == 0xFF:
            chan = self.channel
        if zctrl is None or self.idev_out is None or chan is None:
            return False
        val = self.chain_manager.cc_feedback.value(self.idev, zctrl)
        lib_zyncore.dev_send_ccontrol_change(self.idev_out, chan, cc, val)

    def on_sysex(self, izmip, data):
        """ Handle a MIDI event from the device

        Args:
            ev: MIDI event as list of bytes
        """

        if izmip != self.idev:
            return
        if not self.parse_identity(data):
            return
        if self.skip_identity:
            # Don't send full update on first sysex id received from driver autoload
            self.skip_identity = False
        else:
            # Unsolicited sysex. e.g.pedal restarted
            self.chain_manager.cc_feedback.resend(self.idev)
        return False # Let State Manager handle all MIDI events (we only care about identity updates)

# ------------------------------------------------------------------------------
