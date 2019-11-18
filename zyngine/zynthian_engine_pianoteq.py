# -*- coding: utf-8 -*-
#******************************************************************************
# ZYNTHIAN PROJECT: Zynthian Engine (zynthian_engine_pianoteq)
#
# zynthian_engine implementation for Pianoteq6-Stage
#
# Copyright (C) 2015-2018 Fernando Moyano <jofemodo@zynthian.org>
# 			  Holger Wirtz <holger@zynthian.org>
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
import time
import shutil
import struct
import subprocess
from collections import defaultdict
from os.path import isfile,isdir,join
from xml.etree import ElementTree
from json import JSONEncoder, JSONDecoder

from . import zynthian_engine

#------------------------------------------------------------------------------
# Pianoteq module helper functions
#------------------------------------------------------------------------------

def ensure_dir(file_path):
	directory=os.path.dirname(file_path)
	if not os.path.exists(directory):
		os.makedirs(directory)


def check_pianoteq_binary():
	if os.path.islink(PIANOTEQ_BINARY) and not os.access(PIANOTEQ_BINARY, os.X_OK):
		os.remove(PIANOTEQ_BINARY)

	if not os.path.isfile(PIANOTEQ_BINARY):
		try:
			os.symlink(PIANOTEQ_SW_DIR + "/Pianoteq 6 STAGE", PIANOTEQ_BINARY)
		except:
			return False

	if os.path.isfile(PIANOTEQ_BINARY) and os.access(PIANOTEQ_BINARY, os.X_OK):
		return True
	else:
		return False


# Get product, trial and version info from pianoteq binary
def get_pianoteq_binary_info():
	res=None
	if check_pianoteq_binary():
		version_pattern = re.compile(" version ([0-9]+\.[0-9]+\.[0-9]+)", re.IGNORECASE)
		stage_pattern = re.compile(" stage ", re.IGNORECASE)
		pro_pattern = re.compile(" pro ", re.IGNORECASE)
		trial_pattern = re.compile(" trial ",re.IGNORECASE)
		proc=subprocess.Popen([PIANOTEQ_BINARY,"--version"],stdout=subprocess.PIPE)
		for line in proc.stdout:
			l=line.rstrip().decode("utf-8")
			m = version_pattern.search(l)
			if m:
				res={}
				# Get version info
				res['version'] = m.group(1)
				# Get trial info
				m=trial_pattern.search(l)
				if m:
					res['trial'] = 1
				else:
					res['trial'] = 0
				# Get product info
				m = stage_pattern.search(l)
				if m:
					res['product'] = "STAGE"
				else:
					m = pro_pattern.search(l)
					if m:
						res['product'] = "PRO"
					else:
						res['product'] = "STANDARD"
	return res


def get_pianoteq_subl():
	subl=[]
	if os.path.isfile(PIANOTEQ_CONFIG_FILE):
		root = ElementTree.parse(PIANOTEQ_CONFIG_FILE)
		for xml_value in root.iter("VALUE"):
			if xml_value.attrib['name']=='subl':
				subl=xml_value.attrib['val'].split(';')
	return subl


def fix_pianoteq_config():
	if os.path.isfile(PIANOTEQ_CONFIG_FILE):
		tree = ElementTree.parse(PIANOTEQ_CONFIG_FILE)
		root= tree.getroot()
		try:
			audio_setup_node =  None
			midi_setup_node = None
			for xml_value in root.iter("VALUE"):
				if xml_value.attrib['name']=='engine_rate':
					xml_value.set('val',str(PIANOTEQ_CONFIG_INTERNAL_SR))
				elif xml_value.attrib['name']=='voices':
					xml_value.set('val',str(PIANOTEQ_CONFIG_VOICES))
				elif xml_value.attrib['name']=='multicore':
					xml_value.set('val',str(PIANOTEQ_CONFIG_MULTICORE))
				elif xml_value.attrib['name']=='midiArchiveEnabled':
					xml_value.set('val','0')
				elif xml_value.attrib['name']=='audio-setup':
					audio_setup_node = xml_value
				elif xml_value.attrib['name']=='midi-setup':
					midi_setup_node = xml_value

			if audio_setup_node:
				logging.debug("Fixing Audio Setup")
				for devicesetup in audio_setup_node.iter('DEVICESETUP'):
					devicesetup.set('deviceType','JACK')
					devicesetup.set('audioOutputDeviceName','Auto-connect ON')
					devicesetup.set('audioInputDeviceName','Auto-connect ON')
					devicesetup.set('audioDeviceRate','44100')
					devicesetup.set('forceStereo','0')
			else:
				logging.debug("Creating new Audio Setup")
				value = ElementTree.Element('VALUE')
				value.set('name','audio-setup')
				devicesetup = ElementTree.SubElement(value,'DEVICESETUP')
				devicesetup.set('deviceType','JACK')
				devicesetup.set('audioOutputDeviceName','Auto-connect ON')
				devicesetup.set('audioInputDeviceName','Auto-connect ON')
				devicesetup.set('audioDeviceRate','44100')
				devicesetup.set('forceStereo','0')
				root.append(value)

			if midi_setup_node:
				logging.debug("Fixing MIDI Setup ")
				for midisetup in midi_setup_node.iter('midi-setup'):
					midisetup.set('listen-all','0')
			else:
				logging.debug("Creating new MIDI Setup")
				value = ElementTree.Element('VALUE')
				value.set('name','midi-setup')
				midisetup = ElementTree.SubElement(value,'midi-setup')
				midisetup.set('listen-all','0')
				root.append(value)

			tree.write(PIANOTEQ_CONFIG_FILE)

		except Exception as e:
			logging.error("Fixing Pianoteq config failed: {}".format(e))
			return format(e)


#------------------------------------------------------------------------------
# Pianoteq module constants & parameter configuration/initialization
#------------------------------------------------------------------------------

PIANOTEQ_SW_DIR = os.environ.get('ZYNTHIAN_SW_DIR',"/zynthian/zynthian-sw") + "/pianoteq6"
PIANOTEQ_BINARY = PIANOTEQ_SW_DIR + "/pianoteq"

PIANOTEQ_CONFIG_DIR = os.path.expanduser("~")  + "/.config/Modartt"
PIANOTEQ_DATA_DIR = os.path.expanduser("~")  + '/.local/share/Modartt/Pianoteq'
PIANOTEQ_ADDON_DIR = PIANOTEQ_DATA_DIR + '/Addons'
PIANOTEQ_MY_PRESETS_DIR = PIANOTEQ_DATA_DIR + '/Presets'
PIANOTEQ_MIDIMAPPINGS_DIR = PIANOTEQ_DATA_DIR + '/MidiMappings'

try:
	PIANOTEQ_VERSION=list(map(int, os.environ.get('PIANOTEQ_VERSION').split(".")))
	PIANOTEQ_PRODUCT=os.environ.get('PIANOTEQ_PRODUCT')
	PIANOTEQ_TRIAL=int(os.environ.get('PIANOTEQ_TRIAL'))
except:
	info = get_pianoteq_binary_info()
	if info:
		PIANOTEQ_VERSION=list(map(int, str(info['version']).split(".")))
		PIANOTEQ_PRODUCT=str(info['product'])
		PIANOTEQ_TRIAL=int(info['trial'])
	else:
		PIANOTEQ_VERSION=[6,5,1]
		PIANOTEQ_PRODUCT="STAGE"
		PIANOTEQ_TRIAL=1

PIANOTEQ_NAME="Pianoteq{}{}".format(PIANOTEQ_VERSION[0],PIANOTEQ_VERSION[1])

if PIANOTEQ_VERSION[0]>6 or (PIANOTEQ_VERSION[0]==6 and PIANOTEQ_VERSION[1]>=5):
	PIANOTEQ_JACK_PORT_NAME="Pianoteq"
else:
	PIANOTEQ_JACK_PORT_NAME=PIANOTEQ_NAME

if PIANOTEQ_PRODUCT=="STANDARD":
	PIANOTEQ_CONFIG_FILENAME = "{}.prefs".format(PIANOTEQ_NAME)
else:
	PIANOTEQ_CONFIG_FILENAME = "{} {}.prefs".format(PIANOTEQ_NAME, PIANOTEQ_PRODUCT)

PIANOTEQ_CONFIG_FILE =  PIANOTEQ_CONFIG_DIR + "/" + PIANOTEQ_CONFIG_FILENAME

if PIANOTEQ_VERSION[1]==0:
	PIANOTEQ_CONFIG_INTERNAL_SR=22050
	PIANOTEQ_CONFIG_VOICES=32
	PIANOTEQ_CONFIG_MULTICORE=1
else:
	PIANOTEQ_CONFIG_INTERNAL_SR=22050
	PIANOTEQ_CONFIG_VOICES=32
	PIANOTEQ_CONFIG_MULTICORE=2


#------------------------------------------------------------------------------
# Piantoteq Engine Class
#------------------------------------------------------------------------------

class zynthian_engine_pianoteq(zynthian_engine):

	# ---------------------------------------------------------------------------
	# Banks
	# ---------------------------------------------------------------------------

	bank_list_v6_6 = [
        ('Celtic Harp', 0, 'Celtic Harp', 'Celtic Harp:A')
	]

	bank_list_v6_5 = [
		('Kalimba', 0, 'Kalimba', 'Kalimba:A')
	]

	bank_list_v6_4 = [
		('C. Bechstein DG', 0, 'C. Bechstein DG', 'BechsteinDG:A')
	]

	bank_list_v6_3=[
		('Ant. Petrof', 0, 'Ant. Petrof', 'Antpetrof:A')
	]

	bank_list=[
		('Steinway D', 1, 'Steinway D', 'D4:A'),
		('Steinway B', 2, 'Steinway B', 'Modelb:A'),
		('Steingraeber', 3, 'Steingraeber', 'Steingraeber:A'),
		('Grotrian', 4, 'Grotrian', 'Grotrian:A'),
		('Bluethner', 5, 'Bluethner', 'Bluethner:A'),
		('YC5', 6, 'YC5', 'Rock:A'),
		('K2', 7, 'K2', 'K2:A'),
		('U4', 8, 'U4', 'U4:A'),
		('MKI', 9, 'MKI', 'Electric:A'),
		('MKII', 10, 'MKII', 'Electric:A'),
		('W1', 11, 'W1', 'Electric:A'),
		('Clavinet D6', 12, 'Clavinet D6', 'Clavinet:A'),
		('Pianet N', 13, 'Pianet N', 'Clavinet:A'),
		('Pianet T', 14, 'Pianet T', 'Clavinet:A'),
		('Electra', 15, 'Electra', 'Clavinet:A'),
		('Vibraphone V-B', 16, 'Vibraphone V-B', 'Vibes:A'),
		('Vibraphone V-M', 17, 'Vibraphone V-M', 'Vibes:A'),
		('Celesta', 18, 'Celesta', 'Celeste:A'),
		('Glockenspiel', 19, 'Glockenspiel', 'Celeste:A'),
		('Toy Piano', 20, 'Toy Piano', 'Celeste:A'),
		('Marimba', 21, 'Marimba', 'Xylo:A'),
		('Xylophone', 22, 'Xylophone', 'Xylo:A'),
		('Steel Drum', 23, 'Steel Drum', 'Steel:A'),
		('Spacedrum', 24, 'Spacedrum', 'Steel:A'),
		('Hand Pan', 25, 'Hand Pan', 'Steel:A'),
		('Tank Drum', 26, 'Tank Drum', 'Steel:A'),
		('H. Ruckers II Harpsichord', 27, 'H. Ruckers II Harpsichord', 'Harpsichord:A'),
		('Concert Harp', 28, 'Concert Harp', 'Harp:A'),
		('J. Dohnal', 29, 'J. Dohnal', 'Kremsegg1:A'),
		('I. Besendorfer', 30, 'I. Besendorfer', 'Kremsegg1:A'),
		('S. Erard', 31, 'S. Erard', 'Kremsegg1:A'),
		('J.B. Streicher', 32 , 'J.B. Streicher', 'Kremsegg1:A'),
		('J. Broadwood', 33, 'J. Broadwood', 'Kremsegg2:A'),
		('I. Pleyel', 34, 'I. Pleyel', 'Kremsegg2:A'),
		('J. Frenzel', 35, 'J. Frenzel', 'Kremsegg2:A'),
		('C. Bechstein', 36, 'C. Bechstein', 'Kremsegg2:A'),
		('Cimbalom', 37, 'Cimbalom', 'KIViR'),
		('Neupert Clavichord', 38, 'Neupert Clavichord', 'KIViR'),
		('F.E. Blanchet Harpsichord', 39, 'F.E. Blanchet Harpsichord', 'KIViR'),
		('C. Grimaldi Harpsichord', 40, 'C. Grimaldi Harpsichord', 'KIViR'),
		('J. Schantz', 41, 'J. Schantz', 'KIViR'),
		('J.E. Schmidt', 42, 'J.E. Schmidt', 'KIViR'),
		('A. Walter', 43, 'A. Walter', 'KIViR'),
		('D. Schoffstoss', 44, 'D. Schoffstoss', 'KIViR'),
		('C. Graf', 45, 'C. Graf', 'KIViR'),
		('Erard', 46, 'Erard', 'KIViR'),
		('Pleyel', 47, 'Pleyel', 'KIViR'),
		('CP-80', 48, 'CP-80', 'KIViR'),
		('Church Bells', 49, 'Church Bells', 'bells'),
		('Tubular Bells', 50, 'Tubular Bells', 'bells')
	]

	free_instruments = [
		'bells',
		'KIViR'
	]

	spacer_demo_bank = [
		(None, 0, '---- DEMO Instruments ----')
	]

	# ---------------------------------------------------------------------------
	# Controllers & Screens
	# ---------------------------------------------------------------------------

	_ctrls=[
		['volume',7,96],
		['dynamic',85,64],
		['mute on/off',19,'off','off|on'],
		['sustain',64,'off',[['off','1/4','1/2','3/4','full'],[0,25,51,76,102]]],
		#['sustain on/off',64,'off','off|on'],
		#['sustain',64,0],
		#['rev on/off',30,'off','off|on'],
		#['rev duration',31,0],
		#['rev mix',32,0],
		#['rev room',33,0],
		#['rev p/d',34,0],
		#['rev e/r',35,64],
		#['rev tone',36,64]
	]

	_ctrl_screens=[
		['main',['volume','sustain','dynamic','mute on/off']]
		#['reverb1',['volume','rev on/off','rev duration','rev mix']],
		#['reverb2',['volume','rev room','rev p/d','rev e/r']],
		#['reverb3',['volume','rev tone']]
	]

	#----------------------------------------------------------------------------
	# Config Variables
	#----------------------------------------------------------------------------

	user_presets_dpath = PIANOTEQ_MY_PRESETS_DIR
	user_presets_flist = None

	#----------------------------------------------------------------------------
	# Initialization
	#----------------------------------------------------------------------------

	def __init__(self, zyngui=None, update_presets_cache=False):
		super().__init__(zyngui)
		self.name = PIANOTEQ_NAME
		self.nickname = "PT"
		self.jackname = PIANOTEQ_JACK_PORT_NAME

		self.options['midi_chan']=False

		self.preset = ""
		self.midimapping = "ZynthianControllers"

		if self.config_remote_display():
			self.proc_start_sleep = 5
			self.command_prompt = None
			if PIANOTEQ_VERSION[0]==6 and PIANOTEQ_VERSION[1]==0:
				self.base_command = PIANOTEQ_BINARY
			else:
				self.base_command = PIANOTEQ_BINARY + " --multicore max"
		else:
			self.command_prompt = "Current preset:"
			if PIANOTEQ_VERSION[0]==6 and PIANOTEQ_VERSION[1]==0:
				self.base_command = PIANOTEQ_BINARY + " --headless"
			else:
				self.base_command = PIANOTEQ_BINARY + " --headless --multicore max"

		# Create & fix Pianoteq config
		if not os.path.isfile(PIANOTEQ_CONFIG_FILE):
			logging.debug("Pianoteq configuration does not exist. Creating one...")
			ensure_dir(PIANOTEQ_CONFIG_DIR + "/")
			if os.path.isfile(self.data_dir + "/pianoteq6/" + PIANOTEQ_CONFIG_FILENAME):
				shutil.copy(self.data_dir + "/pianoteq6/" + PIANOTEQ_CONFIG_FILENAME, PIANOTEQ_CONFIG_DIR)
			else:
				shutil.copy(self.data_dir + "/pianoteq6/Pianoteq6.prefs", PIANOTEQ_CONFIG_FILE)

		fix_pianoteq_config()

		# Prepare bank list
		self.prepare_banks()

		# Create "My Presets" directory if not already exist
		if not os.path.exists(self.user_presets_dpath):
			os.makedirs(self.user_presets_dpath)

		# Load (and generate if need it) the preset list
		self.presets = defaultdict(list)
		self.presets_cache_fpath = self.config_dir + '/pianoteq6/presets_cache.json'
		if os.path.isfile(self.presets_cache_fpath) and not update_presets_cache:
			self.load_presets_cache()
		else:
			self.save_presets_cache()

		self.load_user_presets()
		self.purge_banks()
		self.generate_presets_midimapping()


	# ---------------------------------------------------------------------------
	# Layer Management
	# ---------------------------------------------------------------------------

	# ---------------------------------------------------------------------------
	# MIDI Channel Management
	# ---------------------------------------------------------------------------

	def set_midi_chan(self, layer):
		self.stop()
		self.command = self.base_command + ("--midi-channel", str(layer.get_midi_chan()+1),)

	#----------------------------------------------------------------------------
	# Bank Managament
	#----------------------------------------------------------------------------

	# Get user banks
	@classmethod
	def get_user_banks(cls):
		cls.user_presets_flist = cls.get_user_preset_files()
		user_banks = []
		for bank in cls.bank_list:
			user_presets = cls.get_user_presets(bank)
			if len(user_presets)>0:
				user_banks.append(list(bank) + [bank[2]])
		return user_banks


	def get_bank_list(self, layer=None):
		return self.bank_list


	def set_bank(self, layer, bank):
		return True


	def prepare_banks(self):
		if PIANOTEQ_VERSION[0]>=6 and PIANOTEQ_VERSION[1]>=3:
			self.bank_list = self.bank_list_v6_3 + self.bank_list

		if PIANOTEQ_VERSION[0]>=6 and PIANOTEQ_VERSION[1]>=4:
			self.bank_list = self.bank_list_v6_4 + self.bank_list

		if PIANOTEQ_VERSION[0]>=6 and PIANOTEQ_VERSION[1]>=5:
			self.bank_list = self.bank_list_v6_5 + self.bank_list

		if PIANOTEQ_VERSION[0]>=6 and PIANOTEQ_VERSION[1]>=6:
			self.bank_list = self.bank_list_v6_6 + self.bank_list

		if not PIANOTEQ_TRIAL:
			# Separate Licensed from Free and Demo
			subl = get_pianoteq_subl()
			if subl:
				free_banks = []
				licensed_banks = []
				unlicensed_banks = []
				for bank in self.bank_list:
					if bank[3].upper() in map(str.upper, subl):
						licensed_banks.append(bank)
					elif bank[3].upper() in map(str.upper, self.free_instruments):
						free_banks.append(bank)
					else:
						unlicensed_banks.append(bank)
				self.bank_list = licensed_banks + free_banks + self.spacer_demo_bank + unlicensed_banks


	#----------------------------------------------------------------------------
	# Preset Managament
	#----------------------------------------------------------------------------


	def save_presets_cache(self):
		logging.info("Caching Internal Presets ...")
		#Get internal presets from Pianoteq ...
		try:
			pianoteq=subprocess.Popen([PIANOTEQ_BINARY, "--list-presets"],stdout=subprocess.PIPE)
			bank_list = sorted(self.bank_list, key=lambda bank: len(bank[0]) if bank[0] else 0, reverse=True)
			for line in pianoteq.stdout:
				l=line.rstrip().decode("utf-8")
				logging.debug("PRESET => {}".format(l))
				for bank in bank_list:
					try:
						b=bank[0]
						if b:
							if b==l:
								self.presets[b].append([l,None,'<default>',None])
								break
							elif b+' '==l[0:len(b)+1]:
								#logging.debug("'%s' == '%s'" % (b,l[0:len(b)]))
								preset_title=l[len(b):].strip()
								preset_title=re.sub('^- ','',preset_title)
								self.presets[b].append([l,None,preset_title,None])
								break
					except:
						pass
		except Exception as e:
			logging.error("Can't get internal presets: %s" %e)
			return False
		#Encode JSON
		try:
			json=JSONEncoder().encode(self.presets)
			logging.info("Saving presets cache '%s' => \n%s" % (self.presets_cache_fpath,json))
		except Exception as e:
			logging.error("Can't generate JSON while saving presets cache: %s" %e)
			return False
		#Write to file
		ensure_dir(self.presets_cache_fpath)
		try:
			with open(self.presets_cache_fpath,"w") as fh:
				fh.write(json)
				fh.flush()
				os.fsync(fh.fileno())
		except Exception as e:
			logging.error("Can't save presets cache '%s': %s" % (self.presets_cache_fpath,e))
			return False
		return True


	def load_presets_cache(self):
		#Load from file
		try:
			with open(self.presets_cache_fpath,"r") as fh:
				json=fh.read()
				logging.info("Loading presets cache %s => \n%s" % (self.presets_cache_fpath,json))
		except Exception as e:
			logging.error("Can't load presets cache '%s': %s" % (self.presets_cache_fpath,e))
			return False
		#Decode JSON
		try:
			self.presets=JSONDecoder().decode(json)
		except Exception as e:
			logging.error("Can't decode JSON while loading presets cache: %s" % e)
			return False
		return True


	# Get user preset file list
	@classmethod
	def get_user_preset_files(cls):
		flist = []
		for d in sorted(os.listdir(cls.user_presets_dpath)):
			for f in sorted(os.listdir(cls.user_presets_dpath + "/" + d)):
				flist.append(d + "/" + f)
		return flist


	# Get user presets
	@classmethod
	def get_user_presets(cls, bank):
		user_presets = []
		if bank[0]:
			bank_name = bank[0]
			bank_prefix = bank_name + " "
			logging.debug("Getting User presets for {}".format(bank_name))
			for f in cls.user_presets_flist:
				if (isfile(join(cls.user_presets_dpath,f)) and f[-4:].lower()==".fxp"):
					dbank,fname = f.split("/",1)
					if bank_prefix==fname[0:len(bank_prefix)]:
						preset_path = dbank + "/" + fname[:-4]
						preset_title = dbank + "/" + str.replace(fname[len(bank_prefix):-4], '_', ' ').strip()
						user_presets.append([preset_path,None,preset_title,None,dbank])
		return user_presets


	# Get user presets
	def load_user_presets(self):
		type(self).user_presets_flist = self.get_user_preset_files()
		for bank in self.bank_list:
			user_presets = self.get_user_presets(bank)
			if len(user_presets)>0:
				#Add internal presets
				bank_name = bank[0]
				try:
					self.presets[bank_name] = user_presets + self.presets[bank_name]
				except:
					self.presets[bank_name] = user_presets


	# Remove banks without presets
	def purge_banks(self):
		logging.debug("Purge Banks ...")
		purged_bank_list=[]
		for bank in self.bank_list:
			try:
				if not bank[0] or (bank[0] in self.presets and len(self.presets[bank[0]])>0):
					purged_bank_list.append(bank)
			except:
				pass
		self.bank_list=purged_bank_list


	def get_preset_list(self, bank):
		bank_name = bank[0]
		if bank_name in self.presets:
			logging.info("Getting Preset List for %s [%s]" % (self.name,bank_name))
			res = self.presets[bank_name]
		else:
			logging.error("Can't get Preset List for %s [%s]" % (self.name,bank_name))
			res = []
		return res


	def set_preset(self, layer, preset, preload=False):
		mm = "Zynthian-{}".format(preset[3])
		if mm == self.midimapping:
			super().set_preset(layer,preset,preload)
			self.preset = preset[0]
			time.sleep(1)
		else:
			self.midimapping=mm
			self.preset=preset[0]
			self.command = self.base_command + " --midi-channel {}".format(layer.get_midi_chan()+1)
			self.command += " --midimapping \"{}\"".format(self.midimapping)
			self.command += " --preset \"{}\"".format(preset[0])
			self.stop()
			self.start()
			self.zyngui.zynautoconnect(True)

		layer.send_ctrl_midi_cc()
		return True


	def cmp_presets(self, preset1, preset2):
		try:
			if preset1[0]==preset2[0] and preset1[2]==preset2[2]:
				return True
			else:
				return False
		except:
			return False


	#--------------------------------------------------------------------------
	# Special
	#--------------------------------------------------------------------------


	def generate_presets_midimapping(self):
		# Copy default "static" MIDI Mappings if doesn't exist
		if not os.path.isfile(PIANOTEQ_MIDIMAPPINGS_DIR + "/ZynthianControllers.ptm"):
			logging.debug("Pianoteq Base MIDI-Mapping does not exist. Creating ...")
			ensure_dir(PIANOTEQ_MIDIMAPPINGS_DIR + "/")
			shutil.copy(self.data_dir + "/pianoteq6/Zynthian.ptm", PIANOTEQ_MIDIMAPPINGS_DIR + "/ZynthianControllers.ptm")

		# Generate "Program Change" for Presets as MIDI-Mapping registers using Pianoteq binary format
		mmn = 0
		data = []
		for bank in self.bank_list:
			if bank[0] in self.presets:
				for prs in self.presets[bank[0]]:
					try:
						#logging.debug("Generating Pianoteq MIDI-Mapping for {}".format(prs[0]))
						midi_event_str = bytes("Program Change " + str(len(data)+1),"utf8")
						action_str = bytes("{LoadPreset|28||" + prs[0] + "|0}","utf8")
						row = b'\x01\x00\x00\x00'
						row += struct.pack("<I",len(midi_event_str)) + midi_event_str
						row += struct.pack("<I",len(action_str)) + action_str
						prs[1] = len(data)
						prs[3] = mmn
						data.append(row)
						if len(data)>127:
							self.create_midimapping_file(mmn, data)
							mmn += 1
							data = []
					except Exception as e:
						logging.error(e)

		if len(data)>0:
			self.create_midimapping_file(mmn, data)


	def create_midimapping_file(self, mmn, data):
		# Create a new file copying from "static" Controllers Mappging and adding the "generated" Presets Mappgings
		fpath=PIANOTEQ_MIDIMAPPINGS_DIR + "/Zynthian-{}.ptm".format(mmn)
		logging.debug("Generating Pianoteq MIDI-Mapping: {}".format(fpath))
		shutil.copy(PIANOTEQ_MIDIMAPPINGS_DIR + "/ZynthianControllers.ptm", fpath )
		with open(fpath, mode='a+b') as file:
			for row in data:
				file.write(row)

		# Update Header: file size & register counter
		with open(fpath, mode='r+b') as file:
			# Read Header
			file.seek(0)
			header = bytearray(file.read(28))
			# Remaining file size in bytes: (filesize - 8)
			fsize = os.path.getsize(fpath) - 8
			struct.pack_into("<I",header,4,fsize)
			# Register Counter (Num. of Mappings)
			res=struct.unpack_from("<I",header,24)
			counter = res[0] + len(data)
			struct.pack_into("<I",header,24,counter)
			# Write Updated Header
			file.seek(0)
			file.write(header)

	# ---------------------------------------------------------------------------
	# API methods
	# ---------------------------------------------------------------------------

	@classmethod
	def zynapi_get_banks(cls):
		banks=[]
		for b in cls.get_user_banks():
			banks.append({
				'text': b[2],
				'name': b[2],
				'fullpath': b[0],
				'raw': b,
				'readonly': True
			})
		return banks


	@classmethod
	def zynapi_get_presets(cls, bank):
		presets=[]
		for p in cls.get_user_presets(bank['raw']):
			presets.append({
				'text': p[2] + ".fxp",
				'name': p[2][len(p[4])+1:],
				'fullpath': cls.user_presets_dpath + "/" + p[0] + ".fxp",
				'raw': p,
				'readonly': False
			})
		return presets


	@classmethod
	def zynapi_rename_preset(cls, preset_path, new_preset_name):
		head, tail = os.path.split(preset_path)
		fname, ext = os.path.splitext(tail)

		for b in cls.get_user_banks():
			if fname.startswith(b[2]):
				new_preset_path = head + "/" + b[2] + " " + new_preset_name + ext
				os.rename(preset_path, new_preset_path)
				break


	@classmethod
	def zynapi_remove_preset(cls, preset_path):
		os.remove(preset_path)


	@classmethod
	def zynapi_download(cls, fullpath):
		return fullpath


#******************************************************************************
