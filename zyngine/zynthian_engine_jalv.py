# -*- coding: utf-8 -*-
# ******************************************************************************
# ZYNTHIAN PROJECT: Zynthian Engine (zynthian_engine_jalv)
#
# zynthian_engine implementation for Jalv Plugin Host
#
# Copyright (C) 2015-2024 Fernando Moyano <jofemodo@zynthian.org>
#
# ******************************************************************************
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
# ******************************************************************************

import copy
import os
import re
import shutil
import logging
from os.path import isfile
from subprocess import check_output, STDOUT

from . import zynthian_lv2
from . import zynthian_engine
from . import zynthian_controller

# ------------------------------------------------------------------------------
# Jalv Engine Class => Engine for LV2 plugins
# ------------------------------------------------------------------------------


class zynthian_engine_jalv(zynthian_engine):

	# ------------------------------------------------------------------------------
	# Custom plugin info
	# ------------------------------------------------------------------------------

	if "Raspberry Pi 4" in os.environ.get('RBPI_VERSION'):
		rpi = "RPi4"
	elif "Raspberry Pi 3" in os.environ.get('RBPI_VERSION'):
		rpi = "RPi3"
	else:
		rpi = "RPi2"

	# Plugins that required different GUI toolkit to that advertised or cannot run native GUI on Zynthian
	broken_ui = {
			#'http://calf.sourceforge.net/plugins/Monosynth': {"RPi4:":True, "RPi3": False, "RPi2": False },
			#'http://calf.sourceforge.net/plugins/Organ': {"RPi4:":True, "RPi3": False, "RPi2": False },
			#'http://nickbailey.co.nr/triceratops': {"RPi4:":True, "RPi3": False, "RPi2": False },
			#'http://code.google.com/p/amsynth/amsynth': {"RPi4:":True, "RPi3": False, "RPi2": False },
			'http://gareus.org/oss/lv2/tuna#one': {"RPi5": False, "RPi4": False, "RPi3": False, "RPi2": False},  # Disable because CPU usage and widget implemented in main UI
			'http://gareus.org/oss/lv2/tuna#mod': {"RPi5": False, "RPi4": False, "RPi3": False, "RPi2": False},  # Disable because CPU usage and widget implemented in main UI
			#"http://tytel.org/helm": {"RPi5": False, "RPi4": False, "RPi3": True, "RPi2": False}  # Better CPU with gtk but only qt4 works on RPi4
	}

	plugins_custom_gui = {
		'http://gareus.org/oss/lv2/meters#spectr30mono': "/zynthian/zynthian-ui/zyngui/zynthian_widget_spectr30.py",
		'http://gareus.org/oss/lv2/meters#spectr30stereo': "/zynthian/zynthian-ui/zyngui/zynthian_widget_spectr30.py",
		'http://gareus.org/oss/lv2/tuna#one': "/zynthian/zynthian-ui/zyngui/zynthian_widget_tunaone.py",
		'http://gareus.org/oss/lv2/tuna#mod': "/zynthian/zynthian-ui/zyngui/zynthian_widget_tunaone.py",
		'http://looperlative.com/plugins/lp3-basic': "/zynthian/zynthian-ui/zyngui/zynthian_widget_looper.py"
	}

	# ------------------------------------------------------------------------------
	# Native formats configuration (used by zynapi_install, preset converter, etc.)
	# ------------------------------------------------------------------------------

	plugin2native_ext = {
		"Dexed": "syx",
		"synthv1": "synthv1",
		"padthv1": "padthv1",
		"Obxd": "fxb"
		#"Helm": "helm"
	}

	plugin2preset2lv2_format = {
		"Dexed": "dx7syx",
		"synthv1": "synthv1",
		"padthv1": "padthv1",
		"Obxd": "obxdfxb"
		#"Helm": "helm"
	}

	# ---------------------------------------------------------------------------
	# Custom controller pages
	# ---------------------------------------------------------------------------

	plugin_ctrl_info = {
		"ctrls": {
			'modulation wheel': [1, 0],
			'volume': [7, 98],
			'sustain pedal': [64, 'off', 'off|on']
		},
		"ctrl_screens": {
			'_default_synth': ['modulation wheel', 'sustain pedal'],
			'Calf Monosynth': ['modulation wheel'],
			'Dexed': ['sustain pedal'],
			'Fabla': [],
			'Foo YC20 Organ': [],
			'Helm': ['sustain pedal'],
			'MDA DX10': ['volume', 'modulation wheel', 'sustain pedal'],
			'MDA JX10': ['volume', 'modulation wheel', 'sustain pedal'],
			'MDA ePiano': ['volume', 'modulation wheel', 'sustain pedal'],
			'MDA Piano': ['volume', 'modulation wheel', 'sustain pedal'],
			'Nekobi': ['sustain pedal'],
			'Noize Mak3r': [],
			'Obxd': ['modulation wheel', 'sustain pedal'],
			'Pianoteq 7 Stage': ['sustain pedal'],
			'Raffo Synth': [],
			'Red Zeppelin 5': [],
			'reMID': ['volume'],
			'String machine': [],
			'synthv1': [],
			'Surge': ['modulation wheel', 'sustain pedal'],
			'padthv1': [],
			'Vex': [],
			'amsynth': ['modulation wheel', 'sustain pedal']
		}
	}

	# ----------------------------------------------------------------------------
	# ZynAPI variables
	# ----------------------------------------------------------------------------

	zynapi_instance = None

	# ----------------------------------------------------------------------------
	# Initialization
	# ----------------------------------------------------------------------------

	def __init__(self, eng_code, state_manager, dryrun=False, jackname=None):
		super().__init__(state_manager)

		if state_manager:
			self.eng_info = self.state_manager.chain_manager.engine_info[eng_code]
		else:
			self.eng_info = zynthian_lv2.get_engines()[eng_code]

		self.type = self.eng_info["TYPE"]
		self.name = "Jalv/" + self.eng_info["NAME"]
		self.nickname = eng_code
		self.plugin_name = self.eng_info["NAME"]
		self.plugin_url = self.eng_info['URL']

		# WARNING Show all controllers for Gareus Meters, as they seem to be wrongly marked with property "not_on_gui"
		if self.plugin_url.startswith("http://gareus.org/oss/lv2/meters"):
			self.ignore_not_on_gui = True
		else:
			self.ignore_not_on_gui = False

		self.native_gui = False
		if 'UI' in self.eng_info:
			if self.plugin_url in self.broken_ui:
				self.native_gui = self.broken_ui[self.plugin_url][self.rpi]
			else:
				self.native_gui = self.eng_info['UI']
				#if not self.native_gui:
				#	self.native_gui = "AUTO"

		if not dryrun:
			if jackname:
				self.jackname = jackname
			else:
				self.jackname = self.state_manager.chain_manager.get_next_jackname(self.plugin_name)

			logging.debug("CREATING JALV ENGINE => {}".format(self.jackname))

			if self.config_remote_display() and self.native_gui:
				if self.native_gui == "Qt5UI":
					jalv_bin = "jalv.qt5"
				elif self.native_gui == "Qt4UI":
					jalv_bin = "jalv.qt4"
				else:  #  elif self.native_gui=="X11UI":
					jalv_bin = "jalv.gtk"
				self.command = ("{} --jack-name {} {}".format(jalv_bin, self.jackname, self.plugin_url))
			else:
				self.command = ("jalv -n {} {}".format(self.jackname, self.plugin_url))
				# Some plugins need a X11 display for running headless (QT5, QT6),
				# but some others can't run headless if there is a valid DISPLAY defined
				if not self.plugin_name.endswith("v1"):
					self.command_env['DISPLAY'] = "X"

			self.command_prompt = "\n> "

			# Jalv which uses PWD as the root for presets
			self.command_cwd = zynthian_engine.my_data_dir + "/presets/lv2"

			output = self.start()

			# Get Plugin & Jack names from Jalv starting text ...
			if output:
				for line in output.split("\n"):
					if line[0:10] == "JACK Name:":
						self.jackname = line[11:].strip()
						logging.debug("Jack Name => {}".format(self.jackname))
						break

			# Set MIDI Controllers from hardcoded plugin info
			try:
				if self.plugin_name in self.plugin_ctrl_info['ctrl_screens']:
					ctrl_screen = self.plugin_ctrl_info['ctrl_screens'][self.plugin_name]
				elif self.type == 'MIDI Synth':
					logging.info("Using default MIDI controllers for '{}'.".format(self.plugin_name))
					ctrl_screen = self.plugin_ctrl_info['ctrl_screens']['_default_synth']
				else:
					ctrl_screen = None
				if ctrl_screen:
					self._ctrl_screens = [['MIDI Controllers', copy.copy(ctrl_screen)]]
					self._ctrls = []
					for ctrl_name in ctrl_screen:
						self._ctrls.append([ctrl_name] + self.plugin_ctrl_info['ctrls'][ctrl_name])
				else:
					self._ctrls = []
					self._ctrl_screens = []
			except:
				logging.error("Error setting MIDI controllers for '{}'.".format(self.plugin_name))
				self._ctrls = []
				self._ctrl_screens = []

			# Generate LV2-Plugin Controllers
			self.lv2_monitors_dict = {}
			self.lv2_zctrl_dict = self.get_lv2_controllers_dict()
			self.generate_ctrl_screens(self.lv2_zctrl_dict)

			# Look for a custom GUI
			try:
				self.custom_gui_fpath = self.plugins_custom_gui[self.plugin_url]
			except:
				self.custom_gui_fpath = None

		# Get bank & presets info
		self.preset_info = zynthian_lv2.get_plugin_presets_cache(self.plugin_name)

		self.reset()

	# ---------------------------------------------------------------------------
	# Processor Management
	# ---------------------------------------------------------------------------

	def add_processor(self, processor):
		super().add_processor(processor)
		self.set_midi_chan(processor)

	def get_name(self, processor=None):
		return self.plugin_name

	def get_path(self, processor=None):
		return self.plugin_name

	# ---------------------------------------------------------------------------
	# MIDI Channel Management
	# ---------------------------------------------------------------------------

	def set_midi_chan(self, processor):
		if self.plugin_name == "Triceratops":
			self.lv2_zctrl_dict["midi_channel"].set_value(processor.midi_chan+1.5)
		elif self.plugin_name.startswith("SO-"):
			self.lv2_zctrl_dict["channel"].set_value(processor.midi_chan)

	# ----------------------------------------------------------------------------
	# Bank Managament
	# ----------------------------------------------------------------------------

	def get_bank_list(self, processor=None):
		bank_list = []
		for bank_label, info in self.preset_info.items():
			bank_list.append((str(info['bank_url']), None, bank_label, None))
		if len(bank_list) == 0:
			bank_list.append(("", None, "None", None))
		return bank_list

	def set_bank(self, processor, bank):
		return True

	def get_user_bank_urid(self, bank_name):
		return "file://{}/presets/lv2/{}.presets.lv2/{}".format(self.my_data_dir, zynthian_engine_jalv.sanitize_text(self.plugin_name), zynthian_engine_jalv.sanitize_text(bank_name))

	def create_user_bank(self, bank_name):
		bundle_path = "{}/presets/lv2/{}.presets.lv2".format(self.my_data_dir, zynthian_engine_jalv.sanitize_text(self.plugin_name))
		fpath = bundle_path + "/manifest.ttl"

		bank_id = zynthian_engine_jalv.sanitize_text(bank_name)
		bank_ttl = "\n<{}>\n".format(bank_id)
		bank_ttl += "\ta pset:Bank ;\n"
		bank_ttl += "\tlv2:appliesTo <{}> ;\n".format(self.plugin_url)
		bank_ttl += "\trdfs:label \"{}\" .\n".format(bank_name)

		with open(fpath, 'a+') as f:
			f.write(bank_ttl)
			
		# Cache is updated when saving the preset

	def rename_user_bank(self, bank, new_bank_name):
		if self.is_preset_user(bank):
			try:
				# TODO: This changes position of bank in list - Suggest using bank URI as key in preset_info
				zynthian_engine_jalv.lv2_rename_bank(bank[0], new_bank_name)
			except Exception as e:
				logging.error(e)

			# Update cache
			try:
				self.preset_info[new_bank_name] = self.preset_info.pop(bank[2])
				zynthian_lv2.save_plugin_presets_cache(self.plugin_name, self.preset_info)
			except Exception as e:
				logging.error(e)

	def remove_user_bank(self, bank):
		if self.is_preset_user(bank):
			try:
				zynthian_engine_jalv.lv2_remove_bank(bank)
			except Exception as e:
				logging.error(e)
			
			# Update cache
			if bank[2] in self.preset_info:
				try:
					self.preset_info.pop(bank[2])
					zynthian_lv2.save_plugin_presets_cache(self.plugin_name, self.preset_info)
				except Exception as e:
					logging.error(e)

	def delete_user_bank(self, bank):
		if self.is_preset_user(bank):
			try:
				for preset in list(self.preset_info[bank[2]]['presets']):
					self.delete_preset(bank, preset['url'])
				self.remove_user_bank(bank)
				# TODO: self.zyngui.curprocessor.load_preset_list()
			except Exception as e:
				logging.error(e)

	# ----------------------------------------------------------------------------
	# Preset Managament
	# ----------------------------------------------------------------------------

	def get_preset_list(self, bank):
		preset_list = []
		try:
			for info in self.preset_info[bank[2]]['presets']:
				title = info['label'].replace("_", " ").strip()
				preset_list.append([info['url'], None, title, bank[0]])
		except:
			preset_list.append(("", None, "", None))

		return preset_list

	def set_preset(self, processor, preset, preload=False):
		if not preset[0]:
			return
		output = self.proc_cmd("preset {}".format(preset[0]))

		# Parse new controller values
		for line in output.split("\n"):
			try:
				parts = line.split(" = ")
				if len(parts) == 2:
					self.lv2_zctrl_dict[parts[0]]._set_value(float(parts[1]))
			except Exception as e:
				logging.warning(e)

		return True

	def cmp_presets(self, preset1, preset2):
		try:
			if preset1[0]==preset2[0]:
				return True
			else:
				return False
		except:
			return False

	def is_preset_user(self, preset):
		return isinstance(preset[0], str) and preset[0].startswith("file://{}/presets/lv2/".format(self.my_data_dir))

	def preset_exists(self, bank, preset_name):
		# TODO: This would be more robust using URI but that is created dynamically by save_preset()
		if not bank or bank[2] not in self.preset_info:
			return False
		try:
			for preset in self.preset_info[bank[2]]['presets']:
				if preset['label'] == preset_name:
					return True
		except Exception as e:
			logging.error(e)
		return False

	def save_preset(self, bank, preset_name):
		# Save preset (jalv)
		if not bank:
			bank = ["", None, "None", None]
		res = self.proc_cmd("save preset %s,%s" % (bank[0], preset_name)).split("\n")
		
		if res[-1].startswith("ERROR"):
			logging.error("Can't save preset => {}".format(res))
		else:
			preset_uri = res[-1].strip()
			logging.info("Saved preset '{}' => {}".format(preset_name, preset_uri))

			# Add to cache
			try:
				# Add bank if needed
				if bank[2] not in self.preset_info:
					self.preset_info[bank[2]] = {
						'bank_url': bank[0],
						'presets': []
					}
				# Add preset
				if not self.preset_exists(bank, preset_name):
					self.preset_info[bank[2]]['presets'].append({'label': preset_name,  "url": preset_uri})
					# Save presets cache
					zynthian_lv2.save_plugin_presets_cache(self.plugin_name, self.preset_info)
				# Return preset uri
				return preset_uri
			except Exception as e:
				logging.error(e)

	def delete_preset(self, bank, preset):
		if self.is_preset_user(preset):
			try:
				# Remove from LV2 ttl
				zynthian_engine_jalv.lv2_remove_preset(preset[0])

				# Remove from  cache
				for i, p in enumerate(self.preset_info[bank[2]]['presets']):
					if p['url'] == preset[0]:
						del self.preset_info[bank[2]]['presets'][i]
						zynthian_lv2.save_plugin_presets_cache(self.plugin_name, self.preset_info)
						break 

			except Exception as e:
				logging.error(e)
		
		try:
			return len(self.preset_info[bank[2]]['presets'])
		except Exception as e:
			pass
		zynthian_engine_jalv.lv2_remove_bank(bank)
		return 0

	def rename_preset(self, bank, preset, new_preset_name):
		if self.is_preset_user(preset):
			try:
				# Update LV2 ttl
				zynthian_engine_jalv.lv2_rename_preset(preset[0], new_preset_name)

				# Update cache
				for i, p in enumerate(self.preset_info[bank[2]]['presets']):
					if p['url'] == preset[0]:
						self.preset_info[bank[2]]['presets'][i]['label'] = new_preset_name
						zynthian_lv2.save_plugin_presets_cache(self.plugin_name, self.preset_info)
						break

			except Exception as e:
				logging.error(e)

	# ----------------------------------------------------------------------------
	# Controllers Managament
	# ----------------------------------------------------------------------------

	def get_lv2_controllers_dict(self):
		logging.info("Getting Controller List from LV2 Plugin ...")
		zctrls = {}
		for i, info in zynthian_lv2.get_plugin_ports(self.plugin_url).items():
			symbol = info['symbol']
			#logging.debug("Controller {} info =>\n{}!".format(symbol, info))
			try:
				# If there is points info ...
				if len(info['scale_points']) > 1:
					labels = []
					values = []
					for p in info['scale_points']:
						labels.append(p['label'])
						values.append(p['value'])

					zctrls[symbol] = zynthian_controller(self, symbol, {
						'name': info['name'],
						'group_symbol': info['group_symbol'],
						'group_name': info['group_name'],
						'graph_path': info['index'],
						'value': info['value'],
						'labels': labels,
						'ticks': values,
						'value_min': values[0],
						'value_max': values[-1],
						'is_toggle': info['is_toggled'],
						'is_integer': info['is_integer'],
						'not_on_gui': info['not_on_gui'],
						'display_priority': info['display_priority']
					})

				# If it's a numeric controller ...
				else:
					if info['is_integer']:
						if info['is_toggled']:
							if info['value'] == 0:
								val = 'off'
							else:
								val = 'on'

							zctrls[symbol] = zynthian_controller(self, symbol, {
								'name': info['name'],
								'group_symbol': info['group_symbol'],
								'group_name': info['group_name'],
								'graph_path': info['index'],
								'value': val,
								'labels': ['off', 'on'],
								'ticks': [int(info['range']['min']), int(info['range']['max'])],
								'value_min': int(info['range']['min']),
								'value_max': int(info['range']['max']),
								'is_toggle': True,
								'is_integer': True,
								'not_on_gui': info['not_on_gui'],
								'display_priority': info['display_priority']
							})
						else:
							zctrls[symbol] = zynthian_controller(self, symbol, {
								'name': info['name'],
								'group_symbol': info['group_symbol'],
								'group_name': info['group_name'],
								'graph_path': info['index'],
								'value': int(info['value']),
								'value_default': int(info['range']['default']),
								'value_min': int(info['range']['min']),
								'value_max': int(info['range']['max']),
								'is_toggle': False,
								'is_integer': True,
								'is_logarithmic': info['is_logarithmic'],
								'not_on_gui': info['not_on_gui'],
								'display_priority': info['display_priority']
							})
					else:
						if info['is_toggled']:
							if info['value'] == 0:
								val = 'off'
							else:
								val = 'on'

							zctrls[symbol] = zynthian_controller(self, symbol, {
								'name': info['name'],
								'group_symbol': info['group_symbol'],
								'group_name': info['group_name'],
								'graph_path': info['index'],
								'value': val,
								'labels': ['off', 'on'],
								'ticks': [info['range']['min'], info['range']['max']],
								'value_min': info['range']['min'],
								'value_max': info['range']['max'],
								'is_toggle': True,
								'is_integer': False,
								'not_on_gui': info['not_on_gui'],
								'display_priority': info['display_priority']
							})
						else:
							zctrls[symbol] = zynthian_controller(self, symbol, {
								'name': info['name'],
								'group_symbol': info['group_symbol'],
								'group_name': info['group_name'],
								'graph_path': info['index'],
								'value': info['value'],
								'value_default': float(info['range']['default']),
								'value_min': float(info['range']['min']),
								'value_max': float(info['range']['max']),
								'is_toggle': False,
								'is_integer': False,
								'is_logarithmic': info['is_logarithmic'],
								'not_on_gui': info['not_on_gui'],
								'display_priority': info['display_priority']
							})

			# If control info is not OK
			except Exception as e:
				logging.error(e)

		# Sort by suggested display_priority
		new_index = sorted(zctrls, key=lambda x: zctrls[x].display_priority, reverse=True)
		zctrls = {k: zctrls[k] for k in new_index}

		return zctrls

	def get_monitors_dict(self):
		self.lv2_monitors_dict = {}
		for line in self.proc_cmd("monitors").split("\n"):
			try:
				parts=line.split(" = ")
				if len(parts) == 2:
					self.lv2_monitors_dict[parts[0]] = float(parts[1])
			except Exception as e:
				logging.error(e)

		return self.lv2_monitors_dict

	def get_controllers_dict(self, processor):
		# Get plugin static controllers
		zctrls = super().get_controllers_dict(processor)
		# Add plugin native controllers
		for zctrl in self.lv2_zctrl_dict.values():
			zctrl.set_options({"processor": processor})
		zctrls.update(self.lv2_zctrl_dict)
		return zctrls

	def send_controller_value(self, zctrl):
		self.proc_cmd("set %d %.6f" % (zctrl.graph_path, zctrl.value))

	# ---------------------------------------------------------------------------
	# API methods
	# ---------------------------------------------------------------------------

	@classmethod
	def init_zynapi_instance(cls, eng_code):
		if cls.zynapi_instance and cls.zynapi_instance.nickname != eng_code:
			cls.zynapi_instance.stop()
			cls.zynapi_instance = None

		if not cls.zynapi_instance:
			cls.zynapi_instance = cls(eng_code, None, True)
		else:
			logging.debug("\n\n********** REUSING INSTANCE for '{}'***********".format(eng_code))

	@classmethod
	def refresh_zynapi_instance(cls):
		if cls.zynapi_instance:
			zynthian_lv2.generate_presets_cache_workaround()
			zynthian_lv2.generate_plugin_presets_cache(cls.zynapi_instance.plugin_url)
			eng_code = cls.zynapi_instance.nickname
			cls.zynapi_instance.stop()
			cls.zynapi_instance = cls(eng_code, None, True)

	@classmethod
	def zynapi_get_banks(cls):
		banks = []
		for b in cls.zynapi_instance.get_bank_list():
			if b[2]:
				banks.append({
					'text': b[2],
					'name': b[2],
					'fullpath': b[0],
					'raw': b,
					'readonly': False if not b[0] or b[0].startswith("file:///") else True
				})
		return banks

	@classmethod
	def zynapi_get_presets(cls, bank):
		presets = []
		for p in cls.zynapi_instance.get_preset_list(bank['raw']):
			if p[2]:
				presets.append({
					'text': p[2],
					'name': p[2],
					'fullpath': p[0],
					'raw': p,
					'readonly': False if not p[0] or p[0].startswith("file:///") else True
				})
		return presets

	@classmethod
	def zynapi_rename_bank(cls, bank_path, new_bank_name):
		if bank_path.startswith("file:///"):
			cls.lv2_rename_bank(bank_path, new_bank_name)
			cls.refresh_zynapi_instance()
		else:
			raise Exception("Bank is read-only!")

	@classmethod
	def zynapi_remove_bank(cls, bank_path):
		if bank_path.startswith("file:///"):
			bundle_path, bank_name = os.path.split(bank_path)
			bundle_path = bundle_path[7:]
			shutil.rmtree(bundle_path)
			cls.refresh_zynapi_instance()
		else:
			raise Exception("Bank is read-only")

	@classmethod
	def zynapi_rename_preset(cls, preset_path, new_preset_name):
		if preset_path.startswith("file:///"):
			cls.lv2_rename_preset(preset_path, new_preset_name)
			cls.refresh_zynapi_instance()
		else:
			raise Exception("Preset is read-only!")

	@classmethod
	def zynapi_remove_preset(cls, preset_path):
		if preset_path.startswith("file:///"):
			cls.lv2_remove_preset(preset_path)
			cls.refresh_zynapi_instance()
		else:
			raise Exception("Preset is read-only")

	@classmethod
	def zynapi_download(cls, fullpath):
		if fullpath.startswith("file:///"):
			bundle_path, bank_name = os.path.split(fullpath)
			bundle_path = bundle_path[7:]
			return bundle_path
		else:
			raise Exception("Bank is not downloadable!")

	@classmethod
	def zynapi_install(cls, dpath, bank_path):
		fname, ext = os.path.splitext(dpath)
		native_ext = cls.zynapi_get_native_ext()

		# Try to copy LV2 bundles ...
		if os.path.isdir(dpath):
			# Find manifest.ttl
			manifest_files = check_output("find \"{}\" -type f -iname manifest.ttl".format(dpath), shell=True).decode("utf-8").split("\n")
			# Copy LV2 bundle directories to destiny ...
			count = 0
			for f in manifest_files:
				bpath, fname = os.path.split(f)
				head, bname = os.path.split(bpath)
				if bname:
					shutil.rmtree(zynthian_engine.my_data_dir + "/presets/lv2/" + bname, ignore_errors=True)
					shutil.move(bpath, zynthian_engine.my_data_dir + "/presets/lv2/")
					count += 1
			if count > 0:
				cls.refresh_zynapi_instance()
				return

		# Else, try to convert from native format ...
		if os.path.isdir(dpath) or ext[1:].lower()==native_ext:
			preset2lv2_cmd = "cd /tmp; /usr/local/bin/preset2lv2 {} \"{}\"".format(cls.zynapi_get_preset2lv2_format(), dpath)
			try:
				res = check_output(preset2lv2_cmd, stderr=STDOUT, shell=True).decode("utf-8")
				for bname in re.compile("Bundle '(.*)' generated").findall(res):
					bpath = "/tmp/" + bname
					logging.debug("Copying LV2-Bundle '{}' ...".format(bpath))
					shutil.rmtree(zynthian_engine.my_data_dir + "/presets/lv2/" + bname, ignore_errors=True)
					shutil.move(bpath, zynthian_engine.my_data_dir + "/presets/lv2/")

				cls.refresh_zynapi_instance()

			except Exception as e:
				raise Exception("Conversion from {} to LV2 failed! => {}".format(native_ext, e))

		else:
			raise Exception("Unknown preset format: {}".format(native_ext))

	@classmethod
	def zynapi_get_formats(cls):
		formats = "zip,tgz,tar.gz,tar.bz2"
		fmt = cls.zynapi_get_native_ext()
		if fmt:
			formats = fmt + "," + formats

		return formats

	@classmethod
	def zynapi_martifact_formats(cls):
		fmt = cls.zynapi_get_native_ext()
		if fmt:
			return fmt
		else:
			return "lv2"

	@classmethod
	def zynapi_get_native_ext(cls):
		try:
			return cls.plugin2native_ext[cls.zynapi_instance.plugin_name]
		except:
			return None

	@classmethod
	def zynapi_get_preset2lv2_format(cls):
		try:
			return cls.plugin2preset2lv2_format[cls.zynapi_instance.plugin_name]
		except:
			return None

	# --------------------------------------------------------------------------
	# LV2 Bundle TTL file manipulations
	# --------------------------------------------------------------------------

	@staticmethod
	def ttl_read_parts(fpath):
		with open(fpath, 'r') as f:
			data = f.read()
			parts = data.split(".\n")
		return parts

	@staticmethod
	def ttl_write_parts(fpath, parts):
		with open(fpath, 'w') as f:
			data = ".\n".join(parts)
			f.write(data)
			#logging.debug(data)

	@staticmethod
	def lv2_rename_bank(bank_path, new_bank_name):
		bank_path = bank_path[7:]
		bundle_path, bank_dname = os.path.split(bank_path)

		man_fpath = bundle_path + "/manifest.ttl"
		parts = zynthian_engine_jalv.ttl_read_parts(man_fpath)

		bmre1 = re.compile(r"<{}>".format(bank_dname))
		bmre2 = re.compile(r"(.*)a pset:Bank ;")
		brre = re.compile(r"([\s]+rdfs:label[\s]+\").*(\" )")
		for i, p in enumerate(parts):
			if bmre1.search(p) and bmre2.search(p):
				new_bank_name = zynthian_engine_jalv.sanitize_text(new_bank_name)
				parts[i] = brre.sub(lambda m: m.group(1)+new_bank_name+m.group(2), p)
				zynthian_engine_jalv.ttl_write_parts(man_fpath, parts)
				return

		raise Exception("Format doesn't match!")

	@staticmethod
	def lv2_rename_preset(preset_path, new_preset_name):
		preset_path = preset_path[7:]
		bundle_path, preset_fname = os.path.split(preset_path)

		man_fpath = bundle_path + "/manifest.ttl"
		man_parts = zynthian_engine_jalv.ttl_read_parts(man_fpath)
		prs_parts = zynthian_engine_jalv.ttl_read_parts(preset_path)

		bmre1 = re.compile(r"<{}>".format(preset_fname))
		bmre2 = re.compile(r"(.*)a pset:Preset ;")
		brre = re.compile("([\s]+rdfs:label[\s]+\").*(\" )")

		renamed = False
		for i, p in enumerate(man_parts):
			if bmre1.search(p) and bmre2.search(p):
				new_preset_name = zynthian_engine_jalv.sanitize_text(new_preset_name)
				man_parts[i] = brre.sub(lambda m: m.group(1) + new_preset_name + m.group(2), p)
				zynthian_engine_jalv.ttl_write_parts(man_fpath, man_parts)
				renamed = True #TODO: This overrides subsequent assertion in prs_parts
				break

		for i, p in enumerate(prs_parts):
			if bmre2.search(p):
				#new_preset_name = zynthian_engine_jalv.sanitize_text(new_preset_name)
				prs_parts[i] = brre.sub(lambda m: m.group(1) + new_preset_name + m.group(2), p)
				zynthian_engine_jalv.ttl_write_parts(preset_path, prs_parts)
				renamed = True
				break

		if not renamed:
			raise Exception("Format doesn't match!")

	@staticmethod
	def lv2_remove_preset(preset_path):
		preset_path = preset_path[7:]
		bundle_path, preset_fname = os.path.split(preset_path)

		man_fpath = bundle_path + "/manifest.ttl"
		parts = zynthian_engine_jalv.ttl_read_parts(man_fpath)

		bmre1 = re.compile(r"<{}>".format(preset_fname))
		bmre2 = re.compile(r"(.*)a pset:Preset ;")
		for i, p in enumerate(parts):
			if bmre1.search(p) and bmre2.search(p):
				del parts[i]
				zynthian_engine_jalv.ttl_write_parts(man_fpath, parts)
				os.remove(preset_path)
				return

	@staticmethod
	#   Remove a preset bank
	#   bank: Bank object to remove
	#   Returns: True on success
	def lv2_remove_bank(bank):
		try:
			path = bank[0][7:bank[0].rfind("/")]
		except Exception as e:
			return False

		try:
			with open("{}/manifest.ttl".format(path), "r") as manifest:
				lines = manifest.readlines()
		except Exception as e:
			return False

		bank_first_line = None
		bank_last_line = None
		for index, line in enumerate(lines):  # TODO: Use regexp to parse file
			if line.strip() == "<{}>".format(bank[2]):
				bank_first_line = index
			if bank_first_line is not None and line.strip()[-1:] == ".":
				bank_last_line = index
			if bank_last_line is not None:
				del lines[bank_first_line:bank_last_line + 1]
				break
		zynthian_engine.remove_double_spacing(lines)
		try:
			with open("{}/manifest.ttl".format(path), "w") as manifest:
				manifest.writelines(lines)
		except Exception as e:
			logging.error(e)

		# Remove bank reference from presets
		for file in os.listdir(path):
			if file[-4:] == ".ttl" and file != "manifest.ttl":
				bank_lines = []
				with open("{}/{}".format(path, file)) as ttl:
					lines = ttl.readlines()
				for index, line in enumerate(lines):
					if line.strip().startswith("pset:bank") and line.find("<{}>".format(bank[2])) > 0:
						bank_lines.append(index)
				if len(bank_lines):
					bank_lines.sort(reverse=True)
					for line in bank_lines:
						del lines[line]
					zynthian_engine.remove_double_spacing(lines)
					with open("{}/{}".format(path, file), "w") as ttl:
						ttl.writelines(lines)

		return True

	@staticmethod
	def sanitize_text(text):
		# Remove bad chars
		bad_chars = ['.', ',', ';', ':', '!', '*', '+', '?', '@', '&', '$', '%', '=', '"', '\'', '`', '/', '\\', '^', '<', '>', '[', ']', '(', ')', '{', '}']
		for i in bad_chars:
			text = text.replace(i, ' ')

		# Strip and replace (multi)spaces by single underscore
		text = '_'.join(text.split())
		text = '_'.join(filter(None, text.split('_')))

		return text

# ******************************************************************************
