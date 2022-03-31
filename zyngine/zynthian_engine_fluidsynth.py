# -*- coding: utf-8 -*-
#******************************************************************************
# ZYNTHIAN PROJECT: Zynthian Engine (zynthian_engine_fluidsynth)
# 
# zynthian_engine implementation for FluidSynth Sampler
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
import copy
import shutil
import logging
import oyaml as yaml
from collections import OrderedDict
from subprocess import check_output
from . import zynthian_engine
from . import zynthian_controller

#------------------------------------------------------------------------------
# FluidSynth Engine Class
#------------------------------------------------------------------------------

class zynthian_engine_fluidsynth(zynthian_engine):

	# ---------------------------------------------------------------------------
	# Controllers & Screens
	# ---------------------------------------------------------------------------

	# Standard MIDI Controllers
	_ctrls=[
		['volume',7,96],
		['modulation',1,0],
		['pan',10,64],
		['expression',11,127],
		['sustain',64,'off',['off','on']],
		['sostenuto',66,'off',['off','on']],
#		['reverb',91,64],
#		['chorus',93,2],
		['portamento on/off',65,'off',['off','on']],
		['portamento time-coarse',5,0],
		['portamento time-fine',37,0],
		['portamento control',84,0],
		['legato on/off',68,'off',['off','on']]
	]

	# Controller Screens
	default_ctrl_screens=[
		['main',['volume','pan','expression','modulation']],
		['portamento',['legato on/off','portamento on/off','portamento time-coarse','portamento time-fine']],
		['sustain',['sostenuto','sustain']],
	]

	# ---------------------------------------------------------------------------
	# Config variables
	# ---------------------------------------------------------------------------

	soundfont_dirs=[
		('EX', zynthian_engine.ex_data_dir + "/soundfonts/sf2"),
		('MY', zynthian_engine.my_data_dir + "/soundfonts/sf2"),
		('_', zynthian_engine.data_dir + "/soundfonts/sf2")
	]

	# ---------------------------------------------------------------------------
	# Initialization
	# ---------------------------------------------------------------------------

	def __init__(self, zyngui=None):
		super().__init__(zyngui)
		self.name = "FluidSynth"
		self.nickname = "FS"
		self.jackname = "fluidsynth"

		self.options['drop_pc']=True

		self.bank_config = OrderedDict()

		self.fs_options = "-o synth.midi-bank-select=mma -o synth.cpu-cores=3 -o synth.polyphony=64 -o midi.jack.id='{}' -o audio.jack.id='{}' -o audio.jack.autoconnect=0 -o audio.jack.multi='yes' -o synth.audio-groups=16 -o synth.audio-channels=16 -o synth.effects-groups=1 -o synth.chorus.active=0 -o synth.reverb.active=0".format(self.jackname,self.jackname)

		self.command = "fluidsynth -a jack -m jack -g 1 {}".format(self.fs_options)
		self.command_prompt = "\n> "

		self.start()
		self.reset()


	def reset(self):
		super().reset()
		self.soundfont_index={}
		self.clear_midi_routes()
		self.unload_unused_soundfonts()


	# ---------------------------------------------------------------------------
	# Subproccess Management & IPC
	# ---------------------------------------------------------------------------

	def stop(self):
		try:
			self.proc.sendline("quit")
			self.proc.expect("\ncheers!")
		except:
			super().stop()

	# ---------------------------------------------------------------------------
	# Layer Management
	# ---------------------------------------------------------------------------

	def add_layer(self, layer):
		self.layers.append(layer)
		layer.jackname = None
		layer.part_i=None
		self.setup_router(layer)


	def del_layer(self, layer):
		super().del_layer(layer)
		if layer.part_i is not None:
			self.set_all_midi_routes()
		self.unload_unused_soundfonts()

	# ---------------------------------------------------------------------------
	# MIDI Channel Management
	# ---------------------------------------------------------------------------

	def set_midi_chan(self, layer):
		self.setup_router(layer)

	# ---------------------------------------------------------------------------
	# Bank Management
	# ---------------------------------------------------------------------------

	def get_bank_list(self, layer=None):
		return self.get_filelist(self.soundfont_dirs,"sf2") + self.get_filelist(self.soundfont_dirs,"sf3")


	def set_bank(self, layer, bank):
		if self.load_bank(bank[0]):
			layer.refresh_controllers()
			return True
		else:
			return False


	def load_bank(self, bank_fpath, unload_unused_sf=True):
		if bank_fpath in self.soundfont_index:
			return True
		elif self.load_soundfont(bank_fpath):
			self.load_bank_config(bank_fpath)
			if unload_unused_sf:
				self.unload_unused_soundfonts()
			self.set_all_presets()
			return True
		else:
			return False


	def load_bank_config(self, bank_fpath):
		config_fpath = bank_fpath[0:-3] + "yml"
		try:
			with open(config_fpath,"r") as fh:
				yml = fh.read()
				logging.info("Loading bank config file %s => \n%s" % (config_fpath,yml))
				self.bank_config[bank_fpath] = yaml.load(yml, Loader=yaml.SafeLoader)
				return True
		except Exception as e:
			logging.info("Can't load bank config file '%s': %s" % (config_fpath,e))
			return False

	# ---------------------------------------------------------------------------
	# Preset Management
	# ---------------------------------------------------------------------------

	def get_preset_list(self, bank):
		logging.info("Getting Preset List for {}".format(bank[2]))
		preset_list=[]

		try:
			sfi = self.soundfont_index[bank[0]]
		except:
			sfi = self.load_bank(bank[0], False)

		if sfi:
			output=self.proc_cmd("inst {}".format(sfi))
			for f in output.split("\n"):
				try:
					prg=int(f[4:7])
					bank_msb=int(f[0:3])
					bank_lsb=int(bank_msb/128)
					bank_msb=bank_msb%128
					title=str.replace(f[8:-1], '_', ' ')
					preset_list.append([bank[0] + '/' + f.strip(),[bank_msb,bank_lsb,prg],title,bank[0]])
				except:
					pass

		return preset_list


	def set_preset(self, layer, preset, preload=False):
		try:
			sfi = self.soundfont_index[preset[3]]
		except:
			if layer.set_bank_by_id(preset[3]):
				sfi = self.soundfont_index[preset[3]]
			else:
				return False

		midi_bank=preset[1][0]+preset[1][1]*128
		midi_prg=preset[1][2]
		logging.debug("Set Preset => Layer: {}, SoundFont: {}, Bank: {}, Program: {}".format(layer.part_i, sfi, midi_bank, midi_prg))
		self.proc_cmd("select {} {} {} {}".format(layer.part_i, sfi, midi_bank, midi_prg))
		layer.send_ctrl_midi_cc()
		return True


	def cmp_presets(self, preset1, preset2):
		try:
			if preset1[3]==preset2[3] and preset1[1][0]==preset2[1][0] and preset1[1][1]==preset2[1][1] and preset1[1][2]==preset2[1][2]:
				return True
			else:
				return False
		except:
			return False


	#----------------------------------------------------------------------------
	# Controllers Managament
	#----------------------------------------------------------------------------

	def get_controllers_dict(self, layer):
		zctrls=super().get_controllers_dict(layer)
		self._ctrl_screens = copy.copy(self.default_ctrl_screens)

		try:
			sf = layer.bank_info[0]
			ctrl_items = self.bank_config[sf]['midi_controllers'].items()
		except:
			ctrl_items = None

		if ctrl_items:
			logging.debug("Generating extra controllers config ...")
			try:
				c=1
				ctrl_set=[]
				zctrls_extra = OrderedDict()
				for name, options in ctrl_items:
					try:
						if isinstance(options,int):
							options={ 'midi_cc': options }
						if 'midi_chan' not in options:
							options['midi_chan']=layer.midi_chan
						midi_cc=options['midi_cc']
						logging.debug("CTRL %s: %s" % (midi_cc, name))
						title=str.replace(name, '_', ' ')
						zctrls_extra[name]=zynthian_controller(self,name,title,options)
						ctrl_set.append(name)
						if len(ctrl_set)>=4:
							logging.debug("ADDING CONTROLLER SCREEN #"+str(c))
							self._ctrl_screens.append(['Extended#'+str(c),ctrl_set])
							ctrl_set=[]
							c=c+1
					except Exception as err:
						logging.error("Generating extra controller screens: %s" % err)

				if len(ctrl_set)>=1:
					logging.debug("ADDING EXTRA CONTROLLER SCREEN #"+str(c))
					self._ctrl_screens.append(['Extended#'+str(c),ctrl_set])

				zctrls.update(zctrls_extra)

			except Exception as err:
				logging.error("Generating extra controllers config: %s" % err)

		return zctrls


	# ---------------------------------------------------------------------------
	# Specific functions
	# ---------------------------------------------------------------------------

	def get_free_parts(self):
		free_parts = list(range(0,16))
		for layer in self.layers:
			try:
				free_parts.remove(layer.part_i)
			except:
				pass
		return free_parts


	def load_soundfont(self, sf):
		if sf not in self.soundfont_index:
			logging.info("Loading SoundFont '{}' ...".format(sf))
			# Send command to FluidSynth
			output=self.proc_cmd("load \"{}\"".format(sf))
			# Parse ouput ...
			sfi=None
			cre=re.compile(r"loaded SoundFont has ID (\d+)")
			for line in output.split("\n"):
				#logging.debug(" => {}".format(line))
				res=cre.match(line)
				if res:
					sfi=int(res.group(1))
			# If soundfont was loaded succesfully ...
			if sfi is not None:
				logging.info("Loaded SoundFont '{}' => {}".format(sf,sfi))
				# Insert ID in soundfont_index dictionary
				self.soundfont_index[sf]=sfi
				# Return soundfont ID
				return sfi
			else:
				logging.warning("SoundFont '{}' can't be loaded".format(sf))
				return False
		else:
			return self.soundfont_index[sf]


	def unload_unused_soundfonts(self):
		#Make a copy of soundfont index and remove used soundfonts
		sf_unload=copy.copy(self.soundfont_index)
		for layer in self.layers:
			bi=layer.bank_info
			if bi is not None:
				if bi[2] and bi[0] in sf_unload:
					#print("Skip "+bi[0]+"("+str(sf_unload[bi[0]])+")")
					del sf_unload[bi[0]]
			pi=layer.preset_info
			if pi is not None:
				if pi[2] and pi[3] in sf_unload:
					#print("Skip "+pi[0]+"("+str(sf_unload[pi[3]])+")")
					del sf_unload[pi[3]]
		#Then, remove the remaining ;-)
		for sf,sfi in sf_unload.items():
			logging.info("Unload SoundFont => {}".format(sfi))
			self.proc_cmd("unload {}".format(sfi))
			del self.soundfont_index[sf]


	# Set presets for all layers to restore soundfont assign (select) after load/unload soundfonts 
	def set_all_presets(self):
		for layer in self.layers:
			if layer.preset_info:
				self.set_preset(layer, layer.preset_info)


	def setup_router(self, layer):
		if layer.part_i is not None:
			# Clear and recreate all routes if the routes for this layer were set already
			self.set_all_midi_routes()
		else:
			# No need to clear routes if there is the only layer to add
			try:
				i = self.get_free_parts()[0]
				layer.part_i = i
				#layer.jackname = "{}:((l|r)_{:02d}|fx_(l|r)_({:02d}|{:02d}))".format(self.jackname,i,i*2,i*2+1)
				layer.jackname = "{}:(l|r)_{:02d}".format(self.jackname,i)
				self.zyngui.zynautoconnect_audio()
				logging.debug("Add part {} => {}".format(i, layer.jackname))
			except Exception as e:
				logging.error("Can't add part! => {}".format(e))

			self.set_layer_midi_routes(layer)


	def set_layer_midi_routes(self, layer):
		if layer.part_i is not None:
			midich = layer.get_midi_chan()
			router_chan_cmd = "router_chan {0} {0} 0 {1}".format(midich, layer.part_i)
			self.proc_cmd("router_begin note")
			self.proc_cmd(router_chan_cmd)
			self.proc_cmd("router_end")
			self.proc_cmd("router_begin cc")
			self.proc_cmd(router_chan_cmd)
			self.proc_cmd("router_end")
			self.proc_cmd("router_begin pbend")
			self.proc_cmd(router_chan_cmd)
			self.proc_cmd("router_end")
			self.proc_cmd("router_begin prog")
			self.proc_cmd(router_chan_cmd)
			self.proc_cmd("router_end")


	def set_all_midi_routes(self):
		self.clear_midi_routes()
		for layer in self.layers:
			self.set_layer_midi_routes(layer)


	def clear_midi_routes(self):
		self.proc_cmd("router_clear")


	# ---------------------------------------------------------------------------
	# API methods
	# ---------------------------------------------------------------------------

	@classmethod
	def zynapi_get_banks(cls):
		banks=[]
		for b in cls.get_filelist(cls.soundfont_dirs,"sf2") + cls.get_filelist(cls.soundfont_dirs,"sf3"):
			head, tail = os.path.split(b[0])
			fname, fext = os.path.splitext(tail)
			banks.append({
				'text': tail,
				'name': fname,
				'fullpath': b[0],
				'raw': b,
				'readonly': False
			})
		return banks


	@classmethod
	def zynapi_get_presets(cls, bank):
		return []


	@classmethod
	def zynapi_rename_bank(cls, bank_path, new_bank_name):
		head, tail = os.path.split(bank_path)
		fname, ext = os.path.splitext(tail)
		new_bank_path = head + "/" + new_bank_name + ext
		os.rename(bank_path, new_bank_path)


	@classmethod
	def zynapi_remove_bank(cls, bank_path):
		os.remove(bank_path)


	@classmethod
	def zynapi_download(cls, fullpath):
		return fullpath


	@classmethod
	def zynapi_install(cls, dpath, bank_path):

		if os.path.isdir(dpath):
			# Get list of sf2/sf3 files ...
			sfx_files = check_output("find \"{}\" -type f -iname *.sf2 -o -iname *.sf3".format(dpath), shell=True).decode("utf-8").split("\n")

			# Copy sf2/sf3 files to destiny ...
			count = 0
			for f in sfx_files:
				head, fname = os.path.split(f)
				if fname:
					shutil.move(f, zynthian_engine.my_data_dir + "/soundfonts/sf2/" + fname)
					count += 1

			if count==0:
				raise Exception("No SF2/SF3 soundfont files found!")

		else:
			fname, ext = os.path.splitext(dpath)
			if ext.lower() in ['.sf2', '.sf3']:
				shutil.move(dpath, zynthian_engine.my_data_dir + "/soundfonts/sf2")
			else:
				raise Exception("File doesn't look like a SF2/SF3 soundfont")


	@classmethod
	def zynapi_get_formats(cls):
		return "sf2,sf3,zip,tgz,tar.gz,tar.bz2"


	@classmethod
	def zynapi_martifact_formats(cls):
		return "sf2,sf3"


#******************************************************************************
