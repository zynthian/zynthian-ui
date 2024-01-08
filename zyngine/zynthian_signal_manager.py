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
    # Signal handling
    # ----------------------------------------------------------------------------

    def reset_register(self):
        #self.signal_register = [[[]] * self.last_subsignal] * self.last_signal
        self.signal_register = []
        for i in range(self.last_signal):
            self.signal_register.append([])
            for j in range(self.last_subsignal):
                self.signal_register[i].append([])

    def register(self, signal, subsignal, callback):
        if 0 <= signal <= self.last_signal and 0 <= subsignal <= self.last_subsignal:
            #logging.debug(f"Registering callback '{callback.__name__}()' for signal({signal},{subsignal})")
            self.signal_register[signal][subsignal].append(callback)

    def unregister(self, signal, subsignal, callback):
        if 0 <= signal <= self.last_signal and 0 <= subsignal <= self.last_subsignal:
            #logging.debug(f"Unregistering callback '{callback.__name__}()' from signal({signal},{subsignal})")
            try:
                self.signal_register[signal][subsignal].remove(callback)
            except:
                logging.warning(f"Callback not registered for signal({signal},{subsignal})")

    def unregister_all(self, callback):
        for i in range(self.last_signal):
            for j in range(self.last_subsignal):
                try:
                    self.signal_register[i][j].remove(callback)
                except:
                    pass

    def send(self, signal, subsignal, **kwargs):
        if 0 <= signal <= self.last_signal and 0 <= subsignal <= self.last_subsignal:
            #logging.debug(f"Signal({signal},{subsignal}): {kwargs}")
            for cb in self.signal_register[signal][subsignal]:
                try:
                    #logging.debug(f"  => calling {cb.__name__}(...)")
                    cb(**kwargs)
                except Exception as e:
                    logging.error(f"Callback '{cb.__name__}(...)' for signal({signal},{subsignal}): {e}")

    # ----------------------------------------------------------------------------
    # Queued signals
    # ----------------------------------------------------------------------------

    def send_queued(self, signal, subsignal, **kwargs):
        self.queue.put_nowait((signal, subsignal, kwargs))

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
            self.send(data[0], data[1], **data[2])

# ---------------------------------------------------------------------------

global zynsigman
zynsigman = zynthian_signal_manager()  # Instance signal manager

# ---------------------------------------------------------------------------
