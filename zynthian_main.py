#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# ******************************************************************************
# ZYNTHIAN PROJECT: Zynthian GUI
#
# Zynthian GUI Main Program
#
# Copyright (C) 2015-2023 Fernando Moyano <jofemodo@zynthian.org>
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

import sys
import signal
import ctypes
import logging
from tkinter import EventType

# Zynthian specific modules
from zyngui import zynthian_gui_config
from zyngine.zynthian_chain import *
from zyncoder.zyncore import get_lib_zyncore
from zyngui.zynthian_gui import zynthian_gui
from zyngui import zynthian_gui_keybinding
from zynlibs.zynseq import *

# ******************************************************************************
# ------------------------------------------------------------------------------
# Start Zynthian!
# ------------------------------------------------------------------------------
# ******************************************************************************

logging.info("STARTING ZYNTHIAN-UI ...")
zynthian_gui_config.zyngui = zyngui = zynthian_gui()
zyngui.create_screens()
zyngui.run_start_thread()

# ------------------------------------------------------------------------------
# Zynlib Callbacks
# ------------------------------------------------------------------------------


@ctypes.CFUNCTYPE(None, ctypes.c_ubyte, ctypes.c_int)
def zynpot_cb(i, dval):
    # logging.debug("Zynpot {} Callback => {}".format(i, dval))
    try:
        zyngui.zynpot_lock.acquire()
        zyngui.zynpot_dval[i] += dval
        zyngui.zynpot_lock.release()
        zyngui.zynpot_event.set()
    except Exception as err:
        logging.exception(err)


get_lib_zyncore().setup_zynpot_cb(zynpot_cb)

# ------------------------------------------------------------------------------
# Reparent Top Window using GTK XEmbed protocol features
# ------------------------------------------------------------------------------


def flushflush():
    for i in range(1000):
        print("FLUSHFLUSHFLUSHFLUSHFLUSHFLUSHFLUSH")
    zynthian_gui_config.top.after(200, flushflush)


if zynthian_gui_config.wiring_layout == "EMULATOR":
    top_xid = zynthian_gui_config.top.winfo_id()
    print("Zynthian GUI XID: " + str(top_xid))
    if len(sys.argv) > 1:
        parent_xid = int(sys.argv[1])
        print("Parent XID: " + str(parent_xid))
        zynthian_gui_config.top.geometry('-10000-10000')
        zynthian_gui_config.top.overrideredirect(True)
        zynthian_gui_config.top.wm_withdraw()
        flushflush()
        zynthian_gui_config.top.after(
            1000, zynthian_gui_config.top.wm_deiconify)


# ------------------------------------------------------------------------------
# Signal Catching
# ------------------------------------------------------------------------------

def exit_handler(signo, stack_frame):
    logging.info("Catch Exit Signal ({}) ...".format(signo))
    if signo == signal.SIGHUP:
        exit_code = 0
    elif signo == signal.SIGINT:
        exit_code = 100
    elif signo == signal.SIGQUIT:
        exit_code = 102
    elif signo == signal.SIGTERM:
        exit_code = 101
    else:
        exit_code = 0
    zyngui.exit(exit_code)


signal.signal(signal.SIGHUP, exit_handler)
signal.signal(signal.SIGINT, exit_handler)
signal.signal(signal.SIGQUIT, exit_handler)
signal.signal(signal.SIGTERM, exit_handler)


def delete_window():
    exit_code = 101
    zyngui.exit(exit_code)


zynthian_gui_config.top.protocol("WM_DELETE_WINDOW", delete_window)


# ------------------------------------------------------------------------------
# Key Bindings
# ------------------------------------------------------------------------------

cb_toggle = {}


def cb_keybinding(event):
    """Handle key press/release event

    event : key event
    keypress : True if press, False if release
    """
    # Avoid TAB confusing widget focus change
    if event.keycode == 23:
        zynthian_gui_config.top.focus_set()

    cuia = zynthian_gui_keybinding.get_key_action(event.keycode, event.state)
    if cuia is not None:
        # Emulate Zynswitch Push/Release with KeyPress/KeyRelease
        if cuia.lower().startswith("zyn"):
            if cuia[-2:] == ',T':
                if event.type == EventType.KeyPress:
                    if event.keycode in cb_toggle:
                        cb_toggle[event.keycode] = not cb_toggle[event.keycode]
                    else:
                        cb_toggle[event.keycode] = True
                    if cb_toggle[event.keycode]:
                        zyngui.cuia_queue.put_nowait(cuia[:-1] + "P")
                    else:
                        zyngui.cuia_queue.put_nowait(cuia[:-1] + "R")
            elif event.type == EventType.KeyPress:
                zyngui.cuia_queue.put_nowait(cuia + ",P")
            else:
                zyngui.cuia_queue.put_nowait(cuia + ",R")
        # Or normal CUIA
        elif event.type == EventType.KeyPress:
            zyngui.cuia_queue.put_nowait(cuia)


zynthian_gui_config.top.bind("<KeyPress>", cb_keybinding)
zynthian_gui_config.top.bind("<KeyRelease>", cb_keybinding)

# ------------------------------------------------------------------------------
# Mouse/Touch Bindings
# ------------------------------------------------------------------------------

zynthian_gui_config.top.bind("<Button-1>", zyngui.cb_touch)
zynthian_gui_config.top.bind("<ButtonRelease-1>", zyngui.cb_touch_release)

# ------------------------------------------------------------------------------
# TKinter Main Loop
# ------------------------------------------------------------------------------

# import cProfile
# cProfile.run('zynthian_gui_config.top.mainloop()')

try:
    zynthian_gui_config.top.mainloop()
except Exception as e:
    logging.error(f"Main Loop Exception: {e}")

if 0 <= zyngui.exit_wait_count <= 10:
    logging.error("Forced exit! Trying to terminate properly...")
    zyngui.exit()
    sleep(2)

# ------------------------------------------------------------------------------
# Exit
# ------------------------------------------------------------------------------

logging.info("Exit with code {} ...\n\n".format(zyngui.exit_code))
sys.exit(zyngui.exit_code)

# ------------------------------------------------------------------------------
