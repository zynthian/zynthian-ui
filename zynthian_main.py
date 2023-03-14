#!/usr/bin/python3
# -*- coding: utf-8 -*-
#******************************************************************************
# ZYNTHIAN PROJECT: Zynthian GUI
#
# Zynthian GUI Main Program
#
# Copyright (C) 2015-2022 Fernando Moyano <jofemodo@zynthian.org>
#
#******************************************************************************
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
#******************************************************************************

import os
import sys
import signal
import ctypes
import logging

# Zynthian specific modules
from zyngui import zynthian_gui_config
from zyncoder.zyncore import lib_zyncore
from zyngui.zynthian_gui import zynthian_gui
from zyngui.zynthian_gui_keybinding import zynthian_gui_keybinding

#******************************************************************************
#------------------------------------------------------------------------------
# Start Zynthian!
#------------------------------------------------------------------------------
#******************************************************************************

logging.info("STARTING ZYNTHIAN-UI ...")
zynthian_gui_config.zyngui = zyngui = zynthian_gui()
zyngui.start()

#------------------------------------------------------------------------------
# Zynlib Callbacks
#------------------------------------------------------------------------------

@ctypes.CFUNCTYPE(None, ctypes.c_ubyte, ctypes.c_int)
def zynpot_cb(i, dval):
	#logging.debug("Zynpot {} Callback => {}".format(i, dval))
	try:
		zyngui.screens[zyngui.current_screen].zynpot_cb(i, dval)
		zyngui.last_event_flag = True

	except Exception as err:
		pass # Some screens don't use controllers
		logging.exception(err)


lib_zyncore.setup_zynpot_cb(zynpot_cb)


#------------------------------------------------------------------------------
# Reparent Top Window using GTK XEmbed protocol features
#------------------------------------------------------------------------------

def flushflush():
	for i in range(1000):
		print("FLUSHFLUSHFLUSHFLUSHFLUSHFLUSHFLUSH")
	zynthian_gui_config.top.after(200, flushflush)


if zynthian_gui_config.wiring_layout=="EMULATOR":
	top_xid = zynthian_gui_config.top.winfo_id()
	print("Zynthian GUI XID: " + str(top_xid))
	if len(sys.argv) > 1:
		parent_xid = int(sys.argv[1])
		print("Parent XID: " + str(parent_xid))
		zynthian_gui_config.top.geometry('-10000-10000')
		zynthian_gui_config.top.overrideredirect(True)
		zynthian_gui_config.top.wm_withdraw()
		flushflush()
		zynthian_gui_config.top.after(1000, zynthian_gui_config.top.wm_deiconify)


#------------------------------------------------------------------------------
# Signal Catching
#------------------------------------------------------------------------------

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


#------------------------------------------------------------------------------
# Key Bindings
#------------------------------------------------------------------------------

#Function to handle computer keyboard key press
#	event: Key event
def XXX_cb_keybinding(event):
	logging.debug("Key press {} {}".format(event.keycode, event.keysym))
	zynthian_gui_config.top.focus_set()		# Must remove focus from listbox to avoid interference with physical keyboard

	if not zynthian_gui_keybinding.getInstance().isEnabled():
		logging.debug("Key binding is disabled - ignoring key press")
		return

	# Ignore TAB key (for now) to avoid confusing widget focus change
	if event.keysym == "tab":
		return

	# Space is not recognised as keysym so need to convert keycode
	if event.keycode == 65:
		keysym = "space"
	else:
		keysym = event.keysym

	action = zynthian_gui_keybinding.getInstance().get_key_action(keysym, event.state)
	if action != None:
		zyngui.set_event_flag()
		zyngui.callable_ui_action_params(action)

#zynthian_gui_config.top.bind("<Key>", cb_keybinding)


def cb_keybinding(event, keypress=True):
	# Space is not recognised as keysym so need to convert keycode
	if event.keycode == 65:
		keysym = "space"
	else:
		keysym = event.keysym.lower()

	# Ignore TAB key (for now) to avoid confusing widget focus change
	if keysym == "tab":
		return

	cuia_str = zynthian_gui_keybinding.getInstance().get_key_action(keysym, event.state)
	if cuia_str != None:
		zyngui.set_event_flag()
		parts = cuia_str.split(" ", 2)
		cuia = parts[0].lower()
		if len(parts) > 1:
			params = zyngui.parse_cuia_params(parts[1])
		else:
			params = None

		# Emulate Zynswitch Push/Release with KeyPress/KeyRelease
		if cuia == "zynswitch" and len(params) == 1:
			if keypress:
				params.append('P')
			else:
				params.append('R')
			zyngui.cuia_zynswitch(params)
		# Or normal CUIA
		elif keypress:
			zyngui.callable_ui_action(cuia, params)


def cb_keypress(event):
	logging.debug("Key Press {} {}".format(event.keycode, event.keysym))
	cb_keybinding(event, True)

def cb_keyrelease(event):
	logging.debug("Key Release {} {}".format(event.keycode, event.keysym))
	cb_keybinding(event, False)

zynthian_gui_config.top.bind("<KeyPress>", cb_keypress)
zynthian_gui_config.top.bind("<KeyRelease>", cb_keyrelease)


#------------------------------------------------------------------------------
# Mouse/Touch Bindings
#------------------------------------------------------------------------------

zynthian_gui_config.top.bind("<Button-1>", zyngui.cb_touch)
zynthian_gui_config.top.bind("<ButtonRelease-1>", zyngui.cb_touch_release)

#------------------------------------------------------------------------------
# TKinter Main Loop
#------------------------------------------------------------------------------

#import cProfile
#cProfile.run('zynthian_gui_config.top.mainloop()')

zynthian_gui_config.top.mainloop()

#------------------------------------------------------------------------------
# Exit
#------------------------------------------------------------------------------

logging.info("Exit with code {} ...\n\n".format(zyngui.exit_code))
exit(zyngui.exit_code)

#------------------------------------------------------------------------------
