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
from xml.etree import ElementTree as ET
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
	if os.path.isfile(PIANOTEQ_BINARY) and os.access(PIANOTEQ_BINARY, os.X_OK):
		return True
	else:
		return False


def get_pianoteq_binary_info():
	if check_pianoteq_binary():
		# Get version and trial info from pianoteq binary
		res=None
		version_pattern = re.compile(" version ([0-9]+\.[0-9]+\.[0-9]+)", re.IGNORECASE)
		stage_pattern = re.compile(" stage ", re.IGNORECASE)
		trial_pattern = re.compile(" trial ",re.IGNORECASE)
		proc=subprocess.Popen([PIANOTEQ_BINARY,"--version"],stdout=subprocess.PIPE)
		for line in proc.stdout:
			l=line.rstrip().decode("utf-8")
			m = version_pattern.search(l)
			if m:
				res={}
				res['version'] = m.group(1)
				m = stage_pattern.search(l)
				if m:
					res['stage'] = 1
				else:
					res['stage'] = 0
				m=trial_pattern.search(l)
				if m:
					res['trial'] = 1
				else:
					res['trial'] = 0
		return res


def get_pianoteq_subl():
	subl=[]
	if os.path.isfile(PIANOTEQ_CONFIG_FILE):
		root = ET.parse(PIANOTEQ_CONFIG_FILE)
		for xml_value in root.iter("VALUE"):
			if(xml_value.attrib['name']=='subl'):
				subl=xml_value.attrib['val'].split(';')
	return subl


def fix_pianoteq_config():
	if os.path.isfile(PIANOTEQ_CONFIG_FILE):
		root = ET.parse(PIANOTEQ_CONFIG_FILE)
		try:
			for xml_value in root.iter("VALUE"):
				if(xml_value.attrib['name']=='engine_rate'):
					xml_value.set('val',str(PIANOTEQ_INTERNAL_SR))
				if(xml_value.attrib['name']=='voices'):
					xml_value.set('val',str(PIANOTEQ_VOICES))
				if(xml_value.attrib['name']=='multicore'):
					xml_value.set('val',str(PIANOTEQ_MULTICORE))

			if(root.find('DEVICESETUP')):
				logging.debug("Fixing devicesetup node")
				for devicesetup in root.iter('DEVICESETUP'):
					devicesetup.set('deviceType','JACK')
					devicesetup.set('audioOutputDeviceName','Auto-connect ON')
					devicesetup.set('audioInputDeviceName','Auto-connect ON')
					devicesetup.set('audioDeviceRate','44100')
					devicesetup.set('forceStereo','0')
			else:
				logging.debug("Creating new devicesetup node")
				value = ET.Element('VALUE')
				value.set('name','audio-setup')
				devicesetup = ET.SubElement(value,'DEVICESETUP')
				devicesetup.set('deviceType','JACK')
				devicesetup.set('audioOutputDeviceName','Auto-connect ON')
				devicesetup.set('audioInputDeviceName','Auto-connect ON')
				devicesetup.set('audioDeviceRate','44100')
				devicesetup.set('forceStereo','0')
				root.getroot().append(value)

			root.write(PIANOTEQ_CONFIG_FILE)

		except Exception as e:
			logging.error("Installing devicesetup failed: %s" % format(e))
			return format(e)


#------------------------------------------------------------------------------
# Pianoteq module constants & parameter configuration/initialization
#------------------------------------------------------------------------------

PIANOTEQ_SW_DIR = os.environ.get('ZYNTHIAN_SW_DIR',"/zynthian/zynthian-sw") + "/pianoteq6"
PIANOTEQ_BINARY = PIANOTEQ_SW_DIR + "/Pianoteq 6 STAGE"
PIANOTEQ_ADDON_DIR = os.path.expanduser("~")  + '/.local/share/Modartt/Pianoteq/Addons'
PIANOTEQ_MY_PRESETS_DIR = os.path.expanduser("~")  + '/.local/share/Modartt/Pianoteq/Presets/My Presets'
PIANOTEQ_MIDIMAPPINGS_DIR = os.path.expanduser("~") + '/.local/share/Modartt/Pianoteq/MidiMappings'

try:
	PIANOTEQ_VERSION=list(map(int, os.environ.get('PIANOTEQ_VERSION',"6.0.3").split(".")))
except:
	PIANOTEQ_VERSION=(6,0,3)

PIANOTEQ_TRIAL=int(os.environ.get('PIANOTEQ_TRIAL',"1"))
PIANOTEQ_STAGE=int(os.environ.get('PIANOTEQ_STAGE',"1"))
PIANOTEQ_NAME="Pianoteq{}{}".format(PIANOTEQ_VERSION[0],PIANOTEQ_VERSION[1])

if PIANOTEQ_VERSION:
	PIANOTEQ_CONFIG_FILE = os.path.expanduser("~")  + "/.config/Modartt/Pianoteq{}{}".format(PIANOTEQ_VERSION[0],PIANOTEQ_VERSION[1]) + ' STAGE.prefs'
	if PIANOTEQ_VERSION[1]==0:
		PIANOTEQ_INTERNAL_SR=22050
		PIANOTEQ_VOICES=32
		PIANOTEQ_MULTICORE=1
	else:
		PIANOTEQ_INTERNAL_SR=22050
		PIANOTEQ_VOICES=32
		PIANOTEQ_MULTICORE=2

#------------------------------------------------------------------------------
# Piantoteq Engine Class
#------------------------------------------------------------------------------

class zynthian_engine_pianoteq(zynthian_engine):

	# ---------------------------------------------------------------------------
	# Banks
	# ---------------------------------------------------------------------------

	bank_list_v6_3=[
		('Ant. Petrof',0,'Ant. Petrof','_','Antpetrof:A')
	]

	bank_list=[
		('Steinway D',1,'Steinway D','_','D4:A'),
		('Steinway B',2,'Steinway B','_','Modelb:A'),
		('Steingraeber',3,'Steingraeber','_','Steingraeber:A'),
		('Grotrian',4,'Grotrian','_','Grotrian:A'),
		('Bluethner',5,'Bluethner','_','Bluethner:A'),
		('YC5',6,'YC5','_','Rock:A'),
		('K2',7,'K2','_','K2:A'),
		('U4',8,'U4','_','U4:A'),
		('MKI',9,'MKI','_','Electric:A'),
		('MKII',10,'MKII','_','Electric:A'),
		('W1',11,'W1','_','Electric:A'),
		('Clavinet D6',12,'Clavinet D6','_','Clavinet:A'),
		('Pianet N',13,'Pianet N','_','Clavinet:A'),
		('Pianet T',14,'Pianet T','_','Clavinet:A'),
		('Electra',15,'Electra','_','Clavinet:A'),
		('Vibraphone V-B',16,'Vibraphone V-B','_','Vibes:A'),
		('Vibraphone V-M',17,'Vibraphone V-M','_','Vibes:A'),
		('Celesta',18,'Celesta','_','Celeste:A'),
		('Glockenspiel',19,'Glockenspiel','_','Celeste:A'),
		('Toy Piano',20,'Toy Piano','_','Celeste:A'),
		('Marimba',21,'Marimba','_','Xylo:A'),
		('Xylophone',22,'Xylophone','_','Xylo:A'),
		('Steel Drum',23,'Steel Drum','_','Steel:A'),
		('Spacedrum',24,'Spacedrum','_','Steel:A'),
		('Hand Pan',25,'Hand Pan','_','Steel:A'),
		('Tank Drum',26,'Tank Drum','_','Steel:A'),
		('H. Ruckers II Harpsichord',27,'H. Ruckers II Harpsichord','_','Harpsichord:A'),
		('Concert Harp',28,'Concert Harp','_','Harp:A'),
		('J. Dohnal',29,'J. Dohnal','_','Kremsegg1:A'),
		('I. Besendorfer',30,'I. Besendorfer','_','Kremsegg1:A'),
		('S. Erard',31,'S. Erard','_','Kremsegg1:A'),
		('J.B. Streicher',32,'J.B. Streicher','_','Kremsegg1:A'),
		('J. Broadwood',33,'J. Broadwood','_','Kremsegg2:A'),
		('I. Pleyel',34,'I. Pleyel','_','Kremsegg2:A'),
		('J. Frenzel',35,'J. Frenzel','_','Kremsegg2:A'),
		('C. Bechstein',36,'C. Bechstein','_','Kremsegg2:A'),
		('Cimbalom',37,'Cimbalom','_','KIViR'),
		('Neupert Clavichord',38,'Neupert Clavichord','_','KIViR'),
		('F.E. Blanchet Harpsichord',39,'F.E. Blanchet Harpsichord','_','KIViR'),
		('C. Grimaldi Harpsichord',40,'C. Grimaldi Harpsichord','_','KIViR'),
		('J. Schantz',41,'J. Schantz','_','KIViR'),
		('J.E. Schmidt',42,'J.E. Schmidt','_','KIViR'),
		('A. Walter',43,'A. Walter','_','KIViR'),
		('D. Schoffstoss',44,'D. Schoffstoss','_','KIViR'),
		('C. Graf',45,'C. Graf','_','KIViR'),
		('Erard',46,'Erard','_','KIViR'),
		('Pleyel',47,'Pleyel','_','KIViR'),
		('CP-80',48,'CP-80','_','KIViR'),
		('Church Bells',49,'Church Bells','_','bells'),
		('Tubular Bells',50,'Tubular Bells','_','bells')
	]

	free_instruments=[
		'bells',
		'KIViR'
	]

	spacer=[
		(None,0,'=== DEMO Instruments ===')
	]

	if PIANOTEQ_VERSION[0]>=6 and PIANOTEQ_VERSION[1]>=3:
		bank_list = bank_list_v6_3 + bank_list

	# Separate Licensed from Free and Demo
	subl = get_pianoteq_subl()
	if subl:
		free_banks=[]
		licensed_banks=[]
		unlicensed_banks=[]
		for bank in bank_list:
			if bank[4].upper() in map(str.upper, subl):
				licensed_banks.append(bank)
			elif bank[4].upper() in map(str.upper, free_instruments):
				free_banks.append(bank)
			else:
				unlicensed_banks.append(bank)
		bank_list = licensed_banks + free_banks + spacer + unlicensed_banks


	# ---------------------------------------------------------------------------
	# Controllers & Screens
	# ---------------------------------------------------------------------------

	_ctrls=[
		['volume',7,96],
		['dynamic',85,64],
		['mute on/off',19,'off','off|on'],
		['sustain on/off',64,'off','off|on'],
		['rev on/off',30,'off','off|on'],
		['rev duration',31,0],
		['rev mix',32,0],
		['rev room',33,0],
		['rev p/d',34,0],
		['rev e/r',35,64],
		['rev tone',36,64]
	]

	_ctrl_screens=[
		['main',['volume','sustain on/off','dynamic','mute on/off']],
		['reverb1',['volume','rev on/off','rev duration','rev mix']],
		['reverb2',['volume','rev room','rev p/d','rev e/r']],
		['reverb3',['volume','rev tone']]
	]

	#----------------------------------------------------------------------------
	# Initialization
	#----------------------------------------------------------------------------

	def __init__(self, zyngui=None, update_presets_cache=False):
		super().__init__(zyngui)
		self.name = PIANOTEQ_NAME
		self.nickname = "PT"
		self.jackname = PIANOTEQ_NAME

		self.options['midi_chan']=False

		self.preset = ""
		self.midimapping = "ZynthianControllers"

		if self.config_remote_display():
			if PIANOTEQ_VERSION[0]==6 and PIANOTEQ_VERSION[1]==0:
				self.base_command=(PIANOTEQ_BINARY,)
			else:
				self.base_command=(PIANOTEQ_BINARY, "--multicore", "max",)
		else:
			if PIANOTEQ_VERSION[0]==6 and PIANOTEQ_VERSION[1]==0:
				self.base_command=(PIANOTEQ_BINARY, "--headless",)
			else:
				self.base_command=(PIANOTEQ_BINARY, "--multicore", "max", "--headless",)

		self.user_presets_path=PIANOTEQ_MY_PRESETS_DIR
		if not os.path.exists(self.user_presets_path):
			os.makedirs(self.user_presets_path)

		self.presets = defaultdict(list)
		self.presets_cache_fpath = self.my_data_dir + '/pianoteq6/presets_cache.json'
		#self.presets_cache_fpath="/tmp/presets_cache.json"
		if os.path.isfile(self.presets_cache_fpath) and not update_presets_cache:
			self.load_presets_cache()
		else:
			self.save_presets_cache()

		self.get_user_presets()
		self.purge_banks()
		self.generate_presets_midimapping()

		if not os.path.isfile(PIANOTEQ_CONFIG_FILE):
			logging.debug("Pianoteq configuration does not exist. Creating one.")
			ensure_dir("/root/.config/Modartt/")
			pt_config_file = "Pianoteq{}{}".format(PIANOTEQ_VERSION[0],PIANOTEQ_VERSION[1]) + ' STAGE.prefs'
			shutil.copy(self.data_dir + "/pianoteq6/" + pt_config_file, "/root/.config/Modartt/")

		fix_pianoteq_config()


	def start(self, start_queue=False, shell=False):
		self.start_loading()
		logging.debug("Starting"+str(self.command))
		super().start(start_queue,shell)
		logging.debug("Start sleeping...")
		time.sleep(5)
		logging.debug("Stop sleeping...")
		self.stop_loading()

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

	def get_bank_list(self, layer=None):
		return self.bank_list

	def set_bank(self, layer, bank):
		pass

	#----------------------------------------------------------------------------
	# Preset Managament
	#----------------------------------------------------------------------------

	def save_presets_cache(self):
		logging.info("Caching Internal Presets ...")
		#Get internal presets from Pianoteq ...
		try:
			pianoteq=subprocess.Popen([PIANOTEQ_BINARY, "--list-presets"],stdout=subprocess.PIPE)
			for line in pianoteq.stdout:
				l=line.rstrip().decode("utf-8")
				logging.debug("PRESET => {}".format(l))
				for bank in self.bank_list:
					try:
						b=bank[0]
						if b==l:
							self.presets[b].append([l,None,'<default>',None])
						elif b+' '==l[0:len(b)+1]:
							#logging.debug("'%s' == '%s'" % (b,l[0:len(b)]))
							preset_title=l[len(b):].strip()
							preset_title=re.sub('^- ','',preset_title)
							self.presets[b].append([l,None,preset_title,None])
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


	# Get user presets
	def get_user_presets(self):
		user_presets_flist=sorted(os.listdir(self.user_presets_path))
		for bank in self.bank_list:
			if bank[0]:
				user_presets = []
				bank_name = bank[0]
				bank_prefix = bank_name + " "
				logging.debug("Getting User presets for %s [%s]" % (self.name,bank_name))
				for f in user_presets_flist:
					if (isfile(join(self.user_presets_path,f)) and f[-4:].lower()==".fxp"):
						if bank_prefix==f[0:len(bank_prefix)]:
							preset_path="My Presets/" + f[:-4]
							preset_title="MY/" + str.replace(f[len(bank_prefix):-4], '_', ' ').strip()
							user_presets.append((preset_path,None,preset_title,None))
				#Add internal presets
				try:
					self.presets[bank_name] = user_presets + self.presets[bank_name]
				except:
					self.presets[bank_name] = user_presets


	# Remove banks without presets
	def purge_banks(self):
		purged_bank_list=[]
		for bank in self.bank_list:
			if not bank[0] or (bank[0] and len(self.presets[bank[0]])>0):
				purged_bank_list.append(bank)
		self.bank_list=purged_bank_list


	def get_preset_list(self, bank):
		self.start_loading()
		bank_name = bank[0]
		if bank_name in self.presets:
			logging.info("Getting Preset List for %s [%s]" % (self.name,bank_name))
			res = self.presets[bank_name]
		else:
			logging.error("Can't get Preset List for %s [%s]" % (self.name,bank_name))
			res = []
		self.stop_loading()
		return res


	def set_preset(self, layer, preset, preload=False):
		mm = "Zynthian-{}".format(preset[3])
		if mm == self.midimapping:
			super().set_preset(layer,preset,preload)
			self.preset = preset[0]
			time.sleep(1)
		else:
			self.midimapping=mm
			if preset[0]!=self.preset:
				self.start_loading()
				self.preset=preset[0]
				self.command = self.base_command + ("--midi-channel", str(layer.get_midi_chan()+1),)
				self.command += ("--preset", preset[0],)
				self.command += ("--midimapping", self.midimapping,)
				self.stop()
				self.start(True,False)
				self.stop_loading()


	def cmp_presets(self, preset1, preset2):
		return True

	#--------------------------------------------------------------------------
	# Special
	#--------------------------------------------------------------------------

	def generate_presets_midimapping(self):
		# Copy default "static" MIDI Mappings if doesn't exist
		if not os.path.isfile(PIANOTEQ_MIDIMAPPINGS_DIR + "/ZynthianControllers.ptm"):
			logging.debug("Pianoteq Base MIDI-Mapping does not exist. Creating ...")
			ensure_dir(PIANOTEQ_MIDIMAPPINGS_DIR)
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
						prs[1]=len(data)
						prs[3]=mmn
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


#******************************************************************************
