# -*- coding: utf-8 -*-
#******************************************************************************
# ZYNTHIAN PROJECT: Zynthian Engine (zynthian_engine_linuxsampler)
# 
# zynthian_engine implementation for Linux Sampler
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
import socket
from time import sleep
from os.path import isfile, isdir
from subprocess import check_output
from zyngine.zynthian_engine import *

#------------------------------------------------------------------------------
# Linuxsampler Engine Class
#------------------------------------------------------------------------------

class zynthian_engine_linuxsampler(zynthian_engine):
	name="LinuxSampler"
	nickname="LS"

	port=6688
	sock=None

	command=("/usr/bin/linuxsampler","--lscp-port",str(port))
	lscp_dir="./data/lscp"
	bank_dirs=[
		('SFZ', os.getcwd()+"/data/soundfonts/sfz"),
		('GIG', os.getcwd()+"/data/soundfonts/gig"),
		('MySFZ', os.getcwd()+"/my-data/soundfonts/sfz"),
		('MyGIG', os.getcwd()+"/my-data/soundfonts/gig")
	]

	ctrl_list=[
		[[
			['volume',7,96,127],
			['modulation',1,0,127],
			['pan',10,12,127],
			['expression',11,64,127]
		],0,'main'],
		[[
			['volume',7,96,127],
			['modulation',1,0,127],
			['reverb',91,64,127],
			['chorus',93,0,127]
		],0,'effects']
	]

	def __init__(self,parent=None):
		super().__init__(parent)
		self.lscp_send_pattern("init_"+self.audio_driver)

	def lscp_connect(self):
		if not self.sock:
			self.sock=socket.socket(socket.AF_INET,socket.SOCK_STREAM)
			i=0
			while i<20:
				try:
					self.sock.connect(("127.0.0.1",self.port))
					break
				except:
					sleep(0.25)
					i+=1
		return self.sock
   
	def lscp_send(self,data):
		if self.lscp_connect():
			self.sock.send(data.encode()) 
		else:
			print("ERROR connecting with LinuxSampler Server")

	def lscp_send_pattern(self, pattern, pdict=None):
		fpath=self.lscp_dir+'/'+pattern+'.lscp'
		with open(fpath) as f:
			lscp=f.read()
			if pdict:
				try:
					for k, v in pdict.items():
						#print("REPLACING PATTERN: #"+k+"# => "+v)
						lscp=lscp.replace('#'+k+'#',v)
				except Exception as err:
					print("ERROR replacing lscp pattern:"+str(err))
					pass
			#print("LSCP =>\n"+lscp)
			self.lscp_send(lscp)

	def load_bank_list(self):
		self.load_bank_dirlist(self.bank_dirs)

	def load_instr_lscpmap(self,fpath):
		self.instr_list=[]
		#fpath=self.bank_dirs[0]+'/'+self.bank_list[self.get_bank_index()][0]
		with open(fpath) as f:
			lines = f.readlines()
			ptrn=re.compile("^MAP MIDI_INSTRUMENT")
			i=0
			for line in lines:
				m=ptrn.match(line)
				if m:
					try:
						parts=line.split();
						title=parts[11][1:-1].replace('_', ' ')
						self.instr_list.append((i,[0,int(parts[4]),int(parts[5])],title))
						i=i+1
					except:
						pass

	def load_instr_list(self):
		print('Getting Instr List for ' + self.name)
		i=0
		self.instr_list=[]
		instr_dpath=self.bank_list[self.get_bank_index()][0]
		print("Finding in "+instr_dpath)
		if os.path.isdir(instr_dpath):
			print("Finding in "+instr_dpath)
			cmd="find '"+instr_dpath+"' -maxdepth 2 -type f -name '*.sfz'"
			output=check_output(cmd, shell=True).decode('utf8')
			cmd="find '"+instr_dpath+"' -maxdepth 2 -type f -name '*.gig'"
			output=output+"\n"+check_output(cmd, shell=True).decode('utf8')
			lines=output.split('\n')
			for f in lines:
				if f:
					filename, filext = os.path.splitext(f)
					title=filename[len(instr_dpath)+1:].replace('_', ' ')
					engine=filext[1:].lower()
					print("instr_list => " + f)
					self.instr_list.append((i,[0,0,0],title,f,engine))
					i=i+1

	def xset_bank(self, i):
		super().set_bank(i)
		#Send LSCP script
		lscp_fpath=self.lscp_dir+'/'+self.bank_list[self.get_bank_index()][0]
		with open(lscp_fpath) as f:
			lines = f.readlines()
			for line in lines:
				self.lscp_send(line)
				#print("LSCP: "+line)

	def _set_instr(self, instr, chan=None):
		if chan is None: chan=self.midi_chan
		self.lscp_send_pattern("channel",{'chan': str(chan), 'engine': instr[4], 'fpath': instr[3]})

#******************************************************************************
