# -*- coding: utf-8 -*-
#******************************************************************************
# ZYNTHIAN PROJECT: Zynthian Engine (zynthian_engine)
# 
# zynthian_engine is the base class for the Zynthian Synth Engine
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

#import sys
import os
import copy
import signal
import liblo
import logging
from time import sleep
from os.path import isfile, isdir, join
from subprocess import call, Popen, PIPE, STDOUT
from threading  import Thread
from queue import Queue, Empty
from string import Template
from collections import OrderedDict

from . import zynthian_controller

#------------------------------------------------------------------------------
# Synth Engine Base Class
#------------------------------------------------------------------------------

class zynthian_engine:

	# ---------------------------------------------------------------------------
	# Default Controllers & Screens
	# ---------------------------------------------------------------------------

	# Standard MIDI Controllers
	_ctrls=[
		['volume',7,96],
		['modulation',1,0],
		['pan',10,64],
		['expression',11,127],
		['FX send',12,0],
		['sustain',64,'off',['off','on']],
		['resonance',71,64],
		['cutoff',74,64],
		['reverb',91,64],
		['chorus',93,2]
	]

	# Controller Screens
	_ctrl_screens=[
		#['main',['volume','modulation','cutoff','resonance']],
		['main',['volume','expression','pan','sustain']],
		['effects',['volume','modulation','reverb','chorus']]
	]

	# ---------------------------------------------------------------------------
	# Initialization
	# ---------------------------------------------------------------------------

	def __init__(self, zyngui=None):
		self.zyngui=zyngui

		self.name=""
		self.nickname=""

		self.loading=0
		self.layers=[]

		#IPC variables
		self.command=None
		self.command_env=None
		self.proc=None
		self.queue=None
		self.thread_queue=None

		self.osc_target=None
		self.osc_target_port=6693
		self.osc_server=None
		self.osc_server_port=None
		self.osc_server_url=None

	def __del__(self):
		self.stop()

	def reset(self):
		#Reset Vars
		self.loading=0
		self.loading_snapshot=False
		#TODO: OSC, IPC, ...

	def config_remote_display(self):
		fvars={}
		if os.environ.get('ZYNTHIANX'):
			fvars['DISPLAY']=os.environ.get('ZYNTHIANX')
		else:
			try:
				with open("/root/.remote_display_env","r") as fh:
					lines = fh.readlines()
					for line in lines:
						parts=line.strip().split('=')
						if len(parts)>=2 and parts[1]: fvars[parts[0]]=parts[1]
			except:
				fvars['DISPLAY']=""
		if 'DISPLAY' not in fvars or not fvars['DISPLAY']:
			logging.info("NO REMOTE DISPLAY")
			return False
		else:
			logging.info("REMOTE DISPLAY: %s" % fvars['DISPLAY'])
			self.command_env=os.environ.copy()
			for f,v in fvars.items():
				self.command_env[f]=v
			return True

	# ---------------------------------------------------------------------------
	# Loading GUI signalization & refreshing
	# ---------------------------------------------------------------------------

	def start_loading(self):
		self.loading=self.loading+1
		if self.loading<1: self.loading=1
		if self.zyngui:
			self.zyngui.start_loading()

	def stop_loading(self):
		self.loading=self.loading-1
		if self.loading<0: self.loading=0
		if self.zyngui:
			self.zyngui.stop_loading()

	def reset_loading(self):
		self.loading=0
		if self.zyngui:
			self.zyngui.stop_loading()

	# ---------------------------------------------------------------------------
	# Refresh Management
	# ---------------------------------------------------------------------------

	def refresh_all(self, refresh=True):
		for layer in self.layers:
			layer.refresh_flag=refresh

	# ---------------------------------------------------------------------------
	# Subproccess Management & IPC
	# ---------------------------------------------------------------------------

	def proc_enqueue_output(self):
		try:
			for line in self.proc.stdout:
				self.queue.put(line)
				#logging.debug("Proc Out: %s" % line)
		except:
			logging.info("Finished queue thread")

	def proc_get_lines(self, tout=0.1, limit=2):
		n=0
		lines=[]
		while True:
			try:
				lines.append(self.queue.get(True,tout))
				n=n+1
				if n==limit: tout=0.1
			except Empty:
				break
		return lines

	def start(self, start_queue=False, shell=False):
		if not self.proc:
			logging.info("Starting Engine " + self.name)
			try:
				self.start_loading()
				self.proc=Popen(self.command,shell=shell,bufsize=1,universal_newlines=True,
					stdin=PIPE,stdout=PIPE,stderr=STDOUT,env=self.command_env)
					#, preexec_fn=os.setsid
					#, preexec_fn=self.chuser()
				if start_queue:
					self.queue=Queue()
					self.thread_queue=Thread(target=self.proc_enqueue_output, args=())
					self.thread_queue.daemon = True # thread dies with the program
					self.thread_queue.start()
					self.proc_get_lines(2)
			except Exception as err:
				logging.error("Can't start engine %s => %s" % (self.name,err))
			self.stop_loading()

	def stop(self, wait=0.2):
		if self.proc:
			self.start_loading()
			try:
				logging.info("Stoping Engine " + self.name)
				pid=self.proc.pid
				#self.proc.stdout.close()
				#self.proc.stdin.close()
				#os.killpg(os.getpgid(pid), signal.SIGTERM)
				self.proc.terminate()
				if wait>0: sleep(wait)
				try:
					self.proc.kill()
					os.killpg(pid, signal.SIGKILL)
				except:
					pass
			except Exception as err:
				logging.error("Can't stop engine %s => %s" % (self.name,err))
			self.proc=None
			self.stop_loading()

	def proc_cmd(self, cmd, tout=0.1):
		if self.proc:
			self.start_loading()
			try:
				logging.debug("proc command: "+cmd)
				#self.proc.stdin.write(bytes(cmd + "\n", 'UTF-8'))
				self.proc.stdin.write(cmd + "\n")
				self.proc.stdin.flush()
				out=self.proc_get_lines(tout)
				logging.debug("proc output:\n%s" % (out))
			except Exception as err:
				out=""
				logging.error("Can't exec engine command: %s => %s" % (cmd,err))
			self.stop_loading()
			return out

	# ---------------------------------------------------------------------------
	# OSC Management
	# ---------------------------------------------------------------------------

	def osc_init(self, proto=liblo.UDP):
		self.start_loading()
		try:
			self.osc_target=liblo.Address('localhost',self.osc_target_port,proto)
			logging.info("OSC target in port %s" % str(self.osc_target_port))
			self.osc_server=liblo.ServerThread(None,proto)
			self.osc_server_port=self.osc_server.get_port()
			self.osc_server_url=liblo.Address('localhost',self.osc_server_port,proto).get_url()
			logging.info("OSC server running in port %s" % str(self.osc_server_port))
			self.osc_add_methods()
			self.osc_server.start()
		except liblo.AddressError as err:
			logging.error("OSC Server can't be initialized (%s). Running without OSC feedback." % err)
		self.stop_loading()

	def osc_end(self):
		if self.osc_server:
			self.start_loading()
			try:
				#self.osc_server.stop()
				logging.info("OSC server stopped")
			except Exception as err:
				logging.error("Can't stop OSC server => %s" % err)
			self.stop_loading()

	def osc_add_methods(self):
		self.osc_server.add_method(None, None, self.cb_osc_all)

	def cb_osc_all(self, path, args, types, src):
		logging.info("OSC MESSAGE '%s' from '%s'" % (path, src.url))
		for a, t in zip(args, types):
			logging.debug("argument of type '%s': %s" % (t, a))

	# ---------------------------------------------------------------------------
	# Generating list from different sources
	# ---------------------------------------------------------------------------

	def get_filelist(self, dpath, fext):
		self.start_loading()
		res=[]
		if isinstance(dpath, str): dpath=[('_', dpath)]
		fext='.'+fext
		xlen=len(fext)
		i=0
		for dpd in dpath:
			dp=dpd[1]
			dn=dpd[0]
			for f in sorted(os.listdir(dp)):
				if (isfile(join(dp,f)) and f[-xlen:].lower()==fext):
					title=str.replace(f[:-xlen], '_', ' ')
					if dn!='_': title=dn+'/'+title
					#print("filelist => "+title)
					res.append((join(dp,f),i,title,dn))
					i=i+1
		self.stop_loading()
		return res

	def get_dirlist(self, dpath):
		self.start_loading()
		res=[]
		if isinstance(dpath, str): dpath=[('_', dpath)]
		i=0
		for dpd in dpath:
			dp=dpd[1]
			dn=dpd[0]
			for f in sorted(os.listdir(dp)):
				if isdir(join(dp,f)):
					title,ext=os.path.splitext(f)
					title=str.replace(title, '_', ' ')
					if dn!='_': title=dn+'/'+title
					#print("dirlist => "+title)
					res.append((join(dp,f),i,title,dn))
					i=i+1
		self.stop_loading()
		return res

	def get_cmdlist(self,cmd):
		self.start_loading()
		res=[]
		i=0
		output=check_output(cmd, shell=True)
		lines=output.decode('utf8').split('\n')
		for f in lines:
			title=str.replace(f, '_', ' ')
			res.append((f,i,title))
			i=i+1
		self.stop_loading()
		return res

	# ---------------------------------------------------------------------------
	# Layer Management
	# ---------------------------------------------------------------------------

	def add_layer(self, layer):
		self.layers.append(layer)

	def del_layer(self, layer):
		self.layers.remove(layer)

	def del_all_layers(self):
		for layer in self.layers:
			self.del_layer(layer)

	# ---------------------------------------------------------------------------
	# MIDI Channel Management
	# ---------------------------------------------------------------------------

	def set_midi_chan(self, layer):
		pass

	# ---------------------------------------------------------------------------
	# Bank Management
	# ---------------------------------------------------------------------------

	def get_bank_list(self, layer=None):
		logging.info('Getting Bank List for %s: NOT IMPLEMENTED!' % self.name)

	def set_bank(self, layer, bank):
		self.zyngui.zynmidi.set_midi_bank_msb(layer.get_midi_chan(), bank[1])

	# ---------------------------------------------------------------------------
	# Preset Management
	# ---------------------------------------------------------------------------

	def get_preset_list(self, bank):
		logging.info('Getting Preset List for %s: NOT IMPLEMENTED!' % self.name)

	def set_preset(self, layer, preset):
		self.zyngui.zynmidi.set_midi_preset(layer.get_midi_chan(), preset[1][0], preset[1][1], preset[1][2])

	def cmp_presets(self, preset1, preset2):
		if preset1[1][0]==preset2[1][0] and preset1[1][1]==preset2[1][1] and preset1[1][2]==preset2[1][2]:
			return True
		else:
			return False

	# ---------------------------------------------------------------------------
	# Controllers Management
	# ---------------------------------------------------------------------------

	# Get zynthian controllers dictionary:
	# + Default implementation uses a static controller definition array
	def get_controllers_dict(self, layer):
		midich=layer.get_midi_chan()
		zctrls=OrderedDict()
		for ctrl in self._ctrls:
			if len(ctrl)>4:
				zctrl=zynthian_controller(self,ctrl[4],ctrl[0])
				zctrl.setup_controller(midich,ctrl[1],ctrl[2],ctrl[3])
			elif len(ctrl)>3:
				zctrl=zynthian_controller(self,ctrl[0])
				zctrl.setup_controller(midich,ctrl[1],ctrl[2],ctrl[3])
			else:
				zctrl=zynthian_controller(self,ctrl[0])
				zctrl.setup_controller(midich,ctrl[1],ctrl[2])
			zctrls[ctrl[0]]=zctrl
		return zctrls

	def send_controller_value(self, zctrl):
		raise Exception("NOT DEFINED")

	# ---------------------------------------------------------------------------
	# Layer "Path" String
	# ---------------------------------------------------------------------------

	def get_path(self, layer):
		return self.nickname

#******************************************************************************
