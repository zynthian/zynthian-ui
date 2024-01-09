# -*- coding: utf-8 -*-
# ****************************************************************************
# ZYNTHIAN PROJECT: Zynthian State Manager (zynthian_state_manager)
#
# zynthian state manager
#
# Copyright (C) 2015-2024 Fernando Moyano <jofemodo@zynthian.org>
#                         Brian Walton <riban@zynthian.org>
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

import base64
import ctypes
import logging
from glob import glob
from threading import Thread
from time import monotonic
from queue import SimpleQueue
from datetime import datetime
from subprocess import check_output
from json import JSONEncoder, JSONDecoder
from os.path import basename, isdir, isfile, join, dirname, splitext

# Zynthian specific modules
import zynconf
import zynautoconnect

from zyncoder.zyncore import lib_zyncore
from zynlibs.zynseq import zynseq
from zynlibs.zynsmf import zynsmf  # Python wrapper for zynsmf (ensures initialised and wraps load() function)
from zynlibs.zynsmf.zynsmf import libsmf  # Direct access to shared library

from zyngine.zynthian_chain_manager import *
from zyngine.zynthian_processor import zynthian_processor 
from zyngine.zynthian_audio_recorder import zynthian_audio_recorder
from zyngine.zynthian_signal_manager import zynsigman
from zyngine import zynthian_legacy_snapshot
from zyngine import zynthian_engine_audio_mixer
from zyngine import zynthian_midi_filter

from zyngui import zynthian_gui_config
from zyngine.zynthian_ctrldev_manager import zynthian_ctrldev_manager

# ----------------------------------------------------------------------------
# Zynthian State Manager Class
# ----------------------------------------------------------------------------

SNAPSHOT_SCHEMA_VERSION = 1
capture_dir_sdc = os.environ.get('ZYNTHIAN_MY_DATA_DIR', "/zynthian/zynthian-my-data") + "/capture"
ex_data_dir = os.environ.get('ZYNTHIAN_EX_DATA_DIR', "/media/root")


class zynthian_state_manager:

    # Subsignals are defined inside each module. Here we define state manager subsignals:
    SS_AUDIO_PLAYER_STATE = 1
    SS_MIDI_PLAYER_STATE = 2
    SS_MIDI_RECORDER_STATE = 3

    def __init__(self):
        """ Create an instance of a state manager

        Manages full Zynthian state, i.e. snapshot
        """

        logging.info("Creating state manager")

        self.busy = set()  # Set of clients indicating they are busy doing something (may be used by UI to show progress)
        self.busy_message = None
        self.busy_error = None
        self.busy_warning = None
        self.busy_success = None
        self.busy_details = None
        self.start_busy("zynthian_state_manager")

        self.snapshot_dir = os.environ.get('ZYNTHIAN_MY_DATA_DIR', "/zynthian/zynthian-my-data") + "/snapshots"
        self.default_snapshot_fpath = join(self.snapshot_dir, "default.zss")
        self.last_state_snapshot_fpath = join(self.snapshot_dir, "last_state.zss")
        self.last_snapshot_count = 0  # Increments each time a snapshot is loaded - modules may use to update if required
        self.last_snapshot_fpath = ""
        self.snapshot_bank = None  # Name of snapshot bank (without path)
        self.snapshot_program = 0
        self.zs3 = {}  # Dictionary or zs3 configs indexed by "ch/pc"

        # Power saving
        self.power_save_mode = False
        self.last_event_flag = False
        self.last_event_ts = monotonic()

        # Status
        self.status_xrun = False
        self.status_undervoltage = False
        self.overtemp_warning = 75  # Temperature limit before warning overtemperature
        self.status_overtemp = False
        self.status_cpu_load = 0  # 0..100
        self.status_audio_player = False  # True if playing
        self.status_midi_recorder = False
        self.status_midi_player = False
        self.last_midi_file = None
        self.status_midi = False
        self.status_midi_clock = False
        self.update_available = False  # True when updates available from repositories
        self.checking_for_updates = False  # True whilst checking for updates

        self.midi_filter_script = None
        self.midi_learn_state = False
        self.midi_learn_pc = None   # When ZS3 Program Change MIDI learning is enabled, the name used for creating new ZS3, empty string for auto-generating a name. None when disabled.
        self.midi_learn_zctrl = None   # zctrl currently being learned
        self.sync = False  # True to request file system sync

        self.cuia_queue = SimpleQueue()  # Queue for CUIA calls

        self.hwmon_thermal_file = None
        self.hwmon_undervolt_file = None
        self.hwmon_undervolt_file = None
        self.get_throttled_file = None

        self.zynmixer = zynthian_engine_audio_mixer.zynmixer()
        self.chain_manager = zynthian_chain_manager(self)
        self.reset_zs3()

        self.alsa_mixer_processor = zynthian_processor("MX", ("Mixer", "ALSA Mixer", "MIXER", None, zynthian_engine_alsa_mixer, True))
        self.alsa_mixer_processor.engine = zynthian_engine_alsa_mixer(self, self.alsa_mixer_processor)
        self.alsa_mixer_processor.refresh_controllers()

        self.audio_recorder = zynthian_audio_recorder(self)
        self.zynseq = zynseq.zynseq()
        self.ctrldev_manager = None
        self.audio_player = None
        self.aubio_in = [1, 2]  # List of aubio inputs

        # Initialize SMF MIDI recorder and player
        try:
            self.smf_player = libsmf.addSmf()
            libsmf.attachPlayer(self.smf_player)
        except Exception as e:
            logging.error(e)

        try:
            self.smf_recorder = libsmf.addSmf()
            libsmf.attachRecorder(self.smf_recorder)
        except Exception as e:
            logging.error(e)

        # Initialize internal MIDI sender
        self.zynmidi = zynthian_zcmidi()

        self.exit_flag = False
        self.slow_thread = None
        self.fast_thread = None
        self.start()

        self.end_busy("zynthian_state_manager")

    def start(self):
        """Start state manager"""

        self.start_busy("start state")
        # Initialize SOC sensors monitoring
        try:
            self.hwmon_thermal_file = open('/sys/class/hwmon/hwmon0/temp1_input')
            self.hwmon_undervolt_file = open('/sys/class/hwmon/hwmon1/in0_lcrit_alarm')
            self.get_throttled_file = None
        except:
            logging.warning("Can't access sensors. Trying legacy interface...")
            self.hwmon_thermal_file = None
            self.hwmon_undervolt_file = None
            try:
                self.get_throttled_file = open('/sys/devices/platform/soc/soc:firmware/get_throttled')
                logging.debug("Accessing sensors using legacy interface!")
            except Exception as e:
                logging.error(f"Can't access monitoring sensors at all! => {e}")

        # Start VNC as configured
        self.default_vncserver()

        zynautoconnect.start(self)
        self.zynmixer.reset_state()
        self.ctrldev_manager = zynthian_ctrldev_manager(self)
        self.reload_midi_config()
        self.create_audio_player()

        self.exit_flag = False
        self.slow_thread = Thread(target=self.slow_thread_task)
        self.slow_thread.name = "Status Manager Slow"
        self.slow_thread.daemon = True  # thread dies with the program
        self.slow_thread.start()

        self.fast_thread = Thread(target=self.fast_thread_task)
        self.fast_thread.name = "Status Manager Fast"
        self.fast_thread.daemon = True  # thread dies with the program
        self.fast_thread.start()

        self.end_busy("start state")

    def stop(self):
        """Stop state manager"""

        self.start_busy("stop state")

        self.exit_flag = True
        if self.fast_thread and self.fast_thread.is_alive():
            self.fast_thread.join()
        self.fast_thread = None
        if self.slow_thread and self.slow_thread.is_alive():
            self.slow_thread.join()
        self.slow_thread = None

        self.last_snapshot_fpath = ""
        self.zynseq.transport_stop("ALL")
        zynautoconnect.pause()
        self.chain_manager.remove_all_chains(True)
        self.reset_zs3()
        self.zynseq.load("")
        self.ctrldev_manager.unload_all_drivers()
        self.destroy_audio_player()
        zynautoconnect.stop()

        if self.hwmon_thermal_file:
            self.hwmon_thermal_file.close()
            self.hwmon_thermal_file = None
        if self.hwmon_undervolt_file:
            self.hwmon_undervolt_file.close()
            self.hwmon_undervolt_file = None
        if self.get_throttled_file:
            self.get_throttled_file.close()
            self.get_throttled_file = None

        self.end_busy("stop state")

    def reset(self):
        """Reset state manager to clean initial start-up state"""

        self.start_busy("reset state")
        self.stop()
        sleep(0.2)
        self.clear_busy()  # TODO Is this needed?
        self.start()
        self.end_busy("reset state")

    def clean(self, chains=True, zynseq=True):
        """Remove Chains & Sequences.
        chains : True for cleaning all chains
        sequences : True for cleaning zynseq state (sequences)
        """

        self.zynmixer.set_mute(self.zynmixer.MAX_NUM_CHANNELS - 1, 1)
        #self.zynseq.transport_stop("ALL")
        self.zynseq.libseq.stop()
        if zynseq:
            self.zynseq.load("")
        if chains:
            zynautoconnect.pause()
            self.chain_manager.remove_all_chains(True)
            self.reset_zs3()
            self.zynmixer.reset_state()
            self.reload_midi_config()
            zynautoconnect.request_midi_connect(True)
            zynautoconnect.request_audio_connect(True)
            zynautoconnect.resume()
        self.zynmixer.set_mute(self.zynmixer.MAX_NUM_CHANNELS - 1, 0)

    def clean_all(self):
        """Remove ALL Chains & Sequences."""

        self.start_busy("clean all", "cleaning all...")
        self.clean(chains=True, zynseq=True)
        self.last_snapshot_fpath = ""
        self.end_busy("clean all")
        self.busy.clear()  # Sometimes it's needed, why??

    def clean_chains(self):
        """Remove ALL chains while keeping sequences."""

        self.start_busy("clean chains", "cleaning chains...")
        self.clean(chains=True, zynseq=False)
        self.end_busy("clean chains")
        self.busy.clear()  # Sometimes it's needed, why??

    def clean_sequences(self):
        """Remove ALL sequences while keeping chains."""

        self.start_busy("clean sequences", "cleaning sequences...")
        self.clean(chains=False, zynseq=True)
        self.end_busy("clean sequences")
        self.busy.clear()  # Sometimes it's needed, why??

    # -------------------------------------------------------------------------
    # Busy state management
    # -------------------------------------------------------------------------

    def start_busy(self, clid, message=None, details=None):
        """Add client to list of busy clients
        clid : Client id
        """

        self.busy.add(clid)
        if message:
            self.busy_message = message
        if details:
            self.busy_details = details
        #logging.debug(f"Start busy for {clid}. Current busy clients: {self.busy}")

    def end_busy(self, clid):
        """Remove client from list of busy clients
        clid : Client id
        """

        try:
            self.busy.remove(clid)
        except:
            pass
        if len(self.busy) == 0:
            self.busy_message = None
            self.busy_error = None
            self.busy_warning = None
            self.busy_success = None
            self.busy_details = None
        #logging.debug(f"End busy for {clid}: {self.busy}")

    def clear_busy(self):
        self.busy.clear()
        self.busy_message = None
        self.busy_error = None
        self.busy_warning = None
        self.busy_success = None
        self.busy_details = None

    def is_busy(self, client=None):
        """Check if clients are busy
        client : Name of client to check (Default: all clients)
        Returns : True if any clients are busy
        """

        if client:
            return client in self.busy
        return len(self.busy) > 0

    def set_busy_message(self, message, details=None):
        """Set busy message
        message : message text
        """

        if len(self.busy) > 0:
            self.busy_message = message
            if details:
                self.details = details

    def get_busy_message(self):
        """Returns busy message and clean it
        return message text
        """

        res = self.busy_message
        self.busy_message = None
        return res

    def set_busy_error(self, message, details=None):
        """Set busy error message
        message : message text
        """

        if len(self.busy) > 0:
            self.busy_error = message
            if details:
                self.details = details

    def get_busy_error(self):
        """Returns busy error message and clean it
        return message text
        """

        res = self.busy_error
        self.busy_error = None
        return res

    def set_busy_warning(self, message, details=None):
        """Set busy warning message
        message : message text
        """

        if len(self.busy) > 0:
            self.busy_warning = message
            if details:
                self.details = details

    def get_busy_warning(self):
        """Returns busy warning message and clean it
        return message text
        """

        res = self.busy_warning
        self.busy_warning = None
        return res

    def set_busy_success(self, message, details=None):
        """Set busy success message text
        details : details text
        """

        if len(self.busy) > 0:
            self.busy_success = message
            if details:
                self.details = details

    def get_busy_success(self):
        """Returns busy success message and clean it
        return message text
        """

        res = self.busy_success
        self.busy_success = None
        return res

    def set_busy_details(self, details):
        """Set busy details text
        details : details text
        """

        if len(self.busy) > 0:
            self.busy_details = details

    def get_busy_details(self):
        """Returns busy details and clean it
        return details text
        """

        res = self.busy_details
        self.busy_details = None
        return res

    # ----------------------------------------------------------------------------
    # CUIA Queue
    # ----------------------------------------------------------------------------

    def send_cuia(self, cuia, params=None):
       self.cuia_queue.put_nowait((cuia, params))

    def parse_cuia_params(self, params_str):
        params = []
        for i, p in enumerate(params_str.split(",")):
            try:
                params.append(int(p))
            except:
                params.append(p.strip())
        return params

    # ------------------------------------------------------------------
    # Background task threads
    # ------------------------------------------------------------------

    def slow_thread_task(self):
        """Perform slow / low priority background tasks"""

        status_counter = 0
        xruns_status = self.status_xrun
        midi_status = self.status_midi
        midi_clock_status = self.status_midi_clock
        next_update_check = monotonic() + 2 # Short delay after startup before first check for updates
        while not self.exit_flag:
            # Get CPU Load
            #self.status_cpu_load = max(psutil.cpu_percent(None, True))
            self.status_cpu_load = zynautoconnect.get_jackd_cpu_load()
            now = monotonic()

            try:
                # Get SOC sensors (once each 5 refreshes)
                if status_counter > 5:
                    status_counter = 0

                    self.status_overtemp = False
                    self.status_undervoltage = False

                    if self.hwmon_thermal_file and self.hwmon_undervolt_file:
                        try:
                            self.hwmon_thermal_file.seek(0)
                            res = int(self.hwmon_thermal_file.read())/1000
                            #logging.debug(f"CPU Temperature => {res}")
                            if res > self.overtemp_warning:
                                self.status_overtemp = True
                        except Exception as e:
                            logging.error(e)

                        try:
                            self.hwmon_undervolt_file.seek(0)
                            res = self.hwmon_undervolt_file.read()
                            if res == "1":
                                self.status_undervoltage = True
                        except Exception as e:
                            logging.error(e)

                    elif self.get_throttled_file:
                        try:
                            self.get_throttled_file.seek(0)
                            thr = int('0x%s' % self.get_throttled_file.read(), 16)
                            if thr & 0x1:
                                self.status_undervoltage = True
                            elif thr & (0x4 | 0x2):
                                self.status_overtemp = True
                        except Exception as e:
                            logging.error(e)

                    else:
                        self.status_overtemp = True
                        self.status_undervoltage = True

                else:
                    status_counter += 1

                # Audio Player Status
                # TODO: Update audio player status with callback
                self.status_audio_player = self.audio_player.engine.player.get_playback_state(self.audio_player.handle)

                # Audio Recorder Status => Implemented in zyngine/zynthian_audio_recorder.py

                # MIDI Player
                self.status_midi_player = libsmf.getPlayState()

                # MIDI Recorder
                self.status_midi_recorder = libsmf.isRecording()

                # Sequencer Status => It must be improved using callbacks
                self.zynseq.update_state()

                # Clean some status flags
                if xruns_status:
                    self.status_xrun = False
                    xruns_status = False
                if self.status_xrun:
                    xruns_status = True

                if midi_status:
                    self.status_midi = False
                    midi_status = False
                if self.status_midi:
                    midi_status = True

                if midi_clock_status:
                    self.status_midi_clock = False
                    midi_clock_status = False
                if self.status_midi_clock:
                    midi_clock_status = True

                if self.sync:
                    self.sync = False
                    os.sync()

                if now > next_update_check:
                    self.check_for_updates()
                    next_update_check = now + 3600 #TODO: Add update frequency config

            except Exception as e:
                logging.exception(e)

            sleep(0.2)

    def fast_thread_task(self):
        """Perform fast / high priority background tasks"""

        while not self.exit_flag:
            # Process MIDI events
            self.zynmidi_read()
            sleep(0.01)

    # ------------------------------------------------------------------
    # MIDI processing
    # ------------------------------------------------------------------

    def zynmidi_read(self):
        try:
            n = lib_zyncore.get_zynmidi_num_pending()
            if n <= 0:
                return
            midi_events = (ctypes.c_uint32 * n)()
            n = lib_zyncore.read_zynmidi_buffer(midi_events, n)
            for i in range(n):
                ev = midi_events[i]

                # Try to manage with a control device driver
                if self.ctrldev_manager.midi_event(ev):
                    self.status_midi = True
                    self.last_event_flag = True
                    continue

                izmip = (ev >> 24) & 0xff
                evtype = (ev >> 20) & 0xf
                chan = (ev >> 16) & 0xf

                # System Messages (Common & RT)
                if evtype == 0xF:
                    # Clock
                    if chan == 0x8:
                        self.status_midi_clock = True
                        continue
                    # Tick
                    elif chan == 0x9:
                        continue
                    # Active Sense
                    elif chan == 0xE:
                        continue
                    # Reset
                    elif chan == 0xF:
                        pass

                # Master MIDI Channel...
                elif chan == zynthian_gui_config.master_midi_channel:
                    logging.info("MASTER MIDI MESSAGE: %s" % hex(ev))
                    # Webconf configured messages for Snapshot Control...
                    if ev == zynthian_gui_config.master_midi_program_change_up:
                        logging.debug("PROGRAM CHANGE UP!")
                        self.load_snapshot_by_prog(self.state_manager.snapshot_program + 1)
                    elif ev == zynthian_gui_config.master_midi_program_change_down:
                        logging.debug("PROGRAM CHANGE DOWN!")
                        self.load_snapshot_by_prog(self.state_manager.snapshot_program - 1)
                    elif ev == zynthian_gui_config.master_midi_bank_change_up:
                        logging.debug("BANK CHANGE UP!")
                        self.set_snapshot_midi_bank(self.state_manager.snapshot_bank + 1)
                    elif ev == zynthian_gui_config.master_midi_bank_change_down:
                        logging.debug("BANK CHANGE DOWN!")
                        self.set_snapshot_midi_bank(self.state_manager.snapshot_bank - 1)
                    # Program Change => Snapshot Load
                    elif evtype == 0xC:
                        pgm = ((ev & 0x7F00) >> 8)
                        logging.debug("PROGRAM CHANGE %d" % pgm)
                        self.start_busy("load_snapshot", "loading snapshot")
                        self.load_snapshot_by_prog(pgm)
                        self.end_busy("load_snapshot")
                    # Control Change...
                    elif evtype == 0xB:
                        ccnum = (ev & 0x7F00) >> 8
                        ccval = (ev & 0x007F)
                        if ccnum == zynthian_gui_config.master_midi_bank_change_ccnum:
                            bnk = (ev & 0x7F)
                            logging.debug("BANK CHANGE %d" % bnk)
                            self.set_snapshot_midi_bank(bnk)
                        elif ccnum == 120:
                            self.all_sounds_off()
                        elif ccnum == 123:
                            self.all_notes_off()
                        else:
                            if self.midi_learn_zctrl:
                                self.chain_manager.add_midi_learn(chan, ccnum, self.midi_learn_zctrl, (ev >> 24) & 0xff)
                            else:
                                self.zynmixer.midi_control_change(chan, ccnum, ccval)
                    # Master Note CUIA with ZynSwitch emulation
                    elif evtype == 0x8 or evtype == 0x9:
                        note = str((ev >> 8) & 0x7f)
                        vel = ev & 0x7f
                        if note in zynthian_gui_config.master_midi_note_cuia:
                            cuia_str = zynthian_gui_config.master_midi_note_cuia[note]
                            parts = cuia_str.split(" ", 2)
                            cuia = parts[0].lower()
                            if len(parts) > 1:
                                params = self.parse_cuia_params(parts[1])
                            else:
                                params = None
                            # Emulate Zynswitch Push/Release with Note On/Off
                            if cuia == "zynswitch" and len(params) == 1:
                                if evtype == 0x8 or vel == 0:
                                    params.append('R')
                                else:
                                    params.append('P')
                                self.cuia_queue.put_nowait((cuia, params))
                            # Or normal CUIA
                            elif evtype == 0x9 and vel > 0:
                                self.cuia_queue.put_nowait((cuia, params))

                # Control Change...
                elif evtype == 0xB:
                    ccnum = (ev >> 8) & 0x7f
                    ccval = ev & 0x7f
                    #logging.debug("MIDI CONTROL CHANGE: CH{}, CC{} => {}".format(chan,ccnum,ccval))
                    if ccnum < 120:
                        if not self.midi_learn_zctrl:
                            self.chain_manager.midi_control_change((ev >> 24) & 0xff, chan, ccnum, ccval)
                            self.zynmixer.midi_control_change(chan, ccnum, ccval)
                            self.alsa_mixer_processor.midi_control_change(chan, ccnum, ccval)
                            self.audio_player.midi_control_change(chan, ccnum, ccval)
                        zynsigman.send_queued(zynsigman.S_MIDI, zynsigman.SS_MIDI_CC, izmip=izmip, chan=chan, num=ccnum, val=ccval)
                    # Special CCs >= Channel Mode
                    elif ccnum == 120:
                        self.state_manager.all_sounds_off_chan(chan)
                    elif ccnum == 123:
                        self.state_manager.all_notes_off_chan(chan)

                # Program Change...
                elif evtype == 0xC:
                    pgm = (ev & 0x7F00) >> 8
                    logging.info(f"MIDI PROGRAM CHANGE: CH#{chan}, PRG#{pgm}")
                    # MIDI learn SubSnapShot (ZS3)
                    if self.midi_learn_pc is not None:
                        self.save_zs3(f"{chan}/{pgm}")
                        send_signal = True
                    else:
                        # select SubSnapShot (ZS3)
                        if zynthian_gui_config.midi_prog_change_zs3:
                            send_signal = self.load_zs3_by_midi_prog(chan, pgm)
                        # or select preset
                        else:
                            chan = self.chain_manager.get_active_chain().midi_chan
                            send_signal = self.chain_manager.set_midi_prog_preset(chan, pgm)
                    if send_signal:
                        zynsigman.send_queued(zynsigman.S_MIDI, zynsigman.SS_MIDI_PC, izmip=izmip, chan=chan, num=pgm)

                # Note Off
                elif evtype == 0x8:
                    zynsigman.send_queued(zynsigman.S_MIDI, zynsigman.SS_MIDI_NOTE_OFF, izmip=izmip, chan=chan, note=(ev >> 8) & 0x7f, vel=ev & 0x7f)

                # Note On
                elif evtype == 0x9:
                    zynsigman.send_queued(zynsigman.S_MIDI, zynsigman.SS_MIDI_NOTE_ON, izmip=izmip, chan=chan, note=(ev >> 8) & 0x7f, vel=ev & 0x7f)

                # Flag MIDI event
                self.status_midi = True
                self.last_event_flag = True

        except Exception as err:
            logging.exception(err)

    # ---------------------------------------------------------------------------
    # Power Saving
    # ---------------------------------------------------------------------------

    def power_save_check(self):
        if zynthian_gui_config.power_save_secs <= 0:
            return
        if self.last_event_flag:
            self.last_event_ts = monotonic()
            self.last_event_flag = False
            if self.power_save_mode:
                self.set_power_save_mode(False)
        elif not self.power_save_mode and (monotonic() - self.last_event_ts) > zynthian_gui_config.power_save_secs:
            self.set_power_save_mode(True)

    def set_power_save_mode(self, psm=True):
        self.power_save_mode = psm
        if psm:
            logging.info("Power Save Mode: ON")
            self.ctrldev_manager.sleep_on()
            check_output("powersave_control.sh on", shell=True)
        else:
            logging.info("Power Save Mode: OFF")
            check_output("powersave_control.sh off", shell=True)
            self.ctrldev_manager.sleep_off()

    def set_event_flag(self):
        self.last_event_flag = True

    def reset_event_flag(self):
        self.last_event_flag = False

    # ----------------------------------------------------------------------------
    # Snapshot Save & Load
    # ----------------------------------------------------------------------------

    def get_state(self):
        """Get a dictionary describing the full state model"""

        self.save_zs3("zs3-0", "Last state")
        self.clean_zs3()
        state = {
            'schema_version': SNAPSHOT_SCHEMA_VERSION,
            'last_snapshot_fpath': self.last_snapshot_fpath,
            'midi_profile_state': self.get_midi_profile_state(),
            'chains': self.chain_manager.get_state(),
            'zs3': self.zs3
        }

        engine_states = {}
        for eid, engine in self.chain_manager.zyngines.items():
            engine_state = engine.get_extended_config()
            if engine_state:
                engine_states[eid] = engine_state
        if engine_states:
            state["engine_config"] = engine_states

        # Add ALSA-Mixer setting
        if zynthian_gui_config.snapshot_mixer_settings and self.alsa_mixer_processor:
            state['alsa_mixer'] = self.alsa_mixer_processor.get_state()

        # Audio Recorder Armed
        armed_state = []
        for midi_chan in range(self.zynmixer.MAX_NUM_CHANNELS):
            if self.audio_recorder.is_armed(midi_chan):
                armed_state.append(midi_chan)
        if armed_state:
            state['audio_recorder_armed'] = armed_state
        
        # Zynseq RIFF data
        binary_riff_data = self.zynseq.get_riff_data()
        b64_data = base64.b64encode(binary_riff_data)
        state['zynseq_riff_b64'] = b64_data.decode('utf-8')

        return state

    def save_snapshot(self, fpath, extra_data=None):
        """Save current state model to file

        fpath : Full filename and path
        extra_data : Dictionary to add to snapshot, e.g. UI specific config
        Returns : True on success
        """

        self.start_busy("save snapshot", "saving snapshot")
        try:
            # Get state
            state = self.get_state()
            if isinstance(extra_data, dict):
                state = {**state, **extra_data}
            # JSON Encode
            json = JSONEncoder().encode(state)
            with open(fpath, "w") as fh:
                logging.info("Saving snapshot %s => \n%s" % (fpath, json))
                fh.write(json)
                fh.flush()
                os.fsync(fh.fileno())
        except Exception as e:
            logging.error("Can't save snapshot file '%s': %s" % (fpath, e))
            self.set_busy_error("ERROR saving snapshot", e)
            sleep(2)
            self.end_busy("save snapshot")
            return False

        self.last_snapshot_fpath = fpath
        self.end_busy("save snapshot")
        return True

    def load_snapshot(self, fpath, load_chains=True, load_sequences=True):
        """Loads a snapshot from file
        
        fpath : Full path and filename of snapshot file
        load_chains : True to load chains
        load_sequences : True to load sequences into step sequencer
        Returns : State dictionary or None on failure
        """

        self.start_busy("load snapshot", "loading snapshot")
        try:
            with open(fpath, "r") as fh:
                json = fh.read()
                logging.info("Loading snapshot %s => \n%s" % (fpath, json))
        except Exception as e:
            logging.error("Can't load snapshot '%s': %s" % (fpath, e))
            self.end_busy("load snapshot")
            return None

        mute = self.zynmixer.get_mute(self.zynmixer.MAX_NUM_CHANNELS - 1)
        try:
            snapshot = JSONDecoder().decode(json)
            state = self.fix_snapshot(snapshot)

            if load_chains:
                # Mute output to avoid unwanted noises
                self.zynmixer.set_mute(self.zynmixer.MAX_NUM_CHANNELS - 1, True)

                zynautoconnect.pause()
                if "chains" in state:
                    self.chain_manager.set_state(state['chains'])
                self.chain_manager.stop_unused_engines()
                zynautoconnect.resume()

                if "engine_config" in state:
                    self.set_busy_details("processor engine config")
                    for eid, engine_state in state["engine_config"].items():
                        try:
                            self.chain_manager.zyngines[eid].set_extended_config(engine_state)
                        except Exception as e:
                            logging.info("Failed to set extended engine state for %s: %s", eid, e)

                self.zs3 = state["zs3"]
                self.load_zs3("zs3-0")

                if "alsa_mixer" in state:
                    self.alsa_mixer_processor.set_state(state["alsa_mixer"])

                if "audio_recorder_armed" in state:
                    for midi_chan in range(self.zynmixer.MAX_NUM_CHANNELS):
                        if midi_chan in state["audio_recorder_armed"]:
                            self.audio_recorder.arm(midi_chan)
                        else:
                            self.audio_recorder.unarm(midi_chan)

                if "midi_profile_state" in state:
                    self.set_midi_profile_state(state["midi_profile_state"])

            if load_sequences and "zynseq_riff_b64" in state:
                b64_bytes = state["zynseq_riff_b64"].encode("utf-8")
                binary_riff_data = base64.decodebytes(b64_bytes)
                self.zynseq.restore_riff_data(binary_riff_data)

            if fpath == self.last_snapshot_fpath and "last_state_fpath" in state:
                self.last_snapshot_fpath = state["last_snapshot_fpath"]
            else:
                self.last_snapshot_fpath = fpath

        except Exception as e:
            logging.exception("Invalid snapshot: %s" % e)
            self.set_busy_error("ERROR: Invalid snapshot", e)
            sleep(2)
            self.end_busy("load snapshot")
            return None

        zynautoconnect.request_midi_connect()
        zynautoconnect.request_audio_connect(True)

        # Restore mute state
        self.zynmixer.set_mute(self.zynmixer.MAX_NUM_CHANNELS - 1, mute)

        self.last_snapshot_count += 1
        try:
            self.snapshot_program = int(basename(fpath[:3]))
        except:
            pass

        self.end_busy("load snapshot")
        return state

    def set_snapshot_midi_bank(self, bank):
        """Set the current snapshot bank

        bank: Snapshot bank (0..127)
        """

        for bank in glob(f"{self.snapshot_dir}/{bank:03d}*"):
            if isdir(bank):
                self.snapshot_bank = basename(bank)
                return

    def load_snapshot_by_prog(self, program, bank=None):
        """Loads a snapshot from its MIDI program and bank

        program : MIDI program number
        bank : MIDI bank number (Default: Use last selected bank)
        Returns : True on success
        """

        if bank is None:
            bank = self.snapshot_bank
        if bank is None:
            return  # Don't load snapshot if invalid bank selected
        files = glob(f"{self.snapshot_dir}/{bank}/{program:03d}-*.zss")
        if files:
            self.load_snapshot(files[0])
            return True
        return False

    def fix_snapshot(self, snapshot):
        """Apply fixes to snapshot based on format version"""

        if "schema_version" not in snapshot:
            self.set_busy_details("fixing legacy snapshot")
            converter = zynthian_legacy_snapshot.zynthian_legacy_snapshot()
            state = converter.convert_state(snapshot)
        else:
            state = snapshot
            if state["schema_version"] < SNAPSHOT_SCHEMA_VERSION:
                #self.set_busy_details("nothing to fix yet")
                pass
        return state

    def backup_snapshot(self, path):
        """Make a backup copy of a snapshot file"""

        if isfile(path):
            dpath = dirname(path)
            fbase, fext = splitext(basename(path))
            ts_str = datetime.now().strftime("%Y%m%d%H%M%S")
            budir = dpath + "/.backup"
            if not isdir(budir):
                os.mkdir(budir)
            os.rename(path, "{}/{}.{}{}".format(budir, fbase, ts_str, fext))

    def save_default_snapshot(self):
        self.save_snapshot(self.default_snapshot_fpath)

    def load_default_snapshot(self):
        if isfile(self.default_snapshot_fpath):
            return self.load_snapshot(self.default_snapshot_fpath)

    def save_last_state_snapshot(self):
        self.save_snapshot(self.last_state_snapshot_fpath)

    def load_last_state_snapshot(self):
        if isfile(self.last_state_snapshot_fpath):
            return self.load_snapshot(self.last_state_snapshot_fpath)

    def delete_last_state_snapshot(self):
        try:
            os.remove(self.last_state_snapshot_fpath)
        except:
            pass

    # ----------------------------------------------------------------------------
    # ZS3 management
    # ----------------------------------------------------------------------------

    def get_zs3_title(self, zs3_id):
        """Get ZS3 title
        
        zs3_id : ZS3 ID
        Returns : Title as string
        """
        try:
            return self.zs3[zs3_id]["title"]
        except:
            return zs3_id

    def set_zs3_title(self, zs3_id, title):
        self.zs3[zs3_id]["title"] = title

    def toggle_zs3_chain_restore_flag(self, zs3_id, chain_id):
        zs3_state = self.zs3[zs3_id]
        if chain_id == "mixer":
            tstate = zs3_state["mixer"]
        else:
            tstate = zs3_state["chains"][chain_id]
        try:
            tstate["restore"] = not tstate["restore"]
        except:
            tstate["restore"] = False

    def load_zs3(self, zs3_id):
        """Restore a ZS3
        
        zs3_id : ID of ZS3 to restore
        Returns : True on success
        """

        if zs3_id not in self.zs3:
            logging.info("Attepmted to load non-existant ZS3")
            return False

        zs3_state = self.zs3[zs3_id]

        restored_chains = []
        restored_cc_mapping = []
        if "chains" in zs3_state:
            self.set_busy_details("restoring chains state")
            for chain_id, chain_state in zs3_state["chains"].items():
                chain_id = int(chain_id)

                try:
                    restore_flag = chain_state["restore"]
                except:
                    restore_flag = True

                if not restore_flag:
                    continue

                chain = self.chain_manager.get_chain(chain_id)
                if chain:
                    restored_chains.append(chain_id)
                else:
                    continue

                if "midi_chan" in chain_state:
                    if chain.midi_chan and chain.midi_chan != chain_state['midi_chan']:
                        chain.set_midi_chan(chain_state['midi_chan'])

                if chain.zmop_index is not None:
                    if "note_low" in chain_state:
                        lib_zyncore.zmop_set_note_low(chain.zmop_index, chain_state["note_low"])
                    else:
                        lib_zyncore.zmop_set_note_low(chain.zmop_index, 0)
                    if "note_high" in chain_state:
                        lib_zyncore.zmop_set_note_high(chain.zmop_index, chain_state["note_high"])
                    else:
                        lib_zyncore.zmop_set_note_high(chain.zmop_index, 127)
                    if "transpose_octave" in chain_state:
                        lib_zyncore.zmop_set_transpose_octave(chain.zmop_index, chain_state["transpose_octave"])
                    else:
                        lib_zyncore.zmop_set_transpose_octave(chain.zmop_index, 0)
                    if "transpose_semitone" in chain_state:
                        lib_zyncore.zmop_set_transpose_semitone(chain.zmop_index, chain_state["transpose_semitone"])
                    else:
                        lib_zyncore.zmop_set_transpose_semitone(chain.zmop_index, 0)
                if "midi_in" in chain_state:
                    chain.midi_in = chain_state["midi_in"]
                if "midi_out" in chain_state:
                    chain.midi_out = chain_state["midi_out"]
                if "midi_thru" in chain_state:
                    chain.midi_thru = chain_state["midi_thru"]
                if "audio_in" in chain_state:
                    chain.audio_in = chain_state["audio_in"]
                chain.audio_out = []
                if "audio_out" in chain_state:
                    for out in chain_state["audio_out"]:
                        try:
                            chain.audio_out.append(f"{self.chain_manager.processors[out[0]].jackname}:{out[1]}")
                        except:
                            chain.audio_out.append(out)
                    
                if "audio_thru" in chain_state:
                    chain.audio_thru = chain_state["audio_thru"]
                chain.rebuild_graph()
                if "midi_cc" in chain_state:
                    for cc, cfg in chain_state["midi_cc"].items():
                        for proc_id, symbol in cfg:
                            if proc_id in self.chain_manager.processors:
                                restored_cc_mapping.append((proc_id, int(cc), symbol))

        if "processors" in zs3_state:
            for proc_id, proc_state in zs3_state["processors"].items():
                try:
                    processor = self.chain_manager.processors[int(proc_id)]
                    if processor.chain_id in restored_chains:
                        self.set_busy_details(f"restoring {processor.get_basepath()} state")
                        processor.set_state(proc_state)
                except Exception as e:
                    logging.error(f"Failed to restore processor {proc_id} state => {e}")

        for cc_map in restored_cc_mapping:
            processor = self.chain_manager.processors[cc_map[0]]
            self.chain_manager.add_midi_learn(processor.midi_chan, cc_map[1], processor.controllers_dict[cc_map[2]])

        if "active_chain" in zs3_state:
            self.chain_manager.set_active_chain_by_id(zs3_state["active_chain"])

        if "mixer" in zs3_state:
            try:
                restore_flag = zs3_state["mixer"]["restore"]
            except:
                restore_flag = True
            if restore_flag:
                self.set_busy_details("restoring mixer state")
                self.zynmixer.set_state(zs3_state["mixer"])

        if "midi_capture" in zs3_state:
            self.set_busy_details("restoring midi capture state")
            self.set_midi_capture_state(zs3_state['midi_capture'])

        return True

    def load_zs3_by_midi_prog(self, midi_chan, prog_num):
        """Recall ZS3 state from MIDI program change

        midi_chan : MIDI channel
        prog_num : MIDI program change number
        """

        return self.load_zs3(f"{midi_chan}/{prog_num}")

    def save_zs3(self, zs3_id=None, title=None):
        """Store current state as ZS3

        zs3_id : ID of zs3 to save / overwrite (Default: Create new id)
        title : ZS3 title (Default: Create new title)
        """

        if zs3_id is None:
            # Get next id and name
            used_ids = []
            for zid in self.zs3:
                if zid.startswith("zs3-"):
                    try:
                        used_ids.append(int(zid.split('-')[1]))
                    except:
                        pass
            used_ids.sort()
            # Get next free zs3 id
            for index in range(1, len(used_ids) + 2):
                if index not in used_ids:
                    zs3_id = f"zs3-{index}"
                    break


        if title is None:
            title = self.midi_learn_pc

        if not title:
            if zs3_id in self.zs3:
                title = self.zs3[zs3_id]['title']
            else:
                title = zs3_id.upper()

        # Initialise zs3
        self.zs3[zs3_id] = {
            "title": title,
            "active_chain": self.chain_manager.active_chain_id
        }
        chain_states = {}
        for chain_id, chain in self.chain_manager.chains.items():
            chain_state = {
                "midi_chan": chain.midi_chan
            }
            if chain.is_midi():
                note_low = lib_zyncore.zmop_get_note_low(chain.zmop_index)
                if note_low:
                    chain_state["note_low"] = note_low
                note_high = lib_zyncore.zmop_get_note_high(chain.zmop_index)
                if note_high != 127:
                    chain_state["note_high"] = note_high
                transpose_octave = lib_zyncore.zmop_get_transpose_octave(chain.zmop_index)
                if transpose_octave:
                    chain_state["transpose_octave"] = transpose_octave
                transpose_semitone = lib_zyncore.zmop_get_transpose_semitone(chain.zmop_index)
                if transpose_semitone:
                    chain_state["transpose_semitone"] = transpose_semitone
                if chain.midi_in:
                    chain_state["midi_in"] = chain.midi_in.copy()
                if chain.midi_out != ["MIDI-OUT", "NET-OUT"]:
                    chain_state["midi_out"] = chain.midi_out.copy()
                if chain.midi_thru:
                    chain_state["midi_thru"] = chain.midi_thru
            chain_state["audio_in"] = chain.audio_in.copy()
            chain_state["audio_out"] = []
            for out in chain.audio_out:
                if out in zynautoconnect.get_sidechain_portnames():
                    client_name, port_name = out.split(":", 1)
                    for i, proc in self.chain_manager.processors.items():
                        if proc.jackname == client_name:
                            out = [i, port_name]
                            break
                chain_state["audio_out"].append(out)
            if chain.audio_thru:
                chain_state["audio_thru"] = chain.audio_thru
            # Add chain MIDI mapping
            for key, zctrls in self.chain_manager.chain_midi_cc_binding.items():
                if chain_id == (key >> 16) & 0xff:
                    cc = (key >> 8) & 0x7f
                    #TODO: Do not save default engine mapping
                    if "midi_cc" not in chain_state:
                        chain_state["midi_cc"] = {}
                    chain_state["midi_cc"][cc] = []
                    for zctrl in zctrls:
                        chain_state["midi_cc"][cc].append([zctrl.processor.id, zctrl.symbol])
            if chain_state:
                chain_states[chain_id] = chain_state
        if chain_states:
            self.zs3[zs3_id]["chains"] = chain_states

        # Add processors
        processor_states = {}
        for id, processor in self.chain_manager.processors.items():
            processor_state = {
                "bank_info": processor.bank_info,
                "preset_info": processor.preset_info,
                "controllers": {}
            }
            # Add controllers that differ to their default (preset) values
            for symbol, zctrl in processor.controllers_dict.items():
                ctrl_state = {}
                if zctrl.value != zctrl.value_default:
                    ctrl_state["value"] = zctrl.value
                if ctrl_state:
                    processor_state["controllers"][symbol] = ctrl_state
            processor_states[id] = processor_state
        if processor_states:
            self.zs3[zs3_id]["processors"] = processor_states

        # Add mixer state
        mixer_state = self.zynmixer.get_state(False)
        if mixer_state:
            self.zs3[zs3_id]["mixer"] = mixer_state

        # Add MIDI capture state
        mcstate = self.get_midi_capture_state()
        if mcstate:
            self.zs3[zs3_id]["midi_capture"] = mcstate


    def delete_zs3(self, zs3_index):
        """Remove a ZS3
        
        zs3_index : Index of ZS3 to remove
        """
        try:
            del(self.zs3[zs3_index])
        except:
            logging.info("Tried to remove non-existant ZS3")

    def reset_zs3(self):
        """Remove all ZS3"""

        # ZS3 list (subsnapshots)
        self.zs3 = {}
        # Last selected ZS3 subsnapshot

    def clean_zs3(self):
        """Remove non-existant processors from ZS3 state"""
        
        for state in self.zs3:
            if self.zs3[state]["active_chain"] not in self.chain_manager.chains:
                self.zs3[state]["active_chain"] = self.chain_manager.active_chain_id
            if "processors" in self.zs3:
                for processor_id in list(self.zs3[state]["processors"]):
                    if processor_id not in self.chain_manager.processors:
                        del self.zs3[state]["process"][processor_id]

    # ------------------------------------------------------------------
    # Jackd Info
    # ------------------------------------------------------------------

    def get_jackd_samplerate(self):
        """Get the samplerate that jackd is running"""

        return zynautoconnect.get_jackd_samplerate()

    def get_jackd_blocksize(self):
        """Get the block size used by jackd"""

        return zynautoconnect.get_jackd_blocksize()

    # ------------------------------------------------------------------
    # All Notes/Sounds Off => PANIC!
    # ------------------------------------------------------------------

    def all_sounds_off(self):
        logging.info("All Sounds Off!")
        self.start_busy("all_sounds_off")
        for chan in range(16):
            lib_zyncore.ui_send_ccontrol_change(chan, 120, 0)
        self.end_busy("all_sounds_off")

    def all_notes_off(self):
        logging.info("All Notes Off!")
        self.start_busy("all_notes_off")
        self.zynseq.libseq.stop()
        for chan in range(16):
            lib_zyncore.ui_send_ccontrol_change(chan, 123, 0)
        try:
            lib_zyncore.zynaptik_all_gates_off()
        except:
            pass
        self.end_busy("all_notes_off")

    def raw_all_notes_off(self):
        logging.info("Raw All Notes Off!")
        lib_zyncore.ui_send_all_notes_off()

    def all_sounds_off_chan(self, chan):
        logging.info(f"All Sounds Off for channel {chan}!")
        lib_zyncore.ui_send_ccontrol_change(chan, 120, 0)

    def all_notes_off_chan(self, chan):
        logging.info(f"All Notes Off for channel {chan}!")
        lib_zyncore.ui_send_ccontrol_change(chan, 123, 0)

    def raw_all_notes_off_chan(self, chan):
        logging.info(f"Raw All Notes Off for channel {chan}!")
        lib_zyncore.ui_send_all_notes_off_chan(chan)

    # ------------------------------------------------------------------
    # MPE initialization
    # ------------------------------------------------------------------

    def init_mpe_zones(self, lower_n_chans, upper_n_chans):
        # Configure Lower Zone
        if not isinstance(lower_n_chans, int) or lower_n_chans < 0 or lower_n_chans > 0xF:
            logging.error(f"Can't initialize MPE Lower Zone. Incorrect num of channels ({lower_n_chans})")
        else:
            lib_zyncore.ctrlfb_send_ccontrol_change(0x0, 0x79, 0x0)
            lib_zyncore.ctrlfb_send_ccontrol_change(0x0, 0x64, 0x6)
            lib_zyncore.ctrlfb_send_ccontrol_change(0x0, 0x65, 0x0)
            lib_zyncore.ctrlfb_send_ccontrol_change(0x0, 0x06, lower_n_chans)

        # Configure Upper Zone
        if not isinstance(upper_n_chans, int) or upper_n_chans < 0 or upper_n_chans > 0xF:
            logging.error(f"Can't initialize MPE Upper Zone. Incorrect num of channels ({upper_n_chans})")
        else:
            lib_zyncore.ctrlfb_send_ccontrol_change(0xF, 0x79, 0x0)
            lib_zyncore.ctrlfb_send_ccontrol_change(0xF, 0x64, 0x6)
            lib_zyncore.ctrlfb_send_ccontrol_change(0xF, 0x65, 0x0)
            lib_zyncore.ctrlfb_send_ccontrol_change(0xF, 0x06, upper_n_chans)

    # ----------------------------------------------------------------------------
    # MIDI Capture State
    # ----------------------------------------------------------------------------

    def get_midi_capture_state(self):
        """Get state related to midi input (capture): flags, chain routing, etc.

        Returns : dictionary with state
        """
        mcstate = {}
        for idev in range(24):
            if zynautoconnect.devices_in[idev] is None:
                continue

            routed_chains = []
            for ch in range(0, 16):
                if lib_zyncore.zmop_get_route_from(ch, idev):
                    routed_chains.append(ch)

            uid = zynautoconnect.devices_in[idev].aliases[0]
            mcstate[uid] = {
                "zmip_input_mode": bool(lib_zyncore.zmip_get_flag_active_chain(idev)),
                "ctrldev_load": idev in self.ctrldev_manager.drivers,
                "routed_chains": routed_chains
            }
            if uid == "AUBIO:in":
                mcstate[uid]["audio_in"] = self.aubio_in
            # Add global / absolute MIDI mapping
            for key, zctrls in self.chain_manager.absolute_midi_cc_binding.items():
                if idev == (key >> 24) & 0xff:
                    chan = (key >> 16) & 0x7f
                    cc = (key >> 8) & 0x7f
                    if "midi_cc" not in mcstate[uid]:
                        mcstate[uid]["midi_cc"] = {}
                    mcstate[uid]["midi_cc"][cc] = []
                    for zctrl in zctrls:
                        mcstate[uid]["midi_cc"][cc].append([zctrl.processor.id, zctrl.symbol])


        return mcstate

    def set_midi_capture_state(self, mcstate=None):
        """Set midi input (capture) state: flags, chain routing, etc.

        mcstate : dictionary with state. None for reset state to defaults.
        """
        if mcstate:
            for uid, state in mcstate.items():
                zmip = zynautoconnect.get_midi_in_devid_by_uid(uid)
                if zmip is None:
                    continue
                try:
                    lib_zyncore.zmip_set_flag_active_chain(zmip, bool(state["zmip_input_mode"]))
                except:
                    pass
                try:
                    self.aubio_in = state["audio_in"]
                except:
                    pass
                zynautoconnect.update_midi_in_dev_mode(zmip)
                try:
                    if state["ctrldev_load"]:
                        self.ctrldev_manager.load_driver(zmip)
                    else:
                        self.ctrldev_manager.unload_driver(zmip)
                except:
                    pass
                # Route chain zmops
                try:
                    routed_chains = state["routed_chains"]
                    for ch in range(0, 16):
                        lib_zyncore.zmop_set_route_from(ch, zmip, ch in routed_chains)
                except:
                    pass

                if "midi_cc" in state:
                    for cc, cfg in state["midi_cc"].items():
                        for proc_id, symbol in cfg:
                            if proc_id in self.chain_manager.processors:
                                processor = self.chain_manager.processors[proc_id]
                                self.chain_manager.add_midi_learn(processor.midi_chan, cc, processor.controllers_dict[symbol], zmip)

        else:
            zynautoconnect.reset_midi_in_dev_all()


    # ------------------------------------------------------------------
    # MIDI learning
    # ------------------------------------------------------------------

    def set_midi_learn(self, state):
        """Enable / disable MIDI learn in MIDI router

        state : True to enable MIDI learn
        """

        lib_zyncore.set_midi_learning_mode(state)
        self.midi_learn_state = state

    def enable_learn_cc(self, zctrl):
        """Enable MIDI CC learning
    
        zctrl : zctrl to learn to
        """

        self.disable_learn_pc()
        self.midi_learn_zctrl = zctrl
        self.set_midi_learn(True)

    def disable_learn_cc(self):
        """Disables MIDI CC learning"""

        self.midi_learn_zctrl = None
        self.set_midi_learn(False)

    def get_midi_learn_zctrl(self):
        try:
            return self.midi_learn_zctrl
        except:
            return None

    def enable_learn_pc(self, zs3_name=""):
        self.disable_learn_cc()
        self.midi_learn_pc = zs3_name
        self.set_midi_learn(True)

    def disable_learn_pc(self):
        self.midi_learn_pc = None
        self.set_midi_learn(False)

    # ---------------------------------------------------------------------------
    # MIDI Router Init & Config
    # ---------------------------------------------------------------------------

    def init_midi(self):
        """Initialise MIDI configuration"""
        try:
            # Set Global Tuning
            self.fine_tuning_freq = zynthian_gui_config.midi_fine_tuning
            lib_zyncore.set_tuning_freq(ctypes.c_double(self.fine_tuning_freq))
            # Set MIDI Master Channel
            lib_zyncore.set_midi_master_chan(zynthian_gui_config.master_midi_channel)
            # Set MIDI System Messages flag
            lib_zyncore.set_midi_system_events(zynthian_gui_config.midi_sys_enabled)
            # Setup MIDI filter rules
            if self.midi_filter_script:
                self.midi_filter_script.clean()
            self.midi_filter_script = zynthian_midi_filter.MidiFilterScript(zynthian_gui_config.midi_filter_rules)
        except Exception as e:
            logging.error(f"ERROR initializing MIDI : {e}")

    def reload_midi_config(self):
        """Reload MIDI configuration from saved state"""

        zynconf.load_config()
        midi_profile_fpath = zynconf.get_midi_config_fpath()
        if midi_profile_fpath:
            zynconf.load_config(True, midi_profile_fpath)
            zynthian_gui_config.set_midi_config()
            self.init_midi()
            self.init_midi_services()
            zynautoconnect.request_midi_connect()

    def init_midi_services(self):
        """Start/Stop MIDI aux. services"""

        self.default_rtpmidi()
        self.default_qmidinet()
        self.default_touchosc()
        self.default_bluetooth()
        self.default_aubionotes()

    # -------------------------------------------------------------------
    # MIDI profile
    # -------------------------------------------------------------------

    def get_midi_profile_state(self):
        """Get MIDI profile state as an ordered dictionary"""

        midi_profile_state = OrderedDict()
        for key in os.environ.keys():
            if key.startswith("ZYNTHIAN_MIDI_"):
                midi_profile_state[key[14:]] = os.environ[key]
        midi_profile_state["port_names"] = zynautoconnect.get_port_friendly_names()
        return midi_profile_state

    def set_midi_profile_state(self, state):
        """Set MIDI profile from state

        state : MIDI profile state dictionary
        """

        if state is not None:
            for key in state:
                if key == "port_names":
                    zynautoconnect.set_midi_port_names(state[key])
                elif not key.startswith("MASTER_"): # Drop Master Channel config, as it's global
                    os.environ["ZYNTHIAN_MIDI_" + key] = state[key]
            zynthian_gui_config.set_midi_config()
            self.init_midi()
            self.init_midi_services()
            zynautoconnect.request_midi_connect()
            return True

    def reset_midi_profile(self):
        """Clear MIDI profiles"""

        self.reload_midi_config()

    # ---------------------------------------------------------------------------
    # Global Audio Player
    # ---------------------------------------------------------------------------

    def create_audio_player(self):
        if not self.audio_player:
            try:
                self.audio_player = zynthian_processor("AP", self.chain_manager.engine_info["AP"])
                self.chain_manager.start_engine(self.audio_player, "AP")
            except Exception as e:
                logging.error(f"Can't create global Audio Player instance => {e}")
                return

    def destroy_audio_player(self):
        if self.audio_player:
            self.audio_player.engine.remove_processor(self.audio_player)
            self.audio_player = None
            self.status_audio_player = False

    def start_audio_player(self):
        if (self.audio_player.preset_name and os.path.exists(self.audio_player.preset_info[0])) or self.audio_player.engine.player.get_filename(self.audio_player.handle):
            self.audio_player.engine.player.start_playback(self.audio_player.handle)
        else:
            self.audio_player.engine.load_latest(self.audio_player)
            self.audio_player.engine.player.start_playback(self.audio_player.handle)
        zynsigman.send(zynsigman.S_STATE_MAN, self.SS_AUDIO_PLAYER_STATE, state=True)

    def stop_audio_player(self):
        self.audio_player.engine.player.stop_playback(self.audio_player.handle)
        zynsigman.send(zynsigman.S_STATE_MAN, self.SS_AUDIO_PLAYER_STATE, state=False)

    def toggle_audio_player(self):
        """Toggle playback of global audio player"""

        if self.audio_player.engine.player.get_playback_state(self.audio_player.handle):
            self.stop_audio_player()
        else:
            self.start_audio_player()

    # ---------------------------------------------------------------------------
    # Global MIDI Player
    # ---------------------------------------------------------------------------

    def start_midi_record(self):
        if not libsmf.isRecording():
            libsmf.unload(self.smf_recorder)
            libsmf.startRecording()
            zynsigman.send(zynsigman.S_STATE_MAN, self.SS_MIDI_RECORDER_STATE, state=True)
            return True
        else:
            return False

    def stop_midi_record(self):
        result = False
        if libsmf.isRecording():
            logging.info("STOPPING MIDI RECORDING ...")
            libsmf.stopRecording()
            try:
                parts = self.chain_manager.get_processors(self.chain_manager.active_chain_id, "SYNTH")[0].get_presetpath().split('#', 2)
                filename = parts[1].replace("/", ";").replace(">", ";").replace(" ; ", ";")
            except:
                filename = "jack_capture"

            exdirs = zynthian_gui_config.get_external_storage_dirs(ex_data_dir)
            if exdirs:
                midir = exdirs[0]
            else:
                midir = capture_dir_sdc

            n = 1
            for fn in glob(f"{midir}/*mid"):
                try:
                    n = int(fn[:3]) + 1
                except:
                    pass
            fpath = f"{midir}/{n:03}-{filename}.mid"

            if zynsmf.save(self.smf_recorder, fpath):
                self.sync = True
                self.last_midi_file = fpath
                result = True

            zynsigman.send(zynsigman.S_STATE_MAN, self.SS_MIDI_RECORDER_STATE, state=False)

        return result

    def toggle_midi_record(self):
        if libsmf.isRecording():
            self.stop_midi_record()
        else:
            self.start_midi_record()

    def start_midi_playback(self, fpath):
        self.stop_midi_playback()
        if fpath is None:
            if self.last_midi_file:
                fpath = self.last_midi_file
            else:
                # Get latest file
                latest_mtime = 0
                for dir in [capture_dir_sdc] + zynthian_gui_config.get_external_storage_dirs(ex_data_dir):
                    for fn in glob(f"{dir}//*.mid"):
                        mtime = os.path.getmtime(fn)
                        if mtime > latest_mtime:
                            fpath = fn
                            latest_mtime = mtime

        if fpath is None:
            logging.info("No track to play!")
            return self.status_midi_player

        try:
            zynsmf.load(self.smf_player, fpath)
            tempo = libsmf.getTempo(self.smf_player, 0)
            logging.info(f"STARTING MIDI PLAY '{fpath}' => {tempo}BPM")
            self.zynseq.set_tempo(tempo)
            libsmf.startPlayback()
            self.zynseq.transport_start("zynsmf")
            if libsmf.getPlayState() != zynsmf.PLAY_STATE_STOPPED:
                self.status_midi_player = True
                zynsigman.send(zynsigman.S_STATE_MAN, self.SS_MIDI_PLAYER_STATE, state=True)
            self.last_midi_file = fpath
            #self.zynseq.libseq.transportLocate(0)
        except Exception as e:
            logging.error(f"ERROR STARTING MIDI PLAY: {e}")
            return False
        return self.status_midi_player

    def stop_midi_playback(self):
        if libsmf.getPlayState() != zynsmf.PLAY_STATE_STOPPED:
            libsmf.stopPlayback()
            self.status_midi_player = False
            zynsigman.send(zynsigman.S_STATE_MAN, self.SS_MIDI_PLAYER_STATE, state=False)
        return self.status_midi_player

    def toggle_midi_playback(self, fname=None):
        if libsmf.getPlayState() == zynsmf.PLAY_STATE_STOPPED:
            self.start_midi_playback(fname)
        else:
            self.stop_midi_playback()

    # ---------------------------------------------------------------------------
    # Core Network Services
    # ---------------------------------------------------------------------------

    def start_wifi(self):
        self.start_busy("start_wifi", "connecting to WIFI")
        if not zynconf.start_wifi():
            self.set_busy_error("ERROR CONNECTING TO WIFI", "Can't start WIFI network!")
            sleep(2.0)
        self.end_busy("start_wifi")

    def start_wifi_hotspot(self):
        self.start_busy("start_wifi_hotspot", "starting WIFI HotSpot")
        if not zynconf.start_wifi_hotspot():
            self.set_busy_error("ERROR STARTING WIFI HOTSPOT", "Can't start WIFI HotSpot!")
            sleep(2.0)
        self.end_busy("start_wifi_hotspot")

    def stop_wifi(self):
        self.start_busy("stop_wifi", "stopping WIFI")
        if not zynconf.stop_wifi():
            self.set_busy_error("ERROR STOPPING WIFI", "Can't stop WIFI network")
            sleep(2.0)
        self.end_busy("stop_wifi")

    def start_vncserver(self, save_config=True):
        # Start VNC for Zynthian-UI
        self.start_busy("start_vncserver", "starting VNC")

        if not zynconf.is_service_active("vncserver0"):
            try:
                logging.info("STARTING VNC-UI SERVICE")
                self.set_busy_details("starting VNC-UI service")
                check_output("systemctl start novnc0", shell=True)
                zynthian_gui_config.vncserver_enabled = 1
            except Exception as e:
                logging.error(e)
                self.set_busy_error("ERROR STARTING VNC-UI", e)
                sleep(2.0)

        # Start VNC for Engine's native GUIs
        if not zynconf.is_service_active("vncserver1"):
            # Save state and stop engines
            if self.chain_manager.get_chain_count() > 0:
                self.save_last_state_snapshot()
                restore_state = True
            else:
                restore_state = False
            # Start VNC for Engines
            try:
                logging.info("STARTING VNC-ENGINES SERVICE")
                self.set_busy_details("starting VNC-ENGINES service")
                check_output("systemctl start novnc1", shell=True)
                zynthian_gui_config.vncserver_enabled = 1
            except Exception as e:
                logging.error(e)
                self.set_busy_error("ERROR STARTING VNC-ENGINES", e)
                sleep(2.0)
            # Restore state
            if restore_state:
                self.load_last_state_snapshot()

        # Update Config
        if save_config:
            zynconf.save_config({
                "ZYNTHIAN_VNCSERVER_ENABLED": str(zynthian_gui_config.vncserver_enabled)
            })

        self.end_busy("start_vncserver")

    def stop_vncserver(self, save_config=True):
        self.start_busy("stop_vncserver", "stopping VNC")

        # Stop VNC for Zynthian-UI
        if zynconf.is_service_active("vncserver0"):
            try:
                logging.info("STOPPING VNC-UI SERVICE")
                self.set_busy_details("stopping VNC-UI service")
                check_output("systemctl stop vncserver0", shell=True)
                zynthian_gui_config.vncserver_enabled = 0
            except Exception as e:
                logging.error(e)
                self.set_busy_error("ERROR STOPPING VNC-UI", e)
                sleep(2.0)

        # Start VNC for Engine's native GUIs
        if zynconf.is_service_active("vncserver1"):
            # Save state and stop engines
            if len(self.chain_manager.processors) > 0:
                self.save_last_state_snapshot()
                restore_state = True
            else:
                restore_state = False
            # Stop VNC for engiens
            try:
                logging.info("STOPPING VNC-ENGINES SERVICE")
                self.set_busy_details("stopping VNC-ENGINES service")
                check_output("systemctl stop vncserver1", shell=True)
                zynthian_gui_config.vncserver_enabled = 0
            except Exception as e:
                logging.error(e)
                self.set_busy_error("ERROR STOPPING VNC-ENGINES", e)
                sleep(2.0)
            # Restore state
            if restore_state:
                self.load_last_state_snapshot()

        # Update Config
        if save_config:
            zynconf.save_config({
                "ZYNTHIAN_VNCSERVER_ENABLED": str(zynthian_gui_config.vncserver_enabled)
            })

        self.end_busy("stop_vncserver")

    # Start/Stop VNC Server depending on configuration
    def default_vncserver(self):
        if zynthian_gui_config.vncserver_enabled:
            self.start_vncserver(False)
        else:
            self.stop_vncserver(False)

    # ---------------------------------------------------------------------------
    # MIDI Network Services
    # ---------------------------------------------------------------------------

    # Start/Stop RTP-MIDI depending on configuration
    def default_rtpmidi(self):
        if zynthian_gui_config.midi_rtpmidi_enabled:
            self.start_rtpmidi(False)
        else:
            self.stop_rtpmidi(False)

    def start_rtpmidi(self, save_config=True, wait=0):
        self.start_busy("start_rtpmidi", "starting RTP-MIDI")
        logging.info("STARTING RTP-MIDI")
        try:
            check_output("systemctl start jackrtpmidid", shell=True)
            zynthian_gui_config.midi_rtpmidi_enabled = 1
            # Update MIDI profile
            if save_config:
                zynconf.update_midi_profile({
                    "ZYNTHIAN_MIDI_RTPMIDI_ENABLED": str(zynthian_gui_config.midi_rtpmidi_enabled)
                })
            # Call autoconnect after a little time
            sleep(wait)
            zynautoconnect.request_midi_connect(True)
        except Exception as e:
            logging.error(e)
            self.set_busy_error("ERROR STARTING RTP-MIDI", e)
            sleep(2.0)

        self.end_busy("start_rtpmidi")

    def stop_rtpmidi(self, save_config=True, wait=0):
        self.start_busy("stop_rtpmidi", "stopping RTP-MIDI")
        logging.info("STOPPING RTP-MIDI")
        try:
            check_output("systemctl stop jackrtpmidid", shell=True)
            zynthian_gui_config.midi_rtpmidi_enabled = 0
            # Update MIDI profile
            if save_config:
                zynconf.update_midi_profile({
                    "ZYNTHIAN_MIDI_RTPMIDI_ENABLED": str(zynthian_gui_config.midi_rtpmidi_enabled)
                })
            sleep(wait)

        except Exception as e:
            logging.error(e)
            self.set_busy_error("ERROR STOPPING RTP-MIDI", e)
            sleep(2.0)

        self.end_busy("stop_rtpmidi")

    def start_qmidinet(self, save_config=True, wait=0):
        self.start_busy("start_qmidinet", "starting QMidiNet")
        logging.info("STARTING QMidiNet")
        try:
            check_output("systemctl start qmidinet", shell=True)
            zynthian_gui_config.midi_network_enabled = 1
            # Update MIDI profile
            if save_config:
                zynconf.update_midi_profile({
                    "ZYNTHIAN_MIDI_NETWORK_ENABLED": str(zynthian_gui_config.midi_network_enabled)
                })
            # Call autoconnect after a little time
            sleep(wait)
            zynautoconnect.request_midi_connect(True)
        except Exception as e:
            logging.error(e)
            self.set_busy_error("ERROR STARTING QMidiNet", e)
            sleep(2.0)

        self.end_busy("start_qmidinet")

    def stop_qmidinet(self, save_config=True, wait=0):
        self.start_busy("stop_qmidinet", "stopping QMidiNet")
        logging.info("STOPPING QMidiNet")
        try:
            check_output("systemctl stop qmidinet", shell=True)
            zynthian_gui_config.midi_network_enabled = 0
            # Update MIDI profile
            if save_config:
                zynconf.update_midi_profile({
                    "ZYNTHIAN_MIDI_NETWORK_ENABLED": str(zynthian_gui_config.midi_network_enabled)
                })
            sleep(wait)
        except Exception as e:
            logging.error(e)
            self.set_busy_error("ERROR STOPPING QMidiNet", e)
            sleep(2.0)

        self.end_busy("stop_qmidinet")

    # Start/Stop QMidiNet depending on configuration
    def default_qmidinet(self):
        if zynthian_gui_config.midi_network_enabled:
            self.start_qmidinet(False)
        else:
            self.stop_qmidinet(False)

    def start_touchosc2midi(self, save_config=True, wait=0):
        self.start_busy("start_touchosc2midi", "starting Touch-OSC")
        logging.info("STARTING touchosc2midi")
        try:
            check_output("systemctl start touchosc2midi", shell=True)
            zynthian_gui_config.midi_touchosc_enabled = 1
            # Update MIDI profile
            if save_config:
                zynconf.update_midi_profile({
                    "ZYNTHIAN_MIDI_TOUCHOSC_ENABLED": str(zynthian_gui_config.midi_touchosc_enabled)
                })
            # Call autoconnect after a little time
            zynautoconnect.request_midi_connect(True)
            sleep(wait)
        except Exception as e:
            logging.error(e)
            self.set_busy_error("ERROR STARTING Touch-OSC", e)
            sleep(2.0)

        self.end_busy("start_touchosc2midi")

    def stop_touchosc2midi(self, save_config=True, wait=0):
        self.start_busy("stop_touchosc2midi", "stopping Touch-OSC")
        logging.info("STOPPING touchosc2midi")
        try:
            check_output("systemctl stop touchosc2midi", shell=True)
            zynthian_gui_config.midi_touchosc_enabled = 0
            # Update MIDI profile
            if save_config:
                zynconf.update_midi_profile({
                    "ZYNTHIAN_MIDI_TOUCHOSC_ENABLED": str(zynthian_gui_config.midi_touchosc_enabled)
                })
            sleep(wait)
        except Exception as e:
            logging.error(e)
            self.set_busy_error("ERROR STOPPING Touch-OSC", e)
            sleep(2.0)

        self.end_busy("stop_touchosc2midi")

    # Start/Stop TouchOSC depending on configuration
    def default_touchosc(self):
        if zynthian_gui_config.midi_touchosc_enabled:
            self.start_touchosc2midi(False)
        else:
            self.stop_touchosc2midi(False)

    def start_bluetooth(self, save_config=True, wait=0):
        self.start_busy("start_bluetooth", "starting Bluetooth")
        logging.info("STARTING Bluetooth")
        try:
            check_output("systemctl start bluetooth", shell=True)
            zynthian_gui_config.bluetooth_enabled = 1
            # Update MIDI profile
            if save_config:
                zynconf.update_midi_profile({
                    "ZYNTHIAN_MIDI_BLE_ENABLED": str(zynthian_gui_config.bluetooth_enabled)
                })
            # Call autoconnect after a little time
            sleep(wait)
            zynautoconnect.request_midi_connect(True)
        except Exception as e:
            logging.error(e)
            self.set_busy_error("ERROR STARTING Bluetooth", e)
            sleep(2.0)

        self.end_busy("start_bluetooth")

    def stop_bluetooth(self, save_config=True, wait=0):
        self.start_busy("stop_bluetooth", "stopping Bluetooth")
        logging.info("STOPPING bluetooth")
        try:
            check_output("systemctl stop bluetooth", shell=True)
            zynthian_gui_config.bluetooth_enabled = 0
            # Update MIDI profile
            if save_config:
                zynconf.update_midi_profile({
                    "ZYNTHIAN_MIDI_BLE_ENABLED": str(zynthian_gui_config.bluetooth_enabled)
                })
            sleep(wait)
        except Exception as e:
            logging.error(e)
            self.set_busy_error("ERROR STOPPING Bluetooth", e)
            sleep(2.0)

        self.end_busy("stop_bluetooth")

    # Start/Stop Bluetooth depending on configuration
    def default_bluetooth(self):
        if zynthian_gui_config.bluetooth_enabled:
            self.start_bluetooth(False)
        else:
            self.stop_bluetooth(False)


    def start_aubionotes(self, save_config=True, wait=0):
        self.start_busy("start_aubionotes", "starting AubioNotes")
        logging.info("STARTING aubionotes")
        try:
            check_output("systemctl start aubionotes", shell=True)
            zynthian_gui_config.midi_aubionotes_enabled = 1
            # Update MIDI profile
            if save_config:
                zynconf.update_midi_profile({
                    "ZYNTHIAN_MIDI_AUBIONOTES_ENABLED": str(zynthian_gui_config.midi_aubionotes_enabled)
                })
            # Call autoconnect after a little time
            sleep(wait)
            zynautoconnect.request_midi_connect(True)
            zynautoconnect.request_audio_connect()
        except Exception as e:
            logging.error(e)
            self.set_busy_error("ERROR STARTING AubioNotes", e)
            sleep(2.0)

        self.end_busy("start_aubionotes")


    def stop_aubionotes(self, save_config=True, wait=0):
        self.start_busy("stop_aubionotes", "stopping AubioNotes")
        logging.info("STOPPING aubionotes")
        try:
            check_output("systemctl stop aubionotes", shell=True)
            zynthian_gui_config.midi_aubionotes_enabled = 0
            # Update MIDI profile
            if save_config:
                zynconf.update_midi_profile({
                    "ZYNTHIAN_MIDI_AUBIONOTES_ENABLED": str(zynthian_gui_config.midi_aubionotes_enabled)
                })
            sleep(wait)
        except Exception as e:
            logging.error(e)
            self.set_busy_error("ERROR STOPPING AubioNotes", e)
            sleep(2.0)

        self.end_busy("stop_aubionotes")

    # Start/Stop AubioNotes depending on configuration
    def default_aubionotes(self):
        if zynthian_gui_config.midi_aubionotes_enabled:
            self.start_aubionotes(False)
        else:
            self.stop_aubionotes(False)

    # ---------------------------------------------------------------------------
    # Zynthian Config Info
    # ---------------------------------------------------------------------------

    def get_zynthian_config(self, varname):
        try:
            return eval("zynthian_gui_config.{}".format(varname))
        except:
            return None

    def allow_rbpi_headphones(self):
        try:
            return self.alsa_mixer_processor.engine.allow_rbpi_headphones()
        except:
            return False

    def check_for_updates(self):
        if self.checking_for_updates:
            return
        self.checking_for_updates = True
        def update_thread():
            try:
                repos = ["/zynthian/zyncoder", "/zynthian/zynthian-ui", "/zynthian/zynthian-sys", "/zynthian/zynthian-webconf", "/zynthian/zynthian-data"]
                for path in repos:
                    branch = check_output(["git", "-C", path, "rev-parse", "--abbrev-ref", "HEAD"], encoding="utf-8").strip()
                    local_hash = check_output(["git", "-C", path, "rev-parse", "HEAD"], encoding="utf-8").strip()
                    remote_hash = check_output(["git", "-C", path, "ls-remote", "origin", branch], encoding="utf-8").strip().split('\t')[0]
                    self.update_available |= local_hash != remote_hash
            except:
                self.update_available = False
            self.checking_for_updates = False

        thread = Thread(target=update_thread, args=())
        thread.name = "Check update"
        thread.daemon = True  # thread dies with the program
        thread.start()

    # ---------------------------------------------------------------------------
