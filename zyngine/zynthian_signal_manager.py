# -*- coding: utf-8 -*-
# ****************************************************************************
# ZYNTHIAN PROJECT: Zynthian Signal Manager (zynthian_signal_manager)
#
# zynthian signal manager
#
# Copyright (C) 2015-2023 Fernando Moyano <jofemodo@zynthian.org>
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
import traceback
from queue import SimpleQueue
from threading import Thread

# ----------------------------------------------------------------------------
# Zynthian Signal Manager Class
# ----------------------------------------------------------------------------


class zynthian_signal_manager:

    S_ALL = 0  # Clients registering for this signal, will receive all signals
    S_STATE_MAN = 1
    S_CHAIN_MAN = 2
    S_CHAIN = 3
    S_AUDIO_RECORDER = 4
    S_AUDIO_PLAYER = 5
    S_SMF_RECORDER = 6
    S_ALSA_MIXER = 7
    S_AUDIO_MIXER = 8
    S_STEPSEQ = 9
    S_CUIA = 10
    S_GUI = 11
    S_MIDI = 12

    SS_CUIA_REFRESH = 0
    SS_CUIA_MIDI_EVENT = 1

    SS_GUI_SHOW_SCREEN = 0
    SS_GUI_SHOW_SIDEBAR = 1

    SS_MIDI_SYS = 0
    SS_MIDI_CC = 1
    SS_MIDI_PC = 2
    SS_MIDI_NOTE_ON = 3
    SS_MIDI_NOTE_OFF = 4

    last_signal = 13
    last_subsignal = 10

    def __init__(self):
        """ Create an instance of a signal manager

        Manages signaling. Clients register callbacks that are triggered when a given signal is received.
        """

        self.exit_flag = False

        # List of lists of registered callback functions.
        # Indexes ar signal & subsignal numbers
        self.signal_register = None
        self.reset_register()

        self.queue = SimpleQueue()
        self.queue_thread = None
        self.start_queue_thread()

    def stop(self):
        self.exit_flag = True

    # ----------------------------------------------------------------------------
    # Signal register handling
    # ----------------------------------------------------------------------------

    def reset_register(self):
        # self.signal_register = [[[]] * self.last_subsignal] * self.last_signal
        self.signal_register = []
        for i in range(self.last_signal):
            self.signal_register.append([])
            for j in range(self.last_subsignal):
                self.signal_register[i].append([])

    def register(self, signal, subsignal, callback, queued=False):
        if 0 <= signal <= self.last_signal and 0 <= subsignal <= self.last_subsignal:
            # logging.debug(f"Registering callback '{callback.__name__}()' for signal({signal},{subsignal})")
            self.signal_register[signal][subsignal].append((callback, queued))

    def register_queued(self, signal, subsignal, callback):
        if 0 <= signal <= self.last_signal and 0 <= subsignal <= self.last_subsignal:
            # logging.debug(f"Registering queued callback '{callback.__name__}()' for signal({signal},{subsignal})")
            self.signal_register[signal][subsignal].append((callback, True))

    def unregister(self, signal, subsignal, callback):
        if 0 <= signal <= self.last_signal and 0 <= subsignal <= self.last_subsignal:
            # logging.debug(f"Unregistering callback '{callback.__name__}()' from signal({signal},{subsignal})")
            n = 0
            for k, rdata in enumerate(self.signal_register[signal][subsignal]):
                if rdata[0] == callback:
                    del self.signal_register[signal][subsignal][k]
                    n += 1
            if n == 0:
                logging.warning(
                    f"Callback not registered for signal({signal},{subsignal})")

    def unregister_all(self, callback):
        n = 0
        for i in range(self.last_signal):
            for j in range(self.last_subsignal):
                for k, rdata in enumerate(self.signal_register[i][j]):
                    if rdata[0] == callback:
                        del self.signal_register[i][j][k]
                        n += 1
        if n == 0:
            logging.warning(f"Callback not registered")

    def process_signal(self, force_queued, signal, subsignal, **kwargs):
        if 0 <= signal <= self.last_signal and 0 <= subsignal <= self.last_subsignal:
            # logging.debug(f"Signal({signal},{subsignal}): {kwargs}")
            for rdata in self.signal_register[signal][subsignal]:
                if force_queued == 1 or rdata[1]:
                    self.queue.put_nowait(
                        (signal, subsignal, rdata[0], kwargs))
                else:
                    try:
                        # logging.debug(f"  => calling {rdata[0].__name__}(...)")
                        rdata[0](**kwargs)
                    except Exception as e:
                        logging.error(
                            f"Callback '{rdata[0].__name__}(...)' for signal({signal},{subsignal}): {e}")
                        logging.exception(traceback.format_exc())

    def send(self, signal, subsignal, **kwargs):
        """ Send direct call signal
        """
        self.process_signal(False, signal, subsignal, **kwargs)

    def send_queued(self, signal, subsignal, **kwargs):
        """ Send queued signal
        """
        self.process_signal(True, signal, subsignal, **kwargs)

    # ----------------------------------------------------------------------------
    # Queued signal handling
    # ----------------------------------------------------------------------------

    def start_queue_thread(self):
        self.queue_thread = Thread(target=self.queue_thread_task, args=())
        self.queue_thread.name = "SIGNAL_QUEUE"
        self.queue_thread.daemon = True  # thread dies with the program
        self.queue_thread.start()

    def queue_thread_task(self):
        while not self.exit_flag:
            try:
                data = self.queue.get(True, 1)
            except:
                continue
            try:
                # logging.debug(f"  => calling {data[2].__name__}(...)")
                data[2](**data[3])
            except Exception as e:
                logging.error(
                    f"Queued callback '{data[2].__name__}(...)' for signal({data[0]},{data[1]}): {e}")
                logging.exception(traceback.format_exc())

# ---------------------------------------------------------------------------


global zynsigman
zynsigman = zynthian_signal_manager()  # Instance signal manager

# ---------------------------------------------------------------------------
