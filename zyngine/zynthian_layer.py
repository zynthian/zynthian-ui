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

import os
import copy
import logging
from time import sleep
import collections
from collections import OrderedDict

# Zynthian specific modules
from zyncoder.zyncore import lib_zyncore


class zynthian_layer:

	# ---------------------------------------------------------------------------
	# Data dirs
	# ---------------------------------------------------------------------------

	config_dir = os.environ.get('ZYNTHIAN_CONFIG_DIR',"/zynthian/config")
	data_dir = os.environ.get('ZYNTHIAN_DATA_DIR',"/zynthian/zynthian-data")
	my_data_dir = os.environ.get('ZYNTHIAN_MY_DATA_DIR',"/zynthian/zynthian-my-data")
	ex_data_dir = os.environ.get('ZYNTHIAN_EX_DATA_DIR',"/media/usb0")

	# ---------------------------------------------------------------------------
	# Initialization
	# ---------------------------------------------------------------------------


	def __init__(self, engine, midi_chan, zyngui=None):
		self.engine = None
		self.midi_chan = midi_chan
		self.zyngui = zyngui

		self.jackname = None
		
		if self.midi_chan is None:
			self.audio_out = ["system"]	
		else:
			self.audio_out = ["mixer"]

		if engine.nickname == "AI":
			if self.midi_chan == 256:
				self.audio_in = ["zynmixer:send_a", "zynmixer:send_b"]
				self.audio_out = ["zynmixer:return_a", "zynmixer:return_b"]
			else:
				self.audio_in = ["system:capture_1", "system:capture_2"]
		else:
			self.audio_in = [] # Only AI uses audio_in

		self.midi_out = ["MIDI-OUT", "NET-OUT"]

		self.bank_list = []
		self.bank_index = 0
		self.bank_name = None
		self.bank_info = None
		self.bank_msb = 0
		self.bank_msb_info = [[0,0], [0,0], [0,0]] # system, user, external => [offset, n]
		self.auto_save_bank = False # True to skip bank selection when saving preset

		self.show_fav_presets = False
		self.preset_list = []
		self.preset_index = 0
		self.preset_name = None
		self.preset_info = None
		self.preset_bank_index = None
		self.preset_loaded = None

		self.preload_index = None
		self.preload_name = None
		self.preload_info = None

		self.controllers_dict = None
		self.ctrl_screens_dict = None
		self.current_screen_index = -1
		self.refresh_flag = False

		self.status = "" # Allows indication of arbitary status text

		if engine is not None:
			self.set_engine(engine)


	def set_engine(self, engine):
		self.engine = engine
		self.engine.add_layer(self)
		self.refresh_controllers()


	def refresh(self):
		if self.refresh_flag:
			self.refresh_flag=False
			self.refresh_controllers()

			try:
				self.engine.refresh()
			except NotImplementedError:
				pass

			self.zyngui.refresh_screen()


	def reset(self):
		# MIDI-unlearn all controllers
		self.midi_unlearn()
		# Delete layer from engine
		self.engine.del_layer(self)
		# Clear refresh flag
		self.refresh_flag=False


	# ---------------------------------------------------------------------------
	# MIDI chan Management
	# ---------------------------------------------------------------------------

	def set_midi_chan(self, midi_chan):
		self.midi_chan = midi_chan
		self.engine.set_midi_chan(self)
		for zctrl in self.controllers_dict.values():
			zctrl.set_midi_chan(midi_chan)
		self.engine.refresh_midi_learn()
		self.send_ctrlfb_midi_cc()
		self.zyngui.zynautoconnect_audio()


	def get_midi_chan(self):
		return self.midi_chan


	# ---------------------------------------------------------------------------
	# Bank Management
	# ---------------------------------------------------------------------------

	def load_bank_list(self):
		self.bank_list = self.engine.get_bank_list(self)

		# Calculate info for bank_msb
		i = 0
		self.bank_msb_info = [[0,0], [0,0], [0,0]] # system, user, external => [offset, n]
		for bank in self.bank_list:
			if bank[0] is None:
				continue
			if bank[0].startswith(self.ex_data_dir):
				self.bank_msb_info[0][0] += 1
				self.bank_msb_info[1][0] += 1
				self.bank_msb_info[2][1] += 1
				i += 1
			elif bank[0].startswith(self.my_data_dir):
				self.bank_msb_info[0][0] += 1
				self.bank_msb_info[1][1] += 1
				i += 1
			else:
				break
		self.bank_msb_info[0][1] = len(self.bank_list) - i

		# Add favourites virtual bank if there is some preset marked as favourite
		if self.engine.show_favs_bank and len(self.engine.get_preset_favs(self))>0:
			self.bank_list = [["*FAVS*",0,"*** Favorites ***"]] + self.bank_list
			for i in range(3):
				self.bank_msb_info[i][0] += 1

		logging.debug("BANK LIST => \n%s" % str(self.bank_list))
		logging.debug("BANK MSB INFO => \n{}".format(self.bank_msb_info))


	def reset_bank(self):
		self.bank_index=0
		self.bank_name=None
		self.bank_info=None


	# Set bank of layer's engine by index
	# i: Index of the bank to select
	# set_engine: True to set engine's bank
	# returns: True if bank selected, None if more bank selection steps required or False on failure
	def set_bank(self, i, set_engine=True):
		if i < len(self.bank_list):
			bank_name = self.bank_list[i][2]

			if bank_name is None:
				return False

			if i != self.bank_index or self.bank_name != bank_name:
				set_engine_needed = True
				logging.info("Bank selected: %s (%d)" % (self.bank_name, i))
			else:
				set_engine_needed = False
				logging.info("Bank already selected: %s (%d)" % (self.bank_name, i))

			last_bank_index = self.bank_index
			last_bank_name = self.bank_name
			self.bank_index = i
			self.bank_name = bank_name
			self.bank_info = copy.deepcopy(self.bank_list[i])

			if set_engine and set_engine_needed:
				return self.engine.set_bank(self, self.bank_info)

		return False


	#TODO Optimize search!!
	def set_bank_by_name(self, bank_name, set_engine=True):
		for i in range(len(self.bank_list)):
			if bank_name == self.bank_list[i][2]:
				return self.set_bank(i, set_engine)
		return False


	#TODO Optimize search!!
	def set_bank_by_id(self, bank_id, set_engine=True):
		for i in range(len(self.bank_list)):
			if bank_id == self.bank_list[i][0]:
				return self.set_bank(i, set_engine)
		return False


	def get_bank_name(self):
		return self.bank_name


	def get_bank_index(self):
		return self.bank_index


	# ---------------------------------------------------------------------------
	# Preset Management
	# ---------------------------------------------------------------------------


	def load_preset_list(self):
		preset_list = []

		if self.show_fav_presets:
			for v in self.get_preset_favs().values():
				preset_list.append(v[1])

		elif self.bank_info:
			for preset in self.engine.get_preset_list(self.bank_info):
				if self.engine.is_preset_fav(preset):
					preset[2] = "❤" + preset[2]
				preset_list.append(preset)

		else:
			return

		self.preset_list = preset_list
		logging.debug("PRESET LIST => \n%s" % str(self.preset_list))


	def reset_preset(self):
		logging.debug("PRESET RESET!")
		self.preset_index=0
		self.preset_name=None
		self.preset_info=None


	def set_preset(self, i, set_engine=True, force_set_engine=True):
		if i < len(self.preset_list):
			preset_id = str(self.preset_list[i][0])
			preset_name = self.preset_list[i][2]
			preset_info = copy.deepcopy(self.preset_list[i])

			if not preset_name:
				return False

			# Remove favorite marker char
			if preset_name[0]=='❤':
				preset_name=preset_name[1:]

			# Check if preset is in favorites pseudo-bank and set real bank if needed
			if preset_id in self.engine.preset_favs:
				bank_name = self.engine.preset_favs[preset_id][0][2]
				if bank_name!=self.bank_name:
					self.set_bank_by_name(bank_name)

			# Check if force set engine
			if force_set_engine:
				set_engine_needed = True
			# Check if preset is already loaded
			elif self.engine.cmp_presets(preset_info, self.preset_info):
				set_engine_needed = False
				logging.info("Preset already selected: %s (%d)" % (preset_name,i))
				# Check if some other preset is preloaded
				if self.preload_info and not self.engine.cmp_presets(self.preload_info,self.preset_info):
					set_engine_needed = True
			else:
				set_engine_needed = True
				logging.info("Preset selected: %s (%d)" % (preset_name,i))

			last_preset_index = self.preset_index
			last_preset_name = self.preset_name
			self.preset_index = i
			self.preset_name = preset_name
			self.preset_info = preset_info
			self.preset_bank_index = self.bank_index

			# Clean preload info
			self.preload_index = None
			self.preload_name = None
			self.preload_info = None

			if set_engine:
				if set_engine_needed:
					#self.load_ctrl_config()
					return self.engine.set_preset(self, self.preset_info)
				else:
					return False

			return True
		return False


	#TODO Optimize search!!
	def set_preset_by_name(self, preset_name, set_engine=True, force_set_engine=True):
		for i in range(len(self.preset_list)):
			name_i = self.preset_list[i][2]
			try:
				if name_i[0]=='❤':
					name_i=name_i[1:]
				if preset_name == name_i:
					return self.set_preset(i, set_engine, force_set_engine)
			except:
				pass

		return False


	#TODO Optimize search!!
	def set_preset_by_id(self, preset_id, set_engine=True, force_set_engine=True):
		for i in range(len(self.preset_list)):
			if preset_id==self.preset_list[i][0]:
				return self.set_preset(i, set_engine, force_set_engine)
		return False


	def preload_preset(self, i):
		# Avoid preload on engines that take excessive time to load presets
		if self.engine.nickname in ['PD','MD']:
			return True
		if i < len(self.preset_list):
			if (not self.preload_info and not self.engine.cmp_presets(self.preset_list[i], self.preset_info)) or (self.preload_info and not self.engine.cmp_presets(self.preset_list[i], self.preload_info)):
				self.preload_index = i
				self.preload_name = self.preset_list[i][2]
				self.preload_info = copy.deepcopy(self.preset_list[i])
				logging.info("Preset Preloaded: %s (%d)" % (self.preload_name,i))
				self.engine.set_preset(self,self.preload_info,True)
				return True
		return False


	def restore_preset(self):
		if self.preset_name is not None and self.preload_info is not None and not self.engine.cmp_presets(self.preload_info,self.preset_info):
			if self.preset_bank_index is not None and self.bank_index != self.preset_bank_index:
				self.set_bank(self.preset_bank_index, False)
			self.preload_index = None
			self.preload_name = None
			self.preload_info = None
			logging.info("Restore Preset: %s (%d)" % (self.preset_name, self.preset_index))
			self.engine.set_preset(self, self.preset_info)
			return True
		return False


	def get_preset_name(self):
		return self.preset_name


	def get_preset_index(self):
		return self.preset_index


	def get_preset_bank_index(self):
		return self.preset_bank_index


	def get_preset_bank_name(self):
		try:
			return self.bank_list[self.preset_bank_index][2]
		except:
			return None


	def toggle_preset_fav(self, preset):
		self.engine.toggle_preset_fav(self, preset)
		if self.show_fav_presets and not len(self.get_preset_favs()):
			self.set_show_fav_presets(False)


	def remove_preset_fav(self, preset):
		self.engine.remove_preset_fav(preset)
		if self.show_fav_presets and not len(self.get_preset_favs()):
			self.set_show_fav_presets(False)


	def get_preset_favs(self):
		return self.engine.get_preset_favs(self)


	def set_show_fav_presets(self, flag=True):
		if flag and len(self.engine.get_preset_favs(self)):
			self.show_fav_presets = True
			#self.reset_preset()
		else:
			self.show_fav_presets = False


	def get_show_fav_presets(self):
		return self.show_fav_presets


	def toggle_show_fav_presets(self):
		if self.show_fav_presets:
			self.set_show_fav_presets(False)
		else:
			self.set_show_fav_presets(True)
		return self.show_fav_presets

	# ---------------------------------------------------------------------------
	# Controllers Management
	# ---------------------------------------------------------------------------


	def refresh_controllers(self):
		self.init_controllers()
		self.init_ctrl_screens()


	def init_controllers(self):
		self.controllers_dict = self.engine.get_controllers_dict(self)


	# Create controller screens from zynthian controller keys
	def init_ctrl_screens(self):
		#Build control screens ...
		self.ctrl_screens_dict = OrderedDict()
		for cscr in self.engine._ctrl_screens:
			self.ctrl_screens_dict[cscr[0]]=self.build_ctrl_screen(cscr[1])

		#Set active the first screen
		if len(self.ctrl_screens_dict) > 0:
			if self.current_screen_index == -1:
				self.current_screen_index = 0
		else:
			self.current_screen_index = -1


	def get_ctrl_screens(self):
		return self.ctrl_screens_dict


	def get_ctrl_screen(self, key):
		try:
			return self.ctrl_screens_dict[key]
		except:
			return None


	def get_current_screen_index(self):
		return self.current_screen_index


	def set_current_screen_index(self, i):
		self.current_screen_index = i


	# Build array of zynthian_controllers from list of keys
	def build_ctrl_screen(self, ctrl_keys):
		zctrls=[]
		for k in ctrl_keys:
			if k:
				try:
					zctrls.append(self.controllers_dict[k])
				except:
					logging.error("Controller %s is not defined" % k)
		return zctrls


	def send_ctrl_midi_cc(self):
		for k, zctrl in self.controllers_dict.items():
			if zctrl.midi_cc:
				lib_zyncore.ui_send_ccontrol_change(zctrl.midi_chan, zctrl.midi_cc, int(zctrl.value))
				logging.debug("Sending MIDI CH{}#CC{}={} for {}".format(zctrl.midi_chan, zctrl.midi_cc, int(zctrl.value), k))
		self.send_ctrlfb_midi_cc()


	def send_ctrlfb_midi_cc(self):
		for k, zctrl in self.controllers_dict.items():
			if zctrl.midi_learn_cc:
				lib_zyncore.ctrlfb_send_ccontrol_change(zctrl.midi_learn_chan, zctrl.midi_learn_cc, int(zctrl.value))
				logging.debug("Sending MIDI FB CH{}#CC{}={} for {}".format(zctrl.midi_learn_chan, zctrl.midi_learn_cc, int(zctrl.value), k))
			elif zctrl.midi_cc:
				lib_zyncore.ctrlfb_send_ccontrol_change(zctrl.midi_chan, zctrl.midi_cc, int(zctrl.value))
				logging.debug("Sending MIDI FB CH{}#CC{}={} for {}".format(zctrl.midi_chan, zctrl.midi_cc, int(zctrl.value), k))


	def midi_unlearn(self, unused=None):
		for k, zctrl in self.controllers_dict.items():
			zctrl.midi_unlearn()


	#----------------------------------------------------------------------------
	# MIDI processing
	#----------------------------------------------------------------------------

	def midi_control_change(self, chan, ccnum, ccval):
		if self.engine:
			#logging.debug("Receving MIDI CH{}#CC{}={}".format(chan, ccnum, ccval))
			try:
				self.engine.midi_control_change(chan, ccnum, ccval)
			except:
				pass


	def midi_bank_msb(self, i):
		logging.debug("Received Bank MSB for CH#{}: {}".format(self.midi_chan, i))
		if i>=0 and i<=2:
			self.bank_msb = i


	def midi_bank_lsb(self, i):
		info = self.bank_msb_info[self.bank_msb]
		logging.debug("Received Bank LSB for CH#{}: {} => {}".format(self.midi_chan, i, info))
		if i<info[1]:
			logging.debug("MSB offset for CH#{}: {}".format(self.midi_chan, info[0]))
			self.set_show_fav_presets(False)
			self.set_bank(info[0] + i)
			self.load_preset_list()
		else:
			logging.warning("Bank index {} doesn't exist for MSB {} on CH#{}".format(i, self.bank_msb, self.midi_chan))


	# ---------------------------------------------------------------------------
	# State Management
	# ---------------------------------------------------------------------------

	def get_state(self):
		state = {
			'engine_name': self.engine.name,
			'engine_nick': self.engine.nickname,
			'engine_jackname': self.engine.jackname,
			'midi_chan': self.midi_chan,
			'bank_index': self.bank_index,
			'bank_name': self.bank_name,
			'bank_info': self.bank_info,
			'preset_index': self.preset_index,
			'preset_name': self.preset_name,
			'preset_info': self.preset_info,
			'show_fav_presets': self.show_fav_presets,
			'controllers_dict': {},
			'current_screen_index': self.current_screen_index,
		}

		for k in self.controllers_dict:
			state['controllers_dict'][k] = self.controllers_dict[k].get_state()

		return state


	def restore_state_0(self, state):
		# Load bank list
		try:
			self.bank_name = state['bank_name']	#tweak for working with setbfree extended config!! => TODO improve it!!
			self.load_bank_list()
			self.bank_name = None
		except Exception as e:
			logging.warning("Error loading bank list on layer {}: {}".format(self.get_basepath(), e))


	def restore_state_1(self, state):
		self.wait_stop_loading()

		if 'show_fav_presets' in state:
			self.set_show_fav_presets(state['show_fav_presets'])

		# Set bank and load preset_list
		try:
			if self.set_bank_by_name(state['bank_name']):
				self.wait_stop_loading()
				self.load_preset_list()
		except Exception as e:
			logging.warning("Invalid Bank on layer {}: {}".format(self.get_basepath(), e))

		#  and set preset
		try:
			if(state['preset_info']):
				self.preset_loaded = self.set_preset_by_id(state['preset_info'][0], True, False)
			else:
				self.preset_loaded = self.set_preset_by_name(state['preset_name'], True, False)
			self.wait_stop_loading()
		except Exception as e:
			logging.warning("Invalid Preset on layer {}: {}".format(self.get_basepath(), e))

		# Refresh controller config
		if self.refresh_flag:
			self.refresh_flag = False
			self.refresh_controllers()

		# Set active controller page
		if 'current_screen_index' in state:
			self.current_screen_index = state['current_screen_index']

		self.restore_state_legacy(state)


	def restore_state_2(self, state):

		# WARNING => This is really UGLY!
		# For non-LV2 engines, bank and preset can affect what controllers do.
		# In case of LV2, just restoring the controllers ought to be enough, which is nice
		# since it saves the delay between setting a preset and updating controllers.
		if self.preset_loaded and not self.engine.nickname.startswith('JV'):
			sleep(0.2)

		self.wait_stop_loading()

		#Set controller values
		for k in state['controllers_dict']:
			try:
				self.controllers_dict[k].restore_state(state['controllers_dict'][k])
			except Exception as e:
				logging.warning("Invalid Controller on layer {}: {}".format(self.get_basepath(), e))


	def restore_state_legacy(self, state):
		# Set legacy Note Range (BW compatibility)
		if self.midi_chan is not None and self.midi_chan >= 0 and 'note_range' in state:
			nr = state['note_range']
			lib_zyncore.set_midi_filter_note_range(self.midi_chan, nr['note_low'], nr['note_high'], nr['octave_trans'], nr['halftone_trans'])


	def wait_stop_loading(self):
		while self.engine.loading>0:
			logging.debug("WAITING FOR STOP LOADING ({}) ... => {}".format(self.engine.name,self.engine.loading))
			sleep(0.1)


	# ---------------------------------------------------------------------------
	# Audio Output Routing:
	# ---------------------------------------------------------------------------

	def get_jackname(self):
		return self.jackname


	def get_audio_jackname(self):
		return self.jackname


	def get_audio_out(self):
		return self.audio_out


	def set_audio_out(self, ao):
		self.audio_out = []

		# Sanitize audio out list. It should avoid audio routing snapshot version issues.
		for p in ao:
			if p.startswith("system") or p.startswith("zynmixer"):
				if self.midi_chan is None:
					self.audio_out.append("system")
				else:
					self.audio_out.append("mixer")
			else:
				self.audio_out.append(p)

		# Remove duplicates
		self.audio_out = list(dict.fromkeys(self.audio_out).keys())

		self.pair_audio_out()
		self.zyngui.zynautoconnect_audio()


	def add_audio_out(self, jackname):
		if isinstance(jackname, zynthian_layer):
			jackname = jackname.get_audio_jackname()

		if jackname not in self.audio_out:
			self.audio_out.append(jackname)
			logging.debug("Connecting Audio Output {} => {}".format(self.get_audio_jackname(), jackname))

		self.pair_audio_out()
		self.zyngui.zynautoconnect_audio()


	def del_audio_out(self, jackname):
		if isinstance(jackname, zynthian_layer):
			jackname = jackname.get_audio_jackname()

		try:
			self.audio_out.remove(jackname)
			logging.debug("Disconnecting Audio Output {} => {}".format(self.get_audio_jackname(), jackname))
		except:
			pass

		self.pair_audio_out()
		self.zyngui.zynautoconnect_audio()


	def toggle_audio_out(self, jackname):
		if isinstance(jackname, zynthian_layer):
			jackname = jackname.get_audio_jackname()

		if jackname not in self.audio_out:
			self.audio_out.append(jackname)
		else:
			self.audio_out.remove(jackname)

		logging.debug("Toggling Audio Output: {}".format(jackname))

		self.pair_audio_out()
		self.zyngui.zynautoconnect_audio()


	def reset_audio_out(self):
		if self.midi_chan is None:
			self.audio_out = ["system"]
		elif self.midi_chan == 256:
			self.audio_out = ["zynmixer:return_a", "zynmixer:return_b"]
		else:
			self.audio_out = ["mixer"]
			
		self.pair_audio_out()
		self.zyngui.zynautoconnect_audio()


	def mute_audio_out(self):
		self.audio_out = []
		self.pair_audio_out()
		self.zyngui.zynautoconnect_audio()


	def pair_audio_out(self):
		if not self.engine.options['layer_audio_out']:
			for l in self.engine.layers:
				if l != self:
					l.audio_out = self.audio_out
					#logging.debug("Pairing CH#{} => {}".format(l.midi_chan,l.audio_out))


	# ---------------------------------------------------------------------------
	# Audio Input Routing:
	# ---------------------------------------------------------------------------


	def get_audio_in(self):
		return self.audio_in


	def set_audio_in(self, ai):
		if self.midi_chan == 256 and self.engine.nickname == 'AI':
			self.audio_in = ["zynmixer:send_a", "zynmixer:send_b"]
		else:
			self.audio_in = copy.copy(ai)
		self.zyngui.zynautoconnect_audio()


	def add_audio_in(self, jackname):
		if jackname not in self.audio_in:
			self.audio_in.append(jackname)
			logging.debug("Connecting Audio Capture {} => {}".format(jackname, self.get_audio_jackname()))

		self.zyngui.zynautoconnect_audio()


	def del_audio_in(self, jackname):
		try:
			self.audio_in.remove(jackname)
			logging.debug("Disconnecting Audio Capture {} => {}".format(jackname, self.get_audio_jackname()))
		except:
			pass

		self.zyngui.zynautoconnect_audio()


	def toggle_audio_in(self, jackname):
		if jackname not in self.audio_in:
			self.audio_in.append(jackname)
		else:
			self.audio_in.remove(jackname)

		logging.debug("Toggling Audio Capture: {}".format(jackname))

		self.zyngui.zynautoconnect_audio()


	def reset_audio_in(self):
		if self.midi_chan is None or self.midi_chan < 16:
			self.audio_in = ["system:capture_1", "system:capture_2"]
		elif self.midi_chan == 256 and self.engine.nickname == 'AI':
			self.audio_in = ["zynmixer:send_a", "zynmixer:send_b"]
		else:
			self.audio_in = []
		self.zyngui.zynautoconnect_audio()


	def mute_audio_in(self):
		self.audio_in=[]
		self.zyngui.zynautoconnect_audio()


	def is_parallel_audio_routed(self, layer):
		if isinstance(layer, zynthian_layer) and layer != self and layer.midi_chan == self.midi_chan and collections.Counter(layer.audio_out) == collections.Counter(self.audio_out):
			return True
		else:
			return False

	# ---------------------------------------------------------------------------
	# MIDI Routing:
	# ---------------------------------------------------------------------------

	def get_midi_jackname(self):
		return self.engine.jackname


	def get_midi_out(self):
		return self.midi_out


	def set_midi_out(self, mo):
		self.midi_out=mo
		#logging.debug("Setting MIDI connections:")
		#for jn in mo:
		#	logging.debug("  {} => {}".format(self.engine.jackname, jn))
		self.zyngui.zynautoconnect_midi()


	def add_midi_out(self, jackname):
		if isinstance(jackname, zynthian_layer):
			jackname=jackname.get_midi_jackname()

		if jackname not in self.midi_out:
			self.midi_out.append(jackname)
			logging.debug("Connecting MIDI {} => {}".format(self.get_midi_jackname(), jackname))

		self.zyngui.zynautoconnect_midi()


	def del_midi_out(self, jackname):
		if isinstance(jackname, zynthian_layer):
			jackname=jackname.get_midi_jackname()

		try:
			self.midi_out.remove(jackname)
			logging.debug("Disconnecting MIDI {} => {}".format(self.get_midi_jackname(), jackname))
		except:
			pass

		self.zyngui.zynautoconnect_midi()


	def toggle_midi_out(self, jackname):
		if isinstance(jackname, zynthian_layer):
			jackname=jackname.get_midi_jackname()

		if jackname not in self.midi_out:
			self.midi_out.append(jackname)
		else:
			self.midi_out.remove(jackname)

		self.zyngui.zynautoconnect_midi()


	def mute_midi_out(self):
		self.midi_out=[]
		self.zyngui.zynautoconnect_midi()


	def is_parallel_midi_routed(self, layer):
		if isinstance(layer, zynthian_layer) and layer != self and layer.midi_chan == self.midi_chan and collections.Counter(layer.midi_out) == collections.Counter(self.midi_out):
			return True
		else:
			return False


	# ---------------------------------------------------------------------------
	# Path/Breadcrumb Strings
	# ---------------------------------------------------------------------------


	def get_path(self):
		if self.preset_name:
			bank_name = self.get_preset_bank_name()
			if not bank_name:
				bank_name = "???"
			path = bank_name + "/" + self.preset_name
		else:
			path = self.bank_name
		return path


	def get_basepath(self):
		path = self.engine.get_path(self)
		if self.midi_chan is not None:
			if self.midi_chan<16:
				path = "{}#{}".format(self.midi_chan+1, path)
			elif self.midi_chan==256:
				path = "Main#{}".format(path)
		return path


	def get_bankpath(self):
		path = self.get_basepath()
		if self.bank_name and self.bank_name!="None":
			path += " > " + self.bank_name
		return path


	def get_presetpath(self):
		path = self.get_basepath()

		subpath = None
		bank_name = self.get_preset_bank_name()
		if bank_name and bank_name != "None" and not path.endswith(bank_name):
			subpath = bank_name
			if self.preset_name:
				subpath += "/" + self.preset_name
		elif self.preset_name:
			subpath = self.preset_name

		if subpath:
			path += " > " + subpath

		return path


#******************************************************************************
