#!/usr/bin/python3
# -*- coding: utf-8 -*-
# ******************************************************************************
# ZYNTHIAN PROJECT: Zynthian GUI
#
# Main Class for Zynthian GUI
#
# Copyright (C) 2015-2026 Fernando Moyano <jofemodo@zynthian.org>
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
import liblo
import ffmpeg
import logging
import traceback
import importlib
from time import sleep
from queue import Empty
from pathlib import Path
from time import monotonic
from datetime import datetime
from threading import Thread, Lock, Event

# Zynthian specific modules
import zynconf
import zynautoconnect

from zyncoder.zyncore import lib_zyncore
from zynlibs.zynseq import *

from zyngine.zynthian_signal_manager import zynsigman
from zyngine.zynthian_state_manager import zynthian_state_manager

from zyngui import zynthian_gui_config
from zyngui import zynthian_gui_keybinding
from zyngui.multitouch import MultiTouch

from zyngui.zynthian_gui_none import zynthian_gui_none
from zyngui.zynthian_gui_info import zynthian_gui_info
from zyngui.zynthian_gui_help import zynthian_gui_help
from zyngui.zynthian_gui_splash import zynthian_gui_splash
from zyngui.zynthian_gui_loading import zynthian_gui_loading
from zyngui.zynthian_gui_option import zynthian_gui_option
from zyngui.zynthian_gui_confirm import zynthian_gui_confirm
from zyngui.zynthian_gui_file_selector import zynthian_gui_file_selector
from zyngui.zynthian_gui_keyboard import zynthian_gui_keyboard, OSK_QWERTY, OSK_NUMPAD

from zyngui.zynthian_gui_engine import zynthian_gui_engine
from zyngui.zynthian_gui_add_chain import zynthian_gui_add_chain
from zyngui.zynthian_gui_chain_control import zynthian_gui_chain_control
from zyngui.zynthian_gui_chain_options import zynthian_gui_chain_options
from zyngui.zynthian_gui_chain_manager import zynthian_gui_chain_manager
from zyngui.zynthian_gui_processor_options import zynthian_gui_processor_options

from zyngui.zynthian_gui_bank import zynthian_gui_bank
from zyngui.zynthian_gui_preset import zynthian_gui_preset
from zyngui.zynthian_gui_control import zynthian_gui_control
from zyngui.zynthian_gui_control_xy import zynthian_gui_control_xy

from zyngui.zynthian_gui_midi_config import zynthian_gui_midi_config
from zyngui.zynthian_gui_midi_chan import zynthian_gui_midi_chan
from zyngui.zynthian_gui_midi_cc import zynthian_gui_midi_cc
from zyngui.zynthian_gui_midi_cc_range import zynthian_gui_midi_cc_range
from zyngui.zynthian_gui_midi_cc_single import zynthian_gui_midi_cc_single
from zyngui.zynthian_gui_midi_prog import zynthian_gui_midi_prog
from zyngui.zynthian_gui_midi_key_range import zynthian_gui_midi_key_range

from zyngui.zynthian_gui_audio_in import zynthian_gui_audio_in
from zyngui.zynthian_gui_audio_out import zynthian_gui_audio_out

from zyngui.zynthian_gui_snapshot import zynthian_gui_snapshot
from zyngui.zynthian_gui_zs3 import zynthian_gui_zs3
from zyngui.zynthian_gui_zs3_options import zynthian_gui_zs3_options

from zyngui.zynthian_gui_mixer import zynthian_gui_mixer
from zyngui.zynthian_gui_main_menu import zynthian_gui_main_menu
from zyngui.zynthian_gui_selector_grid import zynthian_gui_selector_grid

#from zyngui.zynthian_gui_arranger import zynthian_gui_arranger
from zyngui.zynthian_gui_pated_notes import zynthian_gui_pated_notes
from zyngui.zynthian_gui_pated_cc import zynthian_gui_pated_cc
from zyngui.zynthian_gui_midi_recorder import zynthian_gui_midi_recorder

from zyngui.zynthian_gui_admin import zynthian_gui_admin
from zyngui.zynthian_gui_midi_profile import zynthian_gui_midi_profile
from zyngui.zynthian_gui_wifi import zynthian_gui_wifi
from zyngui.zynthian_gui_bluetooth import zynthian_gui_bluetooth
from zyngui.zynthian_gui_cv_config import zynthian_gui_cv_config
from zyngui.zynthian_gui_brightness_config import zynthian_gui_brightness_config
from zyngui.zynthian_gui_touchscreen_calibration import zynthian_gui_touchscreen_calibration

from zyngui.zynthian_gui_control_test import zynthian_gui_control_test

# TODO This constant should go somewhere else
ZMOP_MOD_INDEX = 16   # Dedicated zmop for MOD-UI

# -------------------------------------------------------------------------------
# Zynthian Main GUI Class
# -------------------------------------------------------------------------------

class DebugLock():
    """ Helper debug class to log mutex lock access
        Replace Lock() with DebugLock() when debugging lock issues,
        e.g. self.screen_lock = DebugLock()
    """
    def __init__(self):
        self.lock = Lock()

    def acquire(self):
        traceback.print_stack(limit=2)
        self.lock.acquire()

    def release(self):
        traceback.print_stack(limit=2)
        self.lock.release()

class zynthian_gui:
    # Subsignals are defined inside each module. Here we define GUI subsignals:

    SS_GUI_SHOW_SCREEN = 0
    SS_GUI_SHOW_SIDEBAR = 1
    SS_GUI_CONTROL_MODE = 2
    SS_GUI_SHOW_FILE_SELECTOR = 3
    SS_GUI_TOGGLE_ALT_MODE = 4
    SS_GUI_SHOW_MESSAGE = 5
    SS_GUI_LAUNCHER_MODE = 6

    # Screen Modes
    SCREEN_HMODE_NONE = 0
    SCREEN_HMODE_ADD = 1
    SCREEN_HMODE_REPLACE = 2
    SCREEN_HMODE_RESET = 3

    def __init__(self):
        self.capture_dir_sdc = os.environ.get('ZYNTHIAN_MY_DATA_DIR', "/zynthian/zynthian-my-data") + "/capture"
        self.ex_data_dir = os.environ.get('ZYNTHIAN_EX_DATA_DIR', "/media/root")

        self.alt_mode = False
        self.ignore_next_touch_release = False

        self.screens = {}
        self.screen_history = []
        self.current_screen = None
        self.screen_timer_id = None

        self.current_processor = None

        # Lock object to avoid concurrence problems when showing/closing screens
        self.screen_lock = Lock()

        self.state_manager = zynthian_state_manager()
        self.chain_manager = self.state_manager.chain_manager

        self.debug_thread = None
        self.busy_thread = None
        self.control_thread = None
        self.status_thread = None
        self.cuia_thread = None
        self.cuia_queue = self.state_manager.cuia_queue
        self.zynread_wait_flag = False
        self.zynpot_thread = None
        self.zynpot_event = Event()
        self.zynpot_lock = Lock()
        self.zynpot_dval = zynthian_gui_config.num_zynpots * [0]
        self.zynpot_pr_state = zynthian_gui_config.num_zynpots * [0]
        self.zynswitch_autolong_disabled = False
        self.dtsw = []

        self.exit_code = 0
        self.exit_flag = False
        self.exit_wait_count = 0

        self.status_counter = 0

        self.modify_chain_status = {"midi_thru": False, "audio_thru": False}

        self.capture_log = False
        self.capture_log_ts0 = None
        self.capture_log_fname = None
        self.capture_ffmpeg_proc = None
        self.touch = 0

        # Init LEDs
        self.wsleds = None
        self.init_wsleds()

        # Init multitouch driver
        #if zynthian_gui_config.check_kit_version(["V5"]) or
        if os.environ.get('DISPLAY_ROTATION', 'None') == 'Inverted':
            self.multitouch = MultiTouch(self.state_manager, invert_x_axis=True, invert_y_axis=True)
        else:
            self.multitouch = MultiTouch(self.state_manager)

        # Load keyboard binding map
        zynthian_gui_keybinding.load()

        # OSC config values
        self.osc_proto = liblo.UDP
        self.osc_server_port = zynconf.ServerPort["cuia_osc"]

        # Dictionary of {OSC clients, last heartbeat} registered for mixer feedback
        self.osc_clients = {}
        self.osc_heartbeat_timeout = 120  # Heartbeat timeout period

        self.prog_change = [0] * 16 # Track last program change for each MIDI channel

    # ---------------------------------------------------------------------------
    # Capture Log
    # ---------------------------------------------------------------------------

    def start_capture_log(self, title="ui_sesion"):
        now = datetime.now()
        self.capture_log_ts0 = now
        self.capture_log_fname = f"{title}-{now.strftime('%Y%m%d%H%M%S')}"
        if title == "ui_session":
            title = self.capture_log_fname
        self.capture_log = True
        self.start_capture_ffmpeg()
        if self.wsleds:
            self.wsleds.reset_last_state()
        self.write_capture_log(f"LAYOUT: {zynthian_gui_config.wiring_layout}")
        self.write_capture_log(f"RESOLUTION: {zynthian_gui_config.display_width},{zynthian_gui_config.display_height}")
        self.write_capture_log(f"TITLE: {title}")
        zynautoconnect.audio_connect_ffmpeg(timeout=2.0)

    def start_capture_ffmpeg(self):
        fbdev = os.environ.get("FRAMEBUFFER", "/dev/fb0")
        fpath = "{}/{}.mp4".format(self.capture_dir_sdc, self.capture_log_fname)
        #fpath = "rtp://localhost:1234"
        self.capture_ffmpeg_proc = ffmpeg.output(
            ffmpeg.input(":0", r=20, f="x11grab"),
            # ffmpeg.input(fbdev, r=20, f="fbdev"),
            # ffmpeg.input("sine=frequency=500", f="lavfi"),
            ffmpeg.input("ffmpeg", f="jack"),
            fpath,
            # vcodec="h264_v4l2m2m", acodec="aac") \
            #rtsp_transport="tcp",
            vcodec="libx264", pix_fmt="yuv420p", acodec="aac", preset="ultrafast", tune="zerolatency", movflags="faststart") \
            .global_args('-nostdin', '-hide_banner', '-nostats') \
            .run_async(quiet=True, overwrite_output=True)

    def stop_capture_ffmpeg(self):
        if self.capture_ffmpeg_proc:
            self.capture_ffmpeg_proc.terminate()
        self.capture_ffmpeg_proc = None

    def stop_capture_log(self):
        self.stop_capture_ffmpeg()
        self.capture_log = False
        self.capture_log_fname = None
        self.capture_log_ts0 = None

    def write_capture_log(self, message):
        if self.capture_log_fname:
            try:
                rts = str(datetime.now() - self.capture_log_ts0)
                fh = open("{}/{}.log".format(self.capture_dir_sdc, self.capture_log_fname), 'a')
                fh.write("{} {}\n".format(rts, message))
                fh.close()
            except Exception as e:
                logging.error("Can't write to capture log: {}".format(e))

    # ---------------------------------------------------------------------------
    # WSLeds Init
    # ---------------------------------------------------------------------------

    def init_wsleds(self):
        if zynthian_gui_config.touch_keypad:
            from zyngui.zynthian_wsleds_v5touch import zynthian_wsleds_v5touch
            self.wsleds = zynthian_wsleds_v5touch(self)
            self.wsleds.start()
        elif zynthian_gui_config.check_wiring_layout(["V5"]):
            from zyngui.zynthian_wsleds_v5 import zynthian_wsleds_v5
            self.wsleds = zynthian_wsleds_v5(self)
            self.wsleds.start()
        elif zynthian_gui_config.check_wiring_layout(["Z2"]):
            from zyngui.zynthian_wsleds_z2 import zynthian_wsleds_z2
            self.wsleds = zynthian_wsleds_z2(self)
            self.wsleds.start()

    # ---------------------------------------------------------------------------
    # Wiring Layout Init & Config
    # ---------------------------------------------------------------------------

    # Initialize custom switches, analog I/O, TOF sensors, etc.
    @staticmethod
    def wiring_midi_setup(current_chan=None):
        #logging.info("CUSTOM I/O SETUP...")

        # Configure Custom Switches
        for i, event in enumerate(zynthian_gui_config.custom_switch_midi_events):
            # logging.debug(f"\tSWITCH MIDI EVENT {i} => {event}")
            if event is not None:
                swi = 4 + i
                if event['type'] >= 0xF8:
                    lib_zyncore.setup_zynswitch_midi(swi, event['type'], 0, 0, 0)
                    logging.info(f"MIDI ZYNSWITCH {swi}: SYS-RT {event['type']}")
                else:
                    if event['chan'] is not None:
                        midi_chan = event['chan']
                    else:
                        midi_chan = current_chan

                    if midi_chan is not None:
                        lib_zyncore.setup_zynswitch_midi(swi, event['type'], midi_chan, event['num'], event['val'])
                        logging.info(f"MIDI ZYNSWITCH {swi}: {event['type']} CH#{midi_chan}, {event['num']}, {event['val']}")
                    else:
                        lib_zyncore.setup_zynswitch_midi(swi, 0, 0, 0, 0)
                        logging.info(f"MIDI ZYNSWITCH {swi}: DISABLED!")

        # Configure Zynaptik Analog Inputs (CV-IN)
        for i, event in enumerate(zynthian_gui_config.zynaptik_ad_midi_events):
            # logging.debug(f"\tCV-IN MIDI EVENT {i} => {event}")
            if event is not None:
                if event['chan'] is not None:
                    midi_chan = event['chan']
                else:
                    midi_chan = current_chan

                if midi_chan is not None:
                    lib_zyncore.setup_zynaptik_cvin(i, event['type'], midi_chan, event['num'])
                    logging.info(f"ZYNAPTIK CV-IN {i}: {event['type']} CH#{midi_chan}, {event['num']}")
                else:
                    lib_zyncore.disable_zynaptik_cvin(i)
                    logging.info(f"ZYNAPTIK CV-IN {i}: DISABLED!")

        # Configure Zynaptik Analog Outputs (CV-OUT)
        for i, event in enumerate(zynthian_gui_config.zynaptik_da_midi_events):
            # logging.debug(f"\tCV-OUT MIDI EVENT {i} => {event}")
            if event is not None:
                if event['chan'] is not None:
                    midi_chan = event['chan']
                else:
                    midi_chan = current_chan

                if midi_chan is not None:
                    lib_zyncore.setup_zynaptik_cvout(i, event['type'], midi_chan, event['num'])
                    logging.info(f"ZYNAPTIK CV-OUT {i}: {event['type']} CH#{midi_chan}, {event['num']}")
                else:
                    lib_zyncore.disable_zynaptik_cvout(i)
                    logging.info(f"ZYNAPTIK CV-OUT {i}: DISABLED!")

        # Configure Zyntof Inputs (Distance Sensor)
        for i, event in enumerate(zynthian_gui_config.zyntof_midi_events):
            if event is not None:
                if event['chan'] is not None:
                    midi_chan = event['chan']
                else:
                    midi_chan = current_chan

                if midi_chan is not None:
                    lib_zyncore.setup_zyntof(i, event['type'], midi_chan, event['num'])
                    logging.info(f"ZYNTOF {i}: {event['type']} CH#{midi_chan}, {event['num']}")
                else:
                    lib_zyncore.disable_zyntof(i)
                    logging.info(f"ZYNTOF {i}: DISABLED!")

    def reload_wiring_layout(self):
        try:
            zynconf.load_config()
            zynthian_gui_config.config_custom_switches()
            zynthian_gui_config.config_zynaptik()
            zynthian_gui_config.config_zyntof()
            self.zynswitches_midi_setup()
            self.alt_mode = False
        except Exception as e:
            logging.error("ERROR configuring wiring: {}".format(e))

    # ---------------------------------------------------------------------------
    # OSC Management
    # ---------------------------------------------------------------------------

    def osc_init(self):
        try:
            self.osc_server = liblo.Server(self.osc_server_port, self.osc_proto)
            self.osc_server_port = self.osc_server.get_port()
            self.osc_server_url = liblo.Address('localhost', self.osc_server_port, self.osc_proto).get_url()
            logging.info("ZYNTHIAN-UI OSC server running in port {}".format(self.osc_server_port))
            self.osc_server.add_method(None, None, self.osc_cb_all)
        # except liblo.AddressError as err:
        except Exception as err:
            logging.error("ZYNTHIAN-UI OSC Server can't be started: {}".format(err))

    def osc_end(self):
        if self.osc_server:
            try:
                self.osc_server.free()
                logging.info("ZYNTHIAN-UI OSC server stopped")
            except Exception as err:
                logging.error("ZYNTHIAN-UI OSC server can't be stopped: {}".format(err))
        self.osc_server = None

    def osc_receive(self):
        while self.osc_server and self.osc_server.recv(0):
            pass

    # @liblo.make_method("RELOAD_MIDI_CONFIG", None)
    # @liblo.make_method(None, None)
    def osc_cb_all(self, path, args, types, src):
        logging.info("OSC MESSAGE '{}' from '{}'".format(path, src.url))

        parts = path.upper().split("/", 2)
        # TODO: message may have fewer parts than expected
        if parts[0] == "" and parts[1] == "CUIA":
            # Execute action
            cuia = parts[2].upper()
            if cuia != "POWER_SAVE":
                self.state_manager.set_event_flag()
            if self.state_manager.is_busy():
                logging.debug("BUSY! Ignoring OSC CUIA '{}' => {}".format(cuia, args))
                return
            self.cuia_queue.put_nowait((cuia, args, src))
            # Run autoconnect if needed
            zynautoconnect.request_audio_connect()
            zynautoconnect.request_midi_connect()
        elif parts[1] in ("MIXER", "DAWOSC"):
            #TODO: Fix OSC control of zynmixer
            self.state_manager.set_event_flag()
            part2 = parts[2]
            if part2 in ("HEARTBEAT", "SETUP"):
                if src.hostname not in self.osc_clients:
                    try:
                        if self.state_manager.zynmixer_chan.add_osc_client(src.hostname) < 0:
                            logging.warning("Failed to add OSC client registration {}".format(src.hostname))
                            return
                        if self.state_manager.zynmixer_bus.add_osc_client(src.hostname) < 0:
                            logging.warning("Failed to add OSC client registration {}".format(src.hostname))
                            return
                    except:
                        logging.warning("Error trying to add OSC client registration {}".format(src.hostname))
                        return
                self.osc_clients[src.hostname] = monotonic()
                self.state_manager.zynmixer_chan.enable_dpm(True)
                self.state_manager.zynmixer_bus.enable_dpm(True)
            else:
                mixer, param = part2.split("/")
                if mixer == "bus":
                    zynmixer = self.state_manager.zynmixer_bus
                else:
                    zynmixer = self.state_manager.zynmixer_chan
                if param[:6] == "VOLUME":
                    zynmixer.set_level(
                        int(part2[6:]), float(args[0]))
                if param[:5] == "FADER":
                    zynmixer.set_level(
                        int(part2[5:]), float(args[0]))
                if param[:5] == "LEVEL":
                    zynmixer.set_level(
                        int(part2[5:]), float(args[0]))
                elif param[:7] == "BALANCE":
                    zynmixer.set_balance(
                        int(part2[7:]), float(args[0]))
                elif param[:4] == "MUTE":
                    zynmixer.set_mute(
                        int(part2[4:]), int(args[0]))
                elif param[:4] == "SOLO":
                    zynmixer.set_solo(
                        int(part2[4:]), int(args[0]))
                elif param[:4] == "MONO":
                    zynmixer.set_mono(
                        int(part2[4:]), int(args[0]))
        else:
            logging.warning(f"Not supported OSC call '{path}'")

        # for a, t in zip(args, types):
        # logging.debug("argument of type '%s': %s" % (t, a))

    # ---------------------------------------------------------------------------
    # GUI Core Management
    # ---------------------------------------------------------------------------

    def create_screens(self):
        # Create Core UI Screens
        self.screens['none'] = zynthian_gui_none()
        self.screens['info'] = zynthian_gui_info()
        self.screens['help'] = zynthian_gui_help()
        self.screens['splash'] = zynthian_gui_splash()
        self.screens['loading'] = zynthian_gui_loading()
        self.screens['option'] = zynthian_gui_option()
        self.screens['confirm'] = zynthian_gui_confirm()
        self.screens['keyboard'] = zynthian_gui_keyboard()
        self.screens['file_selector'] = zynthian_gui_file_selector()

        self.screens['engine'] = zynthian_gui_engine()
        self.screens['chain_control'] = zynthian_gui_chain_control()
        self.screens['chain_options'] = zynthian_gui_chain_options()
        self.screens['chain_manager'] = zynthian_gui_chain_manager()
        self.screens['add_chain'] = zynthian_gui_add_chain()
        self.screens['processor_options'] = zynthian_gui_processor_options()

        self.screens['midi_config'] = zynthian_gui_midi_config()
        self.screens['midi_chan'] = zynthian_gui_midi_chan()
        self.screens['midi_cc'] = zynthian_gui_midi_cc()
        self.screens['midi_cc_range'] = zynthian_gui_midi_cc_range()
        self.screens['midi_cc_single'] = zynthian_gui_midi_cc_single()
        self.screens['midi_prog'] = zynthian_gui_midi_prog()
        self.screens['midi_key_range'] = zynthian_gui_midi_key_range()

        self.screens['audio_out'] = zynthian_gui_audio_out()
        self.screens['audio_in'] = zynthian_gui_audio_in()

        self.screens['bank'] = zynthian_gui_bank()
        self.screens['preset'] = zynthian_gui_preset()
        self.screens['control'] = zynthian_gui_control()
        self.screens['control_xy'] = zynthian_gui_control_xy()

        self.screens['snapshot'] = zynthian_gui_snapshot()
        self.screens['zs3'] = zynthian_gui_zs3()
        self.screens['zs3_options'] = zynthian_gui_zs3_options()

        self.screens['mixer'] = zynthian_gui_mixer()
        self.screens['main_menu'] = zynthian_gui_main_menu()
        self.screens['grid_sel'] = zynthian_gui_selector_grid()

        # Special Control Screens (processor ID < -1)
        self.screens['tempo'] = self.screens['control']
        self.screens['alsa_mixer'] = self.screens['control']
        self.screens['audio_player'] = self.screens['control']

        #self.screens['arranger'] = zynthian_gui_arranger()
        self.screens['pattern_editor'] = zynthian_gui_pated_notes()
        self.screens['pated_cc'] = zynthian_gui_pated_cc()
        self.screens['midi_recorder'] = zynthian_gui_midi_recorder()

        self.screens['admin'] = zynthian_gui_admin()
        self.screens['wifi'] = zynthian_gui_wifi()
        self.screens['bluetooth'] = zynthian_gui_bluetooth()
        self.screens['midi_profile'] = zynthian_gui_midi_profile()
        self.screens['brightness_config'] = zynthian_gui_brightness_config()
        self.screens['touchscreen_calibration'] = zynthian_gui_touchscreen_calibration()
        self.screens['control_test'] = zynthian_gui_control_test()

        # Root screen
        self.screens['root'] = self.screens['mixer']
        self.screens['launcher'] = self.screens['mixer']
        #self.screens['root'] = self.screens['none']

        # Create Zynaptik-related screens
        try:
            if callable(lib_zyncore.init_zynaptik):
                self.screens['cv_config'] = zynthian_gui_cv_config()
        except:
            pass

        # Initialize switches
        try:
            self.zynswitches_init()
            self.zynswitches_midi_setup()
        except Exception as e:
            logging.error(f"ERROR initializing Switches & Wiring MIDI: {e}")

        # Initialize OSC
        self.osc_init()

        # Run debug thread
        if zynthian_gui_config.debug_thread:
            self.start_debug_thread()

        # Initial loading screen. We need "current_screen" from here ...
        self.show_loading("Starting User Interface")

        # Start processing signals, threads & polling
        self.register_signals()
        self.start_busy_thread()
        self.start_control_thread()
        self.start_status_thread()
        self.start_cuia_thread()
        self.start_zynpot_thread()
        self.start_polling()

    # --------------------------------------------------------------------------
    # Debug thread: set a breakpoint and exit when continue
    # --------------------------------------------------------------------------

    def start_debug_thread(self):
        self.debug_thread = Thread(target=self.debug_task, args=())
        self.debug_thread.name = "debug"
        self.debug_thread.daemon = True  # thread dies with the program
        self.debug_thread.start()

    def debug_task(self):
        breakpoint()
        self.screens['admin'].exit_to_console()

    # --------------------------------------------------------------------------
    # Start task => Must run as a thread, so we can go into tkinter loop
    # --------------------------------------------------------------------------

    def run_start_thread(self):
        self.start_thread = Thread(target=self.start_task, args=())
        self.start_thread.name = "start"
        self.start_thread.daemon = True  # thread dies with the program
        self.start_thread.start()

    def start_task(self):
        self.state_manager.start_busy("ui startup")

        snapshot_loaded = False
        if zynthian_gui_config.control_test_enabled:
            init_screen = "control_test"
        else:
            init_screen = "add_chain"
            # Try to load "last_state" snapshot...
            if zynthian_gui_config.restore_last_state:
                snapshot_loaded = self.state_manager.load_last_state_snapshot()
            # Try to load "default" snapshot...
            if not snapshot_loaded:
                snapshot_loaded = self.state_manager.load_default_snapshot()

        if snapshot_loaded:
            init_screen = "root"
        else:
            # Init MIDI Subsystem => MIDI Profile
            self.state_manager.init_midi()
            self.state_manager.init_midi_services()

        # Run autoconnect if needed
        zynautoconnect.request_audio_connect()
        zynautoconnect.request_midi_connect()

        self.state_manager.end_busy("ui startup")

        # Show initial screen
        self.show_screen(init_screen, zynthian_gui.SCREEN_HMODE_RESET)

    def hide_screens(self, exclude=None):
        if not exclude:
            exclude = self.current_screen
        exclude_obj = self.screens[exclude]

        for screen_name, screen_obj in self.screens.items():
            if screen_obj != exclude_obj:
                screen_obj.hide()

    def reset_screen_history(self):
        self.screen_history = []

    def show_screen(self, screen=None, hmode=SCREEN_HMODE_ADD, params=None):
        self.screen_lock.acquire()
        self.cancel_screen_timer()
        # self.current_processor = None

        if screen is None:
            if self.current_screen:
                screen = self.get_current_screen()
            else:
                screen = "root"
        if screen == "root":
            try:
                if self.screens["mixer"].launcher_mode:
                    screen = "launcher"
                else:
                    screen = "mixer"
            except:
                logging.warning("Mixer view not yet created!")
                screen = "mixer"
        elif screen == "mixer":
            self.screens[screen].set_launcher_mode(False)
        elif screen == "launcher":
            self.screens[screen].set_launcher_mode(True)
        elif screen == "alsa_mixer":
            self.state_manager.alsa_mixer_processor.refresh_controllers(params)
            self.current_processor = self.state_manager.alsa_mixer_processor
        elif screen == "tempo":
            self.state_manager.tempo_processor.refresh_controllers(params)
            self.current_processor = self.state_manager.tempo_processor
        elif screen == "audio_player":
            if self.state_manager.audio_player:
                self.current_processor = self.state_manager.audio_player
                # self.state_manager.audio_player.refresh_controllers()
            else:
                logging.error("Audio Player not created!")
                self.screen_lock.release()
                return
        else:
            self.current_processor = self.get_current_processor()

        if screen not in ("bank", "preset", "option"):
            self.chain_manager.restore_presets()

        root_screens = ("root", "mixer", "launcher")
        if screen in root_screens and self.current_screen in root_screens:
            dummy_show = True
        else:
            dummy_show = False

        if not dummy_show and not self.screens[screen].build_view():
            self.screen_lock.release()
            # self.show_screen_reset("mixer")
            self.close_screen()
            return

        if hmode == zynthian_gui.SCREEN_HMODE_ADD:
            if len(self.screen_history) == 0 or self.screen_history[-1] != screen:
                self.prune_screen_history(screen)
                self.screen_history.append(screen)
        elif hmode == zynthian_gui.SCREEN_HMODE_REPLACE:
            self.screen_history.pop()
            self.prune_screen_history(screen)
            self.screen_history.append(screen)
        elif hmode == zynthian_gui.SCREEN_HMODE_RESET:
            self.screen_history = [screen]

        if self.current_screen != screen:
            if not dummy_show:
                self.screens[screen].show()
            self.current_screen = screen
            if not dummy_show:
                self.hide_screens(exclude=screen)
            zynsigman.send(zynsigman.S_GUI, zynsigman.SS_GUI_SHOW_SCREEN, screen=screen)

        self.screen_lock.release()

    def show_modal(self, screen=None):
        self.show_screen(screen, hmode=zynthian_gui.SCREEN_HMODE_ADD)

    def replace_screen(self, screen=None):
        self.show_screen(screen, hmode=zynthian_gui.SCREEN_HMODE_REPLACE)

    def show_screen_reset(self, screen=None):
        self.show_screen(screen, hmode=zynthian_gui.SCREEN_HMODE_RESET)

    def show_current_screen(self):
        self.show_screen(self.current_screen)

    def is_shown_alsa_mixer(self):
        return self.current_processor == self.state_manager.alsa_mixer_processor

    def is_shown_audio_player(self):
        return self.current_processor == self.state_manager.audio_player

    def close_screen(self, screen=None):
        """ Closes the current screen or optionally the specified screen """

        if screen is None:
            screen = self.get_current_screen()
        self.prune_screen_history(screen, soft=False)
        try:
            last_screen = self.screen_history.pop()
        except:
            last_screen = "root"

        if last_screen not in self.screens:
            logging.error(f"Can't back to screen '{last_screen}'. It doesn't exist!")
            last_screen = "root"
        elif last_screen in ("mixer", "launcher"):
            last_screen = "root"
        logging.debug(f"CLOSE SCREEN '{self.current_screen}' => Back to '{last_screen}'")
        self.show_screen(last_screen)

    def purge_screen_history(self, screen):
        self.screen_history = list(filter(lambda i: i != screen, self.screen_history))

    def prune_screen_history(self, screen, soft=True):
        logging.debug(f"SCREEN HISTORY => {self.screen_history}")
        try:
            i = self.screen_history.index(screen)
            last_screen = self.screen_history[-1]
            self.screen_history = self.screen_history[0:i]
            if soft and screen == last_screen:
                self.screen_history.append(screen)
        except:
            pass
        logging.debug(f"PRUNE '{screen}' FROM SCREEN HISTORY => {self.screen_history}")

    def back_screen(self):
        try:
            res = self.screens[self.current_screen].back_action()
        except:
            res = False

        if not res:
            self.close_screen()

    def cancel_screen_timer(self):
        if self.screen_timer_id:
            zynthian_gui_config.top.after_cancel(self.screen_timer_id)
            self.screen_timer_id = None

    def toggle_screen(self, screen, hmode=SCREEN_HMODE_ADD):
        if self.current_screen != screen:
            self.show_screen(screen, hmode)
        else:
            self.close_screen()

    def get_current_screen(self):
        if self.current_screen in ("mixer", "launcher", "root"):
            screen = ("mixer", "launcher")[self.screens["mixer"].launcher_mode]
        else:
            screen = self.current_screen
        return screen

    def get_current_screen_obj(self):
        try:
            return self.screens[self.current_screen]
        except:
            return None

    def show_confirm(self, text, callback=None, cb_params=None):
        self.screen_lock.acquire()
        self.screens['confirm'].show(text, callback, cb_params)
        self.current_screen = 'confirm'
        self.hide_screens(exclude='confirm')
        self.screen_lock.release()

    def show_keyboard(self, callback, text="", max_chars=None):
        self.screens['keyboard'].set_mode(OSK_QWERTY)
        self.screen_lock.acquire()
        self.screens['keyboard'].show(callback, text, max_chars)
        self.current_screen = 'keyboard'
        self.hide_screens(exclude='keyboard')
        self.screen_lock.release()

    def show_numpad(self, callback, text="", max_chars=None):
        self.screens['keyboard'].set_mode(OSK_NUMPAD)
        self.screen_lock.acquire()
        self.screens['keyboard'].show(callback, text, max_chars)
        self.current_screen = 'keyboard'
        self.hide_screens(exclude='keyboard')
        self.screen_lock.release()

    def show_info(self, text, tms=None):
        self.screen_lock.acquire()
        self.screens['info'].show(text)
        self.current_screen = 'info'
        self.hide_screens(exclude='info')
        self.screen_lock.release()
        if tms:
            zynthian_gui_config.top.after(tms, self.hide_info)

    def add_info(self, text, tags=None):
        self.screens['info'].add(text, tags)

    def hide_info(self):
        if self.current_screen == 'info':
            self.close_screen()

    def hide_info_timer(self, tms=3000):
        if self.current_screen == 'info':
            self.cancel_screen_timer()
            self.screen_timer_id = zynthian_gui_config.top.after(tms, self.hide_info)

    def show_splash(self, text):
        self.screen_lock.acquire()
        self.screens['splash'].show(text)
        self.current_screen = 'splash'
        self.hide_screens(exclude='splash')
        self.screen_lock.release()

    def show_loading(self, title="", details=""):
        self.screens['loading'].set_title(title)
        self.screens['loading'].set_details(details)
        self.screen_lock.acquire()
        self.screens['loading'].show()
        self.current_screen = 'loading'
        self.hide_screens(exclude='loading')
        self.screen_lock.release()

    def show_loading_error(self, title="", details=""):
        self.screens['loading'].set_error(title)
        self.screens['loading'].set_details(details)
        self.screen_lock.acquire()
        self.screens['loading'].show()
        self.current_screen = 'loading'
        self.hide_screens(exclude='loading')
        self.screen_lock.release()

    def show_loading_warning(self, title="", details=""):
        self.screens['loading'].set_warning(title)
        self.screens['loading'].set_details(details)
        self.screen_lock.acquire()
        self.screens['loading'].show()
        self.current_screen = 'loading'
        self.hide_screens(exclude='loading')
        self.screen_lock.release()

    def show_loading_success(self, title="", details=""):
        self.screens['loading'].set_warning(title)
        self.screens['loading'].set_details(details)
        self.screen_lock.acquire()
        self.screens['loading'].show()
        self.current_screen = 'loading'
        self.hide_screens(exclude='loading')
        self.screen_lock.release()

    def set_loading_title(self, title):
        self.screens['loading'].set_title(title)

    def set_loading_error(self, title):
        self.screens['loading'].set_error(title)

    def set_loading_warning(self, title):
        self.screens['loading'].set_waning(title)

    def set_loading_success(self, title):
        self.screens['loading'].set_success(title)

    def set_loading_details(self, details):
        self.screens['loading'].set_details(details)

    def calibrate_touchscreen(self):
        self.show_screen('touchscreen_calibration')

    def brightness_config(self):
        self.show_screen('brightness_config')

    def midi_in_config(self, chain=None):
        self.screens['midi_config'].set_chain(chain)
        self.screens['midi_config'].midi_input = True
        self.show_screen('midi_config')

    def midi_out_config(self, chain=None):
        self.screens['midi_config'].set_chain(chain)
        self.screens['midi_config'].midi_input = False
        self.show_screen('midi_config')

    def show_help(self, topic=None):
        if not topic:
            topic = self.current_screen
        fpath = None
        if topic == "chain_control":
            proc = self.get_current_processor()
            fpath = f"./help/widgets/{proc.name.lower()}.html"
            if not Path(fpath).exists():
                fpath = None
        if not fpath:
            fpath = f"./help/{zynthian_gui_config.layout['name']}/{topic}.html"
            if not Path(fpath).exists():
                fpath = None
        if fpath:
            self.screens['help'].load_file(fpath)
        elif topic != "help":
            logging.warning(f"No help for '{topic}'")

    # TODO: Rename - this is called for various chain manipulation purposes
    def modify_chain(self, status=None):
        """Manage the stages of adding or changing a processor or chain

        status - Dictionary of status (Default: continue with current status)
        """

        if status:
            self.modify_chain_status = status

        if "engine" in self.modify_chain_status:
            # We always need an engine for creating or modifying a chain!
            if "chain_id" in self.modify_chain_status:
                # Modifying an existing chain
                if "processor" in self.modify_chain_status:
                    # Replacing processor in existing chain
                    chain = self.chain_manager.get_chain(self.modify_chain_status["chain_id"])
                    old_processor = self.modify_chain_status["processor"]
                    if chain and old_processor:
                        slot = chain.get_slot(old_processor)
                        processor = self.chain_manager.add_processor(self.modify_chain_status["chain_id"],
                                                                     self.modify_chain_status["engine"], slot)
                        if processor:
                            self.chain_manager.remove_processor(self.modify_chain_status["chain_id"], old_processor)
                            chain.rebuild_graph()
                            zynautoconnect.autoconnect()
                            self.close_screen("loading")
                            self.chain_control(self.modify_chain_status["chain_id"], processor, force_bank_preset=True)
                else:
                    # Adding processor to existing chain
                    if "slot" in self.modify_chain_status:
                        slot = self.modify_chain_status["slot"]
                    else:
                        slot = None
                    processor = self.chain_manager.add_processor(self.modify_chain_status["chain_id"],
                                                                 self.modify_chain_status["engine"], slot)
                    if processor:
                        zynautoconnect.autoconnect()
                        self.close_screen("loading")
                        self.chain_control(self.modify_chain_status["chain_id"], processor, force_bank_preset=True)
                    else:
                        #self.show_screen_reset("root")
                        self.chain_control(self.modify_chain_status["chain_id"])
                        self.show_info("Failed to create processor", 1500)
            else:
                # Creating a new chain
                if "midi_chan" in self.modify_chain_status:
                    # We know the MIDI channel so create a new chain and processor
                    if "midi_thru" not in self.modify_chain_status:
                        self.modify_chain_status["midi_thru"] = False
                    if "audio_thru" not in self.modify_chain_status:
                        self.modify_chain_status["audio_thru"] = False
                    if "mixbus" not in self.modify_chain_status:
                        self.modify_chain_status["mixbus"] = False
                    # Detect MOD-UI special chain and assign dedicated zmop index
                    if self.modify_chain_status["engine"] == "MD":
                        zmop_index = ZMOP_MOD_INDEX
                    else:
                        zmop_index = None
                    if "pos" in self.modify_chain_status:
                        pos = self.modify_chain_status["pos"]
                    else:
                        pos = None
                    chain_id = self.chain_manager.add_chain(
                        None,
                        self.modify_chain_status["midi_chan"],
                        self.modify_chain_status["midi_thru"],
                        self.modify_chain_status["audio_thru"],
                        zmop_index,
                        chain_pos=pos,
                        fast_refresh=False
                    )
                    if chain_id is None:
                        self.show_screen_reset("root")
                        self.show_info("Failed to create chain", 1500)
                        return
                    processor = self.chain_manager.add_processor(chain_id, self.modify_chain_status["engine"])
                    if self.chain_manager.chains[chain_id].synth_slots or self.modify_chain_status["audio_thru"]:
                        if self.modify_chain_status["mixbus"]:
                            am_proc = self.chain_manager.add_processor(chain_id, "MR")
                            self.chain_manager.set_chain_title(chain_id, am_proc.name)
                        else:
                            am_proc = self.chain_manager.add_processor(chain_id, "MI")
                    self.chain_manager.rebuild_optimisation_cache()
                    zynautoconnect.request_audio_connect(True)
                    zynautoconnect.request_midi_connect(True)
                    if processor and processor.eng_code != "CL":
                        self.close_screen("loading")
                        self.screen_history = []
                        self.chain_control(chain_id, processor, force_bank_preset=True)
                    else:
                        # Created empty chain
                        # self.chain_manager.set_active_chain_by_id(chain_id)
                        #self.show_screen_reset("chain_manager")
                        self.chain_control(chain_id)
                else:
                    # Select MIDI channel
                    logging.debug(self.modify_chain_status)
                    #if self.modify_chain_status["type"] == "MIDI Tool":
                        # Enable "ALl Channels" option for MIDI chains
                    #    chan_all = True
                    #else:
                    #    chan_all = False
                    self.screens["midi_chan"].set_mode("ADD", chan_all=True)
                    self.show_screen("midi_chan")

        elif "type" in self.modify_chain_status:
            # We know the type so select the engine
            self.show_screen("engine")
        else:
            # TODO: Offer type selection
            pass

    def chain_control(self, chain_id=None, processor=None, hmode=SCREEN_HMODE_ADD, force_bank_preset=False):
        if chain_id is None:
            chain_id = self.chain_manager.active_chain.chain_id
        else:
            self.chain_manager.set_active_chain_by_id(chain_id)

        if processor is None:
            self.current_processor = self.chain_manager.get_active_chain().current_processor
        elif processor in self.chain_manager.get_processors(chain_id):
            self.current_processor = processor
        else:
            self.current_processor = None
            for t in ["MIDI Synth", "MIDI Tool", "Audio Effect", "Special"]:
                processors = self.chain_manager.get_processors(chain_id, t)
                if processors:
                    self.current_processor = processors[0]
                    break

        if self.current_processor.id < -1:
            screen_name = "control"
        else:
            screen_name = "chain_control"
        if self.current_processor and force_bank_preset:
            # If not preset is selected => bank/preset selector screen
            if not self.current_processor.get_preset_name():
                if len(self.current_processor.get_bank_list()) > 1:
                    screen_name = 'bank'
                else:
                    self.current_processor.set_bank(0)
                    self.current_processor.load_preset_list()
                    if len(self.current_processor.preset_list) > 1:
                        screen_name = 'preset'
                    else:
                        if len(self.current_processor.preset_list):
                            self.current_processor.set_preset(0)
        self.show_screen(screen_name, hmode)

    def show_control(self):
        self.chain_control()

    def toggle_favorites(self):
        curproc = self.get_current_processor()
        if curproc:
            curproc.toggle_show_fav_presets()
            self.show_screen("preset")

    def show_favorites(self):
        curproc = self.get_current_processor()
        if curproc:
            self.cuia_bank_preset()
            curproc.set_show_fav_presets(True)
            self.show_screen("preset")

    def set_current_processor(self, processor):
        self.current_processor = processor
        try:
            self.chain_manager.active_chain.set_current_processor(processor)
        except:
            pass

    def get_current_processor(self):
        """ Get the currently selected processor object
            This may not be within a chain.
        """
        if self.current_processor:
            return self.current_processor
        try:
            return self.chain_manager.active_chain.current_processor
        except:
            return None

    def get_current_processor_wait(self):
        # Try until processor is ready
        for j in range(100):
            curproc = self.get_current_processor()
            if curproc:
                return curproc
            else:
                sleep(0.1)

    def get_alt_mode(self):
        try:
            return self.screens[self.current_screen].get_alt_mode()
        except:
            return self.alt_mode

    def get_global_alt_mode(self):
        return self.alt_mode

    def set_global_alt_mode(self, alt_mode):
        self.alt_mode = alt_mode
        zynsigman.send(zynsigman.S_GUI, zynsigman.SS_GUI_TOGGLE_ALT_MODE, alt_mode=self.alt_mode)

    def clean_all(self):
        if self.chain_manager.get_chain_count() > 1:
            self.state_manager.save_last_state_snapshot()
        self.state_manager.clean_all()
        self.show_screen_reset('chain_manager')

    def clean_chains(self):
        if self.chain_manager.get_chain_count() > 1:
            self.state_manager.save_last_state_snapshot()
        self.state_manager.clean_chains()
        self.show_screen_reset('chain_manager')

    def clean_sequences(self):
        if self.chain_manager.get_chain_count() > 1:
            self.state_manager.save_last_state_snapshot()
        self.state_manager.clean_sequences()
        self.show_screen_reset('launcher')

    # -------------------------------------------------------------------
    # Callable UI Actions
    # -------------------------------------------------------------------

    @classmethod
    def get_cuia_list(cls):
        return [method[5:].upper() for method in dir(cls) if method.startswith('cuia_') is True]

    def callable_ui_action(self, cuia, params=None):
        logging.debug("CUIA '{}' => {}".format(cuia, params))
        screen_obj = self.get_current_screen_obj()
        # First, try screen-defined catch-all cuia function
        cuia_func = getattr(screen_obj, "callable_ui_action", None)
        if not callable(cuia_func) or not cuia_func(cuia, params):
            # Second, try screen-defined specific cuia function
            cuia_func_name = "cuia_" + cuia.lower()
            cuia_func = getattr(screen_obj, cuia_func_name, None)
            if not callable(cuia_func) or not cuia_func(params):
                # Third, call default CUIA function (defined in this class)
                cuia_func = getattr(self, cuia_func_name, None)
                if callable(cuia_func):
                    cuia_func(params)
                else:
                    logging.error("Unknown CUIA '{}'".format(cuia))
        # Capture CUIA for UI log
        if self.capture_log:
            self.write_capture_log("CUIA:{},{}".format(cuia, str(params)))

    def callable_ui_action_params(self, cuia_str):
        parts = cuia_str.split(" ", 2)
        cuia = parts[0]
        if len(parts) > 1:
            params = self.state_manager.parse_cuia_params(parts[1])
        else:
            params = None
        self.callable_ui_action(cuia, params)

    # System actions CUIA
    def cuia_nop(self, params):
        pass

    def cuia_toggle_alt_mode(self, params=None):
        self.set_global_alt_mode(not self.alt_mode)

    def cuia_help(self, params=None):
        self.show_help(params)

    def cuia_power_save(self, params=None):
        self.state_manager.set_power_save_mode(True)

    def cuia_power(self, params=None):
        if params == ['CONFIRM']:
            self.screens['admin'].power_off_confirmed()
        else:
            self.screens['admin'].power()

    def cuia_reboot(self, params=None):
        if params == ['CONFIRM']:
            self.screens['admin'].reboot_confirmed()
        else:
            self.screens['admin'].power()

    def cuia_restart_ui(self, params=None):
        self.screens['admin'].restart_gui()

    def cuia_exit_ui(self, params=None):
        self.screens['admin'].exit_to_console()

    def cuia_reload_wiring_layout(self, params=None):
        self.reload_wiring_layout()

    def cuia_reload_midi_config(self, params=None):
        self.state_manager.reload_midi_config()

    def cuia_reload_key_binding(self, params=None):
        zynthian_gui_keybinding.load()

    def cuia_last_state_action(self, params=None):
        self.screens['admin'].last_state_action()

    def cuia_workflow_capture_start(self, params=["ui_sesion"]):
        self.start_capture_log(params[0])

    def cuia_workflow_capture_stop(self, params=None):
        self.stop_capture_log()

    def cuia_workflow_capture_text(self, params=None):
        self.write_capture_log(f"TEXT: {params[0]}")

    # Narration TTS actions
    def cuia_tts_stop(self, params=None):
        self.state_manager._tts.stop()

    def cuia_tts_toggle_enable(self, params=None):
        if zynthian_gui_config.tts_enabled:
            zynthian_gui_config.tts_enabled = False
            self.state_manager._tts.shutdown()
        else:
            zynthian_gui_config.tts_enabled = True
            self.state_manager._tts.start()
        zynconf.save_config({"ZYNTHIAN_TTS_ENABLED": str(zynthian_gui_config.tts_enabled)}, True)

    def cuia_tts_toggle_playback(self, params=None):
        if self.state_manager._tts.playing:
            self.state_manager._tts.stop()
        else:
            screen = self.screens[self.current_screen]
            try:
                screen.tts_info()
            except:
                self.state_manager.tts(f"View: {self.current_screen}", replace="True", interrupt=True)

    # Panic Actions

    def cuia_all_notes_off(self, params=None):
        self.state_manager.all_notes_off()
        sleep(0.1)
        self.state_manager.raw_all_notes_off()
        try:
            self.screens[self.current_screen].set_title("ALL NOTES OFF", None, None, 1)
        except:
            pass

    def cuia_all_sounds_off(self, params=None):
        self.state_manager.all_notes_off()
        self.state_manager.all_sounds_off()
        sleep(0.1)
        self.state_manager.raw_all_notes_off()
        zynautoconnect.reset_xruns()
        try:
            self.screens[self.current_screen].set_title("ALL SOUNDS OFF", None, None, 1)
        except:
            pass

    def cuia_clean_all(self, params=None):
        if params == ['CONFIRM']:
            self.clean_all()
            # TODO: Should send signal so that UI can react
            self.show_screen_reset("chain_manager")

    # Audio & MIDI Recording/Playback actions
    def cuia_start_audio_record(self, params=None):
        if self.current_processor.eng_code == "AP":
            self.state_manager.audio_recorder.start_recording(self.current_processor)
        else:
            self.state_manager.audio_recorder.start_recording()

    def cuia_stop_audio_record(self, params=None):
        self.state_manager.audio_recorder.stop_recording()

    def cuia_toggle_audio_record(self, params=None):
        if self.current_processor.eng_code == "AP":
            self.state_manager.audio_recorder.toggle_recording(self.current_processor)
        else:
            self.state_manager.audio_recorder.toggle_recording()

    def cuia_start_audio_play(self, params=None):
        self.state_manager.start_audio_player()

    def cuia_stop_audio_play(self, params=None):
        if self.current_screen == "pattern_editor":
            self.screens["pattern_editor"].stop_playback()
        else:
            self.state_manager.stop_audio_player(reset_pos=True)

    def cuia_toggle_audio_play(self, params=None):
        # TODO: This logic should not be here
        if self.current_screen == "pattern_editor":
            self.screens["pattern_editor"].toggle_playback()
        else:
            self.state_manager.toggle_audio_player()

    def cuia_audio_file_list(self, params=None):
        self.show_screen("audio_player")
        #return
        self.replace_screen('bank')
        n_banks = len(self.state_manager.audio_player.bank_list)
        if n_banks == 1 or self.state_manager.audio_player.bank_name:
            self.screens['bank'].click_listbox()
        elif n_banks == 0:
            self.close_screen()
            self.close_screen()

    def cuia_start_midi_record(self, params=None):
        self.state_manager.start_midi_record()

    def cuia_stop_midi_record(self, params=None):
        self.state_manager.stop_midi_record()
        if self.current_screen == "midi_recorder":
            self.screens['midi_recorder'].select()

    def cuia_toggle_midi_record(self, params=None):
        self.state_manager.toggle_midi_record()
        if self.current_screen == "midi_recorder":
            self.screens['midi_recorder'].select()

    def cuia_start_midi_play(self, params=None):
        self.state_manager.start_midi_playback()

    def cuia_stop_midi_play(self, params=None):
        self.state_manager.stop_midi_playback()

    def cuia_toggle_midi_play(self, params=None):
        self.state_manager.toggle_midi_playback()

    def cuia_toggle_record(self, params=None):
        if self.alt_mode:
            self.cuia_toggle_midi_record()
        else:
            self.cuia_toggle_audio_record()

    def cuia_stop(self, params=None):
        if self.alt_mode:
            self.cuia_stop_midi_play()
        else:
            self.cuia_stop_audio_play()

    def cuia_toggle_play(self, params=None):
        if self.alt_mode:
            self.cuia_toggle_midi_play()
        else:
            self.cuia_toggle_audio_play()

    def cuia_tempo(self, params=None):
        self.state_manager.zynseq.tap_tempo()
        if self.current_screen != "tempo":
            self.show_screen("tempo")

    def cuia_set_tempo(self, params=None):
        try:
            self.state_manager.zynseq.set_tempo(params[0])
        except (AttributeError, TypeError):
            pass

    def cuia_toggle_seq(self, params=None):
        try:
            self.state_manager.zynseq.libseq.togglePlayState(self.state_manager.zynseq.scene, int(params[0]), int(params[1]))
        except (AttributeError, TypeError):
            pass

    def cuia_tempo_up(self, params=None):
        if params:
            try:
                self.state_manager.zynseq.set_tempo(self.state_manager.zynseq.get_tempo() + params[0])
            except (AttributeError, TypeError):
                pass
        else:
            self.state_manager.zynseq.set_tempo(
                self.state_manager.zynseq.get_tempo() + 1)

    def cuia_tempo_down(self, params=None):
        if params:
            try:
                self.state_manager.zynseq.set_tempo(self.state_manager.zynseq.get_tempo() - params[0])
            except (AttributeError, TypeError):
                pass
        else:
            self.state_manager.zynseq.set_tempo(self.state_manager.zynseq.get_tempo() - 1)

    def cuia_tap_tempo(self, params=None):
        self.state_manager.zynseq.tap_tempo()

    def cuia_copy(self, params=None):
        pass

    def cuia_paste(self, params=None):
        pass

    # Zynpot & Zynswitch emulation CUIAs (low level)
    def cuia_zynpot(self, params=None):
        try:
            i = int(params[0])
            d = int(params[1])
            self.get_current_screen_obj().zynpot_cb(i, d)
            if self.capture_log:
                self.write_capture_log("ZYNPOT:{},{}".format(i, d))
        except IndexError:
            logging.error("zynpot requires 2 parameters: index, delta, not {params}")
            return
        except Exception as e:
            logging.error(e)

    def cuia_zynpot_abs(self, params=None):
        try:
            self.get_current_screen_obj().zynpot_abs(*params)
        except AttributeError:
            pass
        except Exception as e:
            logging.error(e)

    def cuia_zynswitch(self, params=None):
        try:
            i = params[0]
            d = params[1]
            self.cuia_queue.put_nowait(("zynswitch", (i, d)))
        except IndexError:
            logging.error("zynswitch requires 2 parameters: index, delta, not {params}")
            return
        except Exception as e:
            logging.error(e)

    # Basic UI-Control CUIAs
    # 4 x Arrows
    def cuia_arrow_up(self, params=None):
        try:
            self.get_current_screen_obj().arrow_up()
        except (AttributeError, TypeError):
            pass

    def cuia_arrow_down(self, params=None):
        try:
            self.get_current_screen_obj().arrow_down()
        except (AttributeError, TypeError):
            pass

    def cuia_arrow_right(self, params=None):
        try:
            self.get_current_screen_obj().arrow_right()
        except (AttributeError, TypeError):
            pass

    def cuia_arrow_left(self, params=None):
        try:
            self.get_current_screen_obj().arrow_left()
        except (AttributeError, TypeError):
            pass

    cuia_arrow_next = cuia_arrow_right
    cuia_arrow_prev = cuia_arrow_left

    # Back action
    def cuia_back(self, params=None):
        try:
            self.back_screen()
        except:
            pass

    # Select element in list => it receives an integer parameter!
    def cuia_select(self, params=None):
        try:
            self.get_current_screen_obj().select(params[0])
        except (AttributeError, TypeError):
            pass

    def cuia_mixer(self, params):
        """ Set mixer control

        params[0]: Index of mixer strip in display order (-1 for main mixbus)
        params[1]: parameter symbol
        params[2]: parameter value
        """
        try:
            if params[0] == -1:
                chain_id = 0
            else:
                chain_id = list(self.chain_manager.chains)[params[0]]
            chain = self.chain_manager.chains[chain_id]
            action = params[1]
            value = params[2]
            chain.zynmixer_proc.controllers_dict[action].set_value(value)
        except:
            logging.warning(f"Failed to set mixer - bad params? {params}")

    # -------------------------------------------------------------------
    # Screen management CUIAs
    # -------------------------------------------------------------------

    def cuia_toggle_screen(self, params=None):
        if params:
            self.toggle_screen(params[0])

    def cuia_show_screen(self, params=None):
        if params:
            self.show_screen_reset(params[0])

    def cuia_screen_admin(self, params=None):
        self.show_screen("admin")

    def cuia_screen_mixer(self, params=None):
        self.show_screen_reset("mixer")

    def cuia_screen_chain_manager(self, params=None):
        self.show_screen("chain_manager")

    def cuia_screen_audio_mixer(self, params=None):
        self.show_screen_reset("mixer")

    def cuia_screen_snapshot(self, params=None):
        self.show_screen("snapshot")

    def cuia_screen_zs3(self, params=None):
        self.screens["zs3"].enable_midi_learn()
        self.show_screen("zs3")

    def cuia_screen_midi_recorder(self, params=None):
        self.show_screen("midi_recorder")

    def cuia_screen_audio_player(self, params=None):
        self.show_screen("audio_player")

    def cuia_screen_alsa_mixer(self, params=None):
        self.show_screen("alsa_mixer")

    def cuia_screen_launcher(self, params=None):
        if self.current_screen == "mixer" and self.screens["mixer"].launcher_mode:
            self.show_screen("pattern_editor")
        else:
            self.show_screen_reset("launcher")

    def cuia_screen_zynpad(self, params=None):
        self.show_screen("launcher")

    def cuia_screen_pattern_editor(self, params=None):
        success = False
        if self.current_screen == "launcher":
            success = self.screens['launcher'].edit_clip()
        if not success:
            self.show_screen("pattern_editor")

    def cuia_screen_calibrate(self, params=None):
        self.calibrate_touchscreen()

    def cuia_screen_clean(self, params=None):
        self.state_manager.start_busy("clean_screen", "Clean screen")
        for i in range(10, 0, -1):
            self.state_manager.set_busy_details(f"Closing in {i}s")
            sleep(1)
        self.state_manager.end_busy("clean_screen")

    def cuia_refresh_screen(self, params=None):
        if params is None or self.current_screen in params:
            self.screens[self.current_screen].build_view()
            self.screen_lock.acquire()
            self.screens[self.current_screen].show()
            self.screen_lock.release()

    # -------------------------------------------------------------------
    # Menu, Chain Control & Options, Bank/Presets:
    # -------------------------------------------------------------------

    def cuia_show_navigation_grid(self, params):
        if params and len(params) >= 2:
            self.screens["grid_sel"].setup(params[0], params[1])
            self.show_screen("grid_sel")

    def cuia_main_menu(self, params=None):
        self.show_screen("main_menu")

    def cuia_chain_control(self, params=None):
        try:
            # Select chain by index
            index = int(params[0])
            if index == 0:
                chain_id = 0
            else:
                chain_id = self.chain_manager.get_chain_id_by_index(index - 1)
        except:
            chain_id = self.chain_manager.active_chain.chain_id
        self.chain_control(chain_id)

    cuia_layer_control = cuia_chain_control
    cuia_screen_control = cuia_chain_control

    def cuia_chain_options(self, params=None):
        if self.is_shown_alsa_mixer():
            return
        if self.is_shown_audio_player():
            self.cuia_bank_preset()
            self.cuia_menu()
            return
        try:
            # Select chain by ID
            chain_id = params[0]
            # Select chain by index
            if isinstance(chain_id, int):
                if params[0] == 0:
                    chain_id = 0
                else:
                    chain_id = self.chain_manager.get_chain_id_by_index(params[0] - 1)
        except:
            chain_id = self.chain_manager.active_chain.chain_id

        if chain_id is not None:
            self.screens['chain_options'].setup(chain_id)
            self.show_screen('chain_options')

    cuia_layer_options = cuia_chain_options

    def cuia_menu(self, params=None):
        show_menu_func = getattr(self.screens[self.current_screen], "show_menu", None)
        if callable(show_menu_func):
            show_menu_func()
            return
        self.show_screen("chain_manager")

    def cuia_bank_preset(self, params=None):
        if self.is_shown_alsa_mixer():
            return
        if params:
            try:
                self.current_processor = params
                self.chain_manager.get_active_chain().set_current_processor(self.current_processor)
            except:
                logging.error("Can't set processor passed as CUIA parameter!")
        elif not self.is_shown_audio_player():
            self.current_processor = self.chain_manager.get_active_chain().current_processor

        if self.current_screen == 'bank':
            if not self.screens['bank'].browse_back():
                self.close_screen()
        else:
            curproc = self.get_current_processor()
            if curproc:
                if self.current_screen == 'preset':
                    if not self.screens['preset'].browse_back():
                        bank_list = curproc.get_bank_list()
                        if len(bank_list) > 1:
                            self.replace_screen('bank')
                        else:
                            self.close_screen()
                else:
                    bank_list = curproc.get_bank_list()
                    if len(curproc.preset_list) > 0 and curproc.preset_list[0][0] != '':
                        self.screens['preset'].index = curproc.get_preset_index()
                        self.show_screen('preset', hmode=zynthian_gui.SCREEN_HMODE_ADD)
                        if len(curproc.preset_list) == 0 or curproc.preset_list[0][0] == '':
                            # Handle change of bank name, e.g. via webconf
                            self.replace_screen('bank')
                    elif len(bank_list) > 0 and bank_list[0][0] != '':
                        self.show_screen('bank', hmode=zynthian_gui.SCREEN_HMODE_ADD)
                    else:
                        self.show_screen('preset', hmode=zynthian_gui.SCREEN_HMODE_NONE)
                        self.screens['preset'].show_preset_options()

    cuia_preset = cuia_bank_preset

    def cuia_preset_fav(self, params=None):
        self.show_favorites()

    # -------------------------------------------------------------------
    # ZS3 management CUIAs:
    # -------------------------------------------------------------------

    def cuia_zs3_save(self, params=None):
        if len(params) >= 1:
            if isinstance(params[0], int):
                self.state_manager.save_zs3_by_index(params[0])
            else:
                self.state_manager.save_zs3(params[0])

    def cuia_zs3_load(self, params=None):
        if len(params) >= 1:
            if isinstance(params[0], int):
                self.state_manager.load_zs3_by_index(params[0])
            else:
                self.state_manager.load_zs3(params[0])

    def cuia_zs3_next(self, params=None):
        self.state_manager.load_next_zs3()

    def cuia_zs3_prev(self, params=None):
        self.state_manager.load_prev_zs3()

    # -------------------------------------------------------------------
    # MIDI Learn CUIAS:
    # -------------------------------------------------------------------

    def get_midi_learn_screen_obj(self):
        if self.current_screen == "chain_control" and self.screens["chain_control"].subscreen_name == "control":
            return self.screens["chain_control"].subscreen
        elif self.current_screen in ("alsa_mixer"):
            return self.screens[self.current_screen]

    def cuia_enable_midi_learn_cc(self, params=None):
        # TODO: Find zctrl
        if len(params) == 2:
            self.state_manager.enable_learn_cc(params[0], params[1])

    def cuia_disable_midi_learn_cc(self, params=None):
        self.state_manager.disable_learn_cc()

    def cuia_enable_midi_learn_pc(self, params=None):
        if params:
            self.state_manager.enable_learn_pc(params[0])
        else:
            self.state_manager.enable_learn_pc("")

    def cuia_disable_midi_learn_pc(self, params=None):
        self.state_manager.disable_learn_pc()

    def cuia_enable_midi_learn(self, params=None):
        self.state_manager.set_midi_learn(True)
        self.screens[self.current_screen].enter_midi_learn()

    def cuia_disable_midi_learn(self, params=None):
        self.state_manager.set_midi_learn(False)
        try:
            self.get_midi_learn_screen_obj().exit_midi_learn()
        except:
            pass

    def cuia_toggle_midi_learn(self, params=None):
        try:
            state = self.get_midi_learn_screen_obj().toggle_midi_learn()
            self.state_manager.set_midi_learn(state)
        except:
            if self.state_manager.midi_learn_state:
                self.cuia_disable_midi_learn(params)
            else:
                self.cuia_enable_midi_learn(params)

    def cuia_action_midi_unlearn(self, params=None):
        try:
            self.get_midi_learn_screen_obj().midi_unlearn_action()
        except (AttributeError, TypeError):
            pass

    # Learn control options
    def cuia_midi_learn_control_options(self, params=None):
        scrobj = self.get_midi_learn_screen_obj()
        if scrobj:
            scrobj.midi_learn_options(params[0])

    # Learn control
    def cuia_midi_learn_control(self, params=None):
        scrobj = self.get_midi_learn_screen_obj()
        if scrobj:
            scrobj.midi_learn(params[0])

    # Unlearn control
    def cuia_midi_unlearn_control(self, params=None):
        scrobj = self.get_midi_learn_screen_obj()
        if scrobj:
            if params:
                self.midi_learn_zctrl = scrobj.get_zcontroller(params[0])
            # if not parameter, unlearn selected learning control
            if self.midi_learn_zctrl:
                scrobj.midi_unlearn_action()

    # Unlearn all mixer controls
    def cuia_midi_unlearn_mixer(self, params=None):
        for chain in self.chain_manager.chains.values():
            if chain.zynmixer_proc:
                self.chain_manager.clean_midi_learn(chain.zynmixer_proc)

    def cuia_midi_unlearn_node(self, params=None):
        if params:
            self.chain_manager.remove_midi_learn([params[0], params[1]])

    def cuia_midi_unlearn_chain(self, params=None):
        if params:
            self.chain_manager.clean_midi_learn(params[0])
        else:
            self.chain_manager.clean_midi_learn(self.chain_manager.active_chain.chain_id)

    # -------------------------------------------------------------------
    # Z2 knob touch
    # -------------------------------------------------------------------
    def cuia_z2_zynpot_touch(self, params=None):
        if params:
            try:
                self.screens[self.current_screen].zctrl_touch(params[0])
            except AttributeError:
                pass
                # TODO: Should all screens be derived from base?

    # -------------------------------------------------------------------
    # V5 knob's switch action defaults
    # -------------------------------------------------------------------
    def cuia_v5_zynpot_switch(self, params):
        try:
            if self.get_current_screen_obj().cuia_v5_zynpot_switch(params):
                return True
        except:
            pass
        i = params[0]
        t = params[1].upper()
        if t == "L":
            if self.state_manager.zctrl_x and self.state_manager.zctrl_y:
                self.show_screen("control_xy")
        elif i == 3:
            if t == 'S':
                self.zynswitch_short(i)
            elif t == 'B':
                self.zynswitch_bold(i)

    # -------------------------------------------------------------------
    # MIDI CUIAs
    # -------------------------------------------------------------------

    def cuia_program_change(self, params=None):
        if len(params) > 0:
            if len(params) > 1:
                chan = int(params[1])
            else:
                try:
                    chan = int(self.chain_manager.get_active_chain().midi_chan)
                    if chan >= 16:
                        chan = 0
                except:
                    chan = 0
            if params[0] == "+":
                pgm = self.prog_change[chan] + 1
            elif params[0] == "-":
                pgm = self.prog_change[chan] - 1
            else:
                pgm = int(params[0])
            if 0 <= chan < 16 and 0 <= pgm < 128:
                lib_zyncore.write_zynmidi_program_change(chan, pgm)
                self.prog_change[chan] = pgm

    def cuia_zyn_cc(self, params=None):
        if len(params) > 2:
            chan = int(params[0])
            cc = int(params[1])
            if params[-1] == 'R':
                if len(params) > 3:
                    lib_zyncore.write_zynmidi_ccontrol_change(chan, cc, int(params[3]))
            else:
                lib_zyncore.write_zynmidi_ccontrol_change(chan, cc, int(params[2]))

    # -------------------------------------------------------------------
    # Common methods to control views derived from zynthian_gui_base
    # -------------------------------------------------------------------
    def cuia_show_cursor(self, params=None):
        try:
            zynthian_gui_config.top.config(cursor="arrow")
        except (AttributeError, TypeError):
            pass

    def cuia_hide_cursor(self, params=None):
        try:
            zynthian_gui_config.top.config(cursor="none")
        except (AttributeError, TypeError):
            pass

    def cuia_show_topbar(self, params=None):
        try:
            self.screens[self.current_screen].show_topbar(True)
        except (AttributeError, TypeError):
            pass

    def cuia_hide_topbar(self, params=None):
        try:
            self.screens[self.current_screen].show_topbar(False)
        except (AttributeError, TypeError):
            pass

    def cuia_show_sidebar(self, params=None):
        try:
            self.screens[self.current_screen].show_sidebar(True)
            zynsigman.send_queued(zynsigman.S_GUI, zynsigman.SS_GUI_SHOW_SIDEBAR, shown=True)
        except (AttributeError, TypeError):
            pass

    def cuia_hide_sidebar(self, params=None):
        try:
            self.screens[self.current_screen].show_sidebar(False)
            zynsigman.send_queued(zynsigman.S_GUI, zynsigman.SS_GUI_SHOW_SIDEBAR, shown=False)
        except (AttributeError, TypeError):
            pass

    def cuia_toggle_sidebar(self, params=None):
        try:
            show = not self.screens[self.current_screen].sidebar_shown
            self.screens[self.current_screen].show_sidebar(show)
            zynsigman.send_queued(zynsigman.S_GUI, zynsigman.SS_GUI_SHOW_SIDEBAR, shown=show)
        except (AttributeError, TypeError):
            pass

    # -------------------------------------------------------------------
    # Zynaptik config CUIAs (CV/gate, etc.)
    # -------------------------------------------------------------------

    def cuia_zynaptik_cvin_set_volts_octave(self, params):
        try:
            lib_zyncore.zynaptik_cvin_set_volts_octave(float(params[0]))
        except Exception as err:
            logging.debug(err)

    def cuia_zynaptik_cvin_set_note0(self, params):
        try:
            lib_zyncore.zynaptik_cvin_set_note0(int(params[0]))
        except Exception as err:
            logging.debug(err)

    def cuia_zynaptik_cvout_set_volts_octave(self, params):
        try:
            lib_zyncore.zynaptik_cvout_set_volts_octave(float(params[0]))
        except Exception as err:
            logging.debug(err)

    def cuia_zynaptik_cvout_set_note0(self, params):
        try:
            lib_zyncore.zynaptik_cvout_set_note0(int(params[0]))
        except Exception as err:
            logging.debug(err)

    # -------------------------------------------------------------------
    # CUIA backend API - TODO: Move to non-gui api
    # -------------------------------------------------------------------

    def cuia_api(self, params):
        """ Access the backend API
        params (tuple):
            api: Which api to access: "sm" for state manager, "cm" for chain manager
            method: Name of method to call
            params: comma separated list of method parameters
        """

        try:
            api, method, *params = params
            match api:
                case "sm":
                    fn = getattr(self.state_manager, method)
                case "cm":
                    fn = getattr(self.chain_manager, method)
                case _:
                    return
            fn(*params)
        except Exception as err:
             logging.debug(err)

    # -------------------------------------------------------------------
    # Zynswitch Event Management
    # -------------------------------------------------------------------

    def custom_switch_ui_action(self, i, t):
        action_config = zynthian_gui_config.custom_switch_ui_actions[i]
        if not action_config:
            return

        if t == "S" and self.check_current_screen_switch(action_config):
            cuia = action_config['B']
            if cuia:
                self.callable_ui_action_params(cuia)
                return

        if self.alt_mode:
            at = "A" + t
            if at in action_config:
                cuia = action_config[at]
                if cuia:
                    self.callable_ui_action_params(cuia)
                    return

        if t in action_config:
            cuia = action_config[t]
            if cuia:
                self.callable_ui_action_params(cuia)
                return True

    # Get the current workflow name by analyzing screen history
    def get_current_workflow(self):
        # [workflow base screen list, workflow allowed subscreens]
        workflows = {
            "menu": [["main_menu", "grid_sel"], []],
            "add_chain": [["add_chain"], ["engine", "midi_chan"]],
            "chain_manager": [["chain_manager"], ["chain_options", "midi_chan", "midi_cc", "midi_key_range", "midi_config", "processor_options", "audio_in", "audio_out"]],
            "admin": [["admin"], ["wifi", "bluetooth", "brightness_config", "touchscreen_calibration", "cv_config"]],
            "bank_preset": [["bank", "preset"], []],
            "chain_control": [["chain_control"], ["processor_options", "file_selector", "midi_cc_range", "midi_cc_single"]],
            "audio_player": [["audio_player"], ["midi_cc_range", "midi_cc_single"]],
            "alsa_mixer": [["alsa_mixer"], ["midi_cc_range", "midi_cc_single"]],
            "tempo": [["tempo"], ["midi_cc_range", "midi_cc_single"]],
            "pated": [["pattern_editor", "pated_cc"], ["midi_prog"]],
            "snapshot": [["snapshot"], []],
            "zs3": [["zs3"], []]
        }

        sh = self.screen_history + [self.current_screen]

        # Look for a wokflow base screen in the screen history, including current screen
        def get_wf():
            i = len(sh) - 1
            while i >= 0:
                for wf, wfcfg in workflows.items():
                    if sh[i] in wfcfg[0]:
                        return [i, wf, wfcfg]
                i -= 1
            return None

        # Confirm next screens in history are allowed screens for this workflow
        wf_info = get_wf()
        if wf_info:
            i, wf, wfcfg = wf_info
            subscreens = ["option", "confirm", "keyboard"] + wfcfg[1]
            i += 1
            while (i < len(sh)):
                if sh[i] not in subscreens:
                    return None
                i += 1

            return wf
        return None

    def check_current_screen_switch(self, action_config):
        # BIG ÑAPA!!
        if action_config['B'] and action_config['B'].lower() == 'bank_preset' and self.current_screen in ("bank", "preset", "audio_player"):
            return True
        # if self.is_current_workflow_menu():
        if action_config['S']:
            short_action = action_config['S'].lower()
            if short_action.endswith(self.current_screen):
                return True
            if short_action == "menu" and self.current_screen in ("main_menu", "chain_manager"):
                return True
        return False

    def toggle_pated(self):
        if self.current_screen == "pated_cc":
            pated_screen = "pattern_editor"
        elif self.current_screen == "pattern_editor":
            pated_screen = "pated_cc"
        else:
            return
        cur_pated = self.get_current_screen_obj()
        pated = self.screens[pated_screen]

        pated.refresh_sequence_info()
        pated.load_pattern(cur_pated.pattern)

        #pated_obj.bank = cur_pated_obj.bank
        #pated_obj.sequence = cur_pated_obj.sequence
        #pated_obj.load_pattern(cur_pated_obj.pattern)
        #pated_obj.channel = cur_pated_obj.channel

        logging.debug(f"Opening {pated_screen}...")
        self.show_screen(pated_screen, self.SCREEN_HMODE_REPLACE)

    # -------------------------------------------------------------------
    # Switches
    # -------------------------------------------------------------------

    # Init Standard Zynswitches
    def zynswitches_init(self):
        logging.info(f"INIT {zynthian_gui_config.num_zynswitches} ZYNSWITCHES ...")
        self.dtsw = [datetime.now()] * zynthian_gui_config.num_zynswitches

    # Initialize custom switches, analog I/O, TOF sensors, etc.
    def zynswitches_midi_setup(self, current_chan=None):
        if current_chan is None:
            curproc = self.get_current_processor()
            if curproc:
                current_chan = curproc.midi_chan
        self.wiring_midi_setup(current_chan)

    def get_zynswitch_pr_state(self, i):
        if zynthian_gui_config.num_zynpots == 0:
            return 0
        try:
            zpi = zynthian_gui_config.zynpot2switch.index(i)
            return self.zynpot_pr_state[zpi]
        except:
            return 0

    def zynswitch_disable_autolong(self):
        self.zynswitch_autolong_disabled = True

    def zynswitch_enable_autolong(self):
        self.zynswitch_autolong_disabled = False

    def zynswitches(self):
        """Process physical switch triggers"""

        i = 0
        while i <= zynthian_gui_config.last_zynswitch_index:
            try:
                if i >= 4 and not zynthian_gui_config.custom_switch_ui_actions[i - 4]:
                    i += 1
                    continue
            except:
                i += 1
                continue
            # Increase the long push time limit when auto-long push is disabled or push-rotating
            if self.zynswitch_autolong_disabled or self.get_zynswitch_pr_state(i) > 1:
                zs_long_us = 20 * 1000000
            else:
                zs_long_us = zynthian_gui_config.zynswitch_long_us
            # dtus is 0 if switched pressed, dur of last press or -1 if already processed
            dtus = lib_zyncore.get_zynswitch(i, zs_long_us)
            if dtus >= 0:
                #logging.debug(f"ZYNSWITCH {i}: DTUS={dtus}, AUTOLONG-PUSH TIME LIMIT => {zs_long_us}")
                self.cuia_queue.put_nowait(("zynswitch", (i, self.zynswitch_timing(dtus))))
            i += 1

    def zynswitch_timing(self, dtus):
        """Get action based on switch held time

        dtus : Duration switch has been pressed
        Return : Letter indicating the action to take
        # TODO: Does not support Release which means that press and hold expires when Long press is reached
        """
        if dtus == 0:
            return "P"
        elif dtus > zynthian_gui_config.zynswitch_long_us:
            return "L"
        elif dtus > zynthian_gui_config.zynswitch_bold_us:
            return "B"
        elif dtus > 0:
            return "S"

    def zynswitch_push(self, i):
        self.state_manager.set_event_flag()

        if callable(getattr(self.screens[self.current_screen], "switch", None)):
            if self.screens[self.current_screen].switch(i, 'P'):
                return True

        # Standard 4 ZynSwitches
        if 0 <= i <= 3:
            pass
        # Custom ZynSwitches
        elif i >= 4:
            # logging.debug('Push Switch ' + str(i))
            return self.custom_switch_ui_action(i - 4, "P")

    def zynswitch_long(self, i):
        logging.debug('Looooooooong Switch '+str(i))

        if callable(getattr(self.screens[self.current_screen], "switch", None)):
            if self.screens[self.current_screen].switch(i, 'L'):
                return True

        # Standard 4 ZynSwitches
        if i == 0:
            self.cuia_help()
            return True

        elif i == 1:
            self.cuia_power()
            return True

        elif i == 2:
            self.cuia_screen_snapshot()
            return True

        elif i == 3:
            self.cuia_all_sounds_off()
            return True

        # Custom ZynSwitches
        elif i >= 4:
            return self.custom_switch_ui_action(i-4, "L")

    def zynswitch_bold(self, i):
        logging.debug('Bold Switch '+str(i))

        if callable(getattr(self.screens[self.current_screen], "switch", None)):
            if self.screens[self.current_screen].switch(i, 'B'):
                return True

        # Default actions for the 4 standard ZynSwitches
        if i == 0:
            self.show_screen('chain_manager')
            return True

        elif i == 1:
            try:
                self.screens[self.current_screen].disable_param_editor()
            except:
                pass
            self.show_screen_reset('root')
            return True

        elif i == 2:
            if self.current_screen == 'zs3':
                self.cuia_screen_snapshot()
            else:
                self.cuia_screen_zs3()
            return True

        elif i == 3:
            self.screens[self.current_screen].switch_select('B')
            return True

        # Custom ZynSwitches
        elif i >= 4:
            return self.custom_switch_ui_action(i - 4, "B")

    def zynswitch_short(self, i):
        logging.debug('Short Switch ' + str(i))

        if callable(getattr(self.screens[self.current_screen], "switch", None)):
            if self.screens[self.current_screen].switch(i, 'S'):
                return True

        # Default actions for the standard 4 ZynSwitches
        if i == 0:
            # self.cuia_menu()
            return True

        elif i == 1:
            self.back_screen()
            return True

        elif i == 2:
            self.cuia_toggle_midi_learn()
            return True

        elif i == 3:
            self.screens[self.current_screen].switch_select('S')
            return True

        # Custom ZynSwitches
        elif i >= 4:
            return self.custom_switch_ui_action(i - 4, "S")

    # ------------------------------------------------------------------
    # Defered Switch Events
    # ------------------------------------------------------------------

    def zynswitch_defered(self, t, i):
        self.cuia_queue.put_nowait(("zynswitch", (i, t)))

    # ------------------------------------------------------------------
    # Read Physical Zynswitches
    # ------------------------------------------------------------------

    def zynswitch_read(self):
        # TODO: Block control when busy but avoid ui lock-up
        # if self.state_manager.is_busy():
        # return

        # Read Zynswitches
        try:
            self.zynswitches()
        except Exception as err:
            # logging.exception(err)
            logging.exception(traceback.format_exc())

    # ------------------------------------------------------------------
    # Signal processing
    # ------------------------------------------------------------------

    def register_signals(self):
        zynsigman.register(zynsigman.S_MIDI, zynsigman.SS_MIDI_NOTE_ON, self.cb_midi_note_on)
        zynsigman.register(zynsigman.S_MIDI, zynsigman.SS_MIDI_NOTE_OFF, self.cb_midi_note_off)
        zynsigman.register_queued(zynsigman.S_GUI, zynsigman.SS_GUI_SHOW_FILE_SELECTOR, self.cb_show_file_selector)
        zynsigman.register_queued(zynsigman.S_GUI, zynsigman.SS_GUI_SHOW_MESSAGE, self.cb_show_message)
        zynsigman.register_queued(zynsigman.S_CHAIN_MAN, self.chain_manager.SS_SET_ACTIVE_CHAIN, self.cb_set_active_chain)

    def unregister_signals(self):
        zynsigman.unregister(zynsigman.S_MIDI, zynsigman.SS_MIDI_NOTE_ON, self.cb_midi_note_on)
        zynsigman.unregister(zynsigman.S_MIDI, zynsigman.SS_MIDI_NOTE_OFF, self.cb_midi_note_off)
        zynsigman.unregister(zynsigman.S_GUI, zynsigman.SS_GUI_SHOW_FILE_SELECTOR, self.cb_show_file_selector)
        zynsigman.unregister(zynsigman.S_GUI, zynsigman.SS_GUI_SHOW_MESSAGE, self.cb_show_message)
        zynsigman.unregister(zynsigman.S_CHAIN_MAN, self.chain_manager.SS_SET_ACTIVE_CHAIN, self.cb_set_active_chain)

    def cb_midi_note_on(self, izmip, chan, note, vel):
        """Handle MIDI_NOTE_ON signal

        izmip : MIDI input device index
        chan : MIDI channel
        note : Note number
        vel : Velocity value
        """

        # Pattern recording
        if self.current_screen == 'pattern_editor':
            self.screens['pattern_editor'].midi_note_on(note)
        # Preload preset (note-on)
        # => Now using delayed pre-load (see zynthian_gui_preset.py)
        #elif self.current_screen == 'preset':
        #    if zynthian_gui_config.preset_preload_noteon:
        #        curproc = self.get_current_processor()
        #        if curproc and (zynautoconnect.get_midi_in_dev_mode(izmip) or chan == curproc.midi_chan):
        #            self.screens['preset'].preselect_action()
        # Note Range Learn
        elif self.current_screen == 'midi_key_range':
            if self.state_manager.midi_learn_state:
                self.screens['midi_key_range'].learn_note_range(note)
        # Channel activity
        elif self.current_screen == 'midi_chan':
            self.screens['midi_chan'].midi_chan_activity(chan)

    def cb_midi_note_off(self, izmip, chan, note, vel):
        """Handle MIDI_NOTE_OFF signal

        izmip : MIDI input device index
        chan : MIDI channel
        note : Note number
        vel : Velocity value
        """

        # Pattern recording
        if self.current_screen == 'pattern_editor':
            self.screens['pattern_editor'].midi_note_off(note)

    def cb_show_file_selector(self, cb_func, fexts=None, dirnames=None, path=None, preload=False):
        self.screens["file_selector"].config(cb_func, fexts=fexts, dirnames=dirnames, path=path, preload=preload)
        self.show_screen("file_selector")

    def cb_set_active_chain(self, active_chain_id):
        active_chain = self.chain_manager.get_active_chain()
        if active_chain:
            self.zynswitches_midi_setup(active_chain.midi_chan)

    def cb_show_message(self, message):
        try:
            self.get_current_screen_obj().set_title(message, None, None, 1)
        except Exception as e:
            logging.error(f"Can't show GUI message => {e}")

    # ------------------------------------------------------------------
    # Zynpot Thread
    # ------------------------------------------------------------------

    def start_zynpot_thread(self):
        self.zynpot_thread = Thread(target=self.zynpot_thread_task, args=())
        self.zynpot_thread.name = "zynpot"
        self.zynpot_thread.daemon = True  # thread dies with the program
        self.zynpot_thread.start()

    def zynpot_thread_task(self):
        while not self.exit_flag:
            self.zynpot_event.wait()
            self.zynpot_event.clear()
            for i in range(0, zynthian_gui_config.num_zynpots):
                if self.zynpot_dval[i] != 0:
                    try:
                        self.zynpot_lock.acquire()
                        dval = self.zynpot_dval[i]
                        self.zynpot_dval[i] = 0
                        self.zynpot_lock.release()
                        self.screens[self.current_screen].zynpot_cb(i, dval)
                        self.state_manager.set_event_flag()
                        if self.capture_log:
                            self.write_capture_log("ZYNPOT:{},{}".format(i, dval))
                    except Exception as err:
                        pass  # Some screens don't use controllers
                        logging.exception(err)

    # ------------------------------------------------------------------
    # Control Thread
    # ------------------------------------------------------------------

    def start_control_thread(self):
        self.control_thread = Thread(target=self.control_thread_task, args=())
        self.control_thread.name = "Control"
        self.control_thread.daemon = True  # thread dies with the program
        self.control_thread.start()

    def control_thread_task(self):
        j = 0
        while not self.exit_flag:
            # Read zynswitches & OSC events
            self.zynswitch_read()
            self.osc_receive()

            # Every 4 cycles...
            if j > 4:
                j = 0
                # Refresh GUI Controllers
                try:
                    self.screens[self.current_screen].plot_zctrls()
                except AttributeError:
                    pass
                except Exception as e:
                    logging.error(e)

                # Power Save Check
                self.state_manager.power_save_check()
            else:
                j += 1

            # Wait a little bit...
            sleep(0.01)

        # End Thread task
        self.osc_end()

    def cb_touch(self, event):
        # logging.debug("CB EVENT TOUCH!!!")
        if self.capture_log:
            self.touch += 1
            self.write_capture_log(f"TOUCH:{event.x},{event.y}")
        if self.state_manager.power_save_mode:
            self.state_manager.set_event_flag()
            self.ignore_next_touch_release = True
            return "break"
        self.state_manager.set_event_flag()
        if self.multitouch.detect:
            self.multitouch.open_device()
            return "break"

    def cb_touch_release(self, event):
        # logging.debug("CB EVENT TOUCH RELEASE!!!")
        if self.capture_log and self.touch:
            self.touch -= 1
            self.write_capture_log(f"RELEASE:{event.x},{event.y}")
        self.state_manager.set_event_flag()
        if self.ignore_next_touch_release:
            # logging.debug("IGNORING EVENT TOUCH RELEASE!!!")
            self.ignore_next_touch_release = False
            return "break"

    # ------------------------------------------------------------------
    # "Busy" Animated Icon Thread
    # ------------------------------------------------------------------

    def start_busy_thread(self):
        self.busy_thread = Thread(target=self.busy_thread_task, args=())
        self.busy_thread.name = "Busy"
        self.busy_thread.daemon = True  # thread dies with the program
        self.busy_thread.start()
        # logging.debug(f"START BUSY {self.busy_thread}")

    def busy_thread_task(self):
        busy_timeout = 0
        busy_warn_time = 300
        while not self.exit_flag:
            if self.state_manager.is_busy():
                busy_timeout += 1
                busy_message = self.state_manager.get_busy_message()
                busy_details = self.state_manager.get_busy_details()
                # Show loading screen if busy and busy message
                if self.current_screen != "loading":
                    if busy_message:
                        self.show_loading(busy_message, busy_details)
                else:
                    busy_error = self.state_manager.get_busy_error()
                    if busy_error:
                        self.screens['loading'].set_error(busy_error)
                    else:
                        busy_warning = self.state_manager.get_busy_warning()
                        if busy_warning:
                            self.screens['loading'].set_warning(busy_warning)
                        else:
                            busy_success = self.state_manager.get_busy_success()
                            if busy_success:
                                self.screens['loading'].set_success(busy_success)
                            elif busy_message:
                                self.screens['loading'].set_title(busy_message)
                    if busy_details:
                        self.screens['loading'].set_details(busy_details)
            else:
                busy_timeout = 0
                if self.current_screen == "loading":
                    self.close_screen("loading")

            try:
                if self.current_screen:
                    self.screens[self.current_screen].refresh_loading()
            except Exception as err:
                logging.error(f"refresh_loading() on screen '{self.current_screen}' => {err}")

            if busy_timeout == busy_warn_time:
                logging.warning(f"Clients have been busy for longer than {int(busy_warn_time / 10)}s: {self.state_manager.busy}")

            sleep(0.1)

    # ------------------------------------------------------------------
    # Status Refresh Thread
    # ------------------------------------------------------------------

    def start_status_thread(self):
        self.status_thread = Thread(target=self.status_thread_task, args=())
        self.status_thread.name = "Status"
        self.status_thread.daemon = True  # thread dies with the program
        self.status_thread.start()

    def status_thread_task(self):
        while not self.exit_flag:
            # When in power save mode:
            # + Make LED refresh faster so the fading effect looks smooth
            # + Don't need to refresh status info because it's not shown
            if self.state_manager.power_save_mode:
                if self.wsleds:
                    self.wsleds.update()
                sleep(0.05)
            else:
                self.refresh_status()
                if self.wsleds:
                    self.wsleds.update()
                sleep(0.2)

    def refresh_status(self):
        # Refresh on-screen status
        try:
            self.screens[self.current_screen].refresh_status()
        except AttributeError:
            pass
        except Exception as e:
            logging.exception(traceback.format_exc())

    # ------------------------------------------------------------------
    # CUIA Thread
    # ------------------------------------------------------------------

    def start_cuia_thread(self):
        self.cuia_thread = Thread(target=self.cuia_thread_task, args=())
        self.cuia_thread.name = "CUIA"
        self.cuia_thread.daemon = True  # thread dies with the program
        self.cuia_thread.start()

    def cuia_thread_task(self):
        """Thread task to handle CUIA events

        Events are passed via cuia_queue and may be a space separated list:'cuia, param, param...' or list: [cuia, [params]]
        """

        zynswitch_cuia_ts = [None] * zynthian_gui_config.num_zynswitches
        zynswitch_repeat = {}
        zynpot_repeat = {}
        repeat_delay = 3  # Quantity of repeat intervals to delay before triggering auto repeat
        repeat_interval = 0.15  # Auto repeat interval in seconds

        while not self.exit_flag:
            cuia = "unknown"
            try:
                # Check for long press before release
                if not self.zynswitch_autolong_disabled:
                    long_ts = monotonic() - zynthian_gui_config.zynswitch_long_seconds
                    for i, ts in enumerate(zynswitch_cuia_ts):
                        if ts is not None and ts < long_ts:
                            zynswitch_cuia_ts[i] = None
                            try:
                                zpi = zynthian_gui_config.zynpot2switch.index(i)
                                zp_pr_state = self.zynpot_pr_state[zpi]
                            except:
                                zp_pr_state = 0
                            if zp_pr_state <= 1:
                                self.zynswitch_long(i)
                                # Capture log: ZYNSWITCH LONG (autolong)
                                if self.capture_log:
                                    self.write_capture_log(f"ZYNSWITCH:L,{i}")
                # Process events from queue
                event = self.cuia_queue.get(True, repeat_interval)
                params = None
                if isinstance(event, str):
                    if event == "__EXIT__":
                        break
                    # space seperated cuia param,param...
                    parts = event.split(" ", 2)
                    cuia = parts[0].lower()
                    if len(parts) > 1:
                        params = parts[1].split(",")
                else:
                    # list [cuia, [params]]
                    cuia = event[0].lower()
                    if len(event) > 1:
                        params = event[1]

                if cuia == "zynswitch":
                    # zynswitch has parameters: [switch, action] where action is P(ressed), R(eleased), S(hort), B(old), L(ong), X or Y
                    i = int(params[0])
                    t = params[1]
                    if t == 'R':
                        if zynswitch_cuia_ts[i] is None:
                            if i in zynswitch_repeat:
                                del zynswitch_repeat[i]
                            continue
                        else:
                            dtus = int(1000000 * (monotonic() - zynswitch_cuia_ts[i]))
                            zynswitch_cuia_ts[i] = None
                            t = self.zynswitch_timing(dtus)
                    if t == 'P':
                        pr = 0
                        if zynthian_gui_config.num_zynpots > 0:
                            try:
                                zynswitch_cuia_ts[i] = monotonic()
                                zpi = zynthian_gui_config.zynpot2switch.index(i)
                                self.zynpot_pr_state[zpi] = 1
                                pr = 1
                            except:
                                pass
                        if not pr:
                            if self.zynswitch_push(i):
                                zynswitch_repeat[i] = repeat_delay
                            else:
                                zynswitch_cuia_ts[i] = monotonic()
                    else:
                        if zynthian_gui_config.num_zynpots > 0:
                            try:
                                zpi = zynthian_gui_config.zynpot2switch.index(i)
                                if self.zynpot_pr_state[zpi] > 1:
                                    t = 'PR'
                                self.zynpot_pr_state[zpi] = 0
                            except:
                                pass
                        if t == 'S':
                            zynswitch_cuia_ts[i] = None
                            self.zynswitch_short(i)
                        elif t == 'B':
                            zynswitch_cuia_ts[i] = None
                            self.zynswitch_bold(i)
                        elif t == 'L':
                            zynswitch_cuia_ts[i] = None
                            self.zynswitch_long(i)
                        elif t == 'PR':
                            zynswitch_cuia_ts[i] = None
                        else:
                            zynswitch_cuia_ts[i] = None
                            logging.warning("Unknown Action Type: {}".format(t))
                        if i in zynswitch_repeat:
                            del zynswitch_repeat[i]

                    # Capture log: ZYNSWITCH
                    if self.capture_log:
                        self.write_capture_log(f"ZYNSWITCH:{t},{i}")

                elif cuia == "zynpot":
                    # zynpot has parameters: [pot, delta, 'P'|'R']. 'P'&'R' are only used for keybinding to zynpot
                    if len(params) > 2:
                        i = int(params[0])
                        if params[2] == 'R' and i in zynpot_repeat:
                            del zynpot_repeat[i]
                        elif params[2] == 'P':
                            self.cuia_zynpot(params[:2])
                            zynpot_repeat[i] = [repeat_delay, params]
                    else:
                        self.cuia_zynpot(params)

                else:
                    result = self.callable_ui_action(cuia, params)
                    if len(event) > 2:
                        osc_src = event[2]
                        try:
                            osc_src = ("localhost", 1371)
                            liblo.send(osc_src, "/cuia_response", result)
                        except:
                            pass

                if cuia != "power_save":
                    self.state_manager.set_event_flag()

            except Empty:
                for i in zynswitch_repeat:
                    if zynswitch_repeat[i]:
                        zynswitch_repeat[i] -= 1
                    else:
                        self.zynswitch_push(i)
                for i in zynpot_repeat:
                    if zynpot_repeat[i][0]:
                        zynpot_repeat[i][0] -= 1
                    else:
                        self.cuia_zynpot(zynpot_repeat[i][1])

            except Exception as e:
                logging.error(f"CUIA '{cuia}' failed with params: {params}\n{traceback.format_exc()}")
                self.state_manager.set_busy_error(f"ERROR CUIA {cuia}: {params}", e)
                sleep(3)
                self.state_manager.clear_busy()

    # ------------------------------------------------------------------
    # Thread ending on Exit
    # ------------------------------------------------------------------

    def exit(self, code=0):
        self.exit_code = code
        zynthian_gui_config.top.after(1, self.do_exit)

    def do_exit(self):
        # Log exit message
        logging.info("STOPPING ZYNTHIAN-UI...")

        self.exit_flag = True
        self.exit_wait_count = 0

        # End signal manager queue processing
        zynsigman.stop()

        # Signal zynpot thread so it can unlock and finish normally
        self.zynpot_event.set()

        # Light-off LEDs
        if self.wsleds:
            self.wsleds.end()

        # Stop Multitouch driver
        self.multitouch.stop()

        # Stop State manager
        self.state_manager.stop()

        # Signal cuia thread so it can unlock and finish normally
        self.cuia_queue.put_nowait("__EXIT__")

        # Ends UI
        self.stop()

    def stop(self):
        # Get threads still running
        running_thread_names = []
        for t in [self.control_thread, self.status_thread, self.busy_thread, self.cuia_thread, self.state_manager.slow_thread, self.state_manager.fast_thread, self.multitouch.thread, self.zynpot_thread]:
            if t and t.is_alive():
                running_thread_names.append(t.name)
        if zynautoconnect.is_running():
            running_thread_names.append("Autoconnect")

        # Clean End
        if not running_thread_names:
            self.exit_wait_count = -1
            logging.info(f"All threads finished normally")
            zynthian_gui_config.top.quit()
        # End with running threads
        elif self.exit_wait_count > 10:
            for i in running_thread_names:
                logging.error(f"{i} thread failed to terminate")
            zynthian_gui_config.top.quit()
        # Still waiting threads to end ...
        else:
            self.exit_wait_count += 1
            zynthian_gui_config.top.after(160, self.stop)

    # ------------------------------------------------------------------
    # Polling
    # ------------------------------------------------------------------

    def start_polling(self):
        self.osc_timeout()

    def after(self, msec, func):
        zynthian_gui_config.top.after(msec, func)

    def osc_timeout(self):
        if not self.exit_flag:
            self.watchdog_last_check = monotonic()
            for client in list(self.osc_clients):
                if self.osc_clients[client] < self.watchdog_last_check - self.osc_heartbeat_timeout:
                    self.osc_clients.pop(client)
                    try:
                        self.state_manager.zynmixer_chan.remove_osc_client(client)
                        self.state_manager.zynmixer_bus.remove_osc_client(client)
                    except:
                        pass

            if not self.osc_clients and self.current_screen not in ("root", "mixer", "launcher"):
                self.state_manager.zynmixer_chan.enable_dpm(False)
                self.state_manager.zynmixer_bus.enable_dpm(False)

            # Poll
            zynthian_gui_config.top.after(self.osc_heartbeat_timeout * 1000, self.osc_timeout)

    # ------------------------------------------------------------------
    # Zynthian Config Info
    # ------------------------------------------------------------------

    # This should be removed!!
    def get_zynthian_config(self, varname):
        return eval("zynthian_gui_config.{}".format(varname))

# ------------------------------------------------------------------------------
