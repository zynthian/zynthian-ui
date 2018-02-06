# -*- coding: utf-8 -*-
#******************************************************************************
# ZYNTHIAN PROJECT: Zynthian Engine (zynthian_engine_pianoteq)
# 
# zynthian_engine implementation for Pianoteq6-Stage-Demo
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

import re
import logging
import subprocess
from . import zynthian_engine

#------------------------------------------------------------------------------
# Piantoteq Engine Class
#------------------------------------------------------------------------------

class zynthian_engine_pianoteq(zynthian_engine):

	# ---------------------------------------------------------------------------
	# Controllers & Screens
	# ---------------------------------------------------------------------------

	#----------------------------------------------------------------------------
	# Initialization
	#----------------------------------------------------------------------------

	def __init__(self, zyngui=None):
		super().__init__(zyngui)
		self.name="Pianoteq6-Stage-Demo"
		self.nickname="PT"
		
		self.main_command=("/zynthian/zynthian-sw/pianoteq/Pianoteq 6 STAGE", "--headless")
		self.command=("/zynthian/zynthian-sw/pianoteq/Pianoteq 6 STAGE", "--headless","--midi-channel","all")
		self.bank=[
			('Steinway D',0,'Steinway D','_'),
		        ('Steinway B',1,'Steinway B','_'),
		        ('Grotrian',2,'Grotrian','_'),
		        ('Bluethner',3,'Bluethner','_'),
		        ('YC5',4,'YC5','_'),
		        ('K2',5,'K2','_'),
		        ('U4',6,'U4','_'),
		        ('MKI',7,'MKI','_'),
		        ('MKII',8,'MKII','_'),
		        ('W1',9,'W1','_'),
		        ('Clavinet D6',10,'Clavinet D6','_'),
		        ('Pianet N',11,'Pianet N','_'),
		        ('Pianet T',12,'Pianet T','_'),
		        ('Electra',13,'Electra','_'),
		        ('Vibraphone V-B',14,'Vibraphone V-B','_'),
		        ('Vibraphone V-M',15,'Vibraphone V-M','_'),
		        ('Celesta',16,'Celesta','_'),
		        ('Glockenspiel',17,'Glockenspiel','_'),
		        ('Toy Piano',18,'Toy Piano','_'),
		        ('Marimba',19,'Marimba','_'),
		        ('Xylophone',20,'Xylophone','_'),
		        ('Steel Drum',21,'Steel Drum','_'),
		        ('Spacedrum',22,'Spacedrum','_'),
		        ('Hand Pan',23,'Hand Pan','_'),
		        ('Tank Drum',24,'Tank Drum','_'),
		        ('H. Ruckers II Harpsichord',25,'H. Ruckers II Harpsichord','_'),
		        ('Concert Harp',26,'Concert Harp','_'),
		        ('J. Dohnal',27,'J. Dohnal','_'),
		        ('I. Besendorfer',28,'I. Besendorfer','_'),
		        ('S. Erard',29,'S. Erard','_'),
		        ('J.B. Streicher',30,'J.B. Streicher','_'),
		        ('J. Broadwood',31,'J. Broadwood','_'),
		        ('I. Pleyel',32,'I. Pleyel','_'),
		        ('J. Frenzel',33,'J. Frenzel','_'),
		        ('C. Bechstein',34,'C. Bechstein','_'),
		]

        # ---------------------------------------------------------------------------
        # Layer Management
        # ---------------------------------------------------------------------------

	def add_layer(self, layer):
		super().add_layer(layer)

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
		return(self.bank)

	#----------------------------------------------------------------------------
	# Preset Managament
	#----------------------------------------------------------------------------

	def get_preset_list(self, bank):
		bank=bank[2]
		self.start_loading()
		logging.info('Getting Preset List for %s [%s]' % (self.name,bank))
		presets=[]
		pianoteq=subprocess.Popen(self.main_command+("--list-presets",),stdout=subprocess.PIPE)
		for line in pianoteq.stdout:
			l=line.rstrip().decode("utf-8")
			if(bank==l[0:len(bank)]):
				preset_name=l[len(bank):].strip()
				preset_name=re.sub('^- ','',preset_name)
				preset_printable_name=preset_name
				if(preset_name==""):
					preset_printable_name="<Default>"
				presets.append((l,None,preset_printable_name,None))
		self.stop_loading()
		return(presets)

	def set_preset(self, layer, preset, preload=False):
		self.command=self.main_command+("--midi-channel",)+(str(layer.get_midi_chan()+1),)+("--preset",)+("\""+preset[0]+"\"",)
		self.stop()
		self.start(True)

#******************************************************************************
