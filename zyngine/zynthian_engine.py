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
from json import JSONEncoder, JSONDecoder

#------------------------------------------------------------------------------
# OSC Port for Synth Engines
#------------------------------------------------------------------------------

osc_port=6693

#------------------------------------------------------------------------------
# Synth Engine Base Class
#------------------------------------------------------------------------------

class zynthian_engine:
	name=""
	nickname=""
	parent=None

	audio_driver="jack"
	midi_driver="jack"

	command=None
	command_env=None
	proc=None

	queue=None
	thread_queue=None

	user_gid=1000
	user_uid=1000

	osc_target=None
	osc_target_port=osc_port
	osc_server=None
	osc_server_port=None
	osc_server_url=None

	bank_list=[]
	instr_list=[]

	max_chan=16
	midi_chan=0

	loading=0
	snapshot_fpath=None
	loading_snapshot=False

	bank_index=[0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0]
	bank_name=["","","","","","","","","","","","","","","",""]
	bank_set=[None,None,None,None,None,None,None,None,None,None,None,None,None,None,None,None]

	instr_index=[0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0]
	instr_name=["","","","","","","","","","","","","","","",""]
	instr_set=[None,None,None,None,None,None,None,None,None,None,None,None,None,None,None,None]

	ctrl_config=[None,None,None,None,None,None,None,None,None,None,None,None,None,None,None,None]

	default_ctrl_list=[
		[[
			['volume',7,96,127],
			['modulation',1,0,127],
			['filter Q',71,64,127],
			['filter cutoff',74,64,127]
		],0,'main'],
		[[
			['volume',7,96,127],
			['expression',11,127,127],
			['reverb',91,64,127],
			['chorus',93,2,127]
		],0,'effects']
	]
	ctrl_list=default_ctrl_list

	def __init__(self, parent=None):
		self.parent=parent
		self.clean()
		self.start()

	def __del__(self):
		#self.stop()
		self.clean()

	def clean(self):
		self.midi_chan=0
		if not self.loading_snapshot:
			for i in range(16):
				self.bank_index[i]=0
				self.bank_name[i]=""
				self.bank_set[i]=None
				self.instr_index[i]=0
				self.instr_name[i]=""
				self.instr_set[i]=None
				self.ctrl_config[i]=None

	def reset(self):
		self.clean()

	def start_loading(self):
		self.loading=self.loading+1
		if self.loading<1: self.loading=1
		self.parent.start_loading()

	def stop_loading(self):
		self.loading=self.loading-1
		if self.loading<0: self.loading=0
		self.parent.stop_loading()

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

	def chuser(self):
		def result():
			os.setgid(self.user_gid)
			os.setuid(self.user_uid)
		return result

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
				#logging.debug("proc command: "+cmd)
				#self.proc.stdin.write(bytes(cmd + "\n", 'UTF-8'))
				self.proc.stdin.write(cmd + "\n")
				self.proc.stdin.flush()
				out=self.proc_get_lines(tout)
				#logging.debug("proc output:\n%s" % (out))
			except Exception as err:
				out=""
				logging.error("Can't exec engine command: %s => %s" % (cmd,err))
			self.stop_loading()
			return out

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

	def set_midi_chan(self, i):
		logging.info('MIDI Chan Selected: ' + str(i))
		self.midi_chan=i
		#self.load_bank_list()
		#self.set_bank(self.get_bank_index())

	def next_chan(self):
		count=0
		nchan=len(self.bank_index)
		i=self.midi_chan
		while count<nchan:
			i+=1
			count+=1
			if i>=nchan:
				i=0
			if self.instr_name[i]:
				break
		if self.midi_chan!=i:
			self.set_midi_chan(i)
			return True
		else:
			return False

	def get_midi_chan(self):
		return self.midi_chan

	def get_bank_index(self):
		return self.bank_index[self.midi_chan]

	def get_bank_name(self):
		return self.bank_name[self.midi_chan]

	def get_instr_index(self):
		return self.instr_index[self.midi_chan]

	def get_instr_name(self):
		return self.instr_name[self.midi_chan]

	def get_ctrl_list(self):
		try:
			return self.ctrl_config[self.midi_chan]
		except:
			return self.ctrl_list

	def get_ctrl_config(self, i):
		try:
			return self.ctrl_config[self.midi_chan][i][0]
		except:
			return None

	def reset_instr(self, chan=None):
		if chan is None:
			chan=self.midi_chan
		self.instr_index[chan]=0
		self.instr_name[chan]=None

	def refresh(self):
		pass

	def load_bank_filelist(self, dpath, fext):
		logging.info('Getting Bank List for ' + self.name)
		self.start_loading()
		self.bank_list=[]
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
					#print("bank_filelist => "+title)
					self.bank_list.append((join(dp,f),i,title,dn))
					i=i+1
		self.stop_loading()

	def load_bank_dirlist(self,dpath):
		logging.info('Getting Bank List for ' + self.name)
		self.start_loading()
		self.bank_list=[]
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
					#print("bank_dirlist => "+title)
					self.bank_list.append((join(dp,f),i,title,dn))
					i=i+1
		self.stop_loading()

	def load_bank_cmdlist(self,cmd):
		logging.info('Getting Bank List for ' + self.name)
		self.start_loading()
		self.bank_list=[]
		i=0
		output=check_output(cmd, shell=True)
		lines=output.decode('utf8').split('\n')
		for f in lines:
			title=str.replace(f, '_', ' ')
			self.bank_list.append((f,i,title))
			i=i+1
		self.stop_loading()

	def load_bank_list(self):
		self.bank_list=[]

	def load_instr_list(self):
		self.instr_list=[]

	def load_ctrl_config(self, chan=None):
		if chan is None:
			chan=self.midi_chan
		self.ctrl_config[chan]=copy.deepcopy(self.ctrl_list)

	def set_ctrl_value(self, ctrl, val):
		ctrl[2]=val

	def set_bank(self, i, chan=None):
		if chan is None:
			chan=self.midi_chan
		if self.bank_list[i]:
			last_bank_index=self.bank_index[chan]
			self.bank_index[chan]=i
			self.bank_name[chan]=self.bank_list[i][2]
			self.bank_set[chan]=copy.deepcopy(self.bank_list[i])
			logging.info('Bank Selected: ' + self.bank_name[chan] + ' (' + str(i)+')')
			self._set_bank(self.bank_list[i], chan)
			if chan==self.midi_chan:
				pass
				#self.load_instr_list()
			if last_bank_index!=i:
				self.reset_instr(chan)

	def _set_bank(self, bank, chan=None):
		if chan is None:
			chan=self.midi_chan
		self.parent.zynmidi.set_midi_bank_msb(chan, bank[1])

	def set_all_bank(self):
		#logging.debug("set_all_bank()")
		for ch in range(16):
			if self.bank_set[ch]:
				self._set_bank(self.bank_set[ch],ch)

	def set_instr(self, i, chan=None, set_midi=True):
		if chan is None:
			chan=self.midi_chan
		if self.instr_list[i]:
			last_instr_index=self.instr_index[chan]
			last_instr_name=self.instr_name[chan]
			self.instr_index[chan]=i
			self.instr_name[chan]=self.instr_list[i][2]
			self.instr_set[chan]=copy.deepcopy(self.instr_list[i])
			logging.info('Instrument Selected: ' + self.instr_name[chan] + ' (' + str(i)+')')
			#=> '+self.instr_list[i][3]
			if set_midi:
				self._set_instr(self.instr_list[i],chan)
			if last_instr_index!=i or not last_instr_name:
				self.load_ctrl_config(chan)

	def _set_instr(self, instr, chan=None):
		if chan is None:
			chan=self.midi_chan
		self.parent.zynmidi.set_midi_instr(chan, instr[1][0], instr[1][1], instr[1][2])

	def set_all_instr(self):
		#logging.debug("set_all_instr()")
		for ch in range(16):
			if self.instr_set[ch]:
				self._set_instr(self.instr_set[ch],ch)

	#Send Controller Values to Synth
	def set_all_ctrl(self):
		#logging.debug("set_all_ctrl()")
		for ch in range(16):
			if self.ctrl_config[ch]:
				for ctrlcfg in self.ctrl_config[ch]:
					for ctrl in ctrlcfg[0]:
						if isinstance(ctrl[1],str):
							liblo.send(self.osc_target,ctrl[1],self.get_ctrl_osc_val(ctrl[2],ctrl[3]))
						elif ctrl[1]>0:
							self.parent.zynmidi.set_midi_control(ch,ctrl[1],self.get_ctrl_midi_val(ctrl[2],ctrl[3]))

	def get_ctrl_midi_val(self, val, maxval):
		if isinstance(val,int):
			return val
		if isinstance(maxval,str):
			values=maxval.split('|')
		elif isinstance(maxval,list):
			if isinstance(maxval[0],list): 
				values=maxval[0]
				ticks=maxval[1]
			else: values=maxval
		elif max_val>0:
			values=None
			max_value=n_values=maxval
		if values:
			n_values=len(values)
			step=max(1,int(16/n_values));
			max_value=128-step;
			try:
				val=ticks[values.index(val)]
			except:
				val=int(values.index(val)*max_value/(n_values-1))
		if val>max_value:
			val=max_value
		return val

	def get_ctrl_osc_val(self, val, maxval):
		if maxval=='off|on':
			if val=='on': return True
			elif val=='off': return False
		return val

	def get_path(self, chan=None):
		if chan is None:
			chan=self.midi_chan
		path=self.bank_name[chan]
		if self.instr_name[chan]:
			path=path + '/' + self.instr_name[chan]
		return path

	def get_fullpath(self, chan=None):
		if chan is None:
			chan=self.midi_chan
		return self.nickname + "#" + str(chan+1) + " > " + self.get_path(chan)

	def save_snapshot(self, fpath):
		status={
			'engine': self.name,
			'engine_nick': self.nickname,
			'midi_chan': self.midi_chan,
			'max_chan': self.max_chan,
			'bank_index': self.bank_index,
			'bank_name': self.bank_name,
			'bank_set': self.bank_set,
			'instr_index': self.instr_index,
			'instr_name': self.instr_name,
			'instr_set': self.instr_set,
			'ctrl_config': self.ctrl_config
		}
		try:
			json=JSONEncoder().encode(status)
			logging.info("Saving snapshot %s => \n%s" % (fpath,json))
		except:
			logging.error("Can't generate snapshot")
			return False

		try:
			with open(fpath,"w") as fh:
				fh.write(json)
		except:
			logging.error("Can't save snapshot '%s'" % fpath)
			return False
		self.snapshot_fpath=fpath
		return True

	def _load_snapshot(self, fpath):
		self.loading_snapshot=True
		try:
			with open(fpath,"r") as fh:
				json=fh.read()
				logging.info("Loading snapshot %s => \n%s" % (fpath,json))
		except:
			logging.error("Can't load snapshot '%s'" % fpath)
			return False
		try:
			status=JSONDecoder().decode(json)
			if self.name!=status['engine'] or self.nickname!=status['engine_nick']:
				raise UserWarning("Incorrect Engine " + status['engine'])
			self.midi_chan=status['midi_chan']
			self.max_chan=status['max_chan']
			self.bank_index=status['bank_index']
			self.bank_name=status['bank_name']
			self.bank_set=status['bank_set']
			self.instr_index=status['instr_index']
			self.instr_name=status['instr_name']
			self.instr_set=status['instr_set']
			self.ctrl_config=status['ctrl_config']
			self.snapshot_fpath=fpath
		except UserWarning as e:
			logging.error("%s" % e)
			return False
		except Exception as e:
			logging.error("Invalid snapshot format. %s" % e)
			return False

	def load_snapshot(self, fpath):
		self._load_snapshot(fpath)
		return self.load_snapshot_post()

	def load_snapshot_post(self):
		try:
			self.set_all_bank()
			self.load_bank_list()
			self.set_all_instr()
			self.load_instr_list()
			sleep(0.2)
			self.set_all_ctrl()
			self.parent.refresh_screen()
			self.loading_snapshot=False
			return True
		except Exception as e:
			logging.error("%s" % e)
			return False

	def all_sounds_off(self):
		for chan in range(16):
			self.parent.zynmidi.set_midi_control(chan, 120, 0)

#******************************************************************************
