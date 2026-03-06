#!/usr/bin/python3
# -*- coding: utf-8 -*-
# ******************************************************************************
# ZYNTHIAN PROJECT: Zynthian GUI
#
# Main Class for Zynthian JFK GUI
#
# Copyright (C) 2015-2025 Fernando Moyano <jofemodo@zynthian.org>
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
import logging
import traceback
from time import sleep
from queue import Empty
from time import monotonic
from datetime import datetime
from threading import Thread, Lock, Event

# Zynthian specific modules
import zynconf
import zynautoconnect

from zyncoder.zyncore import lib_zyncore
from zynlibs.zynseq import *

from zyngine import zynthian_state_manager
from zyngine.zynthian_signal_manager import zynsigman

from zyngui import zynthian_gui_config
from zyngui.zynthian_gui_info import zynthian_gui_info
from zyngui.zynthian_gui_help import zynthian_gui_help
from zyngui.zynthian_gui_splash import zynthian_gui_splash
from zyngui.zynthian_gui_loading import zynthian_gui_loading
from zyngui.zynthian_gui_confirm import zynthian_gui_confirm

# TODO This constants should go somewhere else
MIXER_MAIN_CHANNEL = 17
ZMOP_MOD_INDEX = 16   # Dedicated zmop for MOD-UI

# -------------------------------------------------------------------------------
# Zynthian Main GUI Class
# -------------------------------------------------------------------------------


class zynthian_gui:
    # Subsignals are defined inside each module. Here we define GUI subsignals:
    SS_GUI_SHOW_SCREEN = 0

    # Screen Modes
    SCREEN_HMODE_NONE = 0
    SCREEN_HMODE_ADD = 1
    SCREEN_HMODE_REPLACE = 2
    SCREEN_HMODE_RESET = 3

    def __init__(self):
        self.capture_dir_sdc = os.environ.get('ZYNTHIAN_MY_DATA_DIR', "/zynthian/zynthian-my-data") + "/capture"
        self.ex_data_dir = os.environ.get('ZYNTHIAN_EX_DATA_DIR', "/media/root")

        self.state_manager = zynthian_state_manager.zynthian_state_manager()
        self.chain_manager = self.state_manager.chain_manager

        self.screens = {}
        self.screen_history = []
        self.current_screen = None
        self.screen_timer_id = None

        self.current_processor = None

        # Lock object to avoid concurrence problems when showing/closing screens
        self.screen_lock = Lock()

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

        # Init LEDs
        self.wsleds = None
        self.init_wsleds()

    # ---------------------------------------------------------------------------
    # WSLeds Init
    # ---------------------------------------------------------------------------

    def init_wsleds(self):
        #from zyngui.zynthian_wsleds_jfk import zynthian_wsleds_jfk
        #self.wsleds = zynthian_wsleds_jfk(self)
        #self.wsleds.start()
        pass

    # ---------------------------------------------------------------------------
    # Wiring Layout Init & Config
    # ---------------------------------------------------------------------------

    def reload_wiring_layout(self):
        try:
            zynconf.load_config()
            zynthian_gui_config.config_custom_switches()
        except Exception as e:
            logging.error("ERROR configuring wiring: {}".format(e))

    # ---------------------------------------------------------------------------
    # GUI Core Management
    # ---------------------------------------------------------------------------

    def create_screens(self):
        # Create Core UI Screens
        self.screens['info'] = zynthian_gui_info()
        self.screens['help'] = zynthian_gui_help()
        self.screens['splash'] = zynthian_gui_splash()
        self.screens['loading'] = zynthian_gui_loading()
        self.screens['confirm'] = zynthian_gui_confirm()

        # Root screen
        self.screens['root'] = self.screens['loading']

        # Initialize switches
        try:
            self.zynswitches_init()
        except Exception as e:
            logging.error(f"ERROR initializing Switches: {e}")

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
        #self.screens['admin'].exit_to_console()

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
        init_screen = "main_menu"
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

        for screen_obj in self.screens.values():
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
                screen = self.current_screen
            else:
                screen = "root"

        if screen == "root":
            screen = "audio_mixer"
        else:
            self.current_processor = self.get_current_processor()

        if not self.screens[screen].build_view():
            self.screen_lock.release()
            # self.show_screen_reset("audio_mixer")
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
            #logging.debug(f"SHOW_SCREEN {screen}")
            self.screens[screen].show()
            self.current_screen = screen
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

    def close_screen(self, screen=None):
        """ Closes the current screen or optionally the specified screen """

        if screen is None:
            screen = self.current_screen
        self.prune_screen_history(screen, soft=False)
        try:
            last_screen = self.screen_history.pop()
        except:
            last_screen = "root"

        if last_screen not in self.screens:
            logging.error(f"Can't back to screen '{last_screen}'. It doesn't exist!")
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
        self.screen_lock.acquire()
        self.screens['loading'].set_title(title)
        self.screens['loading'].set_details(details)
        self.screens['loading'].show()
        self.current_screen = 'loading'
        self.hide_screens(exclude='loading')
        self.screen_lock.release()

    def show_loading_error(self, title="", details=""):
        self.screen_lock.acquire()
        self.screens['loading'].set_error(title)
        self.screens['loading'].set_details(details)
        self.screens['loading'].show()
        self.current_screen = 'loading'
        self.hide_screens(exclude='loading')
        self.screen_lock.release()

    def show_loading_warning(self, title="", details=""):
        self.screen_lock.acquire()
        self.screens['loading'].set_warning(title)
        self.screens['loading'].set_details(details)
        self.screens['loading'].show()
        self.current_screen = 'loading'
        self.hide_screens(exclude='loading')
        self.screen_lock.release()

    def show_loading_success(self, title="", details=""):
        self.screen_lock.acquire()
        self.screens['loading'].set_warning(title)
        self.screens['loading'].set_details(details)
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

    def show_help(self, topic=None):
        if not topic:
            topic = self.current_screen
        if self.screens['help'].load_file(f"./help/{topic}.html"):
            pass
            #self.show_screen("help")
        elif topic != "help":
            logging.warning(f"No help for '{topic}'")

    def get_current_processor(self):
        """Get the currently selected processor object"""
        if self.current_processor:
            return self.current_processor
        try:
            return self.chain_manager.get_active_chain().current_processor
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

    def clean_all(self):
        if self.chain_manager.get_chain_count() > 1:
            self.state_manager.save_last_state_snapshot()
        self.state_manager.clean_all()
        self.show_screen_reset('main_menu')

    def clean_chains(self):
        if self.chain_manager.get_chain_count() > 1:
            self.state_manager.save_last_state_snapshot()
        self.state_manager.clean_chains()
        self.show_screen_reset('main_menu')

    # -------------------------------------------------------------------
    # Callable UI Actions
    # -------------------------------------------------------------------

    @classmethod
    def get_cuia_list(cls):
        return [method[5:].upper() for method in dir(cls) if method.startswith('cuia_') is True]

    def callable_ui_action(self, cuia, params=None):
        logging.debug("CUIA '{}' => {}".format(cuia, params))
        cuia_func_name = "cuia_" + cuia.lower()
        # First try screen defined cuia function
        done = False
        cuia_func = getattr(self.get_current_screen_obj(), cuia_func_name, None)
        if callable(cuia_func):
            if cuia_func(params):
                done = True
        if not done:
            # else, call global function
            cuia_func = getattr(self, cuia_func_name, None)
            if callable(cuia_func):
                cuia_func(params)
            else:
                logging.error("Unknown CUIA '{}'".format(cuia))

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

    def cuia_help(self, params=None):
        self.show_help(params)

    def cuia_power_off(self, params=None):
        if params == ['CONFIRM']:
            self.screens['admin'].power_off_confirmed()
        else:
            self.screens['admin'].power_off()

    def cuia_reboot(self, params=None):
        if params == ['CONFIRM']:
            self.screens['admin'].reboot_confirmed()
        else:
            self.screens['admin'].reboot()

    def cuia_restart_ui(self, params=None):
        self.screens['admin'].restart_gui()

    def cuia_exit_ui(self, params=None):
        self.screens['admin'].exit_to_console()

    def cuia_reload_wiring_layout(self, params=None):
        self.reload_wiring_layout()

    def cuia_last_state_action(self, params=None):
        self.screens['admin'].last_state_action()

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
        try:
            self.screens[self.current_screen].set_title("ALL SOUNDS OFF", None, None, 1)
        except:
            pass

    # Zynpot & Zynswitch emulation CUIAs (low level)
    def cuia_zynpot(self, params=None):
        try:
            i = int(params[0])
            d = int(params[1])
            self.get_current_screen_obj().zynpot_cb(i, d)
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

    # -------------------------------------------------------------------
    # Screen management CUIAs
    # -------------------------------------------------------------------

    def cuia_toggle_screen(self, params=None):
        if params:
            self.toggle_screen(params[0])

    def cuia_show_screen(self, params=None):
        if params:
            self.show_screen_reset(params[0])

    def cuia_screen_clean(self, params=None):
        self.state_manager.start_busy("clean_screen", "Clean screen")
        for i in range(10, 0, -1):
            self.state_manager.set_busy_details(f"Closing in {i}s")
            sleep(1)
        self.state_manager.end_busy("clean_screen")

    def cuia_refresh_screen(self, params=None):
        if params is None or self.current_screen in params:
            self.screen_lock.acquire()
            self.screens[self.current_screen].build_view()
            self.screens[self.current_screen].show()
            self.screen_lock.release()

    # -------------------------------------------------------------------
    # ZS3 management CUIAs:
    # -------------------------------------------------------------------

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
        self.screens[self.current_screen].exit_midi_learn()

    def cuia_toggle_midi_learn(self, params=None):
        try:
            state = self.screens[self.current_screen].toggle_midi_learn()
            self.state_manager.set_midi_learn(state)
        except:
            if self.state_manager.midi_learn_state:
                self.cuia_disable_midi_learn(params)
            else:
                self.cuia_enable_midi_learn(params)

    def cuia_action_midi_unlearn(self, params=None):
        try:
            self.screens[self.current_screen].midi_unlearn_action()
        except (AttributeError, TypeError):
            pass

    # Learn control
    def cuia_midi_learn_control(self, params=None):
        if self.current_screen in ("control", "alsa_mixer"):
            self.screens[self.current_screen].midi_learn(params[0])

    # Unlearn control
    def cuia_midi_unlearn_control(self, params=None):
        if self.current_screen in ("control", "alsa_mixer"):
            if params:
                self.midi_learn_zctrl = self.screens[self.current_screen].get_zcontroller(params[0])
            # if not parameter, unlearn selected learning control
            if self.midi_learn_zctrl:
                self.screens[self.current_screen].midi_unlearn_action()

    def cuia_midi_unlearn_node(self, params=None):
        if params:
            self.chain_manager.remove_midi_learn([params[0], params[1]])

    def cuia_midi_unlearn_chain(self, params=None):
        if params:
            self.chain_manager.clean_midi_learn(params[0])
        else:
            self.chain_manager.clean_midi_learn(self.chain_manager.active_chain_id)

    # -------------------------------------------------------------------
    # MIDI CUIAs
    # -------------------------------------------------------------------

    def cuia_program_change(self, params=None):
        if len(params) > 0:
            pgm = int(params[0])
            if len(params) > 1:
                chan = int(params[1])
            else:
                try:
                    chan = int(self.chain_manager.get_active_chain().midi_chan)
                    if chan >= 16:
                        chan = 0
                except:
                    chan = 0
            if 0 <= chan < 16 and 0 <= pgm < 128:
                lib_zyncore.write_zynmidi_program_change(chan, pgm)

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
    # Zynswitch Event Management
    # -------------------------------------------------------------------

    def custom_switch_ui_action(self, i, t):
        action_config = zynthian_gui_config.custom_switch_ui_actions[i]
        if not action_config:
            return

        if t in action_config:
            cuia = action_config[t]
            if cuia:
                self.callable_ui_action_params(cuia)
                return True

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
            return True

        elif i == 1:
            self.cuia_all_sounds_off()
            return True

        elif i == 2:
            return True

        elif i == 3:
            self.cuia_power_off()
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
            self.show_screen('main_menu')
            return True

        elif i == 1:
            try:
                self.screens[self.current_screen].disable_param_editor()
            except:
                pass
            self.show_screen_reset('root')
            return True

        elif i == 2:
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
        zynsigman.register_queued(zynsigman.S_CHAIN_MAN, self.chain_manager.SS_SET_ACTIVE_CHAIN, self.cb_set_active_chain)


    def unregister_signals(self):
        zynsigman.unregister(zynsigman.S_MIDI, zynsigman.SS_MIDI_NOTE_ON, self.cb_midi_note_on)
        zynsigman.unregister(zynsigman.S_MIDI, zynsigman.SS_MIDI_NOTE_OFF, self.cb_midi_note_off)
        zynsigman.unregister(zynsigman.S_CHAIN_MAN, self.chain_manager.SS_SET_ACTIVE_CHAIN, self.cb_set_active_chain)

    def cb_midi_note_on(self, izmip, chan, note, vel):
        """Handle MIDI_NOTE_ON signal

        izmip : MIDI input device index
        chan : MIDI channel
        note : Note number
        vel : Velocity value
        """

        pass

    def cb_midi_note_off(self, izmip, chan, note, vel):
        """Handle MIDI_NOTE_OFF signal

        izmip : MIDI input device index
        chan : MIDI channel
        note : Note number
        vel : Velocity value
        """

        pass

    def cb_set_active_chain(self, active_chain):
        pass

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

            # Every 4 cycles...
            if j > 4:
                j = 0
                # Refresh GUI Controllers
                try:
                    self.screens[self.current_screen].plot_zctrls()
                    pass
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
                self.screen_lock.acquire()
                if self.current_screen == "loading":
                    self.screen_lock.release()
                    self.close_screen("loading")
                else:
                    self.screen_lock.release()

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
                    self.callable_ui_action(cuia, params)

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
        # Log exit message
        logging.info("STOPPING ZYNTHIAN-UI...")

        self.exit_code = code
        self.exit_flag = True
        self.exit_wait_count = 0

        # End signal manager queue processing
        zynsigman.stop()

        # Signal zynpot thread so it can unlock and finish normally
        self.zynpot_event.set()

        # Light-off LEDs
        if self.wsleds:
            self.wsleds.end()

        # Stop State manager
        self.state_manager.stop()

        # Signal cuia thread so it can unlock and finish normally
        self.cuia_queue.put_nowait("__EXIT__")

        # Ends UI
        self.stop()

    def stop(self):
        # Get threads still running
        running_thread_names = []
        for t in [self.control_thread, self.status_thread, self.busy_thread, self.cuia_thread, self.state_manager.slow_thread, self.state_manager.fast_thread, self.zynpot_thread]:
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
        pass

    def after(self, msec, func):
        zynthian_gui_config.top.after(msec, func)

    # ------------------------------------------------------------------
    # Zynthian Config Info
    # ------------------------------------------------------------------

    # This should be removed!!
    def get_zynthian_config(self, varname):
        return eval("zynthian_gui_config.{}".format(varname))

# ------------------------------------------------------------------------------
