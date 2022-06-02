#!/usr/bin/python3
# -*- coding: utf-8 -*-
#******************************************************************************
# ZYNTHIAN PROJECT: Zynthian GUI
# 
# Zynthian GUI configuration
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
import re
import sys
import logging

# Zynthian specific modules
import zynconf

#******************************************************************************

#------------------------------------------------------------------------------
# Log level and debuging
#------------------------------------------------------------------------------

log_level=int(os.environ.get('ZYNTHIAN_LOG_LEVEL',logging.WARNING))
#log_level=logging.DEBUG

logging.basicConfig(format='%(levelname)s:%(module)s.%(funcName)s: %(message)s', stream=sys.stderr, level=log_level)
logging.getLogger().setLevel(level=log_level)

# Reduce log level for other modules
logging.getLogger("urllib3").setLevel(logging.WARNING)

logging.info("ZYNTHIAN-UI CONFIG ...")

#------------------------------------------------------------------------------
# Wiring layout
#------------------------------------------------------------------------------

ENC_LAYER			= 0
ENC_BACK			= 1
ENC_SNAPSHOT		= 2
ENC_SELECT			= 3

wiring_layout=os.environ.get('ZYNTHIAN_WIRING_LAYOUT',"DUMMIES")
if wiring_layout=="DUMMIES":
	logging.info("No Wiring Layout configured. Only touch interface is available.")
else:
	logging.info("Wiring Layout %s" % wiring_layout)

if wiring_layout=="PROTOTYPE-1":
	select_ctrl=2
else:
	select_ctrl=3

# Zynswitches timing
zynswitch_bold_us = 1000 * 300 
zynswitch_long_us = 1000 * 2000

def config_zynswitch_timing():
	global zynswitch_bold_us
	global zynswitch_long_us
	try:
		zynswitch_bold_us = 1000 * int(os.environ.get('ZYNTHIAN_UI_SWITCH_BOLD_MS', 300))
		zynswitch_long_us = 1000 * int(os.environ.get('ZYNTHIAN_UI_SWITCH_LONG_MS', 2000))
	except Exception as e:
		logging.error("ERROR configuring zynswitch timing: {}".format(e))

#------------------------------------------------------------------------------
# Custom Switches Action Configuration
#------------------------------------------------------------------------------

custom_switch_ui_actions = []
custom_switch_midi_events = []

def config_custom_switches():
	global num_zynswitches
	global custom_switch_ui_actions
	global custom_switch_midi_events

	custom_switch_ui_actions = []
	custom_switch_midi_events = []

	for i in range(num_zynswitches):
		cuias = {}
		midi_event = None

		root_varname = "ZYNTHIAN_WIRING_CUSTOM_SWITCH_{:02d}".format(i+1)
		custom_type = os.environ.get(root_varname, "")

		if custom_type == "UI_ACTION_PUSH":
			cuias['P'] = os.environ.get(root_varname + "__UI_PUSH", "")
			cuias['S'] = ""
			cuias['B'] = ""
			cuias['L'] = ""
		elif custom_type == "UI_ACTION" or custom_type == "UI_ACTION_RELEASE":
			cuias['P'] = ""
			cuias['S'] = os.environ.get(root_varname + "__UI_SHORT", "")
			cuias['B'] = os.environ.get(root_varname + "__UI_BOLD", "")
			cuias['L'] = os.environ.get(root_varname + "__UI_LONG", "")
		elif custom_type != "":
			evtype = None
			if custom_type=="MIDI_CC":
				evtype = 0xB
			elif custom_type=="MIDI_NOTE":
				evtype = 0x9
			elif custom_type=="MIDI_PROG_CHANGE":
				evtype = 0xC
			elif custom_type=="CVGATE_IN":
				evtype = -4
			elif custom_type=="CVGATE_OUT":
				evtype = -5
			elif custom_type=="GATE_OUT":
				evtype = -6
			elif custom_type=="MIDI_CC_SWITCH":
				evtype = -7

			if evtype:
				chan = os.environ.get(root_varname + "__MIDI_CHAN")
				try:
					chan = int(chan) - 1
					if chan<0 or chan>15:
						chan = None
				except:
					chan = None

				if evtype in (-4, -5):
					num = os.environ.get(root_varname + "__CV_CHAN")
				else:
					num = os.environ.get(root_varname + "__MIDI_NUM")

				try:
					val = int(os.environ.get(root_varname + "__MIDI_VAL"))
					val = max(min(127, val), 0)
				except:
					val = 0

				try:
					num = int(num)
					if num>=0 and num<=127:
						midi_event = {
							'type': evtype,
							'chan': chan,
							'num': num,
							'val': val
						}
				except:
					pass

		custom_switch_ui_actions.append(cuias)
		custom_switch_midi_events.append(midi_event)


#------------------------------------------------------------------------------
# Zynaptik & Zyntof configuration
#------------------------------------------------------------------------------

zynaptik_ad_midi_events = []
zynaptik_da_midi_events = []
zyntof_midi_events = []


def get_zynsensor_config(root_varname):
	midi_event = None
	evtype = None

	event_type = os.environ.get(root_varname, "")
	if event_type=="MIDI_CC":
		evtype = 0xB
	elif event_type=="MIDI_PITCH_BEND":
		evtype = 0xE
	elif event_type=="MIDI_CHAN_PRESS":
		evtype = 0xD
	else:
		evtype = None

	if evtype:
		chan = os.environ.get(root_varname + "__MIDI_CHAN")
		try:
			chan = int(chan) - 1
			if chan<0 or chan>15:
				chan = None
		except:
			chan = None

		num = os.environ.get(root_varname + "__MIDI_NUM")
		try:
			num = int(num)
			if num>=0 and num<=127:
				midi_event = {
					'type': evtype,
					'chan': chan,
					'num': num
				}
		except:
			pass

	return midi_event


def config_zynaptik():
	global zynaptik_ad_midi_events
	global zynaptik_da_midi_events

	zynaptik_ad_midi_events = []
	zynaptik_da_midi_events = []

	zynaptik_config = os.environ.get("ZYNTHIAN_WIRING_ZYNAPTIK_CONFIG")
	if zynaptik_config:
		# Zynaptik AD Action Configuration
		if "4xAD" in zynaptik_config:
			for i in range(4):
				root_varname = "ZYNTHIAN_WIRING_ZYNAPTIK_AD{:02d}".format(i+1)
				zynaptik_ad_midi_events.append(get_zynsensor_config(root_varname))

		# Zynaptik DA Action Configuration
		if "4xDA" in zynaptik_config:
			for i in range(4):
				root_varname = "ZYNTHIAN_WIRING_ZYNAPTIK_DA{:02d}".format(i+1)
				zynaptik_da_midi_events.append(get_zynsensor_config(root_varname))


def config_zyntof():
	global zyntof_midi_events
	zyntof_midi_events = []

	zyntof_config = os.environ.get("ZYNTHIAN_WIRING_ZYNTOF_CONFIG")
	if zyntof_config:
		# Zyntof Action Configuration
		n_zyntofs = int(zyntof_config)
		for i in range(0, n_zyntofs):
			root_varname = "ZYNTHIAN_WIRING_ZYNTOF{:02d}".format(i+1)
			zyntof_midi_events.append(get_zynsensor_config(root_varname))


#------------------------------------------------------------------------------
# MIDI Configuration
#------------------------------------------------------------------------------

def set_midi_config():
	global preset_preload_noteon, midi_single_active_channel
	global midi_prog_change_zs3, midi_bank_change, midi_fine_tuning
	global midi_filter_rules, midi_filter_output
	global midi_sys_enabled, midi_cc_automode, midi_aubionotes_enabled
	global midi_network_enabled, midi_rtpmidi_enabled, midi_touchosc_enabled
	global master_midi_channel, master_midi_change_type
	global master_midi_program_change_up, master_midi_program_change_down
	global master_midi_program_base, master_midi_bank_change_ccnum
	global master_midi_bank_change_up, master_midi_bank_change_down
	global master_midi_bank_change_down_ccnum, master_midi_bank_base
	global disabled_midi_in_ports, enabled_midi_out_ports, enabled_midi_fb_ports

	# MIDI options
	midi_fine_tuning=float(os.environ.get('ZYNTHIAN_MIDI_FINE_TUNING',440.0))
	midi_single_active_channel=int(os.environ.get('ZYNTHIAN_MIDI_SINGLE_ACTIVE_CHANNEL',0))
	midi_prog_change_zs3=int(os.environ.get('ZYNTHIAN_MIDI_PROG_CHANGE_ZS3',1))
	midi_bank_change=int(os.environ.get('ZYNTHIAN_MIDI_BANK_CHANGE',0))
	preset_preload_noteon=int(os.environ.get('ZYNTHIAN_MIDI_PRESET_PRELOAD_NOTEON',1))
	midi_filter_output=int(os.environ.get('ZYNTHIAN_MIDI_FILTER_OUTPUT',1))
	midi_sys_enabled=int(os.environ.get('ZYNTHIAN_MIDI_SYS_ENABLED',1))
	midi_cc_automode=int(os.environ.get('ZYNTHIAN_MIDI_CC_AUTOMODE',1))
	midi_network_enabled=int(os.environ.get('ZYNTHIAN_MIDI_NETWORK_ENABLED',0))
	midi_rtpmidi_enabled=int(os.environ.get('ZYNTHIAN_MIDI_RTPMIDI_ENABLED',0))
	midi_touchosc_enabled=int(os.environ.get('ZYNTHIAN_MIDI_TOUCHOSC_ENABLED',0))
	midi_aubionotes_enabled=int(os.environ.get('ZYNTHIAN_MIDI_AUBIONOTES_ENABLED',0))

	# Filter Rules
	midi_filter_rules=os.environ.get('ZYNTHIAN_MIDI_FILTER_RULES',"")
	midi_filter_rules=midi_filter_rules.replace("\\n","\n")

	# MIDI Ports
	midi_ports=os.environ.get('ZYNTHIAN_MIDI_PORTS',"DISABLED_IN=\nENABLED_OUT=ttymidi:MIDI_out\nENABLED_FB=")
	midi_ports=midi_ports.replace("\\n","\n")
	disabled_midi_in_ports=zynconf.get_disabled_midi_in_ports(midi_ports)
	enabled_midi_out_ports=zynconf.get_enabled_midi_out_ports(midi_ports)
	enabled_midi_fb_ports=zynconf.get_enabled_midi_fb_ports(midi_ports)

	# Master Channel Features
	master_midi_channel = int(os.environ.get('ZYNTHIAN_MIDI_MASTER_CHANNEL',16))
	master_midi_channel -= 1
	if master_midi_channel>15:
		master_midi_channel = 15
	if master_midi_channel>=0: 
		mmc_hex = hex(master_midi_channel)[2]
	else:
		mmc_hex = None

	master_midi_change_type = os.environ.get('ZYNTHIAN_MIDI_MASTER_CHANGE_TYPE',"Roland")

	#Use LSB Bank by default
	master_midi_bank_change_ccnum = int(os.environ.get('ZYNTHIAN_MIDI_MASTER_BANK_CHANGE_CCNUM',0x20))
	#Use MSB Bank by default
	#master_midi_bank_change_ccnum = int(os.environ.get('ZYNTHIAN_MIDI_MASTER_BANK_CHANGE_CCNUM',0x00))

	mmpcu = os.environ.get('ZYNTHIAN_MIDI_MASTER_PROGRAM_CHANGE_UP', "")
	if mmc_hex and len(mmpcu)==4:
		master_midi_program_change_up = int('{:<06}'.format(mmpcu.replace('#',mmc_hex)),16)
	else:
		master_midi_program_change_up = None

	mmpcd = os.environ.get('ZYNTHIAN_MIDI_MASTER_PROGRAM_CHANGE_DOWN', "")
	if mmc_hex and len(mmpcd)==4:
		master_midi_program_change_down = int('{:<06}'.format(mmpcd.replace('#',mmc_hex)),16)
	else:
		master_midi_program_change_down = None

	mmbcu = os.environ.get('ZYNTHIAN_MIDI_MASTER_BANK_CHANGE_UP', "")
	if mmc_hex and len(mmbcu)==6:
		master_midi_bank_change_up = int('{:<06}'.format(mmbcu.replace('#',mmc_hex)),16)
	else:
		master_midi_bank_change_up = None

	mmbcd = os.environ.get('ZYNTHIAN_MIDI_MASTER_BANK_CHANGE_DOWN', "")
	if mmc_hex and len(mmbcd)==6:
		master_midi_bank_change_down = int('{:<06}'.format(mmbcd.replace('#',mmc_hex)),16)
	else:
		master_midi_bank_change_down = None

	logging.debug("MMC Bank Change CCNum: {}".format(master_midi_bank_change_ccnum))
	logging.debug("MMC Bank Change UP: {}".format(master_midi_bank_change_up))
	logging.debug("MMC Bank Change DOWN: {}".format(master_midi_bank_change_down))
	logging.debug("MMC Program Change UP: {}".format(master_midi_program_change_up))
	logging.debug("MMC Program Change DOWN: {}".format(master_midi_program_change_down))


#------------------------------------------------------------------------------
# UI Color Parameters
#------------------------------------------------------------------------------

color_bg=os.environ.get('ZYNTHIAN_UI_COLOR_BG',"#000000")
color_tx=os.environ.get('ZYNTHIAN_UI_COLOR_TX',"#ffffff")
color_tx_off=os.environ.get('ZYNTHIAN_UI_COLOR_TX_OFF',"#e0e0e0")
color_on=os.environ.get('ZYNTHIAN_UI_COLOR_ON',"#ff0000")
color_off=os.environ.get('ZYNTHIAN_UI_COLOR_OFF',"#5a626d")
color_hl=os.environ.get('ZYNTHIAN_UI_COLOR_HL',"#00b000")
color_ml=os.environ.get('ZYNTHIAN_UI_COLOR_ML',"#f0f000")
color_low_on=os.environ.get('ZYNTHIAN_UI_COLOR_LOW_ON',"#b00000")
color_panel_bg=os.environ.get('ZYNTHIAN_UI_COLOR_PANEL_BG',"#3a424d")
color_panel_hl=os.environ.get('ZYNTHIAN_UI_COLOR_PANEL_HL',"#2a323d")
color_info=os.environ.get('ZYNTHIAN_UI_COLOR_INFO',"#8080ff")
color_error=os.environ.get('ZYNTHIAN_UI_COLOR_ERROR',"#ff0000")

# Color Scheme
color_panel_bd=color_bg
color_panel_tx=color_tx
color_header_bg=color_bg
color_header_tx=color_tx
color_ctrl_bg_off=color_off
color_ctrl_bg_on=color_on
color_ctrl_tx=color_tx
color_ctrl_tx_off=color_tx_off
color_status_midi=color_info
color_status_play=color_hl
color_status_record=color_low_on
color_status_error=color_error

#------------------------------------------------------------------------------
# Font Family
#------------------------------------------------------------------------------

font_family=os.environ.get('ZYNTHIAN_UI_FONT_FAMILY',"Audiowide")
#font_family="Helvetica" #=> the original ;-)
#font_family="Economica" #=> small
#font_family="Orbitron" #=> Nice, but too strange
#font_family="Abel" #=> Quite interesting, also "Strait"

#------------------------------------------------------------------------------
# Touch Options
#------------------------------------------------------------------------------

enable_touch_widgets=int(os.environ.get('ZYNTHIAN_UI_TOUCH_WIDGETS',False))
enable_onscreen_buttons=int(os.environ.get('ZYNTHIAN_UI_ONSCREEN_BUTTONS',False))
force_enable_cursor=int(os.environ.get('ZYNTHIAN_UI_ENABLE_CURSOR',False))

#------------------------------------------------------------------------------
# UI Options
#------------------------------------------------------------------------------

restore_last_state=int(os.environ.get('ZYNTHIAN_UI_RESTORE_LAST_STATE',False))
snapshot_mixer_settings=int(os.environ.get('ZYNTHIAN_UI_SNAPSHOT_MIXER_SETTINGS',False))
show_cpu_status=int(os.environ.get('ZYNTHIAN_UI_SHOW_CPU_STATUS',False))
visible_mixer_strips=int(os.environ.get('ZYNTHIAN_UI_VISIBLE_MIXER_STRIPS',0))
multichannel_recorder=int(os.environ.get('ZYNTHIAN_UI_MUKTICHANNEL_REC', 0))

#------------------------------------------------------------------------------
# Audio Options
#------------------------------------------------------------------------------

rbpi_headphones=int(os.environ.get('ZYNTHIAN_RBPI_HEADPHONES',False))

#------------------------------------------------------------------------------
# Networking Options
#------------------------------------------------------------------------------

vncserver_enabled=int(os.environ.get('ZYNTHIAN_VNCSERVER_ENABLED',False))

#------------------------------------------------------------------------------
# Player configuration
#------------------------------------------------------------------------------

midi_play_loop=int(os.environ.get('ZYNTHIAN_MIDI_PLAY_LOOP',0))
audio_play_loop=int(os.environ.get('ZYNTHIAN_AUDIO_PLAY_LOOP',0))

#------------------------------------------------------------------------------
# Experimental features
#------------------------------------------------------------------------------

experimental_features = os.environ.get('ZYNTHIAN_EXPERIMENTAL_FEATURES',"").split(',')

#------------------------------------------------------------------------------
# X11 Related Stuff
#------------------------------------------------------------------------------

if "zynthian_gui.py" in sys.argv[0]:
	import tkinter
	from PIL import Image, ImageTk

	try:
		#------------------------------------------------------------------------------
		# Create & Configure Top Level window 
		#------------------------------------------------------------------------------

		top = tkinter.Tk()

		# Screen Size => Autodetect if None
		if os.environ.get('DISPLAY_WIDTH'):
			display_width=int(os.environ.get('DISPLAY_WIDTH'))
		else:
			try:
				display_width = top.winfo_screenwidth()
			except:
				logging.warning("Can't get screen width. Using default 320!")
				display_width=320

		if os.environ.get('DISPLAY_HEIGHT'):
			display_height=int(os.environ.get('DISPLAY_HEIGHT'))
		else:
			try:
				display_height = top.winfo_screenheight()
			except:
				logging.warning("Can't get screen height. Using default 240!")
				display_height=240

		# Global font size
		font_size=int(os.environ.get('ZYNTHIAN_UI_FONT_SIZE',None))
		if not font_size:
			font_size = int(display_width / 40)

		# Geometric params
		button_width = display_width // 4
		buttonbar_height = enable_onscreen_buttons and display_height // 7 or 0
		if display_width>=800:
			topbar_height = display_height // 12
			topbar_fs = int(1.5*font_size)
			title_y = int(0.1 * topbar_height)
		else:
			topbar_height = display_height // 10
			topbar_fs = int(1.1*font_size)
			title_y = int(0.05 * topbar_height)
		body_height = display_height - topbar_height - buttonbar_height

		# Controllers position and size
		if wiring_layout.startswith("Z2"):
			ctrl_both_sides = False
			ctrl_width = display_width // 4
			ctrl_height = (body_height // 4) -1
			ctrl_pos=[
				(1,2,"ne"),
				(2,2,"ne"),
				(3,2,"ne"),
				(4,2,"ne")
			]
		else:
			ctrl_both_sides = True
			ctrl_width = display_width // 4
			ctrl_height = body_height // 2
			ctrl_pos=[
				(1,0,"nw"),
				(2,0,"sw"),
				(1,2,"ne"),
				(2,2,"se")
			]

		# Adjust Root Window Geometry
		top.geometry(str(display_width)+'x'+str(display_height))
		top.maxsize(display_width,display_height)
		top.minsize(display_width,display_height)

		# Disable cursor for real Zynthian Boxes
		if wiring_layout!="EMULATOR" and wiring_layout!="DUMMIES" and not force_enable_cursor:
			top.config(cursor="none")
		else:
			top.config(cursor="cross")

		#------------------------------------------------------------------------------
		# Global Variables
		#------------------------------------------------------------------------------

		# Fonts
		font_listbox = (font_family,int(1.0*font_size))
		font_topbar = (font_family,topbar_fs)
		font_buttonbar = (font_family,int(0.8*font_size))

		# Loading Logo Animation
		loading_imgs=[]
		pil_frame = Image.open("./img/zynthian_gui_loading.gif")
		fw, fh = pil_frame.size
		fw2=ctrl_width-8
		fh2=int(fh*fw2/fw)
		nframes = 0
		while pil_frame:
			pil_frame2 = pil_frame.resize((fw2, fh2), Image.ANTIALIAS)
			# convert PIL image object to Tkinter PhotoImage object
			loading_imgs.append(ImageTk.PhotoImage(pil_frame2))
			nframes += 1
			try:
				pil_frame.seek(nframes)
			except EOFError:
				break
		#for i in range(13):
		#	loading_imgs.append(tkinter.PhotoImage(file="./img/zynthian_gui_loading.gif", format="gif -index "+str(i)))

	except Exception as e:
		logging.error("ERROR initializing Tkinter graphic framework => {}".format(e))


	#------------------------------------------------------------------------------
	# Initialize ZynCore low-level library
	#------------------------------------------------------------------------------

	from zyncoder.zyncore import lib_zyncore_init

	try:
		lib_zyncore = lib_zyncore_init()
	except Exception as e:
		logging.error("ERROR initializing ZynCore: {}".format(e))

	#------------------------------------------------------------------------------
	# Initialize and config control I/O subsystem: switches, analog I/O, ...
	#------------------------------------------------------------------------------

	try:
		num_zynswitches = lib_zyncore.get_num_zynswitches()
		last_zynswitch_index = lib_zyncore.get_last_zynswitch_index()
		num_zynpots = lib_zyncore.get_num_zynpots()
		config_zynswitch_timing()
		config_custom_switches()
		config_zynaptik()
		config_zyntof()
	except Exception as e:
		logging.error("ERROR configuring control I/O subsytem: {}".format(e))

	#------------------------------------------------------------------------------
	# Load MIDI config
	#------------------------------------------------------------------------------

	try:
		set_midi_config()
	except Exception as e:
		logging.error("ERROR configuring MIDI: {}".format(e))



#------------------------------------------------------------------------------
# Zynthian GUI variable
#------------------------------------------------------------------------------

zyngui=None

#------------------------------------------------------------------------------
