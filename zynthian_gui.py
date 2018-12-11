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
from os.path import isfile
from datetime import datetime
from threading  import Thread

# Zynthian specific modules
import zynconf
import zynautoconnect
from zyncoder import *
from zyncoder.zyncoder import lib_zyncoder, lib_zyncoder_init
from zyngine import zynthian_zcmidi
from zyngine import zynthian_midi_filter
from zyngui import zynthian_gui_config
from zyngui.zynthian_gui_controller import zynthian_gui_controller
from zyngui.zynthian_gui_selector import zynthian_gui_selector
from zyngui.zynthian_gui_admin import zynthian_gui_admin
from zyngui.zynthian_gui_info import zynthian_gui_info
from zyngui.zynthian_gui_snapshot import zynthian_gui_snapshot
from zyngui.zynthian_gui_layer import zynthian_gui_layer
from zyngui.zynthian_gui_layer_options import zynthian_gui_layer_options
from zyngui.zynthian_gui_engine import zynthian_gui_engine
from zyngui.zynthian_gui_midi_chan import zynthian_gui_midi_chan
from zyngui.zynthian_gui_transpose import zynthian_gui_transpose
from zyngui.zynthian_gui_audio_out import zynthian_gui_audio_out
from zyngui.zynthian_gui_bank import zynthian_gui_bank
from zyngui.zynthian_gui_preset import zynthian_gui_preset
from zyngui.zynthian_gui_control import zynthian_gui_control
from zyngui.zynthian_gui_control_xy import zynthian_gui_control_xy
from zyngui.zynthian_gui_midi_profile import zynthian_gui_midi_profile
from zyngui.zynthian_gui_audio_recorder import zynthian_gui_audio_recorder
from zyngui.zynthian_gui_midi_recorder import zynthian_gui_midi_recorder
from zyngui.zynthian_gui_zs3_learn import zynthian_gui_zs3_learn
from zyngui.zynthian_gui_confirm import zynthian_gui_confirm

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

	screens_sequence=("admin","layer","bank","preset","control")


	def __init__(self):
		self.zynmidi = None
		self.screens = {}
		self.active_screen = None
		self.modal_screen = None
		self.curlayer = None

		self.dtsw = {}
		self.polling = False

		self.loading = 0
		self.loading_thread = None
		self.zyncoder_thread = None
		self.zynread_wait_flag = False
		self.zynswitch_defered_event = None
		self.exit_flag = False
		self.exit_code = 0

		self.midi_learn_mode = False
		self.midi_learn_zctrl = None

		# Initialize Controllers (Rotary and Switches), MIDI and OSC
		try:
			global lib_zyncoder
			#Init Zyncoder Library
			lib_zyncoder_init()
			lib_zyncoder=zyncoder.get_lib_zyncoder()
			#Init MIDI subsystem
			self.init_midi()
			self.zynmidi=zynthian_zcmidi()
			#Set Master Volume to Max.
			lib_zyncoder.zynmidi_send_master_ccontrol_change(0x7,0xFF)
			#Init MIDI and Switches
			self.zynswitches_init()
		except Exception as e:
			logging.error("ERROR initializing GUI: %s" % e)


	def init_midi(self):
		try:
			global lib_zyncoder
			#Set Global Tuning
			self.fine_tuning_freq=int(zynthian_gui_config.midi_fine_tuning)
			lib_zyncoder.set_midi_filter_tuning_freq(self.fine_tuning_freq)
			#Set MIDI Master Channel
			lib_zyncoder.set_midi_master_chan(zynthian_gui_config.master_midi_channel)
			#Setup MIDI filter rules
			zynthian_midi_filter.MidiFilterScript(zynthian_gui_config.midi_filter_rules)
		except Exception as e:
			logging.error("ERROR initializing MIDI : %s" % e)


	def reload_midi_config(self):
		zynconf.load_config()
		midi_profile_fpath=os.environ.get("ZYNTHIAN_SCRIPT_MIDI_PROFILE")
		if midi_profile_fpath:
			zynconf.load_config(True,midi_profile_fpath)
			zynthian_gui_config.set_midi_config()
			self.init_midi()


	def start(self):
		# Create initial GUI Screens
		self.screens['admin']=zynthian_gui_admin()
		self.screens['info']=zynthian_gui_info()
		self.screens['snapshot']=zynthian_gui_snapshot()
		self.screens['layer']=zynthian_gui_layer()
		self.screens['layer_options']=zynthian_gui_layer_options()
		self.screens['engine']=zynthian_gui_engine()
		self.screens['midi_chan']=zynthian_gui_midi_chan()
		self.screens['transpose']=zynthian_gui_transpose()
		self.screens['audio_out']=zynthian_gui_audio_out()
		self.screens['bank']=zynthian_gui_bank()
		self.screens['preset']=zynthian_gui_preset()
		self.screens['control']=zynthian_gui_control()
		self.screens['control_xy']=zynthian_gui_control_xy()
		self.screens['midi_profile']=zynthian_gui_midi_profile()
		self.screens['audio_recorder']=zynthian_gui_audio_recorder()
		self.screens['midi_recorder']=zynthian_gui_midi_recorder()
		self.screens['zs3_learn']=zynthian_gui_zs3_learn()
		self.screens['confirm']=zynthian_gui_confirm()
		# Show initial screen => Channel list
		self.show_screen('layer')
		# Try to load "default snapshot" or show "load snapshot" popup
		default_snapshot_fpath=os.environ.get('ZYNTHIAN_MY_DATA_DIR',"/zynthian/zynthian-my-data") + "/snapshots/default.zss"
		if not isfile(default_snapshot_fpath) or not self.screens['layer'].load_snapshot(default_snapshot_fpath):
			self.load_snapshot(autoclose=True)
		# Start polling threads
		self.start_polling()
		self.start_loading_thread()
		self.start_zyncoder_thread()


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


	def show_confirm(self, text, callback=None, cb_params=None):
		self.modal_screen='confirm'
		self.screens['confirm'].show(text, callback, cb_params)
		self.hide_screens(exclude='confirm')


	def show_info(self, text, tms=None):
		self.modal_screen='info'
		self.screens['info'].show(text)
		self.hide_screens(exclude='info')
		if tms:
			zynthian_gui_config.top.after(tms, self.hide_info)


	def add_info(self, text, tags=None):
		self.screens['info'].add(text,tags)


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


	def enter_midi_learn(self):
		self.midi_learn_mode = True
		self.midi_learn_zctrl = None
		self.screens['control'].refresh_midi_bind()
		self.show_modal('zs3_learn')


	def exit_midi_learn(self):
		self.midi_learn_mode = False
		self.midi_learn_zctrl = None
		self.show_screen('control')


	def show_control_xy(self, xctrl, yctrl):
		self.modal_screen='control_xy'
		self.screens['control_xy'].set_controllers(xctrl, yctrl)
		self.screens['control_xy'].show()
		self.hide_screens(exclude='control_xy')
		self.active_screen='control'
		self.screens['control'].set_mode_control()
		logging.debug("SHOW CONTROL-XY => %s, %s" % (xctrl.symbol, yctrl.symbol))


	def set_curlayer(self, layer):
		if layer is not None:
			self.start_loading()
			self.curlayer=layer
			self.screens['bank'].fill_list()
			self.screens['preset'].fill_list()
			self.screens['control'].fill_list()
			self.set_active_channel()
			self.stop_loading()
		else:
			self.curlayer=None


	#If "MIDI Single Active Channel" mode is enabled, set MIDI Active Channel to layer's one
	def set_active_channel(self):
		active_chan=-1

		if self.curlayer and zynthian_gui_config.midi_single_active_channel:
			active_chan=self.curlayer.get_midi_chan()
			if active_chan is not None:
				cur_active_chan=lib_zyncoder.get_midi_active_chan()
				if cur_active_chan==active_chan:
					return
				else:
					logging.debug("ACTIVE CHAN: {} => {}".format(cur_active_chan,active_chan))
					if cur_active_chan>=0:
						self.all_notes_off_chan(cur_active_chan)
			else:
				active_chan=-1

		lib_zyncoder.set_midi_active_chan(active_chan)
		self.zynswitches_midi_setup(active_chan)


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
			logging.info("ZYNSWITCHES INIT...")
			for i,pin in enumerate(zynthian_gui_config.zynswitch_pin):
				self.dtsw[i]=ts
				lib_zyncoder.setup_zynswitch(i,pin)
				logging.info("SETUP ZYNSWITCH {} => pin {}".format(i, pin))


	def zynswitches_midi_setup(self, midi_chan):
		logging.info("SWITCHES MIDI SETUP...")

		#Configure 8th zynswitch as Sustain Pedal CC
		lib_zyncoder.setup_zynswitch_midi(7, midi_chan, 64)
		logging.info("SETUP MIDI ZYNSWITCH {} => CH#{}, CC#{} (Sustain Pedal)".format(7, midi_chan, 64))


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

		# Standard 4 ZynSwitches
		if i==0:
			pass

		elif i==1:
			self.show_screen('admin')

		elif i==2:
			pass

		elif i==3:
			self.screens['admin'].power_off()

		# Extra ZynSwitches (AllInOne)
		elif i==4:
			self.all_sounds_off()

		elif i==5:
			pass

		elif i==6:
			pass

		elif i==7:
			pass

		self.stop_loading()


	def zynswitch_bold(self,i):
		logging.info('Bold Switch '+str(i))
		self.start_loading()

		# Standard 4 ZynSwitches
		if i==0:
			if self.active_screen=='layer':
				self.all_sounds_off()
				if self.curlayer is not None:
					self.show_screen('control')
			else:
				self.show_screen('layer')

		elif i==1:
			if self.curlayer is not None:
				if self.active_screen=='preset':
					if self.curlayer.preset_info is not None:
						self.screens['preset'].back_action()
						self.show_screen('control')
					else:
						self.show_screen('bank')
				elif self.active_screen!='bank':
					self.show_screen('bank')
				else:
					self.show_screen('admin')
			else:
				self.show_screen('admin')

		elif i==2:
			if self.modal_screen=='snapshot':
				self.screens['snapshot'].next()
			elif self.active_screen=='control' and self.screens['control'].mode=='control':
				self.load_snapshot()
			else:
				self.save_snapshot()

		elif i==3:
			if self.active_screen=='layer' and self.screens['layer'].get_layer_selected() is not None:
				self.show_modal('layer_options')
			else:
				self.screens[self.active_screen].switch_select()

		# Extra ZynSwitches (AllInOne)
		elif i==4:
			self.all_sounds_off()

		elif i==5:
			pass

		elif i==6:
			pass

		elif i==7:
			pass

		self.stop_loading()


	def zynswitch_short(self,i):
		logging.info('Short Switch '+str(i))
		self.start_loading()

		# Standard 4 ZynSwitches
		if i==0:
			if self.active_screen=='control':
				if self.screens['layer'].get_num_layers()>1:
					logging.info("Next layer")
					self.screens['layer'].next()
					self.show_screen('control')
				else:
					self.show_screen('layer')
			elif self.active_screen=='layer':
				self.all_notes_off()
				if self.curlayer is not None:
					self.show_screen('control')
			else:
				self.zynswitch_bold(i)

		elif i==1:
			# If in MIDI-learn mode, back to instrument control
			if self.midi_learn_mode or self.midi_learn_zctrl:
				self.exit_midi_learn()
			# If in controller map selection, back to instrument control
			elif self.active_screen=='control' and self.screens['control'].mode=='select':
				self.screens['control'].set_mode_control()
			else:
				# If modal screen, back to active screen
				if self.modal_screen:
					if self.modal_screen=='info':
						self.screens['admin'].kill_command()
					screen_back=self.active_screen
					logging.debug("CLOSE MODAL => " + self.modal_screen)
				# If control xyselect mode active
				elif self.active_screen=='control' and self.screens['control'].xyselect_mode:
					screen_back='control'
					self.screens['control'].unset_xyselect_mode()
					logging.debug("DISABLE XYSELECT MODE")
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
			if self.modal_screen=='snapshot':
				self.screens['snapshot'].next()
			elif self.active_screen=='control' and self.screens['control'].mode=='control':
				if self.midi_learn_mode or self.midi_learn_zctrl:
					if self.modal_screen=='zs3_learn':
						self.show_screen('control')
					else:
						self.show_modal('zs3_learn')
				else:
					self.enter_midi_learn()
			else:
				self.load_snapshot()

		elif i==3:
			if self.modal_screen:
				self.screens[self.modal_screen].switch_select()
			elif self.active_screen=='control' and self.screens['control'].mode in ('control','xyselect'):
				self.screens['control'].next()
				logging.info("Next Control Screen")
			else:
				self.screens[self.active_screen].switch_select()

		# Extra ZynSwitches (AllInOne)
		elif i==4:
			self.all_notes_off()

		elif i==5:
			pass

		elif i==6:
			pass

		elif i==7:
			pass

		self.stop_loading()


	def zynswitch_double(self,i):
		self.dtsw[i]=datetime.now()
		for j in range(4):
			if j==i: continue
			if abs((self.dtsw[i]-self.dtsw[j]).total_seconds())<0.3:
				self.start_loading()
				dswstr=str(i)+'+'+str(j)
				logging.info('Double Switch '+dswstr)
				#self.show_control_xy(i,j)
				self.show_screen('control')
				self.screens['control'].set_xyselect_mode(i,j)
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
				self.zynswitch_long(event[1])
			elif event[0]=='X':
				self.zynswitch_X(event[1])
			elif event[0]=='Y':
				self.zynswitch_Y(event[1])


	#------------------------------------------------------------------
	# Threads
	#------------------------------------------------------------------


	def start_zyncoder_thread(self):
		if lib_zyncoder:
			self.zyncoder_thread=Thread(target=self.zyncoder_thread_task, args=())
			self.zyncoder_thread.daemon = True # thread dies with the program
			self.zyncoder_thread.start()


	def zyncoder_thread_task(self):
		while not self.exit_flag:
			self.zyncoder_read()
			self.zynmidi_read()
			sleep(0.04)
			if self.zynread_wait_flag:
				sleep(0.3)
				self.zynread_wait_flag=False


	def zyncoder_read(self):
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


	def zynmidi_read(self):
		try:
			while lib_zyncoder:
				ev=lib_zyncoder.read_zynmidi()
				if ev==0: break
				evtype = (ev & 0xF00000)>>20
				chan = (ev & 0x0F0000)>>16
				
				#logging.info("MIDI_UI MESSAGE: {}".format(hex(ev)))
				#logging.info("MIDI_UI MESSAGE DETAILS: {}, {}".format(chan,evtype))

				#Master MIDI Channel ...
				if chan==zynthian_gui_config.master_midi_channel:
					logging.info("MASTER MIDI MESSAGE: %s" % hex(ev))
					if ev==zynthian_gui_config.master_midi_program_change_up:
						logging.debug("PROGRAM CHANGE UP!")
						self.screens['snapshot'].midi_program_change_up()
					elif ev==zynthian_gui_config.master_midi_program_change_down:
						logging.debug("PROGRAM CHANGE DOWN!")
						self.screens['snapshot'].midi_program_change_down()
					elif ev==zynthian_gui_config.master_midi_bank_change_up:
						logging.debug("BANK CHANGE UP!")
						self.screens['snapshot'].midi_bank_change_up()
					elif ev==zynthian_gui_config.master_midi_bank_change_down:
						logging.debug("BANK CHANGE DOWN!")
						self.screens['snapshot'].midi_bank_change_down()
					elif evtype==0xC:
						pgm = ((ev & 0x7F00)>>8) - zynthian_gui_config.master_midi_program_base
						logging.debug("PROGRAM CHANGE %d" % pgm)
						self.screens['snapshot'].midi_program_change(pgm)
					elif evtype==0xB:
						ccnum=(ev & 0x7F00)>>8
						if ccnum==zynthian_gui_config.master_midi_bank_change_ccnum:
							bnk = (ev & 0x7F) - zynthian_gui_config.master_midi_bank_base
							logging.debug("BANK CHANGE %d" % bnk)
							self.screens['snapshot'].midi_bank_change(bnk)
						elif ccnum==120:
							self.all_sounds_off()
						elif ccnum==123:
							self.all_notes_off()

				#Program Change ...
				elif evtype==0xC:
					pgm = (ev & 0x7F00)>>8
					logging.info("MIDI PROGRAM CHANGE: CH{} => {}".format(chan,pgm))
	
					# SubSnapShot (ZS3) MIDI learn ...
					if self.midi_learn_mode and self.modal_screen=='zs3_learn':
						self.screens['layer'].save_midi_chan_zs3(chan, pgm)
						self.exit_midi_learn()

					# Set Preset or ZS3 (sub-snapshot), depending of config option
					else:
						if zynthian_gui_config.midi_prog_change_zs3:
							self.screens['layer'].set_midi_chan_zs3(chan, pgm)
						else:
							self.screens['layer'].set_midi_chan_preset(chan, pgm)

						if not self.modal_screen and self.curlayer and chan==self.curlayer.get_midi_chan():
							self.show_screen('control')

				#Note-On ...
				elif evtype==0x9:
					#Preload preset (note-on)
					if zynthian_gui_config.preset_preload_noteon and self.active_screen=='preset' and chan==self.curlayer.get_midi_chan():
						self.start_loading()
						self.screens['preset'].preselect_action()
						self.stop_loading()

				#Control Change ...
				elif evtype==0xB:
					ccnum=(ev & 0x7F00)>>8
					ccval=(ev & 0x007F)
					#logging.debug("MIDI CONTROL CHANGE: CH{}, CC{} => {}".format(chan,ccnum,ccval))
					# MIDI learn => If controller is CC-mapped, use MIDI-router learning
					if self.midi_learn_zctrl and self.midi_learn_zctrl.midi_cc:
						self.midi_learn_zctrl.cb_midi_learn(chan,ccnum)
						self.show_screen('control')
					# Try layer's zctrls
					else:
						self.screens['layer'].midi_control_change(chan,ccnum,ccval)

		except Exception as err:
			logging.error("zynthian_gui.zynmidi_read() => %s" % err)


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
		self.zyngine_refresh()


	def stop_polling(self):
		self.polling=False


	def after(self, msec, func):
		zynthian_gui_config.top.after(msec, func)


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
		logging.info("All Sounds Off!")
		for chan in range(16):
			self.zynmidi.set_midi_control(chan, 120, 0)


	def all_notes_off(self):
		logging.info("All Notes Off!")
		for chan in range(16):
			self.zynmidi.set_midi_control(chan, 123, 0)


	def all_sounds_off_chan(self, chan):
		logging.info("All Sounds Off for channel {}!".format(chan))
		self.zynmidi.set_midi_control(chan, 120, 0)


	def all_notes_off_chan(self, chan):
		logging.info("All Notes Off for channel {}!".format(chan))
		#self.zynmidi.set_midi_control(chan, 123, 0)
		for n in range(128):
			self.zynmidi.note_off(chan,n)


	#------------------------------------------------------------------
	# MIDI learning
	#------------------------------------------------------------------


	def set_midi_learn(self, zctrl):
		self.midi_learn_zctrl=zctrl
		lib_zyncoder.set_midi_learning_mode(1)
		self.screens['control'].refresh_midi_bind()


	def unset_midi_learn(self):
		self.midi_learn_zctrl=None
		lib_zyncoder.set_midi_learning_mode(0)
		self.screens['control'].refresh_midi_bind()


	#------------------------------------------------------------------
	# Autoconnect
	#------------------------------------------------------------------


	def zynautoconnect(self):
		zynautoconnect.autoconnect()


	def zynautoconnect_acquire_lock(self):
		#Get Mutex Lock
		zynautoconnect.acquire_lock()


	def zynautoconnect_release_lock(self):
		#Release Mutex Lock
		zynautoconnect.release_lock()


#------------------------------------------------------------------------------
# GUI & Synth Engine initialization
#------------------------------------------------------------------------------


zynthian_gui_config.zyngui=zyngui=zynthian_gui()
zyngui.start()
zynautoconnect.start()


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
