#!/usr/bin/python3
# -*- coding: utf-8 -*-
#******************************************************************************
# ZYNTHIAN PROJECT: Zynthian GUI
# 
# Zynthian GUI configuration
# 
# Copyright (C) 2015-2016 Fernando Moyano <jofemodo@zynthian.org>
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
import tkinter
from PIL import Image, ImageTk

# Zynthian specific modules
import zynconf

#******************************************************************************

#------------------------------------------------------------------------------
# Log level and debuging
#------------------------------------------------------------------------------

log_level=int(os.environ.get('ZYNTHIAN_LOG_LEVEL',logging.WARNING))
#log_level=logging.DEBUG

raise_exceptions=int(os.environ.get('ZYNTHIAN_RAISE_EXCEPTIONS',False))

# Set root logging level
logging.basicConfig(stream=sys.stderr, level=log_level)

#------------------------------------------------------------------------------
# Wiring layout
#------------------------------------------------------------------------------

wiring_layout=os.environ.get('ZYNTHIAN_WIRING_LAYOUT',"DUMMIES")
if wiring_layout=="DUMMIES":
	logging.info("No Wiring Layout configured. Only touch interface is available.")
else:
	logging.info("Wiring Layout %s" % wiring_layout)

if os.environ.get('ZYNTHIAN_WIRING_ENCODER_A'):
	zyncoder_pin_a=list(map(int, os.environ.get('ZYNTHIAN_WIRING_ENCODER_A').split(',')))
else:
	zyncoder_pin_a=None

if os.environ.get('ZYNTHIAN_WIRING_ENCODER_B'):
	zyncoder_pin_b=list(map(int, os.environ.get('ZYNTHIAN_WIRING_ENCODER_B').split(',')))
else:
	zyncoder_pin_b=None

if os.environ.get('ZYNTHIAN_WIRING_SWITCHES'):
	zynswitch_pin=list(map(int, os.environ.get('ZYNTHIAN_WIRING_SWITCHES').split(',')))
else:
	zynswitch_pin=None

#------------------------------------------------------------------------------
# Zyncoder GPIO pin assignment (wiringPi numbering)
#------------------------------------------------------------------------------

# First Prototype => Generic Plastic Case
if wiring_layout=="PROTOTYPE-1":
	if not zyncoder_pin_a: zyncoder_pin_a=[27,21,3,7]
	if not zyncoder_pin_b: zyncoder_pin_b=[25,26,4,0]
	if not zynswitch_pin: zynswitch_pin=[23,None,2,None]
	select_ctrl=2
# Controller RBPi connector downside, controller 1 reversed
elif wiring_layout=="PROTOTYPE-2":
	if not zyncoder_pin_a: zyncoder_pin_a=[27,21,4,0]
	if not zyncoder_pin_b: zyncoder_pin_b=[25,26,3,7]
	if not zynswitch_pin: zynswitch_pin=[23,107,2,106]
	select_ctrl=3
# Controller RBPi connector upside
elif wiring_layout=="PROTOTYPE-3":
	if not zyncoder_pin_a: zyncoder_pin_a=[27,21,3,7]
	if not zyncoder_pin_b: zyncoder_pin_b=[25,26,4,0]
	if not zynswitch_pin: zynswitch_pin=[107,23,106,2]
	select_ctrl=3
# Controller RBPi connector downside (Holger's way)
elif wiring_layout=="PROTOTYPE-3H":
	if not zyncoder_pin_a: zyncoder_pin_a=[21,27,7,3]
	if not zyncoder_pin_b: zyncoder_pin_b=[26,25,0,4]
	if not zynswitch_pin: zynswitch_pin=[107,23,106,2]
	select_ctrl=3
# Controller RBPi connector upside / Controller Singles
elif wiring_layout=="PROTOTYPE-4":
	if not zyncoder_pin_a: zyncoder_pin_a=[26,25,0,4]
	if not zyncoder_pin_b: zyncoder_pin_b=[21,27,7,3]
	if not zynswitch_pin: zynswitch_pin=[107,23,106,2]
	select_ctrl=3
# Controller RBPi connector downside / Controller Singles Inverted
elif wiring_layout=="PROTOTYPE-4B":
	if not zyncoder_pin_a: zyncoder_pin_a=[25,26,4,0]
	if not zyncoder_pin_b: zyncoder_pin_b=[27,21,3,7]
	if not zynswitch_pin: zynswitch_pin=[23,107,2,106]
	select_ctrl=3
# Kees layout, for display Waveshare 3.2
elif wiring_layout=="PROTOTYPE-KEES":
	if not zyncoder_pin_a: zyncoder_pin_a=[27,21,4,5]
	if not zyncoder_pin_b: zyncoder_pin_b=[25,26,31,7]
	if not zynswitch_pin: zynswitch_pin=[23,107,6,106]
	select_ctrl=3
# Controller RBPi connector upside / Controller Singles / Switches throw GPIO expander
elif wiring_layout=="PROTOTYPE-5":
	if not zyncoder_pin_a: zyncoder_pin_a=[26,25,0,4]
	if not zyncoder_pin_b: zyncoder_pin_b=[21,27,7,3]
	if not zynswitch_pin: zynswitch_pin=[107,105,106,104]
	select_ctrl=3
# Desktop Development & Emulation
elif wiring_layout=="EMULATOR":
	if not zyncoder_pin_a: zyncoder_pin_a=[4,5,6,7]
	if not zyncoder_pin_b: zyncoder_pin_b=[8,9,10,11]
	if not zynswitch_pin: zynswitch_pin=[0,1,2,3]
	select_ctrl=3
# No HW Controllers => Dummy Controllers
elif wiring_layout=="DUMMIES":
	if not zyncoder_pin_a: zyncoder_pin_a=[0,0,0,0]
	if not zyncoder_pin_b: zyncoder_pin_b=[0,0,0,0]
	if not zynswitch_pin: zynswitch_pin=[0,0,0,0]
	select_ctrl=3
elif wiring_layout=="CUSTOM":
	select_ctrl=3
# Default to DUMMIES
else:
	if not zyncoder_pin_a: zyncoder_pin_a=[0,0,0,0]
	if not zyncoder_pin_b: zyncoder_pin_b=[0,0,0,0]
	if not zynswitch_pin: zynswitch_pin=[0,0,0,0]
	select_ctrl=3

# Print Wiring Layout
logging.debug("ZYNCODER A: %s" % zyncoder_pin_a)
logging.debug("ZYNCODER B: %s" % zyncoder_pin_b)
logging.debug("SWITCHES layout: %s" % zynswitch_pin)

#------------------------------------------------------------------------------
# UI Geometric Parameters
#------------------------------------------------------------------------------

# Screen Size => Autodetect if None
if os.environ.get('DISPLAY_WIDTH'):
	display_width=int(os.environ.get('DISPLAY_WIDTH'))
	ctrl_width=int(display_width/4)
else:
	display_width=None

if os.environ.get('DISPLAY_HEIGHT'):
	display_height=int(os.environ.get('DISPLAY_HEIGHT'))
	topbar_height=int(display_height/10)
	ctrl_height=int((display_height-topbar_height)/2)
else:
	display_height=None

# Controller Positions
ctrl_pos=[
	(1,0,"nw"),
	(2,0,"sw"),
	(1,2,"ne"),
	(2,2,"se")
]

#------------------------------------------------------------------------------
# UI Color Parameters
#------------------------------------------------------------------------------

color_bg=os.environ.get('ZYNTHIAN_UI_COLOR_BG',"#000000")
color_tx=os.environ.get('ZYNTHIAN_UI_COLOR_TX',"#ffffff")
color_on=os.environ.get('ZYNTHIAN_UI_COLOR_ON',"#ff0000")
color_panel_bg=os.environ.get('ZYNTHIAN_UI_COLOR_PANEL_BG',"#3a424d")

# Color Scheme
color_panel_bd=color_bg
color_panel_tx=color_tx
color_header_bg=color_bg
color_header_tx=color_tx
color_ctrl_bg_off="#5a626d"
color_ctrl_bg_on=color_on
color_ctrl_tx=color_tx
color_ctrl_tx_off="#e0e0e0"

#------------------------------------------------------------------------------
# UI Font Parameters
#------------------------------------------------------------------------------

font_family=os.environ.get('ZYNTHIAN_UI_FONT_FAMILY',"Audiowide")
#font_family="Helvetica" #=> the original ;-)
#font_family="Economica" #=> small
#font_family="Orbitron" #=> Nice, but too strange
#font_family="Abel" #=> Quite interesting, also "Strait"

font_size=int(os.environ.get('ZYNTHIAN_UI_FONT_SIZE',10))

#------------------------------------------------------------------------------
# UI Cursor
#------------------------------------------------------------------------------

force_enable_cursor=int(os.environ.get('ZYNTHIAN_UI_ENABLE_CURSOR',False))

#------------------------------------------------------------------------------
# MIDI Configuration
#------------------------------------------------------------------------------

def set_midi_config():
	global master_midi_channel, master_midi_change_type
	global master_midi_program_change_up, master_midi_program_change_down
	global master_midi_program_base, master_midi_bank_change_ccnum
	global master_midi_bank_change_up, master_midi_bank_change_down
	global master_midi_bank_change_down_ccnum, master_midi_bank_base
	global preset_preload_noteon, midi_fine_tuning, midi_filter_rules
	global disabled_midi_in_ports, enabled_midi_out_ports

	master_midi_channel=int(os.environ.get('ZYNTHIAN_MIDI_MASTER_CHANNEL',16))

	master_midi_change_type=os.environ.get('ZYNTHIAN_MIDI_MASTER_CHANGE_TYPE',"Roland")

	master_midi_program_change_up=os.environ.get('ZYNTHIAN_MIDI_MASTER_PROGRAM_CHANGE_UP',"C#7F")
	master_midi_program_change_down=os.environ.get('ZYNTHIAN_MIDI_MASTER_PROGRAM_CHANGE_DOWN',"C#00")

	if master_midi_program_change_down=="C#00":
		master_midi_program_base=1
	else:
		master_midi_program_base=0

	#Use LSB Bank by default
	master_midi_bank_change_ccnum=os.environ.get('ZYNTHIAN_MIDI_MASTER_BANK_CHANGE_CCNUM',0x20)
	#Use MSB Bank by default
	#master_midi_bank_change_ccnum=os.environ.get('ZYNTHIAN_MIDI_MASTER_BANK_CHANGE_CCNUM',0x00)

	master_midi_bank_change_up=os.environ.get('ZYNTHIAN_MIDI_MASTER_BANK_CHANGE_UP',"B#207F")
	master_midi_bank_change_down=os.environ.get('ZYNTHIAN_MIDI_MASTER_BANK_CHANGE_DOWN',"B#2000")

	try:
		master_midi_bank_change_down_ccnum=int(master_midi_bank_change_down[2:4],16)
		if master_midi_bank_change_down_ccnum==master_midi_bank_change_ccnum:
			master_midi_bank_base=1
		else:
			master_midi_bank_base=0
	except:
		master_midi_bank_base=0

	#MIDI channels: 0-15
	if master_midi_channel>16:
		master_midi_channel=16
	master_midi_channel=master_midi_channel-1
	mmc_hex=hex(master_midi_channel)[2]

	#Calculate MIDI Sequences and convert to Integer
	master_midi_program_change_up=int('{:<06}'.format(master_midi_program_change_up.replace('#',mmc_hex)),16)
	master_midi_program_change_down=int('{:<06}'.format(master_midi_program_change_down.replace('#',mmc_hex)),16)
	master_midi_bank_change_up=int('{:<06}'.format(master_midi_bank_change_up.replace('#',mmc_hex)),16)
	master_midi_bank_change_down=int('{:<06}'.format(master_midi_bank_change_down.replace('#',mmc_hex)),16)

	preset_preload_noteon=int(os.environ.get('ZYNTHIAN_MIDI_PRESET_PRELOAD_NOTEON',1))
	midi_fine_tuning=int(os.environ.get('ZYNTHIAN_MIDI_FINE_TUNING',440))

	midi_filter_rules=os.environ.get('ZYNTHIAN_MIDI_FILTER_RULES',"")
	midi_filter_rules=midi_filter_rules.replace("\\n","\n")

	midi_ports=os.environ.get('ZYNTHIAN_MIDI_PORTS',"DISABLED_IN=\nENABLED_OUT=MIDI_out")
	midi_ports=midi_ports.replace("\\n","\n")
	disabled_midi_in_ports=zynconf.get_disabled_midi_in_ports(midi_ports)
	enabled_midi_out_ports=zynconf.get_enabled_midi_out_ports(midi_ports)

#Set MIDI config variables
set_midi_config()

#------------------------------------------------------------------------------
# Create & Configure Top Level window 
#------------------------------------------------------------------------------

top = tkinter.Tk()

# Try to autodetect screen size if not configured
try:
	if not display_width:
		display_width = top.winfo_screenwidth()
		ctrl_width=int(display_width/4)
	if not display_height:
		display_height = top.winfo_screenheight()
		topbar_height=int(display_height/10)
		ctrl_height=int((display_height-topbar_height)/2)
except:
	logging.warning("Can't get screen size. Using default 320x240!")
	display_width = 320
	display_height = 240
	topbar_height=int(display_height/10)
	ctrl_width=int(display_width/4)
	ctrl_height=int((display_height-topbar_height)/2)

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
font_listbox=(font_family,int(1.0*font_size))
font_topbar=(font_family,int(1.1*font_size))

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
		break;
#for i in range(13):
#	loading_imgs.append(tkinter.PhotoImage(file="./img/zynthian_gui_loading.gif", format="gif -index "+str(i)))

#------------------------------------------------------------------------------
# Zynthian GUI variable
#------------------------------------------------------------------------------

zyngui=None

#------------------------------------------------------------------------------
