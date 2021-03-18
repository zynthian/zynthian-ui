# -*- coding: utf-8 -*-
#******************************************************************************
# ZYNTHIAN PROJECT: Zynthian Engine (zynthian_engine_puredata)
#
# zynthian_engine implementation for PureData
#
# Copyright (C) 2015-2018 Fernando Moyano <jofemodo@zynthian.org>
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
import shutil
import logging
import subprocess
import oyaml as yaml
import socket
import pickle
from time import sleep
from collections import OrderedDict
from os.path import isfile,isdir,join

from . import zynthian_engine
from . import zynthian_controller

#------------------------------------------------------------------------------
# Puredata Engine Class
#------------------------------------------------------------------------------

class zynthian_engine_sdrradio(zynthian_engine):

	# ---------------------------------------------------------------------------
	# Controllers & Screens
	# ---------------------------------------------------------------------------
	corse_freqs = "88|89|90|91|92|93|94|95|96|97|98|99|100|101|102|103|104|105|106|107"
	_ctrls=[
		['volume',7,60,100],
		['corse tune', 39 , '97' , corse_freqs ],
		['fine tune', 32 , 7 , 9]
		
	]

	_ctrl_screens=[
		['main',['volume','corse tune','fine tune']]
	]


	#----------------------------------------------------------------------------
	# Config variables
	#----------------------------------------------------------------------------
	HOST, PORT = "localhost", 2345
	startup_patch = zynthian_engine.my_data_dir + "/playlist/RadioX.pls"
	mplayer_ctrl_fifo_path = "/tmp/radio-control"
	bank_dirs = [
		('EX', zynthian_engine.ex_data_dir + "/playlist/"),
		('MY', zynthian_engine.my_data_dir + "/playlist/"),
		('_', zynthian_engine.data_dir + "/playlist/")
	]

	#----------------------------------------------------------------------------
	# Initialization
	#----------------------------------------------------------------------------

	def __init__(self, zyngui=None):
		super().__init__(zyngui)

		self.type = "Special"
		self.name = "Radio"
		self.nickname = "RD"
		self.jackname = "radio"

		#self.options['midi_chan']=False

		self.preset = ""
		self.preset_config = None
		fpath = "/zynthian/zynthian-my-data/playlist/RadioX.pls"
		self.corse_var = "97"
		self.fine_var = "7"
		self.base_command="/usr/bin/mplayer -nogui -noconsolecontrols -cache 1024 -nolirc -nojoystick -really-quiet -slave -ao jack:name={} -input file={} -playlist  ".format(self.jackname, self.mplayer_ctrl_fifo_path)

		self.reset()

	def reset(self):
		super().reset()
		self.soundfont_index={}

	# ---------------------------------------------------------------------------
	# Layer Management
	# ---------------------------------------------------------------------------

	# ---------------------------------------------------------------------------
	# MIDI Channel Management
	# ---------------------------------------------------------------------------

	#----------------------------------------------------------------------------
	# Bank Managament
	#----------------------------------------------------------------------------

	def get_bank_list(self, layer=None):
		logging.debug(self.bank_dirs)
		return self.get_dirlist(self.bank_dirs)

	#----------------------------------------------------------------------------
	# Preset Managament
	#----------------------------------------------------------------------------

	def get_preset_list(self, bank):
		logging.debug(bank)
		return self.get_filelist(bank[0],"pls") + self.get_filelist(bank[0],"m3u") + self.get_filelist(bank[0],"m3u8")



	def set_preset(self, layer, preset, preload=False):
		logging.debug(preset)
		# Create control fifo is needed ...
		try:
			os.mkfifo(self.mplayer_ctrl_fifo_path)
		except:
			pass

		#self.load_preset_config(preset)
		#self.command=self.base_command+ " " + self.get_preset_filepath(preset)
		self.command=self.base_command+ " " + preset[0]

		self.preset=preset[0]
		self.stop()
		self.start()
		self.refresh_all()
		#self.send_controller_value(self.volume_zctrl)
		sleep(0.3)
		self.zyngui.zynautoconnect()
		#layer.send_ctrl_midi_cc()
		return True


	def load_preset_config(self, preset):
		config_fpath = preset[0] + "/zynconfig.yml"
		try:
			with open(config_fpath,"r") as fh:
				yml = fh.read()
				logging.info("Loading preset config file %s => \n%s" % (config_fpath,yml))
				self.preset_config = yaml.load(yml, Loader=yaml.SafeLoader)
				return True
		except Exception as e:
			logging.error("Can't load preset config file '%s': %s" % (config_fpath,e))
			return False


	def get_preset_filepath(self, preset):
		preset_fpath = zynthian_engine.my_data_dir + "/playlist/RadioX.pls"	
#		if self.preset_config:
#			preset_fpath = preset[0] + "/" + self.preset_config['main_file']
#			if isfile(preset_fpath):
#				return preset_fpath
#
#		preset_fpath = preset[0] + "/main.pd"
#		if isfile(preset_fpath):
#			return preset_fpath
#		
#		preset_fpath = preset[0] + "/" + os.path.basename(preset[0]) + ".pls"
#		if isfile(preset_fpath):
#			return preset_fpath
#		
		return preset_fpath



	def cmp_presets(self, preset1, preset2):
		return True

	#----------------------------------------------------------------------------
	# Controllers Managament
	#----------------------------------------------------------------------------

	# Get zynthian controllers dictionary:
	# + Default implementation uses a static controller definition array

	def rtlsdr_connect(self):
		logging.info("Connecting with rtl_fm_streamer Server...")
		self.sock=socket.socket(socket.AF_INET,socket.SOCK_STREAM)
		self.sock.setblocking(0)
		self.sock.settimeout(1)
		i=0
		while i<20:
			try:
				self.sock.connect(("127.0.0.1",2345))
				break
			except:
				sleep(0.25)
				i+=1
		return self.sock




	def send_mplayer_command(self, cmd):
		logging.debug(cmd + " " + self.mplayer_ctrl_fifo_path)
		with open(self.mplayer_ctrl_fifo_path, "w") as f:
			f.write(cmd + "\n")
			f.close()

	def send_tune_fm_streamer(self, tunefreq):
		logging.debug(tunefreq)
		freq = '{"method": "SetFrequency", "params": ['+ tunefreq+ '00000]}\r\n'
		logging.debug("Thing to sent: {}".format(freq))
		self.rtlsdr_connect()
		try:
			self.sock.send(freq.encode())
			recieve = self.sock.recv(4096)
		except Exception as err:
			logging.error("FAILED rtlsdr_send: %s" % err)
		logging.debug(recieve)


	def send_controller_value(self, zctrl):
		if zctrl.symbol=='volume':
			logging.debug("SET PLAYING VOLUME => {}".format(zctrl.value))
			self.send_mplayer_command("volume {} 1".format(zctrl.value))
		if zctrl.symbol=='corse tune':
			self.corse_var = self.retnum(str(zctrl.value))
			logging.debug("SET CORSE TUNE => {} {}".format(self.corse_var, self.fine_var))
			self.send_tune_fm_streamer(self.corse_var+self.fine_var)
		if zctrl.symbol=='fine tune':
			self.fine_var = str(zctrl.value)
			logging.debug("SET FINE TUNE => {} {}".format(zctrl.value, self.corse_var))
			self.send_tune_fm_streamer(self.corse_var+str(zctrl.value))
	def retnum(self, x):
		numfreq = {
			'0': '88',
			'6': '89',
			'12': '90',
			'19': '91',
			'25': '92',
			'32': '93',
			'38': '94',
			'44': '95',
			'51': '96',
			'57': '97',
			'64': '98',
			'70': '99',
			'76': '100',
			'83': '101',
			'89': '102',
			'96': '103',
			'102': '104',
			'108': '105',
			'115': '106',
			'121': '107'
		}
		return numfreq.get(x)
	#--------------------------------------------------------------------------
	# Special
	#--------------------------------------------------------------------------

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
		for p in cls.get_dirlist(bank['fullpath']):
			presets.append({
				'text': p[4],
				'name': p[2],
				'fullpath': p[0],
				'raw': p,
				'readonly': False
			})
		return presets


	@classmethod
	def zynapi_new_bank(cls, bank_name):
		os.mkdir(zynthian_engine.my_data_dir + "/presets/puredata/" + bank_name)


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
		new_preset_path = head + "/" + new_preset_name
		os.rename(preset_path, new_preset_path)


	@classmethod
	def zynapi_remove_preset(cls, preset_path):
		shutil.rmtree(preset_path)


	@classmethod
	def zynapi_download(cls, fullpath):
		return fullpath


	@classmethod
	def zynapi_install(cls, dpath, bank_path):
		if os.path.isdir(dpath):
			shutil.move(dpath, bank_path)
			#TODO Test if it's a PD bundle
		else:
			fname, ext = os.path.splitext(dpath)
			if ext=='.pd':
				bank_path += "/" + fname
				os.mkdir(bank_path)
				shutil.move(dpath, bank_path)
			else:
				raise Exception("File doesn't look like a PD patch!")


	@classmethod
	def zynapi_get_formats(cls):
		return "pd,zip,tgz,tar.gz,tar.bz2r,pls,m3u,m3u8"


#******************************************************************************
