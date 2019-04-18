# -*- coding: utf-8 -*-
#******************************************************************************
# ZYNTHIAN PROJECT: Zynthian Engine (zynthian_engine_modui)
# 
# zynthian_engine implementation for MOD-UI (LV2 plugin host)
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
import copy
import logging
import requests
import websocket
from time import sleep
from subprocess import check_output
from threading  import Thread
from collections import OrderedDict
from . import zynthian_engine
from . import zynthian_controller

#------------------------------------------------------------------------------
# MOD-UI Engine Class
#------------------------------------------------------------------------------

class zynthian_engine_modui(zynthian_engine):


	# ---------------------------------------------------------------------------
	# Initialization
	# ---------------------------------------------------------------------------


	def __init__(self, zyngui=None):
		super().__init__(zyngui)

		self.type = "Special"
		self.name = "MOD-UI"
		self.nickname = "MD"
		self.jackname = "mod-host"

		self.audio_out = []
		self.options= {
			'clone': False,
			'transpose': False,
			'audio_route': False,
			'midi_chan': False
		}

		self.base_api_url = 'http://localhost:8888'
		self.websocket_url = 'ws://localhost:8888/websocket'
		self.websocket = None
		self.ws_thread = None
		self.ws_preset_loaded = False

		self.bank_dirs = [
			('_', self.my_data_dir + "/mod-pedalboards")
		]
		self.hw_ports = {}

		self.reset()
		self.start()


	def reset(self):
		super().reset()
		self.graph = {}
		self.plugin_info = OrderedDict()
		self.plugin_zctrls = OrderedDict()


	def start(self):
		self.start_loading()
		if not self.is_service_active("mod-ui"):
			logging.info("STARTING MOD-HOST & MOD-UI services...")
			check_output(("systemctl start mod-host && systemctl start mod-ui"),shell=True)
		self.stop_loading()


	def stop(self):
		self.start_loading()
		#self.stop_websocket()
		if self.is_service_active("mod-ui"):
			logging.info("STOPPING MOD-HOST & MOD-UI services...")
			#check_output(("systemctl stop mod-host && systemctl stop mod-ui"),shell=True)
			check_output(("systemctl stop mod-ui"),shell=True)
		self.stop_loading()


	def is_service_active(self, service="mod-ui"):
		cmd="systemctl is-active "+str(service)
		try:
			result=check_output(cmd, shell=True).decode('utf-8','ignore')
		except Exception as e:
			result="ERROR: "+str(e)
		if result.strip()=='active': return True
		else: return False


	# ---------------------------------------------------------------------------
	# Layer Management
	# ---------------------------------------------------------------------------


	def add_layer(self, layer):
		super().add_layer(layer)
		if not self.ws_thread:
			self.start_websocket()


	def del_layer(self, layer):
		super().del_layer(layer)
		self.graph_reset()


	#----------------------------------------------------------------------------
	# Bank Managament
	#----------------------------------------------------------------------------


	def get_bank_list(self, layer=None):
		return self.get_dirlist(self.bank_dirs)


	def set_bank(self, layer, bank):
		self.load_bundle(bank[0])
		return True


	def load_bundle(self, path):
		self.graph_reset()
		res = self.api_post_request("/pedalboard/load_bundle/",data={'bundlepath':path})
		if not res or not res['ok']:
			logging.error("Loading Bundle "+path)
		else:
			return res['name']


	#----------------------------------------------------------------------------
	# Preset Managament
	#----------------------------------------------------------------------------


	def get_num_of_plugins_with_presets(self):
		n=0
		for pgraph in self.plugin_info:
			if len(self.plugin_info[pgraph]['presets'])>0:
				n+=1

		return n


	def get_preset_list(self, bank):
		npwp=self.get_num_of_plugins_with_presets()

		preset_list = []
		for pgraph in self.plugin_info:
			preset_dict = OrderedDict()

			for prs in self.plugin_info[pgraph]['presets']:
				
				#if npwp>1:
				#	title = self.plugin_info[pgraph]['name'] + '/' + prs['label']
				#else:
				#	title = prs['label']

				title = prs['label']

				preset_dict[prs['uri']] = len(preset_list)
				preset_list.append((prs['uri'], [0,0,0], title, pgraph))
				logging.debug("Add Preset " + title)

			self.plugin_info[pgraph]['presets_dict'] = preset_dict

		return preset_list


	def set_preset(self, layer, preset, preload=False):
		self.load_preset(preset[3],preset[0])
		return True


	def load_preset(self, plugin, preset):
		self.ws_preset_loaded = False
		res = self.api_get_request("/effect/preset/load/"+plugin, data={'uri':preset})
		i=0
		while not self.ws_preset_loaded and i<100: 
			sleep(0.1)
			i=i+1


	def cmp_presets(self, preset1, preset2):
		try:
			if preset1[3]==preset2[3]:
				return True
			else:
				return False
		except:
			return False

	#----------------------------------------------------------------------------
	# Controllers Managament
	#----------------------------------------------------------------------------


	def get_controllers_dict(self, layer):
		zctrls=OrderedDict()
		self._ctrl_screens=[]
		try:
			for pgraph in sorted(self.plugin_info, key=lambda k: self.plugin_info[k]['posx']):
				#logging.debug("PLUGIN %s => X=%s" % (pgraph,self.plugin_info[pgraph]['posx']))
				c=1
				ctrl_set=[]
				for param in self.plugin_info[pgraph]['ports']['control']['input']:
					try:
						#logging.debug("CTRL LIST PLUGIN %s PARAM %s" % (pgraph,ctrl))
						zctrls[param['ctrl'].graph_path]=param['ctrl']
						ctrl_set.append(param['ctrl'].graph_path)
						if len(ctrl_set)>=4:
							#logging.debug("ADDING CONTROLLER SCREEN #"+str(c))
							self._ctrl_screens.append([self.plugin_info[pgraph]['name']+'#'+str(c),ctrl_set])
							ctrl_set=[]
							c=c+1
					except Exception as err:
						logging.error("Generating Controller Screens: %s => %s" % (pgraph, err))
				if len(ctrl_set)>=1:
					#logging.debug("ADDING CONTROLLER SCREEN #"+str(c))
					self._ctrl_screens.append([self.plugin_info[pgraph]['name']+'#'+str(c),ctrl_set])
		except Exception as err:
			logging.error("Generating Controller List: %s" % err)
		return zctrls


	def send_controller_value(self, zctrl):
		self.websocket.send("param_set %s %.6f" % (zctrl.graph_path, zctrl.value))
		logging.debug("WS << param_set %s %.6f" % (zctrl.graph_path, zctrl.value))


	#----------------------------------------------------------------------------
	# Websocket & MOD-UI API Management
	#----------------------------------------------------------------------------


	def start_websocket(self):
		logging.info("Connecting to MOD-UI websocket...")
		i=0
		while i<100:
			try:
				self.websocket = websocket.create_connection(self.websocket_url)
				break
			except:
				i=i+1
				sleep(0.1)
		if i<100:
			self.ws_thread=Thread(target=self.task_websocket, args=())
			self.ws_thread.daemon = True # thread dies with the program
			self.ws_thread.start()
			return True
		else:
			return False 


	def stop_websocket(self):
		logging.info("Closing MOD-UI websocket...")
		if self.websocket:
			self.websocket.close()


	def task_websocket(self):
		error_counter=0
		self.enable_midi_devices()
		while True:
			try:
				received =  self.websocket.recv()
				logging.debug("WS >> %s" % received)
				args = received.split() 
				command = args[0]

				if command == "ping":
					self.enable_midi_devices()
					self.websocket.send("pong")
					logging.debug("WS << pong")

				elif command == "add_hw_port":
					if args[3]=='1': pdir="output"
					else: pdir="input"
					self.add_hw_port_cb(args[2],pdir,args[1],args[4],args[5])

				elif command == "add":
					if args[2][0:4] == "http":
						logging.info("ADD PLUGIN: "+args[1]+" => "+args[2])
						self.add_plugin_cb(args[1],args[2],args[3],args[4])

				elif command == "remove":
					if args[1] == ":all":
						logging.info("REMOVE ALL PLUGINS")
						self.reset()
					elif args[1]:
						logging.info("REMOVE PLUGIN: "+args[1])
						self.remove_plugin_cb(args[1])

				elif command == "connect":
					self.graph_connect_cb(args[1],args[2])

				elif command == "disconnect":
					self.graph_disconnect_cb(args[1],args[2])

				elif command == "preset":
					self.preset_cb(args[1],args[2])

				elif command == "param_set":
					self.set_param_cb(args[1],args[2],args[3])

				elif command == "midi_map":
					self.midi_map_cb(args[1],args[2],args[3],args[4])

				elif command == "loading_start":
						logging.info("LOADING START")
						self.start_loading()

				elif command == "loading_end":
					logging.info("LOADING END")
					self.graph_autoconnect_midi_input()
					self.stop_loading()

				elif command == "bundlepath":
					logging.info("BUNDLEPATH %s" % args[1])
					self.bundlepath_cb(args[1])

				elif command == "stop":
					logging.error("Restarting MOD services ...")
					self.stop()
					self.start()

			except websocket._exceptions.WebSocketConnectionClosedException:
				if self.is_service_active("mod-ui"):
					try:
						logging.error("Connection Closed. Retrying to connect ...")
						self.websocket = websocket.create_connection(self.websocket_url)
						error_counter=0
					except:
						if error_counter>100:
							logging.error("Re-connection failed. Restarting MOD services ...")
							self.stop()
							self.start()
							self.set_bank(self.layers[0],self.layers[0].bank_info)
							error_counter=0
						else:
							error_counter+=1
							sleep(0.1)
				else:
					logging.error("Connection Closed & MOD-UI stopped. Finishing...")
					self.ws_thread=None
					return
			except Exception as e:
				logging.error("task_websocket() => %s (%s)" % (e,type(e)))
				sleep(1)


	def api_get_request(self, path, data=None, json=None):
		self.start_loading()
		res=requests.get(self.base_api_url + path, data=data, json=json)
		self.stop_loading()
		if res.status_code != 200:
			logging.error("GET call to MOD-UI API: "+str(res.status_code) + " => " +self.base_api_url + path)
		else:
			return res.json()


	def api_post_request(self, path, data=None, json=None):
		self.start_loading()
		res=requests.post(self.base_api_url + path, data=data, json=json)
		self.stop_loading()
		if res.status_code != 200:
			logging.error("POST call to MOD-UI API: "+str(res.status_code) + " => " +self.base_api_url + path)
		else:
			return res.json()


	def bundlepath_cb(self, bpath):
		bdirname=bpath.split('/')[-1]
		if bdirname!='default.pedalboard':
			#Find bundle_path in bank list ...
			layer=self.layers[0]
			for i in range(len(layer.bank_list)):
				#logging.debug("BUNDLE PATH SEARCH => %s <=> %s" % (layer.bank_list[i][0].split('/')[-1], bdirname))
				if layer.bank_list[i][0].split('/')[-1]==bdirname:
					bank_index=i
					bank_name=layer.bank_list[i][2]
					#Set Bank in GUI, layer and engine without reloading the bundle
					logging.info('Bank Selected from Bundlepath: ' + bank_name + ' (' + str(i)+')')
					self.zyngui.screens['bank'].select(i)
					layer.set_bank(i,False)
					#Show preset screen
					self.zyngui.show_screen('preset')
					break


	def add_hw_port_cb(self, ptype, pdir, pgraph, pname, pnum):
		if ptype not in self.hw_ports:
			self.hw_ports[ptype]={}
		if pdir not in self.hw_ports[ptype]:
			self.hw_ports[ptype][pdir]={}
		self.hw_ports[ptype][pdir][pgraph]={'name':pname,'num':pnum}
		self.graph_autoconnect_midi_input()
		logging.debug("ADD_HW_PORT => "+pgraph+", "+ptype+", "+pdir)


	def add_plugin_cb(self, pgraph, puri, posx, posy):
		self.start_loading()
		pinfo=self.api_get_request("/effect/get",data={'uri':puri})
		if pinfo:
			self.plugin_zctrls[pgraph]={}
			#Add parameters to dictionary
			for param in pinfo['ports']['control']['input']:
				try:
					ctrl_graph=pgraph+'/'+param['symbol']
					#If there is range info (should be!!) ...
					if param['valid'] and param['ranges'] and len(param['ranges'])>2:

						if param['properties'] and 'integer' in param['properties']:
							is_integer=True
						else:
							is_integer=False

						#If there is Scale Points info ...
						if param['scalePoints'] and len(param['scalePoints'])>1:
							labels=[]
							values=[]
							for p in param['scalePoints']:
								if p['valid']:
									labels.append(p['label'])
									values.append(p['value'])
							try:
								val=param['ranges']['default']
							except:
								val=values[0]

							param['ctrl']=zynthian_controller(self,param['symbol'],param['shortName'],{
								'graph_path': ctrl_graph,
								'value': val,
								'labels': labels,
								'ticks': values,
								'value_min': 0,
								'value_max': len(values)-1,
								'is_toggle': False,
								'is_integer': is_integer
							})

						#If it's a normal controller ...
						else:
							pranges=param['ranges']
							r=pranges['maximum']-pranges['minimum']
							if is_integer:
								if r==1:
									val=pranges['default']
									param['ctrl']=zynthian_controller(self,param['symbol'],param['shortName'],{
										'graph_path': ctrl_graph,
										'value': val,
										'labels': ['off','on'],
										'ticks': [0,1],
										'value_min': 0,
										'value_max': 1,
										'is_toggle': True,
										'is_integer': True
									})
								else:
									param['ctrl']=zynthian_controller(self,param['symbol'],param['shortName'],{
										'graph_path': ctrl_graph,
										'value': int(pranges['default']),
										'value_default': int(pranges['default']),
										'value_min': int(pranges['minimum']),
										'value_max': int(pranges['maximum']),
										'is_toggle': False,
										'is_integer': True
									})
							else:
								param['ctrl']=zynthian_controller(self,param['symbol'],param['shortName'],{
									'graph_path': ctrl_graph,
									'value': pranges['default'],
									'value_default': pranges['default'],
									'value_min': pranges['minimum'],
									'value_max': pranges['maximum'],
									'is_toggle': False,
									'is_integer': False
								})

					#If there is no range info (should be!!) => Default MIDI CC controller with 0-127 range
					else:
						param['ctrl']=zynthian_controller(self,param['symbol'],param['shortName'],{
							'graph_path': ctrl_graph,
							'value': 0,
							'value_default': 0,
							'value_min': 0,
							'value_max': 127,
							'is_toggle': False,
							'is_integer': True
						})

					#Add ZController to plugin_zctrl dictionary
					self.plugin_zctrls[pgraph][param['symbol']]=param['ctrl']
				except Exception as err:
					logging.error("Configuring Controllers: "+pgraph+" => "+str(err))

			#Add bypass Zcontroller
			bypass_zctrl=zynthian_controller(self,'bypass','bypass',{
				'graph_path': pgraph+'/:bypass',
				'value': 0,
				'labels': ['off','on'],
				'values': [0,1],
				'value_min': 0,
				'value_max': 1,
				'is_toggle': True,
				'is_integer': True
			})

			self.plugin_zctrls[pgraph][':bypass']=bypass_zctrl
			pinfo['ports']['control']['input'].insert(0,{'symbol':':bypass', 'ctrl':bypass_zctrl})
			#Add position info
			pinfo['posx']=int(round(float(posx)))
			pinfo['posy']=int(round(float(posy)))
			#Add to info array
			self.plugin_info[pgraph]=pinfo
			#Set Refresh
			self.refresh_all()
			self.stop_loading()


	def remove_plugin_cb(self, pgraph):
		self.start_loading()
		if pgraph in self.graph:
			del self.graph[pgraph]
		if pgraph in self.plugin_zctrls:
			del self.plugin_zctrls[pgraph]
		if pgraph in self.plugin_info:
			del self.plugin_info[pgraph]
		#Set Refresh
		self.refresh_all()
		self.stop_loading()


	def graph_connect_cb(self, src, dest):
		if src not in self.graph:
			self.graph[src]=[]
		self.graph[src].append(dest)


	def graph_disconnect_cb(self, src, dest):
		if src in self.graph:
			if dest in self.graph[src]:
				self.graph[src].remove(dest)


	def graph_reset(self):
		graph=copy.deepcopy(self.graph)
		for src in graph:
			for dest in graph[src]:
				self.api_get_request("/effect/disconnect/"+src+","+dest)
				#print("API /effect/disconnect/"+src+","+dest)
		self.api_get_request("/reset")


	#Connect unconnected MIDI-USB devices to the "input plugin" ...
	def graph_autoconnect_midi_input(self):
		midi_master="/graph/serial_midi_in"
		if midi_master in self.graph:
			for dest in self.graph[midi_master]:
				for src in self.hw_ports['midi']['input']:
					if src not in self.graph:
						self.api_get_request("/effect/connect/"+src+","+dest)


	def enable_midi_devices(self):
		res=self.api_get_request("/jack/get_midi_devices")
		#logging.debug("API /jack/get_midi_devices => "+str(res))
		if 'devList' in res:
			data=[]
			for dev in res['devList']: 
				#if dev not in res['devsInUse']: 
				data.append(dev)
			if len(data)>0:
				self.api_post_request("/jack/set_midi_devices",json=data)
				#print("API /jack/set_midi_devices => "+str(data))


	def set_param_cb(self, pgraph, symbol, val):
		try:
			zctrl=self.plugin_zctrls[pgraph][symbol]
			zctrl.value=float(val)

			#Refresh GUI controller in screen when needed ...
			if self.zyngui.active_screen=='control' and self.zyngui.screens['control'].mode=='control':
				self.zyngui.screens['control'].set_controller_value(zctrl)

		except Exception as err:
			logging.error("Parameter Not Found: "+pgraph+"/"+symbol+" => "+str(err))
			#TODO: catch different types of exception


	def preset_cb(self, pgraph, uri):
		try:
			i=self.plugin_info[pgraph]['presets_dict'][uri]
			self.layers[0].set_preset(i, False)
			self.zyngui.screens['control'].set_select_path()

		except Exception as e:
			logging.error("Preset Not Found: {}/{} => {}".format(pgraph, uri, e))

		self.ws_preset_loaded = True


	#----------------------------------------------------------------------------
	# MIDI learning
	#----------------------------------------------------------------------------


	def init_midi_learn(self, zctrl):
		logging.info("Learning '%s' ..." % zctrl.graph_path)
		res = self.api_post_request("/effect/parameter/address/"+zctrl.graph_path,json=self.get_parameter_address_data(zctrl,"/midi-learn"))


	def midi_unlearn(self, zctrl):
		logging.info("Unlearning '%s' ..." % zctrl.graph_path)
		try:
			pad=self.get_parameter_address_data(zctrl,"null")
			if self.api_post_request("/effect/parameter/address/"+zctrl.graph_path,json=pad):
				return zctrl._unset_midi_learn()

		except Exception as e:
			logging.warning("Can't unlearn => {}".format(e))



	def set_midi_learn(self, zctrl, chan, cc):
		try:
			if zctrl.graph_path and chan is not None and cc is not None:
				logging.info("Set MIDI map '{}' => {}, {}" % (zctrl.graph_path, chan, cc))
				uri="/midi-custom_Ch.{}_CC#{}".format(chan+1, cc)
				pad=self.get_parameter_address_data(zctrl,uri)
				if self.api_post_request("/effect/parameter/address/"+zctrl.graph_path,json=pad):
					return zctrl._set_midi_learn(chan, cc)

		except Exception as e:
				logging.warning("Can't learn => {}".format(e))


	def midi_map_cb(self, pgraph, symbol, chan, cc):
		logging.info("MIDI Map: %s %s => %s, %s" % (pgraph,symbol,chan,cc))
		try:
			self.plugin_zctrls[pgraph][symbol]._cb_midi_learn(int(chan),int(cc))
		except Exception as err:
			logging.error("Parameter Not Found: "+pgraph+"/"+symbol+" => "+str(err))


	def get_parameter_address_data(self, zctrl, uri):
		if isinstance(zctrl.labels,list):
			steps=len(zctrl.labels)
		else:
			steps=127
		data={
			"uri": uri,
			"label": zctrl.short_name,
			"minimum": str(zctrl.value_min),
			"maximum": str(zctrl.value_max),
			"value": str(zctrl.value),
			"steps": str(steps)
		}
		#{"uri":"/midi-learn","label":"Record","minimum":"0","maximum":"1","value":0,"steps":"1"}
		#{"uri":"/midi-learn","label":"SooperLooper","minimum":0,"maximum":1,"value":0}
		#{"uri":"/midi-learn","label":"Reset","minimum":"0","maximum":"1","value":0,"steps":"1"}
		logging.debug("Parameter Address Data => %s" % str(data))
		return data


#******************************************************************************
