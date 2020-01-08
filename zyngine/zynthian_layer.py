# -*- coding: utf-8 -*-
#******************************************************************************
# ZYNTHIAN PROJECT: Zynthian Layer (zynthian_layer)
# 
# zynthian layer
# 
# Copyright (C) 2015-2017 Fernando Moyano <jofemodo@zynthian.org>
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

import logging
import copy
from time import sleep
from collections import OrderedDict

class zynthian_layer:

	# ---------------------------------------------------------------------------
	# Initialization
	# ---------------------------------------------------------------------------


	def __init__(self, engine, midi_chan, zyngui=None):
		self.zyngui = zyngui
		self.engine = engine
		self.midi_chan = midi_chan

		self.jackname = None
		self.audio_out = ["system"]

		self.bank_list = []
		self.bank_index = 0
		self.bank_name = None
		self.bank_info = None

		self.preset_list = []
		self.preset_index = 0
		self.preset_name = None
		self.preset_info = None
		self.preset_bank_index = None

		self.preload_index = None
		self.preload_name = None
		self.preload_info = None

		self.controllers_dict = None
		self.ctrl_screens_dict = None
		self.active_screen_index = -1

		self.listen_midi_cc = True
		self.refresh_flag = False

		self.reset_zs3()

		self.engine.add_layer(self)
		self.refresh_controllers()


	def refresh(self):
		if self.refresh_flag:
			self.refresh_flag=False
			self.refresh_controllers()

			#TODO: Improve this Dirty Hack!!
			if self.engine.nickname=='MD':
				self.zyngui.screens['preset'].fill_list()
				if self.zyngui.active_screen=='bank':
					if self.preset_name:
						self.zyngui.show_screen('control')
					else:
						self.zyngui.show_screen('preset')

			self.zyngui.refresh_screen()


	def reset(self):
		# MIDI-unlearn all controllers
		for k,zctrl in self.controllers_dict.items():
			zctrl.midi_unlearn()
		# Delete layer from engine
		self.engine.del_layer(self)
		# Clear refresh flag
		self.refresh_flag=False


	# ---------------------------------------------------------------------------
	# MIDI chan Management
	# ---------------------------------------------------------------------------


	def set_midi_chan(self, midi_chan):
		self.midi_chan=midi_chan
		self.engine.set_midi_chan(self)
		for zctrl in self.controllers_dict.values():
			zctrl.set_midi_chan(midi_chan)


	def get_midi_chan(self):
		return self.midi_chan


	# ---------------------------------------------------------------------------
	# Bank Management
	# ---------------------------------------------------------------------------


	def load_bank_list(self):
		self.bank_list=self.engine.get_bank_list(self)
		logging.debug("BANK LIST => \n%s" % str(self.bank_list))


	def reset_bank(self):
		self.bank_index=0
		self.bank_name=None
		self.bank_info=None


	def set_bank(self, i, set_engine=True):
		if i < len(self.bank_list):
			last_bank_index=self.bank_index
			last_bank_name=self.bank_name
			self.bank_index=i
			self.bank_name=self.bank_list[i][2]
			self.bank_info=copy.deepcopy(self.bank_list[i])
			logging.info("Bank Selected: %s (%d)" % (self.bank_name,i))

			if set_engine and (last_bank_index!=i or not last_bank_name):
				self.reset_preset()
				return self.engine.set_bank(self, self.bank_info)

			return True
		return False


	#TODO Optimize search!!
	def set_bank_by_name(self, name, set_engine=True):
		for i in range(len(self.bank_list)):
			if name==self.bank_list[i][2]:
				return self.set_bank(i,set_engine)
		return False


	def get_bank_name(self):
		return self.preset_name


	def get_bank_index(self):
		return self.bank_index


	# ---------------------------------------------------------------------------
	# Presest Management
	# ---------------------------------------------------------------------------


	def load_preset_list(self):
		if self.bank_info:
			self.preset_list=self.engine.get_preset_list(self.bank_info)
			logging.debug("PRESET LIST => \n%s" % str(self.preset_list))


	def reset_preset(self):
		logging.debug("PRESET RESET!")
		self.preset_index=0
		self.preset_name=None
		self.preset_info=None


	def set_preset(self, i, set_engine=True):
		if i < len(self.preset_list):
			last_preset_index=self.preset_index
			last_preset_name=self.preset_name
			self.preset_index=i
			self.preset_name=self.preset_list[i][2]
			self.preset_info=copy.deepcopy(self.preset_list[i])
			self.preset_bank_index=self.bank_index

			logging.info("Preset Selected: %s (%d)" % (self.preset_name,i))
			#=> '+self.preset_list[i][3]

			if self.preload_info:
				if not self.engine.cmp_presets(self.preload_info,self.preset_info):
					set_engine_needed = True
					self.preload_index = i
					self.preload_name = self.preset_name
					self.preload_info = self.preset_info
				else:
					set_engine_needed = False

			elif last_preset_index!=i or not last_preset_name:
				set_engine_needed = True

			else:
				set_engine_needed = False

			if set_engine and set_engine_needed:
				#TODO => Review this!!
				#self.load_ctrl_config()
				return self.engine.set_preset(self, self.preset_info)

			return True
		return False


	#TODO Optimize search!!
	def set_preset_by_name(self, name, set_engine=True):
		for i in range(len(self.preset_list)):
			if name==self.preset_list[i][2]:
				return self.set_preset(i,set_engine)
		return False


	def preload_preset(self, i):
		if i < len(self.preset_list) and (self.preload_info==None or not self.engine.cmp_presets(self.preload_info,self.preset_list[i])):
			self.preload_index=i
			self.preload_name=self.preset_list[i][2]
			self.preload_info=copy.deepcopy(self.preset_list[i])
			logging.info("Preset Preloaded: %s (%d)" % (self.preload_name,i))
			self.engine.set_preset(self,self.preload_info,True)
			return True
		return False


	def restore_preset(self):
		if self.preset_name is not None and not self.engine.cmp_presets(self.preload_info,self.preset_info):
			if self.preset_bank_index is not None and self.bank_index!=self.preset_bank_index:
				self.set_bank(self.preset_bank_index,False)
			self.preload_index=self.preset_index
			self.preload_name=self.preset_name
			self.preload_info=self.preset_info
			logging.info("Restore Preset: %s (%d)" % (self.preset_name,self.preset_index))
			self.engine.set_preset(self,self.preset_info)
			return True
		return False


	def get_preset_name(self):
		return self.preset_name


	def get_preset_index(self):
		return self.preset_index


	# ---------------------------------------------------------------------------
	# Controllers Management
	# ---------------------------------------------------------------------------


	def refresh_controllers(self):
		self.init_controllers()
		self.init_ctrl_screens()


	def init_controllers(self):
		self.controllers_dict=self.engine.get_controllers_dict(self)


	# Create controller screens from zynthian controller keys
	def init_ctrl_screens(self):
		#Build control screens ...
		self.ctrl_screens_dict=OrderedDict()
		for cscr in self.engine._ctrl_screens:
			self.ctrl_screens_dict[cscr[0]]=self.build_ctrl_screen(cscr[1])
			
		#Set active the first screen
		if len(self.ctrl_screens_dict)>0:
			self.active_screen_index=0
		else:
			self.active_screen_index=-1


	def get_ctrl_screens(self):
		return self.ctrl_screens_dict


	def get_ctrl_screen(self, key):
		try:
			return self.ctrl_screens_dict[key]
		except:
			return None


	def get_active_screen_index(self):
		return self.active_screen_index


	def set_active_screen_index(self, i):
		self.active_screen_index = i


	# Build array of zynthian_controllers from list of keys
	def build_ctrl_screen(self, ctrl_keys):
		zctrls=[]
		for k in ctrl_keys:
			try:
				zctrls.append(self.controllers_dict[k])
			except:
				logging.error("Controller %s is not defined" % k)
		return zctrls


	def send_ctrl_midi_cc(self):
		for k, zctrl in self.controllers_dict.items():
			if zctrl.midi_cc:
				self.zyngui.zynmidi.set_midi_control(zctrl.midi_chan, zctrl.midi_cc, int(zctrl.value))
				logging.debug("Sending MIDI CC{}={} for {}".format(zctrl.midi_cc, zctrl.value, k))


	#----------------------------------------------------------------------------
	# MIDI CC processing
	#----------------------------------------------------------------------------


	def midi_control_change(self, chan, ccnum, ccval):
		if self.engine:
			if self.listen_midi_cc and chan==self.midi_chan:
				#TODO => Optimize!!
				for k, zctrl in self.controllers_dict.items():
					if zctrl.midi_cc==ccnum:
						try:
							# Aeolus, FluidSynth, LinuxSampler, puredata, Pianoteq, setBfree, ZynAddSubFX
							self.engine.midi_zctrl_change(zctrl, ccval)
						except:
							pass

			elif not self.listen_midi_cc:
				try:
					# Jalv
					self.engine.midi_control_change(chan, ccnum, ccval)
				except:
					pass


	# ---------------------------------------------------------------------------
	# Snapshot Management
	# ---------------------------------------------------------------------------


	def get_snapshot(self):
		snapshot={
			'engine_name': self.engine.name,
			'engine_nick': self.engine.nickname,
			'midi_chan': self.midi_chan,
			'bank_index': self.bank_index,
			'bank_name': self.bank_name,
			'bank_info': self.bank_info,
			'preset_index': self.preset_index,
			'preset_name': self.preset_name,
			'preset_info': self.preset_info,
			'controllers_dict': {},
			'zs3_list': self.zs3_list,
			'active_screen_index': self.active_screen_index
		}
		for k in self.controllers_dict:
			snapshot['controllers_dict'][k] = self.controllers_dict[k].get_snapshot()
		return snapshot


	def restore_snapshot_1(self, snapshot):
		#Constructor, including engine and midi_chan info, is called before

		self.wait_stop_loading()

		#Load bank list and set bank
		self.bank_name=snapshot['bank_name']	#tweak for working with setbfree extended config!! => TODO improve it!!
		self.load_bank_list()
		self.bank_name=None
		self.set_bank_by_name(snapshot['bank_name'])
		self.wait_stop_loading()
	
		#Load preset list and set preset
		self.load_preset_list()
		self.preset_loaded=self.set_preset_by_name(snapshot['preset_name'])
		self.wait_stop_loading()

		#Refresh controller config
		if self.refresh_flag:
			self.refresh_flag=False
			self.refresh_controllers()

		#Set zs3 list
		if 'zs3_list' in snapshot:
			self.zs3_list = snapshot['zs3_list']

		#Set active screen
		if 'active_screen_index' in snapshot:
			self.active_screen_index=snapshot['active_screen_index']


	def restore_snapshot_2(self, snapshot):

		# Wait a little bit if a preset has been loaded 
		if self.preset_loaded:
			sleep(0.2)

		self.wait_stop_loading()

		#Set controller values
		for k in snapshot['controllers_dict']:
			self.controllers_dict[k].restore_snapshot(snapshot['controllers_dict'][k])


	def wait_stop_loading(self):
		while self.engine.loading>0:
			logging.debug("WAITING FOR STOP LOADING ...")
			sleep(0.1)


	# ---------------------------------------------------------------------------
	# ZS3 Management (Zynthian SubSnapShots)
	# ---------------------------------------------------------------------------


	def reset_zs3(self):
		self.zs3_list = [None]*128


	def delete_zs3(self, i):
		self.zs3_list[i] = None


	def get_zs3(self, i):
		return self.zs3_list[i]


	def save_zs3(self, i):
		try:
			zs3 = {
				'bank_index': self.bank_index,
				'bank_name': self.bank_name,
				'bank_info': self.bank_info,
				'preset_index': self.preset_index,
				'preset_name': self.preset_name,
				'preset_info': self.preset_info,
				'active_screen_index': self.active_screen_index,
				'controllers_dict': {}
			}

			for k in self.controllers_dict:
				zs3['controllers_dict'][k] = self.controllers_dict[k].get_snapshot()

			self.zs3_list[i] = zs3

		except Exception as e:
			logging.error(e)


	def restore_zs3(self, i):
		zs3 = self.zs3_list[i]

		if zs3:
			#Load bank list and set bank
			self.load_bank_list()
			self.set_bank_by_name(zs3['bank_name'])
			self.wait_stop_loading()

			#Load preset list and set preset
			self.load_preset_list()
			self.set_preset_by_name(zs3['preset_name'])
			self.wait_stop_loading()

			#Refresh controller config
			if self.refresh_flag:
				self.refresh_flag=False
				self.refresh_controllers()

			#Set active screen
			if 'active_screen_index' in zs3:
				self.active_screen_index=zs3['active_screen_index']

			#Set controller values
			sleep(0.3)
			for k in zs3['controllers_dict']:
				self.controllers_dict[k].restore_snapshot(zs3['controllers_dict'][k])

			return True

		else:
			return False


	# ---------------------------------------------------------------------------
	# Audio Routing:
	# ---------------------------------------------------------------------------


	def get_jackname(self):
		return self.jackname
		

	def get_audio_out(self):
		return self.audio_out


	def set_audio_out(self, ao, autoconnect=True):
		self.audio_out=ao
		#logging.debug("Setting connections:")
		#for jn in ao:
		#	logging.debug("  {} => {}".format(self.engine.jackname, jn))
		if autoconnect:
			self.zyngui.zynautoconnect_audio(True)


	def add_audio_out(self, jackname, autoconnect=True):
		if isinstance(jackname, zynthian_layer):
			jackname=jackname.jackname

		if jackname not in self.audio_out:
			self.audio_out.append(jackname)
			logging.debug("Connecting {} => {}".format(self.engine.jackname, jackname))

		if autoconnect:
			self.zyngui.zynautoconnect_audio(True)


	def del_audio_out(self, jackname, autoconnect=True):
		if isinstance(jackname, zynthian_layer):
			jackname=jackname.jackname

		try:
			self.audio_out.remove(jackname)
			logging.debug("Disconnecting {} => {}".format(self.engine.jackname, jackname))
		except:
			pass

		if autoconnect:
			self.zyngui.zynautoconnect_audio(True)


	def toggle_audio_out(self, jackname, autoconnect=True):
		if isinstance(jackname, zynthian_layer):
			jackname=jackname.jackname

		if jackname not in self.audio_out:
			self.audio_out.append(jackname)
		else:
			self.audio_out.remove(jackname)

		if autoconnect:
			self.zyngui.zynautoconnect_audio(True)


	def reset_audio_out(self, autoconnect=True):
		self.audio_out=["system"]
		if autoconnect:
			self.zyngui.zynautoconnect_audio(True)


	def mute_audio_out(self, autoconnect=True):
		self.audio_out=[]
		if autoconnect:
			self.zyngui.zynautoconnect_audio(True)


	# ---------------------------------------------------------------------------
	# Channel "Path" String
	# ---------------------------------------------------------------------------


	def get_path(self):
		path = self.bank_name
		if self.preset_name:
			path = path + "/" + self.preset_name
		return path


	def get_basepath(self):
		path = self.engine.get_path(self)
		if self.midi_chan is not None:
			path = "{}#{}".format(self.midi_chan+1, path)
		return path


	def get_bankpath(self):
		path = self.get_basepath()
		if self.bank_name and self.bank_name!="NoBank":
			path += " > " + self.bank_name
		return path


	def get_presetpath(self):
		path = self.get_basepath()

		subpath = None
		if self.bank_name and self.bank_name!="NoBank":
			subpath = self.bank_name
			if self.preset_name:
				subpath += "/" + self.preset_name
		elif self.preset_name:
			subpath = self.preset_name

		if subpath:
			path += " > " + subpath

		return path


#******************************************************************************
