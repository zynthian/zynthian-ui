#!/usr/bin/python3
# -*- coding: utf-8 -*-
#******************************************************************************
# ZYNTHIAN PROJECT: Zynthian GUI
# 
# Main Class and Program for Zynthian GUI
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
import sys
import copy
import signal
import alsaseq
import logging
from time import sleep
from datetime import datetime
from threading  import Thread

# Zynthian specific modules
import zynautoconnect
from zyncoder import *
from zyncoder.zyncoder import lib_zyncoder, lib_zyncoder_init
from zyngine import zynthian_zcmidi
from zyngui import zynthian_gui_config
from zyngui.zynthian_gui_controller import zynthian_gui_controller
from zyngui.zynthian_gui_selector import zynthian_gui_selector
from zyngui.zynthian_gui_admin import zynthian_gui_admin
from zyngui.zynthian_gui_info import zynthian_gui_info
from zyngui.zynthian_gui_snapshot import zynthian_gui_snapshot
from zyngui.zynthian_gui_layer import zynthian_gui_layer
from zyngui.zynthian_gui_layer_options import zynthian_gui_layer_options
from zyngui.zynthian_gui_engine import zynthian_gui_engine
from zyngui.zynthian_gui_midich import zynthian_gui_midich
from zyngui.zynthian_gui_transpose import zynthian_gui_transpose
from zyngui.zynthian_gui_bank import zynthian_gui_bank
from zyngui.zynthian_gui_preset import zynthian_gui_preset
from zyngui.zynthian_gui_control import zynthian_gui_control
from zyngui.zynthian_gui_control_xy import zynthian_gui_control_xy
#from zyngui.zynthian_gui_control_osc_browser import zynthian_gui_osc_browser

#------------------------------------------------------------------------------
# Configure logging
#------------------------------------------------------------------------------

# Set root logging level
logging.basicConfig(stream=sys.stderr, level=zynthian_gui_config.log_level)

# Reduce log level for other modules
logging.getLogger("urllib3").setLevel(logging.WARNING)

#-------------------------------------------------------------------------------
# Zynthian Main GUI Class
#-------------------------------------------------------------------------------

class zynthian_gui:
	zynmidi=None
	screens={}
	active_screen=None
	modal_screen=None
	screens_sequence=("admin","layer","bank","preset","control")
	curlayer=None

	dtsw={}
	polling=False
	osc_target=None
	osc_server=None

	loading=0
	loading_thread=None
	zyncoder_thread=None
	zynread_wait_flag=False
	zynswitch_defered_event=None
	exit_flag=False
	exit_code=0

	def __init__(self):
		# Initialize Controllers (Rotary and Switches), MIDI and OSC
		try:
			global lib_zyncoder
			zyngine_osc_port=6693
			lib_zyncoder_init(zyngine_osc_port)
			lib_zyncoder=zyncoder.get_lib_zyncoder()
			lib_zyncoder.set_midi_filter_tuning_freq(zynthian_gui_config.master_midi_fine_tuning)
			self.zynmidi=zynthian_zcmidi()
			self.zynswitches_init()
		except Exception as e:
			logging.error("ERROR initializing GUI: %s" % e)

	def start(self):
		# Create initial GUI Screens
		self.screens['admin']=zynthian_gui_admin()
		self.screens['info']=zynthian_gui_info()
		self.screens['snapshot']=zynthian_gui_snapshot()
		self.screens['layer']=zynthian_gui_layer()
		self.screens['layer_options']=zynthian_gui_layer_options()
		self.screens['engine']=zynthian_gui_engine()
		self.screens['midich']=zynthian_gui_midich()
		self.screens['transpose']=zynthian_gui_transpose()
		self.screens['bank']=zynthian_gui_bank()
		self.screens['preset']=zynthian_gui_preset()
		self.screens['control']=zynthian_gui_control()
		self.screens['control_xy']=zynthian_gui_control_xy()
		# Show initial screen => Channel list
		self.show_screen('layer')
		# Start polling threads
		self.start_polling()
		self.start_loading_thread()
		self.start_zyncoder_thread()
		# Try to load "default snapshot" or show "load snapshot" popup
		default_snapshot_fpath=os.getcwd()+"/my-data/snapshots/default.zss"
		if not self.screens['layer'].load_snapshot(default_snapshot_fpath):
			self.load_snapshot(autoclose=True)

	def stop(self):
		self.screens['layer'].reset()

	def hide_screens(self,exclude=None):
		if not exclude:
			exclude=self.active_screen
		for screen_name,screen in self.screens.items():
			if screen_name!=exclude:
				screen.hide();

	def show_active_screen(self):
		self.screens[self.active_screen].show()
		self.hide_screens()
		self.modal_screen=None

	def refresh_screen(self):
		if self.active_screen=='preset' and len(self.curlayer.preset_list)<=1:
			self.active_screen='control'
		self.show_active_screen()

	def show_screen(self,screen=None):
		if screen:
			self.active_screen=screen
		self.show_active_screen()

	def show_modal(self, screen):
		self.modal_screen=screen
		self.screens[screen].show()
		self.hide_screens(exclude=screen)

	def show_info(self, text, tms=None):
		self.modal_screen='info'
		self.screens['info'].show(text)
		self.hide_screens(exclude='info')
		if tms:
			zynthian_gui_config.top.after(tms, self.hide_info)

	def add_info(self, text):
		self.screens['info'].add(text)

	def hide_info_timer(self, tms=3000):
		zynthian_gui_config.top.after(tms, self.hide_info)

	def hide_info(self):
		self.screens['info'].hide()
		self.show_screen()

	def load_snapshot(self, autoclose=False):
		self.modal_screen='snapshot'
		self.screens['snapshot'].load()
		if not autoclose or len(self.screens['snapshot'].list_data)>1:
			self.hide_screens(exclude='snapshot')
		else:
			self.show_screen('layer')

	def save_snapshot(self):
		self.modal_screen='snapshot'
		self.screens['snapshot'].save()
		self.hide_screens(exclude='snapshot')

	def show_control_xy(self, xctrl, yctrl):
		self.modal_screen='control_xy'
		self.screens['control_xy'].set_controllers(xctrl, yctrl)
		self.screens['control_xy'].show()
		self.hide_screens(exclude='control_xy')
		self.active_screen='control'
		self.screens['control'].set_mode_control()
		logging.debug("SHOW CONTROL-XY => %d, %d" % (xctrl, yctrl))

	def set_curlayer(self, layer):
		self.start_loading()
		self.curlayer=layer
		self.screens['bank'].fill_list()
		self.screens['preset'].fill_list()
		self.screens['control'].fill_list()
		self.stop_loading()

	def get_curlayer_wait(self):
		#Try until layer is ready
		for j in range(100):
			if self.curlayer:
				return self.curlayer
			else:
				sleep(0.1)

	# -------------------------------------------------------------------
	# Switches
	# -------------------------------------------------------------------

	# Init GPIO Switches
	def zynswitches_init(self):
		if lib_zyncoder:
			ts=datetime.now()
			logging.info("SWITCHES INIT...")
			for i,pin in enumerate(zynthian_gui_config.zynswitch_pin):
				self.dtsw[i]=ts
				lib_zyncoder.setup_zynswitch(i,pin)
				logging.info("SETUP GPIO SWITCH "+str(i)+" => "+str(pin))

	def zynswitches(self):
		if lib_zyncoder:
			for i in range(len(zynthian_gui_config.zynswitch_pin)):
				dtus=lib_zyncoder.get_zynswitch_dtus(i)
				if dtus>0:
					#print("Switch "+str(i)+" dtus="+str(dtus))
					if dtus>300000:
						if dtus>2000000:
							self.zynswitch_long(i)
							return
						# Double switches must be bold!!! => by now ...
						if self.zynswitch_double(i):
							return
						self.zynswitch_bold(i)
						return
					self.zynswitch_short(i)

	def zynswitch_long(self,i):
		logging.info('Looooooooong Switch '+str(i))
		self.start_loading()
		if i==0:
			pass
		elif i==1:
			self.show_screen('admin')
		elif i==2:
			pass
		elif i==3:
			self.screens['admin'].power_off()
		self.stop_loading()

	def zynswitch_bold(self,i):
		logging.info('Bold Switch '+str(i))
		self.start_loading()
		if i==0:
			if self.active_screen!='layer':
				self.show_screen('layer')
		elif i==1:
			if self.active_screen=='preset':
				if self.curlayer.preset_info is not None:
					self.screens['preset'].back_action()
					self.show_screen('control')
				else:
					self.show_screen('bank')
			elif self.active_screen!='bank':
				self.show_screen('bank')
		elif i==2:
			self.save_snapshot()
		elif i==3:
			if self.active_screen=='layer':
				self.show_modal('layer_options')
			else:
				self.screens[self.active_screen].switch_select()
		self.stop_loading()
		
	def zynswitch_short(self,i):
		logging.info('Short Switch '+str(i))
		self.start_loading()
		if i==0:
			if self.active_screen=='control':
				if self.screens['layer'].get_num_layers()>1:
					logging.info("Next layer")
					self.screens['layer'].next()
					self.show_screen('control')
				else:
					self.show_screen('layer')
			else:
				self.zynswitch_bold(i)
		elif i==1:
			# If in controller map selection, back to instrument control
			if self.active_screen=='control' and self.screens['control'].mode=='select':
				self.screens['control'].set_mode_control()
			else:
				# If modal screen, back to active screen
				if self.modal_screen:
					if self.modal_screen=='info':
						self.screens['admin'].kill_command()
					screen_back=self.active_screen
					logging.debug("CLOSE MODAL => " + self.modal_screen)
				# Else, go back to screen-1
				else:
					j=self.screens_sequence.index(self.active_screen)-1
					if j<0: j=1
					screen_back=self.screens_sequence[j]
				# If there is only one preset, go back to bank selection
				if screen_back=='preset' and len(self.curlayer.preset_list)<=1:
					screen_back='bank'
				# If there is only one bank, go back to layer selection
				if screen_back=='bank' and len(self.curlayer.bank_list)<=1:
					screen_back='layer'
				logging.debug("BACK TO SCREEN => "+screen_back)
				self.show_screen(screen_back)
		elif i==2:
			if self.modal_screen!='snapshot':
				self.load_snapshot()
			else:
				self.screens['snapshot'].next()
		elif i==3:
			if self.modal_screen:
				self.screens[self.modal_screen].switch_select()
			elif self.active_screen=='control' and self.screens['control'].mode=='control':
				self.screens['control'].next()
				logging.info("Next Control Screen")
			else:
				self.screens[self.active_screen].switch_select()
		self.stop_loading()

	def zynswitch_double(self,i):
		self.dtsw[i]=datetime.now()
		for j in range(4):
			if j==i: continue
			if abs((self.dtsw[i]-self.dtsw[j]).total_seconds())<0.3:
				self.start_loading()
				dswstr=str(i)+'+'+str(j)
				logging.info('Double Switch '+dswstr)
				self.show_control_xy(i,j)
				self.stop_loading()
				return True

	def zynswitch_X(self,i):
		logging.info('X Switch %d' % i)
		if self.active_screen=='control' and self.screens['control'].mode=='control':
			self.screens['control'].midi_learn(i)

	def zynswitch_Y(self,i):
		logging.info('Y Switch %d' % i)
		if self.active_screen=='control' and self.screens['control'].mode=='control':
			self.screens['control'].midi_unlearn(i)

	#------------------------------------------------------------------
	# Switch Defered Event
	#------------------------------------------------------------------

	def zynswitch_defered(self, t, i):
		self.zynswitch_defered_event=(t,i)

	def zynswitch_defered_exec(self):
		if self.zynswitch_defered_event is not None:
			#Copy event and clean variable
			event=copy.deepcopy(self.zynswitch_defered_event)
			self.zynswitch_defered_event=None
			#Process event
			if event[0]=='S':
				self.zynswitch_short(event[1])
			elif event[0]=='B':
				self.zynswitch_bold(event[1])
			elif event[0]=='L':
				self.zynswitch_long([1])
			elif event[0]=='X':
				self.zynswitch_X(event[1])
			elif event[0]=='Y':
				self.zynswitch_Y(event[1])

	#------------------------------------------------------------------
	# Threads
	#------------------------------------------------------------------

	def start_zyncoder_thread(self):
		if lib_zyncoder:
			self.zyncoder_thread=Thread(target=self.zyncoder_read, args=())
			self.zyncoder_thread.daemon = True # thread dies with the program
			self.zyncoder_thread.start()

	def zyncoder_read(self):
		while not self.exit_flag:
			if not self.loading: #TODO Es necesario???
				try:
					if self.modal_screen:
						self.screens[self.modal_screen].zyncoder_read()
					else:
						self.screens[self.active_screen].zyncoder_read()
					self.zynswitch_defered_exec()
					self.zynswitches()
				except Exception as err:
					if zynthian_gui_config.raise_exceptions:
						raise err
					else:
						logging.warning("zynthian_gui.zyncoder_read() => %s" % err)
			sleep(0.04)
			if self.zynread_wait_flag:
				sleep(0.3)
				self.zynread_wait_flag=False

	def start_loading_thread(self):
		self.loading_thread=Thread(target=self.loading_refresh, args=())
		self.loading_thread.daemon = True # thread dies with the program
		self.loading_thread.start()

	def start_loading(self):
		self.loading=self.loading+1
		if self.loading<1: self.loading=1
		#logging.debug("START LOADING %d" % self.loading)

	def stop_loading(self):
		self.loading=self.loading-1
		if self.loading<0: self.loading=0
		#logging.debug("STOP LOADING %d" % self.loading)

	def reset_loading(self):
		self.loading=0

	def loading_refresh(self):
		while not self.exit_flag:
			try:
				if self.modal_screen:
					self.screens[self.modal_screen].refresh_loading()
				else:
					self.screens[self.active_screen].refresh_loading()
			except Exception as err:
				logging.error("zynthian_gui.loading_refresh() => %s" % err)
			sleep(0.1)

	def exit(self, code=0):
		self.exit_flag=True
		self.exit_code=code

	#------------------------------------------------------------------
	# Polling
	#------------------------------------------------------------------
	
	def start_polling(self):
		self.polling=True
		self.zynmidi_read()
		self.zyngine_refresh()

	def stop_polling(self):
		self.polling=False

	def after(self, msec, func):
		zynthian_gui_config.top.after(msec, func)

	def zynmidi_read(self):
		try:
			while lib_zyncoder:
				ev=lib_zyncoder.read_zynmidi()
				if ev==0: break
				evtype = (ev & 0xF0)>>4
				chan = ev & 0x0F
				if chan==zynthian_gui_config.master_midi_channel:
					if  evtype==0xC:
						pgm = (ev & 0xF00)>>8
						logging.info("MASTER MIDI PROGRAM CHANGE %s" % pgm)
						#TODO => MASTER MIDI PROGRAM CHANGE AND OTHERS!
				elif evtype==0xC:
					pgm = (ev & 0xF00)>>8
					logging.info("MIDI PROGRAM CHANGE %s, CH%s" % (pgm,chan))
					self.screens['layer'].set_midi_chan_preset(chan, pgm)
					if not self.modal_screen and chan==self.curlayer.get_midi_chan():
						self.show_screen('control')
				elif evtype==0x9:
					#Preload preset
					if zynthian_gui_config.preset_preload_noteon and self.active_screen=='preset' and chan==self.curlayer.get_midi_chan():
						self.screens[self.active_screen].preselect_action()
		except Exception as err:
			logging.error("zynthian_gui.zynmidi_read() => %s" % err)
		if self.polling:
			zynthian_gui_config.top.after(40, self.zynmidi_read)

	def zyngine_refresh(self):
		try:
			if self.exit_flag:
				self.stop()
				sys.exit(self.exit_code)
			elif self.curlayer and not self.loading:
				self.curlayer.refresh()
		except Exception as err:
			if zynthian_gui_config.raise_exceptions:
				raise err
			else:
				logging.error("zynthian_gui.zyngine_refresh() => %s" % err)
		if self.polling:
			zynthian_gui_config.top.after(160, self.zyngine_refresh)

	#------------------------------------------------------------------
	# OSC callbacks
	#------------------------------------------------------------------

	def cb_osc_bank_view(self, path, args):
		pass

	def cb_osc_ctrl(self, path, args):
		#print ("OSC CTRL: " + path + " => "+str(args[0]))
		if path in self.screens['control'].zgui_controllers_map.keys():
			self.screens['control'].zgui_controllers_map[path].set_init_value(args[0])

	#------------------------------------------------------------------
	# All Sounds Off => PANIC!
	#------------------------------------------------------------------

	def all_sounds_off(self):
		for chan in range(16):
			self.zynmidi.set_midi_control(chan, 120, 0)


#------------------------------------------------------------------------------
# GUI & Synth Engine initialization
#------------------------------------------------------------------------------

zynautoconnect.start()
zynthian_gui_config.zyngui=zyngui=zynthian_gui()
zyngui.start()

#------------------------------------------------------------------------------
# Reparent Top Window using GTK XEmbed protocol features
#------------------------------------------------------------------------------

def flushflush():
	for i in range(1000):
		print("FLUSHFLUSHFLUSHFLUSHFLUSHFLUSHFLUSH")
	zynthian_gui_config.top.after(200, flushflush)

if zynthian_gui_config.wiring_layout=="EMULATOR":
	top_xid=zynthian_gui_config.top.winfo_id()
	print("Zynthian GUI XID: "+str(top_xid))
	if len(sys.argv)>1:
		parent_xid=int(sys.argv[1])
		print("Parent XID: "+str(parent_xid))
		zynthian_gui_config.top.geometry('-10000-10000')
		zynthian_gui_config.top.overrideredirect(True)
		zynthian_gui_config.top.wm_withdraw()
		flushflush()
		zynthian_gui_config.top.after(1000, zynthian_gui_config.top.wm_deiconify)

#------------------------------------------------------------------------------
# Catch SIGTERM
#------------------------------------------------------------------------------

def sigterm_handler(_signo, _stack_frame):
	logging.info("Catch SIGTERM ...")
	zyngui.stop()
	zynthian_gui_config.top.destroy()

signal.signal(signal.SIGTERM, sigterm_handler)

#------------------------------------------------------------------------------
# TKinter Main Loop
#------------------------------------------------------------------------------

zynthian_gui_config.top.mainloop()
#zyngui.stop()

#------------------------------------------------------------------------------
