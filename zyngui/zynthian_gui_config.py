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
import sys
import logging

# Zynthian specific modules
from zyngine import zyngine_config

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

if zyngine_config.wiring_layout.startswith("Z2") and not enable_onscreen_buttons:
	enable_touch_controller_switches = 0
else:
	enable_touch_controller_switches = 1

#------------------------------------------------------------------------------
# UI Options
#------------------------------------------------------------------------------

show_cpu_status=int(os.environ.get('ZYNTHIAN_UI_SHOW_CPU_STATUS',False))
visible_mixer_strips=int(os.environ.get('ZYNTHIAN_UI_VISIBLE_MIXER_STRIPS',0))
multichannel_recorder=int(os.environ.get('ZYNTHIAN_UI_MULTICHANNEL_RECORDER', 0))
ctrl_graph=int(os.environ.get('ZYNTHIAN_UI_CTRL_GRAPH', 1))
enable_dpm=int(os.environ.get('ZYNTHIAN_DPM',True))


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
# Sequence states
#------------------------------------------------------------------------------

PAD_COLOUR_DISABLED = '#2a2a2a'
PAD_COLOUR_STARTING = '#ffbb00'
PAD_COLOUR_PLAYING = '#00d000'
PAD_COLOUR_STOPPING = 'red'
PAD_COLOUR_STOPPED = [
	'#000060',			#1 dark
	'#048C8C',			#2 dark
	'#996633',			#3 dark
	'#0010A0',			#4 medium too similar to 12
	'#BF9C7C',			#5 medium
	'#999966',			#6 medium
	'#FC6CB4',			#7 medium
	'#CC8464',			#8 medium
	'#4C94CC',			#9 medium
	'#B454CC',			#10 medium
	'#B08080',			#11 medium
	'#0404FC', 			#12 light
	'#9EBDAC',			#13 light
	'#FF13FC',			#14 light
	'#3080C0',			#15 light
	'#9C7CEC'			#16 light
]


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
			display_width = int(os.environ.get('DISPLAY_WIDTH'))
		else:
			try:
				display_width = top.winfo_screenwidth()
			except:
				logging.warning("Can't get screen width. Using default 320!")
				display_width = 320

		if os.environ.get('DISPLAY_HEIGHT'):
			display_height = int(os.environ.get('DISPLAY_HEIGHT'))
		else:
			try:
				display_height = top.winfo_screenheight()
			except:
				logging.warning("Can't get screen height. Using default 240!")
				display_height = 240

		# Global font size
		font_size = int(os.environ.get('ZYNTHIAN_UI_FONT_SIZE',None))
		if not font_size:
			font_size = int(display_width / 40)

		# Geometric params
		button_width = display_width // 4
		if display_width >= 800:
			topbar_height = display_height // 12
			topbar_fs = int(1.5*font_size)
			title_y = int(0.1 * topbar_height)
		else:
			topbar_height = display_height // 10
			topbar_fs = int(1.1*font_size)
			title_y = int(0.05 * topbar_height)

		# Controllers position and size
		# pos(row,col)
		if zyngine_config.wiring_layout.startswith("Z2"):
			layout = {
				'name': 'Z2',
				'columns': 2,
				'rows': 4,
				'ctrl_pos': [
					(0,1),
					(1,1),
					(2,1),
					(3,1)
				],
				'list_pos': (0,0),
				'ctrl_orientation': 'horizontal'
			}
		else:
			layout = {
				'name': 'V4',
				'columns': 3,
				'rows': 2,
				'ctrl_pos': [
					(0,0),
					(1,0),
					(0,2),
					(1,2)
				],
				'list_pos': (0,1),
				'ctrl_orientation': 'vertical'
			}


		# Adjust Root Window Geometry
		top.geometry(str(display_width)+'x'+str(display_height))
		top.maxsize(display_width, display_height)
		top.minsize(display_width, display_height)

		# Disable cursor for real Zynthian Boxes
		if zyngine_config.wiring_layout!="EMULATOR" and zyngine_config.wiring_layout!="DUMMIES" and not force_enable_cursor:
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
		fw2 = display_width // 4 - 8
		fh2 = int(fh * fw2 / fw)
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
# Zynthian GUI variable
#------------------------------------------------------------------------------

zyngui=None

#------------------------------------------------------------------------------
