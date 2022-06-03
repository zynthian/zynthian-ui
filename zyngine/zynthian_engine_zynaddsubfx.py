# -*- coding: utf-8 -*-
#******************************************************************************
# ZYNTHIAN PROJECT: Zynthian Engine (zynthian_engine_zynaddsubfx)
# 
# zynthian_engine implementation for ZynAddSubFX Synthesizer
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
import logging
import liblo
import shutil
from time import sleep
from os.path import isfile, join
from subprocess import check_output
from . import zynthian_engine

#------------------------------------------------------------------------------
# ZynAddSubFX Engine Class
#------------------------------------------------------------------------------

class zynthian_engine_zynaddsubfx(zynthian_engine):

	# ---------------------------------------------------------------------------
	# Controllers & Screens
	# ---------------------------------------------------------------------------

	bend_ticks = [ [str(x) for x in range(-64,64)], [x for x in range(-6400,6400,100)] ]

	# MIDI Controllers
	_ctrls=[
		['volume',7,115],
		#['panning',10,64],
		#['expression',11,127],
		#['volume','/part$i/Pvolume',96],
		['panning','/part$i/Ppanning',64],
		['filter cutoff',74,64],
		['filter resonance',71,64],

		['voice limit','/part$i/Pvoicelimit',0,60],
		['drum mode','/part$i/Pdrummode','off','off|on'],
		['sustain',64,'off','off|on'],
		['assign mode','/part$i/polyType','poly',[ [ 'poly', 'mono', 'legato', 'latch'], [0, 1, 2, 3 ] ] ],

		#['portamento on/off',65,'off','off|on'],
		['portamento enable','/part$i/ctl/portamento.portamento','off','off|on'],
		['portamento auto','/part$i/ctl/portamento.automode','on','off|on'],
		['portamento receive','/part$i/ctl/portamento.receive','on','off|on'],

		['portamento time','/part$i/ctl/portamento.time',64],
		['portamento up/down','/part$i/ctl/portamento.updowntimestretch',64],
		['threshold type','/part$i/ctl/portamento.pitchthreshtype','<=',['<=','>=']],
		['threshold','/part$i/ctl/portamento.pitchthresh',3],

		['portaprop on/off','/part$i/ctl/portamento.proportional','off','off|on'],
		['portaprop rate','/part$i/ctl/portamento.propRate',80],
		['portaprop depth','/part$i/ctl/portamento.propDepth',90],

		['modulation',1,0],
		['modulation amplitude',76,127],
		['modwheel depth','/part$i/ctl/modwheel.depth',80],
		['modwheel exp','/part$i/ctl/modwheel.exponential','off','off|on'],

		['bendrange','/part$i/ctl/pitchwheel.bendrange','2',bend_ticks],
		['bendrange split','/part$i/ctl/pitchwheel.is_split','off','off|on'],
		['bendrange down','/part$i/ctl/pitchwheel.bendrange_down',0,bend_ticks],

		['resonance center',77,64],
		['resonance bandwidth',78,64],
		['rescenter depth','/part$i/ctl/resonancecenter.depth',64],
		['resbw depth','/part$i/ctl/resonancebandwidth.depth',64],

		['bandwidth',75,64],
		['bandwidth depth','/part$i/ctl/bandwidth.depth',64],
		['bandwidth exp','/part$i/ctl/bandwidth.exponential','off','off|on'],

		['panning depth','/part$i/ctl/panning.depth',64],
		['filter.cutoff depth','/part$i/ctl/filtercutoff.depth',64],
		['filter.Q depth','/part$i/ctl/filterq.depth',64],

		['velocity sens.','/part$i/Pvelsns',64],
		['velocity offs.','/part$i/Pveloffs',64]
	]

	# Controller Screens
	_ctrl_screens=[
		['main',['volume','panning','filter cutoff','filter resonance']],
		['mode',['drum mode','sustain','assign mode','voice limit']],
		['portamento',['portamento enable','portamento auto','portamento receive']],
		['portamento time',['portamento time','portamento up/down','threshold','threshold type']],
		['portamento prop',['portaprop on/off','portaprop rate','portaprop depth']],
		['modulation',['modulation','modulation amplitude','modwheel depth','modwheel exp']],
		['pitchwheel',['bendrange split','bendrange down','bendrange']],
		['resonance',['resonance center','rescenter depth','resonance bandwidth','resbw depth']],
		['bandwidth',['bandwidth','bandwidth depth','bandwidth exp']],
		['depth',['panning depth','filter.cutoff depth','filter.Q depth']],
		['velocity',['velocity sens.','velocity offs.']]
	]

	#----------------------------------------------------------------------------
	# Config variables
	#----------------------------------------------------------------------------

	bank_dirs = [
		('EX', zynthian_engine.ex_data_dir + "/presets/zynaddsubfx/banks"),
		('MY', zynthian_engine.my_data_dir + "/presets/zynaddsubfx/banks"),
		('_', zynthian_engine.data_dir + "/zynbanks")
	]

	#----------------------------------------------------------------------------
	# Initialization
	#----------------------------------------------------------------------------

	def __init__(self, zyngui=None):
		super().__init__(zyngui)
		self.name = "ZynAddSubFX"
		self.nickname = "ZY"
		self.jackname = "zynaddsubfx"

		self.options['drop_pc']=True

		self.osc_target_port = 6693

		try:
			self.sr = int(self.zyngui.get_jackd_samplerate())
		except Exception as e:
			logging.error(e)
			self.sr = 44100

		try:
			self.bs = int(self.zyngui.get_jackd_blocksize())
		except Exception as e:
			logging.error(e)
			self.bs = 256

		if self.config_remote_display():
			self.command = "zynaddsubfx -r {} -b {} -O jack-multi -I jack -P {} -a".format(self.sr, self.bs, self.osc_target_port)
		else:
			self.command = "zynaddsubfx -r {} -b {} -O jack-multi -I jack -P {} -a -U".format(self.sr, self.bs, self.osc_target_port)

		# Zynaddsubfx which uses PWD as the root for presets, due to the fltk
		# toolkit used for the gui file browser.
		self.command_cwd = zynthian_engine.my_data_dir + "/presets"

		self.command_prompt = "\n\\[INFO] Main Loop..."

		self.osc_paths_data = []
		self.current_slot_zctrl = None
		self.slot_zctrls = {}

		self.start()
		self.osc_init()
		self.reset()
		
		
	def reset(self):
		super().reset()
		self.disable_all_parts()

	# ---------------------------------------------------------------------------
	# Layer Management
	# ---------------------------------------------------------------------------

	def add_layer(self, layer):
		self.layers.append(layer)
		layer.part_i = self.get_free_parts()[0]
		layer.jackname = "{}:part{}/".format(self.jackname, layer.part_i)
		logging.debug("ADD LAYER => Part {} ({})".format(layer.part_i, self.jackname))


	def del_layer(self, layer):
		super().del_layer(layer)
		self.disable_part(layer.part_i)
		layer.part_i = None
		layer.jackname = None

	# ---------------------------------------------------------------------------
	# MIDI Channel Management
	# ---------------------------------------------------------------------------

	def set_midi_chan(self, layer):
		if layer.part_i is not None:
			liblo.send(self.osc_target, "/part%d/Prcvchn" % layer.part_i, layer.get_midi_chan())

	#----------------------------------------------------------------------------
	# Bank Managament
	#----------------------------------------------------------------------------

	def get_bank_list(self, layer=None):
		return self.get_dirlist(self.bank_dirs)

	#----------------------------------------------------------------------------
	# Preset Managament
	#----------------------------------------------------------------------------

	@staticmethod
	def _get_preset_list(bank):
		preset_list=[]
		preset_dir=bank[0]
		index=0
		logging.info("Getting Preset List for %s" % bank[2])
		for f in sorted(os.listdir(preset_dir)):
			preset_fpath=join(preset_dir,f)
			ext=f[-3:].lower()
			if (isfile(preset_fpath) and (ext=='xiz' or ext=='xmz' or ext=='xsz' or ext=='xlz')):
				try:
					index=int(f[0:4])-1
					title=str.replace(f[5:-4], '_', ' ')
				except:
					index+=1
					title=str.replace(f[0:-4], '_', ' ')
				bank_lsb=int(index/128)
				bank_msb=bank[1]
				prg=index%128
				preset_list.append([preset_fpath,[bank_msb,bank_lsb,prg],title,ext,f])
		return preset_list


	def get_preset_list(self, bank):
		return self._get_preset_list(bank)


	def set_preset(self, layer, preset, preload=False):
		self.start_loading()
		if preset[3]=='xiz':
			self.enable_part(layer)
			liblo.send(self.osc_target, "/load-part",layer.part_i,preset[0])
			#logging.debug("OSC => /load-part %s, %s" % (layer.part_i,preset[0]))
		elif preset[3]=='xmz':
			self.enable_part(layer)
			liblo.send(self.osc_target, "/load_xmz",preset[0])
			logging.debug("OSC => /load_xmz %s" % preset[0])
		elif preset[3]=='xsz':
			liblo.send(self.osc_target, "/load_xsz",preset[0])
			logging.debug("OSC => /load_xsz %s" % preset[0])
		elif preset[3]=='xlz':
			liblo.send(self.osc_target, "/load_xlz",preset[0])
			logging.debug("OSC => /load_xlz %s" % preset[0])
		liblo.send(self.osc_target, "/volume")
		i=0
		while self.loading and i<100: 
			sleep(0.1)
			i=i+1
		layer.send_ctrl_midi_cc()
		return True


	def cmp_presets(self, preset1, preset2):
		try:
			if preset1[0]==preset2[0]:
				return True
			else:
				return False
		except:
			return False

	# ---------------------------------------------------------------------------
	# Specific functions
	# ---------------------------------------------------------------------------

	def get_free_parts(self):
		free_parts=list(range(0,16))
		for layer in self.layers:
			try:
				free_parts.remove(layer.part_i)
			except:
				pass
		logging.debug("FREE PARTS => %s" % free_parts)
		return free_parts


	def enable_part(self, layer):
		if layer.part_i is not None:
			liblo.send(self.osc_target, "/part%d/Penabled" % layer.part_i, True)
			liblo.send(self.osc_target, "/part%d/Prcvchn" % layer.part_i, layer.get_midi_chan())


	def disable_part(self, i):
		liblo.send(self.osc_target, "/part%d/Penabled" % i, False)


	def enable_layer_parts(self):
		for layer in self.layers:
			self.enable_part(layer)
		for i in self.get_free_parts():
			self.disable_part(i)


	def disable_all_parts(self):
		for i in range(0,16):
			self.disable_part(i)

	#----------------------------------------------------------------------------
	# OSC Managament
	#----------------------------------------------------------------------------

	def osc_add_methods(self):
		self.osc_server.add_method("/volume", 'i', self.cb_osc_load_preset)
		#self.osc_server.add_method("/paths", None, self.cb_osc_paths)
		#super().osc_add_methods()


	def cb_osc_load_preset(self, path, args):
		self.stop_loading()


	def send_controller_value(self, zctrl):
		if zctrl.osc_path:
			liblo.send(self.osc_target,zctrl.osc_path, zctrl.get_ctrl_osc_val())
		else:
			raise Exception("NO OSC CONTROLLER")

	# ---------------------------------------------------------------------------
	# Deprecated functions
	# ---------------------------------------------------------------------------

	def cb_osc_paths(self, path, args, types, src):
		self.get_cb_osc_paths(path, args, types, src)
		self.zyngui.screens['control'].list_data=self.osc_paths_data
		self.zyngui.screens['control'].fill_list()


	def get_cb_osc_paths(self, path, args, types, src):
		for a, t in zip(args, types):
			if not a or t=='b':
				continue
			print("=> %s (%s)" % (a,t))
			a=str(a)
			postfix=prefix=firstchar=lastchar=''
			if a[-1:]=='/':
				tnode='dir'
				postfix=lastchar='/'
				a=a[:-1]
			elif a[-1:]==':':
				tnode='cmd'
				postfix=':'
				a=a[:-1]
				continue
			elif a[0]=='P':
				tnode='par'
				firstchar='P'
				a=a[1:]
			else:
				continue
			parts=a.split('::')
			if len(parts)>1:
				a=parts[0]
				pargs=parts[1]
				if tnode=='par':
					if pargs=='i':
						tnode='ctrl'
						postfix=':i'
					elif pargs=='T:F':
						tnode='bool'
						postfix=':b'
					else:
						continue
			parts=a.split('#',1)
			if len(parts)>1:
				n=int(parts[1])
				if n>0:
					for i in range(0,n):
						title=prefix+parts[0]+str(i)+postfix
						path=firstchar+parts[0]+str(i)+lastchar
						self.osc_paths.append((path,tnode,title))
			else:
				title=prefix+a+postfix
				path=firstchar+a+lastchar
				self.osc_paths_data.append((path,tnode,title))

	# ---------------------------------------------------------------------------
	# API methods
	# ---------------------------------------------------------------------------

	@classmethod
	def zynapi_get_banks(cls):
		banks=[]
		for b in cls.get_dirlist(cls.bank_dirs, False):
			banks.append({
				'text': b[2],
				'name': b[4],
				'fullpath': b[0],
				'raw': b,
				'readonly': False
			})
		return banks


	@classmethod
	def zynapi_get_presets(cls, bank):
		presets=[]
		for p in cls._get_preset_list(bank['raw']):
			presets.append({
				'text': p[4],
				'name': os.path.splitext(p[4])[0],
				'fullpath': p[0],
				'raw': p,
				'readonly': False
			})
		return presets


	@classmethod
	def zynapi_new_bank(cls, bank_name):
		os.mkdir(zynthian_engine.my_data_dir + "/presets/zynaddsubfx/banks/" + bank_name)


	@classmethod
	def zynapi_rename_bank(cls, bank_path, new_bank_name):
		head, tail = os.path.split(bank_path)
		new_bank_path = head + "/" + new_bank_name
		os.rename(bank_path, new_bank_path)


	@classmethod
	def zynapi_remove_bank(cls, bank_path):
		shutil.rmtree(bank_path)


	@classmethod
	def zynapi_rename_preset(cls, preset_path, new_preset_name):
		head, tail = os.path.split(preset_path)
		fname, ext = os.path.splitext(tail)
		new_preset_path = head + "/" + new_preset_name + ext
		os.rename(preset_path, new_preset_path)


	@classmethod
	def zynapi_remove_preset(cls, preset_path):
		os.remove(preset_path)


	@classmethod
	def zynapi_download(cls, fullpath):
		return fullpath


	@classmethod
	def zynapi_install(cls, dpath, bank_path):

		if os.path.isdir(dpath):
			# Get list of directories (banks) containing xiz files ...
			xiz_files = check_output("find \"{}\" -type f -iname *.xiz".format(dpath), shell=True).decode("utf-8").split("\n")

			# Copy xiz files to destiny, creating the bank if needed ...
			count = 0
			for f in xiz_files:
				head, xiz_fname = os.path.split(f)
				head, dbank = os.path.split(head)
				if dbank:
					dest_dir = zynthian_engine.my_data_dir + "/presets/zynaddsubfx/banks/" + dbank
					os.makedirs(dest_dir, exist_ok=True)
					shutil.move(f, dest_dir + "/" + xiz_fname)
					count += 1

			if count==0:
				raise Exception("No XIZ files found!")

		else:
			fname, ext = os.path.splitext(dpath)
			if ext=='.xiz':
				shutil.move(dpath, bank_path)
			else:
				raise Exception("File doesn't look like a XIZ preset!")



	@classmethod
	def zynapi_get_formats(cls):
		return "xiz,zip,tgz,tar.gz,tar.bz2"


	@classmethod
	def zynapi_martifact_formats(cls):
		return "xiz"

#******************************************************************************
