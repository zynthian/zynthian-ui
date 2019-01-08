#!/usr/bin/python3
# -*- coding: utf-8 -*-
#******************************************************************************
# ZYNTHIAN PROJECT: Zynthian GUI
# 
# Zynthian GUI Admin Class
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
import sys
import signal
import socket
import psutil
import logging
from time import sleep
from threading  import Thread
from subprocess import check_output, Popen, PIPE

# Zynthian specific modules
import zynconf
from . import zynthian_gui_config
from . import zynthian_gui_selector

#------------------------------------------------------------------------------
# Configure logging
#------------------------------------------------------------------------------

# Set root logging level
logging.basicConfig(stream=sys.stderr, level=zynthian_gui_config.log_level)

#-------------------------------------------------------------------------------
# Zynthian Admin GUI Class
#-------------------------------------------------------------------------------
class zynthian_gui_admin(zynthian_gui_selector):

	data_dir = os.environ.get('ZYNTHIAN_DATA_DIR',"/zynthian/zynthian-data")
	sys_dir = os.environ.get('ZYNTHIAN_SYS_DIR',"/zynthian/zynthian-sys")


	def __init__(self):
		self.commands=None
		self.thread=None
		self.child_pid=None
		self.last_action=None
		super().__init__('Action', True)
		self.default_qmidinet()


	def fill_list(self):
		self.list_data=[]

		self.list_data.append((self.audio_recorder,0,"Audio Recorder"))
		self.list_data.append((self.midi_recorder,0,"MIDI Recorder"))

		self.list_data.append((self.do_nothing,0,"-----------------------------"))

		if zynthian_gui_config.midi_single_active_channel:
			self.list_data.append((self.toggle_single_channel,0,"[x] Single Channel Mode"))
		else:
			self.list_data.append((self.toggle_single_channel,0,"[  ] Single Channel Mode"))

		self.list_data.append((self.midi_profile,0,"MIDI Profile"))

		self.list_data.append((self.do_nothing,0,"-----------------------------"))
		self.list_data.append((self.network_info,0,"Network Info"))

		if self.is_wifi_active():
			self.list_data.append((self.stop_wifi,0,"[x] WIFI"))
		else:
			self.list_data.append((self.start_wifi,0,"[  ] WIFI"))

		if self.is_service_active("qmidinet"):
			self.list_data.append((self.stop_qmidinet,0,"[x] QMidiNet"))
		else:
			self.list_data.append((self.start_qmidinet,0,"[  ] QMidiNet"))

		if os.environ.get('ZYNTHIAN_TOUCHOSC'):
			if self.is_service_active("touchosc2midi"):
				self.list_data.append((self.stop_touchosc2midi,0,"[x] TouchOSC"))
			else:
				self.list_data.append((self.start_touchosc2midi,0,"[  ] TouchOSC"))

		if os.environ.get('ZYNTHIAN_AUBIONOTES'):
			if self.is_service_active("aubionotes"):
				self.list_data.append((self.stop_aubionotes,0,"[x] Audio->MIDI"))
			else:
				self.list_data.append((self.start_aubionotes,0,"[  ] Audio->MIDI"))

		self.list_data.append((self.do_nothing,0,"-----------------------------"))
		self.list_data.append((self.test_audio,0,"Test Audio"))
		self.list_data.append((self.test_midi,0,"Test MIDI"))
		self.list_data.append((self.do_nothing,0,"-----------------------------"))
		self.list_data.append((self.update_software,0,"Update Software"))
		#self.list_data.append((self.update_library,0,"Update Zynthian Library"))
		#self.list_data.append((self.update_system,0,"Update Operating System"))
		self.list_data.append((self.restart_gui,0,"Restart UI"))
		#self.list_data.append((self.exit_to_console,0,"Exit to Console"))
		self.list_data.append((self.reboot,0,"Reboot"))
		self.list_data.append((self.power_off,0,"Power Off"))
		super().fill_list()


	def select_action(self, i, t='S'):
		self.last_action=self.list_data[i][0]
		self.last_action()


	def set_select_path(self):
		self.select_path.set("Admin")


	def is_process_running(self, procname):
		cmd="ps -e | grep %s" % procname
		try:
			result=check_output(cmd, shell=True).decode('utf-8','ignore')
			if len(result)>3: return True
			else: return False
		except Exception as e:
			return False


	def is_service_active(self, service):
		cmd="systemctl is-active %s" % service
		try:
			result=check_output(cmd, shell=True).decode('utf-8','ignore')
		except Exception as e:
			result="ERROR: %s" % e
		#print("Is service "+str(service)+" active? => "+str(result))
		if result.strip()=='active': return True
		else: return False


	def get_netinfo(self, exclude_down=True):
		netinfo={}
		for ifc, snics in psutil.net_if_addrs().items():
			if ifc=="lo":
				continue
			for snic in snics:
				if snic.family == socket.AF_INET:
					netinfo[ifc]=snic
			if ifc not in netinfo:
				c=0
				for snic in snics:
					if snic.family == socket.AF_INET6:
						c+=1
				if c>=2:
					netinfo[ifc]=snic
			if ifc not in netinfo and not exclude_down:
				netinfo[ifc]=None
		return netinfo


	def is_wifi_active(self):
		for ifc in self.get_netinfo():
			if ifc.startswith("wlan"):
				return True


	def execute_commands(self):
		self.zyngui.start_loading()
		
		error_counter=0
		for cmd in self.commands:
			logging.info("Executing Command: %s" % cmd)
			self.zyngui.add_info("EXECUTING:\n","EMPHASIS")
			self.zyngui.add_info("{}\n".format(cmd))
			try:
				self.proc=Popen(cmd, shell=True, stdout=PIPE, stderr=PIPE, universal_newlines=True)
				self.zyngui.add_info("RESULT:\n","EMPHASIS")
				for line in self.proc.stdout:
					if re.search("ERROR", line, re.IGNORECASE):
						error_counter+=1
						tag="ERROR"
					elif re.search("Already", line, re.IGNORECASE):
						tag="SUCCESS"
					else:
						tag=None
					logging.info(line.rstrip())
					self.zyngui.add_info(line,tag)
				self.zyngui.add_info("\n")
			except Exception as e:
				logging.error(e)
				self.zyngui.add_info("ERROR: %s\n" % e, "ERROR")

		if error_counter>0:
			logging.info("COMPLETED WITH {} ERRORS!".format(error_counter))
			self.zyngui.add_info("COMPLETED WITH {} ERRORS!".format(error_counter), "WARNING")
		else:
			logging.info("COMPLETED OK!")
			self.zyngui.add_info("COMPLETED OK!", "SUCCESS")

		self.commands=None
		self.zyngui.add_info("\n\n")
		self.zyngui.hide_info_timer(5000)
		self.zyngui.stop_loading()
		self.fill_list()


	def start_command(self,cmds):
		if not self.commands:
			logging.info("Starting Command Sequence ...")
			self.commands=cmds
			self.thread=Thread(target=self.execute_commands, args=())
			self.thread.daemon = True # thread dies with the program
			self.thread.start()


	def killable_execute_commands(self):
		#self.zyngui.start_loading()
		for cmd in self.commands:
			logging.info("Executing Command: %s" % cmd)
			self.zyngui.add_info("EXECUTING:\n","EMPHASIS")
			self.zyngui.add_info("{}\n".format(cmd))
			try:
				proc=Popen(cmd.split(" "), stdout=PIPE, stderr=PIPE)
				self.child_pid=proc.pid
				self.zyngui.add_info("\nPID: %s" % self.child_pid)
				(output, error)=proc.communicate()
				self.child_pid=None
				if error:
					result="ERROR: %s" % error
					logging.error(result)
					self.zyngui.add_info(result,"ERROR")
				else:
					logging.info(output)
					self.zyngui.add_info(output)
			except Exception as e:
				result="ERROR: %s" % e
				logging.error(result)
				self.zyngui.add_info(result,"ERROR")

		self.commands=None
		self.zyngui.hide_info_timer(5000)
		#self.zyngui.stop_loading()
		self.fill_list()


	def killable_start_command(self,cmds):
		if not self.commands:
			logging.info("Starting Command Sequence ...")
			self.commands=cmds
			self.thread=Thread(target=self.killable_execute_commands, args=())
			self.thread.daemon = True # thread dies with the program
			self.thread.start()


	def kill_command(self):
		if self.child_pid:
			logging.info("Killing process %s" % self.child_pid)
			os.kill(self.child_pid, signal.SIGTERM)
			self.child_pid=None
			if self.last_action==self.test_midi:
				check_output("systemctl stop a2jmidid", shell=True)
				self.zyngui.all_sounds_off()


	def do_nothing(self):
		pass


	def toggle_single_channel(self):
		if zynthian_gui_config.midi_single_active_channel:
			logging.info("Single Channel Mode OFF")
			zynthian_gui_config.midi_single_active_channel=False
		else:
			logging.info("Single Channel Mode ON")
			zynthian_gui_config.midi_single_active_channel=True

		# Update MIDI profile
		zynconf.update_midi_profile({ 
			"ZYNTHIAN_MIDI_SINGLE_ACTIVE_CHANNEL": str(int(zynthian_gui_config.midi_single_active_channel))
		})

		self.zyngui.set_active_channel()
		sleep(0.5)
		self.fill_list()


	def audio_recorder(self):
		logging.info("Audio Recorder")
		self.zyngui.show_modal("audio_recorder")


	def midi_recorder(self):
		logging.info("MIDI Recorder")
		self.zyngui.show_modal("midi_recorder")


	def midi_profile(self):
		logging.info("MIDI Profile")
		self.zyngui.show_modal("midi_profile")


	def network_info(self):
		logging.info("NETWORK INFO")
		self.zyngui.show_info("NETWORK INFO\n")
		self.zyngui.add_info(" Link-Local Name => {}.local\n".format(os.uname().nodename),"SUCCESS")
		for ifc, snic in self.get_netinfo().items():
			if snic.family==socket.AF_INET and snic.address:
				self.zyngui.add_info(" {} => {}\n".format(ifc,snic.address),"SUCCESS")
			else:
				self.zyngui.add_info(" {} => {}\n".format(ifc,"connecting..."),"WARNING")
		self.zyngui.hide_info_timer(5000)
		self.zyngui.stop_loading()


	def start_wifi(self):
		logging.info("STARTING WIFI")
		for ifc in self.get_netinfo(False):
			if ifc.startswith("wlan"):
				logging.info("Starting %s ..." % ifc)
				try:
					check_output("ifconfig {} up".format(ifc), shell=True)
				except Exception as e:
					logging.error(e)
		sleep(3)
		self.fill_list()


	def stop_wifi(self):
		logging.info("STOPPING WIFI")
		for ifc in self.get_netinfo():
			if ifc.startswith("wlan"):
				logging.info("Stopping %s ..." % ifc)
				try:
					check_output("ifconfig {} down".format(ifc), shell=True)
				except Exception as e:
					logging.error(e)
		sleep(1)
		self.fill_list()


	def start_qmidinet(self):
		logging.info("STARTING QMIDINET")
		try:
			check_output("systemctl start qmidinet", shell=True)
		except Exception as e:
			logging.error(e)
		self.fill_list()


	def stop_qmidinet(self):
		logging.info("STOPPING QMIDINET")
		try:
			check_output("systemctl stop qmidinet", shell=True)
		except Exception as e:
			logging.error(e)
		self.fill_list()


	#Start/Stop QMidiNet depending on configuration
	def default_qmidinet(self):
		if int(os.environ.get('ZYNTHIAN_MIDI_NETWORK_ENABLED',0)):
			self.start_qmidinet()
		else:
			self.stop_qmidinet()


	def start_touchosc2midi(self):
		logging.info("STARTING touchosc2midi")
		check_output("systemctl start touchosc2midi", shell=True)
		self.fill_list()


	def stop_touchosc2midi(self):
		logging.info("STOPPING touchosc2midi")
		check_output("systemctl stop touchosc2midi", shell=True)
		self.fill_list()


	def start_aubionotes(self):
		logging.info("STARTING aubionotes")
		check_output("systemctl start aubionotes", shell=True)
		self.fill_list()


	def stop_aubionotes(self):
		logging.info("STOPPING aubionotes")
		check_output("systemctl stop aubionotes", shell=True)
		self.fill_list()


	def test_audio(self):
		logging.info("TESTING AUDIO")
		self.zyngui.show_info("TEST AUDIO")
		self.killable_start_command(["mpg123 {}/audio/test.mp3".format(self.data_dir)])

	def test_midi(self):
		logging.info("TESTING MIDI")
		self.zyngui.show_info("TEST MIDI")
		check_output("systemctl start a2jmidid", shell=True)
		self.killable_start_command(["aplaymidi -p 14 {}/mid/test.mid".format(self.data_dir)])


	def update_software(self):
		logging.info("UPDATE SOFTWARE")
		self.zyngui.show_info("UPDATE SOFTWARE")
		self.start_command([self.sys_dir + "/scripts/update_zynthian.sh"])

	def update_library(self):
		logging.info("UPDATE LIBRARY")
		self.zyngui.show_info("UPDATE LIBRARY")
		self.start_command([self.sys_dir + "/scripts/update_zynthian_data.sh"])


	def update_system(self):
		logging.info("UPDATE SYSTEM")
		self.zyngui.show_info("UPDATE SYSTEM")
		self.start_command([self.sys_dir + "/scripts/update_system.sh"])


	def restart_gui(self):
		logging.info("RESTART GUI")
		self.last_state_action()
		self.zyngui.exit(102)


	def exit_to_console(self):
		logging.info("EXIT TO CONSOLE")
		self.last_state_action()
		self.zyngui.exit(101)


	def reboot(self):
		self.zyngui.show_confirm("Do you really want to reboot?", self.reboot_confirmed, [100])


	def reboot_confirmed(self, params):
		logging.info("REBOOT")
		self.last_state_action()
		self.zyngui.exit(params[0])


	def power_off(self):
		self.zyngui.show_confirm("Do you really want to power off?", self.power_off_confirmed, [0])


	def power_off_confirmed(self, params):
		logging.info("POWER OFF")
		self.last_state_action()
		self.zyngui.exit(params[0])


	def last_state_action(self):
		if zynthian_gui_config.restore_last_state:
			self.zyngui.screens['snapshot'].save_default_snapshot()
		else:
			self.zyngui.screens['snapshot'].delete_default_snapshot()


#------------------------------------------------------------------------------
