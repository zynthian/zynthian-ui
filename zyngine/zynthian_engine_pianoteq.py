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
		('Ant Petrof',0,'Ant Petrof','_','Antpetrof:A')
	]

	bank_list=[
		('Steinway D',1,'Steinway D','_','D4:A'),
		('Steinway B',2,'Steinway B','_',''),
		('Steingraeber',3,'Steingraeber','_',''),
		('Grotrian',4,'Grotrian','_','Grotrian:A'),
		('Bluethner',5,'Bluethner','_',''),
		('YC5',6,'YC5','_',''),
		('K2',7,'K2','_',''),
		('U4',8,'U4','_',''),
		('MKI',9,'MKI','_','Electric:A'),
		('MKII',10,'MKII','_','Electric:A'),
		('W1',11,'W1','_','Electric:A'),
		('Clavinet D6',12,'Clavinet D6','_','Clavinet:A'),
		('Pianet N',13,'Pianet N','_','Clavinet:A'),
		('Pianet T',14,'Pianet T','_','Clavinet:A'),
		('Electra',15,'Electra','_','Clavinet:A'),
		('Vibraphone V-B',16,'Vibraphone V-B','_',''),
		('Vibraphone V-M',17,'Vibraphone V-M','_',''),
		('Celesta',18,'Celesta','_',''),
		('Glockenspiel',19,'Glockenspiel','_',''),
		('Toy Piano',20,'Toy Piano','_',''),
		('Marimba',21,'Marimba','_',''),
		('Xylophone',22,'Xylophone','_',''),
		('Steel Drum',23,'Steel Drum','_',''),
		('Spacedrum',24,'Spacedrum','_',''),
		('Hand Pan',25,'Hand Pan','_',''),
		('Tank Drum',26,'Tank Drum','_',''),
		('H. Ruckers II Harpsichord',27,'H. Ruckers II Harpsichord','_',''),
		('Concert Harp',28,'Concert Harp','_',''),
		('J. Dohnal',29,'J. Dohnal','_',''),
		('I. Besendorfer',30,'I. Besendorfer','_',''),
		('S. Erard',31,'S. Erard','_',''),
		('J.B. Streicher',32,'J.B. Streicher','_',''),
		('J. Broadwood',33,'J. Broadwood','_',''),
		('I. Pleyel',34,'I. Pleyel','_',''),
		('J. Frenzel',35,'J. Frenzel','_',''),
		('C. Bechstein',36,'C. Bechstein','_',''),
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
		('',0,'-- Other Instruments (DEMO) --')
	]

	if PIANOTEQ_VERSION[0]>=6 and PIANOTEQ_VERSION[1]>=3:
		bank_list = bank_list_v6_3 + bank_list

	subl = get_pianoteq_subl()
	if subl:
		free_banks=[]
		licenced_banks=[]
		unlicenced_banks=[]
		for bank in bank_list:
			if bank[4] in subl:
				licenced_banks.append(bank)
			elif bank[4] in free_instruments:
				free_banks.append(bank)
			else:
				unlicenced_banks.append(bank)
		bank_list = licenced_banks + free_banks + spacer + unlicenced_banks


	# ---------------------------------------------------------------------------
	# Controllers & Screens
	# ---------------------------------------------------------------------------

	_ctrls=[
		['volume',7,96],
		['mute',19,'off','off|on'],
		['rev on/off',30,'off','off|on'],
		['rev duration',31,0],
		['rev mix',32,0],
		['rev room',33,0],
		['rev p/d',34,0],
		['rev e/r',35,64],
		['rev tone',36,64],
		['sustain on/off',64,'off','off|on']
	]

	_ctrl_screens=[
		['main',['volume','sustain on/off']],
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

		if self.config_remote_display():
			if PIANOTEQ_VERSION[0]==6 and PIANOTEQ_VERSION[1]==0:
				self.main_command=(PIANOTEQ_BINARY,"--midimapping","Zynthian")
			else:
				self.main_command=(PIANOTEQ_BINARY,"--multicore","max","--midimapping","Zynthian")
		else:
			if PIANOTEQ_VERSION[0]==6 and PIANOTEQ_VERSION[1]==0:
				self.main_command=(PIANOTEQ_BINARY,"--headless","--midimapping","Zynthian")
			else:
				self.main_command=(PIANOTEQ_BINARY,"--multicore","max","--headless","--midimapping","Zynthian")
		self.command=self.main_command

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

		if not os.path.isfile(PIANOTEQ_CONFIG_FILE):
			logging.debug("Pianoteq configuration does not exist. Creating one.")
			ensure_dir("/root/.config/Modartt/")
			pt_config_file = "Pianoteq{}{}".format(PIANOTEQ_VERSION[0],PIANOTEQ_VERSION[1]) + ' STAGE.prefs'
			shutil.copy(self.data_dir + "/pianoteq6/" + pt_config_file, "/root/.config/Modartt/")

		if not os.path.isfile("/root/.local/share/Modartt/Pianoteq/MidiMappings/Zynthian.ptm"):
			logging.debug("Pianoteq MIDI-mapping does not exist. Creating one.")
			ensure_dir("/root/.local/share/Modartt/Pianoteq/MidiMappings/")
			shutil.copy(self.data_dir + "/pianoteq6/Zynthian.ptm", "/root/.local/share/Modartt/Pianoteq/MidiMappings/")

		fix_pianoteq_config()



	def start(self, start_queue=False, shell=False):
		self.start_loading()
		logging.debug("Starting"+str(self.command))
		super().start(start_queue,shell)
		logging.debug("Start sleeping...")
		time.sleep(4)
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
		self.command=self.main_command+("--midi-channel",)+(str(layer.get_midi_chan()+1),)

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
				#logging.debug("%s" % l)
				for bank in self.bank_list:
					b=bank[0]
					if b==l:
						self.presets[bank[0]].append((l,None,'<default>',None))
					elif b+' '==l[0:len(b)+1]:
						#logging.debug("'%s' == '%s'" % (b,l[0:len(b)]))
						preset_name=l[len(b):].strip()
						preset_name=re.sub('^- ','',preset_name)
						preset_title=preset_name
						self.presets[bank[0]].append((l,None,preset_title,None))
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


	def get_preset_list(self, bank):
		self.start_loading()
		bank=bank[2]
		#Get internal presets
		if bank in self.presets:
			logging.info("Getting Cached Internal Preset List for %s [%s]" % (self.name,bank))
			internal_presets=self.presets[bank]
		else:
			logging.error("Can't get Cached Internal Preset List for %s [%s]" % (self.name,bank))
			internal_presets=[]
		#Get user presets
		bank+=" "
		user_presets=[]
		for f in sorted(os.listdir(self.user_presets_path)):
			if (isfile(join(self.user_presets_path,f)) and f[-4:].lower()==".fxp"):
				if bank==f[0:len(bank)]:
					preset_path="My Presets/" + f[:-4]
					preset_title="MY/" + str.replace(f[len(bank):-4], '_', ' ').strip()
					user_presets.append((preset_path,None,preset_title,None))
		#Return the combined list
		self.stop_loading()
		return user_presets + internal_presets


	def set_preset(self, layer, preset, preload=False):
		if preset[0]!=self.preset:
			self.start_loading()
			self.command=self.main_command+("--midi-channel",)+(str(layer.get_midi_chan()+1),)+("--preset",)+(preset[0],)
			self.preset=preset[0]
			self.stop()
			self.start(True,False)
			self.stop_loading()

	def cmp_presets(self, preset1, preset2):
		return True

	#--------------------------------------------------------------------------
	# Special
	#--------------------------------------------------------------------------


#******************************************************************************
