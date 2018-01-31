# -*- coding: utf-8 -*-
#******************************************************************************
# ZYNTHIAN PROJECT: Zynthian Engine (zynthian_engine_pianoteq)
# 
# zynthian_engine implementation for Pianoteq Stage
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
		self.name="Pianoteq"
		self.nickname="PT"
		
		self.main_command=("/zynthian/zynthian-sw/pianoteq/Pianoteq 6 STAGE", "--headless","--midi-channel")
		self.command=("/zynthian/zynthian-sw/pianoteq/Pianoteq 6 STAGE", "--headless","--midi-channel","all")
		self.bank=[
			'Steinway D',
		        'Steinway B',
		        'Grotrian',
		        'Bluethner',
		        'YC5',
		        'K2',
		        'U4',
		        'MKI',
		        'MKII',
		        'W1',
		        'Clavinet D6',
		        'Pianet N',
		        'Pianet T',
		        'Electra',
		        'Vibraphone V-B',
		        'Vibraphone V-M',
		        'Celesta',
		        'Glockenspiel',
		        'Toy Piano',
		        'Marimba',
		        'Xylophone',
		        'Steel Drum',
		        'Spacedrum',
		        'Hand Pan',
		        'Tank Drum',
		        'H. Ruckers II Harpsichord'
		        'Concert Harp',
		        'J. Dohnal',
		        'I. Besendorfer',
		        'S. Erard',
		        'J.B. Streicher',
		        'J. Broadwood',
		        'I. Pleyel',
		        'J. Frenzel',
		        'C. Bechstein'
		]

        # ---------------------------------------------------------------------------
        # Layer Management
        # ---------------------------------------------------------------------------

	def add_layer(self, layer):
		self.command=self.main_command+("--midi-channel",)+(layer.get_midi_chan(),)
		self.start()
		super().add_layer(layer)

        # ---------------------------------------------------------------------------
        # MIDI Channel Management
        # ---------------------------------------------------------------------------

        def set_midi_chan(self, layer):
		self.stop()
		self.command=self.main_command+("--midi-channel",)+(layer.get_midi_chan(),)
		self.start()

	#----------------------------------------------------------------------------
	# Bank Managament
	#----------------------------------------------------------------------------

	def get_bank_list(self, layer=None):
		return(self.bank)

	#----------------------------------------------------------------------------
	# Preset Managament
	#----------------------------------------------------------------------------

	def get_preset_list(self, bank):
		logging.info('Getting Preset List for %s' % self.name)
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
			return(presets)

	def set_preset(self, layer, preset, preload=False):
		super().set_preset(layer,preset)

#******************************************************************************
