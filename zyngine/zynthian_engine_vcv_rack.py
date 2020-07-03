# -*- coding: utf-8 -*-
#******************************************************************************
# ZYNTHIAN PROJECT: Zynthian Engine (zynthian_engine_vcv_rack)
# 
# zynthian_engine implementation for VCV Rack Synthesizer
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
import json
import logging
import subprocess

from . import zynthian_engine

def check_vcv_rack_binary():
	if os.path.isfile(VCV_RACK_BINARY) and os.access(VCV_RACK_BINARY, os.X_OK):
		return True
	else:
		return False

VCV_RACK_DIR = "{}/vcvrack.raspbian-v1".format(os.environ.get('ZYNTHIAN_SW_DIR', "/zynthian/zynthian-sw"))
VCV_RACK_BINARY = "{}/Rack".format(VCV_RACK_DIR)
VCV_RACK_CONFIG = "{}/settings.json".format(VCV_RACK_DIR)

VCV_RACK_PATCH_DIR = "{}/presets/vcvrack".format(zynthian_engine.my_data_dir)

class zynthian_engine_vcv_rack(zynthian_engine):

    #----------------------------------------------------------------------------
	# Initialization
	#----------------------------------------------------------------------------

	def __init__(self, zyngui=None):
		super().__init__(zyngui)

		self.type = "Special"
		self.name = "VCVRack"
		self.nickname = "VCV"
		self.jackname = "VCV Rack"

		self.options = {}

		# self.base_command = "xpra start-desktop :100 --start-child=\"{} -d\" --exit-with-children --xvfb=\"Xorg :10 vt7 -auth .Xauthority -config xrdp/xorg.conf -noreset -nolisten tcp\" --start-via-proxy=no --systemd-run=no --file-transfer=no --printing=no --resize-display=no --mdns=no --pulseaudio=no --dbus-proxy=no --dbus-control=no --webcam=no --notifications=no".format(VCV_RACK_BINARY)
		self.reset()

	def start(self):
		super().start()
		subprocess.run(["{}/start-vcv-rack.sh".format(VCV_RACK_DIR)])

	def stop(self):
		super().stop()
		subprocess.run(["{}/stop-vcv-rack.sh".format(VCV_RACK_DIR)])

	#----------------------------------------------------------------------------
	# Bank Managament
	#----------------------------------------------------------------------------

	def get_bank_list(self, layer=None):
		return self.get_filelist(VCV_RACK_PATCH_DIR, "vcv")


	def set_bank(self, layer, bank):
		self.load_bundle(bank[0])
		return True


	def load_bundle(self, path):
		with open(VCV_RACK_CONFIG, 'r') as config_file:
			config = json.load(config_file)
			config['patchPath'] = path
		with open(VCV_RACK_CONFIG, 'w') as config_file:
			json.dump(config, config_file, indent=4)
		self.start()


	# ---------------------------------------------------------------------------
	# API methods
	# ---------------------------------------------------------------------------

	@classmethod
	def zynapi_get_banks(cls):
		banks=[]
		for b in cls.get_filelist(VCV_RACK_PATCH_DIR, "vcv"):
			banks.append({
				'text': b[2],
				'name': b[2],
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
		new_bank_path = head + "/" + new_bank_name
		os.rename(bank_path, new_bank_path)


	@classmethod
	def zynapi_remove_bank(cls, bank_path):
		shutil.rmtree(bank_path)


	@classmethod
	def zynapi_download(cls, fullpath):
		return fullpath


	@classmethod
	def zynapi_install(cls, dpath, bank_path):
		if os.path.isdir(dpath):
			shutil.move(dpath, VCV_RACK_PATCH_DIR)

	@classmethod
	def zynapi_get_formats(cls):
		return "vcv"