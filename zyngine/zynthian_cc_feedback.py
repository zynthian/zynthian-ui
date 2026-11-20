# ******************************************************************************
# ZYNTHIAN PROJECT: Zynthian CC feedback broker (zynthian_cc_feedback)
#
# Sends the values of bound controllers back to the devices they are bound to
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
# A control device driver registers its MIDI input (zmip) with a callback. Whenever a controller
# bound to a CC of that input changes, the callback gets the channel, the CC and the controller's
# value as a CC value, so the device can show it (LEDs, LED rings, motor faders, pickup...).
#
# Two kinds of binding are fed back:
#  - MIDI learn bindings (the chain manager's midi_cc_binding) from that input: global ones, and
#    those of the active chain, as only those respond to the device. CCs 120-127 (channel mode
#    messages) are never fed back.
#  - The driver's own bindings, set with set_bindings(), for controllers a driver maps itself
#    (fixed layouts, a mode that follows the chains...). They are always active.
#
# The chain manager tells the broker about every change to its bindings (bindings_changed), every
# CC received (cc_received / cc_handled) and every change of active chain (active_chain_changed),
# so a driver needs no polling and no signal handlers of its own for this:
#  - a CC that gains a binding (MIDI learn, snapshot or ZS3 load, processor reload, a change of
#    active chain, set_bindings) gets the controller's current value at once;
#  - a CC that loses its last binding gets cb(chan, cc, None, None), so a device can clear what it
#    shows (an LED ring); a driver that does not need it ignores it.
#
# The broker remembers the last value each device has for each channel and CC, whether the broker
# sent it or the device sent it, and sends nothing when that value would not change. So a CC that
# came from the device is not echoed back to it. A continuous controller's value is never sent
# back to the CC that set it while it is handled (it would differ only by rounding), but a
# toggle's is when the CC changes it (a momentary switch toggling a controller off with its
# press, which the device shows as on). A CC that leaves a toggle as it is gets nothing back: a
# knob turned up towards a toggle's threshold must keep its position, not be sent the toggle's
# value at each step (an APC40 knob would never reach the threshold). A driver that
# handles a device's CCs itself (not through the chain manager) can call cc_received() and
# cc_handled() around that for the same. A callback that returns False has not sent the value (a
# motor fader being touched): the broker then does not count it as the device's. resend()
# forgets what a device has, for a device that has lost its values (power cycled) or has just
# been found.
#
# A learned binding on any MIDI channel (0xFF) is reported with channel 0xFF: the driver chooses
# the channel to send it on.
# ******************************************************************************

import logging
import threading

OWN = 1 << 32   # Marks a driver's own binding key: OWN | zmip << 16 | chan << 8 | cc


def dev_key(key):
    """(zmip, chan, cc) of a binding key"""
    return ((key >> 16) & 0xFF, (key >> 8) & 0xFF, key & 0xFF)


class zynthian_cc_feedback:

    def __init__(self, chain_manager):
        """Create the CC feedback broker

        chain_manager : Chain manager whose MIDI learn bindings are fed back
        """

        self.chain_manager = chain_manager
        self._lock = threading.RLock()
        self._devices = {}   # Callbacks indexed by zmip
        self._value = {}     # Value functions indexed by zmip
        self._own = {}       # Driver bindings: {(chan, cc): zctrl} indexed by zmip
        self._zctrls = {}    # (zctrl, list of binding keys) indexed by id(zctrl), registered devices only
        self._active = {}    # Active bindings: list of (key, zctrl) indexed by (zmip, chan, cc)
        self._last = {}      # Value each device has, indexed by (zmip, chan, cc)
        self._rx = None      # (zmip, chan, cc) of the CC being handled, see cc_received

    # --------------------------------------------------------------------------
    # Device registration
    # --------------------------------------------------------------------------

    def register(self, zmip, cb, value=None):
        """Register a device for feedback of the controllers bound to its CCs

        zmip : Index of the device's MIDI input
        cb : Function called as cb(chan, cc, val, zctrl) when a bound controller changes. chan is
             the binding's MIDI channel (0-15, or 0xFF for a learned binding on any channel), val
             its value (0-127). val and zctrl are None when the CC has lost its last binding.
             Returning False means the value was not sent.
        value : Function value(zctrl) giving the CC value to send for a controller (Default:
                its MIDI value, inverted for a reversed range)
        Nothing is sent until the first change or a call to resend().
        """

        with self._lock:
            self._devices[zmip] = cb
            self._value[zmip] = value or self.midi_value
            self._forget(zmip)
        self._refresh(send=False)

    def unregister(self, zmip):
        """Stop feedback to a device and drop its own bindings

        zmip : Index of the device's MIDI input
        """

        with self._lock:
            self._own.pop(zmip, None)
            self._value.pop(zmip, None)
            if self._devices.pop(zmip, None) is None:
                return
            self._forget(zmip)
        self._refresh(send=False)

    def set_bindings(self, zmip, bindings):
        """Set a driver's own bindings, replacing those it had. A CC that gains a binding or
        changes controller gets its value; one that loses its last binding is released.

        zmip : Index of the device's MIDI input (registered)
        bindings : Dictionary of zctrls indexed by (chan, cc)
        """

        with self._lock:
            if zmip not in self._devices:
                return
            self._own[zmip] = dict(bindings)
        self._refresh()

    def resend(self, zmip):
        """Send the value of every active binding of a device, whatever it had

        zmip : Index of the device's MIDI input
        """

        with self._lock:
            if zmip not in self._devices:
                return
            self._forget(zmip)
            sends = []
            for dk, pairs in self._active.items():
                # The first controller of each CC, as a device can show only one value
                if dk[0] == zmip:
                    self._queue(sends, pairs[0][0], pairs[0][1])
        self._run(sends)

    # --------------------------------------------------------------------------
    # Notifications from the chain manager
    # --------------------------------------------------------------------------

    def bindings_changed(self):
        """The chain manager's MIDI learn bindings have changed"""

        self._refresh()

    def active_chain_changed(self):
        """The active chain has changed: its bindings become active, the previous chain's not"""

        self._refresh()

    def cc_received(self, zmip, chan, cc, val):
        """A CC has been received and is about to be handled: the device has this value now.
        Until cc_handled(), changes it makes to continuous controllers are not sent back to that
        CC (their value would only differ by rounding); a change to a toggle is, as it can differ
        from what the device sent (a momentary switch).

        zmip : Index of the MIDI input
        chan : MIDI channel
        cc : CC number
        val : CC value
        """

        if zmip in self._devices:
            self._last[(zmip, chan, cc)] = val
            self._last[(zmip, 0xFF, cc)] = val
            self._rx = (zmip, chan, cc)

    def cc_handled(self):
        """The CC passed to cc_received() has been handled. Nothing is sent for a controller it
        left unchanged, even when that differs from what the device sent (a knob turned towards a
        toggle's threshold keeps its position)."""

        self._rx = None

    # --------------------------------------------------------------------------
    # Internal
    # --------------------------------------------------------------------------

    def _refresh(self, send=True):
        """Work out the bindings again: register the value callback on bound controllers, send
        the values of CCs that gained a binding and release CCs that lost theirs

        send : False to send nothing (registration)
        """

        with self._lock:
            if not self._devices and not self._zctrls:
                return
            zctrls = {}

            def add(key, zctrl):
                zctrls.setdefault(id(zctrl), (zctrl, []))[1].append(key)

            for key, zlist in list(self.chain_manager.midi_cc_binding.items()):
                if (key >> 16) & 0xFF in self._devices and key & 0xFF < 120:
                    for zctrl in list(zlist):
                        add(key, zctrl)
            for zmip, bindings in self._own.items():
                for (chan, cc), zctrl in bindings.items():
                    if zctrl is not None:
                        add(OWN | zmip << 16 | (chan & 0xFF) << 8 | (cc & 0x7F), zctrl)

            active = {}
            for zctrl, keys in zctrls.values():
                for key in keys:
                    if self._is_active(key):
                        active.setdefault(dev_key(key), []).append((key, zctrl))

            sends = []
            releases = []
            for dk in self._active:
                if dk not in active:
                    self._last.pop(dk, None)
                    cb = self._devices.get(dk[0])
                    if cb is not None and send:
                        releases.append((cb, dk[0], dk[1], dk[2], None, None))
            for dk, pairs in active.items():
                old = {(key, id(zctrl)) for key, zctrl in self._active.get(dk, ())}
                new = [(key, zctrl) for key, zctrl in pairs if (key, id(zctrl)) not in old]
                if new and send:
                    # A new controller: whatever the device had came from another
                    self._last.pop(dk, None)
                    for key, zctrl in new:
                        self._queue(sends, key, zctrl)

            for zid, (zctrl, keys) in zctrls.items():
                if zid not in self._zctrls:
                    zctrl.register_send_value_cb(self._on_value)
            for zid, (zctrl, keys) in self._zctrls.items():
                if zid not in zctrls:
                    zctrl.unregister_send_value_cb(self._on_value)
            self._zctrls = zctrls
            self._active = active
        self._run(releases + sends)

    def _on_value(self, zctrl):
        """Value change callback of a bound controller"""

        with self._lock:
            entry = self._zctrls.get(id(zctrl))
            if entry is None:
                return
            sends = []
            for key in entry[1]:
                if self._is_active(key):
                    self._queue(sends, key, zctrl)
        self._run(sends)

    @staticmethod
    def midi_value(zctrl):
        """Default CC value of a controller: its MIDI value, inverted for a reversed range (as
        zynthian_controller.midi_control_change inverts what it receives)"""

        val = zctrl.get_ctrl_midi_val()
        if zctrl.range_reversed:
            val = 127 - val
        return val

    def _is_active(self, key):
        if key & OWN:
            return True
        chain_id = (key >> 24) & 0xFF
        if chain_id == 0xFF:
            return True
        try:
            return chain_id == self.chain_manager.active_chain.chain_id
        except Exception:
            return False

    def _forget(self, zmip):
        for k in [k for k in self._last if k[0] == zmip]:
            del self._last[k]

    def _queue(self, sends, key, zctrl):
        """Add a send to the list unless the device has the value already"""

        dk = dev_key(key)
        zmip, chan, cc = dk
        cb = self._devices.get(zmip)
        if cb is None:
            return
        try:
            val = self._value[zmip](zctrl)
        except Exception as e:
            logging.warning(f"Can't get the MIDI value of {zctrl.symbol} => {e}")
            return
        if self._rx is not None and not zctrl.is_toggle and self._rx[0] == zmip and self._rx[2] == cc \
                and chan in (self._rx[1], 0xFF):
            return
        if self._last.get(dk) == val:
            return
        self._last[dk] = val
        sends.append((cb, zmip, chan, cc, val, zctrl))

    def _run(self, sends):
        """Call the device callbacks, outside the lock"""

        for cb, zmip, chan, cc, val, zctrl in sends:
            try:
                if cb(chan, cc, val, zctrl) is False and val is not None:
                    # Not sent: the device does not have it
                    with self._lock:
                        if self._last.get((zmip, chan, cc)) == val:
                            del self._last[(zmip, chan, cc)]
            except Exception as e:
                name = zctrl.symbol if zctrl is not None else "(released)"
                logging.warning(f"Can't send CC{cc} feedback for {name} => {e}")
