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
import liblo
import signal
#import psutil
#import alsaseq
import logging
from time import sleep
from os.path import isfile
from datetime import datetime
from threading  import Thread
from subprocess import check_output

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

	screens_sequence = ("admin","layer","bank","preset","control")

	note2cuia = {
		"0": "POWER_OFF",
		"1": "REBOOT",
		"2": "RESTART_UI",
		"3": "RELOAD_MIDI_CONFIG",

		"10": "ALL_NOTES_OFF",
		"11": "ALL_SOUNDS_OFF",
		"12": "ALL_OFF",

		"51": "SELECT",
		"52": "SELECT_DOWN", 
		"53": "SELECT_UP",

		"64": "SWITCH_BACK_SHORT",
		"63": "SWITCH_BACK_BOLD",
		"62": "SWITCH_BACK_LONG",
		"65": "SWITCH_SELECT_SHORT",
		"66": "SWITCH_SELECT_BOLD",
		"67": "SWITCH_SELECT_LONG",
		"60": "SWITCH_LAYER_SHORT",
		"61": "SWITCH_LAYER_BOLD",
		"59": "SWITCH_LAYER_LONG",
		"71": "SWITCH_SNAPSHOT_SHORT",
		"72": "SWITCH_SNAPSHOT_BOLD",
		"73": "SWITCH_SNAPSHOT_LONG"
	}

	def __init__(self):
		self.zynmidi = None
		self.screens = {}
		self.active_screen = None
		self.modal_screen = None
		self.curlayer = None

		self.dtsw = []
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

		self.status_info = {}
		self.status_counter = 0

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
			#Init OSC
			self.osc_init()
		except Exception as e:
			logging.error("ERROR initializing GUI: %s" % e)


	# ---------------------------------------------------------------------------
	# MIDI Router Init & Config
	# ---------------------------------------------------------------------------


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
		midi_profile_fpath=zynconf.get_midi_config_fpath()
		if midi_profile_fpath:
			zynconf.load_config(True,midi_profile_fpath)
			zynthian_gui_config.set_midi_config()
			self.init_midi()


	# ---------------------------------------------------------------------------
	# OSC Management
	# ---------------------------------------------------------------------------


	def osc_init(self, port=1370, proto=liblo.UDP):
		try:
			self.osc_server=liblo.Server(port,proto)
			self.osc_server_port=self.osc_server.get_port()
			self.osc_server_url=liblo.Address('localhost',self.osc_server_port,proto).get_url()
			logging.info("ZYNTHIAN-UI OSC server running in port {}".format(self.osc_server_port))
			self.osc_server.add_method(None, None, self.osc_cb_all)
			#self.osc_server.start()
		except liblo.AddressError as err:
			logging.error("ZYNTHIAN-UI OSC Server can't be initialized: {}".format(err))


	def osc_end(self):
		if self.osc_server:
			try:
				#self.osc_server.stop()
				logging.info("ZYNTHIAN-UI OSC server stopped")
			except Exception as err:
				logging.error("Can't stop ZYNTHIAN-UI OSC server => %s" % err)
			self.stop_loading()


	def osc_receive(self):
		while self.osc_server.recv(0):
			pass


	#@liblo.make_method("RELOAD_MIDI_CONFIG", None)
	#@liblo.make_method(None, None)
	def osc_cb_all(self, path, args, types, src):
		logging.info("OSC MESSAGE '%s' from '%s'" % (path, src.url))
		self.callable_ui_action(path, args)
		#for a, t in zip(args, types):
		#	logging.debug("argument of type '%s': %s" % (t, a))


	# ---------------------------------------------------------------------------
	# GUI Core Management
	# ---------------------------------------------------------------------------


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

		# Init Auto-connector
		zynautoconnect.start()

		# Load an initial snapshot?
		snapshot_loaded=False
		if zynthian_gui_config.restore_last_state:
			# Try to load "last_state" snapshot ...
			last_state_snapshot_fpath=self.screens['snapshot'].last_state_snapshot_fpath
			if isfile(last_state_snapshot_fpath):
				snapshot_loaded=self.screens['layer'].load_snapshot(last_state_snapshot_fpath)

		if not snapshot_loaded:
			# Try to load "default" snapshot ...
			default_snapshot_fpath=self.screens['snapshot'].default_snapshot_fpath
			if isfile(default_snapshot_fpath):
				snapshot_loaded=self.screens['layer'].load_snapshot(default_snapshot_fpath)

		if not snapshot_loaded:
			# Show "load snapshot" popup. Autoclose if no snapshots available ...
			self.load_snapshot(autoclose=True)

		# Start polling threads
		self.start_polling()
		self.start_loading_thread()
		self.start_zyncoder_thread()


	def stop(self):
		self.screens['layer'].reset()
		self.osc_end()


	def hide_screens(self,exclude=None):
		if not exclude:
			exclude=self.active_screen
		for screen_name,screen in self.screens.items():
			if screen_name!=exclude:
				screen.hide();


	def show_active_screen(self):
		if not self.active_screen:
			self.active_screen = "layer"
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


	def get_current_screen(self):
		if self.modal_screen:
			return self.screens[self.modal_screen]
		else:
			return self.screens[self.active_screen]


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
		if not autoclose or (self.screens['snapshot'].action=="LOAD" and len(self.screens['snapshot'].list_data)>1):
			self.hide_screens(exclude='snapshot')
		else:
			self.show_screen('layer')


	def save_snapshot(self):
		self.modal_screen='snapshot'
		self.screens['snapshot'].save()
		self.hide_screens(exclude='snapshot')


	def enter_midi_learn_mode(self):
		self.midi_learn_mode = True
		self.midi_learn_zctrl = None
		self.screens['control'].refresh_midi_bind()
		self.screens['control'].set_select_path()
		#self.show_modal('zs3_learn')


	def exit_midi_learn_mode(self):
		self.midi_learn_mode = False
		self.midi_learn_zctrl = None
		lib_zyncoder.set_midi_learning_mode(0)
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
		curlayer_chan = -1
		active_chan = -1

		if self.curlayer:
			curlayer_chan = self.curlayer.get_midi_chan()
			if curlayer_chan is None:
				curlayer_chan = -1
			elif zynthian_gui_config.midi_single_active_channel:
				active_chan = curlayer_chan 
				cur_active_chan = lib_zyncoder.get_midi_active_chan()
				if cur_active_chan==active_chan:
					return
				else:
					logging.debug("ACTIVE CHAN: {} => {}".format(cur_active_chan, active_chan))
					if cur_active_chan>=0:
						self.all_notes_off_chan(cur_active_chan)

		lib_zyncoder.set_midi_active_chan(active_chan)
		self.zynswitches_midi_setup(curlayer_chan)


	def get_curlayer_wait(self):
		#Try until layer is ready
		for j in range(100):
			if self.curlayer:
				return self.curlayer
			else:
				sleep(0.1)


	# -------------------------------------------------------------------
	# Callable UI Actions
	# -------------------------------------------------------------------

	def callable_ui_action(self, cuia, params=None):
		if cuia == "POWER_OFF":
			self.screens['admin'].power_off_confirmed()

		elif cuia == "REBOOT":
			self.screens['admin'].reboot_confirmed()

		elif cuia == "RESTART_UI":
			self.screens['admin'].restart_gui()

		elif cuia == "RELOAD_MIDI_CONFIG":
			self.reload_midi_config()

		elif cuia == "ALL_NOTES_OFF":
			self.all_notes_off()
			
		elif cuia == "ALL_SOUNDS_OFF":
			self.all_notes_off()
			self.all_sounds_off()

		elif cuia == "ALL_OFF":
			self.all_notes_off()
			self.all_sounds_off()
			sleep(0.1)
			self.raw_all_notes_off()

		elif cuia == "SELECT":
			try:
				self.get_current_screen().select(params[0])
			except:
				pass

		elif cuia == "SELECT_UP":
			try:
				self.get_current_screen().select_up()
			except:
				pass

		elif cuia == "SELECT_DOWN":
			try:
				self.get_current_screen().select_down()
			except:
				pass

		elif cuia == "SWITCH_LAYER_SHORT":
			self.zynswitch_short(0)

		elif cuia == "SWITCH_LAYER_BOLD":
			self.zynswitch_bold(0)

		elif cuia == "SWITCH_LAYER_LONG":
			self.zynswitch_long(0)

		elif cuia == "SWITCH_BACK_SHORT":
			self.zynswitch_short(1)

		elif cuia == "SWITCH_BACK_BOLD":
			self.zynswitch_bold(1)

		elif cuia == "SWITCH_BACK_LONG":
			self.zynswitch_long(1)

		elif cuia == "SWITCH_SNAPSHOT_SHORT":
			self.zynswitch_short(2)

		elif cuia == "SWITCH_SNAPSHOT_BOLD":
			self.zynswitch_bold(2)

		elif cuia == "SWITCH_SNAPSHOT_LONG":
			self.zynswitch_long(2)

		elif cuia == "SWITCH_SELECT_SHORT":
			self.zynswitch_short(3)

		elif cuia == "SWITCH_SELECT_BOLD":
			self.zynswitch_bold(3)

		elif cuia == "SWITCH_SELECT_LONG":
			self.zynswitch_long(3)


	def custom_switch_ui_action(self, i, t):
		try:
			cuia = zynthian_gui_config.custom_switch_ui_actions[i][t]
			self.callable_ui_action(cuia)
		except Exception as e:
			logging.warning(e)


	# -------------------------------------------------------------------
	# Switches
	# -------------------------------------------------------------------


	# Init GPIO Switches
	def zynswitches_init(self):
		if lib_zyncoder:
			ts=datetime.now()
			logging.info("ZYNSWITCHES INIT...")
			for i,pin in enumerate(zynthian_gui_config.zynswitch_pin):
				self.dtsw.append(ts)
				lib_zyncoder.setup_zynswitch(i,pin)
				logging.info("SETUP ZYNSWITCH {} => wpGPIO {}".format(i, pin))


	def zynswitches_midi_setup(self, midi_chan):
		if midi_chan>0:
			logging.info("SWITCHES MIDI SETUP...")

			for i in range(0, zynthian_gui_config.n_custom_switches):
				swi = 4 + i
				cc_num = zynthian_gui_config.custom_switch_midi_cc[i]
				if cc_num is not None:
					lib_zyncoder.setup_zynswitch_midi(swi, midi_chan, cc_num)
					logging.info("SETUP MIDI ZYNSWITCH {} => CH#{}, CC#{}".format(swi, midi_chan, cc_num))


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

		# Custom ZynSwitches
		elif i==4:
			self.custom_switch_ui_action(0, "L")

		elif i==5:
			self.custom_switch_ui_action(1, "L")

		elif i==6:
			self.custom_switch_ui_action(2, "L")

		elif i==7:
			self.custom_switch_ui_action(3, "L")

		self.stop_loading()


	def zynswitch_bold(self,i):
		logging.info('Bold Switch '+str(i))
		self.start_loading()

		# Standard 4 ZynSwitches
		if i==0:
			if self.active_screen=='layer':
				self.all_notes_off()
				self.all_sounds_off()
				if self.curlayer is not None:
					self.show_screen('control')
			else:
				self.show_screen('layer')

		elif i==1:
			screen_back = None
			# If modal screen ...
			if self.modal_screen:
				logging.debug("CLOSE MODAL => " + self.modal_screen)

				# Try to call modal back_action method:
				try:
					screen_back = self.screens[self.modal_screen].back_action()
				except:
					pass

			# If curlayer is set ...
			elif self.curlayer is not None:
				if self.active_screen=='control':
					if len(self.curlayer.bank_list)>1:
						screen_back = 'bank'
					else:
						screen_back = 'layer'

				elif self.active_screen=='preset':
					if self.curlayer.preset_info is not None:
						self.screens['preset'].restore_preset()
						screen_back = 'control'
					elif len(self.curlayer.bank_list)>1:
						screen_back = 'bank'
					else:
						screen_back = 'layer'

				elif self.active_screen=='bank':
					screen_back = 'admin'

				elif self.active_screen=='layer':
					screen_back = 'control'

				elif self.active_screen=='admin':
					screen_back = 'control'

			# Else, go to admin screen
			else:
				screen_back = 'admin'

			# Back to active screen by default ...
			if screen_back is None:
				screen_back = self.active_screen

			logging.debug("BACK TO SCREEN => {}".format(screen_back))
			self.show_screen(screen_back)


		elif i==2:
			if self.modal_screen=='snapshot':
				self.screens['snapshot'].next()
			elif self.active_screen=='control' and self.screens['control'].mode=='control':
				self.load_snapshot()
			else:
				self.save_snapshot()

		elif i==3:
			if self.modal_screen:
				self.screens[self.modal_screen].switch_select('B')
			else:
				self.screens[self.active_screen].switch_select('B')

		# Custom ZynSwitches
		elif i==4:
			self.custom_switch_ui_action(0, "B")

		elif i==5:
			self.custom_switch_ui_action(1, "B")

		elif i==6:
			self.custom_switch_ui_action(2, "B")

		elif i==7:
			self.custom_switch_ui_action(3, "B")

		self.stop_loading()


	def zynswitch_short(self,i):
		logging.info('Short Switch '+str(i))
		self.start_loading()

		# Standard 4 ZynSwitches
		if i==0:
			if self.active_screen=='control':
				if self.screens['layer'].get_num_root_layers()>1:
					logging.info("Next layer")
					self.screens['layer'].next()
					self.show_screen('control')
				else:
					self.show_screen('layer')

			elif self.active_screen=='layer':
				self.screens['layer'].toggle_show_all_layers()
				self.show_screen('layer')

			else:
				self.show_screen('layer')

		elif i==1:
			screen_back = None
			# If modal screen ...
			if self.modal_screen:
				logging.debug("CLOSE MODAL => " + self.modal_screen)

				# Try to call modal back_action method:
				try:
					screen_back = self.screens[self.modal_screen].back_action()
				except:
					pass

				# Back to active screen by default ...
				if screen_back is None:
					screen_back = self.active_screen

			else:
				try:
					screen_back = self.screens[self.active_screen].back_action()
				except:
					pass

				# Back to screen-1 by default ...
				if screen_back is None:
					j=self.screens_sequence.index(self.active_screen)-1
					if j<0: j=1
					screen_back=self.screens_sequence[j]

			# If there is only one preset, go back to bank selection
			if screen_back=='preset' and len(self.curlayer.preset_list)<=1:
				screen_back='bank'

			# If there is only one bank, go back to layer selection
			if screen_back=='bank' and len(self.curlayer.bank_list)<=1:
				screen_back='layer'

			if screen_back:
				logging.debug("BACK TO SCREEN => {}".format(screen_back))
				self.show_screen(screen_back)

		elif i==2:
			if self.modal_screen=='snapshot':
				self.screens['snapshot'].next()
			elif self.active_screen=='control' and self.screens['control'].mode=='control':
				if self.midi_learn_mode or self.midi_learn_zctrl:
					if self.modal_screen=='zs3_learn':
						self.show_screen('control')
					elif zynthian_gui_config.midi_prog_change_zs3:
						self.show_modal('zs3_learn')
				else:
					self.enter_midi_learn_mode()
			else:
				self.load_snapshot()

		elif i==3:
			if self.modal_screen:
				self.screens[self.modal_screen].switch_select('S')
			else:
				self.screens[self.active_screen].switch_select('S')

		# Custom ZynSwitches
		elif i==4:
			self.custom_switch_ui_action(0, "S")

		elif i==5:
			self.custom_switch_ui_action(1, "S")

		elif i==6:
			self.custom_switch_ui_action(2, "S")

		elif i==7:
			self.custom_switch_ui_action(3, "S")

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
			self.osc_receive()
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

				self.status_info['midi'] = True
				evtype = (ev & 0xF00000)>>20
				chan = (ev & 0x0F0000)>>16
				
				#logging.info("MIDI_UI MESSAGE: {}".format(hex(ev)))
				#logging.info("MIDI_UI MESSAGE DETAILS: {}, {}".format(chan,evtype))

				#Master MIDI Channel ...
				if chan==zynthian_gui_config.master_midi_channel:
					#Webconf configured messages for Snapshot Control ...
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
					#Program Change => Snapshot Load
					elif evtype==0xC:
						pgm = ((ev & 0x7F00)>>8) - zynthian_gui_config.master_midi_program_base
						logging.debug("PROGRAM CHANGE %d" % pgm)
						self.screens['snapshot'].midi_program_change(pgm)
					#Control Change ...
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
					#Note-on => CUIA
					elif evtype==0x9:
						note = str((ev & 0x7F00)>>8)
						vel = (ev & 0x007F)
						if note in self.note2cuia:
							self.callable_ui_action(self.note2cuia[note], [vel])

				#Program Change ...
				elif evtype==0xC:
					pgm = (ev & 0x7F00)>>8
					logging.info("MIDI PROGRAM CHANGE: CH{} => {}".format(chan,pgm))
	
					# SubSnapShot (ZS3) MIDI learn ...
					if self.midi_learn_mode and self.modal_screen=='zs3_learn':
						logging.info("ZS3 Saved: CH{} => {}".format(chan,pgm))
						self.screens['layer'].save_midi_chan_zs3(chan, pgm)
						self.exit_midi_learn_mode()

					# Set Preset or ZS3 (sub-snapshot), depending of config option
					else:
						if zynthian_gui_config.midi_prog_change_zs3:
							self.screens['layer'].set_midi_chan_zs3(chan, pgm)
						else:
							self.screens['layer'].set_midi_chan_preset(chan, pgm)

						#if not self.modal_screen and self.curlayer and chan==self.curlayer.get_midi_chan():
						#	self.show_screen('control')

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
					# If MIDI learn pending ...
					if self.midi_learn_zctrl:
						self.midi_learn_zctrl.cb_midi_learn(chan, ccnum)
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
		self.refresh_status()


	def stop_polling(self):
		self.polling=False


	def after(self, msec, func):
		zynthian_gui_config.top.after(msec, func)


	def zyngine_refresh(self):
		try:
			# Capture exit event and finish
			if self.exit_flag:
				self.stop()
				sys.exit(self.exit_code)
			# Refresh Current Layer
			elif self.curlayer and not self.loading:
				self.curlayer.refresh()

		except Exception as e:
			if zynthian_gui_config.raise_exceptions:
				raise e
			else:
				logging.error(e)

		# Poll
		if self.polling:
			zynthian_gui_config.top.after(160, self.zyngine_refresh)


	def refresh_status(self):
		try:
			# Get CPU Load
			#self.status_info['cpu_load'] = max(psutil.cpu_percent(None, True))
			self.status_info['cpu_load'] = zynautoconnect.get_jack_cpu_load()

			# Get Status Flags (once each 5 refreshes)
			if self.status_counter>5:
				self.status_counter = 0
				try:
					self.status_info['undervoltage'] = False
					self.status_info['overtemp'] = False

					# Get ARM flags
					res = check_output(("vcgencmd", "get_throttled")).decode('utf-8','ignore')
					thr = int(res[12:],16)
					if thr & 0x1:
						self.status_info['undervoltage'] = True
					elif thr & (0x4 | 0x2):
						self.status_info['overtemp'] = True

					# Get Recorder Status
					self.status_info['audio_recorder'] = self.screens['audio_recorder'].get_status()
					self.status_info['midi_recorder'] = self.screens['midi_recorder'].get_status()

				except Exception as e:
					logging.error(e)

			else:
				self.status_counter += 1

			# Refresh On-Screen Status
			try:
				if self.modal_screen:
					self.screens[self.modal_screen].refresh_status(self.status_info)
				else:
					self.screens[self.active_screen].refresh_status(self.status_info)
			except AttributeError:
				pass

			# Clean some status_info
			self.status_info['xrun'] = False
			self.status_info['midi'] = False

		except Exception as e:
			if zynthian_gui_config.raise_exceptions:
				raise err
			else:
				logging.error(e)

		# Poll
		if self.polling:
			zynthian_gui_config.top.after(200, self.refresh_status)


	#------------------------------------------------------------------
	# Engine OSC callbacks => No concurrency!! 
	#------------------------------------------------------------------


	def cb_osc_bank_view(self, path, args):
		pass


	def cb_osc_ctrl(self, path, args):
		#print ("OSC CTRL: " + path + " => "+str(args[0]))
		if path in self.screens['control'].zgui_controllers_map.keys():
			self.screens['control'].zgui_controllers_map[path].set_init_value(args[0])


	#------------------------------------------------------------------
	# All Notes/Sounds Off => PANIC!
	#------------------------------------------------------------------


	def all_sounds_off(self):
		logging.info("All Sounds Off!")
		for chan in range(16):
			lib_zyncoder.zynmidi_send_ccontrol_change(chan, 120, 0)


	def all_notes_off(self):
		logging.info("All Notes Off!")
		for chan in range(16):
			lib_zyncoder.zynmidi_send_ccontrol_change(chan, 123, 0)


	def raw_all_notes_off(self):
		logging.info("Raw All Notes Off!")
		for chan in range(16):
			self.raw_all_notes_off_chan(chan)


	def all_sounds_off_chan(self, chan):
		logging.info("All Sounds Off for channel {}!".format(chan))
		lib_zyncoder.zynmidi_send_ccontrol_change(chan, 120, 0)


	def all_notes_off_chan(self, chan):
		logging.info("All Notes Off for channel {}!".format(chan))
		lib_zyncoder.zynmidi_send_ccontrol_change(chan, 123, 0)


	def raw_all_notes_off_chan(self, chan):
		logging.info("Raw All Notes Off for channel {}!".format(chan))
		for n in range(128):
			lib_zyncoder.zynmidi_send_note_off(chan,n,0)


	#------------------------------------------------------------------
	# MIDI learning
	#------------------------------------------------------------------


	def init_midi_learn(self, zctrl):
		self.midi_learn_zctrl = zctrl
		lib_zyncoder.set_midi_learning_mode(1)
		self.screens['control'].refresh_midi_bind()
		self.screens['control'].set_select_path()


	def end_midi_learn(self):
		self.midi_learn_zctrl = None
		lib_zyncoder.set_midi_learning_mode(0)
		self.screens['control'].refresh_midi_bind()
		self.screens['control'].set_select_path()


	def refresh_midi_learn(self):
		self.screens['control'].refresh_midi_bind()
		self.screens['control'].set_select_path()


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
